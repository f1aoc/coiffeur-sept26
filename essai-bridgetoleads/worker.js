/**
 * Essai gratuit de BridgeToLeads (Cloudflare Worker) — page vorelik.com/essai/.
 *
 *   POST /essai          formulaire de la page : metier, ville, email, actus, ref, cf-turnstile-response
 *                        → { ok, trouves, message } ou { erreur, message } (message en français, à afficher tel quel)
 *   GET  /desinscription  lien de l'e-mail (?e=…&s=signature) → page avec un bouton de confirmation (les messageries
 *                        qui ouvrent les liens pour les analyser ne désinscrivent donc personne par erreur)
 *   POST /desinscription  bouton de cette page, ou désinscription « en un clic » des messageries (List-Unsubscribe-Post)
 *                        → bloque l'adresse dans Brevo
 *   GET  /diagnostic      contrôle de la configuration (variables, clé Brevo, liste, mémoire KV), sans appel Google
 *
 * Déroulé d'un essai : Turnstile → limites (1 essai par e-mail, 3 par adresse IP et par jour, plafond quotidien
 * total) → Google Places (New) Text Search « métier ville », jusqu'à 3 pages de 20 → fiches sans site (ou
 * avec une simple page Facebook), triées par nombre d'avis, 10 premières → e-mail Brevo → contact ajouté à la
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
 * Attributs de contact Brevo utilisés : METIER, VILLE, REF (texte), ACTUS_VORELIK (oui/non : booléen).
 */

const PLACES = "https://places.googleapis.com/v1/places:searchText";
const BREVO = "https://api.brevo.com/v3";
const TURNSTILE = "https://challenges.cloudflare.com/turnstile/v0/siteverify";
const PAGE_BTL = "https://vorelik.com/bridgetoleads/";
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
const FACEBOOK = ["facebook.com", "fb.com", "fb.me"];

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
      return json(500, { erreur: "interne", message: "Un problème technique est survenu. Réessayez dans quelques minutes." }, cors);
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
  const origine = request.headers.get("Origin");
  if (origine && !origines(env).includes(origine)) return refus("origine", "Formulaire non autorisé.", 403);
  const manque = ["GOOGLE_MAPS_API_KEY", "BREVO_API_KEY", "TURNSTILE_SECRET", "DESINSCRIPTION_SECRET", "EXPEDITEUR",
    "BREVO_LISTE_ESSAI"].filter((v) => !env[v]);
  if (manque.length || !env.ESSAIS) {
    console.error("configuration incomplète", manque, env.ESSAIS ? "" : "ESSAIS (KV)");
    return refus("configuration", "L'essai est momentanément indisponible. Réessayez plus tard.", 503);
  }

  let f;
  try {
    f = await lireFormulaire(request);
  } catch {
    return refus("formulaire", "Formulaire illisible : rechargez la page et réessayez.");
  }
  const metier = nettoyer(f.metier, 60);
  const ville = nettoyer(f.ville, 80);
  const email = nettoyer(f.email, 254).toLowerCase();
  const ref = nettoyer(f.ref, 60);
  const actus = ["1", "true", "on", "oui", true].includes(f.actus);
  if (metier.length < 2) return refus("metier", "Indiquez un métier.");
  if (ville.length < 2) return refus("ville", "Indiquez une ville.");
  if (!EMAIL.test(email)) return refus("email", "Cette adresse e-mail ne semble pas valable.");

  const ip = request.headers.get("CF-Connecting-IP") || "inconnue";
  if (!(await turnstileValide(f["cf-turnstile-response"], ip, env))) {
    return refus("turnstile", "La vérification anti-robot a échoué : rechargez la page et réessayez.", 403);
  }

  const jour = new Date().toISOString().slice(0, 10);
  const cleEmail = `email:${await empreinte(email)}`;
  const cleIp = `ip:${jour}:${await empreinte(ip)}`;
  const cleJour = `jour:${jour}`;
  const [dejaEmail, essaisIp, essaisJour] = await Promise.all([
    env.ESSAIS.get(cleEmail), env.ESSAIS.get(cleIp), env.ESSAIS.get(cleJour),
  ]);
  if (dejaEmail) {
    return refus("email_utilise", "Un essai a déjà été envoyé à cette adresse. Pour des recherches illimitées, "
      + "découvrez BridgeToLeads.", 429);
  }
  if (Number(essaisIp || 0) >= ESSAIS_PAR_IP) {
    return refus("limite_ip", "Vous avez atteint la limite de 3 essais par jour. Revenez demain !", 429);
  }
  const plafond = Number(env.PLAFOND_JOUR) > 0 ? Number(env.PLAFOND_JOUR) : PLAFOND_DEFAUT;
  if (Number(essaisJour || 0) >= plafond) {
    return refus("plafond", "Victime de son succès, l'essai gratuit est complet pour aujourd'hui. Revenez demain !", 429);
  }

  let fiches;
  try {
    fiches = await rechercher(`${metier} ${ville}`, env);
  } catch (e) {
    console.error("Google Places", e.message);
    return refus("google", "La recherche Google Maps n'a pas abouti. Réessayez dans quelques minutes.", 502);
  }
  // L'adresse IP compte dès qu'une recherche Google a été faite (c'est elle qui coûte).
  await compter(env, cleIp, Number(essaisIp || 0) + 1, 2 * JOUR);
  await compter(env, cleJour, Number(essaisJour || 0) + 1, 2 * JOUR);

  const prospects = selectionner(fiches);
  if (!prospects.length) {
    return [200, { ok: true, trouves: 0, message: `Aucun commerce sans site trouvé pour « ${metier} » à ${ville} `
      + `(${fiches.length} fiche${fiches.length > 1 ? "s" : ""} analysée${fiches.length > 1 ? "s" : ""}). Essayez une autre `
      + "ville ou un autre métier : cet essai ne vous a pas été décompté." }];
  }

  const lien = await lienDesinscription(email, env, new URL(request.url).origin);
  try {
    await envoyerEmail({ email, metier, ville, prospects, analyses: fiches.length, lien }, env);
  } catch (e) {
    console.error("Brevo e-mail", e.message);
    return refus("envoi", "L'e-mail n'a pas pu être envoyé. Vérifiez votre adresse et réessayez.", 502);
  }
  await env.ESSAIS.put(cleEmail, jour, { expirationTtl: 365 * JOUR });
  try {
    await ajouterContact({ email, metier, ville, ref, actus }, env);
  } catch (e) {
    console.error("Brevo contact", e.message); // l'essai est envoyé : on ne bloque pas le visiteur
  }
  return [200, { ok: true, trouves: prospects.length, message: `C'est parti ! ${prospects.length} commerce`
    + `${prospects.length > 1 ? "s" : ""} sans site ${prospects.length > 1 ? "vous attendent" : "vous attend"} dans votre `
    + `boîte mail (${email}). Pensez à regarder dans les indésirables.` }];
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

