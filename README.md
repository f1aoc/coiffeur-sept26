# L'Hair d'Aujourd'hui — site vitrine

Site vitrine animé pour **L'Hair d'Aujourd'hui**, salon de coiffure mixte à
L'Isle-sur-la-Sorgue (84800), spécialisé dans les produits naturels et végétaux.

Page unique, sans framework ni dépendance : trois fichiers suffisent à la mise
en ligne (`index.html`, `assets/css/style.css`, `assets/js/main.js`).

## Direction artistique

Style « carnet de studio » : papier crème, encre vert forêt, surligneur jaune.

| Rôle              | Valeur    |
|-------------------|-----------|
| Texte & aplats    | `#1a3300` |
| Fond              | `#fcfaf5` |
| Surligneur        | `#ffe95c` |
| Menthe            | `#d5f5c2` |
| Bleu pastel       | `#a8e5e5` |
| Rose pastel       | `#f6d0ff` |
| Terracotta        | `#cb5521` |

Typographies (Google Fonts) : **Bricolage Grotesque 800** pour les titres,
**Inter** pour le texte courant, **Roboto Mono** pour les micro-étiquettes.

## Animations

Rideau d'ouverture · barre de progression de lecture · curseur personnalisé
(anneau magnétique + libellé « voir » sur la galerie) · titres découpés mot à
mot qui montent · surligneur jaune qui se trace au passage · apparitions en
cascade au scroll · bandeau défilant sensible à la vitesse de défilement ·
parallaxe sur le tracé du héros · galerie horizontale pilotée par le scroll
vertical · cartes inclinables au survol · boutons magnétiques · compteurs
animés · accordéon des prestations · SVG qui se dessine au trait.

Tout est désactivé automatiquement si le visiteur a activé
« réduire les animations » dans son système (`prefers-reduced-motion`).

## Mise en ligne

Hébergement statique : déposez le dossier tel quel (Netlify, Vercel, GitHub
Pages, ou un simple FTP vers `public_html/`). Aucune compilation.

Test en local :

```bash
python3 -m http.server 8000   # puis http://localhost:8000
```

## À compléter avant publication

- **Photos** : voir `assets/img/README.md` (les visuels actuels sont des
  illustrations d'attente).
- **Tarifs** : chaque prestation affiche `sur devis` dans
  `<span class="prix">` — remplacez par vos montants si vous souhaitez les
  afficher.
- **Textes** : les informations pratiques (adresse, téléphone, horaires)
  proviennent des annuaires publics ; relisez-les et ajustez les descriptions
  de prestations à votre façon de travailler.
- **Avis clients** : la page renvoie vers Planity, PagesJaunes et Facebook
  plutôt que d'afficher des témoignages recopiés. Pour citer un avis, ajoutez-le
  avec l'accord de la cliente.
- **Mentions légales / RGPD** : à ajouter (page ou section) avant mise en ligne.

## Informations utilisées

80 chemin des Espélugues, centre commercial Super U, 84800 L'Isle-sur-la-Sorgue ·
04 90 38 67 34 · mardi–vendredi 9h–19h, samedi 9h–18h, fermé lundi et dimanche ·
réservation Planity.
