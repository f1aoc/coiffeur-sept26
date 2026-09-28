"""Routes FastAPI : écrans, fragments HTMX, statuts, notes, réglages, sécurité."""

from __future__ import annotations

import re
import sqlite3
import time

from chasseur.db import depot
from chasseur.db.tables import ProspectDB
from conftest import attendre_fin, lancer_scan, televerser
from test_importers_maps import CSV_MAPS

CSV_3 = "nom;url;téléphone;adresse\nSalon Cassé;https://casse.test;0100000001;1 rue A, 69001 Lyon\n" \
        "Salon Vieux;https://vieux.test;0100000002;2 rue B, 29200 Brest\nSalon OK;https://ok.test;0100000003;3 rue C, 75002 Paris\n"


def prospect_par_nom(web, nom):
    with web.app.state.stockage.session() as s:
        return next(p for p in s.exec(depot.select(ProspectDB)) if p.nom == nom)


# --- Navigation ------------------------------------------------------------------


def test_accueil_redirige_vers_les_analyses(web):
    r = web.get("/")
    assert r.status_code == 303 and r.headers["location"] == "/analyses"
    page = web.get("/analyses").text
    assert "Aucune analyse pour l'instant" in page and 'lang="fr"' in page


def test_pages_principales(web):
    assert "Glissez-déposez votre fichier ici" in web.get("/analyses/nouvelle").text
    assert "Aucun prospect ne correspond" in web.get("/resultats").text
    assert "Poids du scoring" in web.get("/reglages").text
    assert web.get("/static/htmx.min.js").status_code == 200
    assert web.get("/prospects/999").status_code == 404
    assert web.get("/analyses/999").status_code == 404


# --- Nouvelle analyse ------------------------------------------------------------------


def test_apercu_des_10_premieres_lignes(web):
    lignes = "\n".join(f"Salon {i};https://s{i}.test;010000000{i % 10}" for i in range(12))
    page = televerser(web, "douze.csv", "nom;url;tel\n" + lignes).text
    assert "CSV / Excel générique" in page
    assert "<strong>12</strong> entreprises" in page and "<strong>12</strong> avec un site" in page
    assert page.count("<tr>") == 1 + 10  # en-tête + 10 lignes
    assert "Salon 9" in page and "Salon 10" not in page
    assert re.search(r'name="jeton" value="[0-9a-f]{32}\.csv"', page)


def test_apercu_detecte_l_outil_google_maps(web):
    page = televerser(web, "leads.csv", CSV_MAPS).text
    assert "Outil Google Maps (CSV)" in page
    assert "<strong>3</strong> entreprises, dont <strong>1</strong> avec un site" in page
    assert "sans vrai site" in page
    assert "L&#39;Isle-sur-la-Sorgue" in page and "4.7 ★ (132)" in page


def test_apercu_refuse_les_mauvais_fichiers(web):
    assert "CSV ou Excel" in televerser(web, "image.png", b"\x89PNG").text
    assert "Aucune colonne reconnue" in televerser(web, "x.csv", "foo;bar\n1;2\n").text
    assert "aucune entreprise" in televerser(web, "vide.csv", "nom;url\n").text
    assert list(web.app.state.stockage.dossier_imports.iterdir()) == []  # fichiers refusés supprimés


def test_lancement_refuse_un_jeton_invalide(web):
    assert web.post("/analyses", data={"jeton": "../../etc/passwd"}).status_code == 400
    assert web.post("/analyses", data={"jeton": "0" * 32 + ".csv"}).status_code == 400


# --- Progression ------------------------------------------------------------------


def test_scan_complet_et_compteurs(web):
    scan_id = lancer_scan(web, "Trois salons", CSV_3)
    assert "Trois salons" in web.get(f"/analyses/{scan_id}").text
    fragment = attendre_fin(web, scan_id)
    assert "<strong>3 / 3</strong> sites analysés (100 %)" in fragment
    assert "Terminé" in fragment
    for libelle, n in (("Cassés", 1), ("Obsolètes", 1), ("Corrects", 1)):
        assert re.search(rf"<span>{libelle}</span><strong>{n}</strong>", fragment)
    assert "Pause" not in fragment and "Reprendre" not in fragment
    liste = web.get("/analyses").text
    assert "Trois salons" in liste and "3 / 3" in liste


def test_pause_et_reprise(fabrique_web):
    web = fabrique_web(duree=0.3)
    lignes = "\n".join(f"Salon {i};https://s{i}.test" for i in range(30))
    scan_id = lancer_scan(web, "Trente", "nom;url\n" + lignes)
    time.sleep(0.1)
    fragment = web.post(f"/analyses/{scan_id}/pause").text
    assert "En pause" in fragment and "Reprendre" in fragment
    time.sleep(0.8)  # les sites déjà commencés (10 au plus) se terminent
    faits_en_pause = int(re.search(r"<strong>(\d+) / 30</strong>", web.get(f"/analyses/{scan_id}/progression").text)[1])
    time.sleep(0.8)
    assert f"<strong>{faits_en_pause} / 30</strong>" in web.get(f"/analyses/{scan_id}/progression").text
    assert faits_en_pause <= 10
    assert "En cours" in web.post(f"/analyses/{scan_id}/reprendre").text
    assert "<strong>30 / 30</strong>" in attendre_fin(web, scan_id)


