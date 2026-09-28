"""Outils communs : configuration de test, DNS et SSL simulés, serveur local.

Les URL de test utilisent le domaine réservé `.test` (RFC 2606) ou le
serveur local 127.0.0.1 : aucune requête ne sort réellement.
"""

from __future__ import annotations

import asyncio
import socket
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

from chasseur.analyzers.reseau import AnalyseurReseau, InfoSSL
from chasseur.config import charger_config
from chasseur.controles import PAR_ID
from chasseur.signatures import charger_signatures
from serveur_local import ServeurLocal

RACINE = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"
MAINTENANT = datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)
VARIABLES_PROXY = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")


@pytest.fixture
def config(tmp_path):
    """La vraie config.yaml du projet, sans pauses, captures dans un dossier temporaire."""
    c = charger_config(RACINE / "config.yaml")
    c.pause_entre_essais = 0
    c.performance = replace(c.performance, pause_base=0, cle_api="")
    c.navigateur = replace(c.navigateur, dossier_captures=str(tmp_path / "captures"))
    return c


@pytest.fixture
def config_fixe(config):
    """Poids figés, pour tester le scoring indépendamment de config.yaml."""
    c = replace(config)
    c.points = dict.fromkeys(PAR_ID, 0) | {
        "dns": 40, "http_4xx": 30, "ssl": 30, "https": 15, "responsive": 15,
        "copyright": 10, "technologies": 10, "title_meta": 5, "contact": 5,
    }
    c.score_max = 100
    return c


@pytest.fixture
def signatures():
    return charger_signatures(RACINE / "signatures.yaml")


@pytest.fixture(autouse=True)
def sans_cle_pagespeed(monkeypatch):
    monkeypatch.delenv("PAGESPEED_API_KEY", raising=False)


@pytest.fixture
def sans_proxy(monkeypatch):
    for var in VARIABLES_PROXY:
        monkeypatch.delenv(var, raising=False)


class DNSSimule:
    """Résout tout sauf les hôtes listés comme inexistants."""

    def __init__(self, inexistants: set[str] = frozenset()):
        self.inexistants = set(inexistants)
        self.appels: list[str] = []

    async def __call__(self, hote: str) -> list[str]:
        self.appels.append(hote)
        if hote in self.inexistants:
            raise socket.gaierror(socket.EAI_NONAME, "Name or service not known")
        return ["192.0.2.10"]


class SSLSimule:
    """Certificat valide 1 an par défaut ; surcharges par hôte."""

    def __init__(self, par_hote: dict[str, InfoSSL] | None = None):
        self.par_hote = par_hote or {}
        self.appels: list[str] = []

    async def __call__(self, hote: str, port: int, timeout: float) -> InfoSSL:
        self.appels.append(hote)
        return self.par_hote.get(
            hote, InfoSSL("valide", expire_le=MAINTENANT + timedelta(days=365), emetteur="Let's Encrypt")
        )


SSL_EXPIRE = InfoSSL("invalide", expire=True, erreur="certificate has expired")
SSL_AUTOSIGNE = InfoSSL("invalide", erreur="self-signed certificate")
SSL_ABSENT = InfoSSL("absent", erreur="port 443 : ConnectionRefusedError")


@pytest.fixture
def dns():
    return DNSSimule({"domaine-mort.test"})


@pytest.fixture
def ssl_simule():
    return SSLSimule(
        {
            "ssl-expire.test": SSL_EXPIRE,
            "autosigne.test": SSL_AUTOSIGNE,
            "institut-http.test": SSL_ABSENT,
            "expire-bientot.test": InfoSSL("valide", expire_le=MAINTENANT + timedelta(days=10), emetteur="R3"),
            "deja-expire.test": InfoSSL("valide", expire_le=MAINTENANT - timedelta(days=2)),
        }
    )


@pytest.fixture
def analyseur(config, dns, ssl_simule):
    return AnalyseurReseau(config, resolveur=dns, verificateur_ssl=ssl_simule, maintenant=lambda: MAINTENANT)


@pytest.fixture
async def client():
    async with httpx.AsyncClient(verify=False, follow_redirects=True, trust_env=False) as c:
        yield c


@pytest.fixture(scope="session")
def serveur():
    with ServeurLocal() as s:
        yield s


# --- Chromium ---------------------------------------------------------------

_chromium_disponible: bool | None = None


def chromium_disponible() -> bool:
    """Vrai si Playwright arrive à lancer Chromium (testé une seule fois)."""
    global _chromium_disponible
    if _chromium_disponible is None:
        from chasseur.analyzers.browser import AnalyseurNavigateur

        async def essai():
            a = AnalyseurNavigateur(charger_config(RACINE / "config.yaml"))
            try:
                await a._demarrer()
                return True
            except Exception:
                return False
            finally:
                await a.fermer()

        _chromium_disponible = asyncio.run(essai())
    return _chromium_disponible


@pytest.fixture
def exige_chromium():
    if not chromium_disponible():
        pytest.skip("Chromium indisponible : lancez « playwright install chromium » (ou CHASSEUR_CHROMIUM=…)")
