"""Rapports PDF (un prospect ou sélection en ZIP), exports Excel / CSV, logo de l'agence."""

from __future__ import annotations

from datetime import datetime
from urllib.parse import quote

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import FileResponse, Response

from chasseur.db.agence import lire_agence
from chasseur.reports.donnees import diagnostic
from chasseur.reports.excel import exporter_csv, exporter_excel
from chasseur.reports.pdf import ErreurPDF, html_rapport, nom_fichier, zip_rapports
from chasseur.web.routes_resultats import filtres_depuis

routeur = APIRouter()
MAX_RAPPORTS = 200


def _telechargement(contenu: bytes, nom: str, type_mime: str) -> Response:
    return Response(
        contenu,
        media_type=type_mime,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(nom)}"},
    )


async def _pdf(request: Request, prospect_id: int) -> tuple[str, bytes]:
    stockage = request.app.state.stockage
    with stockage.session() as s:
        d = diagnostic(s, prospect_id)
        if d is None:
            raise HTTPException(404, "Prospect introuvable")
        html = html_rapport(stockage, d, lire_agence(s))
    try:
        return nom_fichier(d.prospect), await request.app.state.moteur_pdf().pdf(html)
    except ErreurPDF as e:
        raise HTTPException(500, str(e)) from None


@routeur.get("/prospects/{prospect_id}/rapport.pdf")
async def rapport(request: Request, prospect_id: int):
    nom, contenu = await _pdf(request, prospect_id)
    return _telechargement(contenu, nom, "application/pdf")


@routeur.get("/prospects/{prospect_id}/rapport.html", include_in_schema=False)
async def apercu_rapport(request: Request, prospect_id: int):
    """Aperçu HTML du rapport (mise au point du gabarit)."""
    stockage = request.app.state.stockage
    with stockage.session() as s:
        d = diagnostic(s, prospect_id)
        if d is None:
            raise HTTPException(404, "Prospect introuvable")
        return Response(html_rapport(stockage, d, lire_agence(s)), media_type="text/html")


@routeur.post("/rapports.zip")
async def rapports_groupes(request: Request, ids: list[int] = Form(default=[])):
    ids = list(dict.fromkeys(ids))[:MAX_RAPPORTS]
    if not ids:
        raise HTTPException(400, "Cochez au moins un prospect.")
    rapports = [await _pdf(request, i) for i in ids]
    nom = f"diagnostics-{datetime.now():%Y-%m-%d}.zip"
    return _telechargement(zip_rapports(rapports), nom, "application/zip")


@routeur.get("/export.xlsx")
async def export_excel(request: Request):
    stockage = request.app.state.stockage
    filtres = filtres_depuis(request.query_params)
    with stockage.session() as s:
        contenu = exporter_excel(stockage, s, filtres, description=_description(request))
    return _telechargement(contenu, f"prospects-{datetime.now():%Y-%m-%d}.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@routeur.get("/export.csv")
async def export_csv(request: Request):
    stockage = request.app.state.stockage
    with stockage.session() as s:
        contenu = exporter_csv(stockage, s, filtres_depuis(request.query_params))
    return _telechargement(contenu, f"prospects-{datetime.now():%Y-%m-%d}.csv", "text/csv; charset=utf-8")


def _description(request: Request) -> str:
    q = request.query_params
    morceaux = [f"{nom} : {q[cle]}" for cle, nom in (("etat", "catégorie"), ("statut", "statut"), ("probleme", "problème"), ("q", "recherche")) if q.get(cle)]
    return ", ".join(morceaux) or "tous les prospects"


@routeur.get("/agence/logo", include_in_schema=False)
async def logo(request: Request):
    stockage = request.app.state.stockage
    with stockage.session() as s:
        agence = lire_agence(s)
    chemin = stockage.absolu(agence.logo) if agence.logo else None
    if not chemin or not chemin.is_file():
        raise HTTPException(404, "Pas de logo")
    return FileResponse(chemin, headers={"Content-Security-Policy": "script-src 'none'", "Cache-Control": "no-cache"})
