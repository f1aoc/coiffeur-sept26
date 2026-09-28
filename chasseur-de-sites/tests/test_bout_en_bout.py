"""Bout en bout : `chasseur scan` sur 5 URL locales, avec les 4 analyseurs réels.

Réseau (vrai DNS, HTTP, TLS vers 127.0.0.1), Domaine (parking), Navigateur
(vrai Chromium) et Performance (sans clé API → « non vérifié »).
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest
from PIL import Image

from chasseur import cli
from conftest import RACINE

pytestmark = pytest.mark.usefixtures("exige_chromium", "sans_proxy")

PAGES = {
    "Salon Moderne": "responsive.html",
    "Institut Beauté Nature": "wordpress49.html",
    "Salon Disparu": "parking.html",
    "Studio Vide": "blanche.html",
    "Garage Martin": "pirate.html",
}


def test_scan_complet_sur_5_urls(tmp_path, serveur, capsys):
    entree = tmp_path / "prospects.csv"
    lignes = ["nom;url;téléphone"] + [f"{nom};{serveur.url(page)};01 00 00 00 0{i}" for i, (nom, page) in enumerate(PAGES.items())]
    entree.write_text("\n".join(lignes) + "\n", encoding="utf-8")
    sortie = tmp_path / "export" / "resultats.csv"

    code = cli.main(["scan", str(entree), "-o", str(sortie), "-c", str(RACINE / "config.yaml"), "-q"])

    assert code == 0
    resultats = list(csv.DictReader(sortie.read_text(encoding="utf-8-sig").splitlines(), delimiter=";"))
    assert len(resultats) == 5
    r = {l["nom"]: l for l in resultats}

    # États (§3.4). Le serveur local n'a pas de HTTPS : +15 pts « https » pour tous.
    assert r["Salon Moderne"]["etat"] == "Correct"
    assert r["Institut Beauté Nature"]["etat"] == "Obsolète"
    assert r["Salon Disparu"]["etat"] == "Cassé"
    assert r["Studio Vide"]["etat"] == "Cassé"
    assert r["Garage Martin"]["etat"] == "Cassé"

    # Une colonne par contrôle
    assert r["Salon Disparu"]["ctrl_domaine"] == "KO : DOMAINE_PARKING"
    assert r["Studio Vide"]["ctrl_page_blanche_php"] == "KO : PAGE_BLANCHE"
    assert r["Garage Martin"]["ctrl_piratage"] == "KO : PIRATAGE_SPAM"
    assert r["Institut Beauté Nature"]["ctrl_technologies"] == "KO : WORDPRESS_OBSOLETE, JQUERY_OBSOLETE"
    assert r["Institut Beauté Nature"]["version_wordpress"] == "4.9.8"
    assert r["Salon Moderne"]["ctrl_responsive"] == "OK"
    for ligne in resultats:
        assert ligne["ctrl_https"] == "KO : SSL_ABSENT"
        assert ligne["ctrl_performance"] == "non vérifié"  # pas de clé : le scan continue
        assert ligne["ctrl_domaine_expiration"] == "non vérifié"  # 127.0.0.1 n'a pas de WHOIS
        assert ligne["code_http"] == "200"

    # Tri par score, et score = somme des contrôles déclenchés
    scores = [int(l["score"]) for l in resultats]
    assert scores == sorted(scores, reverse=True)
    assert r["Salon Moderne"]["score"] == "15"
    # parking 40 + page blanche 30 + https 15 + viewport 15 + meta 5 + contact 5 = 110, plafonné
    assert r["Salon Disparu"]["score"] == "100"

    # Captures bureau et mobile en WebP < 150 Ko, dans export/captures/
    for ligne in resultats:
        for colonne, largeur in (("capture_bureau", 1366), ("capture_mobile", 375)):
            capture = Path(ligne[colonne])
            assert capture.parent == sortie.parent / "captures"
            assert capture.stat().st_size < 150 * 1024
            with Image.open(capture) as image:
                assert image.width == largeur

    sortie_console = capsys.readouterr().out
    assert "Cassé : 3" in sortie_console and "Obsolète : 1" in sortie_console and "Correct : 1" in sortie_console
