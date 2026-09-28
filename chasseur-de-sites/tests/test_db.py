"""Base SQLite : modèles, enregistrement des résultats, recherche, statuts, notes, réglages."""

from __future__ import annotations

import sqlite3

import pytest
from PIL import Image
from sqlmodel import select

from chasseur.db import depot, reglages
from chasseur.db.secret import ErreurSecret, chiffrer, dechiffrer, masquer
from chasseur.db.tables import STATUTS_COMMERCIAUX, Capture, ConstatDB, HistoriqueStatut, Note, ProspectDB, Scan
from chasseur.modeles import Prospect, Resultat
from chasseur.scoring import noter


def nouveau_scan(stockage, n=3, **champs):
    prospects = [Prospect(nom=f"Salon {i:02d}", url=f"https://s{i}.test", ville="Lyon" if i % 2 else "Brest", ligne=i + 2, **champs) for i in range(n)]
    with stockage.session() as s:
        return depot.creer_scan(s, "Test", prospects, fichier="p.csv", format_="CSV")


def resultat(config, codes=(), **mesures):
    r = Resultat(Prospect(), [config.constat(c, f"message {c}", f"preuve {c}") for c in codes], mesures=dict(mesures))
    return noter(r, config)


def test_tables_creees(stockage):
    connexion = sqlite3.connect(stockage.dossier / "chasseur.db")
    tables = {t for (t,) in connexion.execute("select name from sqlite_master where type='table'")}
    assert {"scans", "prospects", "constats", "captures", "notes", "historique_statuts", "reglages"} <= tables


def test_creer_scan(stockage):
    scan = nouveau_scan(stockage, note_google=4.5, nb_avis=30)
    with stockage.session() as s:
        prospects = depot.a_analyser(s, scan.id)
        assert scan.total == 3 and len(prospects) == 3
        p = prospects[0]
        assert (p.statut, p.analyse, p.note_google, p.nb_avis) == ("À contacter", False, 4.5, 30)
        assert p.source == "Import « p.csv »" and p.collecte_le is not None
        assert depot.vers_prospect(p).ligne == p.id  # l'identifiant sert à nommer les captures


def test_enregistrer_resultat_avec_captures(stockage, config):
    scan = nouveau_scan(stockage, 1)
    dossier = stockage.dossier_captures / f"scan-{scan.id}"
    dossier.mkdir(parents=True)
    Image.new("RGB", (1366, 768), "white").save(dossier / "b.webp", "WEBP")
    Image.new("RGB", (375, 667), "white").save(dossier / "m.webp", "WEBP")
    r = resultat(
        config, ["HTTP_ERREUR_SERVEUR", "VIEWPORT_ABSENT"], code_http="500",
        capture_bureau=str(dossier / "b.webp"), capture_mobile=str(dossier / "m.webp"), capture_date="2026-09-28 10:00:00",
    )
    with stockage.session() as s:
        (p,) = depot.a_analyser(s, scan.id)
        depot.enregistrer_resultat(stockage, s, p.id, r)
        p = s.get(ProspectDB, p.id)
        assert (p.analyse, p.score, p.etat) == (True, 50, "Cassé")
        assert p.mesures == {"code_http": "500", "capture_date": "2026-09-28 10:00:00"}
        constats = depot.constats_de(s, p.id)
        assert {(c.code, c.controle, c.points) for c in constats} == {("HTTP_ERREUR_SERVEUR", "http_5xx", 35), ("VIEWPORT_ABSENT", "responsive", 15)}
        captures = depot.captures_de(s, p.id)
        assert captures["bureau"].chemin == f"captures/scan-{scan.id}/b.webp"
        from chasseur.db.tables import heure_locale

        assert heure_locale(captures["bureau"].prise_le).hour == 10
        with Image.open(stockage.absolu(captures["bureau"].miniature)) as mini:
            assert mini.width == 320
        # Réanalyse : les anciens constats et captures sont remplacés
        depot.enregistrer_resultat(stockage, s, p.id, resultat(config))
        assert depot.constats_de(s, p.id) == [] and depot.captures_de(s, p.id) == {}
        assert s.get(ProspectDB, p.id).etat == "Correct"


def test_enregistrer_resultat_prospect_inconnu(stockage, config):
    with stockage.session() as s, pytest.raises(depot.ErreurDepot):
        depot.enregistrer_resultat(stockage, s, 999, resultat(config))


