"""Scénario complet : chasseur scan prospects.csv, réseau entièrement simulé."""

from __future__ import annotations

import csv

import httpx
import pytest
import respx

from chasseur import cli
from chasseur.analyzers import reseau
from chasseur.controles import CONTROLE_DU_CODE as PAR_CODE
from conftest import FIXTURES, RACINE


@pytest.fixture
def reseau_simule(monkeypatch, dns, ssl_simule):
    for var in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(reseau, "resoudre_dns", dns)
    monkeypatch.setattr(reseau, "verifier_certificat", ssl_simule)
    with respx.mock(assert_all_called=False) as mock:
        mock.get("https://ok.test/").respond(200)
        mock.get("https://erreur500.test/").respond(500)
        mock.get("https://ssl-expire.test/").respond(200)
        mock.get("https://institut-http.test/").mock(side_effect=httpx.ConnectError("refusé"))
        mock.get("http://institut-http.test/").respond(200)
        yield mock


def test_scan_complet(tmp_path, reseau_simule, capsys, config):
    config_rapide = tmp_path / "config.yaml"
    config_rapide.write_text(
        (RACINE / "config.yaml").read_text(encoding="utf-8").replace("pause_entre_essais: 2", "pause_entre_essais: 0"),
        encoding="utf-8",
    )
    sortie = tmp_path / "resultats.csv"

    code = cli.main(
        ["scan", str(FIXTURES / "prospects.csv"), "-o", str(sortie), "-c", str(config_rapide), "-q", "-a", "reseau"]
    )

    assert code == 0
    lignes = list(csv.DictReader(sortie.read_text(encoding="utf-8-sig").splitlines(), delimiter=";"))
    par_nom = {l["nom"]: l for l in lignes}
    assert par_nom["Salon Tout Va Bien"]["codes"] == ""
    assert par_nom["Coiffure Fantôme"]["codes"] == "DNS_INTROUVABLE"
    assert par_nom["Barbier Planté"]["codes"] == "HTTP_ERREUR_SERVEUR"
    assert par_nom["Beauté Expirée"]["codes"] == "SSL_EXPIRE"
    assert par_nom["Onglerie Sans Site"]["codes"] == "SITE_ABSENT"
    assert par_nom["Institut Ancien"]["codes"] == "SSL_ABSENT"

    scores = [int(l["score"]) for l in lignes]
    assert scores == sorted(scores, reverse=True)
    assert lignes[-1]["nom"] == "Salon Tout Va Bien"
    assert par_nom["Coiffure Fantôme"]["etat"] == "Cassé"
    assert par_nom["Institut Ancien"]["etat"] == "Correct"  # 15 pts < 30
    assert par_nom["Onglerie Sans Site"]["etat"] == "Sans site"
    assert par_nom["Coiffure Fantôme"]["ctrl_dns"] == "KO : DNS_INTROUVABLE"
    assert par_nom["Coiffure Fantôme"]["ctrl_ssl"] == "non vérifié"
    assert par_nom["Salon Tout Va Bien"]["ctrl_page_blanche_php"] == "non vérifié"  # analyseur non lancé
    for l in lignes:
        attendu = sum(config.points[i] for i in {PAR_CODE[c].id for c in l["codes"].split(" | ") if c})
        assert int(l["score"]) == min(attendu, config.score_max)

    assert str(sortie) in capsys.readouterr().out


def test_sortie_par_defaut_a_cote_du_fichier(tmp_path, reseau_simule):
    entree = tmp_path / "prospects.csv"
    entree.write_text("nom;url\nA;https://ok.test\n", encoding="utf-8")
    assert cli.main(["scan", str(entree), "-q", "-a", "reseau", "-c", str(RACINE / "config.yaml")]) == 0
    assert (tmp_path / "prospects_resultats.csv").is_file()


def test_fichier_introuvable(tmp_path, capsys):
    assert cli.main(["scan", str(tmp_path / "absent.csv")]) == 2
    assert "introuvable" in capsys.readouterr().err
