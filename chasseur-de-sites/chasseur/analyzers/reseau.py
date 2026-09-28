"""Analyseur Réseau : DNS, code HTTP, certificat SSL.

Les trois vérifications s'enchaînent et s'arrêtent dès qu'une étape rend les
suivantes sans objet (un domaine qui ne résout pas n'a pas de code HTTP).
Le résolveur DNS et le vérificateur SSL sont injectables pour les tests.
"""

from __future__ import annotations

import asyncio
import socket
import ssl
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Awaitable, Callable
from urllib.parse import urlsplit

import httpx

from chasseur.analyzers.base import Analyseur
from chasseur.config import Config
from chasseur import urls
from chasseur.modeles import Constat, Prospect, Rapport

X509_V_ERR_CERT_HAS_EXPIRED = 10


@dataclass
class InfoSSL:
    statut: str  # "valide", "invalide" ou "absent" (pas de HTTPS sur le port 443)
    expire_le: datetime | None = None
    expire: bool = False  # certificat présenté mais expiré
    erreur: str = ""
    emetteur: str = ""


Resolveur = Callable[[str], Awaitable[list[str]]]
VerificateurSSL = Callable[[str, int, float], Awaitable[InfoSSL]]


async def resoudre_dns(hote: str) -> list[str]:
    boucle = asyncio.get_running_loop()
    infos = await boucle.getaddrinfo(hote, None, type=socket.SOCK_STREAM)
    return sorted({info[4][0] for info in infos})


def _emetteur(cert: dict) -> str:
    for rdn in cert.get("issuer", ()):
        for cle, valeur in rdn:
            if cle in ("organizationName", "commonName"):
                return valeur
    return ""


async def verifier_certificat(hote: str, port: int = 443, timeout: float = 15.0) -> InfoSSL:
    """Ouvre une connexion TLS vérifiée et lit la date d'expiration du certificat."""
    contexte = ssl.create_default_context()
    try:
        _, ecrivain = await asyncio.wait_for(
            asyncio.open_connection(hote, port, ssl=contexte, server_hostname=hote), timeout
        )
    except ssl.SSLCertVerificationError as e:
        return InfoSSL(
            "invalide",
            expire=e.verify_code == X509_V_ERR_CERT_HAS_EXPIRED,
            erreur=e.verify_message or str(e),
        )
    except ssl.SSLError as e:
        return InfoSSL("invalide", erreur=f"échec de la négociation TLS : {e.reason or e}")
    except (OSError, asyncio.TimeoutError) as e:
        return InfoSSL("absent", erreur=f"port {port} : {type(e).__name__} {e}".strip())

    try:
        cert = ecrivain.get_extra_info("peercert") or {}
        expire_le = None
        if cert.get("notAfter"):
            expire_le = datetime.fromtimestamp(ssl.cert_time_to_seconds(cert["notAfter"]), tz=timezone.utc)
        return InfoSSL("valide", expire_le=expire_le, emetteur=_emetteur(cert))
    finally:
        ecrivain.close()
        try:
            await ecrivain.wait_closed()
        except (OSError, ssl.SSLError):
            pass


def _decrire_erreur(e: Exception) -> str:
    if isinstance(e, httpx.TimeoutException):
        return f"délai dépassé ({type(e).__name__})"
    if isinstance(e, httpx.ConnectError):
        return f"connexion impossible ({e})"
    return f"{type(e).__name__} : {e}"


