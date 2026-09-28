"""Chiffrement local des clés API (§6.4).

Les clés sont chiffrées (Fernet : AES-128 + HMAC) avec une clé maîtresse
générée au premier lancement dans <dossier de données>/cle.secret, lisible
par l'utilisateur seul. Elles ne sont jamais affichées en clair dans
l'interface ni écrites dans un export.
"""

from __future__ import annotations

import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

NOM_CLE = "cle.secret"


class ErreurSecret(ValueError):
    pass


def _cle_maitresse(dossier: Path) -> bytes:
    chemin = dossier / NOM_CLE
    if chemin.is_file():
        return chemin.read_bytes().strip()
    cle = Fernet.generate_key()
    descripteur = os.open(chemin, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descripteur, "wb") as f:
        f.write(cle)
    return cle


def chiffrer(dossier: Path, texte: str) -> str:
    return Fernet(_cle_maitresse(dossier)).encrypt(texte.encode()).decode()


def dechiffrer(dossier: Path, jeton: str) -> str:
    try:
        return Fernet(_cle_maitresse(dossier)).decrypt(jeton.encode()).decode()
    except InvalidToken:
        raise ErreurSecret("clé API illisible (fichier cle.secret remplacé ?) : ressaisissez-la dans les Réglages") from None


def masquer(cle: str) -> str:
    """« AIzaSyD…Xk3Q » → « ••••••••Xk3Q » pour l'affichage."""
    return "••••••••" + cle[-4:] if len(cle) > 4 else "••••"