def test_compteurs(stockage, config):
    scan = nouveau_scan(stockage, 3)
    with stockage.session() as s:
        a, b, _ = depot.a_analyser(s, scan.id)
        depot.enregistrer_resultat(stockage, s, a.id, resultat(config, ["DNS_INTROUVABLE"]))
        depot.enregistrer_resultat(stockage, s, b.id, resultat(config))
        assert depot.compteurs(s, scan.id) == {"faits": 2, "Cassé": 1, "Correct": 1}
        assert [x.id for x in depot.scans(s)] == [scan.id]


@pytest.fixture
def base_remplie(stockage, config):
    """60 prospects : 20 cassés (DNS), 20 obsolètes (https + viewport), 20 corrects."""
    scan = nouveau_scan(stockage, 60, categorie="Coiffeur")
    with stockage.session() as s:
        for i, p in enumerate(sorted(depot.a_analyser(s, scan.id), key=lambda x: x.id)):
            codes = [["DNS_INTROUVABLE"], ["SSL_ABSENT", "VIEWPORT_ABSENT"], []][i % 3]
            depot.enregistrer_resultat(stockage, s, p.id, resultat(config, codes))
            p.note_google = None if i % 5 == 0 else 3 + (i % 20) / 10
            s.add(p)
        s.commit()
    return scan


def test_recherche_pagination_et_tri(stockage, base_remplie):
    with stockage.session() as s:
        page1 = depot.rechercher(s, depot.Filtres())
        assert (page1.total, page1.pages, len(page1.lignes)) == (60, 2, 50)
        assert [l.prospect.score for l in page1.lignes[:20]] == [40] * 20
        page2 = depot.rechercher(s, depot.Filtres(page=2))
        assert len(page2.lignes) == 10 and page2.page == 2
        assert depot.rechercher(s, depot.Filtres(page=99)).page == 2  # page hors limites ramenée à la dernière
        par_nom = depot.rechercher(s, depot.Filtres(tri="nom", ordre="asc"))
        assert par_nom.lignes[0].prospect.nom == "Salon 00"
        par_note = depot.rechercher(s, depot.Filtres(tri="note", ordre="asc"))
        notes = [l.prospect.note_google for l in par_note.lignes]
        assert notes[0] == 3.1 and notes[47] is not None and notes[48] is None  # 48 notes, puis les absentes
        assert depot.rechercher(s, depot.Filtres(tri="note", ordre="desc")).lignes[0].prospect.note_google == 4.9


def test_recherche_filtres(stockage, base_remplie):
    with stockage.session() as s:
        def total(**f):
            return depot.rechercher(s, depot.Filtres(**f)).total

        assert total(etat="Cassé") == 20 and total(etat="Obsolète") == 20 and total(etat="Correct") == 20
        assert total(probleme="responsive") == 20 and total(probleme="dns") == 20 and total(probleme="piratage") == 0
        assert total(q="salon 0") == 10 and total(q="SALON 05") == 1 and total(q="brest") == 30
        assert total(scan=base_remplie.id) == 60 and total(scan=999) == 0
        premier = depot.rechercher(s, depot.Filtres(etat="Cassé")).lignes[0].prospect
        depot.changer_statut(s, premier.id, "Contacté")
        assert total(statut="Contacté") == 1 and total(statut="Contacté", etat="Obsolète") == 0


def test_problemes_principaux(stockage, config):
    scan = nouveau_scan(stockage, 1)
    r = resultat(config, ["TITLE_ABSENT", "META_DESCRIPTION_ABSENTE", "SSL_INVALIDE", "VIEWPORT_ABSENT", "FLASH", "NON_VERIFIE"])
    with stockage.session() as s:
        (p,) = depot.a_analyser(s, scan.id)
        depot.enregistrer_resultat(stockage, s, p.id, r)
        (ligne,) = depot.rechercher(s, depot.Filtres()).lignes
    # 3 plus graves, un seul par contrôle, jamais « non vérifié »
    assert [code for code, _, _ in ligne.problemes] == ["SSL_INVALIDE", "VIEWPORT_ABSENT", "FLASH"]
    assert ligne.problemes[0][1] == "Certificat de sécurité invalide"


