"""Licence Lemon Squeezy : activation, vérification périodique, désactivation après remboursement.

Fonctionnement :
- à l'achat, Lemon Squeezy envoie au client une clé de licence ;
- « activer » enregistre cet ordinateur auprès de Lemon Squeezy (API License, sans clé secrète) ;
- l'application revérifie la clé au démarrage puis toutes les 24 h ; si Lemon Squeezy répond que la clé
  est désactivée (remboursement), expirée ou inconnue, l'application se bloque ;
- sans Internet, elle reste utilisable TOLERANCE_JOURS jours après la dernière vérification réussie.

Ce module n'utilise que la bibliothèque standard : il peut être copié tel quel dans un autre logiciel.
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

# --- À MODIFIER : identifiants Lemon Squeezy de VOTRE boutique et de VOTRE produit -------------------
# Ils empêchent qu'une clé achetée pour un autre produit (ou dans une autre boutique) ouvre ce logiciel.
# Où les trouver : tableau de bord Lemon Squeezy → Settings → Stores (ID de la boutique) ;
# Products → votre produit → l'ID figure dans l'adresse de la page. 0 = pas de contrôle (à éviter).
STORE_ID = 0
PRODUITS: tuple[int, ...] = ()
# Lien d'achat affiché sur l'écran de licence (lien de paiement Lemon Squeezy de votre produit).
LIEN_ACHAT = ""
# -----------------------------------------------------------------------------------------------------

NOM_LOGICIEL = "Chasseur de sites"
API = "https://api.lemonsqueezy.com/v1/licenses"
TOLERANCE_JOURS = 14  # utilisable hors ligne pendant ce délai après la dernière vérification réussie
INTERVALLE = timedelta(hours=24)  # revérification en ligne
FICHIER = "licence.json"
_SEL = b"chasseur-de-sites/licence/v1"

ACTIVE, ABSENTE, DESACTIVEE, EXPIREE, INVALIDE, A_VERIFIER = (
    "active", "absente", "desactivee", "expiree", "invalide", "a_verifier",
)


class ErreurLicence(Exception):
    """Message destiné à l'utilisateur, en français."""


class HorsLigne(Exception):
    """Lemon Squeezy injoignable (pas d'Internet, pare-feu…)."""


Transport = Callable[[str, dict], tuple[int, dict]]


def transport_urllib(url: str, donnees: dict, timeout: float = 15.0) -> tuple[int, dict]:
    """POST application/x-www-form-urlencoded → (code HTTP, JSON). Respecte les proxys du système."""
    corps = urllib.parse.urlencode(donnees).encode()
    requete = urllib.request.Request(url, data=corps, method="POST", headers={
        "Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": f"{NOM_LOGICIEL.replace(' ', '')}-licence/1.0",
    })
    try:
        with urllib.request.urlopen(requete, timeout=timeout) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:  # 400 / 404 / 422 : réponse JSON avec « error »
        try:
            return e.code, json.loads(e.read() or b"{}")
        except ValueError:
            if e.code >= 500:
                raise HorsLigne(f"Lemon Squeezy indisponible (HTTP {e.code})") from e
            return e.code, {}
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise HorsLigne(str(getattr(e, "reason", e))) from e


def identifiant_machine() -> str:
    """Empreinte stable et anonyme de l'ordinateur (aucune donnée personnelle envoyée)."""
    brut = f"{uuid.getnode()}|{platform.node()}|{platform.system()}"
    return hashlib.sha256(brut.encode()).hexdigest()[:32]


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
    """Lancé depuis le code source (pas l'exécutable) avec CHASSEUR_SANS_LICENCE=1 : tests et développement."""
    return not getattr(sys, "frozen", False) and os.environ.get("CHASSEUR_SANS_LICENCE") == "1"


