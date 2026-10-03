/**
 * Imitation minimale de l'API Stripe utilisée par worker.js (tests uniquement, en mémoire).
 * fauxStripe.fetch remplace globalThis.fetch pour les appels à api.stripe.com.
 */

export function creerFauxStripe(cleSecrete = "sk_test_faux") {
  const sessions = new Map();
  const paiements = new Map();
  let compteur = 0;
  // interdits : chemins refusés en 403, comme une clé restreinte à qui il manque une permission
  const etat = { panne: false, appels: [], interdits: [] };

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
      id: session, created: 1790000000 + compteur, success_url: "https://ptabountchikoff.fr/merci.html?session_id={CHECKOUT_SESSION_ID}",
      payment_status: paye ? "paid" : "unpaid", payment_intent: pi,
      customer_details: { name: nom, email },
      line_items: { data: [produit].flat().map((p, i) => ({ price: { id: `price_${compteur}_${i}`, product: p } })) },
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
    if (etat.interdits.some((chemin) => u.pathname.startsWith(chemin))) {
      return Response.json({ error: { message: `The provided key does not have the required permissions for ${u.pathname}` } }, { status: 403 });
    }
    const liste = { "/v1/checkout/sessions": sessions, "/v1/payment_intents": paiements, "/v1/charges": new Map() }[u.pathname];
    if (liste) {
      const limite = Number(u.searchParams.get("limit") || 10);
      return Response.json({ object: "list", data: [...liste.values()].reverse().slice(0, limite) });
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