class AnalyseurReseau(Analyseur):
    nom = "reseau"
    requiert_url = False  # c'est lui qui signale l'absence d'URL

    def __init__(
        self,
        config: Config,
        resolveur: Resolveur | None = None,
        verificateur_ssl: VerificateurSSL | None = None,
        maintenant: Callable[[], datetime] | None = None,
    ):
        super().__init__(config)
        self._resolveur = resolveur
        self._verificateur_ssl = verificateur_ssl
        self._maintenant = maintenant or (lambda: datetime.now(timezone.utc))

    # Résolus à l'appel pour qu'un test puisse remplacer les fonctions du module.
    @property
    def resolveur(self) -> Resolveur:
        return self._resolveur or resoudre_dns

    @property
    def verificateur_ssl(self) -> VerificateurSSL:
        return self._verificateur_ssl or verifier_certificat

    async def analyser(self, prospect: Prospect, client: httpx.AsyncClient) -> Rapport:
        c = self.config
        suite = ["dns", "http_5xx", "http_4xx", "ssl", "https", "ssl_expiration"]
        brut = prospect.url.strip()
        if not brut:
            return Rapport(
                [c.constat("SITE_ABSENT", "Aucun site web n'est référencé pour votre entreprise.", "colonne url vide")],
                non_verifies=dict.fromkeys(suite, "pas d'URL"),
            )

        candidats = urls.candidates(brut)
        hote = urls.hote(brut)
        if not hote:
            return Rapport(
                [c.constat("URL_INVALIDE", "L'adresse de votre site semble mal saisie.", f"url illisible : {brut!r}")],
                non_verifies=dict.fromkeys(suite, "URL illisible"),
            )

        # 1. DNS
        try:
            ips = await asyncio.wait_for(self.resolveur(hote), c.timeout)
            if not ips:
                raise OSError("aucune adresse IP")
        except (OSError, asyncio.TimeoutError) as e:
            return Rapport(
                [
                    c.constat(
                        "DNS_INTROUVABLE",
                        "Votre nom de domaine ne pointe plus vers aucun serveur : votre site n'existe plus aux yeux "
                        "des internautes (domaine expiré ou mal configuré).",
                        f"résolution DNS de {hote} impossible : {type(e).__name__} {e}".strip(),
                    )
                ],
                non_verifies=dict.fromkeys(suite[1:], "domaine introuvable"),
            )
        rapport = Rapport(mesures={"ip": ", ".join(ips)})

        # 2. HTTP
        reponse, journal = await self._premiere_reponse(client, candidats)
        if reponse is None:
            rapport.append(
                c.constat(
                    "HTTP_INJOIGNABLE",
                    "Votre site ne répond pas : les visiteurs tombent sur une page d'erreur ou attendent indéfiniment.",
                    f"{hote} ({', '.join(ips)}) : " + " ; ".join(journal),
                )
            )
            rapport.non_verifies.update(dict.fromkeys(["http_4xx", "ssl", "https", "ssl_expiration"], "site injoignable"))
            return rapport

        code = reponse.status_code
        url_finale = str(reponse.url)
        rapport.mesures.update({"code_http": str(code), "url_finale": url_finale})
        preuve_http = f"GET {reponse.request.url} → HTTP {code}"
        if reponse.history:
            preuve_http += f" (après {len(reponse.history)} redirection(s) depuis {reponse.history[0].request.url})"
        if code >= 500:
            rapport.append(
                c.constat(
                    "HTTP_ERREUR_SERVEUR",
                    "Votre site affiche une erreur serveur : les visiteurs voient une page cassée au lieu de votre vitrine.",
                    preuve_http,
                )
            )
        elif code >= 400:
            rapport.append(
                c.constat(
                    "HTTP_ERREUR_CLIENT",
                    "La page d'accueil de votre site est introuvable ou refusée (erreur " + str(code) + ").",
                    preuve_http,
                )
            )

        # 3. SSL et HTTPS
        constats_ssl, info = await self._analyser_ssl(hote)
        rapport.extend(constats_ssl)
        if info.expire_le:
            rapport.mesures["ssl_expire_le"] = info.expire_le.strftime("%Y-%m-%d")
        if info.emetteur:
            rapport.mesures["ssl_emetteur"] = info.emetteur
        if info.statut != "absent" and urlsplit(url_finale).scheme == "http":
            rapport.append(
                c.constat(
                    "HTTPS_NON_FORCE",
                    "Votre site s'ouvre sans cadenas (« Non sécurisé » dans le navigateur) alors qu'une version "
                    "sécurisée existe : les visiteurs n'y sont pas redirigés.",
                    f"{preuve_http} : la page finale est en HTTP, sans redirection vers HTTPS",
                )
            )
        return rapport

    async def _premiere_reponse(
        self, client: httpx.AsyncClient, candidats: list[str]
    ) -> tuple[httpx.Response | None, list[str]]:
        """Essaie chaque URL candidate jusqu'à obtenir une réponse HTTP.

        Pour une même URL : jusqu'à `essais` tentatives si erreur réseau ou 5xx.
        Une réponse 5xx définitive est renvoyée (c'est un constat, pas un échec).
        """
        journal: list[str] = []
        for url in candidats:
            derniere: httpx.Response | None = None
            for essai in range(1, self.config.essais + 1):
                if essai > 1 and self.config.pause_entre_essais:
                    await asyncio.sleep(self.config.pause_entre_essais)
                try:
                    derniere = await client.get(url, timeout=self.config.timeout, follow_redirects=True)
                except httpx.ProxyError:
                    raise  # problème de notre réseau, pas du site : ne pas pénaliser le prospect
                except httpx.HTTPError as e:
                    journal.append(f"{url} essai {essai}/{self.config.essais} : {_decrire_erreur(e)}")
                    continue
                if derniere.status_code < 500:
                    return derniere, journal
                journal.append(f"{url} essai {essai}/{self.config.essais} : HTTP {derniere.status_code}")
            if derniere is not None:
                return derniere, journal
        return None, journal

    async def _analyser_ssl(self, hote: str) -> tuple[list[Constat], InfoSSL]:
        c = self.config
        info = await self.verificateur_ssl(hote, 443, c.timeout)
        return self._constats_ssl(hote, info), info

    def _constats_ssl(self, hote: str, info: InfoSSL) -> list[Constat]:
        c = self.config

        if info.statut == "absent":
            return [
                c.constat(
                    "SSL_ABSENT",
                    "Votre site n'est pas sécurisé (pas de HTTPS) : les navigateurs affichent « Non sécurisé » "
                    "à vos visiteurs et Google le pénalise.",
                    f"aucune connexion HTTPS possible sur {hote}:443 ({info.erreur})",
                )
            ]
        if info.statut == "invalide":
            if info.expire:
                return [
                    c.constat(
                        "SSL_EXPIRE",
                        "Le certificat de sécurité de votre site a expiré : les navigateurs bloquent vos visiteurs "
                        "avec un avertissement rouge.",
                        f"{hote} : {info.erreur}",
                    )
                ]
            return [
                c.constat(
                    "SSL_INVALIDE",
                    "Le certificat de sécurité de votre site n'est pas reconnu : les navigateurs affichent un "
                    "avertissement à vos visiteurs.",
                    f"{hote} : {info.erreur}",
                )
            ]

        if info.expire_le is None:
            return []
        jours = (info.expire_le - self._maintenant()).days
        date = info.expire_le.strftime("%d/%m/%Y")
        if jours < 0:
            return [
                c.constat(
                    "SSL_EXPIRE",
                    "Le certificat de sécurité de votre site a expiré.",
                    f"{hote} : certificat expiré le {date}",
                )
            ]
        if jours <= c.ssl_alerte_jours:
            return [
                c.constat(
                    "SSL_EXPIRE_BIENTOT",
                    f"Le certificat de sécurité de votre site expire dans {jours} jour(s) : sans renouvellement, "
                    "vos visiteurs verront un avertissement.",
                    f"{hote} : certificat valide jusqu'au {date} ({jours} j), émis par {info.emetteur or 'inconnu'}",
                )
            ]
        return []
