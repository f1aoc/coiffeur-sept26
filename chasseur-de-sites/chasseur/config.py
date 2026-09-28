"""Chargement et validation de config.yaml."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from chasseur.modeles import GRAVITES, Constat

RACINE_PROJET = Path(__file__).resolve().parent.parent


class ErreurConfig(ValueError):
    pass


@dataclass(frozen=True)
class RegleConstat:
    gravite: str
    points: int


@dataclass
class Config:
    constats: dict[str, RegleConstat]
    priorites: list[tuple[int, str]]  # triées par seuil décroissant
    score_max: int = 100
    priorite_incomplete: str = "? - à revérifier"
    timeout: float = 15.0
    essais: int = 2
    pause_entre_essais: float = 1.0
    ssl_alerte_jours: int = 30
    user_agent: str = "Mozilla/5.0"
    parallelisme: int = 10
    source: str = field(default="", compare=False)

    def constat(self, code: str, message_client: str, preuve: str) -> Constat:
        """Fabrique un constat avec la gravité et les points définis dans la config."""
        regle = self.constats.get(code)
        if regle is None:
            raise ErreurConfig(f"Constat « {code} » absent de la section `constats` de {self.source or 'config.yaml'}")
        return Constat(code, regle.gravite, regle.points, message_client, preuve)


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


def config_depuis_dict(brut: dict, source: str = "") -> Config:
    constats: dict[str, RegleConstat] = {}
    for code, regle in (brut.get("constats") or {}).items():
        if not isinstance(regle, dict) or "points" not in regle or "gravite" not in regle:
            raise ErreurConfig(f"Constat « {code} » : il faut `gravite` et `points`")
        gravite = str(regle["gravite"]).lower()
        if gravite not in GRAVITES:
            raise ErreurConfig(f"Constat « {code} » : gravité « {gravite} » inconnue (attendu : {', '.join(GRAVITES)})")
        try:
            points = int(regle["points"])
        except (TypeError, ValueError):
            raise ErreurConfig(f"Constat « {code} » : `points` doit être un entier") from None
        constats[code] = RegleConstat(gravite, points)
    if not constats:
        raise ErreurConfig("La section `constats` est vide")

    priorites = []
    for p in brut.get("priorites") or []:
        try:
            priorites.append((int(p["min"]), str(p["label"])))
        except (KeyError, TypeError, ValueError):
            raise ErreurConfig(f"Priorité mal formée : {p!r} (attendu : {{min: <entier>, label: <texte>}})") from None
    priorites.sort(key=lambda x: x[0], reverse=True)

    reseau = brut.get("reseau") or {}
    config = Config(
        constats=constats,
        priorites=priorites,
        score_max=int(brut.get("score_max", 100)),
        priorite_incomplete=str(brut.get("priorite_incomplete", "? - à revérifier")),
        timeout=float(reseau.get("timeout", 15)),
        essais=int(reseau.get("essais", 2)),
        pause_entre_essais=float(reseau.get("pause_entre_essais", 1)),
        ssl_alerte_jours=int(reseau.get("ssl_alerte_jours", 30)),
        user_agent=str(reseau.get("user_agent", "Mozilla/5.0")),
        parallelisme=int(brut.get("parallelisme", 10)),
        source=source,
    )
    if config.essais < 1:
        raise ErreurConfig("`reseau.essais` doit valoir au moins 1")
    if config.parallelisme < 1:
        raise ErreurConfig("`parallelisme` doit valoir au moins 1")
    return config
