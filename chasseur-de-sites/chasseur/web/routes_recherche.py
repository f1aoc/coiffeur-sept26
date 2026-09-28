"""Écran « Recherche » : secteur + ville via l'API Google Places, coût estimé avant de lancer."""

from __future__ import annotations

import csv
import secrets

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from chasseur.db import reglages
from chasseur.db.secret import ErreurSecret
from chasseur.sources import places
from chasseur.web.routes_analyses import FORMAT_PLACES, apercu_import

routeur = APIRouter()
VILLES_MAX = 20


def _page(request: Request, gabarit: str, **contexte):
    return request.app.state.templates.TemplateResponse(request, gabarit, contexte)


def _villes(texte: str) -> list[str]:
    villes = [v.strip() for v in texte.replace(",", "\n").splitlines() if v.strip()]
    return list(dict.fromkeys(villes))[:VILLES_MAX]


def _cle(request: Request) -> str:
    stockage = request.app.state.stockage
    with stockage.session() as s:
        try:
            return reglages.lire_cle_api(stockage, s, reglages.CLE_PLACES)
        except ErreurSecret:
            return ""


@routeur.get("/recherche", response_class=HTMLResponse)
async def page(request: Request):
    config = request.app.state.gestionnaire.config()
    return _page(request, "recherche.html", actif="recherche", cle=bool(_cle(request)), pages_max=config.places.pages_max)


@routeur.post("/recherche/estimation", response_class=HTMLResponse)
async def estimation(request: Request, secteur: str = Form(""), villes: str = Form(""), pages: int = Form(3)):
    liste = _villes(villes)
    if not secteur.strip() or not liste:
        return _page(request, "_estimation.html", erreur="Indiquez un secteur et au moins une ville.")
    config = request.app.state.gestionnaire.config().places
    return _page(
        request, "_estimation.html", secteur=secteur.strip(), villes=liste, pages=pages,
        estimation=places.estimer(liste, pages, config), tarifs=places.TARIFS, cle=bool(_cle(request)),
    )


@routeur.post("/recherche", response_class=HTMLResponse)
async def lancer(request: Request, secteur: str = Form(""), villes: str = Form(""), pages: int = Form(3)):
    liste = _villes(villes)
    if not secteur.strip() or not liste:
        return _page(request, "_apercu.html", erreur="Indiquez un secteur et au moins une ville.")
    config = request.app.state.gestionnaire.config().places
    try:
        resultat = await places.rechercher(_cle(request), secteur.strip(), liste, config, pages)
    except places.ErreurPlaces as e:
        return _page(request, "_apercu.html", erreur=str(e))
    ecartees = resultat.sans_site + resultat.pages_tierces + resultat.fermees
    if not resultat.prospects:
        return _page(
            request, "_apercu.html",
            erreur=f"Aucune fiche avec un site trouvée ({ecartees} fiche(s) sans site, avec une simple page tierce ou fermée).",
        )
    # Liste enregistrée comme un import : même aperçu, même lancement, même traçabilité
    stockage = request.app.state.stockage
    jeton = f"{secrets.token_hex(16)}.csv"
    with (stockage.dossier_imports / jeton).open("w", encoding="utf-8-sig", newline="") as f:
        ecrivain = csv.writer(f, delimiter=";")
        ecrivain.writerow(["nom", "url", "téléphone", "adresse", "ville", "catégorie", "note", "avis", "lien google maps"])
        for p in resultat.prospects:
            ecrivain.writerow([p.nom, p.url, p.telephone, p.adresse, p.ville, p.categorie,
                               "" if p.note_google is None else p.note_google, "" if p.nb_avis is None else p.nb_avis, p.lien_maps])
    source = f"Recherche Google Places « {secteur.strip()} » ({', '.join(liste)})"
    info = (
        f"{resultat.requetes} requête(s) effectuée(s) ; {ecartees} fiche(s) écartée(s) "
        "(sans site, simple page Facebook, Planity… ou établissement fermé)."
    )
    return apercu_import(
        request, jeton, f"{secteur.strip()} - {', '.join(liste)}.csv", FORMAT_PLACES, resultat.prospects,
        source=source, info=info,
    )
