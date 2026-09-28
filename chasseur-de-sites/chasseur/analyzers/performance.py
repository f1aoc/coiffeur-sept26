"""Analyseur Performance : score mobile de l'API PageSpeed Insights.

Les appels passent par une file d'attente dédiée (FileDAttente) qui espace les
requêtes selon le quota configuré et limite le nombre d'appels simultanés.
Sur une erreur 429 (quota dépassé) ou 5xx, toute la file est mise en pause
(Retry-After de l'API, sinon attente doublée à chaque fois) puis l'appel est relancé.
Sans clé API : constat « non vérifié », le scan continue.
La clé n'apparaît jamais dans les constats, les mesures ni les messages d'erreur (§6.4).
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

import httpx

from chasseur import urls
from chasseur.analyzers.base import Analyseur
from chasseur.config import Config
from chasseur.controles import CODE_NON_VERIFIE
from chasseur.modeles import Prospect, Rapport

API_PAGESPEED = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"


class FileDAttente:
    """Au plus `simultanees` appels en cours, et au moins `intervalle` s entre deux départs."""

    def __init__(self, simultanees: int, par_minute: float):
        self._places = asyncio.Semaphore(max(1, simultanees))
        self._intervalle = 60.0 / par_minute if par_minute > 0 else 0.0
        self._verrou = asyncio.Lock()
        self._prochain_depart = 0.0

    @asynccontextmanager
    async def place(self):
        async with self._places:
            async with self._verrou:  # verrou équitable : les appels partent dans l'ordre d'arrivée
                boucle = asyncio.get_running_loop()
                attente = self._prochain_depart - boucle.time()
                if attente > 0:
                    await asyncio.sleep(attente)
                self._prochain_depart = max(boucle.time(), self._prochain_depart) + self._intervalle
            yield

    def pause(self, secondes: float) -> None:
        """Repousse tous les prochains départs (après un 429)."""
        maintenant = asyncio.get_running_loop().time()
        self._prochain_depart = max(self._prochain_depart, maintenant + secondes)


def _retry_after(reponse: httpx.Response) -> float | None:
    try:
        return max(0.0, float(reponse.headers.get("retry-after", "")))
    except ValueError:
        return None


class AnalyseurPerformance(Analyseur):
    nom = "performance"
    file_dediee = True

    def __init__(self, config: Config):
        super().__init__(config)
        p = config.performance
        self.file = FileDAttente(p.simultanees, p.requetes_par_minute)
        self._client: httpx.AsyncClient | None = None

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            # Client à part : certificat vérifié (c'est l'API Google, pas le site analysé).
            self._client = httpx.AsyncClient(timeout=self.config.performance.timeout)
        return self._client

    async def fermer(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _masquer(self, texte: str) -> str:
        cle = self.config.performance.cle
        return texte.replace(cle, "***") if cle else texte

    def _non_verifie(self, raison: str, echec: bool) -> Rapport:
        raison = self._masquer(raison)
        return Rapport(
            [self.config.constat(CODE_NON_VERIFIE, "Vitesse du site non vérifiée.", f"performance : {raison}")],
            non_verifies={"performance": raison},
            echec=echec,
        )

    async def analyser(self, prospect: Prospect, client: httpx.AsyncClient) -> Rapport:
        p = self.config.performance
        if not p.cle:
            return self._non_verifie("pas de clé API PageSpeed Insights (config.yaml ou PAGESPEED_API_KEY)", echec=False)

        url = urls.candidates(prospect.url)[0]
        params = {"url": url, "strategy": p.strategie, "category": "performance", "key": p.cle}
        derniere_erreur = ""
        for tentative in range(p.max_relances + 1):
            async with self.file.place():
                try:
                    reponse = await self._http().get(API_PAGESPEED, params=params, timeout=p.timeout)
                except httpx.HTTPError as e:
                    reponse = None
                    derniere_erreur = f"appel à l'API impossible ({type(e).__name__})"
            if reponse is not None and reponse.status_code == 200:
                return self._interpreter(reponse, url)
            if reponse is not None and reponse.status_code not in (429,) and reponse.status_code < 500:
                return self._non_verifie(f"PageSpeed a refusé l'analyse : {self._message_api(reponse)}", echec=True)
            if reponse is not None:
                derniere_erreur = f"HTTP {reponse.status_code} : {self._message_api(reponse)}"
            if tentative < p.max_relances:
                attente = (_retry_after(reponse) if reponse is not None else None) or p.pause_base * 2**tentative
                self.file.pause(attente)
        return self._non_verifie(f"abandon après {p.max_relances + 1} essais ({derniere_erreur})", echec=True)

    @staticmethod
    def _message_api(reponse: httpx.Response) -> str:
        try:
            return str(reponse.json()["error"]["message"])[:200]
        except (ValueError, KeyError, TypeError):
            return reponse.reason_phrase or "erreur inconnue"

    def _interpreter(self, reponse: httpx.Response, url: str) -> Rapport:
        p = self.config.performance
        try:
            resultat = reponse.json()["lighthouseResult"]
            score = resultat["categories"]["performance"]["score"]
            audits = resultat.get("audits", {})
        except (ValueError, KeyError, TypeError):
            return self._non_verifie("réponse PageSpeed illisible", echec=True)
        if score is None:
            return self._non_verifie("PageSpeed n'a pas pu mesurer la page", echec=True)

        def valeur(audit: str) -> float | None:
            v = audits.get(audit, {}).get("numericValue")
            return float(v) if isinstance(v, (int, float)) else None

        note = round(score * 100)
        lcp, cls, tbt = valeur("largest-contentful-paint"), valeur("cumulative-layout-shift"), valeur("total-blocking-time")
        mesures = {"perf_score": str(note)}
        if lcp is not None:
            mesures["perf_lcp_s"] = f"{lcp / 1000:.1f}"
        if cls is not None:
            mesures["perf_cls"] = f"{cls:.2f}"
        if tbt is not None:
            mesures["perf_tbt_ms"] = str(round(tbt))
        rapport = Rapport(mesures=mesures)
        if note < p.seuil:
            detail = f" : il faut {lcp / 1000:.1f} s pour afficher son contenu principal" if lcp else ""
            rapport.append(
                self.config.constat(
                    "PERF_LENTE",
                    f"Sur téléphone, votre site est lent{detail}. Une partie des visiteurs part avant la fin "
                    "du chargement.",
                    f"PageSpeed Insights ({p.strategie}) : score {note}/100 (seuil {p.seuil}) pour {url}",
                )
            )
        return rapport
