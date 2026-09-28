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


class Rapport(list):
    """Ce que renvoie un analyseur : une liste de constats, plus

    - mesures       : preuves brutes à conserver (code HTTP, dates, technologies…) ;
    - non_verifies  : contrôles qui n'ont pas pu être faits → raison ;
    - echec         : True si l'analyseur n'a pas pu travailler normalement
                      (erreur technique), False si c'est un simple « sans objet ».
    """

    def __init__(self, constats=(), mesures=None, non_verifies=None, echec=False):
        super().__init__(constats)
        self.mesures: dict[str, str] = dict(mesures or {})
        self.non_verifies: dict[str, str] = dict(non_verifies or {})
        self.echec = echec


@dataclass
class Resultat:
    prospect: Prospect
    constats: list[Constat] = field(default_factory=list)
    mesures: dict[str, str] = field(default_factory=dict)
    non_verifies: dict[str, str] = field(default_factory=dict)  # contrôle → raison
    sans_objet: list[str] = field(default_factory=list)  # contrôles non applicables (pas d'URL…)
    echecs: list[str] = field(default_factory=list)  # analyseurs en échec
    score: int = 0
    etat: str = ""  # Cassé / Obsolète / Correct
