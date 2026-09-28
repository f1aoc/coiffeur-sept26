"""Réglages de l'agence (en-tête et pied des rapports PDF, signature des messages)."""

from __future__ import annotations

import base64
import io
import re
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass

from sqlmodel import Session

from chasseur.db import reglages
from chasseur.db.moteur import Stockage

TAILLE_LOGO_MAX = 2 * 1024 * 1024
COULEUR_DEFAUT = "#1f5fbf"
APPEL_DEFAUT = (
    "Ces problèmes se corrigent. Contactez-nous pour en parler, sans engagement : "
    "nous vous montrerons ce qu'il faudrait faire pour que votre site travaille à nouveau pour vous."
)
RE_COULEUR = re.compile(r"^#[0-9a-fA-F]{6}$")
RE_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# Tout ce qui pourrait exécuter du code dans un SVG
RE_SVG_DANGEREUX = re.compile(r"<script|javascript:|<foreignObject|\son\w+\s*=|<!ENTITY", re.IGNORECASE)
CHAMPS = ("nom", "couleur", "telephone", "email", "site", "appel")


class ErreurAgence(ValueError):
    pass


@dataclass
class Agence:
    nom: str = ""
    couleur: str = COULEUR_DEFAUT
    telephone: str = ""
    email: str = ""
    site: str = ""
    appel: str = APPEL_DEFAUT
    logo: str = ""  # chemin relatif au dossier de données

    @property
    def nom_affiche(self) -> str:
        return self.nom or "[votre agence]"

    @property
    def coordonnees(self) -> list[str]:
        return [c for c in (self.telephone, self.email, self.site) if c]


def lire_agence(session: Session) -> Agence:
    a = Agence()
    for champ in CHAMPS + ("logo",):
        valeur = reglages.lire(session, f"agence_{champ}", "")
        if valeur:
            setattr(a, champ, valeur)
    return a


def ecrire_agence(session: Session, **valeurs: str) -> Agence:
    a = lire_agence(session)
    for champ in CHAMPS:
        if champ in valeurs:
            setattr(a, champ, (valeurs[champ] or "").strip())
    if not RE_COULEUR.match(a.couleur):
        raise ErreurAgence("Couleur invalide : choisissez une couleur au format #1f5fbf.")
    if a.email and not RE_EMAIL.match(a.email):
        raise ErreurAgence("Adresse e-mail de l'agence invalide.")
    a.appel = a.appel or APPEL_DEFAUT
    for champ in CHAMPS:
        reglages.ecrire(session, f"agence_{champ}", getattr(a, champ))
    return a


def _controler_logo(nom_fichier: str, contenu: bytes) -> str:
    """Renvoie l'extension (png ou svg) si le fichier est un logo acceptable."""
    if len(contenu) > TAILLE_LOGO_MAX:
        raise ErreurAgence("Logo trop lourd (2 Mo maximum).")
    extension = nom_fichier.rsplit(".", 1)[-1].lower() if "." in nom_fichier else ""
    if extension == "png":
        from PIL import Image

        try:
            with Image.open(io.BytesIO(contenu)) as image:
                if image.format != "PNG":
                    raise ValueError
                image.verify()
        except Exception:
            raise ErreurAgence("Ce fichier n'est pas une image PNG valide.") from None
        return "png"
    if extension == "svg":
        texte = contenu.decode("utf-8", errors="replace")
        if RE_SVG_DANGEREUX.search(texte):
            raise ErreurAgence("Ce SVG contient du code (script, événements) : il est refusé par sécurité.")
        try:
            racine = ET.fromstring(contenu)
        except ET.ParseError:
            raise ErreurAgence("Ce fichier n'est pas un SVG valide.") from None
        if not racine.tag.endswith("svg"):
            raise ErreurAgence("Ce fichier n'est pas un SVG valide.")
        return "svg"
    raise ErreurAgence("Le logo doit être un fichier PNG ou SVG.")


def enregistrer_logo(stockage: Stockage, session: Session, nom_fichier: str, contenu: bytes) -> str:
    extension = _controler_logo(nom_fichier, contenu)
    dossier = stockage.dossier / "agence"
    dossier.mkdir(exist_ok=True)
    for ancien in dossier.glob("logo.*"):
        ancien.unlink()
    chemin = dossier / f"logo.{extension}"
    chemin.write_bytes(contenu)
    relatif = stockage.relatif(chemin)
    reglages.ecrire(session, "agence_logo", relatif)
    return relatif


def supprimer_logo(stockage: Stockage, session: Session) -> None:
    for ancien in (stockage.dossier / "agence").glob("logo.*"):
        ancien.unlink()
    reglages.supprimer(session, "agence_logo")


def logo_data_uri(stockage: Stockage, agence: Agence) -> str:
    """Logo intégré au PDF (data: URI), vide s'il n'y en a pas."""
    if not agence.logo:
        return ""
    chemin = stockage.absolu(agence.logo)
    if not chemin.is_file():
        return ""
    type_mime = "image/svg+xml" if chemin.suffix == ".svg" else "image/png"
    return f"data:{type_mime};base64,{base64.b64encode(chemin.read_bytes()).decode()}"


def en_dict(agence: Agence) -> dict:
    return asdict(agence)