def test_statuts_et_historique(stockage):
    scan = nouveau_scan(stockage, 1)
    with stockage.session() as s:
        (p,) = depot.a_analyser(s, scan.id)
        depot.changer_statut(s, p.id, "Contacté")
        depot.changer_statut(s, p.id, "Contacté")  # sans changement : pas d'historique
        depot.changer_statut(s, p.id, "Intéressé")
        assert [(h.ancien, h.nouveau) for h in depot.historique(s, p.id)] == [("Contacté", "Intéressé"), ("À contacter", "Contacté")]
        with pytest.raises(depot.ErreurDepot):
            depot.changer_statut(s, p.id, "Vendu")
        with pytest.raises(depot.ErreurDepot):
            depot.changer_statut(s, 999, "Client")
    assert STATUTS_COMMERCIAUX == ("À contacter", "Contacté", "Intéressé", "Pas intéressé", "Client")


def test_notes(stockage):
    scan = nouveau_scan(stockage, 1)
    with stockage.session() as s:
        (p,) = depot.a_analyser(s, scan.id)
        assert depot.note(s, p.id) is None
        depot.enregistrer_note(s, p.id, "Rappeler lundi")
        depot.enregistrer_note(s, p.id, "Rappeler mardi")
        assert depot.note(s, p.id).texte == "Rappeler mardi"
        assert len(list(s.exec(select(Note)))) == 1
        with pytest.raises(depot.ErreurDepot):
            depot.enregistrer_note(s, 999, "x")


def test_recalcul_des_scores(stockage, config, base_remplie):
    config.points["responsive"] = 40  # obsolètes : 15 + 40 = 55
    with stockage.session() as s:
        assert depot.recalculer_scores(s, config) == 60
        obsolete = depot.rechercher(s, depot.Filtres(probleme="responsive")).lignes[0].prospect
        assert obsolete.score == 55 and obsolete.etat == "Obsolète"
        assert {c.points for c in depot.constats_de(s, obsolete.id) if c.code == "VIEWPORT_ABSENT"} == {40}


# --- Secrets et réglages ------------------------------------------------------------


def test_chiffrement(tmp_path):
    jeton = chiffrer(tmp_path, "AIzaSyD-cle-secrete-1234")
    assert "cle-secrete" not in jeton and dechiffrer(tmp_path, jeton) == "AIzaSyD-cle-secrete-1234"
    assert (tmp_path / "cle.secret").stat().st_mode & 0o077 == 0  # lisible par l'utilisateur seul
    (tmp_path / "cle.secret").unlink()
    with pytest.raises(ErreurSecret):
        dechiffrer(tmp_path, jeton)
    assert masquer("AIzaSyD-cle-secrete-1234") == "••••••••1234"


def test_config_effective(stockage):
    from chasseur.config import charger_config
    from conftest import RACINE

    with stockage.session() as s:
        base = charger_config(RACINE / "config.yaml")
        assert reglages.config_effective(stockage, s, charger_config(RACINE / "config.yaml")).performance.cle == ""
        reglages.ecrire_cle_api(stockage, s, reglages.CLE_PAGESPEED, "  cle-psi  ")
        reglages.ecrire(s, reglages.PARALLELISME, "50")
        reglages.ecrire_points(s, {"dns": 55, "inconnu": 3})
        s.commit()
        brut = s.get(reglages.Reglage, reglages.CLE_PAGESPEED) if hasattr(reglages, "Reglage") else None
        config = reglages.config_effective(stockage, s, charger_config(RACINE / "config.yaml"))
    assert config.performance.cle == "cle-psi"
    assert config.parallelisme == 30  # plafonné
    assert config.points["dns"] == 55 and config.points["ssl"] == base.points["ssl"] and "inconnu" not in config.points
    assert brut is None or brut.valeur != "cle-psi"
    stockée = sqlite3.connect(stockage.dossier / "chasseur.db").execute(
        "select valeur, chiffre from reglages where cle='cle_pagespeed'"
    ).fetchone()
    assert stockée[1] == 1 and "cle-psi" not in stockée[0]


def test_tables_liees(stockage, config):
    scan = nouveau_scan(stockage, 1)
    with stockage.session() as s:
        (p,) = depot.a_analyser(s, scan.id)
        depot.enregistrer_resultat(stockage, s, p.id, resultat(config, ["DNS_INTROUVABLE"]))
        depot.changer_statut(s, p.id, "Client")
        assert s.get(Scan, scan.id).total == 1
        assert len(list(s.exec(select(ConstatDB)))) == 1
        assert len(list(s.exec(select(HistoriqueStatut)))) == 1
        assert list(s.exec(select(Capture))) == []
