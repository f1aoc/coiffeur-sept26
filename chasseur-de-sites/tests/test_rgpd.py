"""Dédoublonnage, bonus commercial et conformité RGPD (opposition, suppression, purge)."""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlmodel import select

from chasseur import rgpd
from chasseur.bonus import a_bonus, prioritaire
from chasseur.db import depot, reglages
from chasseur.db.tables import Capture, ConstatDB, HistoriqueStatut, Note, Opposition, ProspectDB, maintenant
from chasseur.dedoublonnage import cle_domaine, dedoublonner
from chasseur.modeles import Prospect


# --- Dédoublonnage (§3.1) -----------------------------------------------------------


@pytest.mark.parametrize(
    "a, b, doublon",
    [
        ("https://www.salon-lea.fr/", "salon-lea.fr/contact", True),
        ("https://salon-lea.fr", "https://SALON-LEA.fr", True),
        ("https://salon-lea.fr", "https://autre.fr", False),
        ("https://sites.google.com/view/salon-a", "https://sites.google.com/view/salon-b", True),  # même 1er segment
        ("https://www.facebook.com/salonA", "https://www.facebook.com/salonB", False),
        ("http://127.0.0.1:8000/a.html", "http://127.0.0.1:8000/b.html", False),  # IP : URL complète
        ("https://boutique.salon-lea.fr", "https://salon-lea.fr", False),  # sous-domaine distinct
    ],
)
def test_cle_domaine(a, b, doublon):
    assert (cle_domaine(a) == cle_domaine(b)) is doublon


def test_dedoublonner_garde_le_premier_et_les_sans_site():
    ps = [Prospect(nom="A", url="salon.fr"), Prospect(nom="B", url="https://www.salon.fr/"), Prospect(nom="C"), Prospect(nom="D")]
    gardes, doublons = dedoublonner(ps)
    assert [p.nom for p in gardes] == ["A", "C", "D"] and [p.nom for p in doublons] == ["B"]


# --- Bonus commercial (§3.4) --------------------------------------------------------


@pytest.mark.parametrize("note, avis, bonus", [(4.0, 21, True), (4.8, 300, True), (4.0, 20, False), (3.9, 100, False), (None, 50, False), (4.5, None, False)])
def test_bonus(note, avis, bonus):
    assert a_bonus(note, avis) is bonus


def test_prospect_prioritaire():
    assert prioritaire("Cassé", 4.2, 40) and prioritaire("Obsolète", 4.2, 40)
    assert not prioritaire("Correct", 4.2, 40) and not prioritaire("Cassé", 3.5, 40)


def test_filtre_prospects_prioritaires(stockage, base_rapports):
    # Salon Cassé : 4.6 / 52 avis → prioritaire ; Institut Vieillot : obsolète sans avis → non
    with stockage.session() as s:
        assert [l.prospect.nom for l in depot.rechercher(s, depot.Filtres(prioritaires=True)).lignes] == ["Salon Cassé"]


# --- Liste d'opposition (§6.1) --------------------------------------------------------


@pytest.mark.parametrize("saisie, domaine", [("https://www.Salon-Lea.fr/contact", "salon-lea.fr"), ("salon-lea.fr", "salon-lea.fr"),
                                              ("  boutique.salon.co.uk ", "boutique.salon.co.uk")])
def test_normaliser_domaine(saisie, domaine):
    assert rgpd.normaliser_domaine(saisie) == domaine


@pytest.mark.parametrize("saisie", ["", "pas un domaine", "http://127.0.0.1", "localhost"])
def test_domaine_invalide(saisie):
    with pytest.raises(rgpd.ErreurRGPD):
        rgpd.normaliser_domaine(saisie)


def test_opposition_supprime_les_prospects_et_bloque_les_imports(stockage, base_rapports):
    with stockage.session() as s:
        opposition, supprimes = rgpd.ajouter_opposition(stockage, s, "https://www.casse.test/", "Demande du gérant")
        assert (opposition.domaine, supprimes) == ("casse.test", 1)
        assert s.get(ProspectDB, base_rapports["casse"]) is None
        rgpd.ajouter_opposition(stockage, s, "casse.test")  # déjà présent : pas de doublon
        assert len(list(s.exec(select(Opposition)))) == 1
        prepare = depot.preparer_import(s, [Prospect(nom="X", url="https://shop.casse.test"), Prospect(nom="Y", url="https://ok2.test")])
        assert [p.nom for p in prepare.prospects] == ["Y"] and [p.nom for p in prepare.opposes] == ["X"]
        rgpd.retirer_opposition(s, opposition.id)
        assert rgpd.domaines_opposes(s) == []


def test_opposition_exclue_des_exports(stockage, base_rapports):
    from chasseur.reports.excel import lignes

    with stockage.session() as s:
        rgpd.ajouter_opposition(stockage, s, "vieux.test")
        assert "Institut Vieillot" not in [l["Nom"] for l in lignes(stockage, s, depot.Filtres())]


def test_suppression_complete(stockage, base_rapports):
    with stockage.session() as s:
        pid = base_rapports["casse"]
        depot.enregistrer_note(s, pid, "note")
        depot.changer_statut(s, pid, "Contacté")
        fichiers = [stockage.absolu(c.chemin) for c in depot.captures_de(s, pid).values()]
        assert all(f.is_file() for f in fichiers) and fichiers
        assert rgpd.supprimer_prospect(stockage, s, pid)
        for table in (ConstatDB, Capture, Note, HistoriqueStatut):
            assert list(s.exec(select(table).where(table.prospect_id == pid))) == []
        assert not any(f.exists() for f in fichiers)
        assert not rgpd.supprimer_prospect(stockage, s, pid)


# --- Purge automatique ----------------------------------------------------------------


def test_purge_des_prospects_jamais_contactes(stockage, base_rapports):
    with stockage.session() as s:
        vieux = maintenant() - timedelta(days=400)
        for cle in ("casse", "obsolete"):
            p = s.get(ProspectDB, base_rapports[cle])
            p.collecte_le = vieux
            s.add(p)
        s.commit()
        depot.changer_statut(s, base_rapports["obsolete"], "Contacté")  # contacté : conservé
        assert rgpd.duree_conservation(s) == 12
        assert rgpd.purger(stockage, s) == 1
        assert s.get(ProspectDB, base_rapports["casse"]) is None
        assert s.get(ProspectDB, base_rapports["obsolete"]) is not None
        assert s.get(ProspectDB, base_rapports["correct"]) is not None  # récent


def test_duree_de_conservation_reglable(stockage, base_rapports):
    with stockage.session() as s:
        reglages.ecrire(s, rgpd.CONSERVATION, "1")
        s.commit()
        dans_45_jours = maintenant() + timedelta(days=45)
        assert rgpd.purger(stockage, s, dans_45_jours) == 3
