# Chasseur de sites

Repère les sites web d'entreprises locales cassés ou obsolètes et les classe comme prospects.
Cahier des charges : [CAHIER_DES_CHARGES.md](CAHIER_DES_CHARGES.md).

**État : Lot 3**. Les 4 analyseurs (Réseau, Domaine, Navigateur, Performance), le scoring des tableaux 3.2 et 3.3,
les catégories Cassé / Obsolète / Correct, et l'interface web locale (base SQLite, statuts commerciaux, notes).

## Installation

```bash
cd chasseur-de-sites
python -m venv .venv && source .venv/bin/activate   # Windows : .venv\Scripts\activate
pip install -e ".[dev]"
playwright install chromium
```

Clé PageSpeed Insights (facultative, gratuite) : `performance.cle_api` dans `config.yaml`, ou mieux,
la variable d'environnement `PAGESPEED_API_KEY`. Sans clé, le contrôle Performance est noté « non vérifié ».

## Interface web

```bash
chasseur web                       # ouvre http://127.0.0.1:8765/ dans le navigateur
chasseur web --port 9000 --sans-navigateur
chasseur import resultats.csv      # importe dans l'interface un CSV produit par « chasseur scan »
```

- **Nouvelle analyse** : glisser-déposer d'un CSV ou d'un Excel, aperçu des 10 premières lignes.
  Les fichiers de l'outil Google Maps (CSV et Excel) sont reconnus automatiquement. Cet outil ne garde
  que les entreprises *sans vrai site* : elles apparaissent « Sans site ».
- **Progression** : avancement en direct, compteurs cassés / obsolètes / corrects, temps restant,
  Pause / Reprendre. Le scan tourne en tâche de fond ; si l'application est fermée, il est « Interrompu »
  et « Reprendre » analyse les sites restants.
- **Résultats** : tableau triable, filtres (catégorie, problème, statut), recherche, 50 lignes par page,
  statut commercial modifiable sur place.
- **Fiche prospect** : captures agrandissables, problèmes en langage simple, détails techniques,
  notes enregistrées automatiquement, historique des statuts.
- **Réglages** : clés API chiffrées, analyses simultanées (1 à 30), poids du scoring (les scores
  existants sont recalculés).

Les données (base `chasseur.db`, captures, fichiers importés, clé de chiffrement `cle.secret`) sont dans
`~/.chasseur-de-sites/` (ou `--donnees`, ou la variable `CHASSEUR_DONNEES`). L'interface n'écoute que sur
127.0.0.1 : elle n'est pas accessible depuis le réseau, et les requêtes venant d'un autre site sont refusées.

## Ligne de commande

```bash
chasseur scan prospects.csv                        # → prospects_resultats.csv + captures/
chasseur scan prospects.csv -o sortie/top.csv -p 20
chasseur scan prospects.csv -a reseau,domaine      # seulement certains analyseurs
chasseur scan prospects.csv --recommencer          # ignorer un scan interrompu
```

**Reprise** : chaque site terminé est écrit dans `<sortie>.journal.jsonl`. Après une interruption
(Ctrl+C, coupure), relancez la même commande : les sites déjà analysés sont ignorés. Le journal
est supprimé à la fin du scan.

### CSV d'entrée

Colonnes toutes optionnelles, reconnues sans tenir compte de la casse ni des accents :
`nom`, `url`, `téléphone`, `adresse`, `catégorie` (et synonymes : `site web`, `tel`, `entreprise`…).
Séparateur `,` `;` ou tabulation détecté automatiquement ; UTF-8 ou Windows-1252 (Excel).

### CSV de sortie

