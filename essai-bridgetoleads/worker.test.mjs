// Tests de l'essai gratuit : node --test essai-bridgetoleads/worker.test.mjs
// Google Places, Brevo et Turnstile sont simulés ; la mémoire KV est un simple dictionnaire.
import assert from "node:assert/strict";
import { beforeEach, test } from "node:test";

import worker, { contenuEmail, domainePrincipal, pageNonSite, reglages, selectionner } from "./worker.js";

reglages.pauseMs = 0;
const SITE = "https://vorelik.com";

class FausseKV {
  constructor() { this.donnees = new Map(); }
  async get(cle) { return this.donnees.has(cle) ? this.donnees.get(cle) : null; }
  async put(cle, valeur) { this.donnees.set(cle, String(valeur)); }
  async delete(cle) { this.donnees.delete(cle); }
}

function fiche(i, { site, avis = 10 * i, statut = "OPERATIONAL", nom = `Salon ${i}` } = {}) {
  return {
    id: `p${i}`, displayName: { text: nom }, formattedAddress: `${i} rue de la Paix, 84800 L'Isle-sur-la-Sorgue`,
    nationalPhoneNumber: `04 90 00 00 ${String(i).padStart(2, "0")}`, rating: 4.5, userRatingCount: avis,
    websiteUri: site, googleMapsUri: `https://maps.google.com/?cid=${i}`, businessStatus: statut,
  };
}

let env, appels, pagesGoogle, turnstileOk, brevoEchec, googleEchec;
beforeEach(() => {
  env = {
    GOOGLE_MAPS_API_KEY: "AIzaTest", BREVO_API_KEY: "xkeysib-test", TURNSTILE_SECRET: "secret-turnstile",
    DESINSCRIPTION_SECRET: "phrase-secrete-de-test-tres-longue", EXPEDITEUR: "VORELIK <essai@vorelik.com>",
    BREVO_LISTE_ESSAI: "7", BREVO_LISTE_ACTUS: "8", ORIGINE_SITE: "https://vorelik.com,https://www.vorelik.com",
    ESSAIS: new FausseKV(),
  };
  appels = [];
  turnstileOk = true;
  brevoEchec = false;
  googleEchec = false;
  // 2 pages : 20 fiches puis 5 ; sites réels, Facebook, aucun site, fermées
  pagesGoogle = [
    Array.from({ length: 20 }, (_, i) => fiche(i + 1, {
      site: i % 4 === 0 ? undefined : i % 4 === 1 ? "https://www.facebook.com/salon" : `https://salon${i}.fr`,
    })),
    [fiche(30, { avis: 999 }), fiche(31, { avis: 2000, statut: "CLOSED_PERMANENTLY" }),
      fiche(32, { site: "https://m.facebook.com/x", avis: 500 }), fiche(1, {}), fiche(33, { site: "https://instagram.com/x", avis: 3000 })],
  ];
  globalThis.fetch = async (url, init = {}) => {
    const u = String(url);
    const corps = init.body instanceof URLSearchParams ? Object.fromEntries(init.body) : init.body ? JSON.parse(init.body) : null;
    appels.push({ url: u, methode: init.method || "GET", corps, entetes: init.headers || {} });
    if (u.startsWith("https://challenges.cloudflare.com/")) return Response.json({ success: turnstileOk });
    if (u.startsWith("https://cloudflare-dns.com/")) {
      const q = new URL(u).searchParams;
      const nom = q.get("name");
      if (nom.startsWith("inexistant")) return Response.json({ Status: 3 });
      if (nom.startsWith("sans-mx")) return Response.json({ Status: 0, Answer: [] });
      if (nom.startsWith("panne")) return new Response("", { status: 503 });
      return Response.json({ Status: 0, Answer: q.get("type") === "MX" ? [{ type: 15, data: `10 mx.${nom}.` }] : [{ type: 1, data: "1.2.3.4" }] });
    }
    if (u.startsWith("https://places.googleapis.com/")) {
      if (googleEchec) return Response.json({ error: { status: "PERMISSION_DENIED", message: "API key not valid" } }, { status: 403 });
      const page = corps.pageToken ? Number(corps.pageToken) : 0;
      const places = pagesGoogle[page] || [];
      return Response.json({ places, ...(page + 1 < pagesGoogle.length ? { nextPageToken: String(page + 1) } : {}) });
    }
    if (u.startsWith("https://api.brevo.com/")) {
      if (brevoEchec && u.endsWith("/smtp/email")) return new Response('{"message":"sender not valid"}', { status: 400 });
      return Response.json({ messageId: "x" }, { status: 201 });
    }
    throw new Error(`appel inattendu ${u}`);
  };
});

