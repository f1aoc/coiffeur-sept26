"""Routes du Lot 5 : recherche Places, RGPD, prospects prioritaires, planification, comparaison, À propos."""

from __future__ import annotations

import re

import httpx
import respx

from chasseur.db import reglages
from chasseur.db.tables import ProspectDB, Scan
from chasseur.sources import places
from conftest import attendre_fin, lancer_scan
from test_places import fiche


def test_recherche_sans_cle(web):
    page = web.get("/recherche").text
    assert "Recherche « secteur + ville »" in page and "Ajoutez d'abord votre clé Google Places" in page
    assert "Prospection B2B : le rappel" in page
    estimation = web.post("/recherche/estimation", data={"secteur": "coiffeur", "villes": "Avignon\nApt", "pages": "3"}).text
    assert "Au plus 6 requêtes" in estimation and "disabled" in estimation
    assert "Indiquez un secteur" in web.post("/recherche/estimation", data={"secteur": "", "villes": ""}).text
    assert "Aucune clé" in web.post("/recherche", data={"secteur": "coiffeur", "villes": "Apt"}).text


def test_recherche_places_puis_analyse(web):
    with web.app.state.stockage.session() as s:
        reglages.ecrire_cle_api(web.app.state.stockage, s, reglages.CLE_PLACES, "CLE-PLACES-TEST")
        s.commit()
    assert "disabled" not in web.post("/recherche/estimation", data={"secteur": "coiffeur", "villes": "Avignon"}).text
    with respx.mock(assert_all_called=False) as mock:
        mock.post(places.API).respond(200, json={"places": [
            fiche(1, "https://casse-1.test/"), fiche(2, "https://ok-2.test"), fiche(3), fiche(4, "https://www.facebook.com/x"),
            fiche(5, "https://www.casse-1.test/contact"),  # même domaine que la fiche 1
        ]})
        apercu = web.post("/recherche", data={"secteur": "coiffeur", "villes": "Avignon", "pages": "1"}).text
    assert "Recherche Google Places" in apercu and "1 requête(s) effectuée(s) ; 2 fiche(s) écartée(s)" in apercu
    assert "<strong>2</strong> entreprises" in apercu and "1 doublon retiré" in apercu
    assert "Salon 1" in apercu and "4.5 ★ (31)" in apercu
    jeton = re.search(r'name="jeton" value="([^"]+)"', apercu)[1]
    source = re.search(r'name="source" value="([^"]+)"', apercu)[1]
    assert source == "Recherche Google Places « coiffeur » (Avignon)"
    r = web.post("/analyses", data={"jeton": jeton, "nom": "Coiffeurs Avignon", "source": source})
    scan_id = int(r.headers["location"].rsplit("/", 1)[1])
    attendre_fin(web, scan_id)
    with web.app.state.stockage.session() as s:
        scan = s.get(Scan, scan_id)
        assert (scan.total, scan.format, scan.source) == (2, "Recherche Google Places", source)
        p = next(x for x in s.exec(__import__("sqlmodel").select(ProspectDB).where(ProspectDB.scan_id == scan_id)))
        assert p.source == source and p.lien_maps.startswith("https://maps.google.com")
    assert "chaque semaine" not in web.get("/analyses").text


def test_prospects_prioritaires_et_bonus(web, base_rapports):
    page = web.get("/resultats").text
    assert page.count('class="bonus"') == 1 and "Prospects prioritaires" in page
    filtre = web.get("/resultats?prioritaires=1").text
    assert "Salon Cassé" in filtre and "Institut Vieillot" not in filtre and "1 prospect" in filtre
    assert "Bonus commercial" in web.get(f"/prospects/{base_rapports['casse']}").text
    assert "prioritaires=1" in re.search(r'href="(/export\.xlsx\?[^"]*)"', filtre)[1]


