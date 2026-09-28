from __future__ import annotations

import pytest

from chasseur.config import ErreurConfig, config_depuis_dict
from chasseur.modeles import Prospect, Resultat
from chasseur.scoring import calculer_score, classer, noter, priorite


def constats(config, *codes_):
    return [config.constat(code, "msg", "preuve") for code in codes_]


def test_points_et_gravite_viennent_de_la_config(config_fixe):
    (c,) = constats(config_fixe, "B_HAUTE")
    assert (c.gravite, c.points) == ("haute", 30)


def test_code_inconnu(config_fixe):
    with pytest.raises(ErreurConfig, match="INCONNU"):
        config_fixe.constat("INCONNU", "m", "p")


def test_somme_et_plafond(config_fixe):
    assert calculer_score([], config_fixe) == 0
    assert calculer_score(constats(config_fixe, "B_HAUTE", "C_MOYENNE"), config_fixe) == 40
    assert calculer_score(constats(config_fixe, "A_CRITIQUE", "A_CRITIQUE", "B_HAUTE"), config_fixe) == 100


@pytest.mark.parametrize("score, attendu", [(0, "D"), (1, "C"), (29, "C"), (30, "B"), (59, "B"), (60, "A"), (100, "A")])
def test_priorites_quel_que_soit_l_ordre_dans_le_yaml(config_fixe, score, attendu):
    assert priorite(score, config_fixe) == attendu


def test_classement(config_fixe):
    def r(nom, *codes_):
        return noter(Resultat(Prospect(nom=nom), constats(config_fixe, *codes_)), config_fixe)

    resultats = [
        r("sain"),
        r("zèbre", "B_HAUTE"),
        r("abeille", "B_HAUTE"),
        r("critique", "A_CRITIQUE"),
        r("moyen-trois-fois", "C_MOYENNE", "C_MOYENNE", "C_MOYENNE"),  # 30 pts aussi, mais gravité moindre
    ]
    assert [x.prospect.nom for x in classer(resultats)] == ["critique", "abeille", "zèbre", "moyen-trois-fois", "sain"]


def test_config_du_projet_couvre_tous_les_constats_du_reseau(config):
    attendus = {
        "SITE_ABSENT", "URL_INVALIDE", "DNS_INTROUVABLE", "HTTP_INJOIGNABLE", "HTTP_ERREUR_SERVEUR",
        "HTTP_ERREUR_CLIENT", "SSL_ABSENT", "SSL_EXPIRE", "SSL_INVALIDE", "SSL_EXPIRE_BIENTOT", "ERREUR_ANALYSE",
    }
    assert attendus <= set(config.constats)
    assert (config.timeout, config.essais, config.parallelisme) == (15, 2, 10)


@pytest.mark.parametrize(
    "brut, message",
    [
        ({}, "vide"),
        ({"constats": {"X": {"points": 1}}}, "gravite"),
        ({"constats": {"X": {"gravite": "énorme", "points": 1}}}, "inconnue"),
        ({"constats": {"X": {"gravite": "haute", "points": "beaucoup"}}}, "entier"),
        ({"constats": {"X": {"gravite": "haute", "points": 1}}, "priorites": [{"min": 1}]}, "Priorité"),
    ],
)
def test_config_invalide(brut, message):
    with pytest.raises(ErreurConfig, match=message):
        config_depuis_dict(brut)
