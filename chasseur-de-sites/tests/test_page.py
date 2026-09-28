"""Règles de page (analyzers/page.py), sans navigateur : PageInfo construites à la main."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from bs4 import BeautifulSoup

from chasseur.analyzers.page import (
    PageInfo,
    annee_copyright,
    dates_trouvees,
    evaluer_page,
    formulaires_utiles,
    mise_en_page_tableaux,
)
from conftest import MAINTENANT

TEXTE = "Bienvenue dans notre salon. " * 30  # ~840 caractères
BASE = (
    '<html><head><meta name="viewport" content="width=device-width"><title>Salon</title>'
    '<meta name="description" content="Salon"></head><body>{corps}<a href="tel:0100000000">Appeler</a></body></html>'
)


def page(corps="", texte=TEXTE, html=None, **champs) -> PageInfo:
    champs.setdefault("url_demandee", "https://salon.test/")
    champs.setdefault("url_finale", "https://salon.test/")
    champs.setdefault("statut_http", 200)
    return PageInfo(html=html or BASE.format(corps=corps), texte_visible=texte, **champs)


def codes(info, config, signatures):
    return [c.code for c in evaluer_page(info, config, signatures, MAINTENANT)]


def test_page_saine(config, signatures):
    assert codes(page(texte_pied="© 2026 Salon"), config, signatures) == []


def test_page_d_erreur_http_non_jugee(config, signatures):
    rapport = evaluer_page(page(statut_http=404, texte=""), config, signatures, MAINTENANT)
    assert list(rapport) == []
    assert rapport.non_verifies["page_blanche_php"] == "page d'erreur HTTP 404"


@pytest.mark.parametrize(
    "texte, attendu",
    [
        ("Warning: include(header.php): failed to open stream in /var/www/index.php on line 3", "ERREUR_PHP"),
        ("Fatal error: Uncaught Error: Call to undefined function x() in /home/site/f.php on line 12", "ERREUR_PHP"),
        ("Error establishing a database connection", "ERREUR_PHP"),
        ("Il y a eu une erreur critique sur ce site.", "ERREUR_PHP"),
        ("Accueil", "PAGE_BLANCHE"),
    ],
)
def test_page_blanche_ou_erreur_php(config, signatures, texte, attendu):
    assert attendu in codes(page(texte=texte), config, signatures)


def test_erreur_php_sans_double_page_blanche(config, signatures):
    assert codes(page(texte="Parse error: syntax error in /a/b.php on line 2"), config, signatures) == ["ERREUR_PHP"]


def test_maintenance_seulement_sur_page_courte(config, signatures):
    assert "SITE_EN_MAINTENANCE" in codes(page(texte="Site en construction, revenez bientôt. " + "x" * 500), config, signatures)
    long = TEXTE * 3 + " Nous proposons aussi l'entretien et la maintenance de vos chaudières. Site en maintenance"
    assert "SITE_EN_MAINTENANCE" not in codes(page(texte=long), config, signatures)


def test_spam_au_dessus_du_seuil(config, signatures):
    un_mot = page(corps='<div style="display:none">viagra</div>')
    deux_mots = page(corps='<div style="display:none">viagra cialis</div>')
    assert "PIRATAGE_SPAM" not in codes(un_mot, config, signatures)
    assert "PIRATAGE_SPAM" in codes(deux_mots, config, signatures)
    dans_le_titre = page(html=BASE.replace("<title>Salon", "<title>Casino en ligne").format(corps=""))
    assert "PIRATAGE_SPAM" in codes(dans_le_titre, config, signatures)


@pytest.mark.parametrize(
    "finale, suspecte",
    [
        ("https://www.salon.test/accueil", False),  # même site
        ("https://casino-bonus.example/", True),
        ("https://www.facebook.com/salon", False),  # réseau social autorisé
        ("https://sedo.com/search?domain=salon.test", False),  # parking : analyseur Domaine
    ],
)
def test_redirection_vers_domaine_tiers(config, signatures, finale, suspecte):
    assert ("PIRATAGE_REDIRECTION" in codes(page(url_finale=finale), config, signatures)) is suspecte


def test_responsive(config, signatures):
    sans_viewport = page(html=BASE.replace('<meta name="viewport" content="width=device-width">', "").format(corps=""))
    assert "VIEWPORT_ABSENT" in codes(sans_viewport, config, signatures)
    deborde = page(largeur_contenu_mobile=900, largeur_fenetre_mobile=375)
    rapport = evaluer_page(deborde, config, signatures, MAINTENANT)
    assert [c.code for c in rapport] == ["DEFILEMENT_HORIZONTAL"]
    assert rapport.mesures["largeur_mobile"] == "900/375 px"
    assert codes(page(largeur_contenu_mobile=377, largeur_fenetre_mobile=375), config, signatures) == []


@pytest.mark.parametrize(
    "pied, annee",
    [
        ("© 2019 Salon", 2019),
        ("Copyright (c) 2008-2012 Menuiserie", 2012),
        ("&copy; 2015 – 2023 Tous droits réservés", 2023),
        ("2021 © Salon", 2021),
        ("Salon Moderne - Tous droits réservés 2020", 2020),
        ("Ouvert depuis 1998, 12 rue de Paris 75002", None),
    ],
)
def test_annee_copyright(pied, annee):
    assert annee_copyright(pied) == annee


@pytest.mark.parametrize("annee, ancien", [(2023, True), (2024, False), (2026, False)])
def test_copyright_ancien_si_annee_moins_3(config, signatures, annee, ancien):
    assert ("COPYRIGHT_ANCIEN" in codes(page(texte_pied=f"© {annee}"), config, signatures)) is ancien


@pytest.mark.parametrize(
    "corps, version_js, attendu",
    [
        ('<meta name="generator" content="WordPress 5.9.3"><link href="/wp-content/x.css">', "", ["WORDPRESS_OBSOLETE"]),
        ('<meta name="generator" content="WordPress 6.4.2"><link href="/wp-content/x.css">', "", []),
        ('<link href="/wp-content/x.css">', "", []),  # version inconnue : pas de constat
        ('<script src="/js/jquery-1.12.4.min.js"></script>', "", ["JQUERY_OBSOLETE"]),
        ('<script src="/js/jquery-3.7.1.min.js"></script>', "", []),
        ('<script src="/js/app.js"></script>', "2.2.4", ["JQUERY_OBSOLETE"]),  # version lue dans la page
        ('<script src="/js/jquery-1.12.4.min.js"></script>', "3.6.0", []),  # la version réelle prime
        ('<meta name="generator" content="Joomla! 1.5 - Open Source">', "", ["JOOMLA_OBSOLETE"]),
        ('<meta name="generator" content="Joomla! 4.2 - Open Source">', "", []),
        ('<embed src="intro.swf" type="application/x-shockwave-flash">', "", ["FLASH"]),
    ],
)
def test_technologies(config, signatures, corps, version_js, attendu):
    info = page(corps=corps, version_jquery_js=version_js)
    assert codes(info, config, signatures) == attendu


def test_mesures_technologies(config, signatures):
    corps = '<meta name="generator" content="WordPress 4.9.8"><script src="/wp-includes/js/jquery/jquery.js?ver=1.12.4"></script>'
    m = evaluer_page(page(corps=corps), config, signatures, MAINTENANT).mesures
    assert (m["cms"], m["version_wordpress"], m["version_jquery"]) == ("WordPress", "4.9.8", "1.12.4")
    assert m["technologies"] == "WordPress 4.9.8, jQuery 1.12.4"


def test_mise_en_page_tableaux():
    texte = "Du texte de présentation de l'entreprise. " * 10
    imbriques = BeautifulSoup(f"<table><tr><td><table><tr><td>{texte}</td></tr></table></td></tr></table>", "html.parser")
    assert "imbriqués" in mise_en_page_tableaux(imbriques)
    grand = BeautifulSoup(f"<body><table><tr><td>{texte}</td></tr></table><p>fin</p></body>", "html.parser")
    assert "du texte" in mise_en_page_tableaux(grand)
    donnees = BeautifulSoup(f"<body><p>{texte}</p><table><tr><th>Prix</th></tr><tr><td>{texte}</td></tr></table></body>", "html.parser")
    assert mise_en_page_tableaux(donnees) is None
    assert mise_en_page_tableaux(BeautifulSoup("<table><tr><td>court</td></tr></table>", "html.parser")) is None


def test_title_et_meta_description(config, signatures):
    html = "<html><head></head><body><a href='tel:01'>x</a></body></html>"
    rapport = evaluer_page(page(html=html), config, signatures, MAINTENANT)
    assert {"TITLE_ABSENT", "META_DESCRIPTION_ABSENTE"} <= {c.code for c in rapport}


def test_formulaires_utiles():
    def n(html):
        return formulaires_utiles(BeautifulSoup(html, "html.parser"))

    assert n('<form><input name="nom"><textarea name="m"></textarea></form>') == 1
    assert n('<form role="search"><input name="q"></form>') == 0
    assert n('<form><input type="search" name="s"><input type="submit"></form>') == 0
    assert n('<form><input type="hidden" name="t"></form>') == 0


def test_contact(config, signatures):
    sans_rien = page(html=BASE.replace('<a href="tel:0100000000">Appeler</a>', "").format(corps=""))
    assert "CONTACT_ABSENT" in codes(sans_rien, config, signatures)
    # le formulaire est sur la page contact visitée
    avec_page_contact = page(
        html=BASE.replace('<a href="tel:0100000000">Appeler</a>', "").format(corps=""),
        url_contact="https://salon.test/contact", contact_formulaire=True,
    )
    rapport = evaluer_page(avec_page_contact, config, signatures, MAINTENANT)
    assert "CONTACT_ABSENT" not in {c.code for c in rapport}
    assert rapport.mesures["formulaire"] == "oui" and rapport.mesures["page_contact"] == "https://salon.test/contact"


def test_dates_trouvees():
    html = """<html><head><meta property="article:published_time" content="2019-05-02T10:00:00+00:00">
    <script type="application/ld+json">{"dateModified": "2020-01-15"}</script></head>
    <body><time datetime="2018-03-01">1er mars</time></body></html>"""
    texte = "Publié le 12/04/2017. Mis à jour le 3 février 2021. Posted March 5, 2016. Le 31/02/2020 n'existe pas."
    dates = {d.date().isoformat() for d in dates_trouvees(BeautifulSoup(html, "html.parser"), texte)}
    assert dates == {"2019-05-02", "2020-01-15", "2018-03-01", "2017-04-12", "2021-02-03", "2016-03-05"}


@pytest.mark.parametrize(
    "texte, ancien",
    [
        ("Actualité du 12/03/2023", True),
        ("Actualité du 12/03/2025", False),
        ("Actualité du 12/03/2023. Prochain salon le 5 mars 2027.", False),  # événement à venir = site vivant
        ("Pas de date ici, fondé en 1998", False),
    ],
)
def test_actualites_anciennes(config, signatures, texte, ancien):
    info = page(texte=TEXTE + " " + texte)
    assert ("ACTUALITES_ANCIENNES" in codes(info, config, signatures)) is ancien


def test_captures_reportees_dans_les_mesures(config, signatures):
    info = page(captures={"capture_bureau": "c/b.webp", "capture_mobile": "c/m.webp"})
    m = evaluer_page(info, config, signatures, datetime(2026, 1, 1, tzinfo=timezone.utc)).mesures
    assert (m["capture_bureau"], m["capture_mobile"], m["navigateur_code_http"]) == ("c/b.webp", "c/m.webp", "200")
