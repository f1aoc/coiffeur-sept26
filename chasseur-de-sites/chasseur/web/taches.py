"""Scans en tâche de fond dans la boucle asyncio du serveur web.

- Chaque site terminé est enregistré aussitôt en base : un scan interrompu
  (fermeture de l'application, coupure) reprend là où il s'était arrêté.
- Pause : plus aucun site ne démarre ; les sites en cours se terminent.
- Temps restant estimé à partir de la vitesse observée depuis le dernier
  (re)démarrage, pauses exclues.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from sqlmodel import select

from chasseur.analyzers import Analyseur
from chasseur.config import Config, charger_config
from chasseur.db import depot
from chasseur.db.moteur import Stockage
from chasseur.db.reglages import config_effective
from chasseur.db.tables import EN_COURS, EN_ERREUR, EN_PAUSE, INTERROMPU, TERMINE, Scan, maintenant
from chasseur.modeles import Resultat
from chasseur.orchestrateur import analyseurs_par_defaut, analyser_prospects

journal = logging.getLogger("chasseur.web")

FabriqueAnalyseurs = Callable[[Config], list[Analyseur]]


@dataclass
class Suivi:
    """Vitesse d'un scan, pauses exclues."""

    faits: int = 0
    duree_active: float = 0.0
    depuis: float | None = None

    def demarrer(self) -> None:
        if self.depuis is None:
            self.depuis = time.monotonic()

    def arreter(self) -> None:
        if self.depuis is not None:
            self.duree_active += time.monotonic() - self.depuis
            self.depuis = None

    def restant(self, reste: int) -> float | None:
        actif = self.duree_active + (time.monotonic() - self.depuis if self.depuis else 0)
        if self.faits == 0 or reste <= 0:
            return None if reste > 0 else 0.0
        return actif / self.faits * reste


class GestionnaireScans:
    def __init__(
        self,
        stockage: Stockage,
        fabrique_analyseurs: FabriqueAnalyseurs | None = None,
        chemin_config: str | Path | None = None,
    ):
        self.stockage = stockage
        self._fabrique = fabrique_analyseurs or analyseurs_par_defaut
        self._chemin_config = chemin_config
        self._taches: dict[int, asyncio.Task] = {}
        self._portes: dict[int, asyncio.Event] = {}
        self.suivis: dict[int, Suivi] = {}

    # --- Cycle de vie de l'application ---------------------------------------------

    def au_demarrage(self) -> None:
        """Les scans « en cours » d'une session précédente ont été interrompus."""
        with self.stockage.session() as s:
            for scan in s.exec(select(Scan).where(Scan.statut.in_([EN_COURS, EN_PAUSE]))):
                scan.statut = INTERROMPU
                s.add(scan)
            s.commit()

    async def arreter(self) -> None:
        for tache in list(self._taches.values()):
            tache.cancel()
        for tache in list(self._taches.values()):
            try:
                await tache
            except (asyncio.CancelledError, Exception):
                pass

    def config(self) -> Config:
        with self.stockage.session() as s:
            return config_effective(self.stockage, s, charger_config(self._chemin_config))

    # --- Commandes ------------------------------------------------------------------

    def en_cours(self, scan_id: int) -> bool:
        tache = self._taches.get(scan_id)
        return tache is not None and not tache.done()

    def lancer(self, scan_id: int) -> None:
        if self.en_cours(scan_id):
            return
        porte = asyncio.Event()
        porte.set()
        self._portes[scan_id] = porte
        self.suivis[scan_id] = Suivi()
        self._taches[scan_id] = asyncio.get_running_loop().create_task(self._executer(scan_id, porte))

    def pause(self, scan_id: int) -> None:
        if not self.en_cours(scan_id):
            return
        self._portes[scan_id].clear()
        self.suivis[scan_id].arreter()
        self._statut(scan_id, EN_PAUSE)

    def reprendre(self, scan_id: int) -> None:
        if self.en_cours(scan_id):
            self._portes[scan_id].set()
            self.suivis[scan_id].demarrer()
            self._statut(scan_id, EN_COURS)
        else:
            self.lancer(scan_id)  # scan interrompu : on relance les sites non analysés

    def restant(self, scan_id: int, reste: int) -> float | None:
        suivi = self.suivis.get(scan_id)
        return suivi.restant(reste) if suivi else None

    # --- Exécution ------------------------------------------------------------------

    def _statut(self, scan_id: int, statut: str, erreur: str = "") -> None:
        with self.stockage.session() as s:
            scan = s.get(Scan, scan_id)
            scan.statut = statut
            if statut == EN_COURS and scan.demarre_le is None:
                scan.demarre_le = maintenant()
            if statut == TERMINE:
                scan.termine_le = maintenant()
            if erreur:
                scan.erreur = erreur
            s.add(scan)
            s.commit()

    async def _executer(self, scan_id: int, porte: asyncio.Event) -> None:
        suivi = self.suivis[scan_id]
        config: Config | None = None
        try:
            config = self.config()
            config.navigateur.dossier_captures = str(self.stockage.dossier_captures / f"scan-{scan_id}")
            with self.stockage.session() as s:
                prospects = [depot.vers_prospect(p) for p in depot.a_analyser(s, scan_id)]
            self._statut(scan_id, EN_COURS)
            suivi.demarrer()

            def progression(_fait: int, _total: int, r: Resultat) -> None:
                with self.stockage.session() as s:
                    depot.enregistrer_resultat(self.stockage, s, r.prospect.ligne, r)
                suivi.faits += 1

            await analyser_prospects(prospects, config, self._fabrique(config), progression=progression, porte=porte)
            suivi.arreter()
            self._statut(scan_id, TERMINE)
        except asyncio.CancelledError:
            suivi.arreter()
            self._statut(scan_id, INTERROMPU)
            raise
        except Exception as e:  # noqa: BLE001 — l'erreur est affichée sur l'écran Progression
            suivi.arreter()
            message = f"{type(e).__name__} : {str(e)[:300]}"
            cle = config.performance.cle if config else ""
            if cle:
                message = message.replace(cle, "***")  # §6.4 : jamais de clé API à l'écran ni au journal
            journal.error("scan %s en erreur : %s", scan_id, message)
            self._statut(scan_id, EN_ERREUR, message)
