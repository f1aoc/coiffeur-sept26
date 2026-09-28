"""Chasseur de sites : repère les sites d'entreprises locales cassés ou obsolètes."""

import logging

__version__ = "1.0.0"

# Pas d'affichage des avertissements dans la console : l'interface web les écrit dans erreurs.log
# (journal.configurer) et « chasseur scan » les reporte dans la colonne non_verifies du CSV.
logging.getLogger("chasseur").addHandler(logging.NullHandler())
