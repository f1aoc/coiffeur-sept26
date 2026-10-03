# Serveur de licences (Stripe + Cloudflare)

Un seul petit serveur pour tous vos logiciels (BridgeToLeads, Chasseur de sites et les suivants). Il :

- donne au client sa **clé de licence** juste après le paiement (page « Merci ») ;
- **active** la clé sur 2 ordinateurs au maximum ;
- répond aux **vérifications** quotidiennes des logiciels en interrogeant Stripe en direct : paiement
  **remboursé en totalité ou contesté** → licence désactivée.

Pas de base de données : la clé et les ordinateurs activés sont rangés dans le paiement Stripe (« Metadata »).
Hébergement gratuit chez Cloudflare (100 000 requêtes par jour), rien à installer sur votre ordinateur.

Coût : uniquement les frais Stripe sur chaque vente. La TVA n'est pas gérée automatiquement : activez
**Stripe Tax** (option payante) ou voyez avec votre comptable.

> Les noms de menus et de boutons ci-dessous sont ceux du tableau de bord Stripe **en anglais**, écrits
> exactement comme à l'écran (en gras). Stripe modifie parfois l'emplacement d'un menu : si vous ne le trouvez
> pas, tapez son nom dans la barre de recherche en haut du tableau de bord.

---

## Étape 1 — Stripe : passer en mode test

Tout se prépare d'abord **sans argent réel**.

