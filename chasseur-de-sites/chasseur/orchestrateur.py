"""Lance les analyseurs sur tous les prospects, N sites en parallèle."""

from __future__ import annotations

import asyncio
from typing import Callable

import httpx

from chasseur.analyzers import Analyseur, AnalyseurReseau
from chasseur.config import Config
from chasseur.modeles import Prospect, Resultat
from chasseur.scoring import noter

Progression = Callable[[int, int, Resultat], None]


def analyseurs_par_defaut(config: Config) -> list[Analyseur]:
    return [AnalyseurReseau(config)]


def creer_client(config: Config) -> httpx.AsyncClient:
    # verify=False : on veut le code HTTP même si le certificat est mauvais ;
    # la validité SSL est contrôlée à part par l'analyseur Réseau.
    return httpx.AsyncClient(
        verify=False,
        follow_redirects=True,
        timeout=config.timeout,
        headers={"User-Agent": config.user_agent, "Accept-Language": "fr-FR,fr;q=0.9"},
        limits=httpx.Limits(max_connections=config.parallelisme * 2),
    )


async def analyser_prospects(
    prospects: list[Prospect],
    config: Config,
    analyseurs: list[Analyseur] | None = None,
    client: httpx.AsyncClient | None = None,
    progression: Progression | None = None,
) -> list[Resultat]:
    """Renvoie un Resultat noté par prospect, dans l'ordre d'entrée."""
    analyseurs = analyseurs if analyseurs is not None else analyseurs_par_defaut(config)
    semaphore = asyncio.Semaphore(config.parallelisme)
    termines = 0

    async def traiter(prospect: Prospect, http: httpx.AsyncClient) -> Resultat:
        nonlocal termines
        async with semaphore:
            resultat = Resultat(prospect)
            for analyseur in analyseurs:
                try:
                    resultat.constats.extend(await analyseur.analyser(prospect, http))
                except Exception as e:  # un site ne doit jamais faire planter tout le scan
                    resultat.constats.append(
                        config.constat(
                            "ERREUR_ANALYSE",
                            "Analyse incomplète (erreur technique de notre côté).",
                            f"analyseur {analyseur.nom} : {type(e).__name__} {e}".strip(),
                        )
                    )
            noter(resultat, config)
        termines += 1
        if progression:
            progression(termines, len(prospects), resultat)
        return resultat

    if client is not None:
        return list(await asyncio.gather(*(traiter(p, client) for p in prospects)))
    async with creer_client(config) as http:
        return list(await asyncio.gather(*(traiter(p, http) for p in prospects)))
