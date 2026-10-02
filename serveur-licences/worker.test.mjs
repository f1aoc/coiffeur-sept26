// Tests du serveur de licences : node --test serveur-licences/
import assert from "node:assert/strict";
import { beforeEach, test } from "node:test";

import { creerFauxStripe } from "./faux-stripe.mjs";
import worker from "./worker.js";

const CDS = "prod_ChasseurDeSites";
const BTL = "prod_BridgeToLeads";
const ENV = {
  STRIPE_SECRET_KEY: "sk_test_faux",
  LICENCE_SECRET: "secret-de-test-tres-long-0123456789",
  PRODUITS: JSON.stringify({
    [CDS]: { code: "chasseur-de-sites", prefixe: "CDS", limite: 2 },
    [BTL]: { code: "bridgetoleads", prefixe: "BTL" },
  }),
  ORIGINE_SITE: "https://ptabountchikoff.fr",
};
const PC1 = "0123456789abcdef";
const PC2 = "fedcba9876543210";
const PC3 = "00112233445566ff";

let stripe;
beforeEach(() => {
  stripe = creerFauxStripe();
  globalThis.fetch = stripe.fetch;
});

async function appel(chemin, donnees, env = ENV) {
  const init = donnees === undefined ? {} : {
    method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams(donnees).toString(),
  };
  const r = await worker.fetch(new Request(`https://licences.test${chemin}`, init), env);
  return { status: r.status, corps: await r.json(), entetes: r.headers };
}

async function acheter(produit = CDS) {
  const { session, pi } = stripe.payer({ produit });
  const r = await appel(`/cle?session_id=${session}`);
  return { ...r, pi, cle: r.corps.cle };
}

test("la page Merci obtient la clé, rangée dans les métadonnées du paiement", async () => {
  const { status, corps, entetes, pi } = await acheter();
  assert.equal(status, 200);
  assert.match(corps.cle, /^CDS-3Test\d{6}AbCdEf-[0-9A-F]{12}$/);
  assert.equal(corps.produit, "chasseur-de-sites");
  assert.equal(corps.email, "contact@agence-durand.fr");
  assert.equal(stripe.paiements.get(pi).metadata.licence_cle, corps.cle);
  assert.equal(entetes.get("access-control-allow-origin"), "https://ptabountchikoff.fr");
  // Recharger la page redonne la même clé
  const encore = await appel(`/cle?session_id=${[...stripe.sessions.keys()][0]}`);
  assert.equal(encore.corps.cle, corps.cle);
});

test("pas de clé pour une session impayée, inconnue ou d'un autre produit", async () => {
  const impaye = stripe.payer({ produit: CDS, paye: false });
  assert.equal((await appel(`/cle?session_id=${impaye.session}`)).status, 402);
  assert.equal((await appel("/cle?session_id=cs_test_inexistante")).status, 404);
  assert.equal((await appel("/cle?session_id=n'importe quoi")).status, 400);
  const autre = stripe.payer({ produit: "prod_AutreChose" });
  assert.equal((await appel(`/cle?session_id=${autre.session}`)).corps.erreur, "produit_inconnu");
});

test("activation, vérification et limite de 2 ordinateurs", async () => {
  const { cle, pi } = await acheter();
  const a1 = await appel("/activer", { cle, produit: "chasseur-de-sites", machine: PC1 });
  assert.deepEqual(a1.corps, { valide: true, statut: "active", nom: "Agence Durand", email: "contact@agence-durand.fr" });
  assert.equal((await appel("/activer", { cle, produit: "chasseur-de-sites", machine: PC1 })).corps.valide, true); // idempotent
  assert.equal((await appel("/activer", { cle, produit: "chasseur-de-sites", machine: PC2 })).corps.valide, true);
  const a3 = await appel("/activer", { cle, produit: "chasseur-de-sites", machine: PC3 });
  assert.equal(a3.status, 409);
  assert.equal(a3.corps.statut, "limite");
  assert.equal(stripe.paiements.get(pi).metadata.instances, `${PC1},${PC2}`);
  assert.equal((await appel("/verifier", { cle, produit: "chasseur-de-sites", machine: PC1 })).corps.statut, "active");
  assert.equal((await appel("/verifier", { cle, produit: "chasseur-de-sites", machine: PC3 })).corps.statut, "machine_inconnue");
});

