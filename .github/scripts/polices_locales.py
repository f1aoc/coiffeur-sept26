"""Remplace Google Fonts par la police hébergée sur le site (assets/polices/polices.css) dans toutes les pages.

    python .github/scripts/polices_locales.py public

Aucune requête vers Google au chargement d'une page : pas d'adresse IP de visiteur transmise à Google.
Échoue si une page charge encore une ressource de fonts.googleapis.com ou fonts.gstatic.com.
"""

import re
import sys
from pathlib import Path

racine = Path(sys.argv[1])
feuille = racine / "assets" / "polices" / "polices.css"
assert feuille.is_file(), f"{feuille} absent"
PRECONNECT = re.compile(r'[ \t]*<link rel="preconnect" href="https://fonts\.(googleapis|gstatic)\.com"[^>]*>\n?')
FEUILLE = re.compile(r'<link href="https://fonts\.googleapis\.com/css2\?[^"]*" rel="stylesheet">')
restes = []
for page in sorted(racine.rglob("*.html")):
    texte = page.read_text(encoding="utf-8")
    relatif = "../" * (len(page.relative_to(racine).parts) - 1) + "assets/polices/polices.css"
    nouveau = FEUILLE.sub(f'<link href="{relatif}" rel="stylesheet">', PRECONNECT.sub("", texte))
    if nouveau != texte:
        page.write_text(nouveau, encoding="utf-8")
        print(f"{page.relative_to(racine)} → {relatif}")
    if "fonts.googleapis.com" in nouveau or "fonts.gstatic.com" in nouveau:
        restes.append(str(page.relative_to(racine)))
if restes:
    sys.exit("Pages qui chargent encore Google Fonts : " + ", ".join(restes))
