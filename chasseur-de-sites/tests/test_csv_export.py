from __future__ import annotations

import csv

from chasseur.modeles import Prospect, Resultat
from chasseur.reports import COLONNES, exporter_csv
from chasseur.scoring import noter


def test_export_trie_par_score(tmp_path, config_fixe):
    def r(nom, *codes_):
        cs = [config_fixe.constat(c, f"message {c}", f"preuve {c}") for c in codes_]
        return noter(Resultat(Prospect(nom=nom, url=f"https://{nom}.test"), cs), config_fixe)

    sortie = exporter_csv([r("faible", "C_MOYENNE"), r("sain"), r("fort", "A_CRITIQUE", "C_MOYENNE")], tmp_path / "out" / "r.csv")

    brut = sortie.read_bytes()
    assert brut.startswith(b"\xef\xbb\xbf")  # BOM pour Excel
    lignes = list(csv.DictReader(brut.decode("utf-8-sig").splitlines(), delimiter=";"))
    assert list(lignes[0]) == COLONNES
    assert [(l["rang"], l["nom"], l["score"]) for l in lignes] == [("1", "fort", "60"), ("2", "faible", "10"), ("3", "sain", "0")]
    fort = lignes[0]
    assert fort["priorite"] == "A"
    assert fort["codes"] == "A_CRITIQUE | C_MOYENNE"
    assert fort["gravite_max"] == "critique"
    assert fort["messages_client"] == "message A_CRITIQUE | message C_MOYENNE"
    assert lignes[2]["codes"] == "" and lignes[2]["gravite_max"] == ""
