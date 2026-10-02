"""Bout en bout : le vrai client Python face au vrai serveur de licences (serveur-licences/worker.js),
avec un faux Stripe en mémoire. Paiement → clé (page Merci) → activation → remboursement → blocage.

Demande Node.js (ignoré sinon)."""

from __future__ import annotations

import json
import shutil
import subprocess
import urllib.request
from pathlib import Path

import pytest

from chasseur import licence as lic

DOSSIER_SERVEUR = Path(__file__).resolve().parents[2] / "serveur-licences"

pytestmark = pytest.mark.skipif(shutil.which("node") is None or not DOSSIER_SERVEUR.is_dir(), reason="Node.js absent")


@pytest.fixture(scope="module")
def serveur_local():
    proc = subprocess.Popen(["node", str(DOSSIER_SERVEUR / "serveur-local.mjs")], stdout=subprocess.PIPE, text=True)
    ligne = proc.stdout.readline()
    assert ligne.startswith("PRET "), ligne
    yield f"http://127.0.0.1:{ligne.split()[1]}"
    proc.terminate()
    proc.wait(timeout=10)


def lire(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=10) as r:
        return json.loads(r.read())


def test_paiement_activation_remboursement(serveur_local, tmp_path):
    # 1. Paiement Stripe, puis la page « Merci » obtient la clé
    paiement = lire(f"{serveur_local}/_test/payer?produit=prod_ChasseurDeSites")
    cle = lire(f"{serveur_local}/cle?session_id={paiement['session']}")["cle"]
    assert cle.startswith("CDS-")

    # 2. Activation sur deux ordinateurs, refus du troisième
    pc1 = lic.Licence(tmp_path / "pc1", serveur=serveur_local, machine="00000000000000a1")
    etat = pc1.activer(cle)
    assert etat.utilisable and etat.client == "Agence Durand"
    lic.Licence(tmp_path / "pc2", serveur=serveur_local, machine="00000000000000b2").activer(cle)
    with pytest.raises(lic.ErreurLicence, match="nombre maximal"):
        lic.Licence(tmp_path / "pc3", serveur=serveur_local, machine="00000000000000c3").activer(cle)

    # 3. Une clé de BridgeToLeads n'ouvre pas Chasseur de sites
    autre = lire(f"{serveur_local}/_test/payer?produit=prod_BridgeToLeads")
    cle_btl = lire(f"{serveur_local}/cle?session_id={autre['session']}")["cle"]
    with pytest.raises(lic.ErreurLicence, match="autre logiciel"):
        lic.Licence(tmp_path / "pc4", serveur=serveur_local, machine="00000000000000d4").activer(cle_btl)

    # 4. Remboursement dans Stripe → bloqué à la vérification suivante
    assert pc1.verifier().utilisable
    lire(f"{serveur_local}/_test/rembourser?pi={paiement['pi']}")
    etat = pc1.verifier()
    assert etat.statut == lic.DESACTIVEE and not etat.utilisable


def test_liberer_un_ordinateur(serveur_local, tmp_path):
    paiement = lire(f"{serveur_local}/_test/payer?produit=prod_ChasseurDeSites")
    cle = lire(f"{serveur_local}/cle?session_id={paiement['session']}")["cle"]
    pcs = [lic.Licence(tmp_path / f"pc{i}", serveur=serveur_local, machine=f"{i:016x}") for i in range(1, 4)]
    pcs[0].activer(cle)
    pcs[1].activer(cle)
    pcs[0].liberer()
    assert pcs[2].activer(cle).utilisable
