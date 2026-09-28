"""Écran « Réglages » : clés API (chiffrées), analyses simultanées, poids du scoring."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from chasseur.config import PARALLELISME_MAX, charger_config
from chasseur.controles import CONTROLES
from chasseur.db import depot, reglages
from chasseur.db.secret import ErreurSecret, masquer

routeur = APIRouter()

FAMILLES = [
    ("casse", "Site cassé (tableau 3.2)"),
    ("obsolete", "Site obsolète (tableau 3.3)"),
    ("autre", "Hors tableaux"),
]


def _base(request: Request):
    return charger_config(request.app.state.chemin_config)


@routeur.get("/reglages", response_class=HTMLResponse)
async def page(request: Request, ok: int = 0):
    stockage = request.app.state.stockage
    base = _base(request)
    with stockage.session() as s:
        cles = {}
        for cle, nom in reglages.CLES_API.items():
            try:
                valeur = reglages.lire_cle_api(stockage, s, cle)
                cles[cle] = (nom, masquer(valeur) if valeur else "", "")
            except ErreurSecret as e:
                cles[cle] = (nom, "", str(e))
        points = reglages.points(s, base)
        parallelisme = reglages.parallelisme(s, base)
    groupes = [(titre, [(c, points[c.id], base.points[c.id]) for c in CONTROLES if c.famille == f and c.id != "url"]) for f, titre in FAMILLES]
    return request.app.state.templates.TemplateResponse(
        request, "reglages.html",
        dict(actif="reglages", cles=cles, groupes=groupes, parallelisme=parallelisme, maximum=PARALLELISME_MAX, ok=ok),
    )


@routeur.post("/reglages")
async def enregistrer(request: Request):
    formulaire = await request.form()
    stockage = request.app.state.stockage
    base = _base(request)
    with stockage.session() as s:
        for cle in reglages.CLES_API:
            if formulaire.get(f"effacer_{cle}"):
                reglages.supprimer(s, cle)
            elif (valeur := str(formulaire.get(cle, "")).strip()):
                reglages.ecrire_cle_api(stockage, s, cle, valeur)
        try:
            n = int(str(formulaire.get("parallelisme", base.parallelisme)))
            reglages.ecrire(s, reglages.PARALLELISME, str(min(max(1, n), PARALLELISME_MAX)))
        except ValueError:
            pass
        points = {}
        for c in CONTROLES:
            try:
                points[c.id] = max(0, min(100, int(str(formulaire.get(f"points_{c.id}", "")))))
            except ValueError:
                continue
        reglages.ecrire_points(s, points)
        s.commit()
        config = reglages.config_effective(stockage, s, base)
        depot.recalculer_scores(s, config)  # les scores existants suivent les nouveaux poids
    return RedirectResponse("/reglages?ok=1", status_code=303)
