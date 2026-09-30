# Chasseur de sites by ptabountchikoff

Repère les sites web d'entreprises locales **cassés, expirés ou obsolètes**, les classe par « chaleur commerciale »
et prépare le premier contact : rapport PDF à vos couleurs, export Excel, messages pré-remplis.
Application locale, en français : vos données restent sur votre ordinateur.

Cahier des charges : [CAHIER_DES_CHARGES.md](CAHIER_DES_CHARGES.md) · Recette : [RECETTE.md](RECETTE.md) ·
Exemples de rapports : [exemples/](exemples/)

---

## 1. Installation

Trois possibilités ; choisissez-en **une**.

### A. Exécutable (le plus simple, Windows ou macOS)

1. Téléchargez la dernière version (liens permanents, sans compte GitHub) :
   - Windows : [ChasseurDeSites.exe](https://github.com/f1aoc/coiffeur-sept26/releases/download/chasseurdesites-latest/ChasseurDeSites.exe)
   - Mac M1 à M4 : [ChasseurDeSites-mac-apple-silicon.zip](https://github.com/f1aoc/coiffeur-sept26/releases/download/chasseurdesites-latest/ChasseurDeSites-mac-apple-silicon.zip)
   - Mac Intel : [ChasseurDeSites-mac-intel.zip](https://github.com/f1aoc/coiffeur-sept26/releases/download/chasseurdesites-latest/ChasseurDeSites-mac-intel.zip)

   (Onglet **Releases** du dépôt → « Chasseur de sites by ptabountchikoff » ; chaque modification du dossier
   `chasseur-de-sites` la met à jour automatiquement.)
2. **Windows** : double-cliquez sur **ChasseurDeSites.exe** (un seul fichier,
   à ranger où vous voulez). Windows peut afficher « Windows a protégé votre ordinateur » (application non signée) :
   **Informations complémentaires → Exécuter quand même**.
   **Mac** : décompressez, glissez **ChasseurDeSites** dans Applications et ouvrez-le. La première fois, macOS le
   bloque (application non notariée) : Réglages Système → Confidentialité et sécurité → **Ouvrir quand même**.
3. Une petite fenêtre « Chasseur de sites » s'ouvre. **Premier lancement** : elle télécharge le navigateur d'analyse
   (Chromium, environ 150 Mo), une seule fois. Puis l'interface s'ouvre dans votre navigateur.
4. **Gardez la petite fenêtre ouverte** (vous pouvez la réduire) : « Quitter » ou la fermer arrête l'application.
   Relancer l'application quand elle tourne déjà rouvre simplement l'interface.

### B. Avec Python (pour suivre les mises à jour)

Installez Python 3.12 depuis python.org (**cochez « Add python.exe to PATH »**), téléchargez le projet, puis dans
PowerShell ouvert dans le dossier `chasseur-de-sites` :

```powershell
python -m venv .venv
.venv\Scripts\activate            # macOS / Linux : source .venv/bin/activate
pip install -e ".[dev]"
playwright install chromium
chasseur web
```

Les fois suivantes : `.venv\Scripts\activate` puis `chasseur web`.

### C. Docker

```bash
cd chasseur-de-sites
docker compose up -d        # puis ouvrir http://localhost:8765
```

Les données sont dans le volume `chasseur-donnees`. Le port n'est publié que sur `127.0.0.1`.

---

## 2. Clés API (facultatives)

Elles se collent dans **Réglages → Clés API**. Elles y sont chiffrées, jamais réaffichées en entier, jamais exportées
ni écrites dans le journal.

| Clé | À quoi elle sert | Où l'obtenir |
|---|---|---|
| **Google Places** | Recherche « secteur + ville » (écran Recherche) | [Google Cloud](https://console.cloud.google.com/) → créer un projet → activer **Places API (New)** → Identifiants → Créer une clé API (restreignez-la à cette API) |
| **PageSpeed Insights** | Contrôle « lenteur sur mobile » | [Google Cloud](https://console.cloud.google.com/) → activer **PageSpeed Insights API** → clé API (gratuite) |

Sans clé Places, importez vos listes en CSV/Excel. Sans clé PageSpeed, la vitesse est notée « non vérifiée » et le
reste de l'analyse fonctionne normalement.

**Coût Google Places** : l'écran Recherche affiche le nombre maximal de requêtes et une estimation *avant* de lancer.
Le tarif utilisé est indicatif (réglable dans `config.yaml`, section `places`) : vérifiez le tarif en vigueur sur la
[page de tarification Google Maps Platform](https://developers.google.com/maps/billing-and-pricing/pricing).

---

## 3. Premier scan, pas à pas

1. **Réglages → Votre agence** : nom, logo, couleur, coordonnées (utilisés dans les PDF et les messages).
2. Trouvez des entreprises, au choix :
   - **Recherche** : secteur (« coiffeur ») + villes → **Estimer le coût** → **Lancer la recherche** ;
   - **Nouvelle analyse** : glissez un CSV ou un Excel avec au moins les colonnes `nom` et `url`
     (facultatives : `téléphone`, `adresse`, `ville`, `catégorie`, `note`, `avis`).
3. Vérifiez l'aperçu (doublons de domaine et domaines en opposition déjà retirés) → **Lancer l'analyse**.
4. **Progression** : suivez l'avancement ; Pause / Reprendre à tout moment. Si vous fermez l'application,
   « Reprendre » analyse les sites restants.
5. **Résultats** : triez, filtrez (catégorie, problème, statut, **Prospects prioritaires**), ouvrez une fiche en
   cliquant sur le nom.
6. **Fiche** : captures, problèmes expliqués simplement, **Générer le rapport PDF**, messages e-mail / appel / SMS
   à copier, notes, statut commercial.

Exemple de CSV :

```
nom;url;telephone;ville
Salon Léa;www.salon-lea.fr;04 90 00 00 01;Avignon
Garage Dupont;garage-dupont.fr;04 90 00 00 02;Cavaillon
```

---

## 4. Ce que l'outil vérifie

| Catégorie | Contrôles (points) |
|---|---|
| **Cassé** (un seul suffit) | domaine introuvable (40) · domaine expiré ou parqué (40) · erreur serveur ou délai dépassé après 2 essais (35) · page d'accueil introuvable (30) · certificat de sécurité expiré ou invalide (30) · page blanche ou erreur affichée (30) · « en construction » (20) · signes de piratage (25) |
| **Obsolète** (score ≥ 30) | pas de HTTPS (15) · pas adapté au mobile (15) · copyright ancien (10) · CMS ou technologies périmées (10) · lent sur mobile (10) · pas de titre ou description Google (5) · ni formulaire ni appel en un clic (5) · actualités de plus de 2 ans (5) |
| **Correct** | score < 30 |

Score = somme plafonnée à 100 ; les poids se modifient dans **Réglages**. **Bonus commercial** (affiché à part) :
fiche Google avec plus de 20 avis et une note d'au moins 4. **Prospects prioritaires** = cassé ou obsolète + bonus.

---

## 5. Conformité (RGPD) et respect des sites

- Seules des informations publiques d'entreprise sont collectées ; chaque prospect garde sa **source** et sa
  **date de collecte**.
- **Supprimer un prospect** : en bas de sa fiche (captures, notes et historique compris).
- **Liste d'opposition** (lien en bas de page) : un domaine ajouté n'est plus jamais importé, analysé ni exporté.
- **Purge automatique** des prospects jamais contactés après 12 mois (réglable dans Réglages).
- Rappel : la prospection B2B par e-mail est possible si le message concerne l'activité professionnelle du
  destinataire et propose un moyen simple de s'opposer. Vous restez responsable de vos envois : faites valider par
  un juriste avant de commercialiser.
- User-agent explicite `ChasseurDeSites/1.0`, robots.txt respecté, page d'accueil + page contact seulement,
  aucun scraping de Google Maps (API officielle uniquement).
- Navigateur d'analyse isolé : téléchargements bloqués, contexte neuf par site, 20 s par page.

---

## 6. Suivi dans le temps

- **Relance hebdomadaire** : sur l'écran Progression d'une analyse → « Relancer cette analyse chaque semaine ».
  Le statut commercial est conservé. Les relances ont lieu quand l'application est ouverte ; pour un ordinateur
  souvent éteint, programmez `chasseur planifies` dans le Planificateur de tâches Windows (ou cron).
- **Comparaison** : « Comparer avec une autre analyse » → sites **devenus cassés** depuis la dernière fois,
  sites réparés, autres changements.

---

## 7. Ligne de commande

```bash
chasseur web                          # interface (http://127.0.0.1:8765)
chasseur scan prospects.csv           # analyse sans interface → prospects_resultats.csv + captures/
chasseur import prospects_resultats.csv   # importe ces résultats dans l'interface
chasseur rapport 12 -o diagnostic.pdf # rapport PDF du prospect n° 12 (numéro dans l'adresse de sa fiche)
chasseur planifies                    # lance les analyses planifiées arrivées à échéance
chasseur purge                        # applique la durée de conservation
chasseur recette jeu.csv              # mesure le taux de bon classement sur un jeu étiqueté (colonne « attendu »)
```

---

## 8. FAQ

**Où sont mes données ?** Dans `C:\Users\<vous>\.chasseur-de-sites\` (Windows) ou `~/.chasseur-de-sites/` :
base `chasseur.db`, captures, clé de chiffrement `cle.secret`, journal `erreurs.log`. Sauvegardez ce dossier pour
tout garder ; supprimez-le pour tout effacer. La page **À propos** l'indique.

**Je mets à jour l'application : vais-je perdre mes prospects ?** Non. Les données sont à part, et la base est
mise à jour automatiquement au démarrage.

**Beaucoup de sites « À revérifier » ?** L'analyse n'a pas pu les voir (connexion coupée, pare-feu, proxy
d'entreprise). Vérifiez votre connexion puis relancez l'analyse. Ils ne sont jamais classés « Correct » à tort.

**Un site marche chez moi mais ressort « Cassé » ?** Ouvrez sa fiche → Détails techniques : la preuve y figure
(code d'erreur, date du certificat…). Deux essais sont faits avant de conclure à une panne, et un blocage des robots
n'est pas retenu si le vrai navigateur affiche la page.

**Les fichiers de mon outil Google Maps ressortent tous « Sans site » ?** C'est normal : cet outil ne garde que les
entreprises sans vrai site. Pour chasser les sites cassés, utilisez l'écran **Recherche** ou un fichier d'entreprises
qui ont un site.

**Combien de temps pour 500 sites ?** Voir [RECETTE.md](RECETTE.md). Le temps dépend surtout du nombre de sites en
panne (chacun attend 2 × 15 s) ; 10 sites en parallèle par défaut, jusqu'à 30 dans Réglages.

**Le PDF utilise-t-il WeasyPrint ?** S'il est installé (`pip install -e ".[weasyprint]"`, qui demande GTK/Pango
sous Windows), oui ; sinon Chromium, avec le même rendu.

**L'interface est-elle accessible depuis Internet ?** Non : elle n'écoute que sur votre ordinateur (127.0.0.1) et
refuse les requêtes venant d'autres sites.

**Une erreur ?** Page **À propos** → « Dernières erreurs » (clés et e-mails masqués).

---

## 9. Page de vente

`site/` contient la page de vente (`index.html` + `assets/`) et la page de remerciement après achat
(`merci.html` : boutons de téléchargement Windows / Mac et guide de démarrage, non référencée par Google ;
indiquez-la comme page de retour après paiement). Aucune construction : envoyez le dossier sur n'importe quel
hébergeur statique (Netlify, Vercel, GitHub Pages, FTP). Elle est aussi publiée dans la release sous
`ChasseurDeSites-site.zip`.

Avant de publier, modifiez les lignes marquées `À MODIFIER` : le prix et le lien d'achat (lien de paiement
Stripe / PayPal ou e-mail) dans `index.html`, l'adresse e-mail du support dans `merci.html`.
Les captures (`assets/app-screenshot.jpg`, `assets/rapport-exemple.jpg`) montrent des données fictives.

---

## 10. Pour les développeurs

```bash
pytest                    # tests hors ligne (réponses simulées, pages locales dans un vrai Chromium)
pytest -m reseau          # vrais certificats de badssl.com (Internet requis)
pytest -m charge          # 500 sites locaux, temps et reprise après interruption
pytest --cov=chasseur.scoring
python packaging/icone.py && pyinstaller packaging/chasseur.spec --noconfirm   # dist/ChasseurDeSites.exe (Windows), .app (Mac)
```

Structure : `chasseur/` (`importers/`, `analyzers/`, `scoring/`, `reports/`, `web/`, `db/`, `sources/`),
`config.yaml` (poids, délais, tarifs), `signatures.yaml` (motifs de détection), `tests/`, `packaging/`.
