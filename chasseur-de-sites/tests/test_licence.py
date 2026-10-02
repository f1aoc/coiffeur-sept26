"""Licence (paiement Stripe + serveur de licences) : activation, vérifications, remboursement, hors ligne,
écrans et ligne de commande. Le serveur est simulé ; test_licence_bout_en_bout.py utilise le vrai."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from chasseur import licence as lic

SERVEUR = "https://licences.test"
CLE = "CDS-3Test000001AbCdEf-0A1B2C3D4E5F"


class FauxServeur:
    """Imite serveur-licences/worker.js : statut par clé, limite d'ordinateurs, panne réseau simulable."""

    def __init__(self):
        self.cles = {CLE: {"produit": "chasseur-de-sites", "rembourse": False, "machines": []}}
        self.limite = 2
        self.hors_ligne = False
        self.appels: list[tuple[str, dict]] = []

    def __call__(self, url, donnees):
        action = url.rsplit("/", 1)[1]
        self.appels.append((action, donnees))
        if self.hors_ligne:
            raise lic.HorsLigne("pas de réseau")
        c = self.cles.get(donnees["cle"])
        if c is None:
            return 404, {"valide": False, "statut": "inconnue"}
        if donnees.get("produit") != c["produit"]:
            return 403, {"valide": False, "statut": "autre_produit"}
        m = donnees["machine"]
        if action == "liberer":
            c["machines"] = [x for x in c["machines"] if x != m]
            return 200, {"libere": True}
        if c["rembourse"]:
            return 200, {"valide": False, "statut": "desactivee"}
        if action == "activer":
            if m not in c["machines"]:
                if len(c["machines"]) >= self.limite:
                    return 409, {"valide": False, "statut": "limite"}
                c["machines"].append(m)
            return 200, {"valide": True, "statut": "active", "nom": "Agence Durand", "email": "contact@agence-durand.fr"}
        if m not in c["machines"]:
            return 200, {"valide": False, "statut": "machine_inconnue"}
        return 200, {"valide": True, "statut": "active", "nom": "Agence Durand", "email": "contact@agence-durand.fr"}


