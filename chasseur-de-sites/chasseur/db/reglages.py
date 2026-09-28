"""Réglages modifiables depuis l'interface, stockés en base.

La config effective d'un scan = config.yaml + réglages de l'interface
(parallélisme, points du scoring, clés API déchiffrées en mémoire seulement).
"""

from __future__ import annotations

import json

from sqlmodel import Session

from chasseur.config import PARALLELISME_MAX, Config, ErreurConfig, charger_config
from chasseur.controles import PAR_ID
from chasseur.db.moteur import Stockage
from chasseur.db.secret import chiffrer, dechiffrer
from chasseur.db.tables import Reglage
from chasseur.journal import enregistrer_secret

CLE_PAGESPEED = "cle_pagespeed"
CLE_PLACES = "cle_places"
CLES_API = {CLE_PAGESPEED: "PageSpeed Insights", CLE_PLACES: "Google Places (recherche secteur + ville)"}
PARALLELISME = "parallelisme"
POINTS = "points"


def lire(session: Session, cle: str, defaut: str = "") -> str:
    r = session.get(Reglage, cle)
    return r.valeur if r else defaut


def ecrire(session: Session, cle: str, valeur: str, chiffre: bool = False) -> None:
    r = session.get(Reglage, cle) or Reglage(cle=cle)
    r.valeur, r.chiffre = valeur, chiffre
    session.add(r)


def supprimer(session: Session, cle: str) -> None:
    if r := session.get(Reglage, cle):
        session.delete(r)


def lire_cle_api(stockage: Stockage, session: Session, cle: str) -> str:
    r = session.get(Reglage, cle)
    if not r or not r.valeur:
        return ""
    valeur = dechiffrer(stockage.dossier, r.valeur) if r.chiffre else r.valeur
    enregistrer_secret(valeur)  # jamais écrite dans le journal des erreurs
    return valeur


def ecrire_cle_api(stockage: Stockage, session: Session, cle: str, valeur: str) -> None:
    ecrire(session, cle, chiffrer(stockage.dossier, valeur.strip()), chiffre=True)


def points(session: Session, base: Config) -> dict[str, int]:
    personnalises = json.loads(lire(session, POINTS, "{}") or "{}")
    return base.points | {k: int(v) for k, v in personnalises.items() if k in PAR_ID}


def ecrire_points(session: Session, valeurs: dict[str, int]) -> None:
    ecrire(session, POINTS, json.dumps({k: int(v) for k, v in valeurs.items() if k in PAR_ID}))


def parallelisme(session: Session, base: Config) -> int:
    try:
        return min(max(1, int(lire(session, PARALLELISME, str(base.parallelisme)))), PARALLELISME_MAX)
    except ValueError:
        return base.parallelisme


def config_effective(stockage: Stockage, session: Session, base: Config | None = None) -> Config:
    config = base or charger_config()
    config.points = points(session, config)
    config.parallelisme = parallelisme(session, config)
    cle = lire_cle_api(stockage, session, CLE_PAGESPEED)
    if cle:
        config.performance.cle_api = cle
    return config


__all__ = [
    "CLES_API", "CLE_PAGESPEED", "CLE_PLACES", "ErreurConfig", "config_effective", "ecrire", "ecrire_cle_api",
    "ecrire_points", "lire", "lire_cle_api", "parallelisme", "points", "supprimer",
]
