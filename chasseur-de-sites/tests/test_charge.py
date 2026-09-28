"""Charge §7.2 : 500 sites en moins de 30 minutes, sans plantage, avec reprise après interruption.

Désactivé par défaut (plusieurs minutes) : pytest -m charge -s
Le vrai « chasseur scan » tourne dans un processus séparé, avec la vraie config.yaml (4 analyseurs,
Chromium, 2 essais, 10 sites en parallèle). Il est tué brutalement en cours de route, puis relancé.
"""

from __future__ import annotations

import csv
import os
import shutil
import signal
import subprocess
import sys
import time

import pytest

from conftest import RACINE
from serveur_local import PAGES, ServeurLocal
from test_recette import METIERS, page_correcte, page_obsolete, port_ferme

pytestmark = [pytest.mark.charge, pytest.mark.usefixtures("exige_chromium", "sans_proxy")]

NB_SITES = 500
LIMITE = 30 * 60  # secondes
CASSES = ["parking.html", "blanche.html", "erreur_php.html", "maintenance.html", "pirate.html", "disparu.html", "statut/500"]


def lignes_journal(chemin) -> int:
    return sum(1 for _ in chemin.open(encoding="utf-8")) if chemin.exists() else 0


def test_500_sites_avec_interruption_et_reprise(tmp_path):
    site = tmp_path / "site"
    site.mkdir()
    for i, metier in enumerate(METIERS):
        (site / f"correct-{i}.html").write_text(page_correcte(i, metier), encoding="utf-8")
        (site / f"obsolete-{i}.html").write_text(page_obsolete(i, metier), encoding="utf-8")
    for nom in CASSES[:5]:
        shutil.copy(PAGES / nom, site / nom)

    with ServeurLocal(site) as serveur:
        pages = [f"correct-{i}.html" for i in range(10)] + [f"obsolete-{i}.html" for i in range(10)] + CASSES
        urls = []
        for n in range(NB_SITES):
            if n % 50 == 0:  # 2 % de domaines inexistants, 2 % de serveurs éteints
                urls.append(f"http://site-{n}.invalid/")
            elif n % 50 == 25:
                urls.append(f"http://127.0.0.1:{port_ferme()}/")
            else:
                page = pages[n % len(pages)]
                urls.append(serveur.url(page) + ("&" if "?" in page else "?") + f"site={n}")
        entree = tmp_path / "cinq-cents.csv"
        entree.write_text("nom;url\n" + "\n".join(f"Entreprise {n};{u}" for n, u in enumerate(urls)) + "\n", encoding="utf-8")
        sortie = tmp_path / "resultats.csv"
        journal = sortie.with_name(sortie.name + ".journal.jsonl")
        commande = [sys.executable, "-m", "chasseur.cli", "scan", str(entree), "-o", str(sortie), "-q", "-c", str(RACINE / "config.yaml")]
        env = os.environ | {"PYTHONPATH": str(RACINE)}

        # 1. Premier passage, tué brutalement (SIGKILL) après ~150 sites
        debut = time.monotonic()
        premier = subprocess.Popen(commande, cwd=tmp_path, env=env)
        while lignes_journal(journal) < 150 and premier.poll() is None and time.monotonic() - debut < LIMITE:
            time.sleep(0.5)
        premier.send_signal(signal.SIGKILL)
        premier.wait()
        duree_1 = time.monotonic() - debut
        faits_1 = lignes_journal(journal)
        assert 150 <= faits_1 < NB_SITES and not sortie.exists()

        # 2. Reprise : seuls les sites restants sont analysés
        debut_2 = time.monotonic()
        second = subprocess.run(commande, cwd=tmp_path, env=env, capture_output=True, text=True, timeout=LIMITE)
        duree_2 = time.monotonic() - debut_2
        assert second.returncode == 0, second.stderr[-2000:]

    total = duree_1 + duree_2
    lignes = list(csv.DictReader(sortie.read_text(encoding="utf-8-sig").splitlines(), delimiter=";"))
    etats = {}
    for l in lignes:
        etats[l["etat"]] = etats.get(l["etat"], 0) + 1
    print(f"\n{NB_SITES} sites : interruption après {faits_1} sites ({duree_1:.0f} s), reprise en {duree_2:.0f} s, "
          f"total {total:.0f} s ({total / 60:.1f} min) — états : {etats}")
    assert len(lignes) == NB_SITES and len({l["url"] for l in lignes}) == NB_SITES
    assert not journal.exists()  # scan complet : le journal de reprise est effacé
    assert "À revérifier" not in etats, "aucun site ne doit rester non analysé"
    assert total < LIMITE
