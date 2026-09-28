# Cahier des charges – Chasseur de sites cassés ou obsolètes

Sep 28, 2026 · @Patrick

## 1. Contexte et objectifs

Le logiciel analyse une liste d'entreprises locales et repère celles dont le site web est cassé, expiré ou obsolète, puis les classe par « chaleur commerciale ». Il complète l'outil existant qui trouve sur Google Maps les entreprises sans site.

Une entreprise dont le site affiche une erreur, un certificat expiré ou un design de 2014 perd des clients sans le savoir. C'est un prospect chaud : le problème est visible et se démontre en une capture d'écran.

Objectifs mesurables de la version 1 :

- Analyser 500 sites en moins de 30 minutes sur un poste standard.
- Attribuer à chaque site un score de 0 à 100 et une liste de problèmes lisibles par un non-technicien.
- Exporter une liste de prospects exploitable (CSV, Excel) et un mini-rapport PDF par prospect.
- Moins de 5 % de faux positifs sur les détections « site cassé » (vérifié sur un échantillon de 100 sites).

## 2. Utilisateurs cibles et cas d'usage

| Utilisateur | Besoin | Usage type |
| --- | --- | --- |
| Webmaster freelance | Trouver 10 à 20 prospects qualifiés par semaine | Lance un scan sur sa ville et son secteur, appelle les 10 premiers |
| Agence web locale | Alimenter l'équipe commerciale en continu | Scan hebdomadaire planifié, export vers le CRM |
| Consultant SEO local | Vendre de la remise en conformité technique | Cible les sites sans HTTPS ou très lents |

Parcours principal :

1. L'utilisateur importe une liste d'entreprises (export de l'outil Google Maps, CSV ou saisie d'une ville et d'un secteur).
2. Il lance l'analyse et suit l'avancement en direct.
3. Il consulte les résultats triés par score, filtre par type de problème.
4. Il ouvre la fiche d'un prospect : captures d'écran, problèmes détectés, coordonnées publiques.
5. Il exporte la liste ou génère le rapport PDF à joindre à son premier contact.

## 3. Périmètre fonctionnel

Le logiciel enchaîne trois modules : import des entreprises, analyse de chaque site, scoring et classement.

### 3.1 Sources d'entrée

- Import CSV ou Excel avec au minimum les colonnes nom et URL (colonnes optionnelles : téléphone, adresse, catégorie, note Google, nombre d'avis).
- Import direct du fichier produit par l'outil Google Maps existant (même format de colonnes, détection automatique).
- Recherche intégrée « secteur + ville » via l'API officielle Google Places (clé API fournie par l'utilisateur), en ne gardant que les fiches qui ont un site.
- Dédoublonnage par domaine avant analyse.

### 3.2 Détections – site cassé (priorité maximale)

| Contrôle | Méthode | Points |
| --- | --- | --- |
| Domaine qui ne résout pas (DNS) | Résolution DNS A/AAAA | 40 |
| Domaine expiré ou parqué | WHOIS/RDAP + mots-clés de pages de parking (« ce domaine est à vendre », Sedo, GoDaddy…) | 40 |
| Erreur serveur 5xx ou délai dépassé | Requête HTTP, timeout 15 s, 2 essais espacés | 35 |
| Erreur 4xx sur la page d'accueil | Code HTTP | 30 |
| Certificat SSL expiré ou invalide | Poignée de main TLS, date d'expiration, nom de domaine | 30 |
| Page blanche ou erreur PHP affichée | Taille du HTML rendu < 500 caractères de texte, motifs « Fatal error », « Warning: » | 30 |
| Site en maintenance depuis longtemps | Motifs « maintenance », « coming soon », « en construction » | 20 |
| Site piraté (signes visibles) | Motifs spam pharma/casino, redirections vers domaine tiers | 25 |

### 3.3 Détections – site obsolète

| Contrôle | Méthode | Points |
| --- | --- | --- |
| Pas de HTTPS | Absence de redirection HTTP → HTTPS | 15 |
| Non responsive | Absence de balise meta viewport + test de rendu à 375 px (défilement horizontal) | 15 |
| Copyright ancien | Année dans le pied de page ≤ année en cours − 3 | 10 |
| CMS ou technologies périmées | WordPress < 6.0, jQuery < 3, Flash, Joomla 1.x/2.x, tableaux de mise en page | 10 |
| Lenteur | PageSpeed Insights API, score mobile < 40 | 10 |
| Pas de balise title ou meta description | Analyse HTML | 5 |
| Pas de formulaire ni de lien téléphone cliquable | Recherche de `form` et `tel:` | 5 |
| Dernière actualité ancienne | Date la plus récente trouvée sur le site (blog, actualités) > 2 ans | 5 |

### 3.4 Scoring et classement

- Score = somme des points, plafonné à 100. Les poids sont modifiables dans les réglages.
- Trois catégories : **Cassé** (au moins un contrôle de 3.2 déclenché), **Obsolète** (score ≥ 30 sans casse), **Correct** (score < 30).
- Bonus d'intérêt commercial, affiché à part : fiche Google avec plus de 20 avis et une note ≥ 4 (entreprise active qui a les moyens d'investir).
- Chaque problème est traduit en une phrase simple pour le prospect, par exemple : « Votre site affiche un avertissement de sécurité aux visiteurs depuis le 12 août. »

