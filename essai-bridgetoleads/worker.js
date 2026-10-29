/**
 * Essai gratuit de BridgeToLeads (Cloudflare Worker) — pages vorelik.com/essai/ (français) et vorelik.com/en/trial/
 * (anglais : champ ou paramètre « langue=en » ; recherche Google sans région, e-mail et messages en anglais).
 *
 *   POST /essai          formulaire de la page : metier, ville, email, actus, ref, langue (fr|en), cf-turnstile-response
 *                        → { ok, trouves, message } ou { erreur, message } (message en français, à afficher tel quel)
 *   GET  /desinscription  lien de l'e-mail (?e=…&s=signature) → page avec un bouton de confirmation (les messageries
 *                        qui ouvrent les liens pour les analyser ne désinscrivent donc personne par erreur)
 *   POST /desinscription  bouton de cette page, ou désinscription « en un clic » des messageries (List-Unsubscribe-Post)
 *                        → bloque l'adresse dans Brevo
 *   GET  /diagnostic      contrôle de la configuration (variables, clé Brevo, liste, mémoire KV), sans appel Google
 *
 * Déroulé d'un essai : Turnstile → limites (1 essai par e-mail, 3 par adresse IP et par jour, plafond quotidien
 * total) → Google Places (New) Text Search « métier ville », jusqu'à 3 pages de 20 → fiches sans site (ou
 * avec seulement une page Facebook, Instagram, Yelp, Planity… : même liste que le logiciel), triées par nombre d'avis, 10 premières → e-mail Brevo → contact ajouté à la
 * liste Brevo « Essai BridgeToLeads ». Un essai sans résultat n'envoie rien et ne consomme pas l'e-mail.
 *
 * Variables (Cloudflare → Worker → Settings → Variables and Secrets) :
 *   GOOGLE_MAPS_API_KEY   secret : clé Google dédiée à l'essai (Places API (New) uniquement)
 *   BREVO_API_KEY         secret : clé API Brevo (xkeysib-…)
 *   TURNSTILE_SECRET      secret : clé secrète du widget Turnstile
 *   DESINSCRIPTION_SECRET secret : longue phrase aléatoire qui signe les liens de désinscription
 *   EXPEDITEUR            texte  : « VORELIK <essai@vorelik.com> » (adresse validée dans Brevo)
 *   BREVO_LISTE_ESSAI     texte  : numéro de la liste Brevo « Essai BridgeToLeads »
 *   BREVO_LISTE_ACTUS     texte, facultatif : numéro de la liste des personnes qui acceptent les actualités
 *   ORIGINE_SITE          texte  : https://vorelik.com,https://www.vorelik.com
 *   PLAFOND_JOUR          texte, facultatif : nombre maximal d'essais par jour, tous visiteurs confondus (100)
 *   ESSAIS                liaison KV (Settings → Bindings → KV namespace) : mémoire des limites
 *
 * Attributs de contact Brevo utilisés : METIER, VILLE, REF, LANGUE (texte), ACTUS_VORELIK (oui/non : booléen).
 */

const PLACES = "https://places.googleapis.com/v1/places:searchText";
const BREVO = "https://api.brevo.com/v3";
const TURNSTILE = "https://challenges.cloudflare.com/turnstile/v0/siteverify";
const PAGE_BTL = { fr: "https://vorelik.com/bridgetoleads/", en: "https://vorelik.com/en/bridgetoleads/" };
const ACCUEIL = { fr: "https://vorelik.com/", en: "https://vorelik.com/en/" };
const ATTRIBUTS = ["METIER", "VILLE", "REF", "LANGUE", "ACTUS_VORELIK"];
const pluriel = (n, un, plusieurs) => (n > 1 ? plusieurs : un);

