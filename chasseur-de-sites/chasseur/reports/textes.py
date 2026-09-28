"""Textes des rapports et des messages, pour chaque problème (§3.4, §4).

Règles : aucun jargon non expliqué, aucune statistique ni promesse chiffrée.
Les seuls nombres affichés viennent de l'analyse (dates, année, version, temps mesuré).

Chaque entrée :
- titre    : titre court du problème ;
- visiteur : ce que voit le visiteur ;
- impact   : pourquoi c'est gênant ;
- phrase   : fin de phrase pour les messages (« j'ai remarqué que … »).

Les champs peuvent contenir {depuis}, {le}, {annee}, {version}, {date}, {hote},
{duree} : remplis avec les mesures de l'analyse, ou retirés s'ils sont inconnus.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Texte:
    titre: str
    visiteur: str
    impact: str
    phrase: str


TEXTES: dict[str, Texte] = {
    "SITE_ABSENT": Texte(
        "Pas de site internet",
        "En vous cherchant, le client ne trouve aucun site présentant vos services.",
        "Il se tourne plus facilement vers une entreprise qu'il peut découvrir en ligne.",
        "votre entreprise n'a pas encore de site internet",
    ),
    "DNS_INTROUVABLE": Texte(
        "Votre site est introuvable",
        "En tapant votre adresse, le visiteur tombe sur une page « Ce site est inaccessible ».",
        "Pour lui, votre entreprise semble avoir fermé : il se tourne vers un concurrent.",
        "votre adresse web ne mène plus à aucun site",
    ),
    "HTTP_INJOIGNABLE": Texte(
        "Votre site ne répond pas",
        "La page reste blanche, puis le navigateur affiche une erreur de connexion.",
        "Le visiteur n'attend pas : il repart sans avoir vu vos services.",
        "votre site ne répond plus",
    ),
    "HTTP_ERREUR_SERVEUR": Texte(
        "Votre site affiche une erreur",
        "Au lieu de votre page d'accueil, le visiteur voit un message d'erreur technique.",
        "Le site donne une impression d'abandon et le visiteur ne trouve pas vos informations.",
        "votre site affiche une page d'erreur au lieu de l'accueil",
    ),
    "HTTP_ERREUR_CLIENT": Texte(
        "Votre page d'accueil est introuvable",
        "Le visiteur arrive sur une page « introuvable » ou « accès refusé ».",
        "Il pense s'être trompé d'adresse et abandonne.",
        "votre page d'accueil affiche « page introuvable »",
    ),
    "SSL_EXPIRE": Texte(
        "Avertissement de sécurité à l'ouverture",
        "Le navigateur bloque l'accès avec un avertissement rouge « Votre connexion n'est pas privée »{depuis}.",
        "La plupart des visiteurs n'osent pas aller plus loin et repartent.",
        "les navigateurs affichent un avertissement de sécurité à l'ouverture de votre site",
    ),
    "SSL_INVALIDE": Texte(
        "Avertissement de sécurité à l'ouverture",
        "Le navigateur affiche un avertissement de sécurité avant d'ouvrir votre site.",
        "La plupart des visiteurs n'osent pas aller plus loin et repartent.",
        "les navigateurs affichent un avertissement de sécurité à l'ouverture de votre site",
    ),
    "SSL_ABSENT": Texte(
        "Site marqué « Non sécurisé »",
        "À côté de votre adresse, le navigateur affiche « Non sécurisé » (pas de cadenas).",
        "Cela inquiète les visiteurs, surtout au moment de remplir un formulaire, et Google privilégie les sites sécurisés.",
        "votre site est signalé « Non sécurisé » par les navigateurs",
    ),
    "HTTPS_NON_FORCE": Texte(
        "Site parfois marqué « Non sécurisé »",
        "Selon l'adresse tapée, le visiteur arrive sur une version marquée « Non sécurisé ».",
        "Cela inquiète les visiteurs, alors qu'une version sécurisée existe déjà.",
        "votre site s'ouvre parfois dans une version marquée « Non sécurisé »",
    ),
    "SSL_EXPIRE_BIENTOT": Texte(
        "Certificat de sécurité bientôt expiré",
        "Rien de visible pour l'instant, mais le certificat de sécurité du site expire{le}.",
        "Sans renouvellement, les visiteurs seront bloqués par un avertissement rouge.",
        "le certificat de sécurité de votre site expire bientôt",
    ),
    "DOMAINE_EXPIRE": Texte(
        "Votre nom de domaine a expiré",
        "Votre adresse web n'est plus renouvelée{depuis} : le site et les e-mails peuvent s'arrêter du jour au lendemain.",
        "Un tiers peut racheter votre adresse et l'utiliser à sa guise.",
        "le nom de domaine de votre site a expiré",
    ),
    "DOMAINE_NON_ENREGISTRE": Texte(
        "Votre adresse web est libre",
        "Votre adresse ne mène plus à votre site : elle n'est plus réservée à votre nom.",
        "N'importe qui peut la racheter, y compris un concurrent.",
        "votre nom de domaine n'est plus réservé à votre nom",
    ),
    "DOMAINE_PARKING": Texte(
        "Une page « domaine à vendre » à la place de votre site",
        "Le visiteur voit une page publicitaire qui propose d'acheter votre adresse web.",
        "Il pense que l'entreprise n'existe plus.",
        "votre adresse web affiche une page « domaine à vendre »",
    ),
    "DOMAINE_EXPIRE_BIENTOT": Texte(
        "Nom de domaine bientôt expiré",
        "Rien de visible pour l'instant, mais votre adresse web expire{le}.",
        "Sans renouvellement, le site et les e-mails s'arrêteront.",
        "votre nom de domaine expire bientôt",
    ),
    "PAGE_BLANCHE": Texte(
        "Page d'accueil vide",
        "Le visiteur voit une page blanche ou presque, sans vos services ni vos coordonnées.",
        "Il ne comprend pas ce que vous proposez et repart.",
        "la page d'accueil de votre site s'affiche vide",
    ),
    "ERREUR_PHP": Texte(
        "Message d'erreur sur votre site",
        "Un message technique incompréhensible s'affiche à la place du contenu.",
        "Cela donne une image négligée et cache vos informations.",
        "votre site affiche un message d'erreur technique",
    ),
    "SITE_EN_MAINTENANCE": Texte(
        "Site « en construction »",
        "Le visiteur voit « en construction » ou « en maintenance » au lieu de votre site.",
        "Il ne trouve ni vos services ni vos horaires et cherche ailleurs.",
        "votre site affiche « en construction »",
    ),
    "PIRATAGE_SPAM": Texte(
        "Contenus indésirables cachés dans votre site",
        "Des liens publicitaires (médicaments, casinos) sont dissimulés dans vos pages.",
        "C'est le signe d'un piratage : Google peut afficher un avertissement ou faire reculer votre site.",
        "votre site contient des liens publicitaires cachés, signe d'un piratage",
    ),
    "PIRATAGE_REDIRECTION": Texte(
        "Vos visiteurs sont envoyés ailleurs",
        "En ouvrant votre adresse, le visiteur se retrouve sur un autre site{hote}.",
        "Vous perdez ce visiteur, et ce comportement est souvent dû à un piratage.",
        "votre site envoie les visiteurs vers un autre site",
    ),
    "VIEWPORT_ABSENT": Texte(
        "Site non adapté aux téléphones",
        "Sur téléphone, la page s'affiche en tout petit : il faut zoomer pour lire.",
        "Trouver votre numéro ou votre adresse devient pénible, et le visiteur abandonne.",
        "votre site n'est pas adapté aux téléphones",
    ),
    "DEFILEMENT_HORIZONTAL": Texte(
        "Page qui déborde sur téléphone",
        "Sur téléphone, une partie de la page dépasse de l'écran : il faut la faire glisser de gauche à droite.",
        "La lecture devient pénible et le site paraît cassé.",
        "votre site déborde de l'écran sur téléphone",
    ),
    "COPYRIGHT_ANCIEN": Texte(
        "Site qui paraît abandonné",
        "En bas de page, le visiteur lit « ©{annee} ».",
        "Il se demande si l'entreprise est toujours active.",
        "le bas de votre site affiche encore « ©{annee} »",
    ),
    "WORDPRESS_OBSOLETE": Texte(
        "Logiciel du site plus mis à jour",
        "Rien de visible, mais votre site tourne sur une ancienne version de WordPress{version}.",
        "Les anciennes versions ne reçoivent plus de correctifs de sécurité : le site est plus exposé aux piratages.",
        "votre site tourne sur une ancienne version de WordPress",
    ),
    "JOOMLA_OBSOLETE": Texte(
        "Logiciel du site plus mis à jour",
        "Rien de visible, mais votre site tourne sur une ancienne version de Joomla{version}.",
        "Les anciennes versions ne reçoivent plus de correctifs de sécurité : le site est plus exposé aux piratages.",
        "votre site tourne sur une ancienne version de Joomla",
    ),
    "JQUERY_OBSOLETE": Texte(
        "Composants techniques périmés",
        "Rien de visible, mais le site utilise des composants anciens.",
        "Ils ne sont plus corrigés et peuvent provoquer des bugs ou des failles de sécurité.",
        "votre site utilise des composants techniques périmés",
    ),
    "FLASH": Texte(
        "Contenu qui ne s'affiche plus",
        "À la place de certaines animations ou galeries, le visiteur voit un cadre vide.",
        "La technologie utilisée (Flash) n'est plus lue par aucun navigateur actuel.",
        "une partie de votre site utilise Flash, qui ne s'affiche plus",
    ),
    "MISE_EN_PAGE_TABLEAUX": Texte(
        "Construction des années 2000",
        "Le site s'affiche comme un bloc figé qui s'adapte mal aux écrans actuels.",
        "Il paraît daté et se modifie difficilement.",
        "votre site est construit avec une technique des années 2000",
    ),
    "TITLE_ABSENT": Texte(
        "Pas de titre dans Google",
        "Dans les résultats de Google, votre site apparaît sans nom clair.",
        "Le client clique plus volontiers sur un concurrent bien présenté.",
        "votre site n'a pas de titre pour Google",
    ),
    "META_DESCRIPTION_ABSENTE": Texte(
        "Pas de description dans Google",
        "Sous votre nom dans Google, un extrait pris au hasard s'affiche.",
        "Il ne donne pas envie de cliquer.",
        "votre site n'a pas de description pour Google",
    ),
    "CONTACT_ABSENT": Texte(
        "Difficile de vous contacter",
        "Le visiteur ne trouve ni formulaire ni numéro à toucher pour vous appeler depuis son téléphone.",
        "Chaque effort en plus fait renoncer des clients.",
        "on ne peut ni vous écrire ni vous appeler d'un simple clic depuis votre site",
    ),
    "ACTUALITES_ANCIENNES": Texte(
        "Actualités anciennes",
        "La date la plus récente affichée sur votre site est{date}.",
        "Le visiteur se demande si l'entreprise est toujours active.",
        "les dernières actualités de votre site sont anciennes",
    ),
    "PERF_LENTE": Texte(
        "Site lent sur téléphone",
        "Sur téléphone, la page met longtemps à s'afficher{duree}.",
        "Beaucoup de visiteurs n'attendent pas la fin du chargement.",
        "votre site est lent à s'afficher sur téléphone",
    ),
}

MOIS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre")


def date_longue(iso: str) -> str:
    """« 2026-08-12 » → « 12 août 2026 » ; texte vide si la date est illisible."""
    try:
        d = datetime.strptime(iso[:10], "%Y-%m-%d")
    except (TypeError, ValueError):
        return ""
    jour = "1er" if d.day == 1 else str(d.day)
    return f"{jour} {MOIS[d.month - 1]} {d.year}"


def _variables(code: str, mesures: dict) -> dict[str, str]:
    """Fragments tirés des mesures ; chaîne vide quand l'information manque."""
    m = mesures or {}
    date_domaine = date_longue(m.get("domaine_expire_le", ""))
    date_ssl = date_longue(m.get("ssl_expire_le", ""))
    date_expiration = date_domaine if code.startswith("DOMAINE") else date_ssl
    hote = urlsplit(m.get("navigateur_url_finale", "")).hostname or ""
    cle_version = "version_wordpress" if code.startswith("WORDPRESS") else "version_joomla"
    return {
        "depuis": f" depuis le {date_expiration}" if date_expiration else "",
        "le": f" le {date_expiration}" if date_expiration else " prochainement",
        "annee": f" {m['annee_copyright']}" if m.get("annee_copyright") else "",
        "version": f" ({m[cle_version]})" if m.get(cle_version) else "",
        "date": f" le {date_longue(m['derniere_date'])}" if date_longue(m.get("derniere_date", "")) else " ancienne",
        "hote": f" ({hote})" if hote else "",
        "duree": f" (environ {m['perf_lcp_s'].replace('.', ',')} secondes)" if m.get("perf_lcp_s") else "",
    }


def _remplir(modele: str, variables: dict[str, str]) -> str:
    return re.sub(r"\{(\w+)\}", lambda x: variables.get(x[1], ""), modele)


def texte(code: str, mesures: dict | None = None) -> Texte | None:
    """Texte d'un problème, complété avec les mesures de l'analyse (None si le code n'a pas de texte)."""
    modele = TEXTES.get(code)
    if modele is None:
        return None
    v = _variables(code, mesures or {})
    return Texte(*(_remplir(champ, v) for champ in (modele.titre, modele.visiteur, modele.impact, modele.phrase)))