### 3.5 Preuves

- Capture d'écran bureau (1366 px) et mobile (375 px) de chaque site analysé, horodatée.
- Conservation du code HTTP, de la date d'expiration SSL et des technologies détectées pour justifier chaque problème.

### 3.6 Hors périmètre v1

- Envoi automatique d'e-mails de prospection.
- Recherche d'adresses e-mail personnelles de dirigeants.
- Audit SEO complet (positions, backlinks).

## 4. Interface utilisateur et exports

L'interface est une application web locale (ouverte dans le navigateur), en français, avec quatre écrans.

1. **Nouvelle analyse** : glisser-déposer d'un CSV ou formulaire « secteur + ville », aperçu des 10 premières lignes, bouton Lancer.
2. **Progression** : barre d'avancement, nombre de sites analysés, cassés, obsolètes, temps restant estimé. Possibilité de mettre en pause et de reprendre.
3. **Résultats** : tableau triable (nom, ville, catégorie, score, problèmes principaux, téléphone, note Google), filtres par catégorie et par type de problème, miniature de la capture, statut commercial modifiable (À contacter, Contacté, Intéressé, Pas intéressé, Client).
4. **Fiche prospect** : captures bureau et mobile, liste des problèmes en langage simple, données techniques dépliables, champ de notes, bouton « Générer le rapport PDF ».

Exports :