1. Connectez-vous sur [dashboard.stripe.com](https://dashboard.stripe.com).
2. En haut à droite, activez **Test mode** (ou, selon votre compte, ouvrez le menu du compte en haut à gauche →
   **Sandboxes** → votre sandbox). Un bandeau orange « Test mode » / « Sandbox » s'affiche : vous êtes en test.

## Étape 2 — Stripe : créer les deux produits

1. Menu de gauche : **Product catalog** → bouton **+ Add product**.
2. Remplissez :
   - **Name** : `Chasseur de sites`
   - **Description** (facultatif) : une phrase de présentation
   - Sous **Pricing** : choisissez **One-off** (paiement unique, pas d'abonnement), indiquez le **Amount**
     (votre prix) et la devise **EUR**.
3. Cliquez sur **Add product**.
4. Recommencez pour `BridgeToLeads`.
5. Ouvrez chaque produit (clic sur son nom dans **Product catalog**). En haut de la page, à droite du nom, se
   trouve son identifiant **`prod_…`** (bouton de copie à côté). **Notez les deux** : ils servent à l'étape 5.

## Étape 3 — Stripe : créer les deux liens de paiement

1. Menu de gauche : **Payment Links** (ou **Product catalog → …** selon l'affichage ; sinon tapez « Payment
   Links » dans la recherche) → bouton **+ New** (ou **Create payment link**).
2. **Select a product** : choisissez `Chasseur de sites`.
3. Onglet **After payment** (en haut du formulaire) :
   - choisissez **Don't show confirmation page** ;
   - puis **Redirect customers to your website** ;
   - dans le champ d'adresse, collez :

     ```
     https://VOTRE-SITE/chasseur-de-sites/merci.html?session_id={CHECKOUT_SESSION_ID}
     ```

     Remplacez `VOTRE-SITE` par l'adresse de votre site. Recopiez `{CHECKOUT_SESSION_ID}` **tel quel**, avec les
     accolades : Stripe le remplace automatiquement par le numéro du paiement, et c'est ce qui permet à la page
     « Merci » d'afficher la clé.
4. (Conseillé) Onglet **Payment page** / **Options** : cochez **Collect customers' addresses** si vous devez
   facturer avec adresse, et **Allow promotion codes** si vous voulez proposer des codes promo.
5. Cliquez sur **Create link** en haut à droite. Copiez le lien affiché (`https://buy.stripe.com/test_…`).
6. Recommencez pour `BridgeToLeads`, avec l'adresse :

   ```
   https://VOTRE-SITE/bridgetoleads/merci.html?session_id={CHECKOUT_SESSION_ID}
   ```

## Étape 4 — Stripe : créer la clé restreinte du serveur

C'est la clé que le serveur de licences utilisera pour lire les paiements. Elle n'a que les droits strictement
nécessaires.

1. Menu de gauche en bas : **Developers** → **API keys** (ou directement
   [dashboard.stripe.com/test/apikeys](https://dashboard.stripe.com/test/apikeys)).
2. Section **Restricted keys** → bouton **+ Create restricted key**.
   Si Stripe demande « How will you be using this API key? », choisissez **Building your own integration**.
3. **Key name** : `licences`.
4. Dans la liste des permissions, laissez tout sur **None**, sauf :

   | Ressource (dans la liste) | Permission à choisir |
   |---|---|
   | **Charges** (section *Core resources*) | **Read** |
   | **PaymentIntents** (section *Core resources*) | **Write** |
   | **Checkout Sessions** (section *Checkout*) | **Read** |

5. Bouton **Create key** en bas. Stripe affiche la clé une seule fois : cliquez dessus pour la copier
   (`rk_test_…`) et gardez-la pour l'étape 5.

Si un jour Stripe refuse un appel, son message d'erreur indique la permission manquante à ajouter.

## Étape 5 — Cloudflare : mettre le serveur en ligne

1. Créez un compte gratuit sur [dash.cloudflare.com/sign-up](https://dash.cloudflare.com/sign-up).
2. Menu de gauche : **Workers & Pages** → bouton **Create** → onglet **Workers** → **Create Worker**
   (ou **Start with Hello World!**).
3. **Worker name** : `licences` → bouton **Deploy**.
4. Bouton **Edit code**. Effacez tout le code affiché, puis collez celui de
   [`worker.js`](https://raw.githubusercontent.com/f1aoc/coiffeur-sept26/claude/kind-volta-486eo6/serveur-licences/worker.js)
   (ouvrez le lien, **Ctrl+A**, **Ctrl+C**, revenez dans l'éditeur, **Ctrl+V**). Bouton **Deploy** en haut à droite.
5. Revenez à la page du Worker → onglet **Settings** → section **Variables and Secrets** → bouton **+ Add**.
   Ajoutez ces 4 variables une par une (**Type**, **Variable name**, **Value**), puis **Deploy** :

   | Type | Variable name | Value |
   |---|---|---|
   | **Secret** | `STRIPE_SECRET_KEY` | la clé restreinte de l'étape 4 (`rk_test_…`) |
   | **Secret** | `LICENCE_SECRET` | une longue phrase aléatoire de 40 caractères ou plus. **Ne la changez plus jamais** : elle signe les clés déjà vendues. Gardez-en une copie en lieu sûr. |
   | **Text** | `PRODUITS` | voir ci-dessous |
   | **Text** | `ORIGINE_SITE` | l'adresse de votre site, par exemple `https://ptabountchikoff.fr` |

   Valeur de `PRODUITS`, en remplaçant les deux `prod_…` par **vos** identifiants de l'étape 2 :

   ```json
   {"prod_XXXXXXXX": {"code": "chasseur-de-sites", "prefixe": "CDS", "limite": 2}, "prod_YYYYYYYY": {"code": "bridgetoleads", "prefixe": "BTL", "limite": 2}}
   ```

6. L'adresse du serveur s'affiche sur la page du Worker (**Domains & Routes** ou en haut :
   `https://licences.VOTRE-NOM.workers.dev`). Ouvrez-la dans votre navigateur : la page doit afficher
   `{"service":"licences ptabountchikoff","ok":true}`.

## Étape 6 — Brancher les logiciels et les pages

**Envoyez-moi** :
- l'adresse du serveur (`https://licences.….workers.dev`) ;
- vos deux liens de paiement Stripe (`https://buy.stripe.com/…`).

Je les reporte dans les deux logiciels, leurs pages de vente et leurs pages « Merci », puis GitHub reconstruit
les logiciels. (Pour info, les emplacements sont : `SERVEUR` et `LIEN_ACHAT` dans `licence.py`,
`SERVEUR_LICENCES` dans chaque `merci.html`, et le bouton d'achat de chaque page de vente.)

## Étape 7 — Essai complet en mode test

1. Ouvrez votre lien de paiement test. Payez avec la carte **`4242 4242 4242 4242`**, une date d'expiration
   future (par exemple 12/34), n'importe quel code à 3 chiffres et n'importe quel nom.
2. Vous arrivez sur la page « Merci » : elle affiche la clé (`CDS-…` ou `BTL-…`).
   Dans Stripe : **Payments** → ouvrez ce paiement → section **Metadata** : la ligne `licence_cle` est là.
3. Lancez le logiciel, collez la clé → **Licence active**.
4. Dans Stripe : **Payments** → ouvrez le paiement → bouton **Refund** (ou **⋯ → Refund payment**) →
   laissez le montant total → **Refund**.
5. Dans le logiciel : **Licence → Vérifier maintenant** → « Licence inactive », analyses (ou recherches)
   bloquées.

### La clé ne s'affiche pas sur la page « Merci » ?

1. Ouvrez dans votre navigateur l'adresse de votre serveur suivie de **`/diagnostic`**, par exemple
   `https://licences.VOTRE-NOM.workers.dev/diagnostic`. Elle vérifie tout, sans rien afficher de secret :

   | Ligne | Ce qui doit s'afficher | Sinon |
   |---|---|---|
   | `STRIPE_SECRET_KEY` | `présente (mode test)` | ajoutez/corrigez le secret (étape 5) |
   | `LICENCE_SECRET` | `présente` | ajoutez le secret (étape 5) |
   | `PRODUITS` | vos deux `prod_…` | corrigez la valeur JSON (étape 5) |
   | `stripe` | `ok` sur les 3 lignes | `REFUSÉ` : ajoutez la permission nommée à la clé restreinte (étape 4) |
   | `derniers_paiements` → `reconnu` | `chasseur-de-sites` ou `bridgetoleads` | `NON` : le `prod_…` affiché n'est pas dans `PRODUITS` |
   | `derniers_paiements` → `redirection` | votre page merci.html suivie de `(session_id ok)` | corrigez **After payment** du lien (étape 3) |

   Après chaque modification dans Cloudflare, cliquez sur **Deploy**.
2. La page « Merci » affiche aussi, en petit, un **Détail technique** qui donne la cause. Par exemple
   `connexion_impossible — page https://…` : l'adresse affichée doit figurer dans `ORIGINE_SITE` (plusieurs
   adresses possibles, séparées par des virgules, par exemple `https://monsite.fr, https://www.monsite.fr`).
3. Une fois corrigé, rechargez simplement la page « Merci » du paiement : la clé apparaît (inutile de repayer).

## Étape 8 — Passer en réel

Les produits, liens et clés du mode test **n'existent pas** en mode réel.

1. Désactivez **Test mode** (ou quittez la sandbox).
2. Refaites les étapes **2, 3 et 4** en mode réel : vous obtenez de nouveaux `prod_…`, de nouveaux liens
   `https://buy.stripe.com/…` et une clé restreinte `rk_live_…`. Sur chaque lien, cochez aussi
   **Require customers to accept your terms of service** (case CGV sur la page de paiement).
3. Dans Cloudflare (**Settings → Variables and Secrets**), modifiez `STRIPE_SECRET_KEY` (clé `rk_live_…`) et
   `PRODUITS` (nouveaux `prod_…`), puis **Deploy**. **Gardez le même `LICENCE_SECRET`.**
4. Envoyez-moi les deux nouveaux liens de paiement réels : je mets à jour les pages de vente.

## Support client

- **Retrouver la clé d'un client** : Stripe → **Payments** → recherchez son adresse e-mail → ouvrez le
  paiement → **Metadata** → `licence_cle`.
- **Libérer un ordinateur** (client qui a changé de PC sans cliquer sur « Libérer ») : même endroit,
  **Metadata** → bouton **Edit** → supprimez la ligne `instances_chasseur-de-sites` ou `instances_bridgetoleads`
  (ou `instances` pour les toutes premières clés) → **Save**. Le client réactive ensuite la clé sur ses
  ordinateurs actuels.
- **Achat des deux logiciels en une fois** (produit ajouté au lien de paiement, vente croisée) : la page
  « Merci » affiche **une clé par logiciel**, chacune valable sur 2 ordinateurs. `licence_cle` contient alors
  les deux clés.
- **Ce qui désactive une licence** : un remboursement **total** (**Refund** du montant complet) ou une
  contestation (**Dispute**) du paiement. Un remboursement **partiel** (geste commercial) ne désactive pas la
  licence.
- **Rembourser un seul des deux logiciels d'un achat groupé** : faites le remboursement partiel, puis dans
  **Metadata** → **Edit** → **+ Add metadata** : clé `bloquer`, valeur `bridgetoleads` (ou `chasseur-de-sites`)
  → **Save**. Seule cette licence est désactivée (pour les deux : `chasseur-de-sites,bridgetoleads`).

## Pour les développeurs

```bash
node --test serveur-licences/worker.test.mjs   # tests du serveur (faux Stripe en mémoire)
node serveur-licences/serveur-local.mjs 8790   # serveur local + faux Stripe, pour essayer les logiciels
```

Le test `chasseur-de-sites/tests/test_licence_bout_en_bout.py` lance ce serveur local et fait le parcours
complet avec le vrai client Python : paiement → clé → activation → remboursement → blocage.