// Messages affichés sous le formulaire, dans la langue de la page
const MESSAGES = {
  fr: {
    origine: "Formulaire non autorisé.",
    configuration: "L'essai est momentanément indisponible. Réessayez plus tard.",
    formulaire: "Formulaire illisible : rechargez la page et réessayez.",
    metier: "Indiquez un métier.",
    ville: "Indiquez une ville.",
    email: "Cette adresse e-mail ne semble pas valable.",
    turnstile: "La vérification anti-robot a échoué : rechargez la page et réessayez.",
    email_utilise: "Un essai a déjà été envoyé à cette adresse. Pour des recherches illimitées, découvrez BridgeToLeads.",
    limite_ip: "Vous avez atteint la limite de 3 essais par jour. Revenez demain !",
    plafond: "Victime de son succès, l'essai gratuit est complet pour aujourd'hui. Revenez demain !",
    google: "La recherche Google Maps n'a pas abouti. Réessayez dans quelques minutes.",
    envoi: "L'e-mail n'a pas pu être envoyé. Vérifiez votre adresse et réessayez.",
    interne: "Un problème technique est survenu. Réessayez dans quelques minutes.",
    aucun: (metier, ville, n) => `Aucun commerce sans site trouvé pour « ${metier} » à ${ville} (${n} `
      + `${pluriel(n, "fiche analysée", "fiches analysées")}). Essayez une autre ville ou un autre métier : `
      + "cet essai ne vous a pas été décompté.",
    succes: (n, email) => `C'est parti ! ${n} ${pluriel(n, "commerce sans site vous attend", "commerces sans site vous attendent")} `
      + `dans votre boîte mail (${email}). Pensez à regarder dans les indésirables.`,
  },
  en: {
    origine: "Form not allowed.",
    configuration: "The trial is temporarily unavailable. Please try again later.",
    formulaire: "The form could not be read: reload the page and try again.",
    metier: "Enter a business type.",
    ville: "Enter a city.",
    email: "This email address does not look valid.",
    turnstile: "The anti-robot check failed: reload the page and try again.",
    email_utilise: "A trial has already been sent to this address. For unlimited searches, discover BridgeToLeads.",
    limite_ip: "You have reached the limit of 3 trials per day. Come back tomorrow!",
    plafond: "The free trial is fully booked for today. Come back tomorrow!",
    google: "The Google Maps search did not go through. Please try again in a few minutes.",
    envoi: "The email could not be sent. Check your address and try again.",
    interne: "A technical problem occurred. Please try again in a few minutes.",
    aucun: (metier, ville, n) => `No business without a website found for “${metier}” in ${ville} (${n} `
      + `${pluriel(n, "listing", "listings")} checked). Try another city or business type: this trial was not counted.`,
    succes: (n, email) => `Done! ${n} ${pluriel(n, "business with no website is", "businesses with no website are")} `
      + `waiting in your inbox (${email}). Remember to check your spam folder.`,
  },
};
const langueDe = (valeur) => (String(valeur || "").toLowerCase() === "en" ? "en" : "fr");
const CHAMPS = [
  "places.id", "places.displayName", "places.formattedAddress", "places.nationalPhoneNumber",
  "places.internationalPhoneNumber", "places.rating", "places.userRatingCount", "places.websiteUri",
  "places.googleMapsUri", "places.businessStatus", "nextPageToken",
].join(",");
const PAGES_MAX = 3; // 3 × 20 = 60 résultats
const RETENUS = 10;
const ESSAIS_PAR_IP = 3;
const PLAFOND_DEFAUT = 100;
const JOUR = 86400;
const EMAIL = /^[^\s@<>"',;]{1,64}@[^\s@<>"',;]+\.[a-z]{2,}$/i;
// Pages qui ne sont pas un vrai site du commerce (même liste que le logiciel, find_no_website.py) → nom affiché.
// Un commerce qui n'a que l'une d'elles est un prospect : « Instagram seulement », « Yelp only »…
const PAS_UN_SITE = {
  "facebook.com": "Facebook", "fb.com": "Facebook", "fb.me": "Facebook", "instagram.com": "Instagram",
  "tiktok.com": "TikTok", "linkedin.com": "LinkedIn", "twitter.com": "X", "x.com": "X", "youtube.com": "YouTube",
  "linktr.ee": "Linktree", "wa.me": "WhatsApp", "sites.google.com": "Google Sites", "business.site": "Google Business",
  "g.page": "Google Business", "planity.com": "Planity", "treatwell.fr": "Treatwell", "treatwell.com": "Treatwell",
  "kiute.com": "Kiute", "booksy.com": "Booksy", "booksy.net": "Booksy", "fresha.com": "Fresha", "doctolib.fr": "Doctolib",
  "pagesjaunes.fr": "PagesJaunes", "tripadvisor.fr": "Tripadvisor", "tripadvisor.com": "Tripadvisor",
  "thefork.fr": "TheFork", "lafourchette.com": "TheFork", "ubereats.com": "Uber Eats", "deliveroo.fr": "Deliveroo",
  "calendly.com": "Calendly", "yelp.com": "Yelp", "yelp.ca": "Yelp", "yelp.co.uk": "Yelp",
  "yellowpages.com": "Yellow Pages", "yellowpages.ca": "Yellow Pages", "yell.com": "Yell", "nextdoor.com": "Nextdoor",
  "bbb.org": "BBB", "angi.com": "Angi", "homeadvisor.com": "HomeAdvisor", "thumbtack.com": "Thumbtack",
  "houzz.com": "Houzz", "square.site": "Square", "squareup.com": "Square", "vagaro.com": "Vagaro",
  "styleseat.com": "StyleSeat", "schedulicity.com": "Schedulicity", "mindbodyonline.com": "Mindbody",
  "opentable.com": "OpenTable", "doordash.com": "DoorDash", "grubhub.com": "Grubhub", "toasttab.com": "Toast",
  "setmore.com": "Setmore",
};

// Valeur de pause entre deux pages Google (le jeton de page suivante met un instant à devenir valable).
export const reglages = { pauseMs: 1500 };

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const cors = {
      "Access-Control-Allow-Origin": origineAutorisee(env, request.headers.get("Origin")),
      Vary: "Origin",
      "Access-Control-Allow-Methods": "POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
    };
    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: cors });
    try {
      if (url.pathname === "/desinscription") return await desinscription(request, url, env);
      let statut, corps;
      if (request.method === "POST" && url.pathname === "/essai") {
        [statut, corps] = await essai(request, env);
      } else if (request.method === "GET" && url.pathname === "/diagnostic") {
        [statut, corps] = await diagnostic(env);
      } else if (url.pathname === "/") {
        [statut, corps] = [200, { service: "essai BridgeToLeads", ok: true }];
      } else {
        [statut, corps] = [404, { erreur: "introuvable" }];
      }
      return json(statut, corps, cors);
    } catch (e) {
      console.error("essai", e && e.stack || e);
      return json(500, { erreur: "interne", message: MESSAGES[langueDe(url.searchParams.get("langue"))].interne }, cors);
    }
  },
};

