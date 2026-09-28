"""Migration des CSV de résultats du Lot 2 vers la base (`chasseur import`)."""

from __future__ import annotations

import csv

import pytest
import respx
from PIL import Image

from chasseur import cli
from chasseur.analyzers import reseau
from chasseur.db import Stockage, depot
from chasseur.db.import_resultats import ErreurMigration, importer_resultats
from chasseur.reports.csv_export import COLONNES
from conftest import FIXTURES, RACINE


@pytest.fixture
def csv_lot2(tmp_path, monkeypatch, dns, ssl_simule, sans_proxy):
    """Vrai CSV produit par « chasseur scan » (réseau simulé, analyseur Réseau seul)."""
    monkeypatch.setattr(reseau, "resoudre_dns", dns)
    monkeypatch.setattr(reseau, "verifier_certificat", ssl_simule)
    config = tmp_path / "config.yaml"
    config.write_text((RACINE / "config.yaml").read_text(encoding="utf-8").replace("pause_entre_essais: 2", "pause_entre_essais: 0"), encoding="utf-8")
    sortie = tmp_path / "resultats.csv"
    with respx.mock(assert_all_called=False) as mock:
        mock.get("https://ok.test/").respond(200)
        mock.get("https://erreur500.test/").respond(500)
        mock.get("https://ssl-expire.test/").respond(200)
        mock.get("https://institut-http.test/").mock(side_effect=__import__("httpx").ConnectError("refusé"))
        mock.get("http://institut-http.test/").respond(200)
        assert cli.main(["scan", str(FIXTURES / "prospects.csv"), "-o", str(sortie), "-c", str(config), "-q", "-a", "reseau"]) == 0
    return sortie


def test_migration_d_un_export_du_lot_2(tmp_path, csv_lot2, config):
    stockage = Stockage(tmp_path / "donnees")
    scan = importer_resultats(stockage, csv_lot2, config)
    assert scan.total == 6 and scan.statut == "termine" and scan.format == "Résultats CSV (Lot 2)"
    with stockage.session() as s:
        page = depot.rechercher(s, depot.Filtres(scan=scan.id))
        par_nom = {l.prospect.nom: l.prospect for l in page.lignes}
        fantome = par_nom["Coiffure Fantôme"]
        assert (fantome.etat, fantome.score, fantome.analyse, fantome.ville) == ("Cassé", 40, True, "Lyon")
        (constat,) = depot.constats_de(s, fantome.id)
        assert constat.code == "DNS_INTROUVABLE" and "domaine-mort.test" in constat.preuve
        assert "nom de domaine" in constat.message_client
        assert fantome.non_verifies["http_5xx"] == "domaine introuvable"
        assert par_nom["Onglerie Sans Site"].etat == "Sans site"
        assert par_nom["Barbier Planté"].mesures["code_http"] == "500"
        assert par_nom["Salon Tout Va Bien"].etat == "Correct"
        assert depot.compteurs(s, scan.id)["faits"] == 6


def test_commande_import(tmp_path, csv_lot2, capsys):
    donnees = tmp_path / "donnees"
    assert cli.main(["import", str(csv_lot2), "--nom", "Septembre", "--donnees", str(donnees), "-c", str(RACINE / "config.yaml")]) == 0
    assert "6 prospect(s) importé(s) dans l'analyse « Septembre »" in capsys.readouterr().out
    with Stockage(donnees).session() as s:
        assert [x.nom for x in depot.scans(s)] == ["Septembre"]


def test_captures_copiees_et_ancien_format(tmp_path, config):
    """Captures relatives au CSV, et preuves « non vérifié » mélangées (export d'avant l'alignement)."""
    (tmp_path / "captures").mkdir()
    Image.new("RGB", (1366, 768), "white").save(tmp_path / "captures" / "0002-salon-bureau.webp", "WEBP")
    ligne = dict.fromkeys(COLONNES, "")
    ligne.update(
        rang="1", score="45", etat="Cassé", nom="Salon", url="https://salon.test", adresse="1 rue X, 13001 Marseille",
        codes="HTTP_ERREUR_SERVEUR | VIEWPORT_ABSENT", messages_client="Erreur serveur. | Pas mobile.",
        preuves="GET → HTTP 500 | performance : pas de clé API | pas de viewport",
        non_verifies="performance (pas de clé API) | responsive (échec de l'analyseur navigateur)",
        capture_bureau="captures/0002-salon-bureau.webp", capture_mobile="captures/absente.webp",
        capture_date="2026-09-01 09:30:00", ctrl_domaine="n/a", code_http="500",
    )
    chemin = tmp_path / "ancien.csv"
    with chemin.open("w", encoding="utf-8-sig", newline="") as f:
        ecrivain = csv.DictWriter(f, fieldnames=COLONNES, delimiter=";")
        ecrivain.writeheader()
        ecrivain.writerow(ligne)

    stockage = Stockage(tmp_path / "donnees")
    scan = importer_resultats(stockage, chemin, config)
    with stockage.session() as s:
        (p,) = depot.a_analyser(s, scan.id) or [l.prospect for l in depot.rechercher(s, depot.Filtres()).lignes]
        constats = {c.code: c for c in depot.constats_de(s, p.id)}
        assert constats["HTTP_ERREUR_SERVEUR"].preuve == "GET → HTTP 500"
        assert constats["VIEWPORT_ABSENT"].preuve == "pas de viewport"
        assert constats["VIEWPORT_ABSENT"].message_client == "Pas mobile."
        assert p.echecs == ["navigateur"] and "domaine" in p.sans_objet and p.ville == "Marseille"
        captures = depot.captures_de(s, p.id)
        assert set(captures) == {"bureau"}  # la capture absente est ignorée
        assert stockage.absolu(captures["bureau"].chemin).is_file()
        assert captures["bureau"].chemin.startswith(f"captures/scan-{scan.id}/")


def test_fichier_qui_n_est_pas_un_export(tmp_path, config):
    (tmp_path / "x.csv").write_text("nom;url\nA;a.test\n", encoding="utf-8")
    with pytest.raises(ErreurMigration, match="n'est pas un export"):
        importer_resultats(Stockage(tmp_path / "d"), tmp_path / "x.csv", config)
    with pytest.raises(ErreurMigration, match="introuvable"):
        importer_resultats(Stockage(tmp_path / "d"), tmp_path / "absent.csv", config)
