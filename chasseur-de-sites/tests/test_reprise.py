"""Reprise après interruption : les sites déjà analysés sont ignorés."""

from __future__ import annotations

import csv
import json

import respx

from chasseur import cli
from chasseur.analyzers import reseau
from chasseur.modeles import Prospect, Resultat
from chasseur.reprise import Journal, chemin_journal, cle, resultat_en_dict
from chasseur.scoring import noter
from conftest import RACINE


def test_journal_aller_retour(tmp_path, config):
    journal = Journal(tmp_path / "j.jsonl")
    r = noter(Resultat(Prospect(nom="A", url="https://a.test"), [config.constat("SSL_ABSENT", "m", "p")], mesures={"ip": "1"}), config)
    journal.ecrire(r)
    journal.fermer()
    with (tmp_path / "j.jsonl").open("a", encoding="utf-8") as f:
        f.write('{"prospect": {"nom": "tronqu')  # interruption en pleine écriture
    (relu,) = Journal(tmp_path / "j.jsonl").charger(config).values()
    assert relu.prospect.nom == "A" and relu.score == 15 and relu.etat == "Correct" and relu.mesures == {"ip": "1"}


def test_scores_recalcules_avec_la_config_actuelle(tmp_path, config):
    journal = Journal(tmp_path / "j.jsonl")
    journal.ecrire(noter(Resultat(Prospect(nom="A"), [config.constat("SSL_ABSENT", "m", "p")]), config))
    journal.fermer()
    config.points["https"] = 50
    (relu,) = journal.charger(config).values()
    assert relu.score == 50 and relu.constats[0].points == 50 and relu.etat == "Obsolète"


def test_cle_insensible_casse_et_barre_finale():
    assert cle(Prospect(nom="Salon ", url="HTTPS://Salon.test/")) == cle(Prospect(nom="salon", url="https://salon.test"))


def test_scan_repris_ignore_les_sites_deja_faits(tmp_path, monkeypatch, config, dns, ssl_simule, sans_proxy):
    monkeypatch.setattr(reseau, "resoudre_dns", dns)
    monkeypatch.setattr(reseau, "verifier_certificat", ssl_simule)
    entree = tmp_path / "prospects.csv"
    entree.write_text("nom;url\nDéjà fait;https://fait.test\nNouveau;https://nouveau.test\n", encoding="utf-8")
    sortie = tmp_path / "resultats.csv"

    # Journal laissé par un scan interrompu : « Déjà fait » est terminé.
    deja = noter(Resultat(Prospect(nom="Déjà fait", url="https://fait.test", ligne=2), [config.constat("SSL_ABSENT", "m", "p")]), config)
    chemin_journal(sortie).write_text(json.dumps(resultat_en_dict(deja), ensure_ascii=False) + "\n", encoding="utf-8")

    with respx.mock(assert_all_called=False) as mock:
        fait = mock.get("https://fait.test/").respond(200)
        nouveau = mock.get("https://nouveau.test/").respond(200)
        code = cli.main(["scan", str(entree), "-o", str(sortie), "-q", "-a", "reseau", "-c", str(RACINE / "config.yaml")])

    assert code == 0
    assert not fait.called and nouveau.called
    lignes = {l["nom"]: l for l in csv.DictReader(sortie.read_text(encoding="utf-8-sig").splitlines(), delimiter=";")}
    assert lignes["Déjà fait"]["codes"] == "SSL_ABSENT"  # repris du journal
    assert lignes["Nouveau"]["codes"] == ""
    assert not chemin_journal(sortie).exists()  # scan terminé : journal supprimé


def test_recommencer_ignore_le_journal(tmp_path, monkeypatch, config, dns, ssl_simule, sans_proxy):
    monkeypatch.setattr(reseau, "resoudre_dns", dns)
    monkeypatch.setattr(reseau, "verifier_certificat", ssl_simule)
    entree = tmp_path / "p.csv"
    entree.write_text("nom;url\nA;https://fait.test\n", encoding="utf-8")
    sortie = tmp_path / "r.csv"
    deja = noter(Resultat(Prospect(nom="A", url="https://fait.test")), config)
    chemin_journal(sortie).write_text(json.dumps(resultat_en_dict(deja)) + "\n", encoding="utf-8")
    with respx.mock as mock:
        route = mock.get("https://fait.test/").respond(200)
        cli.main(["scan", str(entree), "-o", str(sortie), "-q", "-a", "reseau", "--recommencer", "-c", str(RACINE / "config.yaml")])
    assert route.called


def test_interruption_garde_le_journal(tmp_path, monkeypatch, capsys):
    async def interrompre(*a, **k):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "analyser_prospects", interrompre)
    entree = tmp_path / "p.csv"
    entree.write_text("nom;url\nA;https://a.test\n", encoding="utf-8")
    assert cli.main(["scan", str(entree), "-q", "-a", "reseau", "-c", str(RACINE / "config.yaml")]) == 130
    assert "Relancez la même commande" in capsys.readouterr().err