function json(statut, corps, entetes = {}) {
  return new Response(JSON.stringify(corps), {
    status: statut, headers: { "Content-Type": "application/json; charset=utf-8", ...entetes },
  });
}

function origines(env) {
  return String(env.ORIGINE_SITE || "").split(",").map((o) => o.trim().replace(/\/$/, "")).filter(Boolean);
}

function origineAutorisee(env, origine) {
  const liste = origines(env);
  return origine && liste.includes(origine) ? origine : liste[0] || "null";
}

const refus = (code, message, statut = 400) => [statut, { erreur: code, message }];
const refusEn = (langue) => (code, statut = 400) => refus(code, MESSAGES[langue][code], statut);

// ---------------------------------------------------------------------------------------------------- essai

async function lireFormulaire(request) {
  const type = request.headers.get("Content-Type") || "";
  if (type.includes("application/json")) return await request.json();
  return Object.fromEntries(await request.formData());
}

function nettoyer(texte, max) {
  return String(texte ?? "").replace(/[\u0000-\u001f\u007f<>]/g, " ").replace(/\s+/g, " ").trim().slice(0, max);
}

async function essai(request, env) {
  let langue = langueDe(new URL(request.url).searchParams.get("langue"));
  let non = refusEn(langue);
  const origine = request.headers.get("Origin");
  if (origine && !origines(env).includes(origine)) return non("origine", 403);
  const manque = ["GOOGLE_MAPS_API_KEY", "BREVO_API_KEY", "TURNSTILE_SECRET", "DESINSCRIPTION_SECRET", "EXPEDITEUR",
    "BREVO_LISTE_ESSAI"].filter((v) => !env[v]);
  if (manque.length || !env.ESSAIS) {
    console.error("configuration incomplète", manque, env.ESSAIS ? "" : "ESSAIS (KV)");
    return non("configuration", 503);
  }

  let f;
  try {
    f = await lireFormulaire(request);
  } catch {
    return non("formulaire");
  }
  if (f.langue) {
    langue = langueDe(f.langue);
    non = refusEn(langue);
  }
  const metier = nettoyer(f.metier, 60);
  const ville = nettoyer(f.ville, 80);
  const email = nettoyer(f.email, 254).toLowerCase();
  const ref = nettoyer(f.ref, 60);
  const actus = ["1", "true", "on", "oui", true].includes(f.actus);
  if (metier.length < 2) return non("metier");
  if (ville.length < 2) return non("ville");
  if (!EMAIL.test(email)) return non("email");

  const ip = request.headers.get("CF-Connecting-IP") || "inconnue";
  if (!(await turnstileValide(f["cf-turnstile-response"], ip, env))) {
    return non("turnstile", 403);
  }

  const jour = new Date().toISOString().slice(0, 10);
  const cleEmail = `email:${await empreinte(email)}`;
  const cleIp = `ip:${jour}:${await empreinte(ip)}`;
  const cleJour = `jour:${jour}`;
  const [dejaEmail, essaisIp, essaisJour] = await Promise.all([
    env.ESSAIS.get(cleEmail), env.ESSAIS.get(cleIp), env.ESSAIS.get(cleJour),
  ]);
  if (dejaEmail) {
    return non("email_utilise", 429);
  }
  if (Number(essaisIp || 0) >= ESSAIS_PAR_IP) {
    return non("limite_ip", 429);
  }
  const plafond = Number(env.PLAFOND_JOUR) > 0 ? Number(env.PLAFOND_JOUR) : PLAFOND_DEFAUT;
  if (Number(essaisJour || 0) >= plafond) {
    return non("plafond", 429);
  }

  let fiches;
  try {
    fiches = await rechercher(`${metier} ${ville}`, env, langue);
  } catch (e) {
    console.error("Google Places", e.message);
    return non("google", 502);
  }
  // L'adresse IP compte dès qu'une recherche Google a été faite (c'est elle qui coûte).
  await compter(env, cleIp, Number(essaisIp || 0) + 1, 2 * JOUR);
  await compter(env, cleJour, Number(essaisJour || 0) + 1, 2 * JOUR);

  const prospects = selectionner(fiches);
  if (!prospects.length) {
    return [200, { ok: true, trouves: 0, message: MESSAGES[langue].aucun(metier, ville, fiches.length) }];
  }

  const lien = await lienDesinscription(email, env, new URL(request.url).origin, langue);
  try {
    await envoyerEmail({ email, metier, ville, prospects, analyses: fiches.length, lien, langue }, env);
  } catch (e) {
    console.error("Brevo e-mail", e.message);
    return non("envoi", 502);
  }
  await env.ESSAIS.put(cleEmail, jour, { expirationTtl: 365 * JOUR });
  try {
    await ajouterContact({ email, metier, ville, ref, actus, langue }, env);
  } catch (e) {
    console.error("Brevo contact", e.message); // l'essai est envoyé : on ne bloque pas le visiteur
  }
  return [200, { ok: true, trouves: prospects.length, message: MESSAGES[langue].succes(prospects.length, email) }];
}