async function rechercher(requete, env) {
  const corps = { textQuery: requete, languageCode: "fr", regionCode: "FR", pageSize: 20 };
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
    return new URL(adresse).hostname.toLowerCase().replace(/^(www|m|web|business)\./, "");
  } catch {
    return "";
  }
}

export function pageFacebook(adresse) {
  const h = hote(adresse);
  return FACEBOOK.some((d) => h === d || h.endsWith("." + d));
}

/** Fiches ouvertes sans site (ou avec une simple page Facebook), sans doublon, triées par nombre d'avis. */
export function selectionner(fiches) {
  const vues = new Set();
  return fiches
    .filter((p) => {
      if (vues.has(p.id)) return false;
      vues.add(p.id);
      return (p.businessStatus || "OPERATIONAL") === "OPERATIONAL" && (!p.websiteUri || pageFacebook(p.websiteUri));
    })
    .map((p) => ({
      nom: p.displayName?.text || "",
      adresse: p.formattedAddress || "",
      telephone: p.nationalPhoneNumber || p.internationalPhoneNumber || "",
      note: typeof p.rating === "number" ? p.rating : null,
      avis: p.userRatingCount || 0,
      site: p.websiteUri ? "Facebook seulement" : "Aucun",
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

export function contenuEmail({ metier, ville, prospects, analyses, lien }) {
  const td = "padding:10px 10px;border-bottom:1px solid #EEE8FB;vertical-align:top";
  const lignes = prospects.map((p, i) => `
        <tr style="background:${i % 2 ? "#FFFFFF" : "#FAF7FF"}">
          <td style="${td}"><div style="font-weight:700;color:#1E1B4B">${echapper(p.nom)}</div>
            <div style="margin-top:3px;font-size:12px;font-weight:700;color:${p.site === "Aucun" ? "#DB2777" : "#6D28D9"}">${p.site === "Aucun" ? "Aucun site" : "Facebook seulement"}</div>
            <div style="margin-top:3px;font-size:12px;color:#6B6893">${echapper(p.adresse)}</div></td>
          <td style="${td};white-space:nowrap">${p.telephone ? `<a href="tel:${echapper(p.telephone.replace(/[^\d+]/g, ""))}" style="color:#1E1B4B;text-decoration:none">${echapper(p.telephone)}</a>` : "—"}</td>
          <td style="${td};white-space:nowrap">${p.note === null ? "" : `${echapper(String(p.note).replace(".", ","))}&nbsp;★<br>`}<span style="font-size:12px;color:#6B6893">${p.avis}&nbsp;avis</span></td>
          <td style="${td}">${p.maps ? `<a href="${echapper(p.maps)}" style="color:#7C3AED;font-weight:700">Voir</a>` : ""}</td>
        </tr>`).join("");
  const n = prospects.length;
  const titre = `Vos prospects : ${metier} à ${ville}`;
  const html = `<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>${echapper(titre)}</title></head>
<body style="margin:0;padding:0;background:#F6F3FF;font-family:Segoe UI,Helvetica,Arial,sans-serif;color:#1E1B4B">
  <div style="max-width:760px;margin:0 auto;padding:24px 12px">
    <div style="background:linear-gradient(120deg,#7C3AED,#EC4899 55%,#F97316);background-color:#7C3AED;border-radius:18px 18px 0 0;padding:26px 24px;color:#FFFFFF">
      <div style="font-size:13px;opacity:.9;letter-spacing:.08em;text-transform:uppercase">Essai gratuit BridgeToLeads</div>
      <h1 style="margin:8px 0 0;font-size:24px;line-height:1.25">Vos ${n} prospect${n > 1 ? "s" : ""} : « ${echapper(metier)} » à ${echapper(ville)}</h1>
    </div>
    <div style="background:#FFFFFF;border-radius:0 0 18px 18px;padding:22px 20px 26px">
      <p style="margin:0 0 16px;line-height:1.6">Bonjour,<br>Voici les commerces <b>sans site web</b> (ou avec une simple page Facebook) trouvés sur Google Maps, les plus établis en premier : ${analyses} fiche${analyses > 1 ? "s" : ""} analysée${analyses > 1 ? "s" : ""}, ${n} retenue${n > 1 ? "s" : ""}.</p>
      <table role="presentation" cellspacing="0" cellpadding="0" style="width:100%;border-collapse:collapse;font-size:14px;line-height:1.35">
        <thead><tr style="background:#1E1B4B;color:#FFFFFF;text-align:left;font-size:13px">
          <th style="padding:10px">Commerce</th><th style="padding:10px">Téléphone</th><th style="padding:10px">Note</th><th style="padding:10px">Maps</th>
        </tr></thead>
        <tbody>${lignes}
        </tbody>
      </table>
      <p style="margin:10px 0 0;font-size:12px;color:#6B6893">Données Google Maps.</p>
      <div style="margin:26px 0 0;padding:20px;border-radius:14px;background:#F6F3FF;text-align:center">
        <p style="margin:0 0 12px;font-weight:700;font-size:17px">Envie de la liste complète, pour toutes vos villes ?</p>
        <p style="margin:0 0 16px;color:#4B4870;line-height:1.5">Avec BridgeToLeads : recherches illimitées, tous les métiers et toutes les villes, export Excel en un clic.</p>
        <a href="${PAGE_BTL}" style="display:inline-block;background:#7C3AED;color:#FFFFFF;text-decoration:none;font-weight:700;padding:13px 24px;border-radius:999px">Découvrir BridgeToLeads →</a>
      </div>
    </div>
    <p style="margin:18px 8px 0;font-size:12px;line-height:1.6;color:#6B6893;text-align:center">
      Vous recevez cet e-mail car vous avez demandé un essai gratuit sur vorelik.com.<br>
      VORELIK · <a href="https://vorelik.com/" style="color:#6B6893">vorelik.com</a> · <a href="${echapper(lien)}" style="color:#6B6893">Se désinscrire</a>
    </p>
  </div>
</body></html>`;
  const texte = [`Essai gratuit BridgeToLeads — « ${metier} » à ${ville}`, "",
    ...prospects.map((p, i) => `${i + 1}. ${p.nom} — ${p.site} — ${p.telephone || "pas de téléphone"} — ${p.adresse}`
      + ` — ${p.note === null ? "pas de note" : String(p.note).replace(".", ",") + " ★"} (${p.avis} avis)${p.maps ? " — " + p.maps : ""}`),
    "", "Données Google Maps.", "", `Découvrir BridgeToLeads : ${PAGE_BTL}`, "", `Se désinscrire : ${lien}`].join("\n");
  return { sujet: `${n} prospect${n > 1 ? "s" : ""} sans site web : ${metier} à ${ville}`, html, texte };
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

async function ajouterContact({ email, metier, ville, ref, actus }, env) {
  const listes = [Number(env.BREVO_LISTE_ESSAI)];
  if (actus && Number(env.BREVO_LISTE_ACTUS)) listes.push(Number(env.BREVO_LISTE_ACTUS));
  await brevo("/contacts", env, {
    method: "POST",
    body: JSON.stringify({
      email, updateEnabled: true, listIds: listes,
      attributes: { METIER: metier, VILLE: ville, REF: ref, ACTUS_VORELIK: actus },
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

export async function lienDesinscription(email, env, base) {
  return `${base}/desinscription?e=${encodeURIComponent(email)}&s=${await signature(email, env)}`;
}

function pageHtml(titre, texte, statut = 200, bouton = "") {
  return new Response(`<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex"><title>${echapper(titre)} — VORELIK</title></head>
<body style="margin:0;min-height:100vh;display:grid;place-items:center;background:#F6F3FF;font-family:Segoe UI,Helvetica,Arial,sans-serif;color:#1E1B4B">
<main style="max-width:460px;margin:24px;padding:32px 28px;background:#fff;border-radius:20px;box-shadow:0 20px 50px -25px rgba(124,58,237,.45);text-align:center">
<h1 style="margin:0 0 12px;font-size:1.5rem">${echapper(titre)}</h1><p style="margin:0 0 20px;line-height:1.6;color:#4B4870">${echapper(texte)}</p>
${bouton}<a href="https://vorelik.com/" style="color:#7C3AED;font-weight:700">Retour sur vorelik.com</a></main></body></html>`,
  { status: statut, headers: { "Content-Type": "text/html; charset=utf-8" } });
}

async function desinscription(request, url, env) {
  const email = (url.searchParams.get("e") || "").trim().toLowerCase();
  const s = url.searchParams.get("s") || "";
  if (!email || !env.DESINSCRIPTION_SECRET || s !== await signature(email, env)) {
    return pageHtml("Lien non valable", "Ce lien de désinscription est incomplet. Écrivez-nous à support@vorelik.com : nous vous retirerons de nos listes.", 400);
  }
  if (request.method === "GET") {
    return pageHtml("Se désinscrire", `Ne plus recevoir d'e-mails de VORELIK à l'adresse ${email} ?`, 200,
      `<form method="post" style="margin:0 0 20px"><button type="submit" style="font:inherit;font-weight:700;color:#fff;background:#7C3AED;border:0;border-radius:999px;padding:13px 26px;cursor:pointer">Confirmer la désinscription</button></form>`);
  }
  if (request.method !== "POST") return new Response(null, { status: 405 });
  await brevo(`/contacts/${encodeURIComponent(email)}`, env, {
    method: "PUT", body: JSON.stringify({ emailBlacklisted: true }),
  }).catch(async (e) => {
    if (!String(e.message).includes("HTTP 404")) throw e;
    await brevo("/contacts", env, { method: "POST", body: JSON.stringify({ email, emailBlacklisted: true, updateEnabled: true }) });
  });
  return pageHtml("Vous êtes désinscrit", `L'adresse ${email} ne recevra plus d'e-mails de VORELIK.`);
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
      const absents = ["METIER", "VILLE", "REF", "ACTUS_VORELIK"].filter((a) => !noms.has(a));
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
