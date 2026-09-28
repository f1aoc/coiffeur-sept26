"""Scoring (§3.2 à §3.4) : couverture complète de chasseur/scoring/score.py."""

from __future__ import annotations

import pytest

from chasseur.config import ErreurConfig, config_depuis_dict
from chasseur.controles import CONTROLES, PAR_ID
from chasseur.modeles import Constat, Prospect, Resultat
from chasseur.scoring import calculer_score, classer, controles_declenches, etat, noter, statut_controles
from conftest import RACINE


def constats(config, *codes):
    return [config.constat(code, "msg", "preuve") for code in codes]


def resultat(config, nom="x", *codes, **champs):
    return noter(Resultat(Prospect(nom=nom), constats(config, *codes), **champs), config)


def test_points_et_gravite(config_fixe):
    (c,) = constats(config_fixe, "SSL_INVALIDE")
    assert (c.gravite, c.points) == ("haute", 30)
    (c,) = constats(config_fixe, "NON_VERIFIE")
    assert (c.gravite, c.points) == ("info", 0)


def test_code_inconnu(config_fixe):
    with pytest.raises(ErreurConfig, match="INCONNU"):
        config_fixe.constat("INCONNU", "m", "p")


def test_un_controle_compte_une_seule_fois(config_fixe):
    # « title OU meta description » : 5 points, pas 10
    assert calculer_score(constats(config_fixe, "TITLE_ABSENT", "META_DESCRIPTION_ABSENTE"), config_fixe) == 5
    # plusieurs technologies périmées : 10 points au total
    assert calculer_score(constats(config_fixe, "FLASH", "JQUERY_OBSOLETE", "WORDPRESS_OBSOLETE"), config_fixe) == 10
    assert controles_declenches(constats(config_fixe, "FLASH", "JQUERY_OBSOLETE", "NON_VERIFIE")) == {
        "technologies": ["FLASH", "JQUERY_OBSOLETE"]
    }


def test_somme_et_plafond(config_fixe):
    assert calculer_score([], config_fixe) == 0
    assert calculer_score(constats(config_fixe, "SSL_ABSENT", "VIEWPORT_ABSENT"), config_fixe) == 30
    tout = constats(config_fixe, "DNS_INTROUVABLE", "HTTP_ERREUR_CLIENT", "SSL_INVALIDE", "SSL_ABSENT")
    assert calculer_score(tout, config_fixe) == 100  # 115 plafonné


def test_points_negatifs_ramenes_a_zero(config_fixe):
    config_fixe.points["https"] = -20
    assert calculer_score(constats(config_fixe, "SSL_ABSENT"), config_fixe) == 0


@pytest.mark.parametrize(
    "codes, attendu",
    [
        ((), "Correct"),
        (("TITLE_ABSENT", "CONTACT_ABSENT"), "Correct"),  # 10 < 30
        (("SSL_ABSENT", "VIEWPORT_ABSENT"), "Obsolète"),  # 30 ≥ 30 sans casse
        (("SSL_INVALIDE",), "Cassé"),
        (("DNS_INTROUVABLE", "VIEWPORT_ABSENT"), "Cassé"),
        (("SITE_ABSENT",), "Sans site"),
        (("URL_INVALIDE",), "Sans site"),
        (("NON_VERIFIE",), "Correct"),
    ],
)
def test_etats(config_fixe, codes, attendu):
    cs = constats(config_fixe, *codes)
    assert etat(cs, calculer_score(cs, config_fixe), config_fixe) == attendu


@pytest.mark.parametrize(
    "codes, echecs, attendu",
    [
        ((), ["reseau"], "À revérifier"),
        (("SSL_ABSENT", "VIEWPORT_ABSENT"), ["navigateur"], "À revérifier"),
        (("DNS_INTROUVABLE",), ["navigateur"], "Cassé"),  # la casse prouvée l'emporte
        ((), ["performance"], "Correct"),  # quota PageSpeed épuisé : pas bloquant
    ],
)
def test_analyse_incomplete(config_fixe, codes, echecs, attendu):
    assert resultat(config_fixe, "x", *codes, echecs=echecs).etat == attendu


def test_casse_meme_avec_zero_point(config_fixe):
    """Cassé = au moins un contrôle du tableau 3.2, quels que soient ses points."""
    config_fixe.points["maintenance"] = 0
    assert resultat(config_fixe, "m", "SITE_EN_MAINTENANCE").etat == "Cassé"


