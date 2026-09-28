"""Bonus d'intérêt commercial (§3.4), affiché à part du score.

Une fiche Google avec plus de 20 avis et une note d'au moins 4 : entreprise
active, qui a probablement les moyens d'investir. « Prospects prioritaires » :
site cassé ou obsolète ET bonus.
"""

from __future__ import annotations

AVIS_MIN = 20  # strictement plus de 20 avis
NOTE_MIN = 4.0
ETATS_PRIORITAIRES = ("Cassé", "Obsolète")


def a_bonus(note: float | None, avis: int | None) -> bool:
    return note is not None and avis is not None and note >= NOTE_MIN and avis > AVIS_MIN


def prioritaire(etat: str, note: float | None, avis: int | None) -> bool:
    return etat in ETATS_PRIORITAIRES and a_bonus(note, avis)


def condition_bonus(table):
    """Condition SQL équivalente à a_bonus() sur une table de prospects."""
    return (table.note_google >= NOTE_MIN) & (table.nb_avis > AVIS_MIN)
