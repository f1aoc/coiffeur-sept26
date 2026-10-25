"""Textes français à traduire : appels _("…") et pluriel(n, "…", "…") du code, plus les textes indirects
(listes de constantes passées à _() au moment de l'affichage)."""

from __future__ import annotations

import ast
from pathlib import Path

DOSSIER = Path(__file__).resolve().parent.parent
FICHIERS = ("bridgetoleads.pyw", "find_no_website.py", "licence.py")


def _textes_appels(arbre: ast.AST) -> set[str]:
    textes = set()
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, ast.Call) or not isinstance(noeud.func, ast.Name):
            continue
        if noeud.func.id == "_":
            arguments = noeud.args[:1]
        elif noeud.func.id == "pluriel":
            arguments = noeud.args[1:3]
        else:
            continue
        for a in arguments:
            if isinstance(a, ast.Constant) and isinstance(a.value, str):
                textes.add(a.value)
    return textes


def _constantes(arbre: ast.AST, nom: str):
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Assign) and any(isinstance(c, ast.Name) and c.id == nom for c in noeud.targets):
            return ast.literal_eval(noeud.value)
    raise LookupError(nom)


def textes() -> set[str]:
    arbres = {f: ast.parse((DOSSIER / f).read_text(encoding="utf-8")) for f in FICHIERS}
    resultat: set[str] = set()
    for arbre in arbres.values():
        resultat |= _textes_appels(arbre)
    app, recherche, licence = arbres["bridgetoleads.pyw"], arbres["find_no_website.py"], arbres["licence.py"]
    resultat.add(_constantes(app, "TAGLINE"))
    resultat |= {titre for _cle, titre, _l, _e in _constantes(app, "COLUMNS")}
    resultat |= {"Commerces analysés", "Sans aucun site", "Réseaux / annuaire seulement", "Aucun site"}  # tuiles, légende
    resultat |= {titre for _cle, titre, _l in _constantes(recherche, "XLSX_COLUMNS")}
    resultat |= set(_constantes(recherche, "ERROR_HINTS").values())
    resultat.add("Erreur inattendue de Google, voir le détail ci-dessous.")
    resultat |= {"Cette licence a été désactivée (paiement remboursé ou contesté). Les recherches sont bloquées ; "
                 "les résultats déjà affichés peuvent encore être exportés.",
                 "Cette licence n'est plus reconnue pour cet ordinateur : saisissez à nouveau votre clé.",
                 "Cette clé de licence n'est pas valable."}
    return resultat


if __name__ == "__main__":
    for t in sorted(textes()):
        print(repr(t))
