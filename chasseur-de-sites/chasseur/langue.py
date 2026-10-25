"""Langue de Chasseur de sites : français ou anglais.

Les textes sont écrits en français dans le code et les gabarits, entourés de _("…") ;
langues/en.yaml donne leur traduction anglaise (texte français → texte anglais).
Langue utilisée, par ordre de priorité : variable CHASSEUR_LANGUE, réglage enregistré dans
l'interface (definir_langue), puis langue de l'ordinateur (anglais si ce n'est pas le français).
"""

from __future__ import annotations

import locale
import os
import sys
from functools import lru_cache
from pathlib import Path

import yaml

DOSSIER = Path(__file__).parent / "langues"
LANGUES = ("fr", "en")
AUTO = "auto"
VARIABLE = "CHASSEUR_LANGUE"
LANGUE = "langue"  # clé du réglage enregistré en base
MOIS = {
    "fr": ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"),
    "en": ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"),
}

_choix = AUTO  # réglage de l'interface : "auto", "fr" ou "en"


def langue_systeme() -> str:
    """Langue de l'ordinateur : "fr" si elle est le français, sinon "en"."""
    codes: list[str] = []
    if sys.platform == "win32":
        try:
            import ctypes

            codes.append(locale.windows_locale.get(ctypes.windll.kernel32.GetUserDefaultUILanguage(), ""))
        except (AttributeError, OSError):
            pass
    codes += [os.environ.get(v, "") for v in ("LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE")]
    try:
        codes.append(locale.getlocale()[0] or "")
    except ValueError:
        pass
    for code in codes:
        if code and code.split(".")[0] not in ("C", "POSIX"):
            return "fr" if code.lower().startswith(("fr", "french")) else "en"
    return "fr"


def definir_langue(choix: str | None) -> None:
    global _choix
    _choix = choix if choix in LANGUES else AUTO


def langue_courante() -> str:
    variable = os.environ.get(VARIABLE, "").lower()
    if variable in LANGUES:
        return variable
    return _choix if _choix in LANGUES else langue_systeme()


@lru_cache(maxsize=None)
def traductions(langue: str) -> dict[str, str]:
    fichier = DOSSIER / f"{langue}.yaml"
    if not fichier.is_file():
        return {}
    with fichier.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _(texte: str) -> str:
    """Texte français → sa traduction dans la langue courante (le texte français s'il n'est pas traduit)."""
    langue = langue_courante()
    if langue == "fr" or not texte:
        return texte
    return traductions(langue).get(texte, texte)


def date_longue(d) -> str:
    """12 août 2026 / August 12, 2026 (1er en français)."""
    if langue_courante() == "fr":
        return f"{'1er' if d.day == 1 else d.day} {MOIS['fr'][d.month - 1]} {d.year}"
    return f"{MOIS['en'][d.month - 1]} {d.day}, {d.year}"


def date_courte(d) -> str:
    """25/10/2026 ou 2026-10-25."""
    return d.strftime("%d/%m/%Y" if langue_courante() == "fr" else "%Y-%m-%d")


def nombre(valeur) -> str:
    """Virgule décimale en français, point en anglais."""
    texte = str(valeur)
    return texte.replace(".", ",") if langue_courante() == "fr" else texte.replace(",", ".")
