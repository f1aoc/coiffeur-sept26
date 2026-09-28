"""Analyseur Navigateur : rendu Chromium (Playwright), captures et contrôles de page.

Isolation (§6.4) : un contexte neuf par site (ni cookies ni cache partagés),
téléchargements refusés, aucune permission accordée, service workers bloqués,
boîtes de dialogue fermées, bac à sable Chromium actif quand c'est possible.
Chaque page a 20 s au total pour se charger.
"""

from __future__ import annotations

import asyncio
import io
import os
import re
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

from chasseur import urls
from chasseur.analyzers.base import Analyseur
from chasseur.analyzers.page import PageInfo, evaluer_page, formulaires_utiles, liens_tel
from chasseur.config import Config
from chasseur.modeles import Prospect, Rapport
from chasseur.signatures import Signatures, charger_signatures

JETON_ROBOTS = "ChasseurDeSites"

JS_COLLECTE = """() => {
  const selecteurs = ['footer', '[role=contentinfo]', '#footer', '.footer', '#pied', '.pied-de-page', '#bas-de-page'];
  const vus = new Set();
  let pied = '';
  for (const s of selecteurs) for (const el of document.querySelectorAll(s)) {
    if (!vus.has(el)) { vus.add(el); pied += '\\n' + (el.innerText || ''); }
  }
  const texte = document.body ? (document.body.innerText || '') : '';
  pied += '\\n' + texte.slice(-800);
  let jq = '';
  try { jq = (window.jQuery && window.jQuery.fn && window.jQuery.fn.jquery) || ''; } catch (e) {}
  const liens = [...document.querySelectorAll('a[href]')].slice(0, 400)
    .map(a => ({href: a.href, texte: (a.innerText || a.title || '').trim().slice(0, 80)}));
  return {texte, pied, jq, liens};
}"""

JS_LARGEURS = """() => [
  Math.max(document.documentElement.scrollWidth, document.body ? document.body.scrollWidth : 0),
  document.documentElement.clientWidth
]"""  # innerWidth suit le dézoom automatique du mode mobile : clientWidth reste à 375 px


class ErreurNavigateur(RuntimeError):
    pass


def slug(texte: str) -> str:
    ascii_ = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", ascii_).strip("-")[:40] or "site"


def en_webp(png: bytes, chemin: Path, max_ko: int) -> int:
    """Convertit une capture PNG en WebP de moins de max_ko Ko ; renvoie la taille en octets."""
    from PIL import Image

    image = Image.open(io.BytesIO(png)).convert("RGB")
    limite = max_ko * 1024
    while True:
        for qualite in (80, 70, 60, 50, 40, 30):
            tampon = io.BytesIO()
            image.save(tampon, "WEBP", quality=qualite, method=4)
            if tampon.tell() <= limite:
                chemin.parent.mkdir(parents=True, exist_ok=True)
                chemin.write_bytes(tampon.getvalue())
                return tampon.tell()
        image = image.resize((max(1, int(image.width * 0.8)), max(1, int(image.height * 0.8))))


