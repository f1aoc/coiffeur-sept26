"""Application web locale (FastAPI + HTMX), en français.

Sécurité (§6.4) :
- écoute sur 127.0.0.1 par défaut (voir `chasseur web`) ;
- en-tête Host vérifié (protège contre le « DNS rebinding ») ;
- requêtes POST refusées si elles viennent d'une autre origine (protection CSRF :
  une page web malveillante ne peut pas piloter l'application).
"""

from __future__ import annotations

import asyncio
import logging
import mimetypes
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.trustedhost import TrustedHostMiddleware

from chasseur import __version__, planification, rgpd
from chasseur import licence as lic
from chasseur.journal import configurer as configurer_journal
from chasseur.bonus import a_bonus
from chasseur.config import charger_config
from chasseur.controles import CONTROLES, libelle
from chasseur.db.moteur import Stockage
from chasseur.db.tables import LIBELLES_SCAN, STATUTS_COMMERCIAUX, heure_locale
from chasseur.reports.pdf import MoteurPDF
from chasseur.web.taches import GestionnaireScans

# Sous Windows, le type des fichiers vient du registre, qui ignore souvent .webp (captures)
mimetypes.add_type("image/webp", ".webp")

ICI = Path(__file__).resolve().parent
journal = logging.getLogger("chasseur.web")
HOTES_LOCAUX = ["127.0.0.1", "localhost"]
METHODES_SURES = {"GET", "HEAD", "OPTIONS"}

CLASSES_ETATS = {
    "Cassé": "casse",
    "Obsolète": "obsolete",
    "Correct": "correct",
    "Sans site": "sans-site",
    "À revérifier": "a-reverifier",
}


def classe_etat(etat: str) -> str:
    return CLASSES_ETATS.get(etat or "", "attente")


def duree(secondes: float | None) -> str:
    if secondes is None:
        return "—"
    secondes = int(round(secondes))
    if secondes < 60:
        return f"{secondes} s"
    minutes, s = divmod(secondes, 60)
    if minutes < 60:
        return f"{minutes} min {s:02d} s"
    heures, minutes = divmod(minutes, 60)
    return f"{heures} h {minutes:02d} min"


def date_fr(d) -> str:
    return heure_locale(d).strftime("%d/%m/%Y à %H:%M") if d else "—"


def heure(d) -> str:
    return heure_locale(d).strftime("%H:%M:%S") if d else ""


def creer_templates() -> Jinja2Templates:
    templates = Jinja2Templates(directory=ICI / "templates")
    env = templates.env
    env.filters["classe_etat"] = classe_etat
    env.filters["duree"] = duree
    env.filters["date_fr"] = date_fr
    env.filters["heure"] = heure
    env.filters["libelle"] = libelle
    env.globals.update(
        a_bonus=a_bonus,
        STATUTS=STATUTS_COMMERCIAUX,
        LIBELLES_SCAN=LIBELLES_SCAN,
        CONTROLES=CONTROLES,
        VERSION=__version__,
    )
    return templates


def entretenir(
    stockage: Stockage, gestionnaire: GestionnaireScans, purge: bool, licence_active: bool = True
) -> tuple[int, list[int]]:
    """Purge RGPD (si demandée) et lancement des relances planifiées dues ; renvoie (purgés, scans lancés).

    Sans licence active, la purge continue (protection des données) mais aucune relance n'est lancée."""
    purges, lances = 0, []
    with stockage.session() as s:
        if purge:
            purges = rgpd.purger(stockage, s)
            if purges:
                journal.warning("purge automatique : %s prospect(s) non contacté(s) supprimé(s)", purges)
        for scan in planification.scans_dus(s) if licence_active else []:
            if any(gestionnaire.en_cours(x.id) for x in planification.serie(s, scan)):
                continue  # la relance précédente n'est pas finie
            lances.append(planification.creer_relance(s, scan).id)
    for scan_id in lances:
        gestionnaire.lancer(scan_id)
    return purges, lances


