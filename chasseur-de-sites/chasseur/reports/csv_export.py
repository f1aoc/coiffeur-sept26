"""Export des résultats en CSV, trié par score.

Point-virgule + UTF-8 avec BOM : le fichier s'ouvre directement dans Excel en français.
"""

from __future__ import annotations

import csv
from pathlib import Path

from chasseur.modeles import GRAVITES, Resultat
from chasseur.scoring import classer

COLONNES = [
    "rang",
    "score",
    "priorite",
    "nom",
    "url",
    "telephone",
    "adresse",
    "categorie",
    "nb_constats",
    "codes",
    "gravite_max",
    "messages_client",
    "preuves",
]

SEPARATEUR_LISTE = " | "


def _gravite_max(r: Resultat) -> str:
    connues = [c.gravite for c in r.constats if c.gravite in GRAVITES]
    return min(connues, key=GRAVITES.index, default="")


def exporter_csv(resultats: list[Resultat], chemin: str | Path) -> Path:
    chemin = Path(chemin)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with chemin.open("w", encoding="utf-8-sig", newline="") as f:
        ecrivain = csv.DictWriter(f, fieldnames=COLONNES, delimiter=";")
        ecrivain.writeheader()
        for rang, r in enumerate(classer(resultats), start=1):
            p = r.prospect
            ecrivain.writerow(
                {
                    "rang": rang,
                    "score": r.score,
                    "priorite": r.priorite,
                    "nom": p.nom,
                    "url": p.url,
                    "telephone": p.telephone,
                    "adresse": p.adresse,
                    "categorie": p.categorie,
                    "nb_constats": len(r.constats),
                    "codes": SEPARATEUR_LISTE.join(c.code for c in r.constats),
                    "gravite_max": _gravite_max(r),
                    "messages_client": SEPARATEUR_LISTE.join(c.message_client for c in r.constats),
                    "preuves": SEPARATEUR_LISTE.join(c.preuve for c in r.constats),
                }
            )
    return chemin
