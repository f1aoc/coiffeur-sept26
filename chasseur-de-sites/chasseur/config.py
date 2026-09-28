"""Chargement et validation de config.yaml."""

from __future__ import annotations

import os
from dataclasses import dataclass, field, fields
from pathlib import Path

import yaml

from chasseur.controles import CODE_NON_VERIFIE, CONTROLE_DU_CODE, PAR_ID, gravite_du_code
from chasseur.modeles import Constat

RACINE_PROJET = Path(__file__).resolve().parent.parent
PARALLELISME_MAX = 30  # cahier des charges §6.3 : réglable de 1 à 30


class ErreurConfig(ValueError):
    pass


@dataclass
class ConfigEtats:
    casse: str = "Cassé"
    obsolete: str = "Obsolète"
    correct: str = "Correct"
    sans_site: str = "Sans site"
    a_reverifier: str = "À revérifier"
    seuil_obsolete: int = 30


@dataclass
class ConfigDomaine:
    alerte_jours: int = 30
    rdap_url: str = "https://rdap.org/domain/{domaine}"
    whois_actif: bool = True
    timeout: float = 15.0


@dataclass
class ConfigNavigateur:
    timeout_page: float = 20.0
    largeur_bureau: int = 1366
    hauteur_bureau: int = 768
    largeur_mobile: int = 375
    hauteur_mobile: int = 667
    dossier_captures: str = "captures"
    capture_max_ko: int = 150
    simultanes: int = 5
    chromium: str = ""  # chemin d'un Chromium précis (sinon celui de Playwright)
    sandbox: bool = True
    respecter_robots: bool = True
    page_contact: bool = True
    texte_min: int = 500
    copyright_ans: int = 3
    actualites_ans: int = 2


@dataclass
class ConfigPerformance:
    cle_api: str = ""
    strategie: str = "mobile"
    seuil: int = 40
    requetes_par_minute: int = 60
    simultanees: int = 4
    timeout: float = 90.0
    max_relances: int = 4
    pause_base: float = 5.0  # attente avant la 1re relance après un 429 (doublée ensuite)

    @property
    def cle(self) -> str:
        return self.cle_api or os.environ.get("PAGESPEED_API_KEY", "")


@dataclass
class Config:
    points: dict[str, int]  # contrôle → points
    etats: ConfigEtats = field(default_factory=ConfigEtats)
    score_max: int = 100
    timeout: float = 15.0
    essais: int = 2
    pause_entre_essais: float = 2.0
    ssl_alerte_jours: int = 30
    user_agent: str = "Mozilla/5.0 (compatible; ChasseurDeSites/0.2)"
    parallelisme: int = 10
    domaine: ConfigDomaine = field(default_factory=ConfigDomaine)
    navigateur: ConfigNavigateur = field(default_factory=ConfigNavigateur)
    performance: ConfigPerformance = field(default_factory=ConfigPerformance)
    source: str = field(default="", compare=False)

    def points_du_code(self, code: str) -> int:
        if code == CODE_NON_VERIFIE:
            return 0
        return self.points.get(CONTROLE_DU_CODE[code].id, 0)

    def constat(self, code: str, message_client: str, preuve: str) -> Constat:
        """Fabrique un constat avec la gravité du registre et les points de la config."""
        if code != CODE_NON_VERIFIE and code not in CONTROLE_DU_CODE:
            raise ErreurConfig(f"Code de constat inconnu : « {code} » (voir chasseur/controles.py)")
        return Constat(code, gravite_du_code(code), self.points_du_code(code), message_client, preuve)


def trouver_config(chemin: str | Path | None = None) -> Path:
    """Chemin explicite, sinon ./config.yaml, sinon celui livré avec le projet."""
    if chemin:
        p = Path(chemin)
        if not p.is_file():
            raise ErreurConfig(f"Fichier de configuration introuvable : {p}")
        return p
    for candidat in (Path.cwd() / "config.yaml", RACINE_PROJET / "config.yaml"):
        if candidat.is_file():
            return candidat
    raise ErreurConfig("Aucun config.yaml trouvé (ni dans le dossier courant, ni à la racine du projet)")


def charger_config(chemin: str | Path | None = None) -> Config:
    p = trouver_config(chemin)
    with p.open(encoding="utf-8") as f:
        brut = yaml.safe_load(f) or {}
    return config_depuis_dict(brut, source=str(p))


def _section(classe, brut: dict | None, nom: str):
    """Construit une dataclass de section en convertissant chaque valeur au type par défaut."""
    brut = brut or {}
    connus = {f.name: f for f in fields(classe)}
    inconnus = set(brut) - set(connus)
    if inconnus:
        raise ErreurConfig(f"Section `{nom}` : clé(s) inconnue(s) : {', '.join(sorted(inconnus))}")
    valeurs = {}
    defaut = classe()
    for cle, valeur in brut.items():
        type_attendu = type(getattr(defaut, cle))
        try:
            if type_attendu is bool:
                valeurs[cle] = valeur if isinstance(valeur, bool) else str(valeur).lower() in ("1", "true", "oui", "yes")
            else:
                valeurs[cle] = type_attendu(valeur if valeur is not None else type_attendu())
        except (TypeError, ValueError):
            raise ErreurConfig(f"Section `{nom}` : `{cle}` doit être de type {type_attendu.__name__}") from None
    return classe(**valeurs)


def config_depuis_dict(brut: dict, source: str = "") -> Config:
    points_bruts = brut.get("points") or {}
    if not points_bruts:
        raise ErreurConfig("La section `points` est vide")
    inconnus = set(points_bruts) - set(PAR_ID)
    if inconnus:
        raise ErreurConfig(f"Section `points` : contrôle(s) inconnu(s) : {', '.join(sorted(inconnus))}")
    points: dict[str, int] = {}
    for controle, valeur in points_bruts.items():
        try:
            points[controle] = int(valeur)
        except (TypeError, ValueError):
            raise ErreurConfig(f"Contrôle « {controle} » : les points doivent être un entier") from None
    manquants = set(PAR_ID) - set(points)
    if manquants:
        raise ErreurConfig(f"Section `points` : contrôle(s) manquant(s) : {', '.join(sorted(manquants))}")

    reseau = brut.get("reseau") or {}
    config = Config(
        points=points,
        etats=_section(ConfigEtats, brut.get("etats"), "etats"),
        score_max=int(brut.get("score_max", 100)),
        timeout=float(reseau.get("timeout", 15)),
        essais=int(reseau.get("essais", 2)),
        pause_entre_essais=float(reseau.get("pause_entre_essais", 2)),
        ssl_alerte_jours=int(reseau.get("ssl_alerte_jours", 30)),
        user_agent=str(reseau.get("user_agent", Config.user_agent)),
        parallelisme=int(brut.get("parallelisme", 10)),
        domaine=_section(ConfigDomaine, brut.get("domaine"), "domaine"),
        navigateur=_section(ConfigNavigateur, brut.get("navigateur"), "navigateur"),
        performance=_section(ConfigPerformance, brut.get("performance"), "performance"),
        source=source,
    )
    if config.essais < 1:
        raise ErreurConfig("`reseau.essais` doit valoir au moins 1")
    if not 1 <= config.parallelisme <= PARALLELISME_MAX:
        raise ErreurConfig(f"`parallelisme` doit être compris entre 1 et {PARALLELISME_MAX}")
    return config