class Horloge:
    def __init__(self):
        self.t = datetime(2026, 10, 2, 9, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.t

    def avancer(self, **duree):
        self.t += timedelta(**duree)


@pytest.fixture
def serveur():
    return FauxServeur()


@pytest.fixture
def horloge():
    return Horloge()


def nouvelle(dossier, serveur, horloge, machine="00000000000000a1"):
    return lic.Licence(dossier, transport=serveur, maintenant=horloge, serveur=SERVEUR, machine=machine)


@pytest.fixture
def licence(tmp_path, serveur, horloge):
    return nouvelle(tmp_path, serveur, horloge)


# --- Module ----------------------------------------------------------------------------------------


def test_sans_licence(licence):
    etat = licence.etat()
    assert etat.statut == lic.ABSENTE and not etat.utilisable and "page « Merci »" in etat.message


def test_activation(licence, serveur):
    etat = licence.activer(f"  {CLE[:10]}\n{CLE[10:]}  ")  # espaces et retour à la ligne collés par erreur
    assert etat.utilisable and etat.client == "Agence Durand" and etat.cle_masquee == "CDS-…4E5F"
    action, donnees = serveur.appels[0]
    assert action == "activer" and donnees == {"cle": CLE, "produit": "chasseur-de-sites", "machine": "00000000000000a1"}
    assert json.loads(licence.chemin.read_text(encoding="utf-8"))["signature"]


@pytest.mark.parametrize("cle, attendu", [("CDS-inconnue-000000000000", "Clé de licence inconnue"), ("court", "clé de licence complète")])
def test_cle_refusee(licence, cle, attendu):
    with pytest.raises(lic.ErreurLicence, match=attendu):
        licence.activer(cle)
    assert licence.etat().statut == lic.ABSENTE


def test_cle_d_un_autre_logiciel(licence, serveur):
    serveur.cles[CLE]["produit"] = "bridgetoleads"
    with pytest.raises(lic.ErreurLicence, match="autre logiciel"):
        licence.activer(CLE)


def test_limite_d_ordinateurs(tmp_path, serveur, horloge):
    serveur.limite = 1
    nouvelle(tmp_path / "a", serveur, horloge, "00000000000000a1").activer(CLE)
    with pytest.raises(lic.ErreurLicence, match="nombre maximal d'ordinateurs"):
        nouvelle(tmp_path / "b", serveur, horloge, "00000000000000b2").activer(CLE)


def test_remboursement_bloque_a_la_verification_suivante(licence, serveur, horloge):
    licence.activer(CLE)
    serveur.cles[CLE]["rembourse"] = True  # remboursement dans Stripe
    assert licence.etat().utilisable  # rien ne change tant qu'on n'a pas revérifié
    horloge.avancer(hours=25)
    assert licence.verification_due()
    etat = licence.verifier()
    assert etat.statut == lic.DESACTIVEE and not etat.utilisable and "remboursé" in etat.message
    serveur.hors_ligne = True  # se couper d'Internet ne débloque pas
    assert licence.verifier().statut == lic.DESACTIVEE
    serveur.hors_ligne = False
    with pytest.raises(lic.ErreurLicence, match="désactivée"):
        licence.activer(CLE)  # ni réactiver la même clé


def test_hors_ligne_tolere_puis_bloque(licence, serveur, horloge):
    licence.activer(CLE)
    serveur.hors_ligne = True
    horloge.avancer(days=10)
    etat = licence.verifier()
    assert etat.utilisable and etat.jours_restants == 4 and etat.hors_ligne_depuis_longtemps
    horloge.avancer(days=5)
    etat = licence.verifier()
    assert etat.statut == lic.A_VERIFIER and not etat.utilisable and "14 jours" in etat.message
    serveur.hors_ligne = False  # retour d'Internet : tout repart
    etat = licence.verifier()
    assert etat.utilisable and etat.jours_restants == lic.TOLERANCE_JOURS and not etat.hors_ligne_depuis_longtemps


def test_verification_reussie_repousse_l_echeance(licence, horloge):
    licence.activer(CLE)
    horloge.avancer(hours=23)
    assert not licence.verification_due()
    horloge.avancer(hours=2)
    assert licence.verification_due()
    licence.verifier()
    assert not licence.verification_due()


def test_horloge_reculee(licence, horloge):
    licence.activer(CLE)
    horloge.avancer(days=-3)
    assert licence.etat().statut == lic.A_VERIFIER and licence.verification_due()


def test_fichier_modifie_a_la_main(licence):
    licence.activer(CLE)
    donnees = json.loads(licence.chemin.read_text(encoding="utf-8"))
    donnees["verifie_le"] = "2099-01-01T00:00:00+00:00"  # tentative de repousser l'échéance
    licence.chemin.write_text(json.dumps(donnees), encoding="utf-8")
    etat = licence.etat()
    assert etat.statut == lic.ABSENTE and "modifié" in etat.message


def test_fichier_copie_sur_un_autre_ordinateur(licence, tmp_path, serveur, horloge):
    licence.activer(CLE)
    assert nouvelle(tmp_path, serveur, horloge, "00000000000000b2").etat().statut == lic.ABSENTE


def test_ordinateur_retire_cote_serveur(licence, serveur):
    licence.activer(CLE)
    serveur.cles[CLE]["machines"].clear()  # libérée depuis un autre ordinateur ou par le support
    etat = licence.verifier()
    assert etat.statut == lic.INVALIDE and "saisissez à nouveau" in etat.message


def test_liberer_puis_activer_ailleurs(tmp_path, serveur, horloge):
    serveur.limite = 1
    premier = nouvelle(tmp_path / "a", serveur, horloge, "00000000000000a1")
    premier.activer(CLE)
    premier.liberer()
    assert premier.etat().statut == lic.ABSENTE and not serveur.cles[CLE]["machines"]
    assert nouvelle(tmp_path / "b", serveur, horloge, "00000000000000b2").activer(CLE).utilisable


def test_activation_sans_internet(licence, serveur):
    serveur.hors_ligne = True
    with pytest.raises(lic.ErreurLicence, match="connexion à Internet"):
        licence.activer(CLE)


def test_identifiant_machine_anonyme_et_stable():
    m = lic.identifiant_machine()
    assert len(m) == 16 and int(m, 16) >= 0 and m == lic.identifiant_machine()


def test_mode_developpement(monkeypatch, tmp_path):
    monkeypatch.setenv(lic.VARIABLE_DEV, "1")
    assert lic.licence_par_defaut(tmp_path).etat().utilisable
    monkeypatch.setattr(lic.sys, "frozen", True, raising=False)  # jamais dans l'exécutable
    assert not lic.licence_par_defaut(tmp_path).etat().utilisable
    monkeypatch.delenv(lic.VARIABLE_DEV)
    monkeypatch.delattr(lic.sys, "frozen")
    assert not lic.licence_par_defaut(tmp_path).etat().utilisable


def test_transport_hors_ligne_et_serveur_non_configure():
    with pytest.raises(lic.HorsLigne):
        lic.transport_urllib("http://127.0.0.1:9/activer", {"cle": "x"}, timeout=2)
    with pytest.raises(lic.HorsLigne, match="non configuré"):
        lic.transport_urllib("/activer", {"cle": "x"})


def test_serveur_non_configure_message_clair(tmp_path):
    licence = lic.Licence(tmp_path, serveur="")
    with pytest.raises(lic.ErreurLicence, match="joindre le serveur de licences"):
        licence.activer(CLE)


# --- Interface web ----------------------------------------------------------------------------------


@pytest.fixture
def web_licence(stockage, licence):
    from fastapi.testclient import TestClient

    from chasseur.web.app import creer_app
    from conftest import RACINE

    app = creer_app(stockage, chemin_config=RACINE / "config.yaml", hotes=["testserver"], licence=licence)
    with TestClient(app, follow_redirects=False) as client:
        yield client


def test_web_sans_licence_tout_mene_a_l_ecran_licence(web_licence):
    for chemin in ("/", "/analyses", "/analyses/nouvelle", "/recherche", "/reglages"):
        r = web_licence.get(chemin, follow_redirects=True)
        assert r.url.path == "/licence" and "Activez Chasseur de sites" in r.text, chemin
    assert web_licence.post("/analyses/apercu").headers["location"] == "/licence"
    assert web_licence.post("/recherche", headers={"HX-Request": "true"}).headers["hx-redirect"] == "/licence"
    assert web_licence.get("/a-propos").status_code == 200  # toujours accessible
    assert web_licence.get("/static/style.css").status_code == 200


def test_web_activation(web_licence):
    r = web_licence.post("/licence", data={"cle": "CDS-mauvaise-cle-1234"})
    assert "Clé de licence inconnue" in web_licence.get(r.headers["location"]).text
    r = web_licence.post("/licence", data={"cle": CLE})
    page = web_licence.get(r.headers["location"]).text
    assert "Merci, Agence Durand ! Votre licence est activée" in page and "CDS-…4E5F" in page and CLE not in page
    assert web_licence.get("/analyses").status_code == 200
    assert 'href="/licence"' in web_licence.get("/analyses").text


def test_web_apres_remboursement_donnees_toujours_accessibles(web_licence, licence, serveur, stockage):
    from chasseur.db import depot
    from chasseur.modeles import Prospect

    licence.activer(CLE)
    with stockage.session() as s:
        scan = depot.creer_scan(s, "Salons", [Prospect(nom="Salon Léa", url="https://salon-lea.fr")])
        (p,) = depot.a_analyser(s, scan.id)
        prospect_id = p.id
    serveur.cles[CLE]["rembourse"] = True
    web_licence.post("/licence/verifier")
    page = web_licence.get("/licence").text
    assert "Licence inactive" in page and "remboursé" in page and "exportez vos résultats" in page
    for chemin in ("/analyses/nouvelle", "/recherche", f"/prospects/{prospect_id}/rapport.pdf"):
        assert web_licence.get(chemin).headers["location"] == "/licence", chemin
    assert "Salon Léa" in web_licence.get("/resultats").text
    assert web_licence.get("/export.xlsx").status_code == 200
    assert web_licence.get(f"/prospects/{prospect_id}").status_code == 200
    assert web_licence.post(f"/prospects/{prospect_id}/supprimer").status_code == 303
    assert "Salon Léa" not in web_licence.get("/resultats").text


def test_web_bandeau_hors_ligne(web_licence, licence, serveur, horloge):
    licence.activer(CLE)
    serveur.hors_ligne = True
    horloge.avancer(days=12)
    page = web_licence.get("/analyses").text
    assert "Licence non vérifiée depuis plusieurs jours" in page and "blocage dans 2 jours" in page


def test_web_liberer(web_licence, licence, serveur):
    licence.activer(CLE)
    r = web_licence.post("/licence/liberer")
    assert "Licence libérée" in web_licence.get(r.headers["location"]).text
    assert not serveur.cles[CLE]["machines"] and web_licence.get("/analyses").headers["location"] == "/licence"


def test_relances_planifiees_suspendues_sans_licence(stockage):
    from chasseur import planification
    from chasseur.db import depot
    from chasseur.modeles import Prospect
    from chasseur.web.app import entretenir

    class Gestionnaire:
        def en_cours(self, _):
            return False

        def lancer(self, scan_id):
            raise AssertionError("aucune relance ne doit partir sans licence")

    with stockage.session() as s:
        scan = depot.creer_scan(s, "Hebdo", [Prospect(nom="A", url="https://a.test")])
        planification.planifier(s, scan.id, True)
        scan.prochaine_execution = datetime(2020, 1, 1, tzinfo=timezone.utc)
        s.add(scan)
        s.commit()
    assert entretenir(stockage, Gestionnaire(), purge=False, licence_active=False) == (0, [])


# --- Ligne de commande ------------------------------------------------------------------------------


def test_cli_sans_licence(monkeypatch, tmp_path, capsys):
    from chasseur import cli

    monkeypatch.delenv(lic.VARIABLE_DEV)
    entree = tmp_path / "p.csv"
    entree.write_text("nom;url\nA;https://a.test\n", encoding="utf-8")
    assert cli.main(["scan", str(entree), "-q"]) == 3
    assert "Licence requise" in capsys.readouterr().err
    assert cli.main(["licence"]) == 3
    assert "Saisissez la clé" in capsys.readouterr().out


def test_cli_activer(monkeypatch, tmp_path, capsys, serveur):
    from chasseur import cli

    monkeypatch.delenv(lic.VARIABLE_DEV)
    monkeypatch.setattr(lic, "transport_urllib", serveur)
    monkeypatch.setattr(lic, "SERVEUR", SERVEUR)
    assert cli.main(["licence", "activer", CLE, "--donnees", str(tmp_path / "d")]) == 0
    assert "Licence active. (clé CDS-…4E5F)" in capsys.readouterr().out
    assert cli.main(["licence", "--donnees", str(tmp_path / "d")]) == 0
