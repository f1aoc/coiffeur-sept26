"""Point d'entrée de l'exécutable (PyInstaller) : double-clic = interface web.

Au premier lancement, Chromium (pour les captures et les PDF) est téléchargé
dans <dossier de données>/navigateurs, une seule fois.
Avec des arguments, se comporte comme la commande « chasseur » :
    ChasseurDeSites.exe scan prospects.csv
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def dossier_donnees() -> Path:
    return Path(os.environ.get("CHASSEUR_DONNEES") or Path.home() / ".chasseur-de-sites")


def installer_chromium() -> None:
    """Télécharge Chromium via le pilote Playwright embarqué (sans effet s'il est déjà là)."""
    if os.environ.get("CHASSEUR_SANS_INSTALLATION") or os.environ.get("CHASSEUR_CHROMIUM"):
        return
    from playwright._impl._driver import compute_driver_executable, get_driver_env

    pilote = compute_driver_executable()
    commande = [*pilote, "install", "chromium"] if isinstance(pilote, (tuple, list)) else [str(pilote), "install", "chromium"]
    marqueur = Path(os.environ["PLAYWRIGHT_BROWSERS_PATH"]) / ".chromium-installe"
    if not marqueur.exists():
        print("Premier lancement : téléchargement du navigateur d'analyse (environ 150 Mo, une seule fois)…", flush=True)
    resultat = subprocess.run(commande, env={**os.environ, **get_driver_env()}, check=False)
    if resultat.returncode == 0:
        marqueur.parent.mkdir(parents=True, exist_ok=True)
        marqueur.touch()
    else:
        print("⚠ Le téléchargement de Chromium a échoué : les captures et les PDF ne fonctionneront pas "
              "tant qu'il n'aura pas réussi (vérifiez votre connexion, puis relancez).", flush=True)


def main() -> int:
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(dossier_donnees() / "navigateurs"))
    arguments = sys.argv[1:] or ["web"]
    besoin_navigateur = arguments[0] in ("web", "scan", "rapport", "planifies") and not {"-h", "--help"} & set(arguments)
    if getattr(sys, "frozen", False) and besoin_navigateur:
        installer_chromium()
    from chasseur.cli import main as cli

    return cli(arguments)


if __name__ == "__main__":
    sys.exit(main())
