/**
 * Imitation minimale de l'API Stripe utilisée par worker.js (tests uniquement, en mémoire).
 * fauxStripe.fetch remplace globalThis.fetch pour les appels à api.stripe.com.
 */

export function creerFauxStripe(cleSecrete = "sk_test_faux") {
  const sessions = new Map();
  const paiements = new Map();
  let compteur = 0;
  const etat = { panne: false, appels: [] };

  function payer({ produit, nom = "Agence Durand", email = "contact@agence-durand.fr", paye = true } = {}) {
    compteur += 1;
    const pi = `pi_3Test${String(compteur).padStart(6, "0")}AbCdEf`;
    const session = `cs_test_${String(compteur).padStart(6, "0")}XyZ`;
    paiements.set(pi, {
      id: pi, object: "payment_intent", status: paye ? "succeeded" : "requires_payment_method", metadata: {},
      latest_charge: { id: `ch_${compteur}`, refunded: false, disputed: false, amount: 7900, amount_refunded: 0,
        billing_details: { name: nom, email } },
    });
    sessions.set(session, {
      id: session, payment_status: paye ? "paid" : "unpaid", payment_intent: pi,
      customer_details: { name: nom, email },
      line_items: { data: [{ price: { id: `price_${compteur}`, product: produit } }] },
    });
    return { session, pi };
  }

  function rembourser(pi, { contestation = false } = {}) {
    const c = paiements.get(pi).latest_charge;
    if (contestation) c.disputed = true;
    else Object.assign(c, { refunded: true, amount_refunded: c.amount });
  }

  async function fetchStripe(url, options = {}) {
    const u = new URL(url);
    etat.appels.push(`${options.method || "GET"} ${u.pathname}`);
    if (etat.panne) return new Response("{}", { status: 503 });
    if ((options.headers?.Authorization || "") !== `Bearer ${cleSecrete}`) {
      return Response.json({ error: { message: "Invalid API Key" } }, { status: 401 });
    }
    let m;
    if ((m = u.pathname.match(/^\/v1\/checkout\/sessions\/([^/]+)$/))) {
      const s = sessions.get(m[1]);
      return s ? Response.json(s) : Response.json({ error: { message: "No such session" } }, { status: 404 });
    }
    if ((m = u.pathname.match(/^\/v1\/payment_intents\/([^/]+)$/))) {
      const p = paiements.get(m[1]);
      if (!p) return Response.json({ error: { message: "No such payment_intent" } }, { status: 404 });
      if ((options.method || "GET") === "POST") {
        for (const [k, v] of new URLSearchParams(options.body)) {
          const cle = k.match(/^metadata\[(.+)\]$/);
          if (cle) p.metadata[cle[1]] = v;
        }
      }
      return Response.json(p);
    }
    return Response.json({ error: { message: "Unrecognized request URL" } }, { status: 404 });
  }

  return { payer, rembourser, fetch: fetchStripe, paiements, sessions, etat };
}
