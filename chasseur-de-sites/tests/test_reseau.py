from __future__ import annotations

import socket

import httpx
import pytest
import respx

from chasseur.analyzers.reseau import verifier_certificat
from chasseur.modeles import Prospect


def codes(constats):
    return [c.code for c in constats]


@respx.mock
async def test_site_sain_aucun_constat(analyseur, client):
    respx.get("https://ok.test/").respond(200, text="<html>Bienvenue</html>")
    assert await analyseur.analyser(Prospect(url="https://ok.test"), client) == []


@respx.mock
async def test_constat_a_la_structure_attendue(analyseur, client):
    respx.get("https://ok.test/").respond(404)
    (constat,) = await analyseur.analyser(Prospect(url="https://ok.test"), client)
    assert set(constat.en_dict()) == {"code", "gravite", "points", "message_client", "preuve"}
    assert constat.message_client and constat.preuve
    assert isinstance(constat.points, int)


# --- DNS -------------------------------------------------------------------


@respx.mock
async def test_dns_introuvable_stoppe_l_analyse(analyseur, client, ssl_simule):
    route = respx.get(host="domaine-mort.test")
    constats = await analyseur.analyser(Prospect(url="https://domaine-mort.test"), client)
    assert codes(constats) == ["DNS_INTROUVABLE"]
    assert "domaine-mort.test" in constats[0].preuve
    assert not route.called
    assert ssl_simule.appels == []
    assert set(constats.non_verifies) == {"http_5xx", "http_4xx", "ssl", "https", "ssl_expiration"}


# --- HTTP ------------------------------------------------------------------


@respx.mock
async def test_timeout_sur_les_deux_essais(analyseur, client, ssl_simule):
    route = respx.get("https://lent.test/").mock(side_effect=httpx.ReadTimeout("trop long"))
    constats = await analyseur.analyser(Prospect(url="https://lent.test"), client)
    assert codes(constats) == ["HTTP_INJOIGNABLE"]
    assert route.call_count == 2
    assert "essai 1/2" in constats[0].preuve and "essai 2/2" in constats[0].preuve
    assert "délai dépassé" in constats[0].preuve
    assert ssl_simule.appels == []  # inutile de vérifier le SSL d'un serveur muet


@respx.mock
async def test_deuxieme_essai_reussi(analyseur, client):
    route = respx.get("https://instable.test/").mock(
        side_effect=[httpx.ConnectTimeout("hoquet"), httpx.Response(200)]
    )
    assert await analyseur.analyser(Prospect(url="https://instable.test"), client) == []
    assert route.call_count == 2


@respx.mock
async def test_erreur_de_proxy_local_ne_penalise_pas_le_site(config, analyseur, client):
    from chasseur.orchestrateur import analyser_prospects

    respx.get("https://ok.test/").mock(side_effect=httpx.ProxyError("403 Forbidden"))
    (r,) = await analyser_prospects([Prospect(url="https://ok.test")], config, analyseurs=[analyseur], client=client)
    assert codes(r.constats) == ["NON_VERIFIE"]
    assert "ProxyError" in r.constats[0].preuve
    assert r.score == 0
    assert r.echecs == ["reseau"]
    assert r.etat == "À revérifier"
    assert r.non_verifies.keys() >= {"dns", "http_5xx", "ssl"}


@respx.mock
async def test_http_sans_redirection_vers_https(analyseur, client):
    respx.get("http://ok.test/").respond(200)
    rapport = await analyseur.analyser(Prospect(url="http://ok.test"), client)
    assert codes(rapport) == ["HTTPS_NON_FORCE"]
    assert rapport.mesures["code_http"] == "200"


@respx.mock
async def test_http_redirige_vers_https(analyseur, client):
    respx.get("http://ok.test/").respond(301, headers={"Location": "https://ok.test/"})
    respx.get("https://ok.test/").respond(200)
    rapport = await analyseur.analyser(Prospect(url="http://ok.test"), client)
    assert codes(rapport) == []
    assert rapport.mesures["url_finale"] == "https://ok.test/"
    assert rapport.mesures["ssl_expire_le"] == "2027-09-28"


@respx.mock
async def test_erreur_500_persistante(analyseur, client):
    route = respx.get("https://erreur500.test/").respond(500)
    constats = await analyseur.analyser(Prospect(url="https://erreur500.test"), client)
    assert codes(constats) == ["HTTP_ERREUR_SERVEUR"]
    assert "HTTP 500" in constats[0].preuve
    assert route.call_count == 2


