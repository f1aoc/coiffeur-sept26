"""Migration d'un CSV de résultats du Lot 2 (`chasseur scan`) vers la base.

Chaque ligne devient un prospect déjà analysé : constats (codes, messages,
preuves), mesures techniques, contrôles non vérifiés et captures (copiées
dans le dossier de données). Scores et états sont recalculés avec les poids
actuels.
"""

from __future__ import annotations

import csv
import re
import shutil
from pathlib import Path

from chasseur.config import Config
from chasseur.controles import CONTROLE_DU_CODE
from chasseur.db import depot
from chasseur.db.moteur import Stockage
from chasseur.db.tables import TERMINE, Scan, maintenant
from chasseur.importers.fichiers import ville_depuis_adresse
from chasseur.modeles import Prospect, Resultat
from chasseur.reports.csv_export import COLONNES_MESURES, SEPARATEUR_LISTE
from chasseur.scoring import noter

RE_NON_VERIFIE = re.compile(r"^(\w+) \((.*)\)$")
RE_ECHEC = re.compile(r"échec de l'analyseur (\w+)")
# Preuves des constats « non vérifié » (absents de la colonne `codes`)
RE_PREUVE_NON_VERIFIE = re.compile(r"^(analyseur \w+ :|performance :)")


class ErreurMigration(ValueError):
    pass


def _liste(texte: str) -> list[str]:
    return [x for x in (texte or "").split(SEPARATEUR_LISTE)] if texte else []


def _resultat(ligne: dict, config: Config) -> Resultat:
    p = Prospect(
        nom=ligne.get("nom", ""), url=ligne.get("url", ""), telephone=ligne.get("telephone", ""),
        adresse=ligne.get("adresse", ""), categorie=ligne.get("categorie", ""),
    )
    p.ville = ville_depuis_adresse(p.adresse)
    codes = _liste(ligne.get("codes", ""))
    messages = _liste(ligne.get("messages_client", ""))
    preuves = _liste(ligne.get("preuves", ""))
    if len(preuves) != len(codes):
        preuves = [x for x in preuves if not RE_PREUVE_NON_VERIFIE.match(x)]
    constats = []
    for i, code in enumerate(codes):
        if code not in CONTROLE_DU_CODE:
            continue  # code d'une version plus ancienne : ignoré
        message = messages[i] if i < len(messages) and len(messages) == len(codes) else ""
        preuve = preuves[i] if i < len(preuves) and len(preuves) == len(codes) else ""
        constats.append(config.constat(code, message, preuve))

    non_verifies = {}
    for element in _liste(ligne.get("non_verifies", "")):
        if m := RE_NON_VERIFIE.match(element.strip()):
            non_verifies[m[1]] = m[2]
    echecs = sorted({m[1] for v in non_verifies.values() if (m := RE_ECHEC.search(v))})
    sans_objet = [cle[5:] for cle, valeur in ligne.items() if cle and cle.startswith("ctrl_") and valeur == "n/a"]
    mesures = {k: ligne[k] for k in COLONNES_MESURES if ligne.get(k)}
    for cle in ("capture_bureau", "capture_mobile", "capture_date"):
        if ligne.get(cle):
            mesures[cle] = ligne[cle]
    return noter(Resultat(p, constats, mesures, non_verifies, sans_objet, echecs), config)


def importer_resultats(stockage: Stockage, chemin: str | Path, config: Config, nom: str | None = None) -> Scan:
    chemin = Path(chemin)
    if not chemin.is_file():
        raise ErreurMigration(f"Fichier introuvable : {chemin}")
    texte = chemin.read_text(encoding="utf-8-sig")
    lignes = list(csv.DictReader(texte.splitlines(), delimiter=";"))
    if not lignes or not {"codes", "score", "etat"} <= set(lignes[0]):
        raise ErreurMigration(
            f"{chemin.name} n'est pas un export de résultats de « chasseur scan » (colonnes codes, score, etat attendues)"
        )

    resultats = [_resultat(l, config) for l in lignes]
    with stockage.session() as session:
        scan = depot.creer_scan(
            session, nom or f"Import {chemin.stem}", [r.prospect for r in resultats], fichier=chemin.name,
            format_="Résultats CSV (Lot 2)",
        )
        ids = [p.id for p in depot.a_analyser(session, scan.id)]
        dossier = stockage.dossier_captures / f"scan-{scan.id}"
        for prospect_id, r in zip(sorted(ids), resultats):
            for cle in ("capture_bureau", "capture_mobile"):
                source = Path(r.mesures.get(cle, ""))
                if not r.mesures.get(cle):
                    continue
                if not source.is_absolute():
                    source = (chemin.parent / source) if (chemin.parent / source).is_file() else source
                if source.is_file():
                    dossier.mkdir(parents=True, exist_ok=True)
                    cible = dossier / source.name
                    shutil.copy2(source, cible)
                    r.mesures[cle] = str(cible)
                else:
                    r.mesures.pop(cle)
            depot.enregistrer_resultat(stockage, session, prospect_id, r)
        scan.statut, scan.demarre_le, scan.termine_le = TERMINE, maintenant(), maintenant()
        session.add(scan)
        session.commit()
        return scan
