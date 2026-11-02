# Bannières YouTube VORELIK

- `vorelik-banniere-youtube-fr.png` et `vorelik-banniere-youtube-en.png` : 2560 × 1440 pixels, à envoyer telles quelles
  sur YouTube (YouTube Studio → Personnalisation → Branding → Image de bannière → Importer).
- Tout le texte est dans la zone visible sur tous les appareils (1546 × 423 au centre) ; les captures des logiciels
  sur les côtés n'apparaissent que sur ordinateur et télévision.
- Pour les refaire (après un changement de texte ou de logo) : `python3 banniere.py DOSSIER`, puis capture de
  `banniere-fr.html` et `banniere-en.html` en 2560 × 1440 (navigateur sans interface, par exemple Playwright).
- Le logo du site (240 × 80) est agrandi environ 1,25 fois : avec un logo en haute définition, remplacer
  `vorelik-logo.png` dans le script pour un rendu plus net.
