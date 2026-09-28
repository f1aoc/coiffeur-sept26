"""Pipeline : pour chaque site, les analyseurs tournent en parallèle (§5).

- Au plus `parallelisme` sites analysés en même temps.
- L'analyseur Performance a sa propre file d'attente (quota PageSpeed) : il
  n'occupe pas de place « site » pendant qu'il attend l'API.
- Un analyseur qui plante est noté « non vérifié » ; les autres continuent.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Callable

import httpx

from chasseur import urls
from chasseur.analyzers import TOUS, Analyseur
from chasseur.config import Config
from chasseur.controles import CODE_NON_VERIFIE, CONTROLES
from chasseur.modeles import Prospect, Rapport, Resultat
from chasseur.scoring import noter

Progression = Callable[[int, int, Resultat], None]
journal = logging.getLogger("chasseur.analyse")

# Codes souvent renvoyés aux robots par les protections anti-bots (Cloudflare…) :
# si le vrai navigateur a affiché la page normalement, ce n'est pas une panne.
CODES_ANTI_ROBOTS = {"401", "403", "406", "429", "503"}


def analyseurs_par_defaut(config: Config, noms: list[str] | None = None) -> list[Analyseur]:
    return [TOUS[nom](config) for nom in (noms or list(TOUS))]


def creer_client(config: Config) -> httpx.AsyncClient:
    # verify=False : on veut le code HTTP même si le certificat est mauvais ;
    # la validité SSL est contrôlée à part par l'analyseur Réseau.
    return httpx.AsyncClient(
        verify=False,
        follow_redirects=True,
        timeout=config.timeout,
        headers={"User-Agent": config.user_agent, "Accept-Language": "fr-FR,fr;q=0.9"},
        limits=httpx.Limits(max_connections=config.parallelisme * 4),
    )


def _masquer(texte: str, config: Config) -> str:
    cle = config.performance.cle
    return texte.replace(cle, "***") if cle else texte


async def _executer(analyseur: Analyseur, prospect: Prospect, http: httpx.AsyncClient, config: Config) -> Rapport:
    try:
        rapport = await analyseur.analyser(prospect, http)
        return rapport if isinstance(rapport, Rapport) else Rapport(rapport)
    except Exception as e:  # un analyseur ne doit jamais faire planter le scan
        detail = _masquer(f"{type(e).__name__} {e}".strip().splitlines()[0][:300], config)
        journal.warning("analyseur %s en échec sur %s : %s", analyseur.nom, prospect.url, detail)
        return Rapport(
            [
                config.constat(
                    CODE_NON_VERIFIE,
                    f"Contrôles « {analyseur.nom} » non vérifiés (erreur technique de notre côté).",
                    f"analyseur {analyseur.nom} : {detail}",
                )
            ],
            non_verifies=dict.fromkeys(analyseur.controles, f"échec de l'analyseur {analyseur.nom}"),
            echec=True,
        )


def consolider(resultat: Resultat) -> None:
    """Croise les analyseurs pour éviter les faux positifs « cassé » (objectif < 5 %)."""
    m = resultat.mesures
    code_robot, code_nav = m.get("code_http", ""), m.get("navigateur_code_http", "")
    if code_robot in CODES_ANTI_ROBOTS and code_nav.isdigit() and int(code_nav) < 400:
        avant = len(resultat.constats)
        resultat.constats = [c for c in resultat.constats if c.code not in ("HTTP_ERREUR_CLIENT", "HTTP_ERREUR_SERVEUR")]
        if len(resultat.constats) != avant:
            m["note_http"] = f"HTTP {code_robot} renvoyé au robot, mais page affichée normalement dans le navigateur (HTTP {code_nav})"


async def analyser_prospects(
    prospects: list[Prospect],
    config: Config,
    analyseurs: list[Analyseur] | None = None,
    client: httpx.AsyncClient | None = None,
    progression: Progression | None = None,
    porte: asyncio.Event | None = None,
) -> list[Resultat]:
    """Renvoie un Resultat noté par prospect, dans l'ordre d'entrée.

    `porte` (facultatif) met le scan en pause quand elle est fermée : aucun
    nouveau site ne démarre ; les sites déjà commencés se terminent.
    """
    analyseurs = analyseurs if analyseurs is not None else analyseurs_par_defaut(config)
    places = asyncio.Semaphore(config.parallelisme)
    lances = {a.nom for a in analyseurs}
    non_lances = [c.id for c in CONTROLES if c.analyseur not in lances]
    termines = 0

    async def traiter(prospect: Prospect, http: httpx.AsyncClient) -> Resultat:
        nonlocal termines
        resultat = Resultat(prospect)
        resultat.non_verifies.update(dict.fromkeys(non_lances, "analyseur non lancé"))
        valide = urls.url_valide(prospect.url)
        applicables = [a for a in analyseurs if valide or not a.requiert_url]
        for a in analyseurs:
            if a not in applicables:
                resultat.sans_objet.extend(a.controles)
        limites = [a for a in applicables if not a.file_dediee]
        dedies = [a for a in applicables if a.file_dediee]

        async with places:
            if porte is not None:
                await porte.wait()
            # Les analyseurs à file dédiée (PageSpeed) démarrent avec le site mais ne
            # retiennent pas sa place : elle se libère dès que les autres ont fini.
            taches_dediees = [asyncio.create_task(_executer(a, prospect, http, config)) for a in dedies]
            rapports_limites = list(await asyncio.gather(*(_executer(a, prospect, http, config) for a in limites)))
        rapports_dedies = list(await asyncio.gather(*taches_dediees))
        for analyseur, rapport in zip(limites + dedies, rapports_limites + rapports_dedies):
            resultat.constats.extend(rapport)
            resultat.mesures.update(rapport.mesures)
            resultat.non_verifies.update(rapport.non_verifies)
            if rapport.echec:
                resultat.echecs.append(analyseur.nom)
        consolider(resultat)
        noter(resultat, config)
        termines += 1
        if progression:
            progression(termines, len(prospects), resultat)
        return resultat

    try:
        if client is not None:
            return list(await asyncio.gather(*(traiter(p, client) for p in prospects)))
        async with creer_client(config) as http:
            return list(await asyncio.gather(*(traiter(p, http) for p in prospects)))
    finally:
        for a in analyseurs:
            try:
                await a.fermer()
            except Exception:
                pass
