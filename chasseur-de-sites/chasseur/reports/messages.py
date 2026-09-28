"""Modèles de messages (e-mail, script d'appel, SMS), à copier manuellement.

Variables : {entreprise}, {probleme_principal}, {ville}, {agence}.
Aucun envoi automatique (§3.6). Chaque modèle propose au destinataire un
moyen simple de ne plus être contacté (§6.1).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlmodel import Session

from chasseur.db import reglages

VARIABLES = ("entreprise", "probleme_principal", "ville", "agence")
RE_VARIABLE = re.compile(r"\{(" + "|".join(VARIABLES) + r")\}")


@dataclass(frozen=True)
class Modele:
    id: str
    nom: str
    defaut: str


MODELES = (
    Modele(
        "email",
        "E-mail",
        "Objet : le site internet de {entreprise}\n\n"
        "Bonjour,\n\n"
        "En consultant le site de {entreprise}, j'ai remarqué que {probleme_principal}.\n\n"
        "C'est le genre de détail qui fait partir des visiteurs sans que l'on s'en rende compte. "
        "J'ai préparé un court diagnostic avec des captures d'écran : je peux vous l'envoyer "
        "et vous expliquer comment corriger cela.\n\n"
        "Cela vous intéresse ?\n\n"
        "Bien cordialement,\n"
        "{agence}\n\n"
        "Si vous ne souhaitez pas être recontacté, répondez simplement « non merci ».",
    ),
    Modele(
        "appel",
        "Script d'appel",
        "Bonjour, {agence} à l'appareil. Je vous appelle au sujet du site internet de {entreprise}.\n\n"
        "En le consultant, j'ai remarqué que {probleme_principal}. Est-ce que vous étiez au courant ?\n\n"
        "→ Si oui : Avez-vous prévu de le faire corriger ? Je peux vous expliquer ce que cela demande.\n"
        "→ Si non : J'ai préparé un court diagnostic avec des captures d'écran, pour que vous voyiez "
        "ce que voient vos clients. À quelle adresse e-mail puis-je vous l'envoyer ?\n"
        "→ Si pas intéressé : Pas de souci, je note de ne pas vous rappeler. Bonne journée !",
    ),
    Modele(
        "sms",
        "SMS",
        "Bonjour, {agence} ici. En consultant le site de {entreprise}, j'ai vu que {probleme_principal}. "
        "Voulez-vous que je vous envoie un court diagnostic ? Répondez STOP pour ne plus être contacté.",
    ),
)
PAR_ID = {m.id: m for m in MODELES}


def cle(modele_id: str) -> str:
    return f"modele_{modele_id}"


def lire_modeles(session: Session) -> dict[str, str]:
    return {m.id: reglages.lire(session, cle(m.id), "") or m.defaut for m in MODELES}


def ecrire_modele(session: Session, modele_id: str, texte: str) -> None:
    modele = PAR_ID[modele_id]
    texte = (texte or "").replace("\r\n", "\n").strip()
    if not texte or texte == modele.defaut:
        reglages.supprimer(session, cle(modele_id))  # retour au texte par défaut
    else:
        reglages.ecrire(session, cle(modele_id), texte[:5000])


def rendre(modele: str, valeurs: dict[str, str]) -> str:
    """Remplace les variables connues ; tout autre texte entre accolades est laissé tel quel."""
    return RE_VARIABLE.sub(lambda m: valeurs.get(m[1], m[0]), modele)


def variables(entreprise: str, probleme_principal: str, ville: str, agence: str) -> dict[str, str]:
    return {
        "entreprise": entreprise or "votre entreprise",
        "probleme_principal": probleme_principal or "votre site pourrait être modernisé",
        "ville": ville or "votre ville",
        "agence": agence or "[votre agence]",
    }
