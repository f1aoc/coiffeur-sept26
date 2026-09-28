"""Import de la liste de prospects depuis un CSV.

Toutes les colonnes sont optionnelles : nom, url, téléphone, adresse, catégorie.
Les en-têtes sont reconnus sans tenir compte de la casse, des accents ni des
espaces, avec quelques synonymes courants (« site web », « tel »…).
Le séparateur (virgule, point-virgule, tabulation) est détecté automatiquement.
"""

from __future__ import annotations

import csv
import io
import unicodedata
from pathlib import Path

from chasseur.modeles import Prospect


class ErreurImport(ValueError):
    pass


SYNONYMES = {
    "nom": {"nom", "name", "entreprise", "raison sociale", "societe", "commerce"},
    "url": {"url", "site", "site web", "site internet", "website", "web"},
    "telephone": {"telephone", "tel", "phone", "portable", "numero"},
    "adresse": {"adresse", "address", "adresse postale"},
    "categorie": {"categorie", "category", "activite", "secteur", "metier"},
}


def _normaliser(texte: str) -> str:
    sans_accents = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    return " ".join(sans_accents.lower().replace("_", " ").replace("-", " ").split())


def _correspondance_colonnes(entetes: list[str]) -> dict[str, str]:
    """Associe chaque champ du Prospect à l'en-tête CSV correspondant."""
    correspondance: dict[str, str] = {}
    for entete in entetes:
        cle = _normaliser(entete or "")
        for champ, noms in SYNONYMES.items():
            if cle in noms and champ not in correspondance:
                correspondance[champ] = entete
    return correspondance


def _lire_texte(chemin: Path) -> str:
    donnees = chemin.read_bytes()
    try:
        return donnees.decode("utf-8-sig")
    except UnicodeDecodeError:
        return donnees.decode("cp1252")  # CSV exporté par Excel en français


def importer_csv(chemin: str | Path) -> list[Prospect]:
    chemin = Path(chemin)
    if not chemin.is_file():
        raise ErreurImport(f"Fichier introuvable : {chemin}")
    texte = _lire_texte(chemin)
    if not texte.strip():
        return []

    try:
        dialecte = csv.Sniffer().sniff(texte.splitlines()[0], delimiters=",;\t")
    except csv.Error:
        dialecte = csv.excel

    lecteur = csv.DictReader(io.StringIO(texte, newline=""), dialect=dialecte)
    correspondance = _correspondance_colonnes(lecteur.fieldnames or [])
    if not correspondance:
        raise ErreurImport(
            f"Aucune colonne reconnue dans {chemin.name} (en-têtes lus : {lecteur.fieldnames}). "
            "Colonnes attendues : nom, url, téléphone, adresse, catégorie."
        )

    prospects = []
    for ligne in lecteur:
        numero = lecteur.line_num  # ligne physique dans le fichier
        valeurs = {champ: (ligne.get(entete) or "").strip() for champ, entete in correspondance.items()}
        if not any(valeurs.values()):
            continue
        prospects.append(Prospect(ligne=numero, **valeurs))
    return prospects