async function compter(env, cle, valeur, ttl) {
  await env.ESSAIS.put(cle, String(valeur), { expirationTtl: ttl });
}

async function turnstileValide(jeton, ip, env) {
  if (!jeton) return false;
  const r = await fetch(TURNSTILE, {
    method: "POST",
    body: new URLSearchParams({ secret: env.TURNSTILE_SECRET, response: String(jeton), remoteip: ip }),
  });
  const d = await r.json().catch(() => ({}));
  if (!d.success) console.warn("Turnstile refusé", JSON.stringify(d["error-codes"] || []));
  return d.success === true;
}

async function empreinte(texte) {
  const octets = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(texte));
  return [...new Uint8Array(octets)].map((o) => o.toString(16).padStart(2, "0")).join("").slice(0, 32);
}

// ---------------------------------------------------------------------------------------------- Google Places

async function rechercher(requete, env, langue = "fr") {
  // Français : résultats en français, limités à la France. Anglais : sans région, c'est la ville tapée qui décide.
  const corps = langue === "en" ? { textQuery: requete, languageCode: "en", pageSize: 20 }
    : { textQuery: requete, languageCode: "fr", regionCode: "FR", pageSize: 20 };
  const fiches = [];
  for (let page = 0; page < PAGES_MAX; page++) {
    const r = await fetch(PLACES, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": env.GOOGLE_MAPS_API_KEY,
        "X-Goog-FieldMask": CHAMPS,
      },
      body: JSON.stringify(corps),
    });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) {
      if (page > 0) break; // page suivante refusée : on garde ce qu'on a
      throw new Error(`HTTP ${r.status} ${d.error?.status || ""} ${d.error?.message || ""}`.trim());
    }
    fiches.push(...(d.places || []));
    if (!d.nextPageToken) break;
    corps.pageToken = d.nextPageToken;
    if (reglages.pauseMs) await new Promise((ok) => setTimeout(ok, reglages.pauseMs));
  }
  return fiches;
}

function hote(adresse) {
  try {
    return new URL(adresse).hostname.toLowerCase().replace(/^(www|m|web)\./, "");
  } catch {
    return "";
  }
}

/** Nom de la page (« Instagram », « Yelp »…) si l'adresse n'est pas un vrai site du commerce, sinon null. */
export function pageNonSite(adresse) {
  const h = hote(adresse);
  const domaine = Object.keys(PAS_UN_SITE).find((d) => h === d || h.endsWith("." + d));
  return domaine ? PAS_UN_SITE[domaine] : null;
}

