"""Dossier de données local, moteur SQLite et sessions."""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine

from chasseur.db import tables  # noqa: F401  (enregistre les tables)

NOM_BASE = "chasseur.db"


def dossier_donnees(chemin: str | Path | None = None) -> Path:
    """--donnees, sinon $CHASSEUR_DONNEES, sinon ~/.chasseur-de-sites."""
    dossier = Path(chemin or os.environ.get("CHASSEUR_DONNEES") or Path.home() / ".chasseur-de-sites")
    dossier.mkdir(parents=True, exist_ok=True)
    return dossier.resolve()


class Stockage:
    """Base SQLite + fichiers (captures, imports) d'un dossier de données."""

    def __init__(self, dossier: str | Path | None = None):
        self.dossier = dossier_donnees(dossier)
        self.moteur = create_engine(
            f"sqlite:///{self.dossier / NOM_BASE}",
            connect_args={"check_same_thread": False, "timeout": 30},
        )

        @event.listens_for(self.moteur, "connect")
        def _pragmas(connexion, _):
            curseur = connexion.cursor()
            curseur.execute("PRAGMA journal_mode=WAL")
            curseur.execute("PRAGMA foreign_keys=ON")
            curseur.close()

        SQLModel.metadata.create_all(self.moteur)

    @property
    def dossier_captures(self) -> Path:
        return self.dossier / "captures"

    @property
    def dossier_imports(self) -> Path:
        d = self.dossier / "imports"
        d.mkdir(exist_ok=True)
        return d

    def relatif(self, chemin: str | Path) -> str:
        """Chemin stocké en base : relatif au dossier de données, avec des « / »."""
        return Path(chemin).resolve().relative_to(self.dossier).as_posix()

    def absolu(self, relatif: str) -> Path:
        return self.dossier / relatif

    @contextmanager
    def session(self):
        with Session(self.moteur, expire_on_commit=False) as s:
            yield s
