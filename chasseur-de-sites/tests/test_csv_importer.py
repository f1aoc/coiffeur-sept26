from __future__ import annotations

import pytest

from chasseur.importers import ErreurImport, importer_csv
from conftest import FIXTURES


def ecrire(tmp_path, contenu: str, encodage="utf-8"):
    chemin = tmp_path / "p.csv"
    chemin.write_bytes(contenu.encode(encodage))
    return chemin


def test_fixture_point_virgule_et_accents():
    prospects = importer_csv(FIXTURES / "prospects.csv")
    assert len(prospects) == 6
    p = prospects[0]
    assert (p.nom, p.url, p.telephone, p.categorie) == ("Salon Tout Va Bien", "https://ok.test", "01 02 03 04 05", "coiffeur")
    assert p.ligne == 2
    assert prospects[4].url == ""  # prospect sans site conservé


def test_virgule_et_synonymes(tmp_path):
    chemin = ecrire(tmp_path, "Entreprise,Site Web,Tel\nChez Paul,paul.test,0600000000\n")
    (p,) = importer_csv(chemin)
    assert (p.nom, p.url, p.telephone, p.adresse, p.categorie) == ("Chez Paul", "paul.test", "0600000000", "", "")


def test_colonnes_toutes_optionnelles(tmp_path):
    (p,) = importer_csv(ecrire(tmp_path, "url\nhttps://seul.test\n"))
    assert p.url == "https://seul.test" and p.nom == ""


def test_lignes_vides_ignorees_et_espaces_retires(tmp_path):
    chemin = ecrire(tmp_path, "nom;url\n  A  ; a.test \n;\n\nB;b.test\n")
    assert [(p.nom, p.url) for p in importer_csv(chemin)] == [("A", "a.test"), ("B", "b.test")]


def test_bom_et_cp1252(tmp_path):
    assert importer_csv(ecrire(tmp_path, "﻿nom;url\nA;a.test\n"))[0].nom == "A"
    assert importer_csv(ecrire(tmp_path, "nom;catégorie\nCafé;crêperie\n", "cp1252"))[0].categorie == "crêperie"


def test_adresse_sur_plusieurs_lignes(tmp_path):
    chemin = ecrire(tmp_path, 'nom,adresse,url\nA,"1 rue X\n75000 Paris",a.test\nB,,b.test\n')
    a, b = importer_csv(chemin)
    assert a.adresse == "1 rue X\n75000 Paris" and b.url == "b.test"


def test_colonnes_inconnues(tmp_path):
    with pytest.raises(ErreurImport, match="Aucune colonne reconnue"):
        importer_csv(ecrire(tmp_path, "foo;bar\n1;2\n"))


def test_fichier_absent(tmp_path):
    with pytest.raises(ErreurImport, match="introuvable"):
        importer_csv(tmp_path / "nope.csv")


def test_fichier_vide(tmp_path):
    assert importer_csv(ecrire(tmp_path, "")) == []
