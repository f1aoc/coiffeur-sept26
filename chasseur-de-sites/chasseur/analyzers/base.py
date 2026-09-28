"""Interface commune à tous les analyseurs."""

from __future__ import annotations

from abc import ABC, abstractmethod

import httpx

from chasseur.config import Config
from chasseur.modeles import Constat, Prospect


class Analyseur(ABC):
    nom: str = "analyseur"

    def __init__(self, config: Config):
        self.config = config

    @abstractmethod
    async def analyser(self, prospect: Prospect, client: httpx.AsyncClient) -> list[Constat]:
        """Renvoie la liste des constats relevés sur le site du prospect (vide si tout va bien)."""
