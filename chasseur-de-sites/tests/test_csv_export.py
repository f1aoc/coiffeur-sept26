from __future__ import annotations

import csv

from chasseur.controles import CONTROLES
from chasseur.modeles import Prospect, Resultat
from chasseur.reports import COLONNES, exporter_csv
from chasseur.scoring import noter


def test_export_trie_par_score_avec_une_colonne_par_controle(tmp_path, config_fixe):
    def r(nom, *codes, **champs):
        cs = [config_fixe.constat(c, f"message {c}", f"preuve {c}") for c in codes]
        return noter(Resultat(Prospect(nom=nom, url=f"https://{nom}.test"), cs, **champs), config_fixe)

    sortie = exporter_csv(
        [
            r("faible", "TITLE_ABSENT"),
            r("sain", "NON_VERIFIE", non_verifies={"performance": "pas de clé API"}),
            r(
                "fort", "HTTP_ERREUR_CLIENT", "TITLE_ABSENT",
                mesures={"code_http": "404", "capture_bureau": "captures/0001-fort-bureau.webp", "technologies": "WordPress 4.9.8"},
            ),
        ],
        tmp_path / "out" / "r.csv",
    )

    brut = sortie.read_bytes()
    assert brut.startswith(b"\xef\xbb\xbf")  # BOM pour Excel
    lignes = list(csv.DictReader(brut.decode("utf-8-sig").splitlines(), delimiter=";"))
    assert list(lignes[0]) == COLONNES
    assert all(f"ctrl_{c.id}" in COLONNES for c in CONTROLES)
    assert [(l["rang"], l["nom"], l["score"], l["etat"]) for l in lignes] == [
        ("1", "fort", "35", "Cassé"),
        ("2", "faible", "5", "Correct"),
        ("3", "sain", "0", "Correct"),
    ]
    fort, _, sain = lignes
    assert fort["codes"] == "HTTP_ERREUR_CLIENT | TITLE_ABSENT"
    assert fort["gravite_max"] == "haute"
    assert fort["messages_client"] == "message HTTP_ERREUR_CLIENT | message TITLE_ABSENT"
    assert fort["ctrl_http_4xx"] == "KO : HTTP_ERREUR_CLIENT"
    assert fort["ctrl_dns"] == "OK"
    assert fort["code_http"] == "404"
    assert fort["technologies"] == "WordPress 4.9.8"
    assert fort["capture_bureau"] == "captures/0001-fort-bureau.webp"
    # « non vérifié » : visible dans sa colonne, mais pas compté comme un problème
    assert sain["codes"] == "" and sain["nb_constats"] == "0" and sain["gravite_max"] == ""
    assert sain["ctrl_performance"] == "non vérifié"
    assert sain["non_verifies"] == "performance (pas de clé API)"