def test_temps_restant_affiche(fabrique_web):
    web = fabrique_web(duree=0.2)
    scan_id = lancer_scan(web, "Vingt", "nom;url\n" + "\n".join(f"S{i};https://s{i}.test" for i in range(40)))
    time.sleep(0.5)
    fragment = web.get(f"/analyses/{scan_id}/progression").text
    assert re.search(r"Temps restant estimé : <strong>\d+ s</strong>", fragment)
    attendre_fin(web, scan_id)


def test_reprise_d_un_scan_interrompu(fabrique_web, stockage):
    web = fabrique_web(duree=0.2)
    scan_id = lancer_scan(web, "Coupure", "nom;url\n" + "\n".join(f"S{i};https://s{i}.test" for i in range(20)))
    time.sleep(0.3)
    web.__exit__(None, None, None)  # l'application est fermée pendant le scan
    web2 = fabrique_web()
    fragment = web2.get(f"/analyses/{scan_id}/progression").text
    faits = int(re.search(r"<strong>(\d+) / 20</strong>", fragment)[1])
    assert "Interrompu" in fragment and "Reprendre" in fragment and faits < 20
    web2.post(f"/analyses/{scan_id}/reprendre")
    assert "<strong>20 / 20</strong>" in attendre_fin(web2, scan_id)


# --- Résultats ------------------------------------------------------------------


def test_resultats_filtres_tri_recherche(web):
    scan_id = lancer_scan(web, "Trois salons", CSV_3)
    attendre_fin(web, scan_id)
    page = web.get(f"/resultats?scan={scan_id}").text
    assert page.index("Salon Cassé") < page.index("Salon Vieux") < page.index("Salon OK")  # tri par score
    assert "Erreur serveur" in page and "Pas de HTTPS" in page  # problèmes principaux en clair
    assert "Lyon" in page and 'href="tel:0100000001"' in page
    assert "Salon Vieux" not in web.get("/resultats?etat=Cassé").text
    filtre = web.get("/resultats?probleme=responsive").text
    assert "Salon Vieux" in filtre and "Salon Cassé" not in filtre
    assert "Salon OK" in web.get("/resultats?q=paris").text and "Salon OK" not in web.get("/resultats?q=brest").text
    par_nom = web.get("/resultats?tri=nom&ordre=asc").text
    assert par_nom.index("Salon Cassé") < par_nom.index("Salon OK") < par_nom.index("Salon Vieux")
    assert 'aria-sort="ascending"' in par_nom


def test_pagination_50_lignes(web):
    lignes = "\n".join(f"Salon {i:03d};https://s{i}.test" for i in range(120))
    scan_id = lancer_scan(web, "Cent vingt", "nom;url\n" + lignes)
    attendre_fin(web, scan_id)
    page1 = web.get("/resultats?tri=nom&ordre=asc").text
    assert "120 prospects" in page1 and "Page 1 / 3" in page1
    assert page1.count('class="statut-commercial"') == 50
    assert "Salon 049" in page1 and "Salon 050" not in page1
    page3 = web.get("/resultats?tri=nom&ordre=asc&page=3").text
    assert page3.count('class="statut-commercial"') == 20 and "← Précédente" in page3 and "Suivante" not in page3


def test_statut_modifiable_sur_place(web):
    scan_id = lancer_scan(web, "Trois salons", CSV_3)
    attendre_fin(web, scan_id)
    p = prospect_par_nom(web, "Salon Cassé")
    r = web.post(f"/prospects/{p.id}/statut", data={"statut": "Intéressé"})
    assert r.status_code == 200 and "<option selected>Intéressé</option>" in r.text and "Enregistré" in r.text
    assert 'hx-swap-oob' not in r.text
    assert "Salon Cassé" in web.get("/resultats?statut=Intéressé").text
    assert web.post(f"/prospects/{p.id}/statut", data={"statut": "Vendu"}).status_code == 400
    # Depuis la fiche, l'historique est mis à jour en même temps
    r = web.post(f"/prospects/{p.id}/statut", data={"statut": "Client", "contexte": "fiche"})
    assert 'id="historique" class="historique" hx-swap-oob="true"' in r.text and "Intéressé → <strong>Client</strong>" in r.text


# --- Fiche prospect ------------------------------------------------------------------


def test_fiche_prospect(web):
    scan_id = lancer_scan(web, "Trois salons", CSV_3)
    attendre_fin(web, scan_id)
    p = prospect_par_nom(web, "Salon Vieux")
    page = web.get(f"/prospects/{p.id}").text
    assert "Pas de HTTPS." in page and "Pas mobile." in page  # message_client
    assert "<summary>Détails techniques</summary>" in page and "port 443 fermé" in page
    assert "KO : VIEWPORT_ABSENT" in page and "Aucun changement de statut" in page
    assert "29200 Brest" in page and "Obsolète" in page and "Score <strong>30</strong>/100" in page


