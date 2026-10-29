# Essai gratuit BridgeToLeads (vorelik.com/essai/ et vorelik.com/en/trial/)

Le visiteur choisit un métier et une ville, et reçoit par e-mail les 10 commerces sans site web les plus établis.

- **La page** est `vitrine/essai/index.html`. Elle est publiée avec le site dès que l'adresse du Worker et la clé
  Turnstile y sont renseignées. D'ici là, la fabrication du site la retire, avec un avertissement.
- **Le serveur** est `worker.js`, un Cloudflare Worker séparé du serveur de licences. Il fait, dans l'ordre :
  1. le contrôle anti-robot (Turnstile) ;
  2. les limites : 1 essai par e-mail, 3 par adresse IP et par jour, et un plafond quotidien total ;
  3. la recherche Google Places ;
  4. l'envoi de l'e-mail par Brevo ;
  5. l'ajout du contact à la liste Brevo.
- **Les clés** (Google, Brevo, Turnstile) sont rangées dans Cloudflare, jamais dans la page.

Comptez environ 45 minutes la première fois. Les noms de menus peuvent légèrement changer : si vous ne trouvez pas
un menu, tapez son nom dans la barre de recherche du site concerné.

---

## Étape 1 — Google : la clé dédiée à l'essai

Une clé à part, utilisée seulement par le serveur de l'essai. Vous pourrez la couper sans toucher à vos logiciels.

