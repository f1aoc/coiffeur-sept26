"""Opérations sur la base : scans, résultats d'analyse, recherche, statuts, notes."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from sqlalchemy import delete, func, or_
from sqlmodel import Session, select

from chasseur.config import Config
from chasseur.controles import CODE_NON_VERIFIE, CONTROLE_DU_CODE, libelle
from chasseur.db.moteur import Stockage
from chasseur.db.tables import (
    STATUTS_COMMERCIAUX,
    Capture,
    ConstatDB,
    HistoriqueStatut,
    Note,
    ProspectDB,
    Scan,
    maintenant,
)
from chasseur.modeles import GRAVITES, Constat, Prospect, Resultat
from chasseur.scoring import noter

PAR_PAGE = 50
CLES_CAPTURES = {"capture_bureau": "bureau", "capture_mobile": "mobile"}


class ErreurDepot(ValueError):
    pass


# --- Scans --------------------------------------------------------------------------


def creer_scan(session: Session, nom: str, prospects: list[Prospect], fichier: str = "", format_: str = "") -> Scan:
    scan = Scan(nom=nom, fichier=fichier, format=format_, total=len(prospects))
    session.add(scan)
    session.flush()
    source = f"Import « {fichier or nom} »"
    for p in prospects:
        session.add(
            ProspectDB(
                scan_id=scan.id, nom=p.nom, url=p.url, telephone=p.telephone, adresse=p.adresse, ville=p.ville,
                categorie=p.categorie, note_google=p.note_google, nb_avis=p.nb_avis, lien_maps=p.lien_maps,
                remarque=p.remarque, ligne=p.ligne, source=source,
            )
        )
    session.commit()
    return scan


def vers_prospect(p: ProspectDB) -> Prospect:
    """Prospect d'analyse ; `ligne` reçoit l'identifiant en base (nommage des captures)."""
    return Prospect(
        nom=p.nom, url=p.url, telephone=p.telephone, adresse=p.adresse, categorie=p.categorie, ligne=p.id,
        ville=p.ville, note_google=p.note_google, nb_avis=p.nb_avis, lien_maps=p.lien_maps, remarque=p.remarque,
    )


def a_analyser(session: Session, scan_id: int) -> list[ProspectDB]:
    return list(session.exec(select(ProspectDB).where(ProspectDB.scan_id == scan_id, ProspectDB.analyse == False)))  # noqa: E712


def compteurs(session: Session, scan_id: int) -> dict[str, int]:
    faits = session.exec(
        select(func.count()).select_from(ProspectDB).where(ProspectDB.scan_id == scan_id, ProspectDB.analyse == True)  # noqa: E712
    ).one()
    par_etat = dict(
        session.exec(
            select(ProspectDB.etat, func.count())
            .where(ProspectDB.scan_id == scan_id, ProspectDB.analyse == True)  # noqa: E712
            .group_by(ProspectDB.etat)
        ).all()
    )
    return {"faits": faits, **par_etat}


def scans(session: Session) -> list[Scan]:
    return list(session.exec(select(Scan).order_by(Scan.cree_le.desc(), Scan.id.desc())))


# --- Enregistrement d'un résultat ---------------------------------------------------------


def creer_miniature(source: Path, cible: Path, largeur: int = 320) -> None:
    from PIL import Image

    with Image.open(source) as image:
        image.thumbnail((largeur, largeur * 2))
        cible.parent.mkdir(parents=True, exist_ok=True)
        image.convert("RGB").save(cible, "WEBP", quality=60)


def _date(texte: str) -> datetime | None:
    try:
        return datetime.strptime(texte, "%Y-%m-%d %H:%M:%S").astimezone()  # heure locale de la capture
    except (TypeError, ValueError):
        return None


def enregistrer_resultat(stockage: Stockage, session: Session, prospect_id: int, r: Resultat) -> ProspectDB:
    p = session.get(ProspectDB, prospect_id)
    if p is None:
        raise ErreurDepot(f"prospect {prospect_id} introuvable")
    mesures = {k: v for k, v in r.mesures.items() if k not in CLES_CAPTURES}
    p.analyse, p.analyse_le, p.score, p.etat = True, maintenant(), r.score, r.etat
    p.mesures, p.non_verifies, p.sans_objet, p.echecs = mesures, dict(r.non_verifies), list(r.sans_objet), list(r.echecs)

    session.exec(delete(ConstatDB).where(ConstatDB.prospect_id == prospect_id))
    session.exec(delete(Capture).where(Capture.prospect_id == prospect_id))
    for c in r.constats:
        controle = CONTROLE_DU_CODE[c.code].id if c.code in CONTROLE_DU_CODE else ""
        session.add(
            ConstatDB(
                prospect_id=prospect_id, code=c.code, controle=controle, gravite=c.gravite, points=c.points,
                message_client=c.message_client, preuve=c.preuve,
            )
        )
    for cle, type_ in CLES_CAPTURES.items():
        chemin = r.mesures.get(cle)
        if not chemin or not Path(chemin).is_file():
            continue
        chemin = Path(chemin).resolve()
        miniature = chemin.with_name(chemin.stem + "-mini.webp")
        try:
            creer_miniature(chemin, miniature)
            rel_mini = stockage.relatif(miniature)
        except (OSError, ValueError):
            rel_mini = ""
        session.add(
            Capture(
                prospect_id=prospect_id, type=type_, chemin=stockage.relatif(chemin), miniature=rel_mini,
                prise_le=_date(r.mesures.get("capture_date", "")),
            )
        )
    session.add(p)
    session.commit()
    return p


# --- Rescoring (poids modifiés dans les Réglages) ------------------------------------------


def constats_de(session: Session, prospect_id: int) -> list[ConstatDB]:
    return list(session.exec(select(ConstatDB).where(ConstatDB.prospect_id == prospect_id)))


def recalculer_scores(session: Session, config: Config) -> int:
    n = 0
    for p in list(session.exec(select(ProspectDB).where(ProspectDB.analyse == True))):  # noqa: E712
        constats = []
        for c in constats_de(session, p.id):
            c.points = config.points_du_code(c.code) if (c.code in CONTROLE_DU_CODE or c.code == CODE_NON_VERIFIE) else c.points
            session.add(c)
            constats.append(Constat(c.code, c.gravite, c.points, c.message_client, c.preuve))
        r = noter(Resultat(vers_prospect(p), constats, echecs=list(p.echecs)), config)
        p.score, p.etat = r.score, r.etat
        session.add(p)
        n += 1
    session.commit()
    return n


# --- Recherche (écran Résultats) ---------------------------------------------------------

TRIS = {
    "nom": ProspectDB.nom,
    "ville": ProspectDB.ville,
    "etat": ProspectDB.etat,
    "score": ProspectDB.score,
    "telephone": ProspectDB.telephone,
    "note": ProspectDB.note_google,
    "statut": ProspectDB.statut,
}


@dataclass
class Filtres:
    scan: int | None = None
    etat: str = ""
    probleme: str = ""  # identifiant de contrôle
    statut: str = ""
    q: str = ""
    tri: str = "score"
    ordre: str = "desc"
    page: int = 1


@dataclass
class Ligne:
    prospect: ProspectDB
    problemes: list[tuple[str, str, str]] = field(default_factory=list)  # (code, libellé, gravité)
    miniature: str = ""
    capture: str = ""


@dataclass
class PageResultats:
    lignes: list[Ligne]
    total: int
    page: int
    pages: int


def _requete_filtree(f: Filtres):
    requete = select(ProspectDB)
    if f.scan:
        requete = requete.where(ProspectDB.scan_id == f.scan)
    if f.etat:
        requete = requete.where(ProspectDB.etat == f.etat)
    if f.statut:
        requete = requete.where(ProspectDB.statut == f.statut)
    if f.probleme:
        requete = requete.where(
            ProspectDB.id.in_(select(ConstatDB.prospect_id).where(ConstatDB.controle == f.probleme))
        )
    if f.q.strip():
        motif = f"%{f.q.strip()}%"
        requete = requete.where(or_(ProspectDB.nom.ilike(motif), ProspectDB.ville.ilike(motif)))
    return requete


def problemes_principaux(constats: list[ConstatDB], n: int = 3) -> list[tuple[str, str, str]]:
    utiles = [c for c in constats if c.code != CODE_NON_VERIFIE and (c.points or c.gravite not in ("info",))]
    rang = {g: i for i, g in enumerate(GRAVITES)}
    utiles.sort(key=lambda c: (-c.points, rang.get(c.gravite, 9)))
    vus, sortie = set(), []
    for c in utiles:
        if c.controle in vus:
            continue  # un problème par contrôle
        vus.add(c.controle)
        sortie.append((c.code, libelle(c.code), c.gravite))
    return sortie[:n]


def rechercher(session: Session, f: Filtres) -> PageResultats:
    requete = _requete_filtree(f)
    total = session.exec(select(func.count()).select_from(requete.subquery())).one()
    pages = max(1, math.ceil(total / PAR_PAGE))
    page = min(max(1, f.page), pages)
    colonne = TRIS.get(f.tri, ProspectDB.score)
    ordre = colonne.desc() if f.ordre == "desc" else colonne.asc()
    requete = requete.order_by(ordre.nulls_last(), ProspectDB.id).offset((page - 1) * PAR_PAGE).limit(PAR_PAGE)
    prospects = list(session.exec(requete))
    ids = [p.id for p in prospects]

    constats: dict[int, list[ConstatDB]] = {i: [] for i in ids}
    captures: dict[int, Capture] = {}
    if ids:
        for c in session.exec(select(ConstatDB).where(ConstatDB.prospect_id.in_(ids))):
            constats[c.prospect_id].append(c)
        for c in session.exec(select(Capture).where(Capture.prospect_id.in_(ids), Capture.type == "bureau")):
            captures[c.prospect_id] = c
    lignes = [
        Ligne(
            p,
            problemes_principaux(constats[p.id]),
            miniature=(captures[p.id].miniature or captures[p.id].chemin) if p.id in captures else "",
            capture=captures[p.id].chemin if p.id in captures else "",
        )
        for p in prospects
    ]
    return PageResultats(lignes, total, page, pages)


# --- Suivi commercial ---------------------------------------------------------------------


def changer_statut(session: Session, prospect_id: int, nouveau: str) -> ProspectDB:
    if nouveau not in STATUTS_COMMERCIAUX:
        raise ErreurDepot(f"statut inconnu : {nouveau}")
    p = session.get(ProspectDB, prospect_id)
    if p is None:
        raise ErreurDepot(f"prospect {prospect_id} introuvable")
    if p.statut != nouveau:
        session.add(HistoriqueStatut(prospect_id=prospect_id, ancien=p.statut, nouveau=nouveau))
        p.statut = nouveau
        session.add(p)
        session.commit()
    return p


def historique(session: Session, prospect_id: int) -> list[HistoriqueStatut]:
    return list(
        session.exec(
            select(HistoriqueStatut)
            .where(HistoriqueStatut.prospect_id == prospect_id)
            .order_by(HistoriqueStatut.change_le.desc(), HistoriqueStatut.id.desc())
        )
    )


def note(session: Session, prospect_id: int) -> Note | None:
    return session.exec(select(Note).where(Note.prospect_id == prospect_id)).first()


def enregistrer_note(session: Session, prospect_id: int, texte: str) -> Note:
    if session.get(ProspectDB, prospect_id) is None:
        raise ErreurDepot(f"prospect {prospect_id} introuvable")
    n = note(session, prospect_id) or Note(prospect_id=prospect_id)
    n.texte, n.modifie_le = texte, maintenant()
    session.add(n)
    session.commit()
    return n


def captures_de(session: Session, prospect_id: int) -> dict[str, Capture]:
    return {c.type: c for c in session.exec(select(Capture).where(Capture.prospect_id == prospect_id))}
