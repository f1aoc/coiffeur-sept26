"""Tous les textes français affichés par Chasseur de sites (pour langues/en.yaml et son test)."""

from __future__ import annotations

import ast
import re
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent / "chasseur"


def _textes_python() -> set[str]:
    textes = set()
    for fichier in RACINE.rglob("*.py"):
        if "__pycache__" in fichier.parts:
            continue
        for noeud in ast.walk(ast.parse(fichier.read_text(encoding="utf-8"))):
            if (isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Name) and noeud.func.id == "_"
                    and noeud.args and isinstance(noeud.args[0], ast.Constant) and isinstance(noeud.args[0].value, str)):
                textes.add(noeud.args[0].value)
    return textes


def _textes_gabarits() -> set[str]:
    textes = set()
    for gabarit in list(RACINE.glob("web/templates/*.html")) + list(RACINE.glob("reports/templates/*.html")):
        contenu = gabarit.read_text(encoding="utf-8")
        textes |= {t.replace('\\"', '"') for t in re.findall(r'_\("((?:[^"\\]|\\.)*)"\)', contenu)}
        textes |= {t.replace("\\'", "'") for t in re.findall(r"_\('((?:[^'\\]|\\.)*)'\)", contenu)}
        for un, plusieurs in re.findall(r'pluriel\([^,]+,\s*"((?:[^"\\]|\\.)*)",\s*"((?:[^"\\]|\\.)*)"', contenu):
            textes |= {un.replace("\\'", "'"), plusieurs.replace("\\'", "'")}
    return textes


def _textes_indirects() -> set[str]:
    """Textes traduits à l'affichage : libellés, états, statuts, modèles…"""
    from chasseur import controles, licence
    from chasseur.db import agence, reglages, tables
    from chasseur.importers import fichiers
    from chasseur.reports import excel, messages, textes
    from chasseur.sources import places
    from chasseur.web import routes_reglages

    t = set(controles.LIBELLES.values()) | {c.libelle for c in controles.CONTROLES}
    for x in textes.TEXTES.values():
        t |= {x.titre, x.visiteur, x.impact, x.phrase}
    for m in messages.MODELES:
        t |= {m.nom, m.defaut}
    t |= set(licence.MESSAGES_BLOCAGE.values()) | {licence.NOM_LOGICIEL}
    t |= set(places.MESSAGES_ERREURS.values())
    t |= set(tables.STATUTS_COMMERCIAUX) | set(tables.LIBELLES_SCAN.values())
    t |= {titre for _, titre in routes_reglages.FAMILLES} | set(reglages.CLES_API.values())
    t |= set(excel.COLONNES) | set(excel.ORDRE_ETATS) | {"Non analysé", "En attente"}
    t |= {agence.APPEL_DEFAUT}
    t |= {v for k, v in vars(fichiers).items() if k.startswith("FORMAT_") and isinstance(v, str)}
    from chasseur.db import import_resultats  # noqa: F401
    t |= {"Résultats CSV (Lot 2)", "Cette licence n'est plus reconnue pour cet ordinateur : saisissez à nouveau votre clé.",
          "non vérifié", "catégorie", "statut", "problème", "recherche", "Ordinateur (1366 px)", "Téléphone (375 px)",
          "Sites devenus cassés depuis la dernière fois", "Sites réparés", "Autres changements",
          "Nom", "Ville", "Catégorie", "Score", "Téléphone", "Note Google", "Statut"}
    return t


def textes_a_traduire() -> set[str]:
    return _textes_python() | _textes_gabarits() | _textes_indirects()
