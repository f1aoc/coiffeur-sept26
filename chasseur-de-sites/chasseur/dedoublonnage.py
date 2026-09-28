"""Dédoublonnage par domaine avant analyse (§3.1).

La clé est l'hôte sans « www. ». Exceptions :
- plateformes où plusieurs entreprises partagent un hôte (sites.google.com/…,
  facebook.com/…) : le premier segment du chemin fait partie de la clé ;
- adresse IP ou localhost : l'URL complète (ce ne sont pas des domaines d'entreprise).
Un prospect sans URL n'est jamais considéré comme un doublon.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from chasseur import urls
from chasseur.modeles import Prospect

PLATEFORMES_PARTAGEES = {
    "sites.google.com", "facebook.com", "instagram.com", "linktr.ee", "business.site", "pagesjaunes.fr",
    "planity.com", "treatwell.fr", "linkedin.com", "tiktok.com", "youtube.com",
}


def cle_domaine(url: str) -> str | None:
    hote = urls.hote(url)
    if not hote:
        return None
    parties = urlsplit(urls.candidates(url)[0])
    if urls.est_ip(hote) or hote == "localhost":
        return f"{hote}:{parties.port or ''}{parties.path.rstrip('/')}?{parties.query}"
    hote = hote.removeprefix("www.")
    if hote in PLATEFORMES_PARTAGEES:
        segment = parties.path.strip("/").split("/")[0].lower()
        return f"{hote}/{segment}"
    return hote


def dedoublonner(prospects: list[Prospect]) -> tuple[list[Prospect], list[Prospect]]:
    """(prospects gardés, doublons retirés) ; le premier prospect d'un domaine est gardé."""
    vus: set[str] = set()
    gardes, doublons = [], []
    for p in prospects:
        cle = cle_domaine(p.url) if p.url else None
        if cle is not None and cle in vus:
            doublons.append(p)
            continue
        if cle is not None:
            vus.add(cle)
        gardes.append(p)
    return gardes, doublons
