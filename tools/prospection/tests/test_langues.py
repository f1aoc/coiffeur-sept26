"""BridgeToLeads en français et en anglais : traductions complètes, langue de l'ordinateur, Google Places,
fichier Excel et licence dans la langue choisie."""

from __future__ import annotations

import os
import re
import sys

import pytest

DOSSIER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, DOSSIER)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import find_no_website as fnw  # noqa: E402
import langue as lg  # noqa: E402
import licence as lic  # noqa: E402
from textes_a_traduire import textes  # noqa: E402
from traductions_en import TRADUCTIONS  # noqa: E402

VARIABLES = re.compile(r"\{(\w*)\}")


@pytest.fixture
def anglais(monkeypatch):
    monkeypatch.setenv(lg.VARIABLE, "en")


@pytest.fixture
def francais(monkeypatch):
    monkeypatch.setenv(lg.VARIABLE, "fr")


def test_tous_les_textes_sont_traduits():
    manquants = sorted(textes() - TRADUCTIONS.keys())
    assert not manquants, manquants


def test_aucune_traduction_orpheline():
    assert not sorted(TRADUCTIONS.keys() - textes())


@pytest.mark.parametrize("francais_", sorted(TRADUCTIONS))
def test_memes_variables_et_pas_de_guillemets_droits(francais_):
    anglais_ = TRADUCTIONS[francais_]
    assert sorted(VARIABLES.findall(francais_)) == sorted(VARIABLES.findall(anglais_))
    assert '"' not in anglais_ and "«" not in anglais_ and anglais_.strip()


def test_langue_du_systeme(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.delenv(lg.VARIABLE, raising=False)
    for v in ("LC_ALL", "LC_MESSAGES", "LANGUAGE"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("LANG", "fr_FR.UTF-8")
    assert lg.langue_systeme() == "fr"
    monkeypatch.setenv("LANG", "en_US.UTF-8")
    assert lg.langue_systeme() == "en"
    lg.definir_langue(None)
    assert lg.langue_courante() == "en"
    lg.definir_langue("fr")  # choix enregistré dans l'application
    assert lg.langue_courante() == "fr"
    monkeypatch.setenv(lg.VARIABLE, "en")  # la variable passe avant
    assert lg.langue_courante() == "en"
    lg.definir_langue(None)


def test_pluriel(anglais):
    assert lg.pluriel(1, "{n} prospect exporté vers {fichier}", "{n} prospects exportés vers {fichier}",
                      fichier="a.xlsx") == "1 lead exported to a.xlsx"
    assert lg.pluriel(0, "{n} prospect exporté vers {fichier}", "{n} prospects exportés vers {fichier}",
                      fichier="a.xlsx") == "0 leads exported to a.xlsx"


def test_pluriel_francais(francais):
    assert lg.pluriel(0, "{recherche} : {n} prospect", "{recherche} : {n} prospects", recherche="x") == "x : 0 prospect"
    assert lg.pluriel(3, "{recherche} : {n} prospect", "{recherche} : {n} prospects", recherche="x") == "x : 3 prospects"


class _Reponse:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return b'{"places": []}'


def _corps_envoyes(monkeypatch):
    corps = []

    def urlopen(req, timeout=None, context=None):
        import json
        corps.append(json.loads(req.data))
        return _Reponse()
    monkeypatch.setattr(fnw.urllib.request, "urlopen", urlopen)
    return corps


def test_google_places_en_francais(francais, monkeypatch):
    corps = _corps_envoyes(monkeypatch)
    fnw.find_leads("AIzaTest", ["coiffeur Cavaillon"])
    assert corps[0]["languageCode"] == "fr" and corps[0]["regionCode"] == "FR"


def test_google_places_en_anglais(anglais, monkeypatch):
    corps = _corps_envoyes(monkeypatch)
    fnw.find_leads("AIzaTest", ["hair salon Austin TX"])
    assert corps[0]["languageCode"] == "en" and "regionCode" not in corps[0]


def test_annuaires_anglophones():
    assert fnw.classify_website("https://www.yelp.com/biz/joes-barber") == "social_or_directory:yelp.com"


def test_erreur_google_en_anglais(anglais):
    texte = fnw.explain_http_error(403, '{"error": {"message": "x", "status": "PERMISSION_DENIED", '
                                        '"details": [{"reason": "BILLING_DISABLED"}]}}')
    assert texte.startswith("Billing is not enabled") and "Google details (403 PERMISSION_DENIED" in texte


def test_excel_en_anglais(anglais, tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    chemin = tmp_path / "leads.xlsx"
    fnw.write_xlsx([{"name": "Joe's", "status": "social_or_directory:yelp.com", "website": "https://yelp.com/x",
                     "phone": "", "address": "Austin", "category": "", "rating": 4.5, "reviews": 12,
                     "maps_url": "https://maps.google.com/?cid=1", "query": "barber shop Austin"}], chemin)
    feuille = openpyxl.load_workbook(chemin).active
    assert feuille.title == "Leads"
    assert [c.value for c in feuille[1]][:3] == ["Name", "Website", "Current page"]
    assert feuille["B2"].value == "yelp.com only" and feuille["I2"].value == "Open"


def test_excel_en_francais(francais, tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    chemin = tmp_path / "prospects.xlsx"
    fnw.write_xlsx([{"name": "Salon", "status": "none", "maps_url": ""}], chemin)
    feuille = openpyxl.load_workbook(chemin).active
    assert feuille["A1"].value == "Nom" and feuille["B2"].value == "Aucun"


def test_licence_en_anglais(anglais, tmp_path):
    etat = lic.Licence(tmp_path, transport=lambda u, d: (200, {}), serveur="https://licences.test").etat()
    assert etat.message.startswith("Enter the license key")
    assert lic.lien_achat() == "https://www.vorelik.com/en/bridgetoleads/"


def test_licence_en_francais(francais):
    assert lic.lien_achat() == lic.LIEN_ACHAT