/** Fiches ouvertes sans site (ou avec seulement une page de réseau social, d'annuaire ou de réservation),
 *  sans doublon, triées par nombre d'avis. */
export function selectionner(fiches) {
  const vues = new Set();
  return fiches
    .filter((p) => {
      if (vues.has(p.id)) return false;
      vues.add(p.id);
      return (p.businessStatus || "OPERATIONAL") === "OPERATIONAL" && (!p.websiteUri || pageNonSite(p.websiteUri) !== null);
    })
    .map((p) => ({
      nom: p.displayName?.text || "",
      adresse: p.formattedAddress || "",
      telephone: p.nationalPhoneNumber || p.internationalPhoneNumber || "",
      note: typeof p.rating === "number" ? p.rating : null,
      avis: p.userRatingCount || 0,
      site: p.websiteUri ? pageNonSite(p.websiteUri) : "aucun", // « aucun » ou nom de la page
      maps: p.googleMapsUri || "",
    }))
    .sort((a, b) => b.avis - a.avis)
    .slice(0, RETENUS);
}

// ---------------------------------------------------------------------------------------------------- Brevo

async function brevo(chemin, env, init = {}) {
  const r = await fetch(`${BREVO}${chemin}`, {
    ...init,
    headers: { "api-key": env.BREVO_API_KEY, Accept: "application/json", "Content-Type": "application/json" },
  });
  const texte = await r.text();
  if (!r.ok) throw new Error(`Brevo ${chemin} HTTP ${r.status} ${texte.slice(0, 300)}`);
  return texte ? JSON.parse(texte) : {};
}

function expediteur(env) {
  const m = String(env.EXPEDITEUR).match(/^\s*(.*?)\s*<([^>]+)>\s*$/);
  return m ? { name: m[1] || "VORELIK", email: m[2] } : { name: "VORELIK", email: String(env.EXPEDITEUR).trim() };
}

