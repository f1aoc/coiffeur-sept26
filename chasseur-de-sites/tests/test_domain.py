from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
import pytest
import respx
import whois
from whois import exceptions as whois_exc

from chasseur.analyzers.domain import AnalyseurDomaine, ExpirationInconnue, InfoExpiration, whois_expiration
from chasseur.modeles import Prospect
from conftest import MAINTENANT

RDAP = "https://rdap.org/domain/salon.fr"


def codes(rapport):
    return [c.code for c in rapport]


def rdap(jours: int | None):
    evenements = [{"eventAction": "registration", "eventDate": "2010-01-01T00:00:00Z"}]
    if jours is not None:
        date = (MAINTENANT + timedelta(days=jours)).strftime("%Y-%m-%dT%H:%M:%SZ")
        evenements.append({"eventAction": "expiration", "eventDate": date})
    return httpx.Response(200, json={"ldhName": "salon.fr", "events": evenements})


class WhoisSimule:
    def __init__(self, reponse: InfoExpiration | Exception):
        self.reponse = reponse
        self.appels: list[str] = []

    def __call__(self, domaine: str) -> InfoExpiration:
        self.appels.append(domaine)
        if isinstance(self.reponse, Exception):
            raise self.reponse
        return self.reponse


@pytest.fixture
def domaine(config, signatures):
    def fabrique(whois=None):
        return AnalyseurDomaine(config, signatures=signatures, whois_fn=whois or WhoisSimule(ExpirationInconnue("whois : absent")), maintenant=lambda: MAINTENANT)

    return fabrique


def page_normale(texte="Salon de coiffure à Lyon"):
    return httpx.Response(200, html=f"<html><body><h1>{texte}</h1></body></html>")


# --- Expiration ---------------------------------------------------------------


@respx.mock
async def test_domaine_valide(domaine, client):
    respx.get(RDAP).mock(return_value=rdap(400))
    respx.get("https://www.salon.fr/").mock(return_value=page_normale())
    rapport = await domaine().analyser(Prospect(url="https://www.salon.fr"), client)
    assert codes(rapport) == []
    assert rapport.mesures["domaine"] == "salon.fr"
    assert rapport.mesures["domaine_source"] == "rdap"
    assert rapport.mesures["domaine_expire_le"] == (MAINTENANT + timedelta(days=400)).strftime("%Y-%m-%d")


@respx.mock
async def test_expire_dans_moins_de_30_jours(domaine, client):
    respx.get(RDAP).mock(return_value=rdap(12))
    respx.get("https://salon.fr/").mock(return_value=page_normale())
    (constat,) = await domaine().analyser(Prospect(url="salon.fr"), client)
    assert (constat.code, constat.points) == ("DOMAINE_EXPIRE_BIENTOT", 10)
    assert "10/10/2026" in constat.message_client


@respx.mock
async def test_domaine_expire(domaine, client):
    respx.get(RDAP).mock(return_value=rdap(-5))
    respx.get("https://salon.fr/").mock(return_value=page_normale())
    (constat,) = await domaine().analyser(Prospect(url="https://salon.fr"), client)
    assert (constat.code, constat.points, constat.gravite) == ("DOMAINE_EXPIRE", 40, "critique")
    assert "rdap" in constat.preuve


@respx.mock
async def test_rdap_404_puis_whois_inconnu(domaine, client):
    respx.get(RDAP).respond(404)
    respx.get("https://salon.fr/").mock(side_effect=httpx.ConnectError("refusé"))
    respx.get("http://salon.fr/").mock(side_effect=httpx.ConnectError("refusé"))
    whois = WhoisSimule(InfoExpiration(enregistre=False, source="whois", detail="No match for salon.fr"))
    rapport = await domaine(whois).analyser(Prospect(url="salon.fr"), client)
    assert codes(rapport) == ["DOMAINE_NON_ENREGISTRE"]
    assert whois.appels == ["salon.fr"]
    assert "No match" in rapport[0].preuve


@respx.mock
async def test_repli_whois_quand_rdap_echoue(domaine, client):
    respx.get(RDAP).respond(503)
    respx.get("https://salon.fr/").mock(return_value=page_normale())
    whois = WhoisSimule(InfoExpiration(expire_le=MAINTENANT + timedelta(days=5), enregistre=True, source="whois"))
    rapport = await domaine(whois).analyser(Prospect(url="https://salon.fr"), client)
    assert codes(rapport) == ["DOMAINE_EXPIRE_BIENTOT"]
    assert rapport.mesures["domaine_source"] == "whois"


