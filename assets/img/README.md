# Images du site

Les six visuels de la galerie sont pour l'instant des **illustrations d'attente**
(`galerie-1.svg` … `galerie-6.svg`), dessinées aux couleurs du site.

## Mettre vos vraies photos

Déposez simplement vos fichiers dans ce dossier avec ces noms exacts :

| Fichier         | Emplacement sur le site        | Format conseillé          |
|-----------------|--------------------------------|---------------------------|
| `photo-1.jpg`   | Coupe & mouvement              | 1600 × 1200 px (4:3), JPG |
| `photo-2.jpg`   | Plantes tinctoriales           | idem                      |
| `photo-3.jpg`   | Soins & rituels                | idem                      |
| `photo-4.jpg`   | Finitions / brushing           | idem                      |
| `photo-5.jpg`   | Matière & reflets              | idem                      |
| `photo-6.jpg`   | Le bol de henné                | idem                      |

Aucune modification de code n'est nécessaire : chaque photo se superpose
automatiquement à l'illustration correspondante. Tant qu'un fichier est absent,
le dessin reste affiché — le site n'a donc jamais de trou.

Pour changer les légendes, modifiez les `<figcaption>` de la section
`<section class="galerie">` dans `index.html`.

Conseils : photos en lumière naturelle, poids < 350 Ko chacune
(compressez-les, par exemple avec Squoosh), et pensez à l'accord écrit des
personnes reconnaissables sur les clichés.
