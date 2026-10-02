"""Licence Lemon Squeezy : activation, vérifications, remboursement, hors ligne, écrans et ligne de commande.

Les réponses imitent l'API License de Lemon Squeezy (activate / validate / deactivate) ; aucun appel réseau.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from chasseur import licence as lic

STORE, PRODUIT = 1234, 555
CLE = "38b1460a-5104-4067-a91d-77b872934d51"


class FauxLemon:
    """Imitation de l'API License : statut par clé, limite d'activations, panne réseau simulable."""

    def __init__(self):
        self.cles = {CLE: "active"}
        self.produit = {CLE: PRODUIT}
        self.instances: dict[str, str] = {}
        self.limite = 2
        self.hors_ligne = False
        self.appels: list[tuple[str, dict]] = []

    def _cle(self, cle):
        statut = self.cles[cle]
        return {"id": 1, "status": statut, "key": cle, "activation_limit": self.limite,
                "activation_usage": sum(1 for c in self.instances.values() if c == cle)}

    def _meta(self, cle):
        return {"store_id": STORE, "product_id": self.produit.get(cle, PRODUIT), "product_name": "Chasseur de sites",
                "customer_name": "Agence Durand", "customer_email": "contact@agence-durand.fr"}

    def __call__(self, url, donnees):
        self.appels.append((url.rsplit("/", 1)[1], donnees))
        if self.hors_ligne:
            raise lic.HorsLigne("pas de réseau")
        cle = donnees["license_key"]
        action = url.rsplit("/", 1)[1]
        if cle not in self.cles:
            return 404, {"error": "license_key not found.", "valid": False, "activated": False, "license_key": None}
        if action == "activate":
            if self.cles[cle] != "active" and self.cles[cle] != "inactive":
                return 400, {"activated": False, "error": "This license key is disabled.", "license_key": self._cle(cle)}
            if self._cle(cle)["activation_usage"] >= self.limite:
                return 400, {"activated": False, "error": "This license key has reached the activation limit.",
                             "license_key": self._cle(cle)}
            instance = f"inst-{len(self.instances) + 1}"
            self.instances[instance] = cle
            return 200, {"activated": True, "error": None, "license_key": self._cle(cle),
                         "instance": {"id": instance, "name": donnees["instance_name"]}, "meta": self._meta(cle)}
        if action == "validate":
            instance = donnees.get("instance_id")
            if instance and self.instances.get(instance) != cle:
                return 404, {"valid": False, "error": "license_key instance not found.", "license_key": self._cle(cle)}
            valide = self.cles[cle] == "active"
            return 200, {"valid": valide, "error": None if valide else f"This license key is {self.cles[cle]}.",
                         "license_key": self._cle(cle), "meta": self._meta(cle)}
        if action == "deactivate":
            self.instances.pop(donnees["instance_id"], None)
            return 200, {"deactivated": True, "error": None, "license_key": self._cle(cle), "meta": self._meta(cle)}
        raise AssertionError(action)


class Horloge:
    def __init__(self):
        self.t = datetime(2026, 10, 2, 9, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.t

    def avancer(self, **duree):
        self.t += timedelta(**duree)


@pytest.fixture
def lemon():
    return FauxLemon()


@pytest.fixture
def horloge():
    return Horloge()


@pytest.fixture
def licence(tmp_path, lemon, horloge):
    return lic.Licence(tmp_path, transport=lemon, maintenant=horloge, store_id=STORE, produits=(PRODUIT,), machine="pc-1")


# --- Module ----------------------------------------------------------------------------------------


def test_sans_licence(licence):
    etat = licence.etat()
    assert etat.statut == lic.ABSENTE and not etat.utilisable and "clé de licence" in etat.message


def test_activation(licence, lemon):
    etat = licence.activer(f"  {CLE}  ")
    assert etat.utilisable and etat.client == "Agence Durand" and etat.cle_masquee == "38b1…4d51"
    assert lemon.appels[0][0] == "activate" and lemon.appels[0][1]["instance_name"].startswith("Chasseur de sites – ")
    contenu = json.loads(licence.chemin.read_text(encoding="utf-8"))
    assert contenu["instance"] == "inst-1" and contenu["signature"]


@pytest.mark.parametrize("cle, attendu", [("inconnue-123456", "Clé de licence inconnue"), ("court", "clé de licence complète")])
def test_cle_refusee(licence, cle, attendu):
    with pytest.raises(lic.ErreurLicence, match=attendu):
        licence.activer(cle)
    assert licence.etat().statut == lic.ABSENTE


def test_cle_d_un_autre_produit(licence, lemon):
    lemon.produit[CLE] = 999  # clé achetée pour un autre logiciel de la boutique
    with pytest.raises(lic.ErreurLicence, match="autre logiciel"):
        licence.activer(CLE)


def test_cle_d_une_autre_boutique(tmp_path, lemon, horloge):
    autre = lic.Licence(tmp_path, transport=lemon, maintenant=horloge, store_id=42, produits=(), machine="pc-1")
    with pytest.raises(lic.ErreurLicence, match="ne correspond pas"):
        autre.activer(CLE)


def test_limite_d_activations(tmp_path, lemon, horloge):
    lemon.limite = 1
    lic.Licence(tmp_path / "a", transport=lemon, maintenant=horloge, machine="pc-1").activer(CLE)
    with pytest.raises(lic.ErreurLicence, match="nombre maximal d'ordinateurs"):
        lic.Licence(tmp_path / "b", transport=lemon, maintenant=horloge, machine="pc-2").activer(CLE)


def test_remboursement_bloque_a_la_verification_suivante(licence, lemon, horloge):
    licence.activer(CLE)
    lemon.cles[CLE] = "disabled"  # remboursement dans Lemon Squeezy
    assert licence.etat().utilisable  # rien ne change tant qu'on n'a pas revérifié
    horloge.avancer(hours=25)
    assert licence.verification_due()
    etat = licence.verifier()
    assert etat.statut == lic.DESACTIVEE and not etat.utilisable and "remboursement" in etat.message
    lemon.hors_ligne = True  # se couper d'Internet ne débloque pas
    assert licence.verifier().statut == lic.DESACTIVEE
    with pytest.raises(lic.ErreurLicence, match="désactivée"):
        lemon.hors_ligne = False
        licence.activer(CLE)  # ni réactiver la même clé


def test_licence_expiree(licence, lemon):
    licence.activer(CLE)
    lemon.cles[CLE] = "expired"
    assert licence.verifier().statut == lic.EXPIREE


def test_hors_ligne_tolere_puis_bloque(licence, lemon, horloge):
    licence.activer(CLE)
    lemon.hors_ligne = True
    horloge.avancer(days=10)
    etat = licence.verifier()
    assert etat.utilisable and etat.jours_restants == 4 and etat.hors_ligne_depuis_longtemps
    horloge.avancer(days=5)
    etat = licence.verifier()
    assert etat.statut == lic.A_VERIFIER and not etat.utilisable and "14 jours" in etat.message
    lemon.hors_ligne = False  # retour d'Internet : tout repart
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


def test_fichier_copie_sur_un_autre_ordinateur(licence, tmp_path, lemon, horloge):
    licence.activer(CLE)
    ailleurs = lic.Licence(tmp_path, transport=lemon, maintenant=horloge, machine="pc-2")
    assert ailleurs.etat().statut == lic.ABSENTE


def test_instance_supprimee_dans_lemon_squeezy(licence, lemon):
    licence.activer(CLE)
    lemon.instances.clear()  # vous avez désactivé cet ordinateur depuis le tableau de bord
    etat = licence.verifier()
    assert etat.statut == lic.INVALIDE and "saisissez à nouveau" in etat.message


def test_liberer_puis_activer_ailleurs(tmp_path, lemon, horloge):
    lemon.limite = 1
    premier = lic.Licence(tmp_path / "a", transport=lemon, maintenant=horloge, machine="pc-1")
    premier.activer(CLE)
    premier.liberer()
    assert premier.etat().statut == lic.ABSENTE and not lemon.instances
    assert lic.Licence(tmp_path / "b", transport=lemon, maintenant=horloge, machine="pc-2").activer(CLE).utilisable


def test_activation_sans_internet(licence, lemon):
    lemon.hors_ligne = True
    with pytest.raises(lic.ErreurLicence, match="connexion à Internet"):
        licence.activer(CLE)


def test_mode_developpement(monkeypatch, tmp_path):
    monkeypatch.setenv("CHASSEUR_SANS_LICENCE", "1")
    assert lic.licence_par_defaut(tmp_path).etat().utilisable
    monkeypatch.setattr(lic.sys, "frozen", True, raising=False)  # jamais dans l'exécutable
    assert not lic.licence_par_defaut(tmp_path).etat().utilisable
    monkeypatch.delenv("CHASSEUR_SANS_LICENCE")
    monkeypatch.delattr(lic.sys, "frozen")
    assert not lic.licence_par_defaut(tmp_path).etat().utilisable


def test_transport_urllib_hors_ligne():
    with pytest.raises(lic.HorsLigne):
        lic.transport_urllib("http://127.0.0.1:9/v1/licenses/validate", {"license_key": "x"}, timeout=2)


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


def test_web_activation(web_licence, lemon):
    r = web_licence.post("/licence", data={"cle": "mauvaise-cle-123"})
    assert "Clé de licence inconnue" in web_licence.get(r.headers["location"]).text
    r = web_licence.post("/licence", data={"cle": CLE})
    page = web_licence.get(r.headers["location"]).text
    assert "Merci, Agence Durand ! Votre licence est activée" in page and "38b1…4d51" in page and CLE not in page
    assert web_licence.get("/analyses").status_code == 200
    assert 'href="/licence"' in web_licence.get("/analyses").text


def test_web_apres_remboursement_donnees_toujours_accessibles(web_licence, licence, lemon, horloge, stockage):
    from chasseur.db import depot
    from chasseur.modeles import Prospect

    licence.activer(CLE)
    with stockage.session() as s:
        scan = depot.creer_scan(s, "Salons", [Prospect(nom="Salon Léa", url="https://salon-lea.fr")])
        (p,) = depot.a_analyser(s, scan.id)
        prospect_id = p.id
    lemon.cles[CLE] = "disabled"
    web_licence.post("/licence/verifier")
    page = web_licence.get("/licence").text
    assert "Licence inactive" in page and "remboursement" in page and "exportez vos résultats" in page
    # Bloqué : nouvelles analyses, recherche, rapports PDF
    for chemin in ("/analyses/nouvelle", "/recherche", f"/prospects/{prospect_id}/rapport.pdf"):
        assert web_licence.get(chemin).headers["location"] == "/licence", chemin
    # Toujours possible : consulter, exporter, supprimer
    assert "Salon Léa" in web_licence.get("/resultats").text
    assert web_licence.get("/export.xlsx").status_code == 200
    assert web_licence.get(f"/prospects/{prospect_id}").status_code == 200
    assert web_licence.post(f"/prospects/{prospect_id}/supprimer").status_code == 303
    assert "Salon Léa" not in web_licence.get("/resultats").text


def test_web_bandeau_hors_ligne(web_licence, licence, lemon, horloge):
    licence.activer(CLE)
    lemon.hors_ligne = True
    horloge.avancer(days=12)
    page = web_licence.get("/analyses").text
    assert "Licence non vérifiée depuis plusieurs jours" in page and "blocage dans 2 jours" in page


def test_web_liberer(web_licence, licence, lemon):
    licence.activer(CLE)
    r = web_licence.post("/licence/liberer")
    assert "Licence libérée" in web_licence.get(r.headers["location"]).text
    assert not lemon.instances and web_licence.get("/analyses").headers["location"] == "/licence"


def test_relances_planifiees_suspendues_sans_licence(stockage):
    from chasseur.web.app import entretenir

    class Gestionnaire:
        def en_cours(self, _):
            return False

        def lancer(self, scan_id):
            raise AssertionError("aucune relance ne doit partir sans licence")

    from chasseur import planification
    from chasseur.db import depot
    from chasseur.modeles import Prospect

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

    monkeypatch.delenv("CHASSEUR_SANS_LICENCE")
    entree = tmp_path / "p.csv"
    entree.write_text("nom;url\nA;https://a.test\n", encoding="utf-8")
    assert cli.main(["scan", str(entree), "-q"]) == 3
    assert "Licence requise" in capsys.readouterr().err
    assert cli.main(["licence"]) == 3
    assert "Saisissez la clé" in capsys.readouterr().out


def test_cli_activer(monkeypatch, tmp_path, capsys, lemon):
    from chasseur import cli

    monkeypatch.delenv("CHASSEUR_SANS_LICENCE")
    monkeypatch.setattr(lic, "transport_urllib", lemon)
    assert cli.main(["licence", "activer", CLE, "--donnees", str(tmp_path / "d")]) == 0
    assert "Licence active. (clé 38b1…4d51)" in capsys.readouterr().out
    assert cli.main(["licence", "--donnees", str(tmp_path / "d")]) == 0
