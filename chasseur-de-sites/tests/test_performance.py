from __future__ import annotations

import asyncio
from dataclasses import replace

import httpx
import pytest
import respx

from chasseur.analyzers.performance import API_PAGESPEED, AnalyseurPerformance, FileDAttente
from chasseur.modeles import Prospect

CLE = "CLE-SECRETE-123"


def psi(score: float | None, lcp_ms=5200.0):
    return httpx.Response(
        200,
        json={
            "lighthouseResult": {
                "categories": {"performance": {"score": score}},
                "audits": {
                    "largest-contentful-paint": {"numericValue": lcp_ms},
                    "cumulative-layout-shift": {"numericValue": 0.18},
                    "total-blocking-time": {"numericValue": 640.4},
                },
            }
        },
    )


@pytest.fixture
def perf(config):
    def fabrique(**reglages):
        reglages.setdefault("requetes_par_minute", 60_000)
        config.performance = replace(config.performance, cle_api=CLE, **reglages)
        return AnalyseurPerformance(config)

    return fabrique


async def test_sans_cle_non_verifie_sans_appel(config, client):
    with respx.mock:  # toute requête ferait échouer le test
        rapport = await AnalyseurPerformance(config).analyser(Prospect(url="https://salon.test"), client)
    assert [c.code for c in rapport] == ["NON_VERIFIE"]
    assert rapport[0].points == 0
    assert "pas de clé" in rapport.non_verifies["performance"]
    assert rapport.echec is False  # choix de configuration, pas une panne


@respx.mock
async def test_site_lent(perf, client):
    route = respx.get(API_PAGESPEED).mock(return_value=psi(0.23))
    rapport = await perf().analyser(Prospect(url="salon.test"), client)
    (constat,) = rapport
    assert (constat.code, constat.points) == ("PERF_LENTE", 10)
    assert "5.2 s" in constat.message_client and "23/100" in constat.preuve
    assert rapport.mesures == {"perf_score": "23", "perf_lcp_s": "5.2", "perf_cls": "0.18", "perf_tbt_ms": "640"}
    params = route.calls[0].request.url.params
    assert (params["url"], params["strategy"], params["category"]) == ("https://salon.test", "mobile", "performance")


@respx.mock
async def test_site_rapide(perf, client):
    respx.get(API_PAGESPEED).mock(return_value=psi(0.40))  # 40 n'est pas < 40
    assert list(await perf().analyser(Prospect(url="https://salon.test"), client)) == []


@respx.mock
async def test_relance_apres_429(perf, client):
    route = respx.get(API_PAGESPEED).mock(
        side_effect=[httpx.Response(429, headers={"Retry-After": "0"}), httpx.Response(503), psi(0.9)]
    )
    rapport = await perf().analyser(Prospect(url="https://salon.test"), client)
    assert list(rapport) == [] and rapport.mesures["perf_score"] == "90"
    assert route.call_count == 3


@respx.mock
async def test_abandon_apres_trop_de_429_sans_divulguer_la_cle(perf, client):
    route = respx.get(API_PAGESPEED).respond(429, json={"error": {"message": f"Quota exceeded for key {CLE}"}})
    rapport = await perf(max_relances=2).analyser(Prospect(url="https://salon.test"), client)
    assert route.call_count == 3
    assert [c.code for c in rapport] == ["NON_VERIFIE"] and rapport.echec
    texte = rapport[0].preuve + rapport.non_verifies["performance"]
    assert CLE not in texte and "***" in texte


@respx.mock
async def test_erreur_lighthouse_non_verifiee_sans_relance(perf, client):
    route = respx.get(API_PAGESPEED).respond(
        400, json={"error": {"message": "Lighthouse returned error: FAILED_DOCUMENT_REQUEST"}}
    )
    rapport = await perf().analyser(Prospect(url="https://salon.test"), client)
    assert route.call_count == 1
    assert "FAILED_DOCUMENT_REQUEST" in rapport.non_verifies["performance"]


@respx.mock
async def test_reponse_sans_score(perf, client):
    respx.get(API_PAGESPEED).mock(return_value=psi(None))
    assert "pas pu mesurer" in (await perf().analyser(Prospect(url="https://salon.test"), client)).non_verifies["performance"]


@respx.mock
async def test_api_injoignable(perf, client):
    respx.get(API_PAGESPEED).mock(side_effect=httpx.ConnectError("réseau coupé"))
    rapport = await perf(max_relances=1).analyser(Prospect(url="https://salon.test"), client)
    assert "ConnectError" in rapport.non_verifies["performance"]


async def test_file_espace_les_departs():
    file = FileDAttente(simultanees=10, par_minute=600)  # un départ toutes les 0,1 s
    departs = []

    async def appel():
        async with file.place():
            departs.append(asyncio.get_running_loop().time())

    await asyncio.gather(*(appel() for _ in range(4)))
    ecarts = [b - a for a, b in zip(departs, departs[1:])]
    assert all(e >= 0.09 for e in ecarts)


async def test_file_limite_les_appels_simultanes():
    file = FileDAttente(simultanees=2, par_minute=0)
    en_cours = maxi = 0

    async def appel():
        nonlocal en_cours, maxi
        async with file.place():
            en_cours += 1
            maxi = max(maxi, en_cours)
            await asyncio.sleep(0.02)
            en_cours -= 1

    await asyncio.gather(*(appel() for _ in range(6)))
    assert maxi == 2


async def test_pause_de_la_file():
    file = FileDAttente(simultanees=1, par_minute=0)
    boucle = asyncio.get_running_loop()
    file.pause(0.15)
    debut = boucle.time()
    async with file.place():
        pass
    assert boucle.time() - debut >= 0.14


async def test_performance_hors_places_sites(config, client):
    """Les appels PageSpeed n'occupent pas les places « sites en parallèle »."""
    assert AnalyseurPerformance(config).file_dediee is True