/** Étape 1 seulement : le formulaire (contrôles, e-mail de confirmation). */
async function demander(champs = {}, { ip = "1.2.3.4", origine = SITE } = {}) {
  const donnees = { metier: "coiffeur", ville: "L'Isle-sur-la-Sorgue", email: "Jean@Exemple.fr", "cf-turnstile-response": "jeton", ...champs };
  const r = await worker.fetch(new Request("https://essai.test/essai", {
    method: "POST",
    headers: { "Content-Type": "application/json", "CF-Connecting-IP": ip, ...(origine ? { Origin: origine } : {}) },
    body: JSON.stringify(donnees),
  }), env);
  return { status: r.status, corps: await r.json(), entetes: r.headers };
}

const vers = (debut) => appels.filter((a) => a.url.startsWith(debut));
const avecEtiquette = (tag) => vers("https://api.brevo.com/v3/smtp/email").filter((a) => (a.corps.tags || []).includes(tag));
const confirmations = () => avecEtiquette("essai-confirmation");
const resultats = () => avecEtiquette("essai-bridgetoleads");
const lienDeConfirmation = () => new URL(confirmations().at(-1).corps.textContent.match(/https:\/\/essai\.test\/confirmer\S+/)[0]);

/** Étape 2 : clic sur le bouton de la page de confirmation (réponse JSON pour les tests). */
async function confirmer(lien = lienDeConfirmation(), methode = "POST", json = true) {
  const r = await worker.fetch(new Request(lien, { method: methode, headers: json ? { Accept: "application/json" } : {} }), env);
  return { status: r.status, corps: json ? await r.json() : await r.text() };
}

/** Essai complet : formulaire, puis confirmation si l'e-mail de confirmation est parti. */
async function envoyer(champs = {}, options = {}) {
  const etape1 = await demander(champs, options);
  if (!etape1.corps.confirmation) return etape1;
  return confirmer();
}