Séparateur `;`, UTF-8 avec BOM (s'ouvre tel quel dans Excel), trié par score décroissant :

- `rang, score, etat, nom, url, telephone, adresse, categorie` ;
- synthèse : `codes`, `messages_client` (phrases pour le prospect), `preuves`, `non_verifies` ;
- **une colonne `ctrl_<contrôle>` par contrôle** : `OK`, `KO : CODE…`, `non vérifié` ou `n/a` ;
- preuves techniques (§3.5) : code HTTP, expiration SSL et domaine, CMS et versions, année du copyright,
  score PageSpeed… ;
- `capture_bureau`, `capture_mobile` (WebP < 150 Ko, dans `captures/` à côté du CSV) et `capture_date`.

## Contrôles et points (config.yaml)

| Contrôle (`ctrl_…`) | Analyseur | Points | Famille |
|---|---|---|---|
| `dns` | Réseau | 40 | cassé |
| `domaine` : expiré, non enregistré ou parqué | Domaine | 40 | cassé |
| `http_5xx` : 5xx ou délai dépassé (2 essais) | Réseau | 35 | cassé |
| `http_4xx` | Réseau | 30 | cassé |
| `ssl` : certificat expiré ou invalide | Réseau | 30 | cassé |
| `page_blanche_php` | Navigateur | 30 | cassé |
| `maintenance` | Navigateur | 20 | cassé |
| `piratage` : spam, redirection vers un domaine tiers | Navigateur | 25 | cassé |
| `https` : pas de HTTPS ou pas de redirection HTTP → HTTPS | Réseau | 15 | obsolète |
| `responsive` : pas de meta viewport ou défilement à 375 px | Navigateur | 15 | obsolète |
| `copyright` : année ≤ année en cours − 3 | Navigateur | 10 | obsolète |
| `technologies` : WordPress < 6, jQuery < 3, Joomla < 3, Flash, tableaux | Navigateur | 10 | obsolète |
| `performance` : PageSpeed mobile < 40 | Performance | 10 | obsolète |
| `title_meta` | Navigateur | 5 | obsolète |
| `contact` : ni formulaire ni lien `tel:` (accueil + page contact) | Navigateur | 5 | obsolète |
| `actualites` : date la plus récente > 2 ans | Navigateur | 5 | obsolète |
| `domaine_expiration` : expire dans moins de 30 jours | Domaine | 10 | hors tableaux |
| `ssl_expiration` : certificat qui expire bientôt | Réseau | 0 | information |

- Un contrôle compte **une seule fois**, même si plusieurs de ses codes sont relevés.
- Score = somme plafonnée à 100.
- **Cassé** = au moins un contrôle « cassé » ; **Obsolète** = score ≥ 30 sans casse ; **Correct** sinon.
- **À revérifier** : aucune casse prouvée, mais l'analyseur Réseau ou Navigateur a échoué (panne de
  connexion…). On n'affiche jamais « Correct » pour un site qu'on n'a pas pu voir.
- **Sans site** : pas d'URL dans le CSV.

Les motifs de détection (CMS, parking, spam, maintenance, erreurs PHP) sont dans `signatures.yaml`.

## Garde-fous contre les faux positifs (objectif < 5 %)

- 2 essais HTTP espacés avant de conclure à une panne.
- Un 403, 429 ou 503 renvoyé au robot n'est pas retenu si le vrai navigateur affiche la page.
- « Maintenance » seulement sur une page courte (une phrase « coming soon » dans un vrai site ne suffit pas).
- Spam : au moins 2 mots différents (ou 1 dans le titre).
- Redirection vers un autre domaine tolérée vers les réseaux sociaux, annuaires et créateurs de sites.
- Domaine « non enregistré » seulement si RDAP **et** whois le confirment.
- Pas de jugement sur le contenu d'une page d'erreur HTTP (déjà comptée par l'analyseur Réseau).

## Respect des sites et sécurité (§6.2, §6.4)

- User-agent explicite `ChasseurDeSites/0.2` ; robots.txt respecté pour le rendu navigateur.
- Page d'accueil + page contact si trouvée, pas de crawl.
- Chromium isolé : un contexte neuf par site, téléchargements refusés, aucune permission, service workers
  bloqués, bac à sable Chromium (sauf en root sous Linux), 20 s maximum par page.
- PageSpeed : file d'attente dédiée (60 requêtes/min, 4 simultanées), relance sur 429/5xx.
- La clé API n'apparaît jamais dans les exports ni les messages d'erreur.

## Tests

```bash
pytest                 # 234 tests hors ligne : réponses simulées + pages locales dans un vrai Chromium
pytest -m reseau       # en plus : vrais certificats de badssl.com (connexion Internet requise)
pytest --cov=chasseur.scoring   # couverture du scoring : 100 %
```

Les tests Navigateur et le test de bout en bout sont ignorés si Chromium est absent
(`playwright install chromium`, ou `CHASSEUR_CHROMIUM=/chemin/vers/chrome`).

## Structure

```
config.yaml, signatures.yaml
chasseur/
  cli.py, config.py, controles.py, modeles.py, orchestrateur.py, reprise.py, signatures.py, urls.py
  importers/   csv_importer.py, fichiers.py (CSV/Excel, format Google Maps)
  analyzers/   base.py, reseau.py, domain.py, browser.py, page.py, performance.py
  scoring/     score.py
  reports/     csv_export.py
  db/          tables.py, moteur.py, depot.py, reglages.py, secret.py, import_resultats.py
  web/         app.py, taches.py, routes_*.py, templates/, static/
tests/
  pages/       pages HTML de test (parking, blanche, wordpress49, responsive, pirate…)
```
