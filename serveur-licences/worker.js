/**
 * Serveur de licences ptabountchikoff (Cloudflare Worker) — BridgeToLeads, Chasseur de sites et les suivants.
 *
 * Stripe sert de base de données : la clé de licence et les ordinateurs activés sont rangés dans les
 * « metadata » du paiement (PaymentIntent). Aucun autre stockage, aucun webhook.
 *
 *   GET  /cle?session_id=cs_…   page « Merci » après paiement → { cle, produit, nom, email }
 *   GET  /diagnostic            contrôle de la configuration (variables, clé Stripe, derniers produits payés)
 *   POST /activer   cle, produit, machine   → { valide, statut, nom, email }
 *   POST /verifier  cle, produit, machine   → { valide, statut }
 *   POST /liberer   cle, produit, machine   → { libere }
 *
 * Statuts : active · desactivee (remboursé ou contesté) · limite · machine_inconnue · inconnue · autre_produit.
 *
 * Variables (Cloudflare → Worker → Settings → Variables and Secrets) :
 *   STRIPE_SECRET_KEY  secret : clé Stripe restreinte (voir README)
 *   LICENCE_SECRET     secret : longue chaîne aléatoire qui signe les clés (ne jamais la changer ensuite)
 *   PRODUITS           texte JSON : {"prod_…": {"code": "chasseur-de-sites", "prefixe": "CDS", "limite": 2}, …}
 *   ORIGINE_SITE       texte : adresse de votre site (ex. https://ptabountchikoff.fr), pour la page Merci ;
 *                      plusieurs adresses possibles, séparées par des virgules
 *
 * Erreur de configuration (variable absente, clé Stripe refusée) : réponse 500 { erreur, detail } qui dit
 * quoi corriger. Les logiciels traitent toute réponse 5xx comme « hors ligne » : les clients ne sont pas bloqués.
 */

const STRIPE = "https://api.stripe.com/v1";
const LIMITE_DEFAUT = 2;
const MACHINE = /^[0-9a-f]{16}$/;

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const cors = {
      "Access-Control-Allow-Origin": origineAutorisee(env, request.headers.get("Origin")),
      Vary: "Origin",
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
    };
    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: cors });
    try {
      let reponse;
      if (request.method === "GET" && url.pathname === "/cle") {
        reponse = await cle(url.searchParams.get("session_id") || "", env);
      } else if (request.method === "POST" && ["/activer", "/verifier", "/liberer"].includes(url.pathname)) {
        reponse = await licence(url.pathname.slice(1), await lireCorps(request), env);
      } else if (request.method === "GET" && url.pathname === "/diagnostic") {
        reponse = await diagnostic(env);
      } else if (url.pathname === "/") {
        reponse = [200, { service: "licences ptabountchikoff", ok: true }];
      } else {
        reponse = [404, { erreur: "introuvable" }];
      }
      return json(reponse[0], reponse[1], cors);
    } catch (e) {
      if (e instanceof ErreurConfig) return json(500, { erreur: e.code, detail: e.detail }, cors);
      // Stripe injoignable ou en panne : le logiciel le traite comme « hors ligne » (délai de tolérance).
      return json(502, { erreur: "stripe_indisponible" }, cors);
    }
  },
};

// --- Configuration -----------------------------------------------------------------------------------

class ErreurConfig extends Error {
  constructor(code, detail) {
    super(`${code} : ${detail}`);
    this.code = code;
    this.detail = detail;
  }
}

/** Sans espaces, sans « / » final, en minuscules : « https://Site.fr/ » et « https://site.fr » sont la même adresse. */
function normaliserOrigine(texte) {
  return String(texte || "").trim().replace(/\/+$/, "").toLowerCase();
}

function origines(env) {
  return String(env.ORIGINE_SITE || "").split(",").map(normaliserOrigine).filter(Boolean);
}

function origineAutorisee(env, origine) {
  const liste = origines(env);
  if (!liste.length || liste.includes("*")) return "*";
  return liste.includes(normaliserOrigine(origine)) ? origine : liste[0];
}

function exigerConfig(env) {
  if (!env.STRIPE_SECRET_KEY) throw new ErreurConfig("config_stripe_secret_key", "variable STRIPE_SECRET_KEY absente");
  if (!env.LICENCE_SECRET) throw new ErreurConfig("config_licence_secret", "variable LICENCE_SECRET absente");
  if (!Object.keys(produits(env)).length) {
    throw new ErreurConfig("config_produits", "variable PRODUITS absente ou JSON invalide");
  }
}

// --- Stripe -------------------------------------------------------------------------------------------