@respx.mock
async def test_repli_whois_quand_rdap_n_a_pas_de_date(domaine, client):
    respx.get(RDAP).mock(return_value=rdap(None))
    respx.get("https://salon.fr/").mock(return_value=page_normale())
    whois = WhoisSimule(InfoExpiration(expire_le=MAINTENANT + timedelta(days=300), enregistre=True, source="whois"))
    rapport = await domaine(whois).analyser(Prospect(url="https://salon.fr"), client)
    assert codes(rapport) == [] and whois.appels == ["salon.fr"]


@respx.mock
async def test_ni_rdap_ni_whois(domaine, client):
    respx.get(RDAP).mock(side_effect=httpx.ConnectTimeout("lent"))
    respx.get("https://salon.fr/").mock(return_value=page_normale())
    rapport = await domaine().analyser(Prospect(url="https://salon.fr"), client)
    assert codes(rapport) == []
    assert "RDAP : ConnectTimeout" in rapport.non_verifies["domaine_expiration"]
    assert "domaine" not in rapport.non_verifies  # le parking, lui, a été vérifié


async def test_ip_et_tld_reserve_sans_whois(domaine, client, serveur):
    rapport = await domaine().analyser(Prospect(url=serveur.url("responsive.html")), client)
    assert codes(rapport) == []
    assert rapport.non_verifies["domaine_expiration"] == "pas un nom de domaine public"


# --- Parking ----------------------------------------------------------------


@respx.mock
async def test_redirection_vers_sedo(domaine, client):
    respx.get(RDAP).mock(return_value=rdap(400))
    respx.get("https://salon.fr/").respond(302, headers={"Location": "https://sedo.com/search/details/?domain=salon.fr"})
    respx.get("https://sedo.com/search/details/?domain=salon.fr").mock(return_value=page_normale("Sedo"))
    (constat,) = await domaine().analyser(Prospect(url="https://salon.fr"), client)
    assert constat.code == "DOMAINE_PARKING" and constat.points == 40
    assert "sedo.com" in constat.preuve and "→" in constat.preuve


@pytest.mark.parametrize(
    "html",
    [
        "<h1>This domain is for sale!</h1>",
        "<p>Le nom de domaine salon.fr est à vendre. Ce domaine est à vendre.</p>",
        '<script src="https://img.sedoparking.com/js/park.js"></script>',
        "<p>Buy this domain on Afternic</p>",
    ],
)
@respx.mock
async def test_page_de_parking_par_mots_cles(domaine, client, html):
    respx.get(RDAP).mock(return_value=rdap(400))
    respx.get("https://salon.fr/").respond(200, html=f"<html><body>{html}</body></html>")
    assert codes(await domaine().analyser(Prospect(url="https://salon.fr"), client)) == ["DOMAINE_PARKING"]


@respx.mock
async def test_mention_godaddy_n_est_pas_un_parking(domaine, client):
    respx.get(RDAP).mock(return_value=rdap(400))
    respx.get("https://salon.fr/").mock(return_value=page_normale("Salon — Site créé avec GoDaddy Website Builder"))
    assert codes(await domaine().analyser(Prospect(url="https://salon.fr"), client)) == []


async def test_page_de_parking_locale(domaine, client, serveur):
    rapport = await domaine().analyser(Prospect(url=serveur.url("parking.html")), client)
    assert codes(rapport) == ["DOMAINE_PARKING"]
    assert "est à vendre" in rapport[0].preuve


async def test_page_normale_locale(domaine, client, serveur):
    assert codes(await domaine().analyser(Prospect(url=serveur.url("responsive.html")), client)) == []


# --- Repli python-whois (bibliothèque simulée) -------------------------------------


@pytest.mark.parametrize(
    "reponse, attendu",
    [
        ({"expiration_date": [datetime(2027, 1, 5), datetime(2027, 1, 5, 12)]}, ("2027-01-05", True)),
        ({"expiration_date": datetime(2026, 12, 1, tzinfo=timezone.utc)}, ("2026-12-01", True)),
        (whois_exc.PywhoisError("No match for \"salon-libre.fr\"."), (None, False)),
    ],
)
def test_whois_expiration(monkeypatch, reponse, attendu):
    def faux_whois(domaine, quiet=True):
        if isinstance(reponse, Exception):
            raise reponse
        return reponse

    monkeypatch.setattr(whois, "whois", faux_whois)
    info = whois_expiration("salon.fr")
    assert (info.expire_le.strftime("%Y-%m-%d") if info.expire_le else None, info.enregistre) == attendu
    assert info.source == "whois"


@pytest.mark.parametrize(
    "reponse", [{"expiration_date": None}, whois_exc.PywhoisError("Socket error: connection refused")]
)
def test_whois_sans_conclusion(monkeypatch, reponse):
    def faux_whois(domaine, quiet=True):
        if isinstance(reponse, Exception):
            raise reponse
        return reponse

    monkeypatch.setattr(whois, "whois", faux_whois)
    with pytest.raises(ExpirationInconnue):
        whois_expiration("salon.fr")
