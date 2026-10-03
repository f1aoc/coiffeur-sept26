// Serveur de licences local, avec un faux Stripe en mémoire : tests de bout en bout des logiciels.
//   node serveur-licences/serveur-local.mjs [port]   → affiche « PRET <port> »
// Routes de test : GET /_test/payer?produit=prod_… → { session, pi } ; GET /_test/rembourser?pi=…
import http from "node:http";

import { creerFauxStripe } from "./faux-stripe.mjs";
import worker from "./worker.js";

export const ENV_TEST = {
  STRIPE_SECRET_KEY: "sk_test_faux",
  LICENCE_SECRET: "secret-de-test-tres-long-0123456789",
  PRODUITS: JSON.stringify({
    prod_ChasseurDeSites: { code: "chasseur-de-sites", prefixe: "CDS", limite: 2 },
    prod_BridgeToLeads: { code: "bridgetoleads", prefixe: "BTL", limite: 2 },
  }),
  ORIGINE_SITE: process.env.ORIGINE_SITE || "",
};

const stripe = creerFauxStripe(ENV_TEST.STRIPE_SECRET_KEY);
globalThis.fetch = stripe.fetch;

const serveur = http.createServer(async (req, res) => {
  const url = new URL(req.url, "http://localhost");
  const envoyer = (status, corps) => {
    res.writeHead(status, { "Content-Type": "application/json" });
    res.end(JSON.stringify(corps));
  };
  if (url.pathname === "/_test/payer") return envoyer(200, stripe.payer({ produit: url.searchParams.get("produit") }));
  if (url.pathname === "/_test/rembourser") {
    stripe.rembourser(url.searchParams.get("pi"));
    return envoyer(200, { ok: true });
  }
  let corps = "";
  for await (const morceau of req) corps += morceau;
  const requete = new Request(`http://localhost${req.url}`, {
    method: req.method,
    headers: { "Content-Type": req.headers["content-type"] || "", Origin: req.headers.origin || "" },
    body: ["GET", "HEAD"].includes(req.method) ? undefined : corps,
  });
  const reponse = await worker.fetch(requete, ENV_TEST);
  res.writeHead(reponse.status, Object.fromEntries(reponse.headers));
  res.end(await reponse.text());
});

serveur.listen(Number(process.argv[2] || 0), "127.0.0.1", () => {
  console.log(`PRET ${serveur.address().port}`);
});
