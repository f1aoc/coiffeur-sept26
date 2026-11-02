# Publicités Meta (Facebook et Instagram)

- `vorelik-pub-fr-1…3` et `vorelik-pub-en-1…3` : 3 annonces par langue, chacune en carré 1080 × 1080 (fil d'actualité)
  et en vertical 1080 × 1920 (stories et Reels).
- `textes-annonces.txt` : texte principal, titre, description, bouton et lien (avec un « ref » par annonce) à coller
  dans le Gestionnaire de publicités, et les règles publicitaires de Meta à respecter.
- Les captures `capture-pub-fr/en.png` ne montrent que des commerces « Aucun site » : aucune mention de Facebook ou
  d'Instagram dans les images (règle de Meta). Elles se refont avec `capture_pub.py` (BridgeToLeads, Xvfb).
- Pour refaire les visuels : `python3 pubs.py DOSSIER` puis `node ../facebook/rendu.cjs DOSSIER`.