test("essai réussi : Google paginé, fiches sans site ou Facebook, triées par avis, e-mail et contact Brevo", async () => {
  const etape1 = await demander({ ref: "facebook-octobre", actus: true });
  assert.equal(etape1.status, 200);
  assert.equal(etape1.corps.confirmation, true);
  assert.match(etape1.corps.message, /Plus qu'une étape/);
  assert.equal(etape1.entetes.get("Access-Control-Allow-Origin"), SITE);
  // Avant le clic : ni Google, ni résultats, ni contact Brevo
  assert.equal(vers("https://places.googleapis.com/").length, 0);
  assert.equal(resultats().length, 0);
  assert.equal(vers("https://api.brevo.com/v3/contacts").length, 0);
  const { status, corps } = await confirmer();
  assert.equal(status, 200);
  assert.equal(corps.ok, true);
  assert.equal(corps.trouves, 10);
  assert.match(corps.message, /10 commerces sans site/);

  const google = vers("https://places.googleapis.com/");
  assert.equal(google.length, 2);
  assert.equal(google[0].corps.textQuery, "coiffeur L'Isle-sur-la-Sorgue");
  assert.equal(google[0].corps.languageCode, "fr");
  assert.equal(google[0].entetes["X-Goog-Api-Key"], "AIzaTest");
  assert.match(google[0].entetes["X-Goog-FieldMask"], /places\.websiteUri/);
  assert.equal(google[1].corps.pageToken, "1");

  const [mail] = resultats();
  assert.deepEqual(mail.corps.to, [{ email: "jean@exemple.fr" }]);
  assert.deepEqual(mail.corps.sender, { name: "VORELIK", email: "essai@vorelik.com" });
  assert.equal(mail.entetes["api-key"], "xkeysib-test");
  const html = mail.corps.htmlContent;
  assert.match(html, /Données Google Maps/);
  assert.match(html, /https:\/\/vorelik\.com\/bridgetoleads\//);
  assert.match(html, /Se désinscrire/);
  assert.match(mail.corps.headers["List-Unsubscribe"], /^<https:\/\/essai\.test\/desinscription\?e=jean%40exemple\.fr&s=[0-9a-f]{32}>$/);
  // Ordre : plus d'avis d'abord ; Instagram seulement = prospect ; fermée et sites réels exclus
  const noms = [...html.matchAll(/<div style="font-weight:700;color:#1E1B4B">([^<]+)</g)].map((m) => m[1]);
  assert.deepEqual(noms.slice(0, 4), ["Salon 33", "Salon 30", "Salon 32", "Salon 18"]);
  assert.ok(!noms.includes("Salon 31") && !noms.includes("Salon 3"));
  assert.match(html, /Instagram seulement/);
  assert.equal(noms.length, 10);
  assert.match(html, /Facebook seulement/);

  const [contact] = vers("https://api.brevo.com/v3/contacts");
  assert.deepEqual(contact.corps.listIds, [7, 8]);
  assert.deepEqual(contact.corps.attributes, { METIER: "coiffeur", VILLE: "L'Isle-sur-la-Sorgue", REF: "facebook-octobre", LANGUE: "fr", ACTUS_VORELIK: true });
  assert.equal(contact.corps.updateEnabled, true);
});

test("sans la case actualités : liste Essai seulement", async () => {
  await envoyer({ actus: false });
  const [contact] = vers("https://api.brevo.com/v3/contacts");
  assert.deepEqual(contact.corps.listIds, [7]);
  assert.equal(contact.corps.attributes.ACTUS_VORELIK, false);
});

test("1 essai par e-mail (majuscules comprises), sans nouvel appel Google", async () => {
  assert.equal((await envoyer()).status, 200);
  appels = [];
  const r = await envoyer({ email: "jean@exemple.FR" }, { ip: "9.9.9.9" });
  assert.equal(r.status, 429);
  assert.equal(r.corps.erreur, "email_utilise");
  assert.equal(vers("https://places.googleapis.com/").length, 0);
});

test("3 essais par adresse IP et par jour", async () => {
  for (let i = 0; i < 3; i++) assert.equal((await envoyer({ email: `a${i}@exemple.fr` })).status, 200);
  const r = await envoyer({ email: "a4@exemple.fr" });
  assert.equal(r.status, 429);
  assert.equal(r.corps.erreur, "limite_ip");
  assert.equal((await envoyer({ email: "a5@exemple.fr" }, { ip: "5.6.7.8" })).status, 200);
});

test("plafond quotidien total", async () => {
  env.PLAFOND_JOUR = "2";
  assert.equal((await envoyer({ email: "a@exemple.fr" }, { ip: "1.1.1.1" })).status, 200);
  assert.equal((await envoyer({ email: "b@exemple.fr" }, { ip: "2.2.2.2" })).status, 200);
  const r = await envoyer({ email: "c@exemple.fr" }, { ip: "3.3.3.3" });
  assert.equal(r.corps.erreur, "plafond");
});

test("Turnstile refusé : rien n'est appelé", async () => {
  turnstileOk = false;
  const r = await envoyer();
  assert.equal(r.status, 403);
  assert.equal(r.corps.erreur, "turnstile");
  assert.equal(vers("https://places.googleapis.com/").length, 0);
  assert.equal(vers("https://api.brevo.com/").length, 0);
});

test("jeton Turnstile absent : refusé sans appeler Cloudflare", async () => {
  const r = await envoyer({ "cf-turnstile-response": "" });
  assert.equal(r.corps.erreur, "turnstile");
  assert.equal(appels.length, 0);
});

test("aucun commerce sans site : pas d'e-mail, l'adresse reste utilisable, l'IP est comptée", async () => {
  pagesGoogle = [[fiche(1, { site: "https://vrai-site.fr" })]];
  const r = await envoyer();
  assert.equal(r.status, 200);
  assert.equal(r.corps.trouves, 0);
  assert.match(r.corps.message, /pas été décompté/);
  assert.equal(resultats().length, 0);
  assert.equal(vers("https://api.brevo.com/v3/contacts").length, 0);
  pagesGoogle = [[fiche(2)]];
  assert.equal((await envoyer()).corps.trouves, 1);
  assert.equal([...env.ESSAIS.donnees.entries()].find(([k]) => k.startsWith("ip:"))[1], "2");
});

test("champs invalides", async () => {
  assert.equal((await envoyer({ email: "pas-une-adresse" })).corps.erreur, "email");
  assert.equal((await envoyer({ metier: " " })).corps.erreur, "metier");
  assert.equal((await envoyer({ ville: "" })).corps.erreur, "ville");
  assert.equal(appels.length, 0);
});

test("formulaire envoyé depuis un autre site : refusé", async () => {
  const r = await envoyer({}, { origine: "https://pirate.example" });
  assert.equal(r.status, 403);
  assert.equal(appels.length, 0);
});

test("configuration incomplète : message d'indisponibilité, aucun appel", async () => {
  delete env.BREVO_API_KEY;
  const r = await envoyer();
  assert.equal(r.status, 503);
  assert.equal(appels.length, 0);
});

test("erreur Google : message clair, rien n'est compté, le même lien permet de réessayer", async () => {
  googleEchec = true;
  await demander();
  const lien = lienDeConfirmation();
  const r = await confirmer(lien);
  assert.equal(r.status, 502);
  assert.equal(r.corps.erreur, "google");
  assert.ok(![...env.ESSAIS.donnees.keys()].some((k) => k.startsWith("ip:") || k.startsWith("email:") || k.startsWith("jour:")));
  googleEchec = false;
  assert.equal((await confirmer(lien)).corps.trouves, 10);
});

test("e-mail refusé par Brevo : l'adresse n'est pas consommée", async () => {
  brevoEchec = true;
  const r = await envoyer();
  assert.equal(r.status, 502);
  assert.equal(r.corps.erreur, "envoi");
  assert.ok(![...env.ESSAIS.donnees.keys()].some((k) => k.startsWith("email:") || k.startsWith("attente:") || k.startsWith("renvoi:")));
});

test("formulaire HTML classique (multipart) accepté", async () => {
  const f = new FormData();
  for (const [k, v] of Object.entries({ metier: "plombier", ville: "Avignon", email: "x@exemple.fr", actus: "on", "cf-turnstile-response": "j" })) f.append(k, v);
  const r = await worker.fetch(new Request("https://essai.test/essai", { method: "POST", headers: { Origin: SITE }, body: f }), env);
  assert.equal(r.status, 200);
  assert.equal((await confirmer()).corps.trouves, 10);
  assert.deepEqual(vers("https://api.brevo.com/v3/contacts")[0].corps.listIds, [7, 8]);
});

test("e-mail : contenu échappé (pas d'injection HTML)", () => {
  const { html, sujet, texte } = contenuEmail({
    metier: "coiffeur", ville: "Paris", analyses: 1, lien: "https://essai.test/desinscription?e=a&s=b",
    prospects: [{ nom: '<script>alert(1)</script> & "Co"', adresse: "1 rue <b>", telephone: "01 02", note: 4.2, avis: 3, site: "aucun", maps: "https://maps.google.com/?q=\"x\"" }],
  });
  assert.ok(!html.includes("<script>alert"));
  assert.match(html, /&lt;script&gt;alert\(1\)&lt;\/script&gt; &amp; &quot;Co&quot;/);
  assert.match(html, /4,2&nbsp;★/);
  assert.match(html, /3&nbsp;avis/);
  assert.equal(sujet, "1 prospect sans site web : coiffeur à Paris");
  assert.match(texte, /Données Google Maps/);
});

test("pages qui ne sont pas un vrai site (réseaux, annuaires, réservation)", () => {
  assert.equal(pageNonSite("https://www.facebook.com/salon"), "Facebook");
  assert.equal(pageNonSite("http://m.facebook.com/x"), "Facebook");
  assert.equal(pageNonSite("https://fb.me/x"), "Facebook");
  assert.equal(pageNonSite("https://instagram.com/x"), "Instagram");
  assert.equal(pageNonSite("https://www.yelp.com/biz/joes"), "Yelp");
  assert.equal(pageNonSite("https://joes-barber.square.site/"), "Square");
  assert.equal(pageNonSite("https://www.planity.com/salon-lea"), "Planity");
  assert.equal(pageNonSite("https://monsalon.business.site/"), "Google Business");
  assert.equal(pageNonSite("https://facebook.com.pirate.fr/"), null);
  assert.equal(pageNonSite("https://salon-lea.fr/"), null);
  assert.equal(selectionner([fiche(1), fiche(1)]).length, 1);
});

async function desinscription(methode, query) {
  const r = await worker.fetch(new Request(`https://essai.test/desinscription${query}`, { method: methode }), env);
  return { status: r.status, texte: await r.text() };
}

test("désinscription : signature contrôlée, confirmation par bouton, adresse bloquée dans Brevo", async () => {
  await envoyer();
  const lien = new URL(resultats()[0].corps.headers["List-Unsubscribe"].slice(1, -1));
  appels = [];
  assert.equal((await desinscription("GET", "?e=jean%40exemple.fr&s=faux")).status, 400);
  const page = await desinscription("GET", lien.search);
  assert.equal(page.status, 200);
  assert.match(page.texte, /Confirmer la désinscription/);
  assert.equal(appels.length, 0); // un simple affichage (ou un robot de messagerie) ne désinscrit pas
  const fait = await desinscription("POST", lien.search);
  assert.equal(fait.status, 200);
  assert.match(fait.texte, /désinscrit/);
  const [maj] = vers("https://api.brevo.com/v3/contacts/");
  assert.equal(maj.methode, "PUT");
  assert.match(maj.url, /contacts\/jean%40exemple\.fr$/);
  assert.deepEqual(maj.corps, { emailBlacklisted: true });
});

test("diagnostic : variables et Brevo", async () => {
  globalThis.fetch = async (url) => {
    const u = String(url);
    if (u.endsWith("/account")) return Response.json({ email: "contact@vorelik.com" });
    if (u.includes("/contacts/lists/")) return Response.json({ name: u.endsWith("/7") ? "Essai BridgeToLeads" : "Actualités VORELIK" });
    if (u.endsWith("/contacts/attributes")) return Response.json({ attributes: [{ name: "METIER" }, { name: "VILLE" }] });
    if (u.endsWith("/senders")) return Response.json({ senders: [{ email: "essai@vorelik.com", active: true }] });
    throw new Error(u);
  };
  const r = await worker.fetch(new Request("https://essai.test/diagnostic"), env);
  const d = await r.json();
  assert.equal(d.variables.BREVO_API_KEY, "présente");
  assert.equal(d.brevo.liste_essai, "Essai BridgeToLeads");
  assert.equal(d.brevo.attributs, "À CRÉER dans Brevo : REF, LANGUE, ACTUS_VORELIK");
  assert.equal(d.brevo.expediteur, "validé");
  assert.ok(!JSON.stringify(d).includes("xkeysib-test"));
});

// ------------------------------------------------------------------------------------------ version anglaise

test("essai en anglais : Google sans région, e-mail et messages en anglais, contact LANGUE=en", async () => {
  const { status, corps } = await envoyer({ langue: "en", metier: "hair salon", ville: "Austin TX", ref: "fb-us" });
  assert.equal(status, 200);
  assert.match(corps.message, /^Done! 10 businesses with no website are waiting in your inbox/);
  const [g] = vers("https://places.googleapis.com/");
  assert.equal(g.corps.textQuery, "hair salon Austin TX");
  assert.equal(g.corps.languageCode, "en");
  assert.equal(g.corps.regionCode, undefined);
  const [mail] = resultats();
  assert.equal(mail.corps.subject, "10 leads with no website: hair salon in Austin TX");
  const html = mail.corps.htmlContent;
  assert.match(html, /<html lang="en">/);
  assert.match(html, /Google Maps data\./);
  assert.match(html, /https:\/\/vorelik\.com\/en\/bridgetoleads\//);
  assert.match(html, />Unsubscribe</);
  assert.match(html, /Facebook only/);
  assert.match(html, /4\.5&nbsp;★/);
  assert.match(html, /reviews/);
  assert.ok(!/Aucun site|Données Google|Se désinscrire|avis</.test(html));
  assert.match(mail.corps.headers["List-Unsubscribe"], /&l=en>$/);
  assert.match(mail.corps.textContent, /Discover BridgeToLeads: https:\/\/vorelik\.com\/en\/bridgetoleads\//);
  const [contact] = vers("https://api.brevo.com/v3/contacts");
  assert.equal(contact.corps.attributes.LANGUE, "en");
  assert.equal(contact.corps.attributes.REF, "fb-us");
});

test("refus en anglais (e-mail déjà utilisé, champ manquant, langue dans l'adresse)", async () => {
  await envoyer({ langue: "en" });
  assert.match((await envoyer({ langue: "en" }, { ip: "8.8.8.8" })).corps.message, /^A trial has already been sent/);
  assert.equal((await envoyer({ langue: "en", ville: "" })).corps.message, "Enter a city.");
  const r = await worker.fetch(new Request("https://essai.test/essai?langue=en", {
    method: "POST", headers: { Origin: "https://pirate.example" }, body: "{}" }), env);
  assert.equal((await r.json()).message, "Form not allowed.");
});

test("aucun résultat en anglais", async () => {
  pagesGoogle = [[fiche(1, { site: "https://real-site.com" })]];
  const r = await envoyer({ langue: "en" });
  assert.match(r.corps.message, /^No business without a website found/);
});

test("désinscription en anglais", async () => {
  await envoyer({ langue: "en" });
  const lien = new URL(resultats()[0].corps.headers["List-Unsubscribe"].slice(1, -1));
  const page = await desinscription("GET", lien.search);
  assert.match(page.texte, /Confirm unsubscribe/);
  assert.match(page.texte, /<html lang="en">/);
  const fait = await desinscription("POST", lien.search);
  assert.match(fait.texte, /You are unsubscribed/);
  assert.match((await desinscription("GET", "?e=a%40b.fr&s=faux&l=en")).texte, /Invalid link/);
});

test("langue inconnue : français par défaut", async () => {
  const r = await envoyer({ langue: "de" });
  assert.match(r.corps.message, /^C'est parti/);
  assert.equal(vers("https://places.googleapis.com/")[0].corps.regionCode, "FR");
});

test("e-mail : nom de la page dans les deux langues", () => {
  const p = { nom: "Joe", adresse: "Austin", telephone: "", note: 4.1, avis: 9, site: "Yelp", maps: "" };
  assert.match(contenuEmail({ metier: "x", ville: "y", analyses: 1, lien: "l", prospects: [p], langue: "en" }).html, /Yelp only/);
  assert.match(contenuEmail({ metier: "x", ville: "y", analyses: 1, lien: "l", prospects: [p] }).html, /Yelp seulement/);
});

test("journal des domaines : plateformes comptées par langue, visible sur /domaines", async () => {
  pagesGoogle = [[fiche(1, { site: "https://salon-a.glossgenius.com/" }), fiche(2, { site: "https://salon-b.glossgenius.com/book" }),
    fiche(3, { site: "https://www.yelp.com/biz/x" }), fiche(4, { site: "https://www.yelp.com/biz/y" }),
    fiche(5, { site: "https://joes-salon.com/" }), fiche(6)]];
  await envoyer({ langue: "en" });
  await envoyer({ langue: "en", email: "b@exemple.fr" });
  const r = await worker.fetch(new Request("https://essai.test/domaines"), env);
  const d = await r.json();
  assert.equal(d.en.essais, 2);
  assert.equal(d.en.fiches, 12);
  assert.equal(d.en.sans_site, 2);
  assert.deepEqual(d.en.domaines, ["4 × glossgenius.com", "4 × yelp.com (connu)", "2 × joes-salon.com"]);
  assert.equal(d.fr.essais, 0);
  assert.equal(domainePrincipal("https://shop.example.co.uk/x"), "example.co.uk");
  assert.equal(domainePrincipal("https://www.salon.fr"), "salon.fr");
});

// ------------------------------------------------------------------------------- confirmation de l'adresse

test("adresse jetable refusée, sans e-mail ni Google", async () => {
  const r = await demander({ email: "test@yopmail.com" });
  assert.equal(r.status, 400);
  assert.equal(r.corps.erreur, "email_jetable");
  assert.equal(vers("https://api.brevo.com/").length, 0);
});

test("domaine inexistant ou sans serveur de messagerie refusé ; panne du DNS : accepté", async () => {
  assert.equal((await demander({ email: "a@inexistant-gmial.com" })).corps.erreur, "email_domaine");
  assert.equal((await demander({ email: "a@sans-mx.fr" })).corps.erreur, "email_domaine");
  assert.equal((await demander({ email: "a@panne.fr" })).corps.confirmation, true);
  assert.equal(vers("https://places.googleapis.com/").length, 0);
});

test("e-mail de confirmation : lien à usage unique, valable 24 h, contenu échappé", async () => {
  await demander({ metier: "<b>coiffeur</b>", ville: "Avignon" });
  const [mail] = confirmations();
  assert.deepEqual(mail.corps.to, [{ email: "jean@exemple.fr" }]);
  assert.equal(mail.corps.subject, "Confirmez votre essai gratuit BridgeToLeads");
  assert.match(mail.corps.htmlContent, /Recevoir mes 10 prospects/);
  assert.match(mail.corps.htmlContent, /valable 24 heures/);
  assert.ok(!mail.corps.htmlContent.includes("<b>coiffeur</b>"));
  const cle = [...env.ESSAIS.donnees.keys()].find((k) => k.startsWith("attente:"));
  assert.match(cle, /^attente:[0-9a-f]{32}$/);
  assert.ok(!JSON.parse(env.ESSAIS.donnees.get(cle)).ip.includes("1.2.3.4")); // adresse IP chiffrée
  const lien = lienDeConfirmation();
  assert.equal((await confirmer(lien)).corps.trouves, 10);
  const encore = await confirmer(lien);
  assert.equal(encore.status, 410);
  assert.equal(encore.corps.erreur, "expire");
  assert.equal(vers("https://places.googleapis.com/").length, 2); // une seule recherche (2 pages)
});

test("ouvrir le lien (GET) affiche un bouton sans lancer de recherche", async () => {
  await demander();
  const page = await confirmer(lienDeConfirmation(), "GET", false);
  assert.equal(page.status, 200);
  assert.match(page.corps, /<form method="post">/);
  assert.match(page.corps, /Recevoir mes 10 prospects/);
  assert.equal(vers("https://places.googleapis.com/").length, 0);
  const fin = await confirmer(lienDeConfirmation(), "POST", false);
  assert.match(fin.corps, /C&#39;est envoyé/);
  assert.match(fin.corps, /vorelik\.com\/bridgetoleads\//);
});

test("lien inconnu ou expiré : page claire, en anglais si besoin", async () => {
  const fr = await confirmer(new URL("https://essai.test/confirmer?t=0123"), "GET", false);
  assert.equal(fr.status, 410);
  assert.match(fr.corps, /Lien expiré/);
  assert.match(fr.corps, /vorelik\.com\/essai\//);
  const en = await confirmer(new URL("https://essai.test/confirmer?t=0123&l=en"), "GET", false);
  assert.match(en.corps, /Link expired/);
  assert.match(en.corps, /vorelik\.com\/en\/trial\//);
});

test("pas de nouvel e-mail de confirmation à la même adresse avant 10 minutes", async () => {
  await demander();
  const r = await demander({}, { ip: "9.9.9.9" });
  assert.equal(r.status, 429);
  assert.equal(r.corps.erreur, "deja_envoye");
  assert.equal(confirmations().length, 1);
});

test("5 e-mails de confirmation par adresse IP et par jour", async () => {
  for (let i = 0; i < 5; i++) assert.equal((await demander({ email: `x${i}@exemple.fr` })).corps.confirmation, true);
  assert.equal((await demander({ email: "x6@exemple.fr" })).corps.erreur, "limite_ip");
});

test("confirmation en anglais : e-mail et page en anglais", async () => {
  const r = await demander({ langue: "en", email: "joe@example.com" });
  assert.match(r.corps.message, /^One last step!/);
  const [mail] = confirmations();
  assert.equal(mail.corps.subject, "Confirm your BridgeToLeads free trial");
  assert.match(mail.corps.textContent, /&l=en/);
  const page = await confirmer(lienDeConfirmation(), "GET", false);
  assert.match(page.corps, /Get my 10 leads/);
  assert.match(page.corps, /<html lang="en">/);
});