async function stripe(env, methode, chemin, params = null) {
  const options = { method: methode, headers: { Authorization: `Bearer ${env.STRIPE_SECRET_KEY}` } };
  if (params) {
    options.headers["Content-Type"] = "application/x-www-form-urlencoded";
    options.body = new URLSearchParams(params).toString();
  }
  const r = await fetch(STRIPE + chemin, options);
  if (r.status >= 500) throw new Error(`Stripe HTTP ${r.status}`);
  const corps = await r.json();
  // 401 : clé invalide ; 403 : permission manquante (le message de Stripe la nomme).
  if (r.status === 401 || r.status === 403) {
    throw new ErreurConfig("cle_stripe_refusee", corps.error?.message || `Stripe HTTP ${r.status}`);
  }
  return { status: r.status, corps };
}

function produits(env) {
  try {
    return JSON.parse(env.PRODUITS || "{}");
  } catch {
    return {};
  }
}

// --- Clés : PREFIXE-<identifiant du paiement>-<signature> ----------------------------------------------

async function signature(env, code, pi) {
  const cle = await crypto.subtle.importKey(
    "raw", new TextEncoder().encode(env.LICENCE_SECRET), { name: "HMAC", hash: "SHA-256" }, false, ["sign"],
  );
  const brut = new Uint8Array(await crypto.subtle.sign("HMAC", cle, new TextEncoder().encode(`${code}:${pi}`)));
  return [...brut.slice(0, 6)].map((o) => o.toString(16).padStart(2, "0")).join("").toUpperCase();
}

async function fabriquerCle(env, conf, pi) {
  return `${conf.prefixe}-${pi.replace(/^pi_/, "")}-${await signature(env, conf.code, pi)}`;
}

/** Retrouve le paiement et la configuration produit d'une clé ; null si la clé est fausse. */
async function lireCle(env, texte) {
  const morceaux = String(texte || "").trim().split("-");
  if (morceaux.length !== 3 || !/^[A-Za-z0-9]{8,64}$/.test(morceaux[1])) return null;
  const [prefixe, id, sig] = morceaux;
  const conf = Object.values(produits(env)).find((p) => p.prefixe === prefixe.toUpperCase());
  if (!conf) return null;
  const pi = `pi_${id}`;
  return (await signature(env, conf.code, pi)) === sig.toUpperCase() ? { conf, pi } : null;
}

// --- Page « Merci » : la clé du paiement qui vient d'avoir lieu ----------------------------------------

async function cle(sessionId, env) {
  if (!/^cs_[A-Za-z0-9_]{10,200}$/.test(sessionId)) {
    return [400, { erreur: "session_invalide", detail: "adresse de redirection Stripe sans ?session_id={CHECKOUT_SESSION_ID}" }];
  }
  exigerConfig(env);
  const s = await stripe(env, "GET", `/checkout/sessions/${sessionId}?expand[]=line_items`);
  if (s.status === 404) {
    const mode = sessionId.startsWith("cs_test_") ? "test" : "réel";
    return [404, { erreur: "session_inconnue", detail: `paiement en mode ${mode} : la clé Stripe du serveur doit être du même mode et du même compte` }];
  }
  const session = s.corps;
  if (session.payment_status !== "paid" || !session.payment_intent) return [402, { erreur: "non_payee" }];
  const prix = session.line_items?.data?.[0]?.price;
  const idProduit = typeof prix?.product === "string" ? prix.product : prix?.product?.id;
  const conf = produits(env)[idProduit];
  if (!conf) return [400, { erreur: "produit_inconnu", detail: `${idProduit || "?"} absent de la variable PRODUITS` }];
  const pi = typeof session.payment_intent === "string" ? session.payment_intent : session.payment_intent.id;
  const cleLicence = await fabriquerCle(env, conf, pi);
  // Visible dans le tableau de bord Stripe (paiement → métadonnées), pour retrouver la clé d'un client.
  await stripe(env, "POST", `/payment_intents/${pi}`, { "metadata[licence_cle]": cleLicence, "metadata[produit]": conf.code });
  return [200, {
    cle: cleLicence, produit: conf.code,
    nom: session.customer_details?.name || "", email: session.customer_details?.email || "",
  }];
}

// --- Activation, vérification, libération --------------------------------------------------------------

async function lireCorps(request) {
  const type = request.headers.get("Content-Type") || "";
  if (type.includes("application/json")) return await request.json().catch(() => ({}));
  return Object.fromEntries(new URLSearchParams(await request.text()));
}

