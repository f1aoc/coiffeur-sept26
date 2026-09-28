"""Écrans « Résultats » et « Fiche prospect »."""

from __future__ import annotations

from urllib.parse import urlencode

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse

from chasseur.controles import CODE_NON_VERIFIE, CONTROLES, libelle
from chasseur.db import depot
from chasseur.db.tables import STATUTS_COMMERCIAUX, ProspectDB, Scan
from chasseur.modeles import GRAVITES, Prospect, Resultat
from chasseur.scoring import statut_controles

routeur = APIRouter()

ETATS = ["Cassé", "Obsolète", "Correct", "À revérifier", "Sans site"]


def _page(request: Request, gabarit: str, **contexte):
    return request.app.state.templates.TemplateResponse(request, gabarit, contexte)


def _entier(texte: str | None) -> int | None:
    try:
        return int(texte) if texte else None
    except ValueError:
        return None


@routeur.get("/resultats", response_class=HTMLResponse)
async def resultats(
    request: Request, scan: str = "", etat: str = "", probleme: str = "", statut: str = "", q: str = "",
    tri: str = "score", ordre: str = "desc", page: int = 1,
):
    filtres = depot.Filtres(
        scan=_entier(scan), etat=etat, probleme=probleme, statut=statut, q=q,
        tri=tri if tri in depot.TRIS else "score", ordre="asc" if ordre == "asc" else "desc", page=page,
    )
    with request.app.state.stockage.session() as s:
        resultat = depot.rechercher(s, filtres)
        analyses = depot.scans(s)

    parametres = {k: v for k, v in vars(filtres).items() if v not in (None, "", 1) or k in ("tri", "ordre")}

    def lien(**changements) -> str:
        valeurs = {**parametres, **changements}
        return "/resultats?" + urlencode({k: v for k, v in valeurs.items() if v not in (None, "")})

    def lien_tri(colonne: str) -> str:
        ordre_suivant = "asc" if filtres.tri == colonne and filtres.ordre == "desc" else "desc"
        if filtres.tri != colonne and colonne in ("nom", "ville", "statut", "etat"):
            ordre_suivant = "asc"
        return lien(tri=colonne, ordre=ordre_suivant, page=1)

    return _page(
        request, "resultats.html", actif="resultats", r=resultat, f=filtres, analyses=analyses, etats=ETATS,
        lien=lien, lien_tri=lien_tri,
    )


def _prospect(session, prospect_id: int) -> ProspectDB:
    p = session.get(ProspectDB, prospect_id)
    if p is None:
        raise HTTPException(404, "Prospect introuvable")
    return p


@routeur.get("/prospects/{prospect_id}", response_class=HTMLResponse)
async def fiche(request: Request, prospect_id: int):
    with request.app.state.stockage.session() as s:
        p = _prospect(s, prospect_id)
        scan = s.get(Scan, p.scan_id)
        constats = depot.constats_de(s, prospect_id)
        captures = depot.captures_de(s, prospect_id)
        note = depot.note(s, prospect_id)
        historique = depot.historique(s, prospect_id)
    rang = {g: i for i, g in enumerate(GRAVITES)}
    problemes = sorted(
        (c for c in constats if c.code != CODE_NON_VERIFIE),
        key=lambda c: (-c.points, rang.get(c.gravite, 9)),
    )
    resultat = Resultat(Prospect(), non_verifies=p.non_verifies, sans_objet=p.sans_objet)
    resultat.constats = [c for c in constats]  # statut_controles ne lit que code
    statuts = statut_controles(resultat)
    controles = [(c, statuts[c.id]) for c in CONTROLES]
    return _page(
        request, "fiche.html", actif="resultats", p=p, scan=scan, problemes=problemes, constats=constats,
        captures=captures, note=note, historique=historique, controles=controles, libelle=libelle,
    )


@routeur.post("/prospects/{prospect_id}/statut", response_class=HTMLResponse)
async def changer_statut(request: Request, prospect_id: int, statut: str = Form(...), contexte: str = Form("")):
    if statut not in STATUTS_COMMERCIAUX:
        raise HTTPException(400, "Statut inconnu")
    with request.app.state.stockage.session() as s:
        _prospect(s, prospect_id)
        p = depot.changer_statut(s, prospect_id, statut)
        historique = depot.historique(s, prospect_id) if contexte == "fiche" else None
    return _page(
        request, "_statut.html", p=p, enregistre=True, contexte=contexte, historique=historique, oob=contexte == "fiche"
    )


@routeur.post("/prospects/{prospect_id}/note", response_class=HTMLResponse)
async def enregistrer_note(request: Request, prospect_id: int, texte: str = Form("")):
    with request.app.state.stockage.session() as s:
        _prospect(s, prospect_id)
        note = depot.enregistrer_note(s, prospect_id, texte[:20_000])
    return _page(request, "_note.html", note=note)