@respx.mock
async def test_erreur_503_passagere(analyseur, client):
    respx.get("https://surcharge.test/").mock(side_effect=[httpx.Response(503), httpx.Response(200)])
    assert await analyseur.analyser(Prospect(url="https://surcharge.test"), client) == []


@respx.mock
async def test_404_sans_nouvel_essai(analyseur, client):
    route = respx.get("https://disparu.test/").respond(404)
    constats = await analyseur.analyser(Prospect(url="https://disparu.test"), client)
    assert codes(constats) == ["HTTP_ERREUR_CLIENT"]
    assert "404" in constats[0].message_client
    assert route.call_count == 1


@respx.mock
async def test_redirection_suivie_et_tracee(analyseur, client):
    respx.get("https://ok.test/").respond(301, headers={"Location": "https://ok.test/accueil"})
    respx.get("https://ok.test/accueil").respond(410)
    constats = await analyseur.analyser(Prospect(url="https://ok.test"), client)
    assert codes(constats) == ["HTTP_ERREUR_CLIENT"]
    assert "/accueil" in constats[0].preuve and "1 redirection" in constats[0].preuve


@respx.mock
async def test_url_sans_schema_bascule_sur_http(analyseur, client):
    https = respx.get("https://institut-http.test/").mock(side_effect=httpx.ConnectError("refusé"))
    http = respx.get("http://institut-http.test/").respond(200)
    constats = await analyseur.analyser(Prospect(url="institut-http.test"), client)
    assert codes(constats) == ["SSL_ABSENT"]
    assert https.call_count == 2 and http.call_count == 1


# --- SSL -------------------------------------------------------------------


@pytest.mark.parametrize(
    "hote, attendu",
    [
        ("ssl-expire.test", "SSL_EXPIRE"),
        ("deja-expire.test", "SSL_EXPIRE"),
        ("autosigne.test", "SSL_INVALIDE"),
        ("expire-bientot.test", "SSL_EXPIRE_BIENTOT"),
    ],
)
@respx.mock
async def test_constats_ssl(analyseur, client, hote, attendu):
    respx.get(f"https://{hote}/").respond(200)
    constats = await analyseur.analyser(Prospect(url=f"https://{hote}"), client)
    assert codes(constats) == [attendu]


@respx.mock
async def test_ssl_expire_bientot_donne_le_delai(analyseur, client):
    respx.get("https://expire-bientot.test/").respond(200)
    (constat,) = await analyseur.analyser(Prospect(url="https://expire-bientot.test"), client)
    assert "10 jour" in constat.message_client
    assert "08/10/2026" in constat.preuve


@respx.mock
async def test_erreur_http_et_ssl_cumulees(analyseur, client):
    respx.get("https://ssl-expire.test/").respond(500)
    constats = await analyseur.analyser(Prospect(url="https://ssl-expire.test"), client)
    assert codes(constats) == ["HTTP_ERREUR_SERVEUR", "SSL_EXPIRE"]


# --- Cas limites -----------------------------------------------------------


async def test_url_vide(analyseur, client):
    assert codes(await analyseur.analyser(Prospect(nom="Sans site"), client)) == ["SITE_ABSENT"]


@pytest.mark.parametrize("url", ["ftp://vieux.test", "https://", "http:///chemin"])
async def test_url_invalide(analyseur, client, url):
    assert codes(await analyseur.analyser(Prospect(url=url), client)) == ["URL_INVALIDE"]


async def test_verificateur_ssl_port_ferme():
    """Vrai appel TLS, hors ligne : un port fermé en local donne « absent »."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]  # port libéré à la sortie du bloc : plus personne n'écoute
    info = await verifier_certificat("127.0.0.1", port, timeout=2)
    assert info.statut == "absent"


# --- Tests sur de vrais sites (pytest -m reseau) ---------------------------


@pytest.mark.reseau
@pytest.mark.parametrize(
    "hote, statut, expire",
    [
        ("badssl.com", "valide", False),
        ("expired.badssl.com", "invalide", True),
        ("self-signed.badssl.com", "invalide", False),
        ("wrong.host.badssl.com", "invalide", False),
    ],
)
async def test_badssl_reel(hote, statut, expire):
    info = await verifier_certificat(hote, 443, timeout=15)
    assert (info.statut, info.expire) == (statut, expire)
