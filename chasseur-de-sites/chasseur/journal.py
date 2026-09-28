"""Journal des erreurs sans données sensibles (§6.4).

Fichier <dossier de données>/erreurs.log (1 Mo, 3 fichiers en rotation).
Avant écriture, chaque ligne est nettoyée : clés API connues, paramètres
« key= » d'URL, clés au format Google (AIza…) et adresses e-mail sont masqués.
"""

from __future__ import annotations

import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path

NOM_FICHIER = "erreurs.log"
_SECRETS: set[str] = set()
MOTIFS = [
    (re.compile(r"AIza[0-9A-Za-z_\-]{20,}"), "***"),
    (re.compile(r"((?:api[_-]?)?key|token|secret|password|mot_de_passe)=([^&\s\"']+)", re.I), r"\1=***"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[e-mail masqué]"),
]


def enregistrer_secret(valeur: str) -> None:
    """Déclare une valeur à ne jamais écrire dans le journal (ex. clé API saisie dans les Réglages)."""
    if valeur and len(valeur) >= 6:
        _SECRETS.add(valeur)


def nettoyer(texte: str) -> str:
    for secret in sorted(_SECRETS, key=len, reverse=True):
        texte = texte.replace(secret, "***")
    for motif, remplacement in MOTIFS:
        texte = motif.sub(remplacement, texte)
    return texte


class _Nettoyeur(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return nettoyer(super().format(record))


def configurer(dossier: Path) -> Path:
    """Installe le fichier journal (une seule fois par dossier) et renvoie son chemin."""
    chemin = Path(dossier) / NOM_FICHIER
    racine = logging.getLogger("chasseur")
    racine.setLevel(logging.INFO)
    if not any(getattr(h, "baseFilename", None) == str(chemin) for h in racine.handlers):
        gestionnaire = RotatingFileHandler(chemin, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        gestionnaire.setLevel(logging.WARNING)
        gestionnaire.setFormatter(_Nettoyeur("%(asctime)s %(levelname)s %(name)s : %(message)s", "%Y-%m-%d %H:%M:%S"))
        racine.addHandler(gestionnaire)
    return chemin


def dernieres_lignes(chemin: Path, n: int = 50) -> list[str]:
    if not chemin.is_file():
        return []
    return chemin.read_text(encoding="utf-8", errors="replace").splitlines()[-n:]