async def boucle_entretien(
    stockage: Stockage, gestionnaire: GestionnaireScans, intervalle: float, licence: lic.Licence
) -> None:
    """Toutes les `intervalle` secondes : licence (au démarrage puis toutes les 24 h), relances planifiées ;
    une fois par jour : purge."""
    derniere_purge = 0.0
    premier_tour = True
    while True:
        try:
            if premier_tour or licence.verification_due():
                await asyncio.to_thread(licence.verifier)
            premier_tour = False
            boucle = asyncio.get_running_loop()
            purge = boucle.time() - derniere_purge > 24 * 3600 or not derniere_purge
            entretenir(stockage, gestionnaire, purge, licence.etat().utilisable)
            if purge:
                derniere_purge = boucle.time()
        except Exception as e:  # noqa: BLE001 — l'entretien ne doit jamais arrêter l'application
            journal.error("entretien : %s %s", type(e).__name__, e)
        await asyncio.sleep(intervalle)


def creer_app(
    stockage: Stockage | None = None,
    gestionnaire: GestionnaireScans | None = None,
    chemin_config: str | Path | None = None,
    hotes: list[str] | None = None,
    intervalle_entretien: float = 300,
    licence: lic.Licence | None = None,
) -> FastAPI:
    stockage = stockage or Stockage()
    licence = licence or lic.licence_par_defaut(stockage.dossier)
    fichier_journal = configurer_journal(stockage.dossier)
    gestionnaire = gestionnaire or GestionnaireScans(stockage, chemin_config=chemin_config)

    moteurs: list[MoteurPDF] = []

    def moteur_pdf() -> MoteurPDF:
        """Moteur PDF créé au premier rapport, réutilisé ensuite (Chromium reste ouvert)."""
        if not moteurs:
            try:
                chromium = charger_config(chemin_config).navigateur.chromium or None
            except Exception:
                chromium = None
            moteurs.append(MoteurPDF(chromium=chromium))
        return moteurs[0]

    @asynccontextmanager
    async def cycle_de_vie(app: FastAPI):
        gestionnaire.au_demarrage()
        entretien = asyncio.get_running_loop().create_task(boucle_entretien(stockage, gestionnaire, intervalle_entretien, licence))
        yield
        entretien.cancel()
        await gestionnaire.arreter()
        for m in moteurs:
            await m.fermer()

    app = FastAPI(title="Chasseur de sites", version=__version__, lifespan=cycle_de_vie, docs_url=None, redoc_url=None)
    app.state.stockage = stockage
    app.state.gestionnaire = gestionnaire
    app.state.templates = creer_templates()
    app.state.chemin_config = chemin_config
    app.state.moteur_pdf = moteur_pdf
    app.state.fichier_journal = fichier_journal
    app.state.licence = licence
    app.state.templates.env.globals["licence"] = licence.etat

    @app.exception_handler(Exception)
    async def erreur_interne(request: Request, exc: Exception):
        journal.error("erreur sur %s %s : %s %s", request.method, request.url.path, type(exc).__name__, exc)
        return PlainTextResponse(
            "Une erreur inattendue s'est produite. Elle est notée dans le journal (page « À propos »).", status_code=500
        )

    hotes_autorises = hotes or HOTES_LOCAUX

    @app.middleware("http")
    async def meme_origine(request: Request, suivant):
        if request.method not in METHODES_SURES:
            origine = request.headers.get("origin") or request.headers.get("referer")
            if origine and urlsplit(origine).netloc != request.headers.get("host"):
                return PlainTextResponse("Requête refusée : elle ne vient pas de l'application.", status_code=403)
        return await suivant(request)

    from chasseur.web.routes_licence import chemin_libre, refus

    @app.middleware("http")
    async def controle_licence(request: Request, suivant):
        if not chemin_libre(request.method, request.url.path) and not licence.etat().utilisable:
            return refus(request)
        return await suivant(request)

    app.add_middleware(TrustedHostMiddleware, allowed_hosts=hotes_autorises)

    stockage.dossier_captures.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=ICI / "static"), name="static")
    app.mount("/captures", StaticFiles(directory=stockage.dossier_captures), name="captures")

    from chasseur.web import (
        routes_analyses,
        routes_conformite,
        routes_licence,
        routes_rapports,
        routes_recherche,
        routes_reglages,
        routes_resultats,
    )

    app.include_router(routes_licence.routeur)
    app.include_router(routes_recherche.routeur)
    app.include_router(routes_conformite.routeur)
    app.include_router(routes_rapports.routeur)
    app.include_router(routes_analyses.routeur)
    app.include_router(routes_resultats.routeur)
    app.include_router(routes_reglages.routeur)

    @app.get("/", include_in_schema=False)
    async def accueil():
        return RedirectResponse("/analyses", status_code=303)

    return app