const echapper = (t) => String(t ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

// Textes de l'e-mail, dans la langue de la page
const EMAIL_TEXTES = {
  fr: {
    lang: "fr", sur: "Essai gratuit BridgeToLeads", aucun: "Aucun site", seulement: (page) => `${page} seulement`,
    nombre: (x) => String(x).replace(".", ","), avis: "avis", voir: "Voir",
    titre: (n, m, v) => `Vos ${n} ${pluriel(n, "prospect", "prospects")} : « ${m} » à ${v}`,
    intro: (a, n) => `Bonjour,<br>Voici les commerces <b>sans site web</b> (ou avec seulement une page Facebook, Instagram, d'annuaire ou de `
      + `réservation) trouvés sur `
      + `Google Maps, les plus établis en premier : ${a} ${pluriel(a, "fiche analysée", "fiches analysées")}, `
      + `${n} ${pluriel(n, "retenue", "retenues")}.`,
    colonnes: ["Commerce", "Téléphone", "Note", "Maps"],
    donnees: "Données Google Maps.",
    accroche: "Envie de la liste complète, pour toutes vos villes ?",
    pitch: "Avec BridgeToLeads : recherches illimitées, tous les métiers et toutes les villes, export Excel en un clic.",
    bouton: "Découvrir BridgeToLeads →",
    pourquoi: "Vous recevez cet e-mail car vous avez demandé un essai gratuit sur vorelik.com.",
    desinscrire: "Se désinscrire",
    sansTel: "pas de téléphone", sansNote: "pas de note",
    decouvrir: "Découvrir BridgeToLeads :", desinscrireTexte: "Se désinscrire :",
    sujet: (n, m, v) => `${n} ${pluriel(n, "prospect", "prospects")} sans site web : ${m} à ${v}`,
    enTete: (m, v) => `Essai gratuit BridgeToLeads — « ${m} » à ${v}`,
  },
  en: {
    lang: "en", sur: "BridgeToLeads free trial", aucun: "No website", seulement: (page) => `${page} only`,
    nombre: (x) => String(x), avis: "reviews", voir: "View",
    titre: (n, m, v) => `Your ${n} ${pluriel(n, "lead", "leads")}: “${m}” in ${v}`,
    intro: (a, n) => `Hello,<br>Here are the businesses <b>with no website</b> (or just a social media, directory or booking page) found `
      + `on Google Maps, `
      + `most established first: ${a} ${pluriel(a, "listing", "listings")} checked, ${n} selected.`,
    colonnes: ["Business", "Phone", "Rating", "Maps"],
    donnees: "Google Maps data.",
    accroche: "Want the full list, for all your cities?",
    pitch: "With BridgeToLeads: unlimited searches, every business type and every city, one-click Excel export.",
    bouton: "Discover BridgeToLeads →",
    pourquoi: "You are receiving this email because you requested a free trial on vorelik.com.",
    desinscrire: "Unsubscribe",
    sansTel: "no phone", sansNote: "no rating",
    decouvrir: "Discover BridgeToLeads:", desinscrireTexte: "Unsubscribe:",
    sujet: (n, m, v) => `${n} ${pluriel(n, "lead", "leads")} with no website: ${m} in ${v}`,
    enTete: (m, v) => `BridgeToLeads free trial — “${m}” in ${v}`,
  },
};

export function contenuEmail({ metier, ville, prospects, analyses, lien, langue = "fr" }) {
  const T = EMAIL_TEXTES[langueDe(langue)];
  const page = PAGE_BTL[T.lang];
  const td = "padding:10px 10px;border-bottom:1px solid #EEE8FB;vertical-align:top";
  const lignes = prospects.map((p, i) => `
        <tr style="background:${i % 2 ? "#FFFFFF" : "#FAF7FF"}">
          <td style="${td}"><div style="font-weight:700;color:#1E1B4B">${echapper(p.nom)}</div>
            <div style="margin-top:3px;font-size:12px;font-weight:700;color:${p.site === "aucun" ? "#DB2777" : "#6D28D9"}">${echapper(p.site === "aucun" ? T.aucun : T.seulement(p.site))}</div>
            <div style="margin-top:3px;font-size:12px;color:#6B6893">${echapper(p.adresse)}</div></td>
          <td style="${td};white-space:nowrap">${p.telephone ? `<a href="tel:${echapper(p.telephone.replace(/[^\d+]/g, ""))}" style="color:#1E1B4B;text-decoration:none">${echapper(p.telephone)}</a>` : "—"}</td>
          <td style="${td};white-space:nowrap">${p.note === null ? "" : `${echapper(T.nombre(p.note))}&nbsp;★<br>`}<span style="font-size:12px;color:#6B6893">${p.avis}&nbsp;${T.avis}</span></td>
          <td style="${td}">${p.maps ? `<a href="${echapper(p.maps)}" style="color:#7C3AED;font-weight:700">${T.voir}</a>` : ""}</td>
        </tr>`).join("");
  const n = prospects.length;
  const html = `<!doctype html>
<html lang="${T.lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>${echapper(T.titre(n, metier, ville))}</title></head>
<body style="margin:0;padding:0;background:#F6F3FF;font-family:Segoe UI,Helvetica,Arial,sans-serif;color:#1E1B4B">
  <div style="max-width:760px;margin:0 auto;padding:24px 12px">
    <div style="background:linear-gradient(120deg,#7C3AED,#EC4899 55%,#F97316);background-color:#7C3AED;border-radius:18px 18px 0 0;padding:26px 24px;color:#FFFFFF">
      <div style="font-size:13px;opacity:.9;letter-spacing:.08em;text-transform:uppercase">${T.sur}</div>
      <h1 style="margin:8px 0 0;font-size:24px;line-height:1.25">${echapper(T.titre(n, metier, ville))}</h1>
    </div>
    <div style="background:#FFFFFF;border-radius:0 0 18px 18px;padding:22px 20px 26px">
      <p style="margin:0 0 16px;line-height:1.6">${T.intro(analyses, n)}</p>
      <table role="presentation" cellspacing="0" cellpadding="0" style="width:100%;border-collapse:collapse;font-size:14px;line-height:1.35">
        <thead><tr style="background:#1E1B4B;color:#FFFFFF;text-align:left;font-size:13px">
          ${T.colonnes.map((c) => `<th style="padding:10px">${c}</th>`).join("")}
        </tr></thead>
        <tbody>${lignes}
        </tbody>
      </table>
      <p style="margin:10px 0 0;font-size:12px;color:#6B6893">${T.donnees}</p>
      <div style="margin:26px 0 0;padding:20px;border-radius:14px;background:#F6F3FF;text-align:center">
        <p style="margin:0 0 12px;font-weight:700;font-size:17px">${T.accroche}</p>
        <p style="margin:0 0 16px;color:#4B4870;line-height:1.5">${T.pitch}</p>
        <a href="${page}" style="display:inline-block;background:#7C3AED;color:#FFFFFF;text-decoration:none;font-weight:700;padding:13px 24px;border-radius:999px">${T.bouton}</a>
      </div>
    </div>
    <p style="margin:18px 8px 0;font-size:12px;line-height:1.6;color:#6B6893;text-align:center">
      ${T.pourquoi}<br>
      VORELIK · <a href="${ACCUEIL[T.lang]}" style="color:#6B6893">vorelik.com</a> · <a href="${echapper(lien)}" style="color:#6B6893">${T.desinscrire}</a>
    </p>
  </div>
</body></html>`;
  const texte = [T.enTete(metier, ville), "",
    ...prospects.map((p, i) => `${i + 1}. ${p.nom} — ${p.site === "aucun" ? T.aucun : T.seulement(p.site)} — ${p.telephone || T.sansTel}`
      + ` — ${p.adresse} — ${p.note === null ? T.sansNote : T.nombre(p.note) + " ★"} (${p.avis} ${T.avis})${p.maps ? " — " + p.maps : ""}`),
    "", T.donnees, "", `${T.decouvrir} ${page}`, "", `${T.desinscrireTexte} ${lien}`].join("\n");
  return { sujet: T.sujet(n, metier, ville), html, texte };
}

async function envoyerEmail(donnees, env) {
  const { sujet, html, texte } = contenuEmail(donnees);
  await brevo("/smtp/email", env, {
    method: "POST",
    body: JSON.stringify({
      sender: expediteur(env),
      to: [{ email: donnees.email }],
      subject: sujet,
      htmlContent: html,
      textContent: texte,
      headers: { "List-Unsubscribe": `<${donnees.lien}>`, "List-Unsubscribe-Post": "List-Unsubscribe=One-Click" },
      tags: ["essai-bridgetoleads"],
    }),
  });
}

async function ajouterContact({ email, metier, ville, ref, actus, langue = "fr" }, env) {
  const listes = [Number(env.BREVO_LISTE_ESSAI)];
  if (actus && Number(env.BREVO_LISTE_ACTUS)) listes.push(Number(env.BREVO_LISTE_ACTUS));
  await brevo("/contacts", env, {
    method: "POST",
    body: JSON.stringify({
      email, updateEnabled: true, listIds: listes,
      attributes: { METIER: metier, VILLE: ville, REF: ref, LANGUE: langue, ACTUS_VORELIK: actus },
    }),
  });
}

// ------------------------------------------------------------------------------------------- désinscription

async function signature(email, env) {
  const cle = await crypto.subtle.importKey("raw", new TextEncoder().encode(env.DESINSCRIPTION_SECRET),
    { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const octets = await crypto.subtle.sign("HMAC", cle, new TextEncoder().encode(email.toLowerCase()));
  return [...new Uint8Array(octets)].map((o) => o.toString(16).padStart(2, "0")).join("").slice(0, 32);
}

export async function lienDesinscription(email, env, base, langue = "fr") {
  return `${base}/desinscription?e=${encodeURIComponent(email)}&s=${await signature(email, env)}${langue === "en" ? "&l=en" : ""}`;
}

const DESINSCRIPTION = {
  fr: {
    invalide: ["Lien non valable", "Ce lien de désinscription est incomplet. Écrivez-nous à support@vorelik.com : nous vous retirerons de nos listes."],
    question: (e) => ["Se désinscrire", `Ne plus recevoir d'e-mails de VORELIK à l'adresse ${e} ?`],
    bouton: "Confirmer la désinscription",
    fait: (e) => ["Vous êtes désinscrit", `L'adresse ${e} ne recevra plus d'e-mails de VORELIK.`],
    retour: "Retour sur vorelik.com",
  },
  en: {
    invalide: ["Invalid link", "This unsubscribe link is incomplete. Write to us at support@vorelik.com and we will remove you from our lists."],
    question: (e) => ["Unsubscribe", `Stop receiving emails from VORELIK at ${e}?`],
    bouton: "Confirm unsubscribe",
    fait: (e) => ["You are unsubscribed", `${e} will no longer receive emails from VORELIK.`],
    retour: "Back to vorelik.com",
  },
};

function pageHtml(titre, texte, statut = 200, bouton = "", langue = "fr") {
  const D = DESINSCRIPTION[langue];
  return new Response(`<!doctype html><html lang="${langue}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex"><title>${echapper(titre)} — VORELIK</title></head>
<body style="margin:0;min-height:100vh;display:grid;place-items:center;background:#F6F3FF;font-family:Segoe UI,Helvetica,Arial,sans-serif;color:#1E1B4B">
<main style="max-width:460px;margin:24px;padding:32px 28px;background:#fff;border-radius:20px;box-shadow:0 20px 50px -25px rgba(124,58,237,.45);text-align:center">
<h1 style="margin:0 0 12px;font-size:1.5rem">${echapper(titre)}</h1><p style="margin:0 0 20px;line-height:1.6;color:#4B4870">${echapper(texte)}</p>
${bouton}<a href="${ACCUEIL[langue]}" style="color:#7C3AED;font-weight:700">${D.retour}</a></main></body></html>`,
  { status: statut, headers: { "Content-Type": "text/html; charset=utf-8" } });
}

async function desinscription(request, url, env) {
  const email = (url.searchParams.get("e") || "").trim().toLowerCase();
  const s = url.searchParams.get("s") || "";
  const langue = langueDe(url.searchParams.get("l"));
  const D = DESINSCRIPTION[langue];
  if (!email || !env.DESINSCRIPTION_SECRET || s !== await signature(email, env)) {
    return pageHtml(...D.invalide, 400, "", langue);
  }
  if (request.method === "GET") {
    return pageHtml(...D.question(email), 200,
      `<form method="post" style="margin:0 0 20px"><button type="submit" style="font:inherit;font-weight:700;color:#fff;background:#7C3AED;border:0;border-radius:999px;padding:13px 26px;cursor:pointer">${D.bouton}</button></form>`, langue);
  }
  if (request.method !== "POST") return new Response(null, { status: 405 });
  await brevo(`/contacts/${encodeURIComponent(email)}`, env, {
    method: "PUT", body: JSON.stringify({ emailBlacklisted: true }),
  }).catch(async (e) => {
    if (!String(e.message).includes("HTTP 404")) throw e;
    await brevo("/contacts", env, { method: "POST", body: JSON.stringify({ email, emailBlacklisted: true, updateEnabled: true }) });
  });
  return pageHtml(...D.fait(email), 200, "", langue);
}

// ---------------------------------------------------------------------------------------------- diagnostic

async function diagnostic(env) {
  const variables = Object.fromEntries(["GOOGLE_MAPS_API_KEY", "BREVO_API_KEY", "TURNSTILE_SECRET", "DESINSCRIPTION_SECRET",
    "EXPEDITEUR", "BREVO_LISTE_ESSAI", "BREVO_LISTE_ACTUS", "ORIGINE_SITE", "PLAFOND_JOUR"]
    .map((v) => [v, env[v] ? (/KEY|SECRET/.test(v) ? "présente" : String(env[v])) : "ABSENTE"]));
  const resultat = { variables, memoire_kv: env.ESSAIS ? "liée" : "ABSENTE : Settings → Bindings → KV namespace « ESSAIS »" };
  if (env.BREVO_API_KEY) {
    try {
      const compte = await brevo("/account", env);
      resultat.brevo = { compte: compte.email, ok: true };
      if (env.BREVO_LISTE_ESSAI) {
        const liste = await brevo(`/contacts/lists/${Number(env.BREVO_LISTE_ESSAI)}`, env);
        resultat.brevo.liste_essai = liste.name;
      }
      if (env.BREVO_LISTE_ACTUS) {
        const liste = await brevo(`/contacts/lists/${Number(env.BREVO_LISTE_ACTUS)}`, env);
        resultat.brevo.liste_actus = liste.name;
      }
      const { attributes = [] } = await brevo("/contacts/attributes", env);
      const noms = new Set(attributes.map((a) => a.name));
      const absents = ATTRIBUTS.filter((a) => !noms.has(a));
      resultat.brevo.attributs = absents.length ? `À CRÉER dans Brevo : ${absents.join(", ")}` : "ok";
      const { senders = [] } = await brevo("/senders", env);
      const exp = env.EXPEDITEUR ? expediteur(env).email.toLowerCase() : "";
      const trouve = senders.find((x) => String(x.email).toLowerCase() === exp);
      resultat.brevo.expediteur = !exp ? "ABSENT" : trouve ? (trouve.active ? "validé" : "EN ATTENTE de validation")
        : `INCONNU de Brevo : ajoutez ${exp} dans Senders, Domains & Dedicated IPs`;
    } catch (e) {
      resultat.brevo = { ok: false, erreur: e.message };
    }
  }
  const ok = !Object.entries(variables).some(([v, x]) => x === "ABSENTE" && !["BREVO_LISTE_ACTUS", "PLAFOND_JOUR"].includes(v))
    && Boolean(env.ESSAIS) && resultat.brevo?.ok !== false
    && (!resultat.brevo || ["validé", undefined].includes(resultat.brevo.expediteur))
    && (!resultat.brevo || ["ok", undefined].includes(resultat.brevo.attributs));
  return [200, { ok, ...resultat }];
}
