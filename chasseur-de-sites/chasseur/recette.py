"""Recette du classement (§7.2) : « chasseur recette jeu.csv ».

Le CSV contient les colonnes habituelles (nom, url…) et une colonne « attendu »
(Cassé, Obsolète ou Correct). Les sites sont analysés normalement et l'état
obtenu est comparé à l'attendu. Objectif du cahier des charges : au moins 90 %.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from chasseur.analyzers import Analyseur
from chasseur.config import Config
from chasseur.importers.fichiers import ErreurImport, lire_prospects, lire_tableau, normaliser
from chasseur.modeles import Resultat
from chasseur.orchestrateur import analyser_prospects

ETATS = {"casse": "Cassé", "obsolete": "Obsolète", "correct": "Correct"}
OBJECTIF = 0.90


@dataclass
class LigneRecette:
    nom: str
    url: str
    attendu: str
    obtenu: str
    score: int
    codes: list[str]

    @property
    def conforme(self) -> bool:
        return self.attendu == self.obtenu


@dataclass
class Recette:
    lignes: list[LigneRecette] = field(default_factory=list)
    duree: float = 0.0

    @property
    def taux(self) -> float:
        return sum(l.conforme for l in self.lignes) / len(self.lignes) if self.lignes else 0.0

    @property
    def reussie(self) -> bool:
        return self.taux >= OBJECTIF

    def par_categorie(self) -> dict[str, tuple[int, int]]:
        """Catégorie attendue → (bien classés, total)."""
        sortie = {}
        for etat in ETATS.values():
            lignes = [l for l in self.lignes if l.attendu == etat]
            sortie[etat] = (sum(l.conforme for l in lignes), len(lignes))
        return sortie


def lire_attendus(chemin: Path) -> dict[int, str]:
    entetes, lignes = lire_tableau(chemin)
    colonne = next((e for e in entetes if normaliser(e) in ("attendu", "etat attendu", "categorie attendue")), None)
    if colonne is None:
        raise ErreurImport("Colonne « attendu » absente (valeurs : Cassé, Obsolète ou Correct).")
    attendus = {}
    for numero, ligne in lignes:
        valeur = ETATS.get(normaliser(ligne.get(colonne, "")))
        if valeur is None:
            raise ErreurImport(f"Ligne {numero} : « attendu » doit valoir Cassé, Obsolète ou Correct.")
        attendus[numero] = valeur
    return attendus


async def recetter(chemin: str | Path, config: Config, analyseurs: list[Analyseur] | None = None) -> Recette:
    chemin = Path(chemin)
    attendus = lire_attendus(chemin)
    prospects = lire_prospects(chemin).prospects
    debut = time.monotonic()
    resultats: list[Resultat] = await analyser_prospects(prospects, config, analyseurs)
    recette = Recette(duree=time.monotonic() - debut)
    for r in resultats:
        codes = [c.code for c in r.constats if c.code != "NON_VERIFIE"]
        recette.lignes.append(
            LigneRecette(r.prospect.nom, r.prospect.url, attendus.get(r.prospect.ligne, ""), r.etat, r.score, codes)
        )
    return recette


def afficher(recette: Recette) -> str:
    lignes = [f"{'':2} {'Nom':32} {'Attendu':9} {'Obtenu':13} Score  Constats"]
    for l in recette.lignes:
        marque = "✓" if l.conforme else "✗"
        lignes.append(f"{marque:2} {l.nom[:32]:32} {l.attendu:9} {l.obtenu:13} {l.score:>5}  {', '.join(l.codes)[:70]}")
    lignes.append("")
    for etat, (bons, total) in recette.par_categorie().items():
        if total:
            lignes.append(f"{etat:9} : {bons}/{total}")
    bons = sum(l.conforme for l in recette.lignes)
    lignes.append(
        f"Taux de bon classement : {recette.taux * 100:.0f} % ({bons}/{len(recette.lignes)}) — objectif {OBJECTIF * 100:.0f} % : "
        f"{'ATTEINT' if recette.reussie else 'NON ATTEINT'} · durée {recette.duree:.0f} s"
    )
    return "\n".join(lignes)
