"""Rapport PDF : site cassé, obsolète et correct, avec chaque moteur disponible."""

from __future__ import annotations

import io
import re
import zipfile

import pytest

from chasseur.db.agence import Agence, lire_agence
from chasseur.reports.donnees import diagnostic
from chasseur.reports.pdf import MoteurPDF, couleur_texte, eclaircir, html_rapport, nom_fichier, zip_rapports
from conftest import moteurs_pdf_disponibles, texte_pdf

MOTEURS = moteurs_pdf_disponibles()


def html_de(stockage, prospect_id):
    with stockage.session() as s:
        return html_rapport(stockage, diagnostic(s, prospect_id), lire_agence(s))


# --- Contenu (HTML) ---------------------------------------------------------------------


def test_verdicts(stockage, base_rapports):
    with stockage.session() as s:
        casse = diagnostic(s, base_rapports["casse"])
        obsolete = diagnostic(s, base_rapports["obsolete"])
        correct = diagnostic(s, base_rapports["correct"])
    assert casse.verdict == "Votre site présente 6 problèmes qui font fuir vos visiteurs."
    assert obsolete.verdict == "Votre site présente 4 problèmes qui font fuir vos visiteurs."  # jQuery + WordPress = 1 contrôle
    assert correct.verdict == "Votre site ne présente pas de problème majeur."
    assert [p.code for p in casse.principaux] == [
        "DOMAINE_PARKING", "PAGE_BLANCHE", "SSL_ABSENT", "VIEWPORT_ABSENT", "META_DESCRIPTION_ABSENTE"
    ]  # site cassé d'abord, 5 au plus, jamais « non vérifié »
    assert casse.autres == 1
    assert casse.probleme_principal == "votre adresse web affiche une page « domaine à vendre »"


def test_rapport_site_casse(stockage, base_rapports):
    html = html_de(stockage, base_rapports["casse"])
    assert "Salon Cassé" in html and "Votre site présente 6 problèmes qui font fuir vos visiteurs." in html
    assert html.count('class="probleme casse"') == 2 and html.count('class="probleme obsolete"') == 3
    assert "Ce que voit le visiteur :" in html and "Pourquoi c'est gênant :" in html
    assert "Et 1 autre point de moindre importance" in html
    assert "Atelier Web Provence" in html and "06 12 34 56 78" in html and "bonjour@atelier-web.test" in html
    assert "Contactez-nous pour en parler, sans engagement" in html  # appel à l'action
    assert "captures du 28 septembre 2026 à 10:30" in html
    assert "background: #0a7f5a" in html  # couleur de l'agence
    # Aucune ressource externe : images intégrées, aucune URL chargée
    assert not re.search(r'src="(?!data:)', html) and "data:image/svg+xml;base64," in html
    assert html.count("data:image/webp;base64,") == 2
    # Pas de jargon technique : les codes et les preuves brutes ne sont pas dans le rapport
    assert "DOMAINE_PARKING" not in html and "preuve " not in html and "message " not in html


def test_rapport_site_obsolete(stockage, base_rapports):
    html = html_de(stockage, base_rapports["obsolete"])
    assert "Institut Vieillot" in html and "Ce que nous avons relevé" in html
    assert "ancienne version de WordPress (4.9.8)" in html and "© 2017" in html
    assert 'class="probleme casse"' not in html


def test_rapport_site_correct(stockage, base_rapports):
    html = html_de(stockage, base_rapports["correct"])
    assert "Votre site ne présente pas de problème majeur." in html
    assert "Bonne nouvelle" in html and "Pour garder votre site en bon état" in html
    assert "Ces problèmes se corrigent" not in html and 'class="bref"' not in html


def test_rapport_site_correct_avec_points_a_ameliorer(stockage, base_rapports, config):
    from chasseur.db import depot
    from chasseur.modeles import Prospect, Resultat
    from chasseur.scoring import noter

    with stockage.session() as s:
        r = noter(Resultat(Prospect(), [config.constat("TITLE_ABSENT", "m", "p")]), config)
        depot.enregistrer_resultat(stockage, s, base_rapports["correct"], r)
    html = html_de(stockage, base_rapports["correct"])
    assert "Votre site est en bon état, avec 1 point à améliorer." in html and "Les points à améliorer" in html
    assert "Pour améliorer ces points" in html and "Ces problèmes se corrigent" not in html


def test_rapport_sans_agence_ni_captures(stockage, base_rapports):
    from sqlmodel import delete

    from chasseur.db.tables import Capture, Reglage

    with stockage.session() as s:
        s.exec(delete(Capture))
        s.exec(delete(Reglage))
        s.commit()
    html = html_de(stockage, base_rapports["casse"])
    assert "[votre agence]" in html and "Capture sur ordinateur indisponible" in html


def test_couleurs():
    assert couleur_texte("#ffffff") == "#1c2330" and couleur_texte("#1f5fbf") == "#ffffff"
    assert eclaircir("#000000", 0.5) == "#808080"


def test_nom_de_fichier():
    from chasseur.db.tables import ProspectDB

    assert nom_fichier(ProspectDB(scan_id=1, nom="Coiffure Élégance & Co")) == "diagnostic-coiffure-elegance-co.pdf"
    assert nom_fichier(ProspectDB(scan_id=1)) == "diagnostic-prospect.pdf"


# --- PDF ----------------------------------------------------------------------------


@pytest.fixture(params=MOTEURS or ["aucun"])
async def moteur(request):
    if request.param == "aucun":
        pytest.skip("Aucun moteur PDF : installez weasyprint ou Chromium (playwright install chromium)")
    m = MoteurPDF(request.param)
    yield m
    await m.fermer()


@pytest.mark.parametrize(
    "cle, attendus",
    [
        ("casse", ["Salon Cassé", "6 problèmes", "domaine à vendre", "Ce que voit le visiteur", "Atelier Web Provence"]),
        ("obsolete", ["Institut Vieillot", "4 problèmes", "WordPress"]),
        ("correct", ["Coiffure Impeccable", "pas de problème majeur", "Bonne nouvelle"]),
    ],
)
async def test_pdf_deux_pages(stockage, base_rapports, moteur, cle, attendus):
    contenu = await moteur.pdf(html_de(stockage, base_rapports[cle]))
    assert contenu.startswith(b"%PDF")
    pages, texte = texte_pdf(contenu)
    assert pages == 2
    for attendu in attendus:
        assert attendu in texte.replace("\n", " "), (moteur.nom, attendu)


async def test_zip_des_rapports(stockage, base_rapports, moteur):
    rapports = []
    with stockage.session() as s:
        for cle in ("casse", "correct"):
            d = diagnostic(s, base_rapports[cle])
            rapports.append((nom_fichier(d.prospect), await moteur.pdf(html_rapport(stockage, d, lire_agence(s)))))
    rapports.append(rapports[0])  # même nom : dédoublonné
    with zipfile.ZipFile(io.BytesIO(zip_rapports(rapports))) as z:
        assert z.namelist() == ["diagnostic-salon-casse.pdf", "diagnostic-coiffure-impeccable.pdf", "diagnostic-salon-casse-2.pdf"]
        assert all(z.read(n).startswith(b"%PDF") for n in z.namelist())


def test_moteur_inconnu():
    from chasseur.reports.pdf import ErreurPDF

    with pytest.raises(ErreurPDF):
        MoteurPDF("word")


def test_agence_par_defaut():
    assert Agence().nom_affiche == "[votre agence]" and Agence().coordonnees == []
