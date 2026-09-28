"""Rapport PDF par prospect (2 pages), gabarit HTML Jinja2.

Moteur de rendu :
- WeasyPrint (cahier des charges §5) quand il est installé et fonctionnel ;
- sinon Chromium (Playwright), déjà présent pour les captures : sous Windows,
  WeasyPrint demande d'installer GTK/Pango à la main.
Variable CHASSEUR_MOTEUR_PDF = auto (défaut) | weasyprint | chromium.

Le HTML ne charge rien de l'extérieur : captures et logo y sont intégrés.
"""

from __future__ import annotations

import asyncio
import base64
import io
import os
import re
import unicodedata
import zipfile
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from chasseur.db.agence import Agence, logo_data_uri
from chasseur.db.moteur import Stockage
from chasseur.db.tables import heure_locale
from chasseur.reports.donnees import Diagnostic
from chasseur.reports.textes import date_longue

GABARITS = Path(__file__).resolve().parent / "templates"
_env = Environment(loader=FileSystemLoader(GABARITS), autoescape=select_autoescape(["html"]))

COULEURS_ETATS = {
    "Cassé": ("#b42318", "#fdecea"),
    "Obsolète": ("#a15c00", "#fff4e0"),
    "Correct": ("#1e7a3c", "#e6f4ea"),
}


class ErreurPDF(RuntimeError):
    pass


# --- HTML ------------------------------------------------------------------------------


def _rgb(couleur: str) -> tuple[int, int, int]:
    c = couleur.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def couleur_texte(couleur: str) -> str:
    """Texte blanc ou foncé selon la clarté de la couleur de l'agence (lisibilité)."""
    r, g, b = _rgb(couleur)
    return "#1c2330" if (0.299 * r + 0.587 * g + 0.114 * b) > 160 else "#ffffff"


def eclaircir(couleur: str, part: float = 0.88) -> str:
    r, g, b = _rgb(couleur)
    return "#" + "".join(f"{round(v + (255 - v) * part):02x}" for v in (r, g, b))


def _image(stockage: Stockage, relatif: str) -> str:
    chemin = stockage.absolu(relatif) if relatif else None
    if not chemin or not chemin.is_file():
        return ""
    type_mime = "image/webp" if chemin.suffix == ".webp" else "image/png"
    return f"data:{type_mime};base64,{base64.b64encode(chemin.read_bytes()).decode()}"


def html_rapport(stockage: Stockage, d: Diagnostic, agence: Agence, aujourd_hui: datetime | None = None) -> str:
    p = d.prospect
    date_analyse = heure_locale(p.analyse_le) or aujourd_hui or datetime.now()
    bureau, mobile = d.captures.get("bureau"), d.captures.get("mobile")
    prise = heure_locale(bureau.prise_le) if bureau and bureau.prise_le else None
    couleur_etat, fond_etat = COULEURS_ETATS.get(p.etat, ("#4a5361", "#eceff3"))
    return _env.get_template("rapport.html").render(
        p=p,
        d=d,
        agence=agence,
        logo=logo_data_uri(stockage, agence),
        date=date_longue(date_analyse.strftime("%Y-%m-%d")),
        prise_le=f"{date_longue(prise.strftime('%Y-%m-%d'))} à {prise:%H:%M}" if prise else "",
        capture_bureau=_image(stockage, bureau.chemin) if bureau else "",
        capture_mobile=_image(stockage, mobile.chemin) if mobile else "",
        couleur=agence.couleur,
        couleur_texte=couleur_texte(agence.couleur),
        couleur_claire=eclaircir(agence.couleur),
        couleur_etat=couleur_etat,
        fond_etat=fond_etat,
    )


def nom_fichier(p) -> str:
    base = unicodedata.normalize("NFKD", p.nom or p.url or "prospect").encode("ascii", "ignore").decode().lower()
    return f"diagnostic-{re.sub(r'[^a-z0-9]+', '-', base).strip('-')[:60] or 'prospect'}.pdf"


# --- Moteurs -------------------------------------------------------------------------------


def weasyprint_disponible() -> bool:
    try:
        import weasyprint  # noqa: F401  (échoue sous Windows sans GTK/Pango)
    except Exception:
        return False
    return True


class MoteurPDF:
    """Transforme le HTML en PDF ; garde Chromium ouvert entre deux rapports (génération groupée)."""

    def __init__(self, moteur: str | None = None, chromium: str | None = None):
        choix = (moteur or os.environ.get("CHASSEUR_MOTEUR_PDF") or "auto").lower()
        if choix == "auto":
            choix = "weasyprint" if weasyprint_disponible() else "chromium"
        if choix not in ("weasyprint", "chromium"):
            raise ErreurPDF(f"Moteur PDF inconnu : {choix}")
        self.nom = choix
        self._chromium = chromium or os.environ.get("CHASSEUR_CHROMIUM") or None
        self._playwright = None
        self._navigateur = None
        self._verrou = asyncio.Lock()

    async def pdf(self, html: str) -> bytes:
        if self.nom == "weasyprint":
            return await asyncio.to_thread(self._weasyprint, html)
        return await self._pdf_chromium(html)

    @staticmethod
    def _weasyprint(html: str) -> bytes:
        from weasyprint import HTML
        from weasyprint import urls

        # Rien n'est chargé de l'extérieur : seules les images intégrées (data:) sont lues.
        if hasattr(urls, "URLFetcher"):  # WeasyPrint ≥ 66
            recuperateur = urls.URLFetcher(allowed_protocols=["data"])
        else:  # pragma: no cover — anciennes versions

            def recuperateur(url, *args, **kwargs):
                if url.startswith("data:"):
                    return urls.default_url_fetcher(url, *args, **kwargs)
                raise ValueError(f"ressource externe refusée : {url[:80]}")

        return HTML(string=html, url_fetcher=recuperateur).write_pdf()

    async def _pdf_chromium(self, html: str) -> bytes:
        async with self._verrou:
            if self._navigateur is None:
                from playwright.async_api import async_playwright

                self._playwright = await async_playwright().start()
                try:
                    self._navigateur = await self._playwright.chromium.launch(executable_path=self._chromium)
                except Exception as e:
                    await self._playwright.stop()
                    self._playwright = None
                    raise ErreurPDF(
                        "Chromium ne démarre pas pour créer le PDF : lancez « playwright install chromium ». "
                        f"({str(e).splitlines()[0][:150]})"
                    ) from None
        contexte = await self._navigateur.new_context(java_script_enabled=False, offline=True)
        try:
            page = await contexte.new_page()
            await page.set_content(html, wait_until="load")
            return await page.pdf(format="A4", print_background=True, prefer_css_page_size=True)
        finally:
            await contexte.close()

    async def fermer(self) -> None:
        if self._navigateur is not None:
            await self._navigateur.close()
            self._navigateur = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None


def zip_rapports(rapports: list[tuple[str, bytes]]) -> bytes:
    """ZIP de plusieurs rapports ; noms dédoublonnés (deux « Salon Léa » → -2)."""
    tampon, vus = io.BytesIO(), {}
    with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED) as z:
        for nom, contenu in rapports:
            n = vus[nom] = vus.get(nom, 0) + 1
            z.writestr(nom if n == 1 else nom.replace(".pdf", f"-{n}.pdf"), contenu)
    return tampon.getvalue()
