"""Licence BridgeToLeads (paiement Stripe + serveur de licences) : activation, vérifications, remboursement,
hors ligne. Le serveur de licences est simulé (même contrat que serveur-licences/worker.js)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import licence as lic  # noqa: E402

SERVEUR = "https://licences.test"
CLE = "BTL-3Test000001AbCdEf-0A1B2C3D4E5F"


class FauxServeur:
    """Imite serveur-licences/worker.js : statut par clé, limite d'ordinateurs, panne réseau simulable."""

    def __init__(self):
        self.cles = {CLE: {"produit": "bridgetoleads", "rembourse": False, "machines": []}}
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
    assert etat.utilisable and etat.client == "Agence Durand" and etat.cle_masquee == "BTL-…4E5F"
    action, donnees = serveur.appels[0]
    assert action == "activer" and donnees == {"cle": CLE, "produit": "bridgetoleads", "machine": "00000000000000a1"}
    assert json.loads(licence.chemin.read_text(encoding="utf-8"))["signature"]


@pytest.mark.parametrize("cle, attendu", [("BTL-inconnue-000000000000", "Clé de licence inconnue"), ("court", "clé de licence complète")])
def test_cle_refusee(licence, cle, attendu):
    with pytest.raises(lic.ErreurLicence, match=attendu):
        licence.activer(cle)
    assert licence.etat().statut == lic.ABSENTE


def test_cle_d_un_autre_logiciel(licence, serveur):
    serveur.cles[CLE]["produit"] = "chasseur-de-sites"
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
