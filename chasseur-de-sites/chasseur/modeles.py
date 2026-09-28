"""Structures de données partagées par tous les modules."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

GRAVITES = ("critique", "haute", "moyenne", "basse", "info")


@dataclass
class Prospect:
    nom: str = ""
    url: str = ""
    telephone: str = ""
    adresse: str = ""
    categorie: str = ""
    ligne: int = 0  # numéro de ligne dans le CSV source, pour s'y retrouver


@dataclass
class Constat:
    """Un problème relevé par un analyseur."""

    code: str
    gravite: str
    points: int
    message_client: str  # phrase compréhensible par le gérant de l'entreprise
    preuve: str  # élément technique vérifiable (code HTTP, erreur, date…)

    def en_dict(self) -> dict:
        return asdict(self)


@dataclass
class Resultat:
    prospect: Prospect
    constats: list[Constat] = field(default_factory=list)
    score: int = 0
    priorite: str = ""