class Licence:
    def __init__(self, dossier: str | Path, transport: Transport | None = None,
                 maintenant: Callable[[], datetime] = _maintenant, store_id: int | None = None,
                 produits: tuple[int, ...] | None = None, machine: str | None = None):
        self.chemin = Path(dossier) / FICHIER
        self.transport = transport or transport_urllib
        self.maintenant = maintenant
        self.store_id = STORE_ID if store_id is None else store_id
        self.produits = PRODUITS if produits is None else produits
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
            return Etat(ABSENTE, "Saisissez la clé de licence reçue par e-mail après votre achat.")
        if d.get("altere"):
            return Etat(ABSENTE, "Le fichier de licence a été modifié ou vient d'un autre ordinateur : "
                                 "saisissez à nouveau votre clé de licence.")
        commun = dict(cle=d.get("cle", ""), client=d.get("client", ""), email=d.get("email", ""))
        statut = d.get("statut", INVALIDE)
        verifie = datetime.fromisoformat(d["verifie_le"]) if d.get("verifie_le") else None
        if statut == DESACTIVEE:
            return Etat(DESACTIVEE, "Cette licence a été désactivée (par exemple après un remboursement). "
                                    "Les analyses sont bloquées ; vous pouvez encore exporter ou supprimer vos données.",
                        derniere_verification=verifie, **commun)
        if statut == EXPIREE:
            return Etat(EXPIREE, "Cette licence a expiré.", derniere_verification=verifie, **commun)
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
        if not d or d.get("altere") or d.get("statut") not in (ACTIVE,):
            return False
        verifie = datetime.fromisoformat(d["verifie_le"]) if d.get("verifie_le") else None
        return verifie is None or self.maintenant() - verifie >= INTERVALLE or verifie > self.maintenant()

    # --- appels Lemon Squeezy -------------------------------------------------------------------------

    def _controler_produit(self, reponse: dict) -> None:
        meta = reponse.get("meta") or {}
        if self.store_id and meta.get("store_id") != self.store_id:
            raise ErreurLicence(f"Cette clé de licence ne correspond pas à {NOM_LOGICIEL}.")
        if self.produits and meta.get("product_id") not in self.produits:
            raise ErreurLicence(f"Cette clé de licence est celle d'un autre logiciel, pas de {NOM_LOGICIEL}.")

    @staticmethod
    def _statut_lemon(reponse: dict) -> str:
        return ((reponse.get("license_key") or {}).get("status") or "").lower()

    def activer(self, cle: str) -> Etat:
        cle = cle.strip()
        if len(cle) < 8:
            raise ErreurLicence("Collez la clé de licence complète, telle qu'elle figure dans l'e-mail de Lemon Squeezy.")
        nom = f"{NOM_LOGICIEL} – {platform.node() or 'ordinateur'}"[:180]
        try:
            code, r = self.transport(f"{API}/activate", {"license_key": cle, "instance_name": nom})
        except HorsLigne as e:
            raise ErreurLicence("Impossible de joindre le serveur de licences : vérifiez votre connexion à Internet, "
                                "puis réessayez.") from e
        if not r.get("activated"):
            erreur = (r.get("error") or "").lower()
            if "limit" in erreur:
                raise ErreurLicence("Cette clé est déjà utilisée sur le nombre maximal d'ordinateurs. Libérez-la sur "
                                    "l'ancien ordinateur (écran Licence → « Libérer »), ou contactez le support.")
            statut = self._statut_lemon(r)
            if statut == "disabled":
                raise ErreurLicence("Cette licence a été désactivée (par exemple après un remboursement).")
            if statut == "expired":
                raise ErreurLicence("Cette licence a expiré.")
            raise ErreurLicence("Clé de licence inconnue : vérifiez qu'elle est copiée en entier, sans espace.")
        self._controler_produit(r)
        meta = r.get("meta") or {}
        self._ecrire({
            "cle": cle, "instance": (r.get("instance") or {}).get("id", ""), "statut": ACTIVE,
            "verifie_le": self.maintenant().isoformat(), "client": meta.get("customer_name", ""),
            "email": meta.get("customer_email", ""), "produit": meta.get("product_name", ""),
        })
        return self.etat()

    def verifier(self) -> Etat:
        """Revérifie en ligne. Hors ligne : l'état local reste valable (délai de tolérance)."""
        d = self._lire()
        if not d or d.get("altere") or not d.get("cle"):
            return self.etat()
        try:
            code, r = self.transport(f"{API}/validate", {"license_key": d["cle"], "instance_id": d.get("instance", "")})
        except HorsLigne:
            return self.etat()
        statut_lemon = self._statut_lemon(r)
        if r.get("valid") and statut_lemon in ("active", "inactive", ""):
            try:
                self._controler_produit(r)
            except ErreurLicence as e:
                self._ecrire({**d, "statut": INVALIDE, "message": str(e)})
                return self.etat()
            self._ecrire({**d, "statut": ACTIVE, "verifie_le": self.maintenant().isoformat(), "message": ""})
        elif statut_lemon == "disabled":
            self._ecrire({**d, "statut": DESACTIVEE})
        elif statut_lemon == "expired":
            self._ecrire({**d, "statut": EXPIREE})
        elif code in (400, 404, 422) or r.get("valid") is False:
            self._ecrire({**d, "statut": INVALIDE, "message": "Cette licence n'est plus reconnue pour cet ordinateur : "
                                                              "saisissez à nouveau votre clé."})
        return self.etat()

    def liberer(self) -> None:
        """Désactive cet ordinateur chez Lemon Squeezy (pour installer le logiciel ailleurs) et oublie la clé."""
        d = self._lire()
        if d and not d.get("altere") and d.get("cle") and d.get("instance"):
            try:
                self.transport(f"{API}/deactivate", {"license_key": d["cle"], "instance_id": d["instance"]})
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