def test_notes_enregistrees_automatiquement(web):
    scan_id = lancer_scan(web, "Trois salons", CSV_3)
    attendre_fin(web, scan_id)
    p = prospect_par_nom(web, "Salon OK")
    assert 'hx-trigger="input changed delay:800ms, blur changed"' in web.get(f"/prospects/{p.id}").text
    r = web.post(f"/prospects/{p.id}/note", data={"texte": "Gérante sympa, rappeler jeudi"})
    assert r.status_code == 200 and "Enregistré à" in r.text
    assert "Gérante sympa, rappeler jeudi" in web.get(f"/prospects/{p.id}").text
    assert web.post("/prospects/999/note", data={"texte": "x"}).status_code == 404


def test_captures_servies_et_agrandissables(web, config):
    from PIL import Image

    from chasseur.modeles import Prospect, Rapport, Resultat
    from chasseur.scoring import noter

    stockage = web.app.state.stockage
    with stockage.session() as s:
        scan = depot.creer_scan(s, "Captures", [Prospect(nom="Salon Photo", url="https://photo.test")])
        (p,) = depot.a_analyser(s, scan.id)
        dossier = stockage.dossier_captures / f"scan-{scan.id}"
        dossier.mkdir(parents=True)
        for nom, taille in (("b.webp", (1366, 768)), ("m.webp", (375, 667))):
            Image.new("RGB", taille, "white").save(dossier / nom, "WEBP")
        r = noter(Resultat(Prospect(), mesures={"capture_bureau": str(dossier / "b.webp"), "capture_mobile": str(dossier / "m.webp")}), config)
        depot.enregistrer_resultat(stockage, s, p.id, r)
    fiche = web.get(f"/prospects/{p.id}").text
    assert f'data-agrandir="/captures/scan-{scan.id}/b.webp"' in fiche and f'data-agrandir="/captures/scan-{scan.id}/m.webp"' in fiche
    liste = web.get("/resultats").text
    assert f'src="/captures/scan-{scan.id}/b-mini.webp"' in liste
    image = web.get(f"/captures/scan-{scan.id}/b-mini.webp")
    assert image.status_code == 200 and image.headers["content-type"] == "image/webp"


# --- Réglages ------------------------------------------------------------------


def test_reglages_cles_chiffrees_parallelisme_et_poids(web):
    scan_id = lancer_scan(web, "Trois salons", CSV_3)
    attendre_fin(web, scan_id)
    formulaire = {"cle_pagespeed": "AIzaSy-cle-tres-secrete-9876", "cle_places": "", "parallelisme": "45", "points_responsive": "40"}
    r = web.post("/reglages", data=formulaire)
    assert r.status_code == 303 and r.headers["location"] == "/reglages?ok=1"
    page = web.get("/reglages?ok=1").text
    assert "Réglages enregistrés" in page
    assert "cle-tres-secrete" not in page and "Enregistrée : ••••••••9876" in page  # jamais affichée en clair
    assert 'value="30"' in page  # parallélisme plafonné à 30
    assert 'value="40"' in page and "par défaut : 15" in page
    base = sqlite3.connect(web.app.state.stockage.dossier / "chasseur.db")
    assert "cle-tres-secrete" not in str(base.execute("select * from reglages").fetchall())
    # Les scores existants suivent les nouveaux poids : 15 (https) + 40 (responsive)
    assert prospect_par_nom(web, "Salon Vieux").score == 55
    assert web.app.state.gestionnaire.config().performance.cle == "AIzaSy-cle-tres-secrete-9876"
    # Champ vide = clé inchangée ; case « Supprimer » = clé effacée
    web.post("/reglages", data={"cle_pagespeed": "", "parallelisme": "10"})
    assert web.app.state.gestionnaire.config().performance.cle == "AIzaSy-cle-tres-secrete-9876"
    web.post("/reglages", data={"effacer_cle_pagespeed": "1", "parallelisme": "10"})
    assert web.app.state.gestionnaire.config().performance.cle == ""


# --- Sécurité ------------------------------------------------------------------


def test_requetes_d_une_autre_origine_refusees(web):
    r = web.post("/reglages", data={"parallelisme": "5"}, headers={"Origin": "https://site-malveillant.example"})
    assert r.status_code == 403
    ok = web.post("/reglages", data={"parallelisme": "5"}, headers={"Origin": "http://testserver"})
    assert ok.status_code == 303


def test_hote_inconnu_refuse(web):
    assert web.get("/analyses", headers={"Host": "attaquant.example"}).status_code == 400


def test_scan_en_erreur_sans_divulguer_la_cle(fabrique_web):
    def fabrique(config):
        raise RuntimeError(f"panne avec la clé {config.performance.cle}")

    web = fabrique_web(analyseurs=fabrique)
    web.post("/reglages", data={"cle_pagespeed": "SECRET-XYZ-1234", "parallelisme": "10"})
    scan_id = lancer_scan(web, "Panne", "nom;url\nA;https://a.test\n")
    fragment = attendre_fin(web, scan_id)
    assert "Erreur : RuntimeError : panne avec la clé ***" in fragment
    assert "SECRET-XYZ" not in fragment and "Reprendre" in fragment