1. Allez sur [console.cloud.google.com](https://console.cloud.google.com), avec le compte Google qui a déjà la
   facturation (celui de vos logiciels). En haut, choisissez le même projet que d'habitude.
2. Menu ☰ → **API et services** → **Identifiants**.
3. Cliquez sur **+ Créer des identifiants** → **Clé API**. La clé s'affiche : cliquez sur **Modifier la clé**
   (ou fermez, puis cliquez sur le nom de la nouvelle clé dans la liste).
4. Réglez la clé :
   - **Nom** : `Essai site vorelik`.
   - **Restrictions relatives aux applications** : **Aucune**. Le serveur Cloudflare n'a pas d'adresse IP fixe ;
     la protection se fait par la restriction d'API ci-dessous et par le plafond de l'étape 5.
   - **Restrictions relatives aux API** : **Restreindre la clé**, puis cochez uniquement **Places API (New)**.
   - Cliquez sur **Enregistrer**.
5. **Plafond de sécurité (conseillé).** Menu ☰ → **API et services** → **API et services activés** →
   **Places API (New)** → onglet **Quotas et limites du système**.
   - Si une ligne de recherche de texte **par jour** existe (« Text Search … per day »), cliquez sur ✏️, saisissez
     `300` et enregistrez.
   - Sinon, prenez la ligne **par minute** et mettez `30`.

   Le serveur de l'essai a aussi son propre plafond : 100 essais par jour au total, soit 300 recherches au maximum.
   - Un essai coûte jusqu'à 3 recherches, soit environ 0,10 $.
   - Google offre environ 1 000 recherches gratuites par mois sur ce type de recherche.
6. Vérifiez qu'une **alerte de budget** existe : menu ☰ → **Facturation** → **Budgets et alertes**. Si besoin,
   créez-en une, par exemple 10 € par mois.
7. Copiez la clé (bouton **Afficher la clé**, puis copier). **Ne l'envoyez à personne** : vous la collerez à l'étape 4.

## Étape 2 — Cloudflare Turnstile (anti-robot)

1. Sur [dash.cloudflare.com](https://dash.cloudflare.com), avec le même compte que le serveur de licences :
   menu de gauche → **Turnstile** → **Add widget**.
2. **Widget name** : `Essai vorelik`. **Hostnames** : ajoutez `vorelik.com` et `www.vorelik.com`.
   **Widget Mode** : **Managed**. Cliquez sur **Create**.
3. Deux clés s'affichent :
   - la **Site Key** est publique : **envoyez-la-moi**, elle va dans la page ;
   - la **Secret Key** est secrète : gardez-la pour l'étape 4.

## Étape 3 — Brevo (envoi des e-mails et liste de contacts)

1. Créez un compte gratuit sur [brevo.com](https://www.brevo.com). Le gratuit permet 300 e-mails par jour.
2. **Authentifier le domaine** (indispensable pour ne pas arriver en indésirables) :
   1. dans Brevo, ouvrez le menu du compte en haut à droite → **Expéditeurs, domaines et IP dédiées** → onglet
      **Domaines** → **Ajouter un domaine** → `vorelik.com`. Brevo affiche des enregistrements DNS (TXT pour le code
      Brevo, DKIM et DMARC) ;
   2. dans le cPanel o2switch → **Zone Editor** (ou **Éditeur de zone**) → `vorelik.com`, ajoutez ces enregistrements
      un par un, en recopiant exactement le **nom** et la **valeur** donnés par Brevo ;
   3. revenez dans Brevo et cliquez sur **Authentifier ce domaine**. Si ça ne passe pas tout de suite, réessayez
      1 heure plus tard : le temps que les DNS se propagent.
3. **Expéditeur** : onglet **Expéditeurs** → **Ajouter un expéditeur**. **Nom** : `VORELIK`, **e-mail** :
   `essai@vorelik.com`. Avec le domaine authentifié, l'adresse n'a pas besoin d'exister vraiment. Si vous voulez
   recevoir les réponses, créez-la quand même dans o2switch.
4. **Listes** : menu **Contacts** → **Listes** → **Créer une liste** :
   - `Essai BridgeToLeads`. Une fois créée, notez son **numéro (ID)**, affiché dans la liste ;
   - `Actualités VORELIK` : les personnes qui ont coché la case. Notez aussi son numéro.
5. **Attributs** : menu **Contacts** → **Paramètres** (⚙) → **Attributs de contact** → **Ajouter un nouvel
   attribut**, cinq fois :

   | Nom de l'attribut | Type |
   |---|---|
   | `METIER` | Texte |
   | `VILLE` | Texte |
   | `REF` | Texte |
   | `LANGUE` | Texte (`fr` ou `en` : la langue de la page d'essai) |
   | `ACTUS_VORELIK` | Booléen (oui / non) |

6. **Clé API** : menu du compte → **SMTP et API** → onglet **Clés API** → **Générer une nouvelle clé API**.
   Nom : `essai vorelik`. Copiez la clé (`xkeysib-…`). Elle ne s'affiche qu'une fois.

> **Important (RGPD).** Pour vos newsletters, envoyez uniquement à la liste **Actualités VORELIK**. La liste
> **Essai BridgeToLeads** contient aussi des personnes qui n'ont pas accepté vos actualités.

## Étape 4 — Cloudflare : mettre le serveur de l'essai en ligne

1. **Mémoire des limites** : menu de gauche → **Storage & Databases** → **KV** → **Create** (ou **Create a
   namespace**) → nom : `essai-bridgetoleads` → **Add** / **Create**.
2. **Le Worker** :
   1. menu de gauche → **Workers & Pages** → **Create** → **Create Worker** (ou **Start with Hello World!**).
      **Worker name** : `essai-bridgetoleads` → **Deploy** ;
   2. bouton **Edit code** : effacez tout, puis collez le contenu de
      [`worker.js`](https://raw.githubusercontent.com/f1aoc/coiffeur-sept26/claude/kind-volta-486eo6/essai-bridgetoleads/worker.js)
      (ouvrez le lien, **Ctrl+A**, **Ctrl+C**, revenez dans l'éditeur, **Ctrl+V**) ;
   3. cliquez sur **Deploy** en haut à droite.
3. **Lier la mémoire** : page du Worker → onglet **Settings** → **Bindings** → **+ Add** → **KV namespace**.
   - **Variable name** : `ESSAIS` (en majuscules) ;
   - **KV namespace** : `essai-bridgetoleads` ;
   - **Deploy**.
4. **Variables** : onglet **Settings** → **Variables and Secrets** → **+ Add**, une par une, puis **Deploy** :

   | Type | Variable name | Value |
   |---|---|---|
   | **Secret** | `GOOGLE_MAPS_API_KEY` | la clé Google de l'étape 1 |
   | **Secret** | `TURNSTILE_SECRET` | la **Secret Key** de l'étape 2 |
   | **Secret** | `BREVO_API_KEY` | la clé `xkeysib-…` de l'étape 3 |
   | **Secret** | `DESINSCRIPTION_SECRET` | une longue phrase aléatoire de 40 caractères ou plus (ne la changez plus ensuite) |
   | **Text** | `EXPEDITEUR` | `VORELIK <support@vorelik.com>` |
   | **Text** | `BREVO_LISTE_ESSAI` | le numéro de la liste « Essai BridgeToLeads » |
   | **Text** | `BREVO_LISTE_ACTUS` | le numéro de la liste « Actualités VORELIK » |
   | **Text** | `ORIGINE_SITE` | `https://vorelik.com,https://www.vorelik.com` |
   | **Text** | `PLAFOND_JOUR` | `100` (nombre maximal d'essais par jour, tous visiteurs confondus) |

5. **Vérification** : l'adresse du Worker s'affiche sur sa page (`https://essai-bridgetoleads.VOTRE-NOM.workers.dev`).
   Ouvrez-la en ajoutant `/diagnostic` à la fin. Vous devez voir `"ok": true` et :
   - les listes Brevo, avec leur nom ;
   - `"attributs": "ok"` ;
   - `"expediteur": "validé"`.

   Sinon, la ligne concernée dit quoi corriger.

## Étape 5 — Brancher la page et tester

1. **Envoyez-moi** l'adresse du Worker (étape 4.5) et la **Site Key** Turnstile (étape 2). Je les mets dans la page :
   le site complet la publie alors sous `vorelik.com/essai/`.
2. **Testez** avec votre propre e-mail, par exemple « coiffeur » à « Cavaillon ». Vérifiez :
   - l'e-mail reçu (et s'il est arrivé en indésirables) ;
   - le contact dans Brevo, avec le métier, la ville et la ref ;
   - le lien « Se désinscrire ».
3. **Liens de campagne** : ajoutez `?ref=…` à l'adresse, par exemple `https://vorelik.com/essai/?ref=facebook-novembre`.
   La ref est enregistrée avec le contact dans Brevo : vous saurez quelle campagne apporte le plus d'essais.

## Version anglaise (vorelik.com/en/trial/)

Même serveur, mêmes clés, mêmes listes et mêmes limites (1 essai par e-mail, 3 par adresse IP et par jour, plafond
quotidien commun aux deux langues). La page anglaise envoie `langue=en` :

- la recherche Google se fait en anglais, sans région : c'est la ville tapée qui décide (« Austin TX », « Leeds UK ») ;
- l'e-mail, les messages et la page de désinscription sont en anglais, avec un lien vers la page de vente anglaise ;
- le contact est enregistré dans Brevo avec `LANGUE` = `en`. Pour des actualités en anglais, filtrez la liste
  « Actualités VORELIK » sur cet attribut.

## Bon à savoir

- **Un essai sans résultat** (aucun commerce sans site) n'envoie pas d'e-mail et ne consomme pas l'adresse e-mail.
  Le visiteur peut réessayer une autre ville. L'essai compte quand même dans les 3 par IP et par jour.
- **Pour désactiver l'essai** rapidement : dans Cloudflare, mettez `PLAFOND_JOUR` à `1`, ou supprimez la clé Google
  « Essai site vorelik ». Vos logiciels n'en dépendent pas.
- **Désinscription** : le lien de l'e-mail ouvre une page avec un bouton de confirmation. Les messageries qui
  « visitent » les liens ne désinscrivent donc personne par erreur. L'adresse est ensuite bloquée dans Brevo.
- **Tests automatiques** (pour les développeurs) : `node --test essai-bridgetoleads/worker.test.mjs`. Google, Brevo
  et Turnstile y sont simulés.
