"""Chargement de signatures.yaml (motifs compilés une seule fois)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

from chasseur.config import RACINE_PROJET, ErreurConfig
from chasseur.controles import CONTROLE_DU_CODE

FLAGS = re.IGNORECASE | re.DOTALL


def _compiler(motifs, contexte: str) -> list[re.Pattern]:
    compiles = []
    for m in motifs or []:
        try:
            compiles.append(re.compile(str(m), FLAGS))
        except re.error as e:
            raise ErreurConfig(f"signatures.yaml, {contexte} : motif invalide {m!r} ({e})") from None
    return compiles


@dataclass
class Technologie:
    id: str
    nom: str
    detection: list[re.Pattern]
    version: list[re.Pattern]
    obsolete_avant: tuple[int, ...] | None
    constat: str | None


@dataclass
class Signatures:
    technologies: list[Technologie]
    parking_phrases: list[re.Pattern]
    parking_services: list[str]
    parking_motifs_html: list[re.Pattern]
    maintenance: list[re.Pattern]
    maintenance_texte_max: int
    erreurs_php: list[re.Pattern]
    spam: list[re.Pattern]
    seuil_spam: int
    redirections_autorisees: list[str]
    page_contact: list[re.Pattern] = field(default_factory=list)


def version_en_tuple(version: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", version)[:4])


def trouver_signatures(chemin: str | Path | None = None) -> Path:
    if chemin:
        return Path(chemin)
    for candidat in (Path.cwd() / "signatures.yaml", RACINE_PROJET / "signatures.yaml"):
        if candidat.is_file():
            return candidat
    raise ErreurConfig("Aucun signatures.yaml trouvé (ni dans le dossier courant, ni à la racine du projet)")


@lru_cache(maxsize=8)
def _charger(chemin: str) -> Signatures:
    with open(chemin, encoding="utf-8") as f:
        brut = yaml.safe_load(f) or {}

    technologies = []
    for tid, t in (brut.get("technologies") or {}).items():
        constat = t.get("constat")
        if constat and constat not in CONTROLE_DU_CODE:
            raise ErreurConfig(f"signatures.yaml, technologie {tid} : constat inconnu « {constat} »")
        avant = t.get("obsolete_avant")
        technologies.append(
            Technologie(
                id=tid,
                nom=str(t.get("nom", tid)),
                detection=_compiler(t.get("detection"), f"technologie {tid}"),
                version=_compiler(t.get("version"), f"technologie {tid}"),
                obsolete_avant=version_en_tuple(str(avant)) if avant is not None else None,
                constat=constat,
            )
        )

    parking = brut.get("parking") or {}
    maintenance = brut.get("maintenance") or {}
    piratage = brut.get("piratage") or {}
    return Signatures(
        technologies=technologies,
        parking_phrases=_compiler(parking.get("phrases"), "parking.phrases"),
        parking_services=[str(s).lower() for s in parking.get("services") or []],
        parking_motifs_html=_compiler(parking.get("motifs_html"), "parking.motifs_html"),
        maintenance=_compiler(maintenance.get("phrases"), "maintenance"),
        maintenance_texte_max=int(maintenance.get("texte_max", 1500)),
        erreurs_php=_compiler(brut.get("erreurs_php"), "erreurs_php"),
        spam=_compiler(piratage.get("spam"), "piratage.spam"),
        seuil_spam=int(piratage.get("seuil_spam", 2)),
        redirections_autorisees=[str(s).lower() for s in piratage.get("redirections_autorisees") or []],
        page_contact=_compiler(brut.get("page_contact"), "page_contact"),
    )


def charger_signatures(chemin: str | Path | None = None) -> Signatures:
    return _charger(str(trouver_signatures(chemin).resolve()))


def hote_dans(hote: str, domaines: list[str]) -> bool:
    """Vrai si l'hôte est l'un des domaines ou un de leurs sous-domaines."""
    hote = hote.lower().rstrip(".")
    return any(hote == d or hote.endswith("." + d) for d in domaines)
