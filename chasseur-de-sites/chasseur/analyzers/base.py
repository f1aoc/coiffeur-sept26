"""Interface commune à tous les analyseurs."""

from __future__ import annotations

from abc import ABC, abstractmethod

import httpx

from chasseur.config import Config
from chasseur.controles import controles_de
from chasseur.modeles import Prospect, Rapport


class Analyseur(ABC):
    nom: str = "analyseur"
    # False : l'analyseur sait traiter un prospect sans URL valide (le Réseau le signale).
    requiert_url: bool = True
    # True : l'analyseur a sa propre file d'attente (quota d'API) et ne consomme pas
    # une des places « sites en parallèle ».
    file_dediee: bool = False

    def __init__(self, config: Config):
        self.config = config

    @property
    def controles(self) -> list[str]:
        return controles_de(self.nom)

    @abstractmethod
    async def analyser(self, prospect: Prospect, client: httpx.AsyncClient) -> Rapport:
        """Renvoie la liste des constats relevés (un Rapport, vide si tout va bien)."""

    async def fermer(self) -> None:
        """Libère les ressources (navigateur, clients HTTP…) en fin de scan."""