test("libérer un ordinateur permet d'en activer un autre", async () => {
  const { cle } = await acheter();
  await appel("/activer", { cle, produit: "chasseur-de-sites", machine: PC1 });
  await appel("/activer", { cle, produit: "chasseur-de-sites", machine: PC2 });
  assert.equal((await appel("/liberer", { cle, produit: "chasseur-de-sites", machine: PC1 })).corps.libere, true);
  assert.equal((await appel("/verifier", { cle, produit: "chasseur-de-sites", machine: PC1 })).corps.statut, "machine_inconnue");
  assert.equal((await appel("/activer", { cle, produit: "chasseur-de-sites", machine: PC3 })).corps.valide, true);
});

test("remboursement : la licence est désactivée à la vérification suivante", async () => {
  const { cle, pi } = await acheter();
  await appel("/activer", { cle, produit: "chasseur-de-sites", machine: PC1 });
  stripe.rembourser(pi);
  assert.deepEqual((await appel("/verifier", { cle, produit: "chasseur-de-sites", machine: PC1 })).corps,
    { valide: false, statut: "desactivee" });
  assert.equal((await appel("/activer", { cle, produit: "chasseur-de-sites", machine: PC2 })).corps.statut, "desactivee");
});

test("contestation (chargeback) : licence désactivée", async () => {
  const { cle, pi } = await acheter();
  await appel("/activer", { cle, produit: "chasseur-de-sites", machine: PC1 });
  stripe.rembourser(pi, { contestation: true });
  assert.equal((await appel("/verifier", { cle, produit: "chasseur-de-sites", machine: PC1 })).corps.statut, "desactivee");
});

test("clé falsifiée, inventée ou d'un autre logiciel refusée", async () => {
  const { cle } = await acheter();
  const falsifiee = cle.slice(0, -1) + (cle.endsWith("A") ? "B" : "A");
  assert.equal((await appel("/activer", { cle: falsifiee, produit: "chasseur-de-sites", machine: PC1 })).corps.statut, "inconnue");
  assert.equal((await appel("/activer", { cle: "CDS-3TestInvente00-000000000000", produit: "chasseur-de-sites", machine: PC1 })).corps.statut, "inconnue");
  assert.equal((await appel("/activer", { cle, produit: "bridgetoleads", machine: PC1 })).corps.statut, "autre_produit");
  const btl = await acheter(BTL);
  assert.match(btl.cle, /^BTL-/);
  assert.equal((await appel("/activer", { cle: btl.cle, produit: "chasseur-de-sites", machine: PC1 })).corps.statut, "autre_produit");
  assert.equal((await appel("/activer", { cle: btl.cle, produit: "bridgetoleads", machine: PC1 })).corps.valide, true);
});

test("la signature dépend du secret : une clé fabriquée sans le secret ne passe pas", async () => {
  const { cle } = await acheter();
  const autreSecret = { ...ENV, LICENCE_SECRET: "un-autre-secret" };
  assert.equal((await appel("/verifier", { cle, produit: "chasseur-de-sites", machine: PC1 }, autreSecret)).corps.statut, "inconnue");
});

test("identifiant d'ordinateur invalide refusé", async () => {
  const { cle } = await acheter();
  assert.equal((await appel("/activer", { cle, produit: "chasseur-de-sites", machine: "pas-un-hash" })).status, 400);
});

test("Stripe en panne : 502, que le logiciel traite comme « hors ligne »", async () => {
  const { cle } = await acheter();
  stripe.etat.panne = true;
  const r = await appel("/verifier", { cle, produit: "chasseur-de-sites", machine: PC1 });
  assert.equal(r.status, 502);
  assert.equal(r.corps.erreur, "stripe_indisponible");
});

test("routes inconnues et préflight CORS", async () => {
  assert.equal((await appel("/autre")).status, 404);
  assert.equal((await appel("/")).corps.ok, true);
  const r = await worker.fetch(new Request("https://licences.test/cle", { method: "OPTIONS" }), ENV);
  assert.equal(r.status, 204);
});
