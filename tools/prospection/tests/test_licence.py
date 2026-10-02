"""Licence Lemon Squeezy de BridgeToLeads : activation, vérifications, remboursement, hors ligne.

Les réponses imitent l'API License de Lemon Squeezy (activate / validate / deactivate) ; aucun appel réseau.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import licence as lic  # noqa: E402

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
        return {"store_id": STORE, "product_id": self.produit.get(cle, PRODUIT), "product_name": "BridgeToLeads",
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
    assert lemon.appels[0][0] == "activate" and lemon.appels[0][1]["instance_name"].startswith("BridgeToLeads – ")
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
    monkeypatch.setenv("BRIDGETOLEADS_SANS_LICENCE", "1")
    assert lic.licence_par_defaut(tmp_path).etat().utilisable
    monkeypatch.setattr(lic.sys, "frozen", True, raising=False)  # jamais dans l'exécutable
    assert not lic.licence_par_defaut(tmp_path).etat().utilisable
    monkeypatch.delenv("BRIDGETOLEADS_SANS_LICENCE")
    monkeypatch.delattr(lic.sys, "frozen")
    assert not lic.licence_par_defaut(tmp_path).etat().utilisable


def test_transport_urllib_hors_ligne():
    with pytest.raises(lic.HorsLigne):
        lic.transport_urllib("http://127.0.0.1:9/v1/licenses/validate", {"license_key": "x"}, timeout=2)
