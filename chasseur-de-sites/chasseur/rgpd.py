"""Conformité RGPD (§6.1) : liste d'opposition, suppression, purge automatique.

- Liste d'opposition : un domaine ajouté n'est plus jamais importé, analysé
  (y compris par les relances planifiées) ni exporté ; les prospects existants
  de ce domaine sont supprimés.
- Suppression d'un prospect : fiche, constats, captures (fichiers compris),
  notes et historique.
- Purge : les prospects jamais contactés (statut « À contacter ») collectés il y
  a plus de N mois (12 par défaut) sont supprimés automatiquement.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete
from sqlmodel import Session, select

from chasseur import urls
from chasseur.db import reglages
from chasseur.db.moteur import Stockage
from chasseur.db.tables import (
    STATUT_INITIAL,
    Capture,
    ConstatDB,
    HistoriqueStatut,
    Note,
    Opposition,
    ProspectDB,
    maintenant,
)
from chasseur.modeles import Prospect

CONSERVATION = "conservation_mois"
CONSERVATION_DEFAUT = 12
RE_DOMAINE = re.compile(r"^(?=.{1,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z][a-z0-9-]{1,62}$")


class ErreurRGPD(ValueError):
    pass


# --- Liste d'opposition ------------------------------------------------------------


def normaliser_domaine(saisie: str) -> str:
    """« https://www.Salon-Lea.fr/contact » → « salon-lea.fr »."""
    hote = urls.hote(saisie.strip()) if saisie and saisie.strip() else None
    domaine = (hote or "").removeprefix("www.")
    if not RE_DOMAINE.match(domaine):
        raise ErreurRGPD(f"« {saisie.strip()[:80]} » n'est pas un nom de domaine valide (ex. salon-lea.fr).")
    return domaine


def domaines_opposes(session: Session) -> list[str]:
    return [o.domaine for o in session.exec(select(Opposition))]


def est_oppose(url: str, domaines: list[str]) -> bool:
    hote = (urls.hote(url) or "").removeprefix("www.") if url else ""
    return bool(hote) and any(hote == d or hote.endswith("." + d) for d in domaines)


def filtrer_opposes(prospects: list[Prospect], domaines: list[str]) -> tuple[list[Prospect], list[Prospect]]:
    """(prospects autorisés, prospects écartés car leur domaine est dans la liste d'opposition)."""
    gardes, ecartes = [], []
    for p in prospects:
        (ecartes if est_oppose(p.url, domaines) else gardes).append(p)
    return gardes, ecartes


def ajouter_opposition(stockage: Stockage, session: Session, saisie: str, motif: str = "") -> tuple[Opposition, int]:
    """Ajoute un domaine ; renvoie (opposition, nombre de prospects existants supprimés)."""
    domaine = normaliser_domaine(saisie)
    opposition = session.exec(select(Opposition).where(Opposition.domaine == domaine)).first()
    if opposition is None:
        opposition = Opposition(domaine=domaine, motif=motif.strip()[:200])
        session.add(opposition)
    supprimes = 0
    for p in list(session.exec(select(ProspectDB))):
        if est_oppose(p.url, [domaine]):
            supprimer_prospect(stockage, session, p.id, valider=False)
            supprimes += 1
    session.commit()
    return opposition, supprimes


def retirer_opposition(session: Session, opposition_id: int) -> None:
    if (o := session.get(Opposition, opposition_id)) is not None:
        session.delete(o)
        session.commit()


# --- Suppression ------------------------------------------------------------------


def supprimer_prospect(stockage: Stockage, session: Session, prospect_id: int, valider: bool = True) -> bool:
    p = session.get(ProspectDB, prospect_id)
    if p is None:
        return False
    for c in session.exec(select(Capture).where(Capture.prospect_id == prospect_id)):
        for relatif in (c.chemin, c.miniature):
            if relatif:
                stockage.absolu(relatif).unlink(missing_ok=True)
    for table in (ConstatDB, Capture, Note, HistoriqueStatut):
        session.exec(delete(table).where(table.prospect_id == prospect_id))
    session.delete(p)
    if valider:
        session.commit()
    return True


# --- Purge automatique ---------------------------------------------------------------


def duree_conservation(session: Session) -> int:
    try:
        return max(1, int(reglages.lire(session, CONSERVATION, str(CONSERVATION_DEFAUT))))
    except ValueError:
        return CONSERVATION_DEFAUT


def purger(stockage: Stockage, session: Session, maintenant_: datetime | None = None) -> int:
    """Supprime les prospects « À contacter » collectés il y a plus de N mois ; renvoie leur nombre."""
    maintenant_ = maintenant_ or maintenant()
    limite = maintenant_ - timedelta(days=round(duree_conservation(session) * 30.44))
    anciens = []
    for p in session.exec(select(ProspectDB).where(ProspectDB.statut == STATUT_INITIAL)):
        collecte = p.collecte_le if p.collecte_le.tzinfo else p.collecte_le.replace(tzinfo=timezone.utc)
        if collecte < limite:
            anciens.append(p.id)
    for prospect_id in anciens:
        supprimer_prospect(stockage, session, prospect_id, valider=False)
    session.commit()
    return len(anciens)
