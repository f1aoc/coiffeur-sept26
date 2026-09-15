# L'Hair d'Aujourd'hui — site vitrine

Refonte du site [coiffure-hairdaujourdhui.fr](https://coiffure-hairdaujourdhui.fr/),
salon de coiffure mixte à L'Isle-sur-la-Sorgue (84800), spécialisé dans les
produits naturels et végétaux **Végétalement Provence**.

Six pages statiques, sans framework ni dépendance : HTML, une feuille de style,
un petit script. Les noms de fichiers reprennent ceux du site actuel, donc la
mise en ligne se fait en remplacement direct sans casser le référencement.

| Fichier                  | Page                  |
|--------------------------|-----------------------|
| `index.html`             | Le salon (accueil)    |
| `produits-naturels.html` | Produits naturels     |
| `spa-cheveu.html`        | Spa du cheveu         |
| `tarifs.html`            | Prestations & tarifs  |
| `contact.html`           | Contact               |
| `mentions.html`          | Mentions légales      |

## Direction artistique

**Le nuancier végétal.** Une coloration aux plantes, c'est du pigment extrait de
feuilles et de racines : le site est donc construit autour du nuancier des
plantes tinctoriales, présenté en échantillons sur la page d'accueil. C'est le
seul endroit où le site hausse la voix ; tout le reste est tenu au calme et à la
lisibilité, parce que le premier travail de ce site est de faire décrocher le
téléphone.

| Rôle                  | Valeur    | Plante          |
|-----------------------|-----------|-----------------|
| Encre principale      | `#24374e` | indigo          |
| Accent, liens, appel  | `#a6431e` | henné           |
| Profond               | `#7e2b38` | garance         |
| Or                    | `#c9a227` | cassia          |
| Végétal               | `#5e7b6b` | Sorgue          |
| Brun                  | `#4a3527` | brou de noix    |
| Doré clair            | `#d2b14e` | camomille       |
| Fond                  | `#e9ede6` | papier minéral  |

Typographies (Google Fonts) : **Fraunces** pour les titres, **Karla** pour le
texte courant. Le logo reste typographique, comme sur le site actuel.

## Photos

Les photos sont celles du site existant, servies depuis le compte Cloudinary
`res.cloudinary.com/ddpeetkek/` et appelées par leur URL d'origine — rien à
téléverser, rien à recompresser.

Pour remplacer une photo : téléversez la nouvelle sur Cloudinary et changez
l'URL dans le `src` correspondant. Chaque image a un `width`/`height` et un
cadrage `object-fit: cover`, donc le format exact du fichier n'a pas
d'importance pour la mise en page.

## Accessibilité

Contrastes vérifiés au niveau AA (le plus faible mesuré est de 4,53:1), lien
d'évitement, focus visible, navigation au clavier, `prefers-reduced-motion`
respecté. Une seule animation sur le site : les échantillons du nuancier se
déploient quand la section arrive à l'écran.

## Mise en ligne

Hébergement statique, aucune compilation. Déposez le dossier tel quel (GitHub
Pages, Netlify, Vercel, ou FTP vers `public_html/`).

Test en local :

```bash
python3 -m http.server 8000   # puis http://localhost:8000
```

## À relire avant publication

- **Adresse** : le site actuel indique le 82 chemin des Espélugues, les
  annuaires publics le 80. C'est le 82 qui a été repris ici — à confirmer.
- **Horaires** : mardi–vendredi 9h–19h, samedi 9h–17h, fermé lundi et dimanche.
- **Tarifs** : repris à l'identique de la page actuelle. À vérifier s'ils ont
  bougé depuis.
- **Mentions légales** : l'hébergeur indiqué est GitHub ; à corriger si le site
  est déposé ailleurs.
- **Photos de personnes reconnaissables** : pensez à l'accord écrit.

## Informations utilisées

82 chemin des Espélugues, centre commercial Super U, 84800 L'Isle-sur-la-Sorgue ·
04 90 38 67 34 · mardi–vendredi 9h–19h, samedi 9h–17h · fermé lundi et dimanche.
