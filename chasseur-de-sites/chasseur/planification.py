"""Scans planifiés (relance hebdomadaire) et comparaison entre deux scans.

Une analyse « planifiée » est relancée chaque semaine : un nouveau scan est créé
avec la liste la plus récente de la série (sans les prospects supprimés ni les
domaines en opposition), en conservant le statut commercial de chaque prospect.
Les relances ont lieu quand l'application est ouverte ; pour un ordinateur
souvent éteint, « chasseur planifies » peut être lancé par le Planificateur de
tâches Windows ou cron.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from chasseur.db import depot
from chasseur.db.tables import ProspectDB, Scan, maintenant
from chasseur.dedoublonnage import cle_domaine
from chasseur.rgpd import domaines_opposes, est_oppose

INTERVALLE = timedelta(days=7)


def _aware(d: datetime | None) -> datetime | None:
    if d is None:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def racine(session: Session, scan: Scan) -> Scan:
    """Premier scan de la série (celui qui porte la planification)."""
    return session.get(Scan, scan.origine_id) if scan.origine_id else scan


def serie(session: Session, scan_racine: Scan) -> list[Scan]:
    """Scans de la série, du plus ancien au plus récent."""
    enfants = list(session.exec(select(Scan).where(Scan.origine_id == scan_racine.id).order_by(Scan.id)))
    return [scan_racine, *enfants]


def planifier(session: Session, scan_id: int, actif: bool, a_partir_de: datetime | None = None) -> Scan:
    scan = racine(session, session.get(Scan, scan_id))
    scan.planifie = actif
    scan.prochaine_execution = ((a_partir_de or maintenant()) + INTERVALLE) if actif else None
    session.add(scan)
    session.commit()
    return scan


def scans_dus(session: Session, instant: datetime | None = None) -> list[Scan]:
    instant = instant or maintenant()
    return [
        s for s in session.exec(select(Scan).where(Scan.planifie == True))  # noqa: E712
        if s.prochaine_execution is not None and _aware(s.prochaine_execution) <= instant
    ]


def creer_relance(session: Session, scan_racine: Scan, instant: datetime | None = None) -> Scan:
    """Nouveau scan de la série, à analyser ; reporte la prochaine exécution d'une semaine."""
    instant = instant or maintenant()
    dernier = serie(session, scan_racine)[-1]
    anciens = list(session.exec(select(ProspectDB).where(ProspectDB.scan_id == dernier.id)))
    opposes = domaines_opposes(session)
    anciens = [p for p in anciens if not est_oppose(p.url, opposes)]
    prospects = [depot.vers_prospect(p) for p in anciens]
    for p, ancien in zip(prospects, anciens):
        p.ligne = ancien.ligne
    nouveau = depot.creer_scan(
        session, f"{scan_racine.nom} – {instant.astimezone():%d/%m/%Y}", prospects, fichier=scan_racine.fichier,
        format_=scan_racine.format, source=scan_racine.source, origine_id=scan_racine.id,
    )
    # Le suivi commercial continue d'une semaine à l'autre
    nouveaux = sorted(depot.a_analyser(session, nouveau.id), key=lambda p: p.id)
    for p, ancien in zip(nouveaux, anciens):
        p.statut, p.source, p.collecte_le = ancien.statut, ancien.source, ancien.collecte_le
        session.add(p)
    scan_racine.prochaine_execution = instant + INTERVALLE
    session.add(scan_racine)
    session.commit()
    return nouveau


# --- Comparaison ------------------------------------------------------------------


def cle(p: ProspectDB) -> str:
    return (cle_domaine(p.url) if p.url else None) or f"nom:{p.nom.strip().lower()}"


@dataclass
class Comparaison:
    ancien: Scan
    nouveau: Scan
    devenus_casses: list[tuple[ProspectDB, ProspectDB]] = field(default_factory=list)
    repares: list[tuple[ProspectDB, ProspectDB]] = field(default_factory=list)
    changements: list[tuple[ProspectDB, ProspectDB]] = field(default_factory=list)  # autre changement d'état
    nouveaux: list[ProspectDB] = field(default_factory=list)
    disparus: list[ProspectDB] = field(default_factory=list)
    inchanges: int = 0


def scan_precedent(session: Session, scan: Scan) -> Scan | None:
    """Scan de comparaison par défaut : le précédent de la même série, sinon le scan précédent."""
    scans = serie(session, racine(session, scan))
    rang = next((i for i, s in enumerate(scans) if s.id == scan.id), 0)
    if rang > 0:
        return scans[rang - 1]
    return session.exec(select(Scan).where(Scan.id < scan.id).order_by(Scan.id.desc())).first()


def comparer(session: Session, ancien: Scan, nouveau: Scan) -> Comparaison:
    avant = {cle(p): p for p in session.exec(select(ProspectDB).where(ProspectDB.scan_id == ancien.id))}
    apres = {cle(p): p for p in session.exec(select(ProspectDB).where(ProspectDB.scan_id == nouveau.id))}
    c = Comparaison(ancien, nouveau)
    for k, p in apres.items():
        a = avant.get(k)
        if a is None:
            c.nouveaux.append(p)
        elif not (a.analyse and p.analyse) or a.etat == p.etat:
            c.inchanges += 1
        elif p.etat == "Cassé":
            c.devenus_casses.append((a, p))
        elif a.etat == "Cassé":
            c.repares.append((a, p))
        else:
            c.changements.append((a, p))
    c.disparus = [p for k, p in avant.items() if k not in apres]
    return c
