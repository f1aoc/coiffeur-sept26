# Série d'e-mails « Essai BridgeToLeads → client »

Destinataires : les personnes qui ont fait l'essai gratuit (liste Brevo **« Essai BridgeToLeads »**, n° 2).
But : les transformer en acheteurs. Dès qu'ils achètent, le serveur de licences les ajoute à la liste
**« Clients BridgeToLeads »** et la série s'arrête pour eux.

Les mots entre `{{ … }}` sont remplacés par Brevo avec les informations de l'essai (métier et ville recherchés).
Copiez-les tels quels.

---

## 1. Construire l'automatisation dans Brevo

1. **Automatisations** → **Créer une automatisation** → **Créer à partir de zéro**.
2. **Point d'entrée** : « Un contact est ajouté à une liste » → **Essai BridgeToLeads**.
3. Ajoutez une étape **Condition** (« Si / sinon ») : attribut **LANGUE** *est égal à* `en`.
   - branche **Oui** → les 4 e-mails anglais ;
   - branche **Non** → les 4 e-mails français.
4. Dans chaque branche, enchaînez :
   **Attendre 1 jour** → **Condition** « le contact est dans la liste Clients BridgeToLeads ? »
   (Oui → **Fin**, Non → **Envoyer l'e-mail 1**) → **Attendre 2 jours** → même condition → **e-mail 2**
   → **Attendre 4 jours** → condition → **e-mail 3** → **Attendre 7 jours** → condition → **e-mail 4** → **Fin**.
   *(Si votre Brevo propose « Conditions de sortie » dans les paramètres de l'automatisation, choisissez
   « le contact est ajouté à la liste Clients BridgeToLeads » : vous n'avez alors plus besoin des conditions
   avant chaque e-mail.)*
5. Pour chaque e-mail : expéditeur **VORELIK – support@vorelik.com**, objet et texte ci-dessous, et gardez le
   lien de désinscription de Brevo en bas.
6. Envoyez-vous chaque e-mail en **test**, puis **Activer**.

Calendrier : e-mail 1 à J+1, e-mail 2 à J+3, e-mail 3 à J+7, e-mail 4 à J+14.

**Code promo de l'e-mail 4** (facultatif) : Stripe → **Product catalog** → **Coupons** → **Create coupon**
(20 %, *Once*), puis **Promotion codes** → code `ESSAI20`. Sur le lien de paiement BridgeToLeads :
**Edit** → cochez **Allow promotion codes**. Sans code, supprimez simplement le paragraphe de l'offre.

---

## 2. Les e-mails en français

### E-mail 1 — J+1

**Objet** : Vos 10 prospects : comment les appeler
**Aperçu** : 30 secondes suffisent pour décrocher un rendez-vous.

Bonjour,

Hier, BridgeToLeads vous a trouvé 10 {{ contact.METIER | default : "entreprises" }} sans site web à
{{ contact.VILLE | default : "votre ville" }}. Voici comment transformer cette liste en rendez-vous :

1. **Appelez plutôt qu'écrire** : ces entreprises n'ont pas de site, elles lisent rarement leurs e-mails.
2. **Commencez par les avis** : « J'ai vu que vous aviez 120 avis très positifs sur Google, mais aucun site
   pour vous trouver. »
3. **Proposez un exemple, pas un devis** : « Je peux vous montrer en 10 minutes à quoi ressemblerait le vôtre. »

Les entreprises en haut de la liste ont le plus d'avis : ce sont celles qui ont le plus de clients, donc le
plus à gagner avec un site.

Bonne prospection,
Patrick – VORELIK

---

### E-mail 2 — J+3

**Objet** : Et dans les villes d'à côté ?
**Aperçu** : l'essai s'arrête à 10 entreprises. Le logiciel, non.

Bonjour,

L'essai gratuit vous a montré 10 entreprises, pour un métier et une ville. Avec BridgeToLeads, vous faites
autant de recherches que vous voulez :

- **tous les métiers** (plombiers, restaurants, coiffeurs, artisans…) et **toutes les villes** ;
- toutes les entreprises trouvées, pas seulement les 10 premières ;
- la liste **exportée dans un fichier Excel**, prête à appeler ou à importer dans votre outil.

En une matinée, vous avez de quoi prospecter pendant un mois.

👉 [Découvrir BridgeToLeads](https://vorelik.com/bridgetoleads/?ref=sequence-2)

Patrick – VORELIK

---

### E-mail 3 — J+7

**Objet** : Un seul client rembourse le logiciel
**Aperçu** : paiement unique, pas d'abonnement.

Bonjour,

Un petit calcul : un site vitrine se vend en général plusieurs centaines d'euros. BridgeToLeads coûte
**59 €, en paiement unique** : pas d'abonnement, pas de frais cachés.

Autrement dit, **votre premier client rembourse le logiciel plusieurs fois**. Tous les suivants sont du bénéfice.

Et si vous proposez aussi la refonte de sites, le **pack VORELIK** (179 €) ajoute Chasseur de sites, qui trouve
les sites cassés ou dépassés, et Audit express, qui produit en quelques minutes un audit à montrer au client.

👉 [Acheter BridgeToLeads – 59 €](https://buy.stripe.com/cNi28seh5dqSbcT0GlcfK03)
👉 [Voir le pack complet – 179 €](https://vorelik.com/?ref=sequence-3)

Une question avant d'acheter ? Répondez simplement à cet e-mail.

Patrick – VORELIK

---

### E-mail 4 — J+14

**Objet** : Dernier message (et −20 % réservé aux testeurs)
**Aperçu** : ensuite, je ne vous relance plus.

Bonjour,

C'est mon dernier message à propos de BridgeToLeads.

Si vous cherchez des clients pour vos sites web, c'est le moment : avec le code **ESSAI20**, vous avez
**−20 % réservé aux personnes qui ont fait l'essai**, soit 47,20 € au lieu de 59 €.

👉 [Profiter de l'offre](https://buy.stripe.com/cNi28seh5dqSbcT0GlcfK03)
(saisissez `ESSAI20` dans « Ajouter un code promotionnel »)

Si ce n'est pas pour vous en ce moment, aucun souci : vous ne recevrez plus de relance. Et si quelque chose
vous a manqué pendant l'essai, dites-le-moi en répondant : chaque retour m'aide à améliorer le logiciel.

Merci d'avoir essayé,
Patrick – VORELIK

---

## 3. The emails in English (contacts with LANGUE = en)

### Email 1 — Day 1

**Subject**: Your 10 leads: how to call them
**Preview**: 30 seconds is all it takes to book a meeting.

Hi,

Yesterday, BridgeToLeads found you 10 {{ contact.METIER | default : "businesses" }} with no website in
{{ contact.VILLE | default : "your city" }}. Here's how to turn that list into meetings:

1. **Call, don't email**: businesses without a website rarely check their inbox.
2. **Start with their reviews**: "I saw you have 120 great reviews on Google, but no website for people to find you."
3. **Offer an example, not a quote**: "I can show you in 10 minutes what yours could look like."

The businesses at the top of the list have the most reviews: they have the most customers, and the most to
gain from a website.

Happy prospecting,
Patrick – VORELIK

---

### Email 2 — Day 3

**Subject**: What about the next town over?
**Preview**: the trial stops at 10 businesses. The software doesn't.

Hi,

The free trial showed you 10 businesses, for one trade in one city. With BridgeToLeads, you can run as many
searches as you like:

- **any trade** (plumbers, restaurants, hair salons, contractors…) in **any city**;
- every business found, not just the top 10;
- the list **exported to an Excel file**, ready to call or import into your CRM.

One morning gives you a month's worth of prospects.

👉 [Discover BridgeToLeads](https://vorelik.com/en/bridgetoleads/?ref=sequence-2)

Patrick – VORELIK

---

### Email 3 — Day 7

**Subject**: One client pays for the software
**Preview**: one-time payment, no subscription.

Hi,

Quick math: a small business website usually sells for several hundred dollars. BridgeToLeads costs
**$69, one-time**: no subscription, no hidden fees.

In other words, **your first client pays for the software several times over**. Every client after that is profit.

And if you also redesign websites, the **VORELIK bundle** ($199) adds Site Hunter, which finds broken or
outdated sites, and Audit Express, which builds a client-ready audit in minutes.

👉 [Buy BridgeToLeads – $69](https://buy.stripe.com/fZu3cw0qf4Um4Ovdt7cfK06)
👉 [See the full bundle – $199](https://vorelik.com/en/?ref=sequence-3)

Any question before buying? Just reply to this email.

Patrick – VORELIK

---

### Email 4 — Day 14

**Subject**: Last email (and 20% off for trial users)
**Preview**: after this, no more reminders.

Hi,

This is my last email about BridgeToLeads.

If you're looking for website clients, now's the time: with the code **ESSAI20**, you get
**20% off, reserved for trial users**: $55.20 instead of $69.

👉 [Claim the offer](https://buy.stripe.com/fZu3cw0qf4Um4Ovdt7cfK06)
(enter `ESSAI20` under "Add promotion code")

If it's not the right time, no problem: you won't hear from me about this again. And if something was missing
from the trial, just reply and let me know: every piece of feedback helps me improve the software.

Thanks for trying it,
Patrick – VORELIK
