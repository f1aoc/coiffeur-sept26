# Chasseur de sites

Repère les sites web d'entreprises locales cassés ou obsolètes et les classe comme prospects.

**État : Lot 1** — import CSV, analyseur Réseau (DNS, HTTP, SSL), scoring, export CSV.

## Installation

```bash
cd chasseur-de-sites
python -m venv .venv && source .venv/bin/activate   # Windows : .venv\Scripts\activate
pip install -e ".[dev]"
```

## Utilisation

```bash
chasseur scan prospects.csv                    # → prospects_resultats.csv
chasseur scan prospects.csv -o top.csv -p 20   # sortie choisie, 20 sites en parallèle
chasseur scan prospects.csv -c ma_config.yaml
```

### CSV d'entrée

Colonnes toutes optionnelles, reconnues sans tenir compte de la casse ni des accents :
`nom`, `url`, `téléphone`, `adresse`, `catégorie` (et synonymes : `site web`, `tel`, `entreprise`…).
Séparateur `,` `;` ou tabulation détecté automatiquement ; UTF-8 ou Windows-1252 (Excel).
Une URL sans `https://` est essayée en HTTPS puis en HTTP.

### CSV de sortie

Séparateur `;`, UTF-8 avec BOM (s'ouvre tel quel dans Excel), trié par score décroissant :
`rang, score, priorite, nom, url, telephone, adresse, categorie, nb_constats, codes, gravite_max, messages_client, preuves`.

## Analyseur Réseau

| Étape | Constats possibles |
|---|---|
| URL | `SITE_ABSENT`, `URL_INVALIDE` |
| DNS | `DNS_INTROUVABLE` (arrête l'analyse) |
| HTTP (2 essais, timeout 15 s, redirections suivies) | `HTTP_INJOIGNABLE` (arrête l'analyse), `HTTP_ERREUR_SERVEUR` (5xx), `HTTP_ERREUR_CLIENT` (4xx) |
| SSL (port 443) | `SSL_ABSENT`, `SSL_EXPIRE`, `SSL_INVALIDE`, `SSL_EXPIRE_BIENTOT` |

Un nouvel essai HTTP n'est fait qu'après une erreur réseau ou un code 5xx.
Une erreur de proxy local donne `ERREUR_ANALYSE` (0 point) au lieu de pénaliser le site.

Chaque constat : `{code, gravite, points, message_client, preuve}`.

## Scoring — `config.yaml`

⚠️ **Poids provisoires** en attendant les tableaux 3.2 et 3.3 du cahier des charges.
Tout se règle dans `config.yaml` sans toucher au code :

- `constats` : gravité et points par code (tableau 3.2) ;
- `score_max` : plafond du score (somme des points) ;
- `priorites` : seuils de score → libellé de priorité (tableau 3.3) ;
- `reseau` : timeout, nombre d'essais, seuil d'alerte SSL, User-Agent ;
- `parallelisme` : sites analysés en même temps (10).

## Tests

```bash
pytest              # tests hors ligne, réponses HTTP/DNS/SSL simulées
pytest -m reseau    # en plus : vrais certificats de badssl.com (connexion Internet directe requise)
```

## Structure

```
chasseur/
  cli.py, config.py, modeles.py, orchestrateur.py
  importers/   csv_importer.py
  analyzers/   base.py, reseau.py
  scoring/     score.py
  reports/     csv_export.py
  web/         (lot ultérieur)
tests/
```
