from chasseur.analyzers.base import Analyseur
from chasseur.analyzers.browser import AnalyseurNavigateur
from chasseur.analyzers.domain import AnalyseurDomaine
from chasseur.analyzers.performance import AnalyseurPerformance
from chasseur.analyzers.reseau import AnalyseurReseau, InfoSSL

TOUS = {
    "reseau": AnalyseurReseau,
    "domaine": AnalyseurDomaine,
    "navigateur": AnalyseurNavigateur,
    "performance": AnalyseurPerformance,
}

__all__ = [
    "TOUS",
    "Analyseur",
    "AnalyseurDomaine",
    "AnalyseurNavigateur",
    "AnalyseurPerformance",
    "AnalyseurReseau",
    "InfoSSL",
]
