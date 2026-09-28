"""Reprise après interruption (§6.3).

Chaque site terminé est ajouté immédiatement à un journal JSON Lines placé à
côté du CSV de sortie. Relancer la même commande ignore les sites déjà
présents dans le journal ; le journal est supprimé quand le scan se termine.
Les scores des sites repris sont recalculés avec la config actuelle.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from chasseur.config import Config
from chasseur.modeles import Constat, Prospect, Resultat
from chasseur.scoring import noter


def cle(prospect: Prospect) -> str:
    return f"{prospect.nom.strip().lower()}|{prospect.url.strip().lower().rstrip('/')}"


def chemin_journal(sortie: Path) -> Path:
    return sortie.with_name(sortie.name + ".journal.jsonl")


def resultat_en_dict(r: Resultat) -> dict:
    return asdict(r)


def resultat_depuis_dict(d: dict, config: Config) -> Resultat:
    r = Resultat(
        prospect=Prospect(**d["prospect"]),
        constats=[Constat(**c) for c in d.get("constats", [])],
        mesures=d.get("mesures", {}),
        non_verifies=d.get("non_verifies", {}),
        sans_objet=d.get("sans_objet", []),
        echecs=d.get("echecs", []),
    )
    for c in r.constats:  # les poids ont pu changer entre-temps
        c.points = config.points_du_code(c.code)
    return noter(r, config)


class Journal:
    def __init__(self, chemin: Path):
        self.chemin = chemin
        self._fichier = None

    def charger(self, config: Config) -> dict[str, Resultat]:
        faits: dict[str, Resultat] = {}
        if not self.chemin.is_file():
            return faits
        with self.chemin.open(encoding="utf-8") as f:
            for ligne in f:
                try:
                    r = resultat_depuis_dict(json.loads(ligne), config)
                except (ValueError, KeyError, TypeError):
                    continue  # dernière ligne tronquée par l'interruption
                faits[cle(r.prospect)] = r
        return faits

    def ecrire(self, r: Resultat) -> None:
        if self._fichier is None:
            self.chemin.parent.mkdir(parents=True, exist_ok=True)
            self._fichier = self.chemin.open("a", encoding="utf-8")
        self._fichier.write(json.dumps(resultat_en_dict(r), ensure_ascii=False) + "\n")
        self._fichier.flush()

    def fermer(self) -> None:
        if self._fichier is not None:
            self._fichier.close()
            self._fichier = None

    def supprimer(self) -> None:
        self.fermer()
        self.chemin.unlink(missing_ok=True)
