"""Scans planifiés (hebdomadaires), comparaison entre scans, journal des erreurs."""

from __future__ import annotations

import logging
from datetime import timedelta

from chasseur import planification
from chasseur.db import depot
from chasseur.db.tables import ProspectDB, Scan, maintenant
from chasseur.journal import configurer, dernieres_lignes, enregistrer_secret, nettoyer
from chasseur.modeles import Prospect, Resultat
from chasseur.rgpd import ajouter_opposition
from chasseur.scoring import noter


def test_planifier_et_relancer(stockage, base_rapports):
    with stockage.session() as s:
        racine = planification.planifier(s, base_rapports["scan"], True)
        assert racine.planifie and racine.prochaine_execution is not None
        assert planification.scans_dus(s) == []
        dans_8_jours = maintenant() + timedelta(days=8)
        assert [x.id for x in planification.scans_dus(s, dans_8_jours)] == [racine.id]

        depot.changer_statut(s, base_rapports["casse"], "Intéressé")
        ajouter_opposition(stockage, s, "vieux.test")  # l'Institut Vieillot ne doit plus être relancé
        relance = planification.creer_relance(s, s.get(Scan, racine.id), dans_8_jours)
        assert relance.origine_id == racine.id and relance.total == 2 and relance.nom.startswith("Vaucluse – ")
        nouveaux = {p.nom: p for p in depot.a_analyser(s, relance.id)}
        assert set(nouveaux) == {"Salon Cassé", "Coiffure Impeccable"}
        assert nouveaux["Salon Cassé"].statut == "Intéressé"  # le suivi commercial continue
        assert planification.scans_dus(s, dans_8_jours) == []  # reporté d'une semaine
        assert [x.id for x in planification.serie(s, racine)] == [racine.id, relance.id]
        planification.planifier(s, relance.id, False)  # arrêter depuis n'importe quel scan de la série
        assert not s.get(Scan, racine.id).planifie


def test_comparaison_sites_devenus_casses(stockage, base_rapports, config):
    with stockage.session() as s:
        racine = s.get(Scan, base_rapports["scan"])
        relance = planification.creer_relance(s, racine)
        prospects = {p.nom: p for p in depot.a_analyser(s, relance.id)}

        def analyser(nom, *codes):
            r = noter(Resultat(Prospect(), [config.constat(c, "m", "p") for c in codes]), config)
            depot.enregistrer_resultat(stockage, s, prospects[nom].id, r)

        analyser("Coiffure Impeccable", "SSL_EXPIRE")  # Correct → Cassé
        analyser("Salon Cassé")  # Cassé → Correct
        analyser("Institut Vieillot", "WORDPRESS_OBSOLETE", "SSL_ABSENT", "VIEWPORT_ABSENT")  # Obsolète → Obsolète
        assert planification.scan_precedent(s, relance).id == racine.id
        c = planification.comparer(s, racine, relance)
        assert [n.nom for _, n in c.devenus_casses] == ["Coiffure Impeccable"]
        assert [n.nom for _, n in c.repares] == ["Salon Cassé"]
        assert c.inchanges == 1 and c.nouveaux == [] and c.disparus == []


def test_entretien_lance_les_relances_dues(stockage, base_rapports):
    import asyncio

    from chasseur.web.app import entretenir
    from chasseur.web.taches import GestionnaireScans

    async def scenario():
        gestionnaire = GestionnaireScans(stockage, fabrique_analyseurs=lambda config: [])
        with stockage.session() as s:
            racine = planification.planifier(s, base_rapports["scan"], True)
            racine.prochaine_execution = maintenant() - timedelta(minutes=1)
            s.add(racine)
            s.commit()
        purges, lances = entretenir(stockage, gestionnaire, purge=True)
        assert purges == 0 and len(lances) == 1
        await gestionnaire.attendre(lances[0])
        with stockage.session() as s:
            assert s.get(Scan, lances[0]).statut == "termine"
            assert entretenir(stockage, gestionnaire, purge=False) == (0, [])  # plus rien de dû

    asyncio.run(scenario())


# --- Journal ----------------------------------------------------------------------


def test_journal_masque_les_donnees_sensibles(tmp_path):
    enregistrer_secret("MA-CLE-PAGESPEED-123")
    texte = nettoyer("échec https://api/x?key=ABCDEF&url=a MA-CLE-PAGESPEED-123 AIzaSyA1234567890abcdefghijklmnopqrs contact@salon.fr")
    assert "ABCDEF" not in texte and "MA-CLE" not in texte and "AIzaSy" not in texte and "contact@salon.fr" not in texte
    assert "key=***" in texte and "[e-mail masqué]" in texte

    chemin = configurer(tmp_path)
    logging.getLogger("chasseur.test").error("panne pour MA-CLE-PAGESPEED-123")
    logging.getLogger("chasseur.test").info("information non écrite")
    for h in logging.getLogger("chasseur").handlers:
        h.flush()
    lignes = dernieres_lignes(chemin)
    assert len(lignes) == 1 and "panne pour ***" in lignes[0] and "ERROR" in lignes[0]
    assert configurer(tmp_path) == chemin and sum(getattr(h, "baseFilename", "") == str(chemin) for h in logging.getLogger("chasseur").handlers) == 1


def test_journal_absent(tmp_path):
    assert dernieres_lignes(tmp_path / "absent.log") == []


def test_migration_d_une_base_existante(tmp_path):
    import sqlite3

    from chasseur.db import Stockage
    from chasseur.db.moteur import migrer

    c = sqlite3.connect(tmp_path / "chasseur.db")
    c.execute("create table scans (id integer primary key, nom varchar not null, fichier varchar, format varchar, statut varchar,"
              " total integer, cree_le datetime, demarre_le datetime, termine_le datetime, erreur varchar)")
    c.execute("insert into scans (nom, statut, total) values ('Septembre', 'termine', 3)")
    c.commit()
    c.close()
    stockage = Stockage(tmp_path)
    with stockage.session() as s:
        scan = s.get(Scan, 1)
        assert (scan.nom, scan.planifie, scan.source, scan.origine_id) == ("Septembre", False, "", None)
    assert migrer(stockage.moteur) == []
    assert ProspectDB  # la table prospects a été créée normalement
