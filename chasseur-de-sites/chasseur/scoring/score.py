"""Scoring (cahier des charges §3.2 à §3.4).

- Chaque contrôle déclenché apporte ses points une seule fois.
- Score = somme, plafonnée à score_max.
- Cassé    : au moins un contrôle de la famille « casse » (tableau 3.2) ;
  Obsolète : score ≥ seuil_obsolete sans casse ;
  Correct  : sinon.
- À revérifier : ni casse prouvée ni analyse complète (Réseau ou Navigateur en
  échec, ex. panne de connexion) : on n'affiche jamais « Correct » à tort.
"""

from __future__ import annotations

from chasseur.config import Config
from chasseur.controles import CODE_NON_VERIFIE, CONTROLE_DU_CODE, CONTROLES
from chasseur.modeles import GRAVITES, Constat, Resultat

CODES_SANS_SITE = {"SITE_ABSENT", "URL_INVALIDE"}
# Sans ces analyseurs, on ne peut pas affirmer qu'un site est correct ou seulement obsolète.
ANALYSEURS_ESSENTIELS = {"reseau", "navigateur"}


def controles_declenches(constats: list[Constat]) -> dict[str, list[str]]:
    """Contrôle → codes relevés (hors « non vérifié »)."""
    declenches: dict[str, list[str]] = {}
    for c in constats:
        if c.code == CODE_NON_VERIFIE:
            continue
        declenches.setdefault(CONTROLE_DU_CODE[c.code].id, []).append(c.code)
    return declenches


def calculer_score(constats: list[Constat], config: Config) -> int:
    total = sum(config.points.get(controle, 0) for controle in controles_declenches(constats))
    return max(0, min(total, config.score_max))


def etat(constats: list[Constat], score: int, config: Config, echecs: list[str] = ()) -> str:
    e = config.etats
    codes = {c.code for c in constats}
    if codes & CODES_SANS_SITE:
        return e.sans_site
    if any(CONTROLE_DU_CODE[code].famille == "casse" for code in codes if code != CODE_NON_VERIFIE):
        return e.casse
    if ANALYSEURS_ESSENTIELS & set(echecs):
        return e.a_reverifier
    return e.obsolete if score >= e.seuil_obsolete else e.correct


def noter(resultat: Resultat, config: Config) -> Resultat:
    resultat.score = calculer_score(resultat.constats, config)
    resultat.etat = etat(resultat.constats, resultat.score, config, resultat.echecs)
    return resultat


def statut_controles(resultat: Resultat) -> dict[str, str]:
    """Contrôle → « OK », « KO : CODE… », « non vérifié » ou « n/a » (une colonne par contrôle)."""
    declenches = controles_declenches(resultat.constats)
    statuts = {}
    for c in CONTROLES:
        if c.id in declenches:
            statuts[c.id] = "KO : " + ", ".join(dict.fromkeys(declenches[c.id]))
        elif c.id in resultat.non_verifies:
            statuts[c.id] = "non vérifié"
        elif c.id in resultat.sans_objet:
            statuts[c.id] = "n/a"
        else:
            statuts[c.id] = "OK"
    return statuts


def _rang_gravite(resultat: Resultat) -> int:
    """0 = critique … len(GRAVITES) = aucun constat ; sert à départager les ex æquo."""
    rangs = [GRAVITES.index(c.gravite) for c in resultat.constats if c.gravite in GRAVITES and c.points]
    return min(rangs, default=len(GRAVITES))


def classer(resultats: list[Resultat]) -> list[Resultat]:
    """Score décroissant, puis gravité la plus forte, puis nom."""
    return sorted(resultats, key=lambda r: (-r.score, _rang_gravite(r), r.prospect.nom.lower()))
