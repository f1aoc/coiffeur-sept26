"""Dossier de données local, moteur SQLite et sessions."""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import event, inspect, text
from sqlmodel import Session, SQLModel, create_engine

from chasseur.db import tables  # noqa: F401  (enregistre les tables)

NOM_BASE = "chasseur.db"


def dossier_donnees(chemin: str | Path | None = None) -> Path:
    """--donnees, sinon $CHASSEUR_DONNEES, sinon ~/.chasseur-de-sites."""
    dossier = Path(chemin or os.environ.get("CHASSEUR_DONNEES") or Path.home() / ".chasseur-de-sites")
    dossier.mkdir(parents=True, exist_ok=True)
    return dossier.resolve()


def migrer(moteur) -> list[str]:
    """Ajoute aux tables existantes les colonnes apparues dans une version plus récente.

    Une base créée par une version précédente est ainsi mise à jour sans perte
    (SQLite sait ajouter une colonne, pas en retirer ; il n'y en a jamais besoin ici).
    """
    ajoutees = []
    inspecteur = inspect(moteur)
    with moteur.begin() as connexion:
        for table in SQLModel.metadata.sorted_tables:
            if not inspecteur.has_table(table.name):
                continue
            existantes = {c["name"] for c in inspecteur.get_columns(table.name)}
            for colonne in table.columns:
                if colonne.name in existantes:
                    continue
                type_sql = colonne.type.compile(dialect=moteur.dialect)
                defaut = colonne.default.arg if colonne.default is not None and not callable(colonne.default.arg) else None
                clause = ""
                if isinstance(defaut, bool):
                    clause = f" DEFAULT {int(defaut)}"
                elif isinstance(defaut, (int, float)):
                    clause = f" DEFAULT {defaut}"
                elif isinstance(defaut, str):
                    clause = " DEFAULT '" + defaut.replace("'", "''") + "'"
                connexion.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{colonne.name}" {type_sql}{clause}'))
                ajoutees.append(f"{table.name}.{colonne.name}")
    return ajoutees


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
        migrer(self.moteur)

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