async function licence(action, d, env) {
  exigerConfig(env);
  const trouve = await lireCle(env, d.cle);
  if (!trouve) return [404, { valide: false, statut: "inconnue" }];
  const { conf, pi } = trouve;
  if (d.produit && d.produit !== conf.code) return [403, { valide: false, statut: "autre_produit" }];
  const machine = String(d.machine || "").toLowerCase().slice(0, 16);
  if (!MACHINE.test(machine)) return [400, { valide: false, statut: "machine_invalide" }];

  const p = await stripe(env, "GET", `/payment_intents/${pi}?expand[]=latest_charge`);
  if (p.status === 404) return [404, { valide: false, statut: "inconnue" }];
  const paiement = p.corps;
  const charge = paiement.latest_charge && typeof paiement.latest_charge === "object" ? paiement.latest_charge : {};
  const instances = String(paiement.metadata?.instances || "").split(",").filter((x) => MACHINE.test(x));
  const client = { nom: charge.billing_details?.name || "", email: charge.billing_details?.email || "" };
  const enregistrer = (liste) => stripe(env, "POST", `/payment_intents/${pi}`, { "metadata[instances]": liste.join(",") });

  if (action === "liberer") {
    if (instances.includes(machine)) await enregistrer(instances.filter((x) => x !== machine));
    return [200, { libere: true }];
  }
  // Remboursement total ou contestation (chargeback) : licence désactivée.
  if (paiement.status !== "succeeded" || charge.refunded === true || charge.disputed === true) {
    return [200, { valide: false, statut: "desactivee" }];
  }
  if (action === "activer") {
    if (!instances.includes(machine)) {
      if (instances.length >= (conf.limite || LIMITE_DEFAUT)) return [409, { valide: false, statut: "limite" }];
      await enregistrer([...instances, machine]);
    }
    return [200, { valide: true, statut: "active", ...client }];
  }
  if (!instances.includes(machine)) return [200, { valide: false, statut: "machine_inconnue" }];
  return [200, { valide: true, statut: "active", ...client }];
}

// --- Diagnostic : ce qu'il faut corriger, sans rien révéler de secret ------------------------------------

async function diagnostic(env) {
  const cleStripe = String(env.STRIPE_SECRET_KEY || "");
  const liste = produits(env);
  const rapport = {
    STRIPE_SECRET_KEY: !cleStripe ? "ABSENTE"
      : /^(rk|sk)_test_/.test(cleStripe) ? "présente (mode test)"
      : /^(rk|sk)_live_/.test(cleStripe) ? "présente (mode réel)"
      : "INVALIDE : doit commencer par rk_test_ ou rk_live_",
    LICENCE_SECRET: !env.LICENCE_SECRET ? "ABSENTE"
      : String(env.LICENCE_SECRET).length < 20 ? "TROP COURTE (40 caractères conseillés)" : "présente",
    PRODUITS: Object.keys(liste).length
      ? Object.entries(liste).map(([id, p]) => `${id} → ${p.code} (${p.prefixe})`)
      : "ABSENTE ou JSON INVALIDE",
    ORIGINE_SITE: origines(env).length ? origines(env) : "non renseignée (toutes les adresses acceptées)",
  };
  if (!cleStripe) return [200, rapport];
  // Les 5 derniers paiements par lien Stripe : leur produit est-il reconnu ? (ni nom, ni e-mail, ni identifiant de session)
  const essais = { "Checkout Sessions (Read)": "/checkout/sessions?limit=5&expand[]=data.line_items", "Charges (Read)": "/charges?limit=1", "PaymentIntents": "/payment_intents?limit=1" };
  rapport.stripe = {};
  let sessions = [];
  for (const [nom, chemin] of Object.entries(essais)) {
    try {
      const r = await stripe(env, "GET", chemin);
      rapport.stripe[nom] = "ok";
      if (nom.startsWith("Checkout")) sessions = r.corps.data || [];
    } catch (e) {
      rapport.stripe[nom] = e instanceof ErreurConfig ? `REFUSÉ : ${e.detail}` : "Stripe injoignable";
    }
  }
  rapport.derniers_paiements = sessions.map((s) => {
    const prix = s.line_items?.data?.[0]?.price;
    const id = typeof prix?.product === "string" ? prix.product : prix?.product?.id;
    return {
      date: s.created ? new Date(s.created * 1000).toISOString().slice(0, 16).replace("T", " ") : "",
      payee: s.payment_status === "paid",
      produit: id || "?",
      reconnu: liste[id] ? liste[id].code : "NON : ajoutez ce prod_… dans PRODUITS",
      redirection: redirection(s.success_url),
    };
  });
  return [200, rapport];
}

/** Page vers laquelle Stripe renvoie le client, sans la partie après « ? » (elle peut contenir le numéro de session). */
function redirection(adresse) {
  if (!adresse) return "AUCUNE : Stripe affiche sa propre page de confirmation (réglage After payment du lien)";
  const page = adresse.split("?")[0];
  const avecSession = adresse.includes("{CHECKOUT_SESSION_ID}") || /session_id=cs_/.test(adresse);
  return avecSession ? `${page} (session_id ok)` : `${page} SANS ?session_id={CHECKOUT_SESSION_ID}`;
}

function json(status, corps, entetes) {
  return new Response(JSON.stringify(corps), {
    status, headers: { ...entetes, "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" },
  });
}