def test_toutes_les_familles_de_casse_sont_des_controles_du_tableau_3_2(config):
    casse = {c.id for c in CONTROLES if c.famille == "casse"}
    assert casse == {"dns", "domaine", "http_5xx", "http_4xx", "ssl", "page_blanche_php", "maintenance", "piratage"}
    assert {c.id for c in CONTROLES if c.famille == "obsolete"} == {
        "https", "responsive", "copyright", "technologies", "performance", "title_meta", "contact", "actualites"
    }


def test_points_du_cahier_des_charges(config):
    attendus = {
        "dns": 40, "domaine": 40, "http_5xx": 35, "http_4xx": 30, "ssl": 30, "page_blanche_php": 30,
        "maintenance": 20, "piratage": 25, "https": 15, "responsive": 15, "copyright": 10,
        "technologies": 10, "performance": 10, "title_meta": 5, "contact": 5, "actualites": 5,
        "domaine_expiration": 10,
    }
    assert {k: config.points[k] for k in attendus} == attendus
    assert config.etats.seuil_obsolete == 30 and config.score_max == 100
    assert (config.timeout, config.essais, config.parallelisme, config.navigateur.timeout_page) == (15, 2, 10, 20)


def test_statut_des_controles(config_fixe):
    r = resultat(
        config_fixe, "x", "FLASH", "JQUERY_OBSOLETE", "NON_VERIFIE",
        non_verifies={"performance": "pas de clé"}, sans_objet=["domaine"],
    )
    statuts = statut_controles(r)
    assert list(statuts) == [c.id for c in CONTROLES]
    assert statuts["technologies"] == "KO : FLASH, JQUERY_OBSOLETE"
    assert statuts["performance"] == "non vérifié"
    assert statuts["domaine"] == "n/a"
    assert statuts["dns"] == "OK"


def test_classement(config_fixe):
    resultats = [
        resultat(config_fixe, "sain"),
        resultat(config_fixe, "zèbre", "HTTP_ERREUR_CLIENT"),
        resultat(config_fixe, "abeille", "HTTP_ERREUR_CLIENT"),
        resultat(config_fixe, "dns", "DNS_INTROUVABLE"),
        resultat(config_fixe, "obsolete-30", "SSL_ABSENT", "VIEWPORT_ABSENT"),  # 30 pts, gravité moindre
        resultat(config_fixe, "info", "NON_VERIFIE"),
    ]
    assert [r.prospect.nom for r in classer(resultats)] == ["dns", "abeille", "zèbre", "obsolete-30", "info", "sain"]


def _config_minimale(**autres):
    return {"points": dict.fromkeys(PAR_ID, 1)} | autres


@pytest.mark.parametrize(
    "brut, message",
    [
        ({}, "vide"),
        ({"points": {"dns": 1}}, "manquant"),
        (_config_minimale() | {"points": dict.fromkeys(PAR_ID, 1) | {"inconnu": 3}}, "inconnu"),
        ({"points": dict.fromkeys(PAR_ID, "beaucoup")}, "entier"),
        (_config_minimale(parallelisme=31), "entre 1 et 30"),
        (_config_minimale(parallelisme=0), "entre 1 et 30"),
        (_config_minimale(reseau={"essais": 0}), "essais"),
        (_config_minimale(navigateur={"inexistant": 1}), "clé"),
        (_config_minimale(navigateur={"timeout_page": "vite"}), "float"),
    ],
)
def test_config_invalide(brut, message):
    with pytest.raises(ErreurConfig, match=message):
        config_depuis_dict(brut)


def test_config_booleens_et_cle_api_par_variable(monkeypatch):
    c = config_depuis_dict(_config_minimale(navigateur={"sandbox": "non", "page_contact": True}))
    assert c.navigateur.sandbox is False and c.navigateur.page_contact is True
    monkeypatch.setenv("PAGESPEED_API_KEY", "secret")
    assert c.performance.cle == "secret"


def test_config_du_projet_se_charge():
    from chasseur.config import charger_config

    c = charger_config(RACINE / "config.yaml")
    assert set(c.points) == set(PAR_ID)
    assert isinstance(c.constat("DNS_INTROUVABLE", "m", "p"), Constat)
