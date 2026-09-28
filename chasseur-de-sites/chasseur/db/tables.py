"""Tables SQLite (SQLModel) : scans, prospects, constats, captures, notes,
historique des statuts commerciaux et réglages."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

STATUTS_COMMERCIAUX = ("À contacter", "Contacté", "Intéressé", "Pas intéressé", "Client")
STATUT_INITIAL = STATUTS_COMMERCIAUX[0]

# Cycle de vie d'un scan
EN_ATTENTE, EN_COURS, EN_PAUSE, TERMINE, INTERROMPU, EN_ERREUR = (
    "en_attente", "en_cours", "en_pause", "termine", "interrompu", "erreur",
)
LIBELLES_SCAN = {
    EN_ATTENTE: "En attente",
    EN_COURS: "En cours",
    EN_PAUSE: "En pause",
    TERMINE: "Terminé",
    INTERROMPU: "Interrompu",
    EN_ERREUR: "Erreur",
}


def maintenant() -> datetime:
    """Horodatage en UTC (converti à l'heure locale à l'affichage)."""
    return datetime.now(timezone.utc).replace(microsecond=0)


def heure_locale(d: datetime | None) -> datetime | None:
    if d is None:
        return None
    if d.tzinfo is None:  # SQLite peut rendre une date sans fuseau : elle a été écrite en UTC
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone()


class Scan(SQLModel, table=True):
    __tablename__ = "scans"

    id: int | None = Field(default=None, primary_key=True)
    nom: str
    fichier: str = ""
    format: str = ""
    statut: str = Field(default=EN_ATTENTE, index=True)
    total: int = 0
    cree_le: datetime = Field(default_factory=maintenant)
    demarre_le: datetime | None = None
    termine_le: datetime | None = None
    erreur: str = ""
    # Lot 5 : relance hebdomadaire et filiation des scans (pour la comparaison)
    source: str = ""  # « Import … » ou « Recherche Google Places … »
    planifie: bool = False
    prochaine_execution: datetime | None = None
    origine_id: int | None = Field(default=None, index=True)  # scan d'origine d'une relance


class ProspectDB(SQLModel, table=True):
    __tablename__ = "prospects"

    id: int | None = Field(default=None, primary_key=True)
    scan_id: int = Field(foreign_key="scans.id", index=True)
    nom: str = Field(default="", index=True)
    url: str = ""
    telephone: str = ""
    adresse: str = ""
    ville: str = Field(default="", index=True)
    categorie: str = ""
    note_google: float | None = None
    nb_avis: int | None = None
    lien_maps: str = ""
    remarque: str = ""
    ligne: int = 0
    source: str = ""  # d'où vient la fiche (fichier importé…)
    collecte_le: datetime = Field(default_factory=maintenant)
    # Résultat d'analyse
    analyse: bool = Field(default=False, index=True)
    analyse_le: datetime | None = None
    score: int = Field(default=0, index=True)
    etat: str = Field(default="", index=True)
    mesures: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False, default=dict))
    non_verifies: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False, default=dict))
    sans_objet: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False, default=list))
    echecs: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False, default=list))
    # Suivi commercial
    statut: str = Field(default=STATUT_INITIAL, index=True)


class ConstatDB(SQLModel, table=True):
    __tablename__ = "constats"

    id: int | None = Field(default=None, primary_key=True)
    prospect_id: int = Field(foreign_key="prospects.id", index=True)
    code: str = Field(index=True)
    controle: str = Field(default="", index=True)
    gravite: str = ""
    points: int = 0
    message_client: str = ""
    preuve: str = ""


class Capture(SQLModel, table=True):
    __tablename__ = "captures"

    id: int | None = Field(default=None, primary_key=True)
    prospect_id: int = Field(foreign_key="prospects.id", index=True)
    type: str  # « bureau » ou « mobile »
    chemin: str  # relatif au dossier de données
    miniature: str = ""
    prise_le: datetime | None = None


class Note(SQLModel, table=True):
    __tablename__ = "notes"

    id: int | None = Field(default=None, primary_key=True)
    prospect_id: int = Field(foreign_key="prospects.id", index=True, unique=True)
    texte: str = ""
    modifie_le: datetime = Field(default_factory=maintenant)


class HistoriqueStatut(SQLModel, table=True):
    __tablename__ = "historique_statuts"

    id: int | None = Field(default=None, primary_key=True)
    prospect_id: int = Field(foreign_key="prospects.id", index=True)
    ancien: str
    nouveau: str
    change_le: datetime = Field(default_factory=maintenant)


class Reglage(SQLModel, table=True):
    __tablename__ = "reglages"

    cle: str = Field(primary_key=True)
    valeur: str = ""
    chiffre: bool = False


class Opposition(SQLModel, table=True):
    """Liste d'opposition (§6.1) : domaines à ne plus jamais analyser, exporter ni contacter."""

    __tablename__ = "oppositions"

    id: int | None = Field(default=None, primary_key=True)
    domaine: str = Field(index=True, unique=True)
    motif: str = ""
    ajoute_le: datetime = Field(default_factory=maintenant)
