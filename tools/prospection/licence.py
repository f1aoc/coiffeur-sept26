"""Licence : activation, vérification périodique, désactivation après remboursement (paiement Stripe).

Fonctionnement :
- après le paiement Stripe, la page « Merci » affiche au client sa clé de licence (serveur-licences/) ;
- « activer » enregistre cet ordinateur auprès du serveur de licences (2 ordinateurs par licence) ;
- le logiciel revérifie la clé au démarrage puis toutes les 24 h ; le serveur interroge Stripe : si le
  paiement a été remboursé ou contesté, il répond « désactivée » et le logiciel se bloque ;
- sans Internet, il reste utilisable TOLERANCE_JOURS jours après la dernière vérification réussie.

Ce module n'utilise que la bibliothèque standard : il peut être copié tel quel dans un autre logiciel
(changer NOM_LOGICIEL, PRODUIT, _SEL et la variable de développement).
Ce n'est pas inviolable (rien ne l'est côté client) : le but est d'empêcher « j'achète, je me fais
rembourser et je garde le logiciel ».
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import platform
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

# --- À MODIFIER -------------------------------------------------------------------------------------
# Adresse de VOTRE serveur de licences (Cloudflare Worker, voir serveur-licences/README.md),
# par exemple "https://licences.votre-nom.workers.dev".
SERVEUR = "https://licences.patrick-tabountchikoff.workers.dev"
# Lien de paiement Stripe du logiciel (affiché sur l'écran de licence).
LIEN_ACHAT = "https://buy.stripe.com/test_28EaEYeh51Ia5Sz74JcfK01"
# -----------------------------------------------------------------------------------------------------

NOM_LOGICIEL = "BridgeToLeads"
PRODUIT = "bridgetoleads"  # même code que dans la variable PRODUITS du serveur
VARIABLE_DEV = "BRIDGETOLEADS_SANS_LICENCE"
TOLERANCE_JOURS = 14  # utilisable hors ligne pendant ce délai après la dernière vérification réussie
INTERVALLE = timedelta(hours=24)  # revérification en ligne
FICHIER = "licence.json"
_SEL = b"bridgetoleads/licence/v2"

ACTIVE, ABSENTE, DESACTIVEE, INVALIDE, A_VERIFIER = "active", "absente", "desactivee", "invalide", "a_verifier"

MESSAGES_BLOCAGE = {
    DESACTIVEE: "Cette licence a été désactivée (paiement remboursé ou contesté). Les recherches sont bloquées ; "
                "les résultats déjà affichés peuvent encore être exportés.",
}


class ErreurLicence(Exception):
    """Message destiné à l'utilisateur, en français."""


class HorsLigne(Exception):
    """Serveur de licences injoignable (pas d'Internet, pare-feu, panne)."""


Transport = Callable[[str, dict], tuple[int, dict]]


def transport_urllib(url: str, donnees: dict, timeout: float = 15.0) -> tuple[int, dict]:
    """POST application/x-www-form-urlencoded → (code HTTP, JSON). Respecte les proxys du système."""
    if not url.startswith("https://") and not url.startswith("http://127.0.0.1"):
        raise HorsLigne("serveur de licences non configuré")
    corps = urllib.parse.urlencode(donnees).encode()
    requete = urllib.request.Request(url, data=corps, method="POST", headers={
        "Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": f"{NOM_LOGICIEL.replace(' ', '')}-licence/2.0",
    })
    try:
        with urllib.request.urlopen(requete, timeout=timeout) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        if e.code >= 500:  # serveur ou Stripe en panne : comme hors ligne (délai de tolérance)
            raise HorsLigne(f"serveur de licences indisponible (HTTP {e.code})") from e
        try:
            return e.code, json.loads(e.read() or b"{}")
        except ValueError:
            return e.code, {}
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise HorsLigne(str(getattr(e, "reason", e))) from e


def identifiant_machine() -> str:
    """Empreinte stable et anonyme de l'ordinateur (16 caractères hexadécimaux, aucune donnée personnelle)."""
    brut = f"{uuid.getnode()}|{platform.node()}|{platform.system()}"
    return hashlib.sha256(brut.encode()).hexdigest()[:16]


def masquer(cle: str) -> str:
    return f"{cle[:4]}…{cle[-4:]}" if len(cle) > 10 else "…"


