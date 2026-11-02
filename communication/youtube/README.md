# Bannières YouTube VORELIK

- `vorelik-banniere-youtube-fr.png` et `vorelik-banniere-youtube-en.png` : 2560 × 1440 pixels, à envoyer telles quelles
  sur YouTube (YouTube Studio → Personnalisation → Branding → Image de bannière → Importer).
- Tout le texte est dans la zone visible sur tous les appareils (1546 × 423 au centre) ; les captures des logiciels
  sur les côtés n'apparaissent que sur ordinateur et télévision.
- Pour les refaire (après un changement de texte ou de logo) : `python3 banniere.py DOSSIER`, puis capture de
  `banniere-fr.html` et `banniere-en.html` en 2560 × 1440 (navigateur sans interface, par exemple Playwright).
- Le logo du site (240 × 80) est agrandi environ 1,25 fois : avec un logo en haute définition, remplacer
  `vorelik-logo.png` dans le script pour un rendu plus net.

## Miniatures de vidéos (1280 × 720)

`miniatures/` : 4 miniatures en français et en anglais, dans le style de la bannière (une par logiciel + une VORELIK).
Pour en créer une nouvelle (autre titre, autre étiquette) : ajouter une ligne à `MINIATURES` dans `miniatures.py`
(le mot entre [crochets] est mis en jaune, `<br>` = retour à la ligne, 3 lignes courtes au maximum), puis
`python3 miniatures.py DOSSIER` et `node rendu.cjs DOSSIER` (Playwright) : les .jpg sont créés dans DOSSIER.
