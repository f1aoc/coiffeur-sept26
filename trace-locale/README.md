# Trace Locale — page de vente et liste d'attente

Page de vente pour **Trace Locale**, un service de veille sur les **domaines
expirés dont le site était rattaché à une fiche Google Business** (France et
francophonie).

Page unique, sans framework ni dépendance : trois fichiers suffisent à la mise
en ligne (`index.html`, `assets/css/style.css`, `assets/js/main.js`).

## Le produit

Les listes de domaines expirés sont publiques et gratuites. Elles ne disent pas
lequel de ces milliers de noms appartenait à un commerce réel, avec une adresse,
une catégorie et des années de citations dans les annuaires locaux. Trace Locale
vend ce croisement, livré chaque matin :

| Bloc | Contenu |
|------|---------|
| Domaine | Nom complet, extension, registrar sortant |
| Établissement | Catégorie Google principale et secondaires |
| Localisation | Commune, code postal, département, région |
| Audience | Nombre d'avis et note, dernière observation |
| Liens | Domaines référents, liens entrants, score d'autorité |
| Ancienneté | Date de première archive connue |
| Calendrier | Expiration, date de libération, jours restants |

**Clients visés** : consultants SEO local, agences web, investisseurs en noms de
domaine, éditeurs de sites de génération de leads.

**Formules** : Veille 0 € (3 fiches/semaine) · Indépendant 39 €/mois · Agence
129 €/mois. Offre de lancement : −50 % à vie pour les 100 premiers inscrits.

## Direction artistique

Un bulletin de veille, pas une page SaaS générique : la donnée se lit comme un
registre.

| Rôle | Clair | Sombre |
|------|-----------|-----------|
| Marque (outremer) | `#1f2b6b` | `#9dabf6` |
| Urgence (vermillon) | `#b93c1c` | `#ff8a66` |
| Disponible (vert) | `#146b4f` | `#4fc79b` |
| Papier | `#edeef1` | `#0e1016` |
| Surface | `#fbfbfc` | `#161923` |
| Encre | `#12151c` | `#e9ebf2` |
| Encre secondaire | `#58607a` | `#98a1b9` |

Typographies (Google Fonts) : **Spectral** 600/700 pour les titres — dessinée
par Production Type, fonderie parisienne —, **IBM Plex Sans** pour le texte
courant, **IBM Plex Mono** pour les domaines, les dates et les étiquettes.

Le thème suit le réglage système ; le bouton de la barre haute force un choix,
mémorisé localement quand le navigateur l'autorise.

## Configurer le formulaire

Tout est en haut de `assets/js/main.js` :

```js
var CONFIG = {
  endpoint: "",                      // ← URL Formspree / Tally / Brevo / la vôtre
  contact:  "contact@tracelocale.fr" // ← adresse de repli et de contact
};
```

- **`endpoint` renseigné** : le formulaire envoie un `POST` JSON et affiche la
  confirmation sans quitter la page.
- **`endpoint` vide** (état livré) : le formulaire ouvre un email pré-rempli vers
  `contact`. Aucune inscription n'est perdue, mais la collecte n'est pas
  automatique — à renseigner avant toute campagne.

Champs transmis : `prenom`, `email`, `metier`, `departements`, `besoin`,
`consent`, `source`.

## Mise en ligne

Hébergement statique : déposez le dossier tel quel (Netlify, Vercel, GitHub
Pages, ou un simple FTP vers `public_html/`). Aucune compilation.

```bash
python3 -m http.server 8000   # puis http://localhost:8000
```

## Les données de démonstration

Le tableau de la section « Aperçu » est alimenté par la constante `DEMO` de
`assets/js/main.js` : **14 lignes illustratives figées au bulletin du
19/09/2026**. Aucune ne désigne un établissement réel — elles montrent la forme
de la donnée, pas la donnée. Un bandeau le dit explicitement sur la page.

Les noms de domaine y sont tronqués (`stem` visible, `mask` caractères masqués).
Ce n'est pas qu'une précaution de démo : c'est le mécanisme du produit. Une
fenêtre de libération dure quelques jours, publier les noms en clair
reviendrait à donner le travail.

## À faire avant d'ouvrir le service

### Produit

- **Le pipeline de données.** C'est le vrai travail, et il n'est pas dans ce
  dépôt. Trois passes nocturnes : collecte (fichier quotidien des domaines
  supprimés de l'AFNIC pour le `.fr`, flux de *drop* des registres pour
  `.com`/`.net`/`.org`, WHOIS de contrôle), croisement avec les fiches
  d'établissement Google sur le domaine enregistré, puis qualification
  (catégorie, commune, avis, domaines référents, ancienneté, date de
  libération).
- **Budget données.** Le croisement fiches + backlinks passe par une API payante
  (DataForSEO, Semrush ou équivalent). À chiffrer avant de fixer les prix :
  c'est le coût variable principal, et il détermine si 39 €/mois tient.
- **Paiement.** Stripe Billing pour les deux formules payantes, plus un compte
  et un espace abonné — le tableau public ne montre que des noms masqués.

### Juridique et conformité

- **Mentions légales et politique de confidentialité** : à publier avant
  ouverture. Le pied de page l'annonce, les pages n'existent pas encore.
- **RGPD** : registre de traitement, durée de conservation (annoncée sur la page
  à 12 mois après lancement), procédure d'accès et de suppression, lien de
  désinscription dans chaque email.
- **Promesse produit** : la page dit clairement qu'acheter un domaine ne donne
  pas la fiche Google. Ne pas laisser cette phrase disparaître d'une future
  version — c'est ce qui sépare un outil de recherche d'un argumentaire de
  détournement de fiche, et c'est aussi ce qui protège les clients.
- **Marque** : la vérification INPI reste à la charge de l'acheteur, la FAQ le
  dit. Si le service devait un jour la pré-filtrer, ce serait une fonction à
  part entière, pas une mention.

### Commercial

- **Valider les prix** avant de les figer : les réponses du formulaire
  (activité, départements, volume acheté) servent exactement à ça.
- **Couverture géographique** : l'ordre des départements se décide sur les
  réponses reçues, pas à l'avance.