- **CSV et Excel** de la liste filtrée, avec une colonne par problème détecté.
- **Rapport PDF par prospect** (2 pages) : logo et coordonnées de l'agence, captures d'écran, 3 à 5 problèmes expliqués simplement avec leur impact (« les visiteurs voient un avertissement et repartent »), appel à l'action. Aucune promesse chiffrée inventée.
- **Modèle de message** personnalisé (e-mail ou script d'appel) pré-rempli avec le nom de l'entreprise et le problème principal, à copier manuellement.
- **Réglages** : logo, nom et couleurs de l'agence pour les PDF, clés API, poids du scoring, nombre d'analyses simultanées.

## 5. Architecture technique et stack

Une application Python locale, asynchrone, qui fait passer chaque site dans un pipeline unique et stocke tout dans une base SQLite.

&#91;embedded content: architecture · 5 étapes, 4 analyseurs\]

Les quatre analyseurs tournent en parallèle pour un même site ; un analyseur en échec n'arrête pas les autres, il est noté « non vérifié ».

| Brique | Choix recommandé | Rôle |
| --- | --- | --- |
| Langage | Python 3.12 | Tout le cœur métier |
| Requêtes HTTP | httpx (asynchrone) | Codes HTTP, redirections, HTML |
| DNS et SSL | dnspython, module ssl standard | Résolution, validité et expiration du certificat |
| Domaine | Requêtes RDAP (repli python-whois) | Date d'expiration du domaine |
| Rendu et captures | Playwright (Chromium) | Rendu JavaScript, captures bureau et mobile, test responsive |
| Analyse HTML | BeautifulSoup + signatures maison | Copyright, CMS, versions, meta, formulaires |
| Performance | API PageSpeed Insights (clé gratuite) | Score mobile |
| Données | SQLite via SQLModel | Prospects, résultats, historique des scans |
| Interface | FastAPI + HTMX | Application web locale, sans build front |
| Exports | openpyxl, WeasyPrint | Excel et PDF |
| Distribution | Exécutable PyInstaller ou Docker | Installation simple chez le client |

Organisation du code attendue : `importers/`, `analyzers/` (un fichier par analyseur, interface commune), `scoring/`, `reports/`, `web/`, `tests/`. Chaque analyseur renvoie une liste de constats `{code, gravité, points, message_client, preuve}`, ce qui permet d'ajouter un contrôle sans toucher au reste.

## 6. Contraintes légales, performances et sécurité

Le logiciel n'analyse que des pages publiques et ne collecte que des données professionnelles ; c'est ce qui le rend vendable à des agences sérieuses.

### 6.1 RGPD et prospection

- Données collectées limitées aux informations publiques de l'entreprise : raison sociale, adresse, téléphone standard, site, e-mail générique (contact@, info@). Aucune recherche de données personnelles de dirigeants.
- Mention de la source et de la date de collecte pour chaque prospect.
- Bouton de suppression d'un prospect et liste d'opposition (domaines à ne plus jamais analyser ni contacter).
- Purge automatique des prospects non contactés après une durée réglable (par défaut 12 mois).
- Rappel dans l'interface : la prospection B2B par e-mail est possible si le message concerne l'activité professionnelle du destinataire et propose un moyen simple de s'opposer. L'utilisateur reste responsable de ses envois ; faire valider par un juriste avant commercialisation.

### 6.2 Respect des sites et des services tiers

- Une seule page analysée par site en v1 (page d'accueil + page contact si trouvée), aucun crawl complet.
- User-agent explicite avec le nom du logiciel, respect du robots.txt pour le rendu navigateur.
- Pas de scraping de Google Maps : uniquement l'API officielle Places, avec la clé et le quota de l'utilisateur.
- Respect des quotas PageSpeed Insights (mise en file d'attente et relance automatique).

### 6.3 Performances

- 10 sites analysés en parallèle par défaut, réglable de 1 à 30.
- Objectif : 500 sites en moins de 30 minutes, hors limitation de l'API PageSpeed.
- Reprise après interruption : un scan interrompu reprend là où il s'est arrêté.
- Captures compressées en WebP, moins de 150 Ko chacune.

### 6.4 Sécurité

- Clés API stockées chiffrées localement, jamais dans les exports.
- Interface accessible uniquement sur localhost par défaut.
- Le navigateur d'analyse tourne en mode isolé, sans téléchargement de fichiers, pour ne pas être exposé aux sites piratés détectés.
- Journal des erreurs sans données sensibles.

## 7. Planning, critères d'acceptation et démarrage

Le développement se fait en cinq lots, chacun testable seul ; demander à Claude Code de ne passer au lot suivant qu'une fois le précédent validé.

### 7.1 Lots de développement

1. **Lot 1 – Moteur en ligne de commande** : import CSV, analyseur Réseau (DNS, HTTP, SSL), scoring, export CSV. Commande : `chasseur scan prospects.csv`.
2. **Lot 2 – Analyses complètes** : analyseurs Domaine, Navigateur (captures, responsive, copyright, CMS) et Performance.
3. **Lot 3 – Interface web** : les quatre écrans, statuts commerciaux, notes, base SQLite.
4. **Lot 4 – Rapports** : PDF brandé par prospect, export Excel, modèles de messages.
5. **Lot 5 – Finitions** : recherche Places intégrée, liste d'opposition, purge automatique, exécutable installable.

### 7.2 Critères d'acceptation

- [ ] Un jeu de test de 30 URL connues (10 cassées, 10 obsolètes, 10 correctes) est classé correctement à au moins 90 %.
- [ ] Un domaine inexistant, un certificat expiré et une page parquée sont chacun détectés avec leur preuve.
- [ ] Un site en panne temporaire n'est pas classé « cassé » après une seule erreur (deuxième essai).
- [ ] 500 sites analysés en moins de 30 minutes, sans plantage, avec reprise après interruption.
- [ ] Le fichier exporté par l'outil Google Maps existant s'importe sans retouche.
- [ ] Le rapport PDF est lisible par un non-technicien et ne contient aucun jargon non expliqué.
- [ ] Tests automatisés pour chaque analyseur (pytest), couverture du scoring à 100 %.

### 7.3 Prompt de démarrage pour Claude Code

```text
Tu vas développer « Chasseur de sites », un outil Python qui repère les sites web
d'entreprises locales cassés ou obsolètes et les classe comme prospects.
Le cahier des charges complet est dans CAHIER_DES_CHARGES.md : lis-le entièrement.

Commence uniquement par le Lot 1 :
- structure du projet (importers/, analyzers/, scoring/, reports/, web/, tests/)
- import CSV (colonnes nom, url, téléphone, adresse, catégorie optionnelles)
- analyseur Réseau : DNS, code HTTP avec 2 essais et timeout 15 s, SSL (validité, expiration)
- chaque analyseur renvoie une liste de constats {code, gravité, points, message_client, preuve}
- scoring selon les tableaux 3.2 et 3.3, poids dans un fichier config.yaml
- export CSV trié par score, commande : chasseur scan prospects.csv
- tests pytest avec des URL de test et des réponses simulées

Analyse en asynchrone (httpx), 10 sites en parallèle.
Montre-moi le plan des fichiers avant d'écrire le code, puis arrête-toi à la fin du Lot 1
pour que je teste.
```

Pour l'utiliser : exporte ce document en Markdown, enregistre-le sous `CAHIER_DES_CHARGES.md` à la racine du projet, puis colle le prompt dans Claude Code.

### 7.4 Prompt pour le Lot 2

À coller une fois le Lot 1 testé et validé.

```text
Le Lot 1 est validé. Relis CAHIER_DES_CHARGES.md (sections 3.2, 3.3, 3.5 et 5)
puis réalise uniquement le Lot 2 : les analyses complètes.

1. Analyseur Domaine (analyzers/domain.py)
   - date d'expiration via RDAP, repli sur python-whois
   - détection des pages de parking : mots-clés (« domaine à vendre », « domain for sale »,
     Sedo, Dan, GoDaddy, Afternic) et redirections vers ces services
   - domaine qui expire dans moins de 30 jours = constat à part, 10 points

2. Analyseur Navigateur (analyzers/browser.py) avec Playwright Chromium
   - captures bureau 1366 px et mobile 375 px, en WebP < 150 Ko, dossier captures/
   - responsive : balise meta viewport + défilement horizontal à 375 px
   - page blanche (< 500 caractères de texte visibles), erreurs PHP affichées
   - maintenance / en construction, signes de piratage (spam pharma, casino,
     redirection vers un domaine tiers)
   - copyright : année la plus récente dans le pied de page
   - technologies : WordPress et sa version, jQuery, Joomla, Flash,
     mise en page en tableaux ; signatures dans un fichier signatures.yaml
   - title, meta description, formulaire, lien tel:
   - navigateur isolé : téléchargements bloqués, timeout 20 s par page

3. Analyseur Performance (analyzers/performance.py)
   - API PageSpeed Insights, stratégie mobile, clé dans config.yaml
   - file d'attente dédiée qui respecte le quota, relance sur erreur 429
   - si pas de clé : constat « non vérifié », sans bloquer le scan

4. Intégration
   - les 4 analyseurs tournent en parallèle pour chaque site ;
     un analyseur en échec est noté « non vérifié » sans arrêter les autres
   - scoring mis à jour avec tous les contrôles des tableaux 3.2 et 3.3
     et les catégories Cassé / Obsolète / Correct
   - export CSV : une colonne par contrôle + chemins des captures
   - reprise après interruption (sites déjà analysés ignorés)

5. Tests
   - pytest pour chaque analyseur avec pages HTML de test en local
     (parking, page blanche, WordPress 4.9, site responsive, site piraté)
   - un test de bout en bout sur 5 URL

Montre-moi d'abord la liste des fichiers créés ou modifiés, puis code.
Arrête-toi à la fin du Lot 2 et donne-moi la commande pour tester sur 20 sites.
```
