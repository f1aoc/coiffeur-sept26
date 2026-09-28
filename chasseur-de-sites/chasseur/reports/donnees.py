"""Données d'un diagnostic prospect : problèmes triés, verdict, captures.

Partagé par le rapport PDF, les modèles de messages et l'écran Fiche.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlmodel import Session

from chasseur.controles import CODE_NON_VERIFIE, CONTROLE_DU_CODE
from chasseur.db import depot
from chasseur.db.tables import Capture, ConstatDB, ProspectDB
from chasseur.modeles import GRAVITES
from chasseur.reports.textes import Texte, texte

MAX_PROBLEMES_RAPPORT = 5
EXCLUS = {CODE_NON_VERIFIE, "URL_INVALIDE"}


@dataclass
class Probleme:
    code: str
    controle: str
    famille: str
    gravite: str
    points: int
    texte: Texte


@dataclass
class Diagnostic:
    prospect: ProspectDB
    problemes: list[Probleme] = field(default_factory=list)  # un par contrôle, du plus grave au moins grave
    captures: dict[str, Capture] = field(default_factory=dict)

    @property
    def principaux(self) -> list[Probleme]:
        """Les 3 à 5 problèmes à présenter (moins s'il y en a moins)."""
        return self.problemes[:MAX_PROBLEMES_RAPPORT]

    @property
    def autres(self) -> int:
        return max(0, len(self.problemes) - MAX_PROBLEMES_RAPPORT)

    @property
    def probleme_principal(self) -> str:
        return self.problemes[0].texte.phrase if self.problemes else ""

    @property
    def verdict(self) -> str:
        p, n = self.prospect, len(self.problemes)
        if p.etat == "Sans site":
            return "Votre entreprise n'a pas encore de site internet."
        if not p.analyse:
            return "Votre site n'a pas encore été analysé."
        if n == 0:
            return "Votre site ne présente pas de problème majeur."
        if p.etat == "Correct":
            return f"Votre site est en bon état, avec {n} point{'s' if n > 1 else ''} à améliorer."
        if n == 1:
            return "Votre site présente 1 problème qui fait fuir vos visiteurs."
        return f"Votre site présente {n} problèmes qui font fuir vos visiteurs."


def problemes(constats: list[ConstatDB], mesures: dict) -> list[Probleme]:
    """Un problème par contrôle (le plus grave), trié : site cassé d'abord, puis par points et gravité."""
    rang = {g: i for i, g in enumerate(GRAVITES)}
    retenus: dict[str, Probleme] = {}
    for c in constats:
        if c.code in EXCLUS or c.code not in CONTROLE_DU_CODE or (c.points == 0 and c.gravite == "info"):
            continue
        t = texte(c.code, mesures)
        if t is None:
            continue
        controle = CONTROLE_DU_CODE[c.code]
        candidat = Probleme(c.code, controle.id, controle.famille, c.gravite, c.points, t)
        actuel = retenus.get(controle.id)
        if actuel is None or (candidat.points, -rang.get(candidat.gravite, 9)) > (actuel.points, -rang.get(actuel.gravite, 9)):
            retenus[controle.id] = candidat
    return sorted(
        retenus.values(),
        key=lambda p: (p.famille != "casse", -p.points, rang.get(p.gravite, 9)),
    )


def diagnostic(session: Session, prospect_id: int) -> Diagnostic | None:
    p = session.get(ProspectDB, prospect_id)
    if p is None:
        return None
    return Diagnostic(p, problemes(depot.constats_de(session, prospect_id), p.mesures), depot.captures_de(session, prospect_id))
