"""Registre des contrôles (cahier des charges, tableaux 3.2 et 3.3).

Un contrôle regroupe un ou plusieurs codes de constat. Les points sont fixés
par contrôle dans config.yaml et comptés une seule fois par site, même si
plusieurs codes du même contrôle sont relevés (ex. « page blanche OU erreur
PHP » = 30 points au total).

Familles :
- casse    : tableau 3.2, un seul déclenchement classe le site « Cassé » ;
- obsolete : tableau 3.3 ;
- autre    : hors tableaux (alertes d'expiration proche, informations).
"""

from __future__ import annotations

from dataclasses import dataclass

CODE_NON_VERIFIE = "NON_VERIFIE"


@dataclass(frozen=True)
class Controle:
    id: str
    libelle: str
    analyseur: str
    famille: str
    codes: dict[str, str]  # code de constat → gravité


CONTROLES: tuple[Controle, ...] = (
    # --- Réseau ---------------------------------------------------------------
    Controle("url", "URL renseignée", "reseau", "autre", {"SITE_ABSENT": "info", "URL_INVALIDE": "info"}),
    Controle("dns", "Domaine qui résout (DNS)", "reseau", "casse", {"DNS_INTROUVABLE": "critique"}),
    Controle(
        "http_5xx",
        "Erreur serveur 5xx ou délai dépassé",
        "reseau",
        "casse",
        {"HTTP_INJOIGNABLE": "critique", "HTTP_ERREUR_SERVEUR": "critique"},
    ),
    Controle("http_4xx", "Erreur 4xx sur la page d'accueil", "reseau", "casse", {"HTTP_ERREUR_CLIENT": "haute"}),
    Controle("ssl", "Certificat SSL expiré ou invalide", "reseau", "casse", {"SSL_EXPIRE": "critique", "SSL_INVALIDE": "haute"}),
    Controle("https", "HTTPS et redirection HTTP → HTTPS", "reseau", "obsolete", {"SSL_ABSENT": "moyenne", "HTTPS_NON_FORCE": "moyenne"}),
    Controle("ssl_expiration", "Certificat SSL qui expire bientôt", "reseau", "autre", {"SSL_EXPIRE_BIENTOT": "basse"}),
    # --- Domaine --------------------------------------------------------------
    Controle(
        "domaine",
        "Domaine expiré ou parqué",
        "domaine",
        "casse",
        {"DOMAINE_EXPIRE": "critique", "DOMAINE_NON_ENREGISTRE": "critique", "DOMAINE_PARKING": "critique"},
    ),
    Controle("domaine_expiration", "Domaine qui expire bientôt", "domaine", "autre", {"DOMAINE_EXPIRE_BIENTOT": "haute"}),
    # --- Navigateur -----------------------------------------------------------
    Controle("page_blanche_php", "Page blanche ou erreur PHP", "navigateur", "casse", {"PAGE_BLANCHE": "critique", "ERREUR_PHP": "critique"}),
    Controle("maintenance", "Site en maintenance / en construction", "navigateur", "casse", {"SITE_EN_MAINTENANCE": "haute"}),
    Controle("piratage", "Signes de piratage", "navigateur", "casse", {"PIRATAGE_SPAM": "critique", "PIRATAGE_REDIRECTION": "critique"}),
    Controle("responsive", "Site responsive", "navigateur", "obsolete", {"VIEWPORT_ABSENT": "moyenne", "DEFILEMENT_HORIZONTAL": "moyenne"}),
    Controle("copyright", "Copyright récent", "navigateur", "obsolete", {"COPYRIGHT_ANCIEN": "basse"}),
    Controle(
        "technologies",
        "CMS ou technologies périmées",
        "navigateur",
        "obsolete",
        {
            "WORDPRESS_OBSOLETE": "moyenne",
            "JQUERY_OBSOLETE": "basse",
            "JOOMLA_OBSOLETE": "moyenne",
            "FLASH": "moyenne",
            "MISE_EN_PAGE_TABLEAUX": "moyenne",
        },
    ),
    Controle("title_meta", "Balise title et meta description", "navigateur", "obsolete", {"TITLE_ABSENT": "basse", "META_DESCRIPTION_ABSENTE": "basse"}),
    Controle("contact", "Formulaire ou lien téléphone cliquable", "navigateur", "obsolete", {"CONTACT_ABSENT": "basse"}),
    Controle("actualites", "Dernière actualité récente", "navigateur", "obsolete", {"ACTUALITES_ANCIENNES": "basse"}),
    # --- Performance ----------------------------------------------------------
    Controle("performance", "Performance mobile (PageSpeed)", "performance", "obsolete", {"PERF_LENTE": "moyenne"}),
)

PAR_ID: dict[str, Controle] = {c.id: c for c in CONTROLES}
CONTROLE_DU_CODE: dict[str, Controle] = {code: c for c in CONTROLES for code in c.codes}


def controles_de(analyseur: str) -> list[str]:
    return [c.id for c in CONTROLES if c.analyseur == analyseur]


def gravite_du_code(code: str) -> str:
    if code == CODE_NON_VERIFIE:
        return "info"
    return CONTROLE_DU_CODE[code].codes[code]
