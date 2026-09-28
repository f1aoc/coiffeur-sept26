"""Écrans « Nouvelle analyse » et « Progression »."""

from __future__ import annotations

import re
import secrets
from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse

from chasseur.db import depot
from chasseur.db.tables import EN_ATTENTE, EN_COURS, EN_PAUSE, Scan
from chasseur.importers import FORMAT_GENERIQUE, ErreurImport, lire_prospects

routeur = APIRouter()

TAILLE_MAX = 20 * 1024 * 1024
EXTENSIONS = {".csv", ".txt", ".xlsx"}
RE_JETON = re.compile(r"^[0-9a-f]{32}\.(csv|txt|xlsx)$")
APERCU = 10


def _page(request: Request, gabarit: str, **contexte):
    return request.app.state.templates.TemplateResponse(request, gabarit, contexte)


@routeur.get("/analyses", response_class=HTMLResponse)
async def liste(request: Request):
    stockage = request.app.state.stockage
    with stockage.session() as s:
        lignes = [(scan, depot.compteurs(s, scan.id)) for scan in depot.scans(s)]
    return _page(request, "analyses.html", actif="analyses", lignes=lignes)


@routeur.get("/analyses/nouvelle", response_class=HTMLResponse)
async def nouvelle(request: Request):
    return _page(request, "nouvelle.html", actif="nouvelle")


@routeur.post("/analyses/apercu", response_class=HTMLResponse)
async def apercu(request: Request, fichier: UploadFile):
    stockage = request.app.state.stockage
    extension = Path(fichier.filename or "").suffix.lower()
    if extension not in EXTENSIONS:
        return _page(request, "_apercu.html", erreur="Choisissez un fichier CSV ou Excel (.csv, .xlsx).")
    contenu = await fichier.read(TAILLE_MAX + 1)
    if len(contenu) > TAILLE_MAX:
        return _page(request, "_apercu.html", erreur="Fichier trop volumineux (20 Mo maximum).")
    jeton = f"{secrets.token_hex(16)}{extension}"
    chemin = stockage.dossier_imports / jeton
    chemin.write_bytes(contenu)
    try:
        resultat = lire_prospects(chemin)
    except ErreurImport as e:
        chemin.unlink(missing_ok=True)
        return _page(request, "_apercu.html", erreur=str(e))
    if not resultat.prospects:
        chemin.unlink(missing_ok=True)
        return _page(request, "_apercu.html", erreur="Le fichier ne contient aucune entreprise.")
    avec_site = sum(1 for p in resultat.prospects if p.url)
    return _page(
        request,
        "_apercu.html",
        jeton=jeton,
        nom_fichier=fichier.filename,
        nom=Path(fichier.filename or "Analyse").stem,
        format=resultat.format,
        format_maps=resultat.format != FORMAT_GENERIQUE,
        total=len(resultat.prospects),
        avec_site=avec_site,
        lignes=resultat.prospects[:APERCU],
    )


@routeur.post("/analyses")
async def lancer(request: Request, jeton: str = Form(...), nom: str = Form(""), nom_fichier: str = Form("")):
    if not RE_JETON.match(jeton):
        raise HTTPException(400, "Fichier d'import invalide")
    stockage = request.app.state.stockage
    chemin = stockage.dossier_imports / jeton
    if not chemin.is_file():
        raise HTTPException(400, "Fichier d'import expiré : déposez-le à nouveau")
    resultat = lire_prospects(chemin)
    with stockage.session() as s:
        scan = depot.creer_scan(
            s, nom.strip() or Path(nom_fichier).stem or "Analyse", resultat.prospects,
            fichier=nom_fichier or jeton, format_=resultat.format,
        )
    request.app.state.gestionnaire.lancer(scan.id)
    return RedirectResponse(f"/analyses/{scan.id}", status_code=303)


def _etat_progression(request: Request, scan_id: int) -> dict:
    stockage = request.app.state.stockage
    gestionnaire = request.app.state.gestionnaire
    with stockage.session() as s:
        scan = s.get(Scan, scan_id)
        if scan is None:
            raise HTTPException(404, "Analyse introuvable")
        compte = depot.compteurs(s, scan_id)
    faits, total = compte["faits"], scan.total
    en_marche = scan.statut in (EN_ATTENTE, EN_COURS, EN_PAUSE) and gestionnaire.en_cours(scan_id)
    autres = faits - sum(compte.get(e, 0) for e in ("Cassé", "Obsolète", "Correct"))
    return dict(
        scan=scan,
        faits=faits,
        total=total,
        pourcentage=round(100 * faits / total) if total else 100,
        casses=compte.get("Cassé", 0),
        obsoletes=compte.get("Obsolète", 0),
        corrects=compte.get("Correct", 0),
        autres=autres,
        restant=gestionnaire.restant(scan_id, total - faits) if en_marche else None,
        en_marche=en_marche,
        en_pause=scan.statut == EN_PAUSE,
    )


@routeur.get("/analyses/{scan_id}", response_class=HTMLResponse)
async def progression(request: Request, scan_id: int):
    return _page(request, "progression.html", actif="analyses", **_etat_progression(request, scan_id))


@routeur.get("/analyses/{scan_id}/progression", response_class=HTMLResponse)
async def progression_fragment(request: Request, scan_id: int):
    return _page(request, "_progression.html", **_etat_progression(request, scan_id))


@routeur.post("/analyses/{scan_id}/pause", response_class=HTMLResponse)
async def pause(request: Request, scan_id: int):
    request.app.state.gestionnaire.pause(scan_id)
    return _page(request, "_progression.html", **_etat_progression(request, scan_id))


@routeur.post("/analyses/{scan_id}/reprendre", response_class=HTMLResponse)
async def reprendre(request: Request, scan_id: int):
    _etat_progression(request, scan_id)  # 404 si inconnu
    request.app.state.gestionnaire.reprendre(scan_id)
    return _page(request, "_progression.html", **_etat_progression(request, scan_id))