@dataclass(frozen=True)
class Etat:
    statut: str
    message: str
    cle: str = ""
    client: str = ""
    email: str = ""
    derniere_verification: datetime | None = None
    jours_restants: int | None = None  # hors ligne : jours avant blocage

    @property
    def utilisable(self) -> bool:
        return self.statut == ACTIVE

    @property
    def cle_masquee(self) -> str:
        return masquer(self.cle) if self.cle else ""

    @property
    def hors_ligne_depuis_longtemps(self) -> bool:
        return self.utilisable and self.jours_restants is not None and self.jours_restants <= TOLERANCE_JOURS - 3


def _maintenant() -> datetime:
    return datetime.now(timezone.utc)


def licence_desactivee_pour_developpement() -> bool:
    """Lancé depuis le code source (pas l'exécutable) avec la variable de développement à 1 : tests."""
    return not getattr(sys, "frozen", False) and os.environ.get(VARIABLE_DEV) == "1"


class Licence:
    def __init__(self, dossier: str | Path, transport: Transport | None = None,
                 maintenant: Callable[[], datetime] = _maintenant, serveur: str | None = None,
                 produit: str | None = None, machine: str | None = None):
        self.chemin = Path(dossier) / FICHIER
        self.transport = transport or transport_urllib
        self.maintenant = maintenant
        self.serveur = (SERVEUR if serveur is None else serveur).rstrip("/")
        self.produit = produit or PRODUIT
        self.machine = machine or identifiant_machine()

    # --- fichier local signé ------------------------------------------------------------------------

    def _signature(self, donnees: dict) -> str:
        cle = hashlib.sha256(_SEL + self.machine.encode()).digest()
        texte = json.dumps({k: v for k, v in donnees.items() if k != "signature"}, sort_keys=True)
        return hmac.new(cle, texte.encode(), hashlib.sha256).hexdigest()

    def _lire(self) -> dict | None:
        try:
            donnees = json.loads(self.chemin.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if not isinstance(donnees, dict) or not hmac.compare_digest(str(donnees.get("signature", "")), self._signature(donnees)):
            return {"altere": True}  # fichier modifié à la main, ou copié depuis un autre ordinateur
        return donnees

    def _ecrire(self, donnees: dict) -> None:
        donnees = {**donnees, "signature": ""}
        donnees["signature"] = self._signature(donnees)
        self.chemin.parent.mkdir(parents=True, exist_ok=True)
        temporaire = self.chemin.with_suffix(".tmp")
        temporaire.write_text(json.dumps(donnees, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporaire, self.chemin)

    # --- état ---------------------------------------------------------------------------------------

    def etat(self) -> Etat:
        """État d'après le fichier local, sans appel réseau."""
        d = self._lire()
        if d is None:
            return Etat(ABSENTE, "Saisissez la clé de licence affichée après votre achat (page « Merci »).")
        if d.get("altere"):
            return Etat(ABSENTE, "Le fichier de licence a été modifié ou vient d'un autre ordinateur : "
                                 "saisissez à nouveau votre clé de licence.")
        commun = dict(cle=d.get("cle", ""), client=d.get("client", ""), email=d.get("email", ""))
        statut = d.get("statut", INVALIDE)
        verifie = datetime.fromisoformat(d["verifie_le"]) if d.get("verifie_le") else None
        if statut in MESSAGES_BLOCAGE:
            return Etat(statut, MESSAGES_BLOCAGE[statut], derniere_verification=verifie, **commun)
        if statut != ACTIVE or verifie is None:
            return Etat(INVALIDE, d.get("message") or "Cette clé de licence n'est pas valable.", **commun)
        maintenant = self.maintenant()
        if verifie - maintenant > timedelta(days=1):  # horloge de l'ordinateur reculée
            return Etat(A_VERIFIER, "La date de l'ordinateur semble incorrecte : connectez-vous à Internet "
                                    "pour vérifier votre licence.", derniere_verification=verifie, **commun)
        restants = TOLERANCE_JOURS - (maintenant - verifie).days
        if restants <= 0:
            return Etat(A_VERIFIER, f"Votre licence n'a pas pu être vérifiée depuis plus de {TOLERANCE_JOURS} jours : "
                                    "connectez-vous à Internet puis cliquez sur « Vérifier maintenant ».",
                        derniere_verification=verifie, **commun)
        return Etat(ACTIVE, "Licence active.", derniere_verification=verifie, jours_restants=restants, **commun)

    def verification_due(self) -> bool:
        d = self._lire()
        if not d or d.get("altere") or d.get("statut") != ACTIVE:
            return False
        verifie = datetime.fromisoformat(d["verifie_le"]) if d.get("verifie_le") else None
        return verifie is None or self.maintenant() - verifie >= INTERVALLE or verifie > self.maintenant()

    # --- serveur de licences --------------------------------------------------------------------------

    def _appel(self, action: str, cle: str) -> tuple[int, dict]:
        return self.transport(f"{self.serveur}/{action}", {"cle": cle, "produit": self.produit, "machine": self.machine})

    def activer(self, cle: str) -> Etat:
        cle = "".join(cle.split())  # espaces et retours à la ligne collés par erreur
        if len(cle) < 12:
            raise ErreurLicence("Collez la clé de licence complète, telle qu'elle est affichée après votre achat.")
        try:
            code, r = self._appel("activer", cle)
        except HorsLigne as e:
            raise ErreurLicence("Impossible de joindre le serveur de licences : vérifiez votre connexion à Internet, "
                                "puis réessayez.") from e
        if not r.get("valide"):
            statut = r.get("statut")
            if statut == "limite":
                raise ErreurLicence("Cette clé est déjà utilisée sur le nombre maximal d'ordinateurs. Libérez-la sur "
                                    "l'ancien ordinateur (bouton « Licence » → « Libérer »), ou contactez le support.")
            if statut == "desactivee":
                raise ErreurLicence("Cette licence a été désactivée (paiement remboursé ou contesté).")
            if statut == "autre_produit":
                raise ErreurLicence(f"Cette clé de licence est celle d'un autre logiciel, pas de {NOM_LOGICIEL}.")
            raise ErreurLicence("Clé de licence inconnue : vérifiez qu'elle est copiée en entier.")
        self._ecrire({"cle": cle, "statut": ACTIVE, "verifie_le": self.maintenant().isoformat(),
                      "client": r.get("nom", ""), "email": r.get("email", "")})
        return self.etat()

    def verifier(self) -> Etat:
        """Revérifie en ligne. Hors ligne : l'état local reste valable (délai de tolérance)."""
        d = self._lire()
        if not d or d.get("altere") or not d.get("cle"):
            return self.etat()
        try:
            code, r = self._appel("verifier", d["cle"])
        except HorsLigne:
            return self.etat()
        if r.get("valide"):
            self._ecrire({**d, "statut": ACTIVE, "verifie_le": self.maintenant().isoformat(), "message": "",
                          "client": r.get("nom") or d.get("client", ""), "email": r.get("email") or d.get("email", "")})
        elif r.get("statut") == "desactivee":
            self._ecrire({**d, "statut": DESACTIVEE})
        elif r.get("statut") in ("machine_inconnue", "inconnue", "autre_produit", "machine_invalide"):
            self._ecrire({**d, "statut": INVALIDE, "message": "Cette licence n'est plus reconnue pour cet ordinateur : "
                                                              "saisissez à nouveau votre clé."})
        return self.etat()  # réponse inattendue : on ne change rien

    def liberer(self) -> None:
        """Retire cet ordinateur de la licence (pour l'activer ailleurs) et oublie la clé."""
        d = self._lire()
        if d and not d.get("altere") and d.get("cle"):
            try:
                self._appel("liberer", d["cle"])
            except HorsLigne as e:
                raise ErreurLicence("Impossible de joindre le serveur de licences : connectez-vous à Internet pour "
                                    "libérer la licence.") from e
        self.chemin.unlink(missing_ok=True)


class LicenceLibre(Licence):
    """Toujours active : tests et développement (jamais dans l'exécutable)."""

    def __init__(self):
        pass

    def etat(self) -> Etat:
        return Etat(ACTIVE, "Licence non contrôlée (mode développement).")

    def verification_due(self) -> bool:
        return False

    def verifier(self) -> Etat:
        return self.etat()


def licence_par_defaut(dossier: str | Path) -> Licence:
    return LicenceLibre() if licence_desactivee_pour_developpement() else Licence(dossier)
