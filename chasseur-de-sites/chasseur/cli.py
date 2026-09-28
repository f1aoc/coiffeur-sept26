"""Ligne de commande : chasseur scan prospects.csv"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections import Counter
from pathlib import Path

from chasseur import __version__
from chasseur.analyzers import TOUS
from chasseur.config import PARALLELISME_MAX, ErreurConfig, charger_config
from chasseur.importers import ErreurImport, importer_csv
from chasseur.modeles import Resultat
from chasseur.orchestrateur import analyser_prospects, analyseurs_par_defaut
from chasseur.reports import exporter_csv
from chasseur.reprise import Journal, chemin_journal, cle
from chasseur.scoring import classer


def _liste_analyseurs(texte: str) -> list[str]:
    noms = [n.strip() for n in texte.split(",") if n.strip()]
    inconnus = [n for n in noms if n not in TOUS]
    if inconnus or not noms:
        raise argparse.ArgumentTypeError(f"analyseurs possibles : {', '.join(TOUS)}")
    return noms


def _parseur() -> argparse.ArgumentParser:
    parseur = argparse.ArgumentParser(prog="chasseur", description="Repère les sites d'entreprises cassés ou obsolètes.")
    parseur.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sous = parseur.add_subparsers(dest="commande", required=True)

    scan = sous.add_parser("scan", help="analyser une liste de prospects (CSV)")
    scan.add_argument("fichier", type=Path, help="CSV d'entrée (colonnes : nom, url, téléphone, adresse, catégorie)")
    scan.add_argument("-o", "--sortie", type=Path, help="CSV de sortie (défaut : <fichier>_resultats.csv)")
    scan.add_argument("-c", "--config", type=Path, help="fichier de configuration (défaut : ./config.yaml)")
    scan.add_argument("-p", "--parallele", type=int, help=f"sites analysés en parallèle, 1 à {PARALLELISME_MAX} (défaut : config)")
    scan.add_argument(
        "-a", "--analyseurs", type=_liste_analyseurs,
        help=f"analyseurs à lancer, séparés par des virgules (défaut : {','.join(TOUS)})",
    )
    scan.add_argument("--recommencer", action="store_true", help="ignorer un scan interrompu et tout réanalyser")
    scan.add_argument("-q", "--silencieux", action="store_true", help="ne pas afficher la progression")
    return parseur


def _afficher_progression(fait: int, total: int, r: Resultat) -> None:
    nom = r.prospect.nom or r.prospect.url or f"ligne {r.prospect.ligne}"
    codes = ", ".join(dict.fromkeys(c.code for c in r.constats if c.code != "NON_VERIFIE")) or "aucun problème"
    print(f"[{fait}/{total}] {r.score:>3} pts  {r.etat:<9} {nom} — {codes}", file=sys.stderr)


def commande_scan(args: argparse.Namespace) -> int:
    try:
        config = charger_config(args.config)
        prospects = importer_csv(args.fichier)
    except (ErreurConfig, ErreurImport) as e:
        print(f"Erreur : {e}", file=sys.stderr)
        return 2
    if args.parallele:
        config.parallelisme = min(max(1, args.parallele), PARALLELISME_MAX)
    if not prospects:
        print("Aucun prospect dans le fichier.", file=sys.stderr)
        return 1

    sortie = args.sortie or args.fichier.with_name(f"{args.fichier.stem}_resultats.csv")
    captures = Path(config.navigateur.dossier_captures)
    if not captures.is_absolute():
        config.navigateur.dossier_captures = str(sortie.parent / captures)

    journal = Journal(chemin_journal(sortie))
    if args.recommencer:
        journal.supprimer()
    deja_faits = journal.charger(config)
    a_faire = [p for p in prospects if cle(p) not in deja_faits]

    if not args.silencieux:
        print(
            f"Analyse de {len(a_faire)} prospect(s), {config.parallelisme} en parallèle (config : {config.source})",
            file=sys.stderr,
        )
        if deja_faits:
            print(f"Reprise : {len(prospects) - len(a_faire)} site(s) déjà analysé(s) ignoré(s).", file=sys.stderr)

    def progression(fait: int, total: int, r: Resultat) -> None:
        journal.ecrire(r)
        if not args.silencieux:
            _afficher_progression(fait, total, r)

    try:
        nouveaux = asyncio.run(
            analyser_prospects(a_faire, config, analyseurs_par_defaut(config, args.analyseurs), progression=progression)
        )
    except KeyboardInterrupt:
        journal.fermer()
        print(f"\nInterrompu. Relancez la même commande pour reprendre ({journal.chemin.name}).", file=sys.stderr)
        return 130
    journal.fermer()

    par_cle = {**deja_faits, **{cle(r.prospect): r for r in nouveaux}}
    resultats = [par_cle[cle(p)] for p in prospects if cle(p) in par_cle]
    resultats = list({id(r): r for r in resultats}.values())  # doublons exacts du CSV : une seule ligne
    exporter_csv(resultats, sortie)
    journal.supprimer()

    etats = Counter(r.etat for r in resultats)
    print(f"\n{len(resultats)} prospect(s) analysé(s) → {sortie}")
    print("  " + " · ".join(f"{etat} : {n}" for etat, n in etats.most_common()))
    echecs = Counter(nom for r in resultats for nom in r.echecs)
    if echecs:
        detail = ", ".join(f"{nom} ×{n}" for nom, n in echecs.items())
        print(f"⚠ Contrôles non vérifiés suite à une erreur : {detail} (voir la colonne « preuves »).", file=sys.stderr)
    print("Top 5 :")
    for r in classer(resultats)[:5]:
        print(f"  {r.score:>3} pts  {r.etat:<9} {r.prospect.nom or r.prospect.url}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parseur().parse_args(argv)
    if args.commande == "scan":
        return commande_scan(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
