# Serveur de licences (Stripe + Cloudflare)

Un seul petit serveur pour tous vos logiciels (BridgeToLeads, Chasseur de sites et les suivants). Il :

- donne au client sa **clé de licence** juste après le paiement (page « Merci ») ;
- **active** la clé sur 2 ordinateurs au maximum ;
- répond aux **vérifications** quotidiennes des logiciels en interrogeant Stripe en direct : paiement
  **remboursé ou contesté** → licence désactivée.

Pas de base de données : la clé et les ordinateurs activés sont rangés dans le paiement Stripe (« métadonnées »).
Hébergement gratuit chez Cloudflare (100 000 requêtes par jour), rien à installer sur votre ordinateur.

Coût : uniquement les frais Stripe sur chaque vente. La TVA n'est pas gérée automatiquement : activez
*Stripe Tax* (option payante) ou voyez avec votre comptable.

---

## 1. Stripe : produits et liens de paiement

Commencez en **mode test** (interrupteur « Mode test » en haut du tableau de bord Stripe).

1. **Catalogue de produits → Ajouter un produit** :
   - « Chasseur de sites », paiement **unique**, votre prix ;
   - « BridgeToLeads », paiement **unique**, votre prix.

   Ouvrez chaque produit et notez son identifiant, qui commence par `prod_…` (en haut de la page).
2. **Liens de paiement → Nouveau** pour chaque produit. Dans l'onglet **Après le paiement**, choisissez
   « Ne pas afficher de page de confirmation » → **Rediriger les clients vers votre site** :

   ```
   https://VOTRE-SITE/chasseur-de-sites/merci.html?session_id={CHECKOUT_SESSION_ID}
   https://VOTRE-SITE/bridgetoleads/merci.html?session_id={CHECKOUT_SESSION_ID}
   ```

   Recopiez `{CHECKOUT_SESSION_ID}` tel quel : Stripe le remplace par le numéro du paiement.
3. **Développeurs → Clés API → Créer une clé restreinte**, nommée « licences », avec ces permissions
   (tout le reste sur « Aucun ») :

   | Ressource | Permission |
   |---|---|
   | Checkout Sessions | Lecture |
   | PaymentIntents | Écriture |
   | Charges | Lecture |

   Copiez la clé (`rk_test_…`). Si un jour Stripe refuse un appel, son message d'erreur indique la permission
   à ajouter.

## 2. Cloudflare : mettre le serveur en ligne

1. Créez un compte gratuit sur [cloudflare.com](https://dash.cloudflare.com/sign-up).
2. **Workers & Pages → Créer → Créer un Worker**, nommez-le `licences`, puis **Déployer**.
3. **Modifier le code** : effacez tout, collez le contenu de [`worker.js`](worker.js), puis **Déployer**.
4. **Paramètres → Variables et secrets** du Worker, ajoutez :

   | Nom | Type | Valeur |
   |---|---|---|
   | `STRIPE_SECRET_KEY` | Secret | la clé restreinte Stripe (`rk_test_…`) |
   | `LICENCE_SECRET` | Secret | une longue phrase aléatoire (40 caractères ou plus) — **ne la changez plus jamais** : elle signe les clés déjà vendues |
   | `PRODUITS` | Texte | voir ci-dessous |
   | `ORIGINE_SITE` | Texte | l'adresse de votre site, par exemple `https://ptabountchikoff.fr` |

   `PRODUITS`, avec **vos** identifiants `prod_…` :

   ```json
   {"prod_XXXXXXXX": {"code": "chasseur-de-sites", "prefixe": "CDS", "limite": 2},
    "prod_YYYYYYYY": {"code": "bridgetoleads", "prefixe": "BTL", "limite": 2}}
   ```

5. L'adresse du serveur s'affiche en haut : `https://licences.VOTRE-NOM.workers.dev`. Ouvrez-la : la page doit
   afficher `{"service":"licences ptabountchikoff","ok":true}`.

## 3. Brancher les logiciels et les pages

L'adresse du serveur doit être reportée à 4 endroits. Le plus simple : **envoyez-la-moi** avec vos deux liens de
paiement Stripe, et je le fais.

- `chasseur-de-sites/chasseur/licence.py` : `SERVEUR` (et `LIEN_ACHAT` = lien de paiement) ;
- `chasseur-de-sites/site/merci.html` : `SERVEUR_LICENCES` ;
- et la même chose dans BridgeToLeads (`tools/prospection/licence.py` et `tools/prospection/site/merci.html`).

## 4. Essai complet en mode test

1. Ouvrez votre lien de paiement test et payez avec la carte `4242 4242 4242 4242`, une date future, n'importe
   quel code.
2. La page « Merci » affiche la clé (`CDS-…`). Dans le tableau de bord Stripe, le paiement porte maintenant la
   métadonnée `licence_cle`.
3. Lancez le logiciel, collez la clé → **Licence active**.
4. Dans Stripe : **Paiements → ce paiement → Rembourser** (montant total).
5. Dans le logiciel : **Licence → Vérifier maintenant** → « Licence inactive », analyses bloquées.

## 5. Passer en réel

Les produits, liens et clés du mode test **n'existent pas** en mode réel. Désactivez le mode test, puis refaites
l'étape 1 (produits, liens de paiement, clé restreinte `rk_live_…`) et mettez à jour `STRIPE_SECRET_KEY` et
`PRODUITS` dans Cloudflare. Gardez le même `LICENCE_SECRET`.

## Support client

- **Retrouver la clé d'un client** : Stripe → Paiements → recherchez son e-mail → ouvrez le paiement →
  Métadonnées → `licence_cle`.
- **Libérer un ordinateur** (client qui a changé de PC sans « Libérer ») : même endroit, métadonnée `instances`
  → effacez-la (le client réactive ensuite sur ses ordinateurs actuels).
- **Ce qui désactive une licence** : un remboursement total ou une contestation (chargeback) du paiement.
- Un **remboursement partiel** ne désactive pas la licence (geste commercial possible) ; seul un remboursement
  total le fait.

## Pour les développeurs

```bash
node --test serveur-licences/worker.test.mjs   # tests du serveur (faux Stripe en mémoire)
node serveur-licences/serveur-local.mjs 8790   # serveur local + faux Stripe, pour essayer les logiciels
```

Le test `chasseur-de-sites/tests/test_licence_bout_en_bout.py` lance ce serveur local et fait le parcours
complet avec le vrai client Python : paiement → clé → activation → remboursement → blocage.
