"""Analyseur Navigateur : vrai Chromium sur les pages HTML locales de tests/pages."""

from __future__ import annotations

from pathlib import Path

import pytest
import respx
from PIL import Image

from chasseur.analyzers.browser import AnalyseurNavigateur, ErreurNavigateur, en_webp, slug
from chasseur.modeles import Prospect
from conftest import MAINTENANT

pytestmark = pytest.mark.usefixtures("exige_chromium")


@pytest.fixture
async def navigateur(config, signatures):
    a = AnalyseurNavigateur(config, signatures=signatures, maintenant=lambda: MAINTENANT)
    yield a
    await a.fermer()


async def analyser(navigateur, client, serveur, page, nom="Salon Test", ligne=7):
    return await navigateur.analyser(Prospect(nom=nom, url=serveur.url(page), ligne=ligne), client)


def codes(rapport):
    return sorted(c.code for c in rapport)


async def test_site_responsive_sain_et_captures(navigateur, client, serveur):
    rapport = await analyser(navigateur, client, serveur, "responsive.html")
    assert codes(rapport) == []
    m = rapport.mesures
    assert m["annee_copyright"] == str(MAINTENANT.year)  # année écrite par JavaScript : le rendu est bien exécuté
    assert m["formulaire"] == "oui" and m["lien_tel"] == "oui"
    assert m["title"] == "Salon Moderne – Coiffeur à Lyon"
    assert m["capture_date"] == "2026-09-28 12:00:00"

    bureau, mobile = Path(m["capture_bureau"]), Path(m["capture_mobile"])
    assert bureau.name == "0007-salon-test-20260928-120000-bureau.webp"
    for capture, largeur in ((bureau, 1366), (mobile, 375)):
        assert capture.is_file() and capture.stat().st_size < 150 * 1024
        with Image.open(capture) as image:
            assert image.format == "WEBP" and image.width == largeur


async def test_page_blanche(navigateur, client, serveur):
    rapport = await analyser(navigateur, client, serveur, "blanche.html")
    assert "PAGE_BLANCHE" in codes(rapport)
    assert rapport.mesures["texte_visible_car"] == "0"


async def test_page_de_parking_est_quasi_vide(navigateur, client, serveur):
    # Le parking lui-même est signalé par l'analyseur Domaine ; ici, la page est vide de contenu.
    assert "PAGE_BLANCHE" in codes(await analyser(navigateur, client, serveur, "parking.html"))


async def test_wordpress_49(navigateur, client, serveur):
    rapport = await analyser(navigateur, client, serveur, "wordpress49.html")
    assert codes(rapport) == ["ACTUALITES_ANCIENNES", "COPYRIGHT_ANCIEN", "JQUERY_OBSOLETE", "WORDPRESS_OBSOLETE"]
    m = rapport.mesures
    assert (m["cms"], m["version_wordpress"], m["version_jquery"], m["annee_copyright"]) == ("WordPress", "4.9.8", "1.12.4", "2017")
    assert m["derniere_date"] == "2018-03-14"


async def test_site_pirate(navigateur, client, serveur):
    rapport = await analyser(navigateur, client, serveur, "pirate.html")
    assert codes(rapport) == ["PIRATAGE_SPAM"]
    assert "viagra" in rapport[0].preuve and "cialis" in rapport[0].preuve


async def test_redirection_javascript_vers_domaine_tiers(navigateur, client, serveur):
    rapport = await analyser(navigateur, client, serveur, "redirection.html")
    assert codes(rapport) == ["PIRATAGE_REDIRECTION"]
    assert rapport.mesures["navigateur_url_finale"].startswith("http://localhost:")


async def test_maintenance(navigateur, client, serveur):
    assert codes(await analyser(navigateur, client, serveur, "maintenance.html")) == ["PAGE_BLANCHE", "SITE_EN_MAINTENANCE"]


async def test_erreur_php(navigateur, client, serveur):
    rapport = await analyser(navigateur, client, serveur, "erreur_php.html")
    assert "ERREUR_PHP" in codes(rapport) and "PAGE_BLANCHE" not in codes(rapport)
    assert "wp-db.php on line 1612" in next(c.preuve for c in rapport if c.code == "ERREUR_PHP")


