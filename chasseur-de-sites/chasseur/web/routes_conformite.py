"""RGPD (liste d'opposition, suppression), planification, comparaison de scans, page « À propos »."""

from __future__ import annotations

import platform
from urllib.parse import urlencode

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import func, select

from chasseur import __version__, planification, rgpd
from chasseur.db import depot
from chasseur.db.tables import Opposition, ProspectDB, Scan
from chasseur.journal import dernieres_lignes
from chasseur.reports.pdf import weasyprint_disponible

routeur = APIRouter()


def _page(request: Request, gabarit: str, **contexte):
    return request.app.state.templates.TemplateResponse(request, gabarit, contexte)


# --- Liste d'opposition ---------------------------------------------------------------


@routeur.get("/oppositions", response_class=HTMLResponse)
async def oppositions(request: Request, ok: str = "", erreur: str = ""):
    with request.app.state.stockage.session() as s:
        liste = list(s.exec(select(Opposition).order_by(Opposition.domaine)))
    return _page(request, "oppositions.html", actif="oppositions", oppositions=liste, ok=ok[:200], erreur=erreur[:200])


@routeur.post("/oppositions")
async def ajouter(request: Request, domaine: str = Form(""), motif: str = Form("")):
    stockage = request.app.state.stockage
    with stockage.session() as s:
        try:
            opposition, supprimes = rgpd.ajouter_opposition(stockage, s, domaine, motif)
        except rgpd.ErreurRGPD as e:
            return RedirectResponse(f"/oppositions?{urlencode({'erreur': str(e)})}", status_code=303)
    message = f"{opposition.domaine} ajouté à la liste d'opposition" + (f" ; {supprimes} prospect(s) supprimé(s)." if supprimes else ".")
    return RedirectResponse(f"/oppositions?{urlencode({'ok': message})}", status_code=303)


@routeur.post("/oppositions/{opposition_id}/retirer")
async def retirer(request: Request, opposition_id: int):
    with request.app.state.stockage.session() as s:
        rgpd.retirer_opposition(s, opposition_id)
    return RedirectResponse("/oppositions", status_code=303)


# --- Suppression d'un prospect ---------------------------------------------------------


@routeur.post("/prospects/{prospect_id}/supprimer")
async def supprimer(request: Request, prospect_id: int, opposer: str = Form("")):
    stockage = request.app.state.stockage
    with stockage.session() as s:
        p = s.get(ProspectDB, prospect_id)
        if p is None:
            raise HTTPException(404, "Prospect introuvable")
        scan_id, nom, url = p.scan_id, p.nom, p.url
        if opposer and url:
            try:
                rgpd.ajouter_opposition(stockage, s, url, motif=f"Demande de {nom}"[:200])
            except rgpd.ErreurRGPD:
                rgpd.supprimer_prospect(stockage, s, prospect_id)
        else:
            rgpd.supprimer_prospect(stockage, s, prospect_id)
    message = f"« {nom or url} » a été supprimé" + (" et son domaine ne sera plus jamais analysé." if opposer and url else ".")
    return RedirectResponse(f"/resultats?{urlencode({'scan': scan_id, 'message': message})}", status_code=303)


# --- Planification et comparaison -------------------------------------------------------


@routeur.post("/analyses/{scan_id}/planifier")
async def planifier(request: Request, scan_id: int, actif: str = Form("")):
    with request.app.state.stockage.session() as s:
        if s.get(Scan, scan_id) is None:
            raise HTTPException(404, "Analyse introuvable")
        planification.planifier(s, scan_id, actif == "1")
    return RedirectResponse(f"/analyses/{scan_id}", status_code=303)


@routeur.get("/analyses/{scan_id}/comparaison", response_class=HTMLResponse)
async def comparaison(request: Request, scan_id: int, avec: int | None = None):
    with request.app.state.stockage.session() as s:
        nouveau = s.get(Scan, scan_id)
        if nouveau is None:
            raise HTTPException(404, "Analyse introuvable")
        ancien = s.get(Scan, avec) if avec else planification.scan_precedent(s, nouveau)
        autres = [x for x in depot.scans(s) if x.id != scan_id]
        c = planification.comparer(s, ancien, nouveau) if ancien else None
    return _page(request, "comparaison.html", actif="analyses", nouveau=nouveau, ancien=ancien, autres=autres, c=c)


# --- À propos -----------------------------------------------------------------------


@routeur.get("/a-propos", response_class=HTMLResponse)
async def a_propos(request: Request):
    stockage = request.app.state.stockage
    with stockage.session() as s:
        prospects = s.exec(select(func.count()).select_from(ProspectDB)).one()
        analyses = s.exec(select(func.count()).select_from(Scan)).one()
        conservation = rgpd.duree_conservation(s)
    journal = request.app.state.fichier_journal
    return _page(
        request, "a_propos.html", actif="a-propos", version=__version__, python=platform.python_version(),
        systeme=f"{platform.system()} {platform.release()}", dossier=stockage.dossier, journal=journal,
        erreurs=dernieres_lignes(journal, 30), prospects=prospects, analyses=analyses, conservation=conservation,
        moteur_pdf="WeasyPrint" if weasyprint_disponible() else "Chromium (WeasyPrint absent)",
    )
