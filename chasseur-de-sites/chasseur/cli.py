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

    web = sous.add_parser("web", help="ouvrir l'interface web locale")
    web.add_argument("--port", type=int, default=8765, help="port local (défaut : 8765)")
    web.add_argument(
        "--hote", default="127.0.0.1",
        help="adresse d'écoute (défaut : 127.0.0.1, accessible depuis cet ordinateur seulement)",
    )
    web.add_argument("--donnees", type=Path, help="dossier des données (défaut : ~/.chasseur-de-sites)")
    web.add_argument("-c", "--config", type=Path, help="fichier de configuration (défaut : ./config.yaml)")
    web.add_argument("--sans-navigateur", action="store_true", help="ne pas ouvrir le navigateur automatiquement")

    imp = sous.add_parser("import", help="importer dans l'interface web un CSV de résultats de « chasseur scan »")
    imp.add_argument("fichier", type=Path, help="CSV produit par « chasseur scan »")
    imp.add_argument("--nom", help="nom de l'analyse (défaut : Import <fichier>)")
    imp.add_argument("--donnees", type=Path, help="dossier des données (défaut : ~/.chasseur-de-sites)")
    imp.add_argument("-c", "--config", type=Path, help="fichier de configuration (défaut : ./config.yaml)")

    rap = sous.add_parser("rapport", help="générer le rapport PDF d'un prospect (identifiant visible dans l'adresse de sa fiche)")
    rap.add_argument("prospect", type=int, help="identifiant du prospect (ex. 12 pour /prospects/12)")
    rap.add_argument("-o", "--sortie", type=Path, help="fichier PDF (défaut : diagnostic-<nom>.pdf)")
    rap.add_argument("--donnees", type=Path, help="dossier des données (défaut : ~/.chasseur-de-sites)")
    rap.add_argument("--moteur", choices=["auto", "weasyprint", "chromium"], default=None, help="moteur PDF (défaut : auto)")
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


def commande_web(args: argparse.Namespace) -> int:
    import threading
    import webbrowser

    import uvicorn

    from chasseur.db import Stockage
    from chasseur.web.app import HOTES_LOCAUX, creer_app

    try:
        charger_config(args.config)
    except ErreurConfig as e:
        print(f"Erreur : {e}", file=sys.stderr)
        return 2
    hotes = HOTES_LOCAUX if args.hote in HOTES_LOCAUX else [*HOTES_LOCAUX, args.hote]
    if args.hote not in HOTES_LOCAUX:
        print(f"⚠ L'interface sera accessible depuis le réseau ({args.hote}) : réservez-le à un réseau de confiance.",
              file=sys.stderr)
    stockage = Stockage(args.donnees)
    app = creer_app(stockage, chemin_config=args.config, hotes=hotes)
    adresse = f"http://{'127.0.0.1' if args.hote in ('0.0.0.0', '::') else args.hote}:{args.port}/"
    print(f"Chasseur de sites : {adresse}  (données : {stockage.dossier})  — Ctrl+C pour arrêter")
    if not args.sans_navigateur:
        threading.Timer(1.2, webbrowser.open, args=(adresse,)).start()
    uvicorn.run(app, host=args.hote, port=args.port, log_level="warning")
    return 0


def commande_import(args: argparse.Namespace) -> int:
    from chasseur.db import Stockage
    from chasseur.db.import_resultats import ErreurMigration, importer_resultats
    from chasseur.db.reglages import config_effective

    try:
        stockage = Stockage(args.donnees)
        with stockage.session() as s:
            config = config_effective(stockage, s, charger_config(args.config))
        scan = importer_resultats(stockage, args.fichier, config, nom=args.nom)
    except (ErreurConfig, ErreurMigration) as e:
        print(f"Erreur : {e}", file=sys.stderr)
        return 2
    print(f"{scan.total} prospect(s) importé(s) dans l'analyse « {scan.nom} » ({stockage.dossier}).")
    print("Lancez « chasseur web » pour les consulter.")
    return 0


def commande_rapport(args: argparse.Namespace) -> int:
    from chasseur.db import Stockage
    from chasseur.db.agence import lire_agence
    from chasseur.reports.donnees import diagnostic
    from chasseur.reports.pdf import ErreurPDF, MoteurPDF, html_rapport, nom_fichier

    stockage = Stockage(args.donnees)
    with stockage.session() as s:
        d = diagnostic(s, args.prospect)
        if d is None:
            print(f"Erreur : prospect {args.prospect} introuvable dans {stockage.dossier}", file=sys.stderr)
            return 2
        html = html_rapport(stockage, d, lire_agence(s))

    async def rendre() -> bytes:
        moteur = MoteurPDF(args.moteur)
        try:
            return await moteur.pdf(html)
        finally:
            await moteur.fermer()

    try:
        contenu = asyncio.run(rendre())
    except ErreurPDF as e:
        print(f"Erreur : {e}", file=sys.stderr)
        return 2
    sortie = args.sortie or Path(nom_fichier(d.prospect))
    sortie.write_bytes(contenu)
    print(f"Rapport de « {d.prospect.nom} » → {sortie}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parseur().parse_args(argv)
    commandes = {"scan": commande_scan, "web": commande_web, "import": commande_import, "rapport": commande_rapport}
    return commandes[args.commande](args)


if __name__ == "__main__":
    sys.exit(main())