async def test_site_ancien(navigateur, client, serveur):
    rapport = await analyser(navigateur, client, serveur, "ancien.html")
    assert codes(rapport) == [
        "CONTACT_ABSENT", "COPYRIGHT_ANCIEN", "DEFILEMENT_HORIZONTAL", "FLASH", "JQUERY_OBSOLETE",
        "META_DESCRIPTION_ABSENTE", "MISE_EN_PAGE_TABLEAUX", "VIEWPORT_ABSENT",
    ]
    assert rapport.mesures["annee_copyright"] == "2012"
    assert rapport.mesures["technologies"] == "jQuery 1.4.2, Flash, mise en page en tableaux"


async def test_defilement_horizontal_a_375_px(navigateur, client, serveur):
    rapport = await analyser(navigateur, client, serveur, "debordement.html")
    assert codes(rapport) == ["DEFILEMENT_HORIZONTAL"]
    assert rapport.mesures["largeur_mobile"].endswith("/375 px")


async def test_formulaire_trouve_sur_la_page_contact(navigateur, client, serveur):
    rapport = await analyser(navigateur, client, serveur, "accueil_contact.html")
    assert "CONTACT_ABSENT" not in codes(rapport)
    assert rapport.mesures["page_contact"].endswith("/contact.html")
    assert rapport.mesures["formulaire"] == "oui"


async def test_page_404_non_jugee(navigateur, client, serveur):
    rapport = await analyser(navigateur, client, serveur, "absente.html")
    assert codes(rapport) == []
    assert rapport.mesures["navigateur_code_http"] == "404"
    assert rapport.non_verifies["page_blanche_php"] == "page d'erreur HTTP 404"
    assert Path(rapport.mesures["capture_bureau"]).is_file()  # la capture de l'erreur reste une preuve


async def test_telechargement_bloque(navigateur, client, serveur, tmp_path):
    with pytest.raises(ErreurNavigateur, match="(?i)download"):
        await analyser(navigateur, client, serveur, "fichier.zip")
    assert not any(tmp_path.rglob("*.zip"))


async def test_site_injoignable(navigateur, client):
    with pytest.raises(ErreurNavigateur, match="inaccessible"):
        await navigateur.analyser(Prospect(url="http://127.0.0.1:9/"), client)


@respx.mock
async def test_robots_txt_respecte(navigateur, client):
    respx.get("https://interdit.test/robots.txt").respond(200, text="User-agent: *\nDisallow: /\n")
    rapport = await navigateur.analyser(Prospect(url="https://interdit.test"), client)
    assert list(rapport) == []
    assert rapport.non_verifies["responsive"] == "robots.txt interdit l'analyse"
    assert rapport.mesures["robots_txt"] == "interdit"


@respx.mock
async def test_robots_txt_autorise(navigateur, client):
    respx.get("https://a.test/robots.txt").respond(200, text="User-agent: *\nDisallow: /admin\n")
    respx.get("https://b.test/robots.txt").respond(404)
    respx.get("https://c.test/robots.txt").respond(200, text="User-agent: ChasseurDeSites\nDisallow: /\n")
    assert await navigateur._robots_autorise("https://a.test/", client)
    assert await navigateur._robots_autorise("https://b.test/", client)
    assert not await navigateur._robots_autorise("https://c.test/", client)


def test_webp_compresse_sous_la_limite(tmp_path):
    import io
    import random

    random.seed(1)
    bruit = Image.frombytes("RGB", (1366, 768), bytes(random.getrandbits(8) for _ in range(1366 * 768 * 3)))
    tampon = io.BytesIO()
    bruit.save(tampon, "PNG")
    taille = en_webp(tampon.getvalue(), tmp_path / "c.webp", 150)
    assert taille == (tmp_path / "c.webp").stat().st_size <= 150 * 1024


def test_slug():
    assert slug("Coiffure Élégance & Co !") == "coiffure-elegance-co"
    assert slug("") == "site"


async def test_echec_de_demarrage_memorise(config, signatures, client, monkeypatch):
    from dataclasses import replace

    config.navigateur = replace(config.navigateur, chromium="/chemin/inexistant/chrome")
    monkeypatch.delenv("CHASSEUR_CHROMIUM", raising=False)
    a = AnalyseurNavigateur(config, signatures=signatures)
    for _ in range(2):
        with pytest.raises(ErreurNavigateur, match="playwright install chromium"):
            await a.analyser(Prospect(url="https://x.test"), client)
    assert a._erreur_demarrage is not None