def test_suppression_avec_opposition(web, base_rapports):
    fiche_html = web.get(f"/prospects/{base_rapports['casse']}").text
    assert "Supprimer ce prospect" in fiche_html and "liste d'opposition" in fiche_html
    r = web.post(f"/prospects/{base_rapports['casse']}/supprimer", data={"opposer": "1"})
    assert r.status_code == 303
    page = web.get(r.headers["location"]).text
    assert "« Salon Cassé » a été supprimé et son domaine ne sera plus jamais analysé." in page
    assert web.get(f"/prospects/{base_rapports['casse']}").status_code == 404
    assert "casse.test" in web.get("/oppositions").text
    # Un nouvel import de ce domaine est écarté
    apercu = web.post("/analyses/apercu", files={"fichier": ("x.csv", b"nom;url\nRevenu;https://casse.test\nAutre;https://neuf.test\n", "text/csv")}).text
    assert "1 entreprise écartée" in apercu and "<strong>1</strong> entreprise," in apercu


def test_liste_d_opposition(web, base_rapports):
    r = web.post("/oppositions", data={"domaine": "https://www.vieux.test/page", "motif": "Refus par téléphone"})
    page = web.get(r.headers["location"]).text
    assert "vieux.test ajouté à la liste d&#39;opposition ; 1 prospect(s) supprimé(s)." in page and "Refus par téléphone" in page
    erreur = web.get(web.post("/oppositions", data={"domaine": "n'importe quoi"}).headers["location"]).text
    assert "n&#39;est pas un nom de domaine valide" in erreur
    identifiant = re.search(r'action="/oppositions/(\d+)/retirer"', page)[1]
    web.post(f"/oppositions/{identifiant}/retirer")
    assert "Aucun domaine dans la liste d'opposition" in web.get("/oppositions").text


def test_simple_suppression(web, base_rapports):
    r = web.post(f"/prospects/{base_rapports['correct']}/supprimer")
    assert "a été supprimé." in web.get(r.headers["location"]).text
    assert "Aucun domaine" in web.get("/oppositions").text
    assert web.post("/prospects/999/supprimer").status_code == 404


def test_planification_et_comparaison(web):
    scan_id = lancer_scan(web, "Salons", "nom;url\nA;https://casse.test\nB;https://ok.test\n")
    attendre_fin(web, scan_id)
    page = web.get(f"/analyses/{scan_id}").text
    assert "Relancer cette analyse chaque semaine" in page
    web.post(f"/analyses/{scan_id}/planifier", data={"actif": "1"})
    page = web.get(f"/analyses/{scan_id}").text
    assert "Relancée chaque semaine" in page and "Arrêter la relance hebdomadaire" in page
    assert "chaque semaine" in web.get("/analyses").text
    assert "Aucune autre analyse à comparer" in web.get(f"/analyses/{scan_id}/comparaison").text

    second = lancer_scan(web, "Salons bis", "nom;url\nA;https://ok-maintenant.test\nB;https://casse-maintenant.test\n")
    attendre_fin(web, second)
    comparaison = web.get(f"/analyses/{second}/comparaison?avec={scan_id}").text
    assert "Sites devenus cassés depuis la dernière fois" in comparaison
    assert web.get(f"/analyses/999/comparaison").status_code == 404
    web.post(f"/analyses/{scan_id}/planifier", data={"actif": "0"})
    assert "Relancer cette analyse chaque semaine" in web.get(f"/analyses/{scan_id}").text


def test_a_propos_et_journal(web):
    import logging

    logging.getLogger("chasseur.test").error("panne simulée contact@exemple.fr")
    for h in logging.getLogger("chasseur").handlers:
        h.flush()
    page = web.get("/a-propos").text
    assert "Chasseur de sites" in page and "Moteur PDF" in page and "erreurs.log" in page
    assert "panne simulée [e-mail masqué]" in page and "contact@exemple.fr" not in page
    assert 'href="/a-propos"' in web.get("/analyses").text


def test_reglage_de_la_conservation(web):
    assert 'id="conservation_mois" name="conservation_mois" min="1" max="120" value="12"' in web.get("/reglages").text
    web.post("/reglages", data={"conservation_mois": "6", "parallelisme": "10"})
    assert 'value="6"' in web.get("/reglages").text
