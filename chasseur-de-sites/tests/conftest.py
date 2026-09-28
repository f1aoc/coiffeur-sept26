"""Outils communs : configuration de test, DNS et SSL simulés.

Les URL de test utilisent le domaine réservé `.test` (RFC 2606) : aucune
requête ne sort réellement, toutes les réponses HTTP sont simulées par respx.
"""

from __future__ import annotations

import socket
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

from chasseur.analyzers.reseau import AnalyseurReseau, InfoSSL
from chasseur.config import charger_config, config_depuis_dict

RACINE = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"
MAINTENANT = datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def config():
    """La vraie config.yaml du projet, sans pause entre les essais."""
    return replace(charger_config(RACINE / "config.yaml"), pause_entre_essais=0)


@pytest.fixture
def config_fixe():
    """Config aux poids figés, pour tester le scoring indépendamment de config.yaml."""
    return config_depuis_dict(
        {
            "constats": {
                "A_CRITIQUE": {"gravite": "critique", "points": 50},
                "B_HAUTE": {"gravite": "haute", "points": 30},
                "C_MOYENNE": {"gravite": "moyenne", "points": 10},
                "D_INFO": {"gravite": "info", "points": 0},
            },
            "score_max": 100,
            "priorites": [
                {"min": 1, "label": "C"},
                {"min": 60, "label": "A"},
                {"min": 30, "label": "B"},
                {"min": 0, "label": "D"},
            ],
        }
    )


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
