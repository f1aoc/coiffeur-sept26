"""Langue de BridgeToLeads : français ou anglais.

Les textes sont écrits en français dans le code, entourés de _("…") ; traductions_en.py donne leur
traduction anglaise (texte français → texte anglais).
Langue utilisée, par ordre de priorité : variable BRIDGETOLEADS_LANGUE, choix enregistré dans
l'application (definir_langue), puis langue de l'ordinateur (anglais si ce n'est pas le français).
"""

from __future__ import annotations

import locale
import os
import sys

from traductions_en import TRADUCTIONS as _EN

LANGUES = ("fr", "en")
AUTO = "auto"
VARIABLE = "BRIDGETOLEADS_LANGUE"
TRADUCTIONS = {"en": _EN}

_choix = AUTO  # choix enregistré dans l'application : "auto", "fr" ou "en"


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


def _(texte: str) -> str:
    """Texte français → sa traduction dans la langue courante (le texte français s'il n'est pas traduit)."""
    langue = langue_courante()
    if langue == "fr" or not texte:
        return texte
    return TRADUCTIONS[langue].get(texte, texte)


def pluriel(n: int, un: str, plusieurs: str, **valeurs) -> str:
    """Singulier si n vaut 1 (ou 0 en français), pluriel sinon ; {n} et les autres valeurs sont insérés."""
    singulier = n == 1 or (n == 0 and langue_courante() == "fr")
    return _(un if singulier else plusieurs).format(n=n, **valeurs)
