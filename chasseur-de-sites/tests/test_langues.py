"""Version anglaise : chaque texte affiché a sa traduction, avec les mêmes variables ; écrans et rapport en anglais."""

from __future__ import annotations

import string

import pytest

from chasseur import langue
from chasseur.langue import _, langue_courante, traductions
from chasseur.reports.textes import texte
from chasseur.sources import places
from textes_a_traduire import textes_a_traduire


def _variables(t: str) -> set[str]:
    return {nom for _, nom, _, _ in string.Formatter().parse(t) if nom}


def test_tous_les_textes_sont_traduits():
    en = traductions("en")
    manquants = sorted(textes_a_traduire() - set(en))
    assert not manquants, manquants


def test_memes_variables_et_pas_de_guillemets_droits():
    for fr, en in traductions("en").items():
        assert _variables(fr) == _variables(en), fr
        assert '"' not in en, fr  # textes insérés tels quels dans des attributs HTML


@pytest.fixture
def anglais(monkeypatch):
    monkeypatch.setenv("CHASSEUR_LANGUE", "en")
    yield
    langue.definir_langue("auto")


def test_textes_en_anglais(anglais):
    assert langue_courante() == "en"
    assert _("Nouvelle analyse") == "New analysis"
    t = texte("DOMAINE_EXPIRE", {"domaine_expire_le": "2026-08-12"})
    assert t.titre == "Your domain name has expired" and "since August 12, 2026" in t.visiteur
    assert places.langue_recherche() == {"languageCode": "en"}


def test_recherche_google_en_francais():
    assert places.langue_recherche() == {"languageCode": "fr", "regionCode": "FR"}


@pytest.mark.parametrize("code, attendu", [("fr_FR.UTF-8", "fr"), ("en_GB.UTF-8", "en"), ("es_ES.UTF-8", "en"), ("C.UTF-8", "fr")])
def test_langue_du_systeme(monkeypatch, code, attendu):
    for variable in ("LC_ALL", "LC_MESSAGES", "LANGUAGE"):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv("LANG", code)
    monkeypatch.setattr(langue.locale, "getlocale", lambda: (None, None))
    monkeypatch.setattr(langue.sys, "platform", "linux")  # sous Windows, la langue de Windows passerait avant LANG
    assert langue.langue_systeme() == attendu


def test_ecrans_en_anglais(web, monkeypatch):
    monkeypatch.delenv("CHASSEUR_LANGUE")
    try:
        web.post("/reglages", data={"langue": "en"})
        for chemin, attendu in (("/analyses", "No analysis yet"), ("/analyses/nouvelle", "Drag and drop your file here"),
                                ("/resultats", "No prospect matches these filters"), ("/reglages", "Scoring weights"),
                                ("/recherche", "“Trade + city” search"), ("/licence", "How it works"),
                                ("/oppositions", "Opt-out list"), ("/a-propos", "Site Hunter")):
            page = web.get(chemin)
            assert page.status_code == 200 and attendu in page.text and 'lang="en"' in page.text, chemin
        web.post("/reglages", data={"langue": "fr"})
        assert "Aucune analyse pour l'instant" in web.get("/analyses").text
    finally:
        langue.definir_langue("auto")


def test_rapport_en_anglais(stockage, base_rapports, anglais):
    from chasseur.db.agence import lire_agence
    from chasseur.reports.donnees import diagnostic
    from chasseur.reports.pdf import html_rapport

    with stockage.session() as s:
        d = diagnostic(s, base_rapports["casse"])
        html = html_rapport(stockage, d, lire_agence(s))
    assert '<html lang="en">' in html and "Your website check-up" in html
    assert "Your website has 6 problems that drive your visitors away." in html
    assert "What the visitor sees:" in html and "Why it matters:" in html
    assert "screenshots of September 28, 2026 at 10:30" in html
    assert "Contact us to talk about it, with no commitment" in html
    assert "Votre site" not in html
