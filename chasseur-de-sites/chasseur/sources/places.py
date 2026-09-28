"""Recherche « secteur + ville » via l'API officielle Google Places (Text Search, API « New »).

Aucun scraping de Google Maps (§6.2) : uniquement l'API, avec la clé et le quota
de l'utilisateur. On ne garde que les fiches qui ont un vrai site (ni aucun site,
ni une simple page Facebook, Planity… : celles-là relèvent de l'outil Google Maps
existant, qui cherche justement les entreprises sans site).
"""

from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass, field
from urllib.parse import urlsplit

import httpx

from chasseur.config import ConfigPlaces
from chasseur.importers.fichiers import ville_depuis_adresse
from chasseur.modeles import Prospect

API = "https://places.googleapis.com/v1/places:searchText"
PAR_PAGE = 20
CHAMPS = [
    "places.id", "places.displayName", "places.formattedAddress", "places.nationalPhoneNumber",
    "places.internationalPhoneNumber", "places.websiteUri", "places.primaryTypeDisplayName", "places.rating",
    "places.userRatingCount", "places.googleMapsUri", "places.businessStatus", "nextPageToken",
]
# Pages qui ne sont pas un site propre à l'entreprise
PAGES_TIERCES = {
    "facebook.com", "fb.com", "instagram.com", "linktr.ee", "planity.com", "treatwell.fr", "treatwell.com",
    "booksy.com", "fresha.com", "doctolib.fr", "pagesjaunes.fr", "tripadvisor.fr", "tripadvisor.com",
    "thefork.fr", "lafourchette.com", "ubereats.com", "deliveroo.fr", "calendly.com", "business.site",
    "linkedin.com", "tiktok.com", "youtube.com", "google.com",
}
MESSAGES_ERREURS = {
    400: "Requête refusée par Google : vérifiez le secteur et la ville saisis.",
    401: "Clé API Google Places refusée : vérifiez-la dans les Réglages.",
    403: "Accès refusé : activez « Places API (New) » dans Google Cloud et vérifiez les restrictions de la clé.",
    429: "Quota Google Places dépassé : réessayez plus tard ou augmentez le quota dans Google Cloud.",
}
TARIFS = "https://developers.google.com/maps/billing-and-pricing/pricing"


class ErreurPlaces(RuntimeError):
    pass


@dataclass
class Estimation:
    requetes_max: int
    cout_max: float
    prix_1000: float
    devise: str

    @property
    def texte(self) -> str:
        cout = f"{self.cout_max:.2f}".replace(".", ",")
        return (
            f"Au plus {self.requetes_max} requête{'s' if self.requetes_max > 1 else ''} à l'API, "
            f"soit {cout} {self.devise} au maximum au tarif indicatif de "
            f"{self.prix_1000:g} {self.devise} les 1 000 requêtes."
        )


def estimer(villes: list[str], pages: int, config: ConfigPlaces) -> Estimation:
    """Borne haute : chaque ville peut coûter jusqu'à `pages` requêtes (20 fiches par requête)."""
    pages = max(1, min(pages, config.pages_max))
    n = len(villes) * pages
    return Estimation(n, math.ceil(n * config.prix_1000_requetes / 1000 * 100) / 100, config.prix_1000_requetes, config.devise)


def page_tierce(url: str) -> bool:
    hote = (urlsplit(url).hostname or "").lower().removeprefix("www.")
    return any(hote == d or hote.endswith("." + d) for d in PAGES_TIERCES)


@dataclass
class ResultatRecherche:
    prospects: list[Prospect] = field(default_factory=list)
    sans_site: int = 0
    pages_tierces: int = 0
    fermees: int = 0
    requetes: int = 0


def vers_prospect(fiche: dict) -> Prospect:
    adresse = fiche.get("formattedAddress", "")
    return Prospect(
        nom=fiche.get("displayName", {}).get("text", ""),
        url=fiche.get("websiteUri", ""),
        telephone=fiche.get("nationalPhoneNumber") or fiche.get("internationalPhoneNumber", ""),
        adresse=adresse,
        ville=ville_depuis_adresse(adresse),
        categorie=fiche.get("primaryTypeDisplayName", {}).get("text", ""),
        note_google=fiche.get("rating"),
        nb_avis=fiche.get("userRatingCount"),
        lien_maps=fiche.get("googleMapsUri", ""),
    )


async def rechercher(
    cle: str,
    secteur: str,
    villes: list[str],
    config: ConfigPlaces,
    pages: int = 3,
    client: httpx.AsyncClient | None = None,
) -> ResultatRecherche:
    if not cle:
        raise ErreurPlaces("Aucune clé Google Places : ajoutez-la dans les Réglages.")
    pages = max(1, min(pages, config.pages_max))
    entetes = {"X-Goog-Api-Key": cle, "X-Goog-FieldMask": ",".join(CHAMPS), "Content-Type": "application/json"}
    resultat, vus = ResultatRecherche(), set()
    propre = client is None
    http = client or httpx.AsyncClient(timeout=config.timeout)
    try:
        for ville in villes:
            corps = {"textQuery": f"{secteur} {ville}".strip(), "languageCode": "fr", "regionCode": "FR", "pageSize": PAR_PAGE}
            for numero in range(pages):
                if numero and config.pause_pages:
                    await asyncio.sleep(config.pause_pages)
                try:
                    r = await http.post(API, json=corps, headers=entetes)
                except httpx.HTTPError as e:
                    raise ErreurPlaces(f"Google Places injoignable ({type(e).__name__}) : vérifiez votre connexion.") from None
                resultat.requetes += 1
                if r.status_code != 200:
                    raise ErreurPlaces(MESSAGES_ERREURS.get(r.status_code, f"Erreur Google Places (HTTP {r.status_code})."))
                donnees = r.json()
                for fiche in donnees.get("places", []):
                    if fiche.get("id") in vus:
                        continue
                    vus.add(fiche.get("id"))
                    if fiche.get("businessStatus", "OPERATIONAL") != "OPERATIONAL":
                        resultat.fermees += 1
                    elif not fiche.get("websiteUri"):
                        resultat.sans_site += 1
                    elif page_tierce(fiche["websiteUri"]):
                        resultat.pages_tierces += 1
                    else:
                        resultat.prospects.append(vers_prospect(fiche))
                jeton = donnees.get("nextPageToken")
                if not jeton:
                    break
                corps["pageToken"] = jeton
    finally:
        if propre:
            await http.aclose()
    return resultat
