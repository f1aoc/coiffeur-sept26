from __future__ import annotations

import asyncio

from chasseur.analyzers import Analyseur
from chasseur.modeles import Prospect
from chasseur.orchestrateur import analyser_prospects


class AnalyseurLent(Analyseur):
    """Mesure combien d'analyses tournent en même temps."""

    nom = "lent"
    requiert_url = False

    def __init__(self, config):
        super().__init__(config)
        self.en_cours = 0
        self.max_simultanes = 0

    async def analyser(self, prospect, client):
        self.en_cours += 1
        self.max_simultanes = max(self.max_simultanes, self.en_cours)
        await asyncio.sleep(0.01)
        self.en_cours -= 1
        if prospect.nom == "boum":
            raise RuntimeError("analyseur cassé")
        return [self.config.constat("SSL_ABSENT", "m", "p")]


async def test_dix_en_parallele_maximum(config, client):
    lent = AnalyseurLent(config)
    prospects = [Prospect(nom=f"p{i}") for i in range(35)]
    resultats = await analyser_prospects(prospects, config, analyseurs=[lent], client=client)
    assert lent.max_simultanes == 10
    assert [r.prospect.nom for r in resultats] == [p.nom for p in prospects]  # ordre d'entrée conservé


async def test_une_erreur_n_arrete_pas_le_scan(config, client):
    progres = []
    resultats = await analyser_prospects(
        [Prospect(nom="boum"), Prospect(nom="ok")],
        config,
        analyseurs=[AnalyseurLent(config)],
        client=client,
        progression=lambda fait, total, r: progres.append((fait, total)),
    )
    boum, ok = resultats
    assert [c.code for c in boum.constats] == ["NON_VERIFIE"]
    assert boum.echecs == ["lent"]
    assert "analyseur cassé" in boum.constats[0].preuve
    assert [c.code for c in ok.constats] == ["SSL_ABSENT"]
    assert ok.score == config.points["https"]
    assert sorted(progres) == [(1, 2), (2, 2)]


class AnalyseurDormeur(Analyseur):
    requiert_url = False

    def __init__(self, config, nom, duree=0.1, file_dediee=False):
        super().__init__(config)
        self.nom, self.duree, self.file_dediee = nom, duree, file_dediee

    async def analyser(self, prospect, client):
        await asyncio.sleep(self.duree)
        return []


async def test_les_analyseurs_d_un_site_tournent_en_parallele(config, client):
    analyseurs = [AnalyseurDormeur(config, n) for n in ("reseau", "domaine", "navigateur", "performance")]
    debut = asyncio.get_running_loop().time()
    await analyser_prospects([Prospect(nom="x")], config, analyseurs=analyseurs, client=client)
    assert asyncio.get_running_loop().time() - debut < 0.3  # 4 × 0,1 s en série = 0,4 s


async def test_file_dediee_ne_bloque_pas_les_places_sites(config, client):
    config.parallelisme = 1
    rapide = AnalyseurDormeur(config, "reseau", duree=0.01)
    lent = AnalyseurDormeur(config, "performance", duree=0.3, file_dediee=True)
    debut = asyncio.get_running_loop().time()
    await analyser_prospects([Prospect(nom=f"p{i}") for i in range(5)], config, analyseurs=[rapide, lent], client=client)
    # si l'attente PageSpeed occupait la place unique, il faudrait 5 × 0,3 s
    assert asyncio.get_running_loop().time() - debut < 0.8


async def test_controles_sans_objet_sans_url(config, client):
    from chasseur.analyzers import AnalyseurNavigateur

    (r,) = await analyser_prospects([Prospect(nom="sans site")], config, analyseurs=[AnalyseurNavigateur(config)], client=client)
    assert r.constats == [] and "responsive" in r.sans_objet


class AnalyseurFixe(Analyseur):
    requiert_url = False

    def __init__(self, config, nom, rapport):
        super().__init__(config)
        self.nom, self.rapport = nom, rapport

    async def analyser(self, prospect, client):
        return self.rapport


async def test_403_au_robot_mais_page_affichee_dans_le_navigateur(config, client):
    from chasseur.modeles import Rapport

    reseau = AnalyseurFixe(config, "reseau", Rapport([config.constat("HTTP_ERREUR_CLIENT", "m", "p")], mesures={"code_http": "403"}))
    nav = AnalyseurFixe(config, "navigateur", Rapport(mesures={"navigateur_code_http": "200"}))
    (r,) = await analyser_prospects([Prospect(nom="x")], config, analyseurs=[reseau, nav], client=client)
    assert r.constats == [] and r.etat == "Correct"
    assert "403" in r.mesures["note_http"]


async def test_vraie_404_conservee(config, client):
    from chasseur.modeles import Rapport

    reseau = AnalyseurFixe(config, "reseau", Rapport([config.constat("HTTP_ERREUR_CLIENT", "m", "p")], mesures={"code_http": "404"}))
    nav = AnalyseurFixe(config, "navigateur", Rapport(mesures={"navigateur_code_http": "404"}))
    (r,) = await analyser_prospects([Prospect(nom="x")], config, analyseurs=[reseau, nav], client=client)
    assert [c.code for c in r.constats] == ["HTTP_ERREUR_CLIENT"] and r.etat == "Cassé"


async def test_cle_api_masquee_dans_les_erreurs(config, client):
    from dataclasses import replace

    config.performance = replace(config.performance, cle_api="SECRET42")

    class Fuyard(Analyseur):
        nom = "performance"
        requiert_url = False

        async def analyser(self, prospect, client):
            raise RuntimeError("échec sur https://api/?key=SECRET42")

    (r,) = await analyser_prospects([Prospect(nom="x")], config, analyseurs=[Fuyard(config)], client=client)
    assert "SECRET42" not in r.constats[0].preuve and "***" in r.constats[0].preuve
