"""Scoring : points des constats (tableau 3.2) → score et priorité (tableau 3.3)."""

from __future__ import annotations

from chasseur.config import Config
from chasseur.modeles import GRAVITES, Constat, Resultat

CODE_ANALYSE_INCOMPLETE = "ERREUR_ANALYSE"


def calculer_score(constats: list[Constat], config: Config) -> int:
    return max(0, min(sum(c.points for c in constats), config.score_max))


def priorite(score: int, config: Config) -> str:
    for seuil, label in config.priorites:  # triées par seuil décroissant
        if score >= seuil:
            return label
    return ""


def noter(resultat: Resultat, config: Config) -> Resultat:
    resultat.score = calculer_score(resultat.constats, config)
    resultat.priorite = priorite(resultat.score, config)
    if any(c.code == CODE_ANALYSE_INCOMPLETE for c in resultat.constats):
        resultat.priorite = config.priorite_incomplete  # ne jamais afficher « site sain » à tort
    return resultat


def _rang_gravite(resultat: Resultat) -> int:
    """0 = critique … len(GRAVITES) = aucun constat ; sert à départager les ex æquo."""
    rangs = [GRAVITES.index(c.gravite) for c in resultat.constats if c.gravite in GRAVITES]
    return min(rangs, default=len(GRAVITES))


def classer(resultats: list[Resultat]) -> list[Resultat]:
    """Score décroissant, puis gravité la plus forte, puis nom."""
    return sorted(resultats, key=lambda r: (-r.score, _rang_gravite(r), r.prospect.nom.lower()))
