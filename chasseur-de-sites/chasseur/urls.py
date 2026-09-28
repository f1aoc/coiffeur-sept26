"""Petits outils autour des URL, partagés par les analyseurs."""

from __future__ import annotations

import ipaddress
from urllib.parse import urlsplit

# Suffixes publics à deux niveaux les plus courants (liste volontairement courte).
SUFFIXES_DOUBLES = {
    "co.uk", "org.uk", "me.uk", "ac.uk", "gouv.fr", "asso.fr", "nom.fr", "com.fr", "tm.fr",
    "com.au", "net.au", "co.nz", "co.za", "com.br", "co.jp", "com.es", "com.pt", "co.il",
}
TLD_RESERVES = {"test", "example", "invalid", "localhost", "local", "internal"}


def candidates(url: str) -> list[str]:
    """URL à essayer, dans l'ordre : sans schéma, HTTPS puis HTTP."""
    url = url.strip()
    if not url:
        return []
    return [url] if "://" in url else [f"https://{url}", f"http://{url}"]


def hote(url: str) -> str | None:
    """Nom d'hôte d'une URL (avec ou sans schéma), None si illisible."""
    c = candidates(url)
    if not c:
        return None
    parties = urlsplit(c[0])
    if parties.scheme not in ("http", "https") or not parties.hostname:
        return None
    return parties.hostname.lower().rstrip(".")


def url_valide(url: str) -> bool:
    return hote(url) is not None


def est_ip(nom: str) -> bool:
    try:
        ipaddress.ip_address(nom.strip("[]"))
        return True
    except ValueError:
        return False


def domaine_racine(nom_hote: str) -> str:
    """« www.coiffure.paris.fr » → « paris.fr » ; « a.b.co.uk » → « b.co.uk »."""
    nom_hote = nom_hote.lower().rstrip(".")
    if est_ip(nom_hote):
        return nom_hote
    parties = nom_hote.split(".")
    if len(parties) >= 3 and ".".join(parties[-2:]) in SUFFIXES_DOUBLES:
        return ".".join(parties[-3:])
    return ".".join(parties[-2:])


def domaine_enregistrable(nom_hote: str) -> bool:
    """Faux pour une IP, localhost ou un TLD réservé (RFC 2606) : pas de WHOIS possible."""
    if est_ip(nom_hote) or "." not in nom_hote:
        return False
    return nom_hote.rsplit(".", 1)[-1] not in TLD_RESERVES


def meme_site(hote_a: str, hote_b: str) -> bool:
    return domaine_racine(hote_a) == domaine_racine(hote_b)
