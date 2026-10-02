# Vitrine ptabountchikoff

Page d'accueil qui présente tous les logiciels (BridgeToLeads, Chasseur de sites et les prochains) et renvoie vers
la page de vente de chacun.

## Mettre en ligne (le plus simple)

GitHub assemble automatiquement le site complet : téléchargez **ptabountchikoff-site-complet.zip** dans la release
[chasseurdesites-latest](https://github.com/f1aoc/coiffeur-sept26/releases/tag/chasseurdesites-latest),
décompressez-le et envoyez tout le dossier sur votre hébergeur (Netlify, Vercel, GitHub Pages, FTP…).

```
index.html              ← la vitrine
assets/
bridgetoleads/          ← page de vente BridgeToLeads (index.html + merci.html)
chasseur-de-sites/      ← page de vente Chasseur de sites (index.html + merci.html)
```

Avant de publier, cherchez `À MODIFIER` dans les fichiers : prix, liens d'achat (liens de paiement Lemon Squeezy) et adresse e-mail.

## Ajouter un nouveau logiciel

1. Mettez son icône et une capture dans `assets/`.
2. Dans `index.html`, section « Le catalogue », copiez un bloc `<article class="product …">` et changez le nom,
   les textes, le prix et le lien (par exemple `mon-logiciel/`). Un commentaire explique comment lui donner ses
   couleurs.
3. Facultatif : ajoutez un bloc « zoom » (`<div class="spotlight …">`) et un lien dans le pied de page.
4. Tant qu'il n'est pas prêt, la carte « Le prochain arrive » et la section « À venir » annoncent la suite.
