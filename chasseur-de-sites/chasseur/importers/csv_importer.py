"""Import de la liste de prospects (CSV ou Excel).

Toutes les colonnes sont optionnelles : nom, url, téléphone, adresse, catégorie.
Les en-têtes sont reconnus sans tenir compte de la casse, des accents ni des
espaces, avec quelques synonymes courants (« site web », « tel »…).
Le séparateur (virgule, point-virgule, tabulation) est détecté automatiquement.
Le format de l'outil Google Maps existant est reconnu (voir fichiers.py).
"""

from __future__ import annotations

from pathlib import Path

from chasseur.importers.fichiers import ErreurImport, lire_prospects
from chasseur.modeles import Prospect

__all__ = ["ErreurImport", "importer_csv"]


def importer_csv(chemin: str | Path) -> list[Prospect]:
    return lire_prospects(chemin).prospects
