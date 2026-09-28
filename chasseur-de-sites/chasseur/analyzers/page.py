"""Règles appliquées à une page rendue par le navigateur.

Tout ici est pur (aucun accès réseau) : browser.py collecte une PageInfo,
evaluer_page() en tire les constats. Les tests peuvent donc fabriquer une
PageInfo à la main.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from bs4 import BeautifulSoup

from chasseur import urls
from chasseur.config import Config
from chasseur.modeles import Rapport
from chasseur.signatures import Signatures, hote_dans, version_en_tuple

CONTROLES_CONTENU = [
    "page_blanche_php", "maintenance", "piratage", "responsive", "copyright",
    "technologies", "title_meta", "contact", "actualites",
]


@dataclass
class PageInfo:
    url_demandee: str
    url_finale: str
    statut_http: int | None
    html: str
    texte_visible: str
    texte_pied: str = ""
    version_jquery_js: str = ""  # window.jQuery.fn.jquery, lu dans la page
    largeur_contenu_mobile: int | None = None
    largeur_fenetre_mobile: int | None = None
    # Page contact éventuellement visitée (§6.2)
    url_contact: str = ""
    contact_formulaire: bool = False
    contact_tel: bool = False
    captures: dict[str, str] = field(default_factory=dict)


# --- Extraction ------------------------------------------------------------

RE_ANNEE_COPYRIGHT = re.compile(
    r"(?:©|&copy;|\(c\)|copyright|tous droits réservés|all rights reserved)[^0-9]{0,40}"
    r"((?:19|20)\d{2})(?:\s*[-–/à]\s*((?:19|20)\d{2}))?",
    re.IGNORECASE,
)
RE_ANNEE_AVANT_MENTION = re.compile(r"((?:19|20)\d{2})\s*[-–]?\s*(?:©|tous droits réservés|all rights reserved)", re.I)

MOIS = {
    "janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6, "juillet": 7,
    "août": 8, "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12, "decembre": 12,
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}
_NOMS_MOIS = "|".join(sorted(MOIS, key=len, reverse=True))
RE_DATES = [
    (re.compile(r"\b(\d{1,2})[/.](\d{1,2})[/.]((?:19|20)\d{2})\b"), "jma"),
    (re.compile(r"\b((?:19|20)\d{2})-(\d{2})-(\d{2})\b"), "amj"),
    (re.compile(rf"\b(\d{{1,2}})(?:er)?\s+({_NOMS_MOIS})\s+((?:19|20)\d{{2}})\b", re.I), "jMa"),
    (re.compile(rf"\b({_NOMS_MOIS})\s+(\d{{1,2}}),?\s+((?:19|20)\d{{2}})\b", re.I), "Mja"),
]
META_DATES = ("article:published_time", "article:modified_time", "og:updated_time", "date", "dc.date")


def annee_copyright(texte_pied: str) -> int | None:
    annees = []
    for m in RE_ANNEE_COPYRIGHT.finditer(texte_pied):
        annees += [int(a) for a in m.groups() if a]
    annees += [int(m[1]) for m in RE_ANNEE_AVANT_MENTION.finditer(texte_pied)]
    return max(annees, default=None)


def _date(a: int, m: int, j: int) -> datetime | None:
    try:
        return datetime(a, m, j, tzinfo=timezone.utc)
    except ValueError:
        return None


def dates_trouvees(soup: BeautifulSoup, texte: str) -> list[datetime]:
    dates: list[datetime] = []
    for t in soup.find_all("time"):
        if d := _iso(t.get("datetime", "")):
            dates.append(d)
    for meta in soup.find_all("meta"):
        nom = (meta.get("property") or meta.get("name") or meta.get("itemprop") or "").lower()
        if nom in META_DATES or nom in ("datepublished", "datemodified"):
            if d := _iso(meta.get("content", "")):
                dates.append(d)
    for script in soup.find_all("script", type="application/ld+json"):
        for cle in re.findall(r'"date(?:Published|Modified)"\s*:\s*"([^"]+)"', script.string or ""):
            if d := _iso(cle):
                dates.append(d)
    for motif, ordre in RE_DATES:
        for m in motif.finditer(texte):
            if ordre == "jma":
                d = _date(int(m[3]), int(m[2]), int(m[1]))
            elif ordre == "amj":
                d = _date(int(m[1]), int(m[2]), int(m[3]))
            elif ordre == "jMa":
                d = _date(int(m[3]), MOIS[m[2].lower()], int(m[1]))
            else:
                d = _date(int(m[3]), MOIS[m[1].lower()], int(m[2]))
            if d:
                dates.append(d)
    return dates


def _iso(texte: str) -> datetime | None:
    m = re.match(r"\s*((?:19|20)\d{2})-(\d{2})-(\d{2})", texte or "")
    return _date(int(m[1]), int(m[2]), int(m[3])) if m else None


def mise_en_page_tableaux(soup: BeautifulSoup) -> str | None:
    """Preuve textuelle si la page est mise en page avec des <table>, sinon None."""
    tables = soup.find_all("table")
    if any(t.find_parent("table") for t in tables):
        return "tableaux imbriqués (mise en page des années 2000)"
    corps = soup.body or soup
    total = len(corps.get_text(" ", strip=True))
    if total < 200:
        return None
    for t in tables:
        if t.find("th"):
            continue  # tableau de données
        part = len(t.get_text(" ", strip=True)) / total
        if part > 0.5:
            return f"un tableau sans en-têtes contient {part:.0%} du texte de la page"
    return None


def formulaires_utiles(soup: BeautifulSoup) -> int:
    """Nombre de formulaires hors simples champs de recherche."""
    n = 0
    for form in soup.find_all("form"):
        champs = form.find_all(["input", "textarea", "select"])
        visibles = [c for c in champs if (c.get("type") or "text").lower() not in ("hidden", "submit", "button")]
        recherche = form.get("role") == "search" or all(
            (c.get("type") or "").lower() == "search" or (c.get("name") or "").lower() in ("s", "q", "search", "recherche")
            for c in visibles
        )
        if visibles and not recherche:
            n += 1
    return n


def liens_tel(soup: BeautifulSoup) -> int:
    return len(soup.select('a[href^="tel:" i]'))


# --- Évaluation ------------------------------------------------------------


def evaluer_page(info: PageInfo, config: Config, sig: Signatures, maintenant: datetime | None = None) -> Rapport:
    maintenant = maintenant or datetime.now(timezone.utc)
    c = config
    nav = config.navigateur
    rapport = Rapport(mesures={k: v for k, v in info.captures.items()})
    rapport.mesures["navigateur_url_finale"] = info.url_finale
    if info.statut_http is not None:
        rapport.mesures["navigateur_code_http"] = str(info.statut_http)

    # Une page d'erreur HTTP est déjà signalée par l'analyseur Réseau : on n'en juge pas le contenu.
    if info.statut_http is not None and info.statut_http >= 400:
        rapport.non_verifies.update(dict.fromkeys(CONTROLES_CONTENU, f"page d'erreur HTTP {info.statut_http}"))
        return rapport

    soup = BeautifulSoup(info.html, "html.parser")
    texte = " ".join(info.texte_visible.split())
    html_min = info.html.lower()
    rapport.mesures["texte_visible_car"] = str(len(texte))

    # Page blanche / erreur PHP
    if m := next((m for p in sig.erreurs_php if (m := p.search(texte))), None):
        rapport.append(
            c.constat(
                "ERREUR_PHP",
                "Votre site affiche un message d'erreur technique à la place de son contenu : "
                "les visiteurs pensent que l'entreprise n'existe plus.",
                f"texte affiché : « {m[0][:200]} »",
            )
        )
    elif len(texte) < nav.texte_min:
        rapport.append(
            c.constat(
                "PAGE_BLANCHE",
                "La page d'accueil de votre site est vide ou presque : les visiteurs ne voient ni vos "
                "services ni vos coordonnées.",
                f"{len(texte)} caractères de texte visibles (seuil : {nav.texte_min}) sur {info.url_finale}",
            )
        )

    # Maintenance
    if len(texte) <= sig.maintenance_texte_max:
        if m := next((m for p in sig.maintenance if (m := p.search(texte))), None):
            rapport.append(
                c.constat(
                    "SITE_EN_MAINTENANCE",
                    "Votre site affiche « en construction » ou « en maintenance » : les visiteurs repartent "
                    "sans trouver vos informations.",
                    f"texte affiché : « {m[0]} » ({len(texte)} caractères visibles)",
                )
            )

    # Piratage
    titre = (soup.title.get_text(" ", strip=True) if soup.title else "").strip()
    spams = sorted({m[0].lower() for p in sig.spam if (m := p.search(html_min))})
    spam_titre = [s for s in spams if s in titre.lower()]
    if len(spams) >= sig.seuil_spam or spam_titre:
        rapport.append(
            c.constat(
                "PIRATAGE_SPAM",
                "Votre site contient des publicités cachées pour des médicaments ou des casinos : c'est le "
                "signe d'un piratage, et Google peut vous déclasser ou afficher un avertissement.",
                f"mots de spam trouvés dans le code de la page : {', '.join(spams)}",
            )
        )
    hote_depart, hote_final = urls.hote(info.url_demandee), urls.hote(info.url_finale)
    if (
        hote_depart
        and hote_final
        and not urls.meme_site(hote_depart, hote_final)
        and not hote_dans(hote_final, sig.redirections_autorisees)
        and not hote_dans(hote_final, sig.parking_services)  # déjà signalé par l'analyseur Domaine
    ):
        rapport.append(
            c.constat(
                "PIRATAGE_REDIRECTION",
                f"Les visiteurs de votre site sont redirigés vers un autre site ({hote_final}) : c'est souvent "
                "le signe d'un piratage.",
                f"{info.url_demandee} → {info.url_finale}",
            )
        )

    # Responsive
    viewport = soup.find("meta", attrs={"name": re.compile(r"^viewport$", re.I)})
    rapport.mesures["meta_viewport"] = (viewport.get("content") or "").strip() if viewport else ""
    if not viewport:
        rapport.append(
            c.constat(
                "VIEWPORT_ABSENT",
                "Votre site n'est pas adapté aux téléphones : sur mobile, le texte est minuscule et il faut zoomer.",
                "pas de balise <meta name=\"viewport\"> dans la page",
            )
        )
    if info.largeur_contenu_mobile and info.largeur_fenetre_mobile:
        rapport.mesures["largeur_mobile"] = f"{info.largeur_contenu_mobile}/{info.largeur_fenetre_mobile} px"
        if info.largeur_contenu_mobile > info.largeur_fenetre_mobile + 5:
            rapport.append(
                c.constat(
                    "DEFILEMENT_HORIZONTAL",
                    "Sur téléphone, votre site déborde de l'écran : il faut faire défiler de gauche à droite pour le lire.",
                    f"contenu de {info.largeur_contenu_mobile} px pour un écran de {info.largeur_fenetre_mobile} px",
                )
            )

    # Copyright
    annee = annee_copyright(info.texte_pied)
    if annee:
        rapport.mesures["annee_copyright"] = str(annee)
        if annee <= maintenant.year - nav.copyright_ans:
            rapport.append(
                c.constat(
                    "COPYRIGHT_ANCIEN",
                    f"Le bas de votre site affiche « © {annee} » : les visiteurs ont l'impression que le site "
                    "n'est plus entretenu.",
                    f"année la plus récente du pied de page : {annee}",
                )
            )

    # Technologies
    trouvees = []
    for t in sig.technologies:
        if not any(p.search(info.html) for p in t.detection) and not (t.id == "jquery" and info.version_jquery_js):
            continue
        version = info.version_jquery_js if t.id == "jquery" and info.version_jquery_js else ""
        if not version:
            version = next((m[1] for p in t.version if (m := p.search(info.html))), "")
        trouvees.append(f"{t.nom} {version}".strip())
        if t.id in ("wordpress", "joomla"):
            rapport.mesures["cms"] = t.nom
            if version:
                rapport.mesures[f"version_{t.id}"] = version
        if t.id == "jquery" and version:
            rapport.mesures["version_jquery"] = version
        if not t.constat:
            continue
        if t.obsolete_avant is None:
            rapport.append(
                c.constat(
                    t.constat,
                    f"Votre site utilise {t.nom}, une technologie abandonnée que les navigateurs actuels "
                    "n'affichent plus.",
                    f"{t.nom} détecté dans le code de la page",
                )
            )
        elif version and version_en_tuple(version) < t.obsolete_avant:
            minimum = ".".join(map(str, t.obsolete_avant))
            rapport.append(
                c.constat(
                    t.constat,
                    f"Votre site tourne sur une version ancienne de {t.nom} ({version}) : elle n'est plus mise "
                    "à jour et expose le site aux piratages.",
                    f"{t.nom} {version} détecté (version minimale conseillée : {minimum})",
                )
            )
    tableaux = mise_en_page_tableaux(soup)
    if tableaux:
        trouvees.append("mise en page en tableaux")
        rapport.append(
            c.constat(
                "MISE_EN_PAGE_TABLEAUX",
                "Votre site est construit avec une technique des années 2000 : il s'affiche mal sur les "
                "écrans actuels et se modifie difficilement.",
                tableaux,
            )
        )
    rapport.mesures["technologies"] = ", ".join(trouvees)

    # Title / meta description
    description = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
    description = (description.get("content") or "").strip() if description else ""
    rapport.mesures["title"] = titre[:120]
    rapport.mesures["meta_description"] = description[:160]
    if not titre:
        rapport.append(
            c.constat(
                "TITLE_ABSENT",
                "Votre site n'a pas de titre : dans Google, il apparaît sans nom clair et attire moins de clics.",
                "balise <title> absente ou vide",
            )
        )
    if not description:
        rapport.append(
            c.constat(
                "META_DESCRIPTION_ABSENTE",
                "Votre site n'a pas de description pour Google : le moteur affiche un extrait au hasard sous votre nom.",
                "balise <meta name=\"description\"> absente ou vide",
            )
        )

    # Formulaire / lien tel:
    formulaire = formulaires_utiles(soup) > 0 or info.contact_formulaire
    tel = liens_tel(soup) > 0 or info.contact_tel
    rapport.mesures["formulaire"] = "oui" if formulaire else "non"
    rapport.mesures["lien_tel"] = "oui" if tel else "non"
    if info.url_contact:
        rapport.mesures["page_contact"] = info.url_contact
    if not formulaire and not tel:
        rapport.append(
            c.constat(
                "CONTACT_ABSENT",
                "Sur votre site, on ne peut ni vous écrire par formulaire ni vous appeler d'un simple clic "
                "sur mobile : des clients renoncent à vous contacter.",
                f"ni <form> ni lien tel: sur l'accueil{' ni sur ' + info.url_contact if info.url_contact else ''}",
            )
        )

    # Dernière actualité
    dates = [d for d in dates_trouvees(soup, texte) if d <= maintenant + timedelta(days=365)]
    if dates:
        recente = max(dates)
        rapport.mesures["derniere_date"] = recente.strftime("%Y-%m-%d")
        if recente < maintenant - timedelta(days=365 * nav.actualites_ans):
            rapport.append(
                c.constat(
                    "ACTUALITES_ANCIENNES",
                    f"La date la plus récente de votre site remonte au {recente:%d/%m/%Y} : les visiteurs "
                    "se demandent si l'entreprise est toujours active.",
                    f"date la plus récente trouvée sur la page : {recente:%Y-%m-%d}",
                )
            )
    return rapport
