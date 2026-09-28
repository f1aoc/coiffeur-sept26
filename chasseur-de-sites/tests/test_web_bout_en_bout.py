"""Bout en bout, interface web : import d'un CSV de 5 sites, scan réel, changement de statut.

Les 4 vrais analyseurs tournent (Chromium compris) sur 5 pages servies en local.
"""

from __future__ import annotations

import re

import pytest

from chasseur.orchestrateur import analyseurs_par_defaut
from conftest import attendre_fin, lancer_scan

pytestmark = pytest.mark.usefixtures("exige_chromium", "sans_proxy")

PAGES = {
    "Salon Moderne": "responsive.html",
    "Institut Beauté Nature": "wordpress49.html",
    "Salon Disparu": "parking.html",
    "Studio Vide": "blanche.html",
    "Garage Martin": "pirate.html",
}


def test_import_scan_et_statut(fabrique_web, serveur):
    web = fabrique_web(analyseurs=analyseurs_par_defaut)
    contenu = "nom;url;téléphone;adresse\n" + "\n".join(
        f"{nom};{serveur.url(page)};01 00 00 00 0{i};{i} rue du Test, 8400{i} Avignon" for i, (nom, page) in enumerate(PAGES.items())
    )

    # 1. Import : aperçu puis lancement
    apercu = web.post("/analyses/apercu", files={"fichier": ("cinq.csv", contenu.encode(), "text/csv")}).text
    assert "<strong>5</strong> entreprises, dont <strong>5</strong> avec un site" in apercu
    scan_id = lancer_scan(web, "cinq.csv", contenu)

    # 2. Scan en tâche de fond jusqu'au bout
    fin = attendre_fin(web, scan_id, delai=180)
    assert "<strong>5 / 5</strong> sites analysés" in fin and "Terminé" in fin
    assert re.search(r"<span>Cassés</span><strong>3</strong>", fin)
    assert re.search(r"<span>Obsolètes</span><strong>1</strong>", fin)
    assert re.search(r"<span>Corrects</span><strong>1</strong>", fin)

    # 3. Résultats : tri par score, miniatures, problèmes en clair
    page = web.get(f"/resultats?scan={scan_id}").text
    assert page.index("Salon Disparu") < page.index("Salon Moderne")
    assert page.count('class="miniature"') == 5
    assert "Domaine parqué (à vendre)" in page and "Spam caché (piratage)" in page and "WordPress périmé" in page
    miniature = re.search(r'<img src="(/captures/scan-\d+/[^"]+-mini\.webp)"', page)[1]
    assert web.get(miniature).headers["content-type"] == "image/webp"

    # 4. Fiche : captures bureau + mobile, message client, détails techniques
    prospect_id = int(re.search(r'<a href="/prospects/(\d+)"><strong>Garage Martin', page)[1])
    fiche = web.get(f"/prospects/{prospect_id}").text
    assert "Ordinateur (1366 px)" in fiche and "Téléphone (375 px)" in fiche
    assert "publicités cachées pour des médicaments" in fiche
    assert "viagra" in fiche  # preuve dans les détails techniques

    # 5. Changement de statut, visible dans la liste filtrée et l'historique
    r = web.post(f"/prospects/{prospect_id}/statut", data={"statut": "Contacté", "contexte": "fiche"})
    assert "À contacter → <strong>Contacté</strong>" in r.text
    filtre = web.get(f"/resultats?scan={scan_id}&statut=Contacté").text
    assert "Garage Martin" in filtre and "Salon Moderne" not in filtre and "1 prospect" in filtre
    assert "À contacter → <strong>Contacté</strong>" in web.get(f"/prospects/{prospect_id}").text
