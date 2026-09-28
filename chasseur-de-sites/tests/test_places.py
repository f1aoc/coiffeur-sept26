"""Recherche Google Places (API officielle, réponses simulées)."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from chasseur.config import ConfigPlaces
from chasseur.sources import places

CONFIG = ConfigPlaces(pause_pages=0)


def fiche(i, site="", statut="OPERATIONAL", **autres):
    return {
        "id": f"lieu-{i}", "displayName": {"text": f"Salon {i}"}, "websiteUri": site, "businessStatus": statut,
        "formattedAddress": f"{i} rue de la Paix, 84000 Avignon, France", "nationalPhoneNumber": f"04 90 00 00 {i:02d}",
        "primaryTypeDisplayName": {"text": "Coiffeur"}, "rating": 4.5, "userRatingCount": 30 + i,
        "googleMapsUri": f"https://maps.google.com/?cid={i}", **autres,
    }


def test_estimation_du_cout():
    e = places.estimer(["Avignon", "Apt"], 3, ConfigPlaces(prix_1000_requetes=35))
    assert (e.requetes_max, e.cout_max) == (6, 0.21)
    assert "Au plus 6 requêtes" in e.texte and "0,21 USD" in e.texte and "35 USD les 1 000 requêtes" in e.texte
    assert places.estimer(["Apt"], 9, ConfigPlaces(pages_max=3)).requetes_max == 3  # plafonné


@respx.mock
async def test_recherche_ne_garde_que_les_fiches_avec_un_site():
    route = respx.post(places.API).mock(side_effect=[
        httpx.Response(200, json={"places": [fiche(1, "https://salon1.fr/"), fiche(2), fiche(3, "https://www.facebook.com/salon3"),
                                             fiche(4, "https://salon4.fr", statut="CLOSED_PERMANENTLY")], "nextPageToken": "p2"}),
        httpx.Response(200, json={"places": [fiche(5, "https://salon5.fr"), fiche(1, "https://salon1.fr/")]}),
        httpx.Response(200, json={"places": [fiche(6, "https://salon6.fr")]}),
    ])
    r = await places.rechercher("CLE-TEST", "coiffeur", ["Avignon", "Apt"], CONFIG, pages=3)
    assert [p.nom for p in r.prospects] == ["Salon 1", "Salon 5", "Salon 6"]  # doublon d'id ignoré
    assert (r.sans_site, r.pages_tierces, r.fermees, r.requetes) == (1, 1, 1, 3)
    p = r.prospects[0]
    assert (p.url, p.telephone, p.ville, p.categorie, p.note_google, p.nb_avis, p.lien_maps) == (
        "https://salon1.fr/", "04 90 00 00 01", "Avignon", "Coiffeur", 4.5, 31, "https://maps.google.com/?cid=1"
    )
    premiere = route.calls[0].request
    corps = json.loads(premiere.content)
    assert corps["textQuery"] == "coiffeur Avignon" and corps["languageCode"] == "fr" and "pageToken" not in corps
    assert premiere.headers["X-Goog-Api-Key"] == "CLE-TEST"
    assert "places.websiteUri" in premiere.headers["X-Goog-FieldMask"] and "nextPageToken" in premiere.headers["X-Goog-FieldMask"]
    assert json.loads(route.calls[1].request.content)["pageToken"] == "p2"
    assert json.loads(route.calls[2].request.content)["textQuery"] == "coiffeur Apt"


@pytest.mark.parametrize("code, message", [(403, r"Places API \(New\)"), (429, "Quota"), (400, "secteur"), (500, "HTTP 500")])
@respx.mock
async def test_erreurs_expliquees(code, message):
    respx.post(places.API).respond(code, json={"error": {"message": "x"}})
    with pytest.raises(places.ErreurPlaces, match=message):
        await places.rechercher("CLE", "coiffeur", ["Apt"], CONFIG)


async def test_sans_cle():
    with pytest.raises(places.ErreurPlaces, match="Aucune clé"):
        await places.rechercher("", "coiffeur", ["Apt"], CONFIG)


@respx.mock
async def test_reseau_coupe():
    respx.post(places.API).mock(side_effect=httpx.ConnectError("coupé"))
    with pytest.raises(places.ErreurPlaces, match="injoignable"):
        await places.rechercher("CLE", "coiffeur", ["Apt"], CONFIG)


@pytest.mark.parametrize("url, tierce", [("https://www.facebook.com/x", True), ("https://m.facebook.com/x", True),
                                          ("https://www.planity.com/x", True), ("https://salon.fr", False)])
def test_pages_tierces(url, tierce):
    assert places.page_tierce(url) is tierce
