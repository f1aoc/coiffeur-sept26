"""Analyseur Domaine : date d'expiration (RDAP, repli python-whois) et pages de parking."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

import httpx
from bs4 import BeautifulSoup

from chasseur import urls
from chasseur.analyzers.base import Analyseur
from chasseur.config import Config
from chasseur.modeles import Prospect, Rapport
from chasseur.signatures import Signatures, charger_signatures, hote_dans

TAILLE_HTML_MAX = 500_000


@dataclass
class InfoExpiration:
    expire_le: datetime | None = None
    enregistre: bool | None = None  # False = le registre dit que le domaine n'existe pas
    source: str = ""
    detail: str = ""


class ExpirationInconnue(Exception):
    pass


def _date_iso(texte: str) -> datetime | None:
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", texte or "")
    return datetime(int(m[1]), int(m[2]), int(m[3]), tzinfo=timezone.utc) if m else None


def whois_expiration(domaine: str) -> InfoExpiration:
    """Repli python-whois (bloquant : appelé dans un thread)."""
    import whois
    from whois import exceptions as exc

    introuvable = tuple(
        e for e in (getattr(exc, "WhoisDomainNotFoundError", None),) if e is not None
    )
    try:
        w = whois.whois(domaine, quiet=True)
    except introuvable:
        return InfoExpiration(enregistre=False, source="whois", detail="domaine introuvable")
    except exc.PywhoisError as e:
        message = str(e).lower()
        if any(m in message for m in ("no match", "not found", "no entries", "no data found", "status: free")):
            return InfoExpiration(enregistre=False, source="whois", detail=str(e).splitlines()[0][:200])
        raise ExpirationInconnue(f"whois : {str(e).splitlines()[0][:200]}") from None

    date = w.get("expiration_date")
    if isinstance(date, list):
        date = min((d for d in date if isinstance(d, datetime)), default=None)
    if isinstance(date, datetime):
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
        return InfoExpiration(expire_le=date, enregistre=True, source="whois")
    raise ExpirationInconnue("whois : pas de date d'expiration dans la réponse")


class AnalyseurDomaine(Analyseur):
    nom = "domaine"

    def __init__(
        self,
        config: Config,
        signatures: Signatures | None = None,
        whois_fn: Callable[[str], InfoExpiration] | None = None,
        maintenant: Callable[[], datetime] | None = None,
    ):
        super().__init__(config)
        self.signatures = signatures or charger_signatures()
        self._whois_fn = whois_fn
        self._maintenant = maintenant or (lambda: datetime.now(timezone.utc))

    async def analyser(self, prospect: Prospect, client: httpx.AsyncClient) -> Rapport:
        hote = urls.hote(prospect.url)
        racine = urls.domaine_racine(hote)
        rapport = Rapport(mesures={"domaine": racine})
        expiration_ok, parking_ok = await asyncio.gather(
            self._expiration(racine, client, rapport),
            self._parking(prospect.url, client, rapport),
        )
        if not expiration_ok and not parking_ok:
            rapport.non_verifies.setdefault("domaine", "ni l'expiration ni le parking n'ont pu être vérifiés")
        return rapport

    # --- Expiration -------------------------------------------------------

    async def _expiration(self, racine: str, client: httpx.AsyncClient, rapport: Rapport) -> bool:
        cfg = self.config.domaine
        if not urls.domaine_enregistrable(racine):
            rapport.non_verifies["domaine_expiration"] = "pas un nom de domaine public"
            return False
        erreurs: list[str] = []
        info: InfoExpiration | None = None
        try:
            info = await self._rdap(racine, client)
        except ExpirationInconnue as e:
            erreurs.append(str(e))
        concluant = info is not None and (info.expire_le is not None or info.enregistre is False)
        if not concluant:
            if info is not None:
                erreurs.append(f"RDAP : {info.detail}")
            if cfg.whois_actif:
                try:
                    whois_fn = self._whois_fn or whois_expiration
                    info = await asyncio.wait_for(asyncio.to_thread(whois_fn, racine), cfg.timeout)
                    concluant = info.expire_le is not None or info.enregistre is False
                except (ExpirationInconnue, asyncio.TimeoutError, OSError) as e:
                    erreurs.append(str(e) or f"whois : {type(e).__name__}")
        if not concluant:
            rapport.non_verifies["domaine_expiration"] = " ; ".join(erreurs) or "date d'expiration introuvable"
            return False

        if info.enregistre is False:
            rapport.append(
                self.config.constat(
                    "DOMAINE_NON_ENREGISTRE",
                    "Votre nom de domaine n'est plus enregistré : n'importe qui peut le racheter, "
                    "et votre site comme vos e-mails ne fonctionnent plus.",
                    f"{racine} : inconnu du registre ({info.source}{' : ' + info.detail if info.detail else ''})",
                )
            )
            return True

        rapport.mesures["domaine_expire_le"] = info.expire_le.strftime("%Y-%m-%d")
        rapport.mesures["domaine_source"] = info.source
        jours = (info.expire_le - self._maintenant()).days
        date = info.expire_le.strftime("%d/%m/%Y")
        if jours < 0:
            rapport.append(
                self.config.constat(
                    "DOMAINE_EXPIRE",
                    f"Votre nom de domaine a expiré le {date} : votre site et vos e-mails risquent de "
                    "s'arrêter et le domaine peut être racheté par un tiers.",
                    f"{racine} : date d'expiration {date} ({info.source})",
                )
            )
        elif jours < cfg.alerte_jours:
            rapport.append(
                self.config.constat(
                    "DOMAINE_EXPIRE_BIENTOT",
                    f"Votre nom de domaine expire le {date} (dans {jours} jour(s)) : sans renouvellement, "
                    "votre site et vos e-mails s'arrêteront.",
                    f"{racine} : date d'expiration {date} ({info.source})",
                )
            )
        return True

    async def _rdap(self, racine: str, client: httpx.AsyncClient) -> InfoExpiration:
        cfg = self.config.domaine
        try:
            r = await client.get(
                cfg.rdap_url.format(domaine=racine),
                timeout=cfg.timeout,
                follow_redirects=True,
                headers={"Accept": "application/rdap+json, application/json"},
            )
        except httpx.HTTPError as e:
            raise ExpirationInconnue(f"RDAP : {type(e).__name__}") from None
        if r.status_code == 404:
            # 404 = domaine inconnu OU extension non couverte par RDAP : confirmation par whois.
            return InfoExpiration(source="rdap", detail="RDAP 404")
        if r.status_code >= 400:
            raise ExpirationInconnue(f"RDAP : HTTP {r.status_code}")
        try:
            donnees = r.json()
        except ValueError:
            raise ExpirationInconnue("RDAP : réponse illisible") from None
        for evenement in donnees.get("events") or []:
            if str(evenement.get("eventAction", "")).lower() == "expiration":
                date = _date_iso(str(evenement.get("eventDate", "")))
                if date:
                    return InfoExpiration(expire_le=date, enregistre=True, source="rdap")
        return InfoExpiration(enregistre=True, source="rdap", detail="pas de date d'expiration")

    # --- Parking ----------------------------------------------------------

    async def _parking(self, url: str, client: httpx.AsyncClient, rapport: Rapport) -> bool:
        sig = self.signatures
        hote_origine = urls.hote(url)
        reponse = None
        for candidat in urls.candidates(url):
            try:
                reponse = await client.get(candidat, timeout=self.config.timeout, follow_redirects=True)
                break
            except httpx.HTTPError:
                continue
        if reponse is None:
            rapport.mesures["parking"] = "non vérifié (page d'accueil injoignable)"
            return False

        chaine = [str(r.url) for r in reponse.history] + [str(reponse.url)]
        for etape in chaine:
            h = urls.hote(etape) or ""
            if h and not urls.meme_site(h, hote_origine) and hote_dans(h, sig.parking_services):
                rapport.append(self._constat_parking(f"redirection vers un service de parking : {' → '.join(chaine)}"))
                return True

        html = reponse.text[:TAILLE_HTML_MAX]
        for motif in sig.parking_motifs_html:
            if m := motif.search(html):
                rapport.append(self._constat_parking(f"{reponse.url} : ressource de parking « {m[0][:80]} »"))
                return True
        texte = " ".join(BeautifulSoup(html, "html.parser").get_text(" ").split())
        for motif in sig.parking_phrases:
            if m := motif.search(texte):
                rapport.append(self._constat_parking(f"{reponse.url} : texte « {m[0][:80]} »"))
                return True
        return True

    def _constat_parking(self, preuve: str):
        return self.config.constat(
            "DOMAINE_PARKING",
            "Votre adresse web affiche une page publicitaire « domaine à vendre » au lieu de votre site : "
            "vos clients ne vous trouvent plus.",
            preuve,
        )
