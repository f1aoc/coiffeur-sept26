from __future__ import annotations

import asyncio

from chasseur.analyzers import Analyseur
from chasseur.modeles import Prospect
from chasseur.orchestrateur import analyser_prospects


class AnalyseurLent(Analyseur):
    """Mesure combien d'analyses tournent en même temps."""

    nom = "lent"

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
    assert [c.code for c in boum.constats] == ["ERREUR_ANALYSE"]
    assert "analyseur cassé" in boum.constats[0].preuve
    assert [c.code for c in ok.constats] == ["SSL_ABSENT"]
    assert ok.score == config.constats["SSL_ABSENT"].points
    assert sorted(progres) == [(1, 2), (2, 2)]
