"""Ligne de commande : chasseur scan prospects.csv"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from chasseur import __version__
from chasseur.config import ErreurConfig, charger_config
from chasseur.importers import ErreurImport, importer_csv
from chasseur.modeles import Resultat
from chasseur.orchestrateur import analyser_prospects
from chasseur.reports import exporter_csv
from chasseur.scoring import classer


def _parseur() -> argparse.ArgumentParser:
    parseur = argparse.ArgumentParser(prog="chasseur", description="Repère les sites d'entreprises cassés ou obsolètes.")
    parseur.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sous = parseur.add_subparsers(dest="commande", required=True)

    scan = sous.add_parser("scan", help="analyser une liste de prospects (CSV)")
    scan.add_argument("fichier", type=Path, help="CSV d'entrée (colonnes : nom, url, téléphone, adresse, catégorie)")
    scan.add_argument("-o", "--sortie", type=Path, help="CSV de sortie (défaut : <fichier>_resultats.csv)")
    scan.add_argument("-c", "--config", type=Path, help="fichier de configuration (défaut : ./config.yaml)")
    scan.add_argument("-p", "--parallele", type=int, help="nombre de sites analysés en parallèle (défaut : config)")
    scan.add_argument("-q", "--silencieux", action="store_true", help="ne pas afficher la progression")
    return parseur


def _afficher_progression(fait: int, total: int, r: Resultat) -> None:
    nom = r.prospect.nom or r.prospect.url or f"ligne {r.prospect.ligne}"
    codes = ", ".join(c.code for c in r.constats) or "OK"
    print(f"[{fait}/{total}] {r.score:>3} pts  {nom} — {codes}", file=sys.stderr)


def commande_scan(args: argparse.Namespace) -> int:
    try:
        config = charger_config(args.config)
        prospects = importer_csv(args.fichier)
    except (ErreurConfig, ErreurImport) as e:
        print(f"Erreur : {e}", file=sys.stderr)
        return 2
    if args.parallele:
        config.parallelisme = max(1, args.parallele)
    if not prospects:
        print("Aucun prospect dans le fichier.", file=sys.stderr)
        return 1

    if not args.silencieux:
        print(
            f"Analyse de {len(prospects)} prospect(s), {config.parallelisme} en parallèle (config : {config.source})",
            file=sys.stderr,
        )
    resultats = asyncio.run(
        analyser_prospects(prospects, config, progression=None if args.silencieux else _afficher_progression)
    )

    sortie = args.sortie or args.fichier.with_name(f"{args.fichier.stem}_resultats.csv")
    exporter_csv(resultats, sortie)

    classes = classer(resultats)
    print(f"\n{len(resultats)} prospect(s) analysé(s) → {sortie}")
    incompletes = sum(any(c.code == "ERREUR_ANALYSE" for c in r.constats) for r in resultats)
    if incompletes:
        print(
            f"⚠ {incompletes} analyse(s) incomplète(s) (erreur technique ou proxy) : voir la colonne « preuves ».",
            file=sys.stderr,
        )
    print("Top 5 :")
    for r in classes[:5]:
        print(f"  {r.score:>3} pts  {r.priorite:<18} {r.prospect.nom or r.prospect.url}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parseur().parse_args(argv)
    if args.commande == "scan":
        return commande_scan(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
