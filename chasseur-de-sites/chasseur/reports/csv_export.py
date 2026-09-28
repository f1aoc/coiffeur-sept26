"""Export des résultats en CSV, trié par score.

Point-virgule + UTF-8 avec BOM : le fichier s'ouvre directement dans Excel en français.
Une colonne par contrôle (OK / KO : codes / non vérifié / n/a), les preuves
techniques (§3.5) et les chemins des captures.
"""

from __future__ import annotations

import csv
from pathlib import Path

from chasseur.controles import CODE_NON_VERIFIE, CONTROLES
from chasseur.modeles import GRAVITES, Resultat
from chasseur.scoring import classer, statut_controles

COLONNES_PROSPECT = ["rang", "score", "etat", "nom", "url", "telephone", "adresse", "categorie"]
COLONNES_CONTROLES = [f"ctrl_{c.id}" for c in CONTROLES]
COLONNES_MESURES = [
    "code_http", "url_finale", "ip", "ssl_expire_le", "ssl_emetteur", "domaine", "domaine_expire_le",
    "domaine_source", "cms", "version_wordpress", "version_joomla", "version_jquery", "technologies",
    "annee_copyright", "derniere_date", "title", "meta_description", "meta_viewport", "largeur_mobile",
    "formulaire", "lien_tel", "page_contact", "texte_visible_car", "perf_score", "perf_lcp_s", "perf_cls",
    "perf_tbt_ms", "note_http",
]
COLONNES_CAPTURES = ["capture_bureau", "capture_mobile", "capture_date"]
COLONNES_SYNTHESE = ["nb_constats", "codes", "gravite_max", "messages_client", "preuves", "non_verifies"]
COLONNES = COLONNES_PROSPECT + COLONNES_SYNTHESE + COLONNES_CONTROLES + COLONNES_MESURES + COLONNES_CAPTURES

SEPARATEUR_LISTE = " | "


def _gravite_max(r: Resultat) -> str:
    connues = [c.gravite for c in r.constats if c.gravite in GRAVITES and c.points]
    return min(connues, key=GRAVITES.index, default="")


def ligne_export(rang: int, r: Resultat) -> dict:
    p = r.prospect
    constats = [c for c in r.constats if c.code != CODE_NON_VERIFIE]
    ligne = {
        "rang": rang,
        "score": r.score,
        "etat": r.etat,
        "nom": p.nom,
        "url": p.url,
        "telephone": p.telephone,
        "adresse": p.adresse,
        "categorie": p.categorie,
        "nb_constats": len(constats),
        "codes": SEPARATEUR_LISTE.join(c.code for c in constats),
        "gravite_max": _gravite_max(r),
        "messages_client": SEPARATEUR_LISTE.join(c.message_client for c in constats),
        "preuves": SEPARATEUR_LISTE.join(c.preuve for c in r.constats),
        "non_verifies": SEPARATEUR_LISTE.join(f"{k} ({v})" for k, v in r.non_verifies.items()),
    }
    for controle, statut in statut_controles(r).items():
        ligne[f"ctrl_{controle}"] = statut
    for cle in COLONNES_MESURES + COLONNES_CAPTURES:
        ligne[cle] = r.mesures.get(cle, "")
    return ligne


def exporter_csv(resultats: list[Resultat], chemin: str | Path) -> Path:
    chemin = Path(chemin)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with chemin.open("w", encoding="utf-8-sig", newline="") as f:
        ecrivain = csv.DictWriter(f, fieldnames=COLONNES, delimiter=";")
        ecrivain.writeheader()
        for rang, r in enumerate(classer(resultats), start=1):
            ecrivain.writerow(ligne_export(rang, r))
    return chemin
