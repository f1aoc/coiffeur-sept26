"""Téléchargements des logiciels depuis Cloudflare R2 (via le serveur de licences) au lieu de GitHub.

    python .github/scripts/telechargements_r2.py public

Vérifie d'abord que les 9 fichiers répondent sur https://…workers.dev/telecharger/<fichier> ; si oui, remplace dans
toutes les pages les liens GitHub par ces liens. Sinon, garde les liens GitHub et le signale (avertissement GitHub
Actions) : une page de vente ne doit jamais proposer un téléchargement qui ne marche pas.
"""

import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

SERVEUR = "https://licences.patrick-tabountchikoff.workers.dev/telecharger"
FICHIERS = [f"{nom}{fin}" for nom, win in (("BridgeToLeads", ".exe"), ("ChasseurDeSites", ".exe"), ("AuditExpress", "-Windows.zip"))
            for fin in (win, "-mac-apple-silicon.zip", "-mac-intel.zip")]
GITHUB = [
    ("https://github.com/f1aoc/coiffeur-sept26/releases/download/chasseurdesites-latest/", SERVEUR + "/"),
    ("https://github.com/f1aoc/coiffeur-sept26/releases/download/bridgetoleads-latest/", SERVEUR + "/"),
    ("https://github.com/f1aoc/audit_express/releases/download/auditexpress-latest/", SERVEUR + "/"),
    # pages Merci : constante + chemin construits dans le script
    ("${TELECHARGEMENTS}/chasseurdesites-latest/", "${TELECHARGEMENTS}/"),
    ("${TELECHARGEMENTS}/bridgetoleads-latest/", "${TELECHARGEMENTS}/"),
    ('"https://github.com/f1aoc/coiffeur-sept26/releases/download"', f'"{SERVEUR}"'),
    ('"https://github.com/f1aoc/audit_express/releases/download/auditexpress-latest/AuditExpress"', f'"{SERVEUR}/AuditExpress"'),
]


def present(fichier: str) -> bool:
    try:
        with urllib.request.urlopen(urllib.request.Request(f"{SERVEUR}/{fichier}", method="HEAD"), timeout=30) as r:
            return r.status == 200 and int(r.headers.get("Content-Length") or 0) > 1_000_000
    except (urllib.error.URLError, OSError, ValueError):
        return False


racine = Path(sys.argv[1])
manquants = [f for f in FICHIERS if not present(f)]
if manquants:
    print(f"::warning::Téléchargements laissés sur GitHub : fichiers absents de Cloudflare R2 : {', '.join(manquants)}")
    sys.exit(0)
for page in sorted(racine.rglob("*.html")):
    texte = page.read_text(encoding="utf-8")
    nouveau = texte
    for ancien, neuf in GITHUB:
        nouveau = nouveau.replace(ancien, neuf)
    if nouveau != texte:
        page.write_text(nouveau, encoding="utf-8")
        print(f"{page.relative_to(racine)} : téléchargements depuis Cloudflare R2")
    if re.search(r"github\.com/f1aoc/[\w-]+/releases/download", nouveau):
        sys.exit(f"{page.relative_to(racine)} : lien de téléchargement GitHub non converti")
