"""Écran « Licence » et contrôle d'accès : sans licence active, seules la consultation, l'export et la
suppression des données restent possibles."""

from __future__ import annotations

import asyncio
import re
from urllib.parse import urlencode

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from chasseur import licence as lic

routeur = APIRouter()

# Toujours accessibles, même sans licence active (consulter, exporter, supprimer ses données)
LIBRES_GET = re.compile(r"^/(licence|a-propos|resultats|export\.(xlsx|csv)|prospects/\d+|oppositions|agence/logo"
                        r"|static/.*|captures/.*)$")
LIBRES_POST = re.compile(r"^/(licence(/.*)?|prospects/\d+/supprimer|oppositions(/\d+/retirer)?)$")


def chemin_libre(methode: str, chemin: str) -> bool:
    motif = LIBRES_GET if methode in ("GET", "HEAD") else LIBRES_POST
    return bool(motif.match(chemin))


def refus(request: Request) -> Response:
    """Redirige vers l'écran Licence (aussi pour les fragments htmx)."""
    if request.headers.get("hx-request"):
        return Response(status_code=200, headers={"HX-Redirect": "/licence"})
    return RedirectResponse("/licence", status_code=303)


def _rediriger(**params) -> RedirectResponse:
    return RedirectResponse("/licence" + (f"?{urlencode(params)}" if params else ""), status_code=303)


@routeur.get("/licence", response_class=HTMLResponse)
async def page(request: Request, ok: str = "", erreur: str = ""):
    etat = request.app.state.licence.etat()
    return request.app.state.templates.TemplateResponse(request, "licence.html", {
        "actif": "licence", "etat": etat, "ok": ok, "erreur": erreur, "lien_achat": lic.LIEN_ACHAT,
        "tolerance": lic.TOLERANCE_JOURS,
    })


@routeur.post("/licence")
async def activer(request: Request, cle: str = Form("")):
    try:
        etat = await asyncio.to_thread(request.app.state.licence.activer, cle)
    except lic.ErreurLicence as e:
        return _rediriger(erreur=str(e))
    nom = f", {etat.client}" if etat.client else ""
    return _rediriger(ok=f"Merci{nom} ! Votre licence est activée sur cet ordinateur.")


@routeur.post("/licence/verifier")
async def verifier(request: Request):
    etat = await asyncio.to_thread(request.app.state.licence.verifier)
    if etat.utilisable:
        return _rediriger(ok="Licence vérifiée : tout est en ordre.")
    return _rediriger()  # la page affiche déjà la raison (désactivée, expirée, hors ligne…)


@routeur.post("/licence/liberer")
async def liberer(request: Request):
    try:
        await asyncio.to_thread(request.app.state.licence.liberer)
    except lic.ErreurLicence as e:
        return _rediriger(erreur=str(e))
    return _rediriger(ok="Licence libérée : vous pouvez maintenant l'activer sur un autre ordinateur.")
