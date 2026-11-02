# Page Facebook VORELIK (anglais)

- `vorelik-facebook-couverture.png` : photo de couverture 1640 × 924 (texte dans la zone centrale, visible sur
  ordinateur et téléphone).
- `vorelik-facebook-profil.png` : photo de profil (le « V », affiché en rond).
- `vorelik-facebook-post-1…5` : visuels de publication 1080 × 1080, avec leur texte à copier dans `textes-publications.txt`.
- Pour les refaire : `python3 facebook.py DOSSIER` puis `node rendu.cjs DOSSIER` (Playwright).
- `stories/vorelik-story-1…5` (anglais) et `stories/vorelik-story-fr-1…5` (français) : stories 1080 × 1920 (Facebook et Instagram), une par publication. Contenu dans la zone
  sûre (ni dans les 260 px du haut ni dans les 380 px du bas). Ajouter l'autocollant « Lien » sur le bouton blanc.
  Pour les refaire : `python3 stories.py DOSSIER` puis `node rendu.cjs DOSSIER`.