class AnalyseurNavigateur(Analyseur):
    nom = "navigateur"

    def __init__(
        self,
        config: Config,
        signatures: Signatures | None = None,
        maintenant: Callable[[], datetime] | None = None,
    ):
        super().__init__(config)
        self.signatures = signatures or charger_signatures()
        self._maintenant = maintenant or (lambda: datetime.now(timezone.utc))
        self._playwright = None
        self._navigateur = None
        self._user_agent = ""
        self._erreur_demarrage: ErreurNavigateur | None = None
        self._verrou = asyncio.Lock()
        self._places = asyncio.Semaphore(config.navigateur.simultanes)

    # --- Cycle de vie -----------------------------------------------------

    async def _demarrer(self):
        async with self._verrou:
            if self._navigateur is not None:
                return self._navigateur
            if self._erreur_demarrage is not None:  # inutile de réessayer pour chaque site
                raise self._erreur_demarrage
            try:
                from playwright.async_api import async_playwright
            except ImportError:
                raise ErreurNavigateur("Playwright n'est pas installé : pip install playwright") from None
            nav = self.config.navigateur
            chemin = nav.chromium or os.environ.get("CHASSEUR_CHROMIUM") or None
            en_root = hasattr(os, "geteuid") and os.geteuid() == 0  # le bac à sable refuse de démarrer en root
            self._playwright = await async_playwright().start()
            try:
                self._navigateur = await self._playwright.chromium.launch(
                    executable_path=chemin,
                    chromium_sandbox=nav.sandbox and not en_root,
                    args=["--disable-extensions", "--no-first-run", "--disable-background-networking", "--mute-audio"],
                )
            except Exception as e:
                await self._playwright.stop()
                self._playwright = None
                premiere_ligne = str(e).strip().splitlines()[0] if str(e).strip() else type(e).__name__
                self._erreur_demarrage = ErreurNavigateur(
                    f"Chromium ne démarre pas ({premiere_ligne}). Lancez « playwright install chromium » "
                    "ou renseignez navigateur.chromium dans config.yaml."
                )
                raise self._erreur_demarrage from None
            version = self._navigateur.version.split(".")[0]
            # §6.2 : user-agent explicite, avec le nom du logiciel.
            self._user_agent = (
                f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                f"Chrome/{version}.0.0.0 Safari/537.36 {JETON_ROBOTS}/0.2"
            )
            return self._navigateur

    async def fermer(self) -> None:
        if self._navigateur is not None:
            await self._navigateur.close()
            self._navigateur = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None

    # --- Analyse ----------------------------------------------------------

    async def analyser(self, prospect: Prospect, client: httpx.AsyncClient) -> Rapport:
        navigateur = await self._demarrer()
        async with self._places:
            return await self._analyser(navigateur, prospect, client)

    async def _analyser(self, navigateur, prospect: Prospect, client: httpx.AsyncClient) -> Rapport:
        from playwright.async_api import Error as ErreurPlaywright

        nav = self.config.navigateur
        erreurs = []
        for url in urls.candidates(prospect.url):
            if nav.respecter_robots and not await self._robots_autorise(url, client):
                return Rapport(
                    mesures={"robots_txt": "interdit"},
                    non_verifies=dict.fromkeys(self.controles, "robots.txt interdit l'analyse"),
                )
            bureau = await navigateur.new_context(**self._options_contexte(mobile=False))
            try:
                try:
                    page, reponse = await self._ouvrir(bureau, url)
                except ErreurPlaywright as e:
                    erreurs.append(f"{url} : {str(e).splitlines()[0][:200]}")
                    continue
                info = await self._collecter(page, reponse, url, prospect, bureau)
            finally:
                await bureau.close()
            await self._mobile(navigateur, info, prospect)
            return evaluer_page(info, self.config, self.signatures, self._maintenant())
        raise ErreurNavigateur("page inaccessible dans le navigateur : " + " ; ".join(erreurs))

    def _options_contexte(self, mobile: bool) -> dict:
        nav = self.config.navigateur
        options = dict(
            user_agent=self._user_agent,
            accept_downloads=False,
            ignore_https_errors=True,  # le certificat est jugé par l'analyseur Réseau
            service_workers="block",
            permissions=[],
            locale="fr-FR",
            timezone_id="Europe/Paris",
        )
        if mobile:
            options.update(
                viewport={"width": nav.largeur_mobile, "height": nav.hauteur_mobile},
                is_mobile=True,
                has_touch=True,
                device_scale_factor=1,
                user_agent=self._user_agent.replace("(Windows NT 10.0; Win64; x64)", "(Linux; Android 14; Pixel 8)")
                .replace("Safari/537.36", "Mobile Safari/537.36"),
            )
        else:
            options.update(viewport={"width": nav.largeur_bureau, "height": nav.hauteur_bureau})
        return options

    async def _ouvrir(self, contexte, url: str):
        """Charge une page en 20 s maximum au total (chargement + stabilisation)."""
        from playwright.async_api import TimeoutError as DelaiPlaywright

        budget = self.config.navigateur.timeout_page * 1000
        debut = time.monotonic()
        restant = lambda: max(1.0, budget - (time.monotonic() - debut) * 1000)  # noqa: E731

        page = await contexte.new_page()
        page.set_default_timeout(budget)
        page.on("dialog", lambda d: asyncio.ensure_future(d.dismiss()))
        reponse = await page.goto(url, wait_until="domcontentloaded", timeout=budget)
        for etat, plafond in (("load", budget), ("networkidle", 3000)):
            try:
                await page.wait_for_load_state(etat, timeout=min(plafond, restant()))
            except DelaiPlaywright:
                pass
        return page, reponse

    async def _contenu(self, page) -> str:
        return await self._reessayer(page, page.content, "")

    async def _reessayer(self, page, action, defaut):
        """Une redirection JavaScript peut être en cours : on laisse la page se stabiliser."""
        from playwright.async_api import Error as ErreurPlaywright

        for essai in range(3):
            try:
                return await action()
            except ErreurPlaywright:
                if essai == 2:
                    if defaut is not None:
                        return defaut
                    raise
                try:
                    await page.wait_for_load_state("load", timeout=5000)
                except ErreurPlaywright:
                    await page.wait_for_timeout(500)

    async def _collecter(self, page, reponse, url: str, prospect: Prospect, contexte) -> PageInfo:
        donnees = await self._reessayer(page, lambda: page.evaluate(JS_COLLECTE), None)
        html = await self._contenu(page)
        info = PageInfo(
            url_demandee=url,
            url_finale=page.url,
            statut_http=reponse.status if reponse else None,
            html=html,
            texte_visible=donnees["texte"],
            texte_pied=donnees["pied"],
            version_jquery_js=donnees["jq"],
        )
        info.captures["capture_bureau"] = await self._capturer(page, prospect, "bureau")
        info.captures["capture_date"] = self._maintenant().strftime("%Y-%m-%d %H:%M:%S")

        soup = BeautifulSoup(html, "html.parser")
        if self.config.navigateur.page_contact and not (formulaires_utiles(soup) and liens_tel(soup)):
            await self._visiter_contact(contexte, info, donnees["liens"])
        return info

    async def _visiter_contact(self, contexte, info: PageInfo, liens: list[dict]) -> None:
        from playwright.async_api import Error as ErreurPlaywright

        hote = urls.hote(info.url_finale) or ""
        for lien in liens:
            href = lien.get("href", "")
            if not href.startswith(("http://", "https://")) or href.split("#")[0] == info.url_finale.split("#")[0]:
                continue
            if not urls.meme_site(urls.hote(href) or "", hote):
                continue
            chemin = urlsplit(href).path
            if any(p.search(lien.get("texte", "")) or p.search(chemin) for p in self.signatures.page_contact):
                try:
                    page, _ = await self._ouvrir(contexte, href)
                    soup = BeautifulSoup(await self._contenu(page), "html.parser")
                except ErreurPlaywright:
                    return
                info.url_contact = href
                info.contact_formulaire = formulaires_utiles(soup) > 0
                info.contact_tel = liens_tel(soup) > 0
                return

    async def _mobile(self, navigateur, info: PageInfo, prospect: Prospect) -> None:
        from playwright.async_api import Error as ErreurPlaywright

        mobile = await navigateur.new_context(**self._options_contexte(mobile=True))
        try:
            page, _ = await self._ouvrir(mobile, info.url_finale)
            info.largeur_contenu_mobile, info.largeur_fenetre_mobile = await page.evaluate(JS_LARGEURS)
            info.captures["capture_mobile"] = await self._capturer(page, prospect, "mobile")
        except ErreurPlaywright:
            pass  # le bureau a fonctionné : on garde ses résultats, la mesure mobile reste vide
        finally:
            await mobile.close()

    async def _capturer(self, page, prospect: Prospect, format_: str) -> str:
        nav = self.config.navigateur
        horodatage = self._maintenant().strftime("%Y%m%d-%H%M%S")
        nom = slug(prospect.nom or urls.hote(prospect.url) or "site")
        chemin = Path(nav.dossier_captures) / f"{prospect.ligne:04d}-{nom}-{horodatage}-{format_}.webp"
        png = await page.screenshot(type="png", timeout=nav.timeout_page * 1000)
        await asyncio.to_thread(en_webp, png, chemin, nav.capture_max_ko)
        return str(chemin)

    async def _robots_autorise(self, url: str, client: httpx.AsyncClient) -> bool:
        parties = urlsplit(url)
        try:
            r = await client.get(
                urljoin(f"{parties.scheme}://{parties.netloc}", "/robots.txt"),
                timeout=min(10.0, self.config.timeout),
                follow_redirects=True,
            )
        except httpx.HTTPError:
            return True
        if r.status_code >= 400 or "html" in r.headers.get("content-type", ""):
            return True  # pas de robots.txt exploitable : tout est permis
        robots = RobotFileParser()
        robots.parse(r.text.splitlines())
        return robots.can_fetch(JETON_ROBOTS, url)
