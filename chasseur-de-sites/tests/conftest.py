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


# --- Interface web (Lot 3) ------------------------------------------------------------

from chasseur.analyzers import Analyseur  # noqa: E402
from chasseur.modeles import Rapport  # noqa: E402


class FauxAnalyseur(Analyseur):
    """Analyseur instantané : le résultat dépend de mots présents dans l'URL.

    « casse » → erreur serveur (Cassé) ; « vieux » → pas de HTTPS ni viewport (Obsolète, 30 pts) ;
    sinon rien (Correct). `duree` ralentit l'analyse (tests de pause)."""

    nom = "reseau"
    requiert_url = False

    def __init__(self, config, duree: float = 0.0):
        super().__init__(config)
        self.duree = duree

    async def analyser(self, prospect, client):
        if self.duree:
            await asyncio.sleep(self.duree)
        c = self.config
        if not prospect.url:
            return Rapport([c.constat("SITE_ABSENT", "Aucun site.", "colonne url vide")])
        if "casse" in prospect.url:
            return Rapport([c.constat("HTTP_ERREUR_SERVEUR", "Votre site affiche une erreur.", "HTTP 500")], mesures={"code_http": "500"})
        if "vieux" in prospect.url:
            return Rapport(
                [c.constat("SSL_ABSENT", "Pas de HTTPS.", "port 443 fermé"), c.constat("VIEWPORT_ABSENT", "Pas mobile.", "pas de viewport")],
                mesures={"code_http": "200"},
            )
        return Rapport(mesures={"code_http": "200"})


@pytest.fixture
def stockage(tmp_path):
    from chasseur.db import Stockage

    return Stockage(tmp_path / "donnees")


@pytest.fixture
def fabrique_web(stockage):
    """Fabrique une application web de test (analyseurs remplaçables)."""
    from fastapi.testclient import TestClient

    from chasseur.web.app import creer_app
    from chasseur.web.taches import GestionnaireScans

    ouverts = []

    def fabrique(analyseurs=None, duree: float = 0.0):
        def faux(config):
            config.pause_entre_essais = 0
            return analyseurs(config) if analyseurs else [FauxAnalyseur(config, duree)]

        gestionnaire = GestionnaireScans(stockage, fabrique_analyseurs=faux, chemin_config=RACINE / "config.yaml")
        app = creer_app(stockage, gestionnaire, chemin_config=RACINE / "config.yaml", hotes=["testserver", "127.0.0.1"])
        client = TestClient(app, follow_redirects=False)
        client.__enter__()
        ouverts.append(client)
        return client

    yield fabrique
    for c in ouverts:
        c.__exit__(None, None, None)


@pytest.fixture
def web(fabrique_web):
    return fabrique_web()


def attendre_fin(web, scan_id: int, delai: float = 60.0) -> str:
    """Interroge l'écran Progression jusqu'à la fin du scan ; renvoie le dernier fragment."""
    import time

    fin = time.monotonic() + delai
    while time.monotonic() < fin:
        fragment = web.get(f"/analyses/{scan_id}/progression").text
        if 'hx-trigger="every 1s"' not in fragment:
            return fragment
        time.sleep(0.1)
    raise AssertionError(f"scan {scan_id} non terminé après {delai} s")


def televerser(web, nom: str, contenu: bytes | str, type_mime: str = "text/csv"):
    if isinstance(contenu, str):
        contenu = contenu.encode("utf-8")
    return web.post("/analyses/apercu", files={"fichier": (nom, contenu, type_mime)})


def lancer_scan(web, nom: str, contenu: str) -> int:
    import re

    fichier = nom if nom.endswith((".csv", ".xlsx")) else f"{nom}.csv"
    apercu = televerser(web, fichier, contenu).text
    jeton = re.search(r'name="jeton" value="([^"]+)"', apercu)
    assert jeton, apercu
    r = web.post("/analyses", data={"jeton": jeton[1], "nom": nom, "nom_fichier": fichier})
    assert r.status_code == 303, r.text
    return int(r.headers["location"].rsplit("/", 1)[1])


# --- Rapports (Lot 4) -----------------------------------------------------------------

LOGO_SVG = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 10"><rect width="40" height="10" fill="#0a7"/></svg>'


@pytest.fixture
def base_rapports(stockage, config):
    """Trois prospects analysés : cassé, obsolète, correct ; captures et agence renseignées."""
    from PIL import Image

    from chasseur.db import depot
    from chasseur.db.agence import ecrire_agence, enregistrer_logo
    from chasseur.modeles import Prospect, Resultat
    from chasseur.scoring import noter

    prospects = [
        Prospect(nom="Salon Cassé", url="https://casse.test", ville="Avignon", telephone="04 90 00 00 01", note_google=4.6, nb_avis=52),
        Prospect(nom="Institut Vieillot", url="https://vieux.test", ville="Apt", telephone="04 90 00 00 02"),
        Prospect(nom="Coiffure Impeccable", url="https://ok.test", ville="Cavaillon"),
    ]
    codes = [
        ["DOMAINE_PARKING", "PAGE_BLANCHE", "SSL_ABSENT", "VIEWPORT_ABSENT", "META_DESCRIPTION_ABSENTE", "CONTACT_ABSENT", "NON_VERIFIE"],
        ["WORDPRESS_OBSOLETE", "JQUERY_OBSOLETE", "COPYRIGHT_ANCIEN", "SSL_ABSENT", "VIEWPORT_ABSENT"],
        [],
    ]
    mesures = [{}, {"version_wordpress": "4.9.8", "annee_copyright": "2017"}, {}]
    with stockage.session() as s:
        scan = depot.creer_scan(s, "Vaucluse", prospects, fichier="vaucluse.csv")
        ids = sorted(p.id for p in depot.a_analyser(s, scan.id))
        dossier = stockage.dossier_captures / f"scan-{scan.id}"
        dossier.mkdir(parents=True)
        for i, prospect_id in enumerate(ids):
            Image.new("RGB", (1366, 768), (240, 240, 245)).save(dossier / f"{i}-bureau.webp", "WEBP")
            Image.new("RGB", (375, 667), (230, 235, 240)).save(dossier / f"{i}-mobile.webp", "WEBP")
            r = Resultat(
                Prospect(),
                [config.constat(c, f"message {c}", f"preuve {c}") for c in codes[i]],
                mesures={**mesures[i], "capture_bureau": str(dossier / f"{i}-bureau.webp"),
                         "capture_mobile": str(dossier / f"{i}-mobile.webp"), "capture_date": "2026-09-28 10:30:00"},
            )
            depot.enregistrer_resultat(stockage, s, prospect_id, noter(r, config))
        ecrire_agence(s, nom="Atelier Web Provence", couleur="#0a7f5a", telephone="06 12 34 56 78",
                      email="bonjour@atelier-web.test", site="atelier-web.test")
        enregistrer_logo(stockage, s, "logo.svg", LOGO_SVG)
        s.commit()
    return dict(zip(("casse", "obsolete", "correct"), ids)) | {"scan": scan.id}


def moteurs_pdf_disponibles() -> list[str]:
    from chasseur.reports.pdf import weasyprint_disponible

    return (["weasyprint"] if weasyprint_disponible() else []) + (["chromium"] if chromium_disponible() else [])


def texte_pdf(contenu: bytes) -> tuple[int, str]:
    """(nombre de pages, texte) d'un PDF."""
    import io

    from pypdf import PdfReader

    lecteur = PdfReader(io.BytesIO(contenu))
    return len(lecteur.pages), "\n".join(page.extract_text() for page in lecteur.pages)
