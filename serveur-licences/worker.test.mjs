// Tests du serveur de licences : node --test serveur-licences/worker.test.mjs
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
  assert.equal(stripe.paiements.get(pi).metadata["instances_chasseur-de-sites"], `${PC1},${PC2}`);
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

test("erreurs de configuration : la page Merci reçoit la cause exacte", async () => {
  const { session } = stripe.payer({ produit: CDS });
  const sansCle = await appel(`/cle?session_id=${session}`, undefined, { ...ENV, STRIPE_SECRET_KEY: "" });
  assert.equal(sansCle.status, 500);
  assert.equal(sansCle.corps.erreur, "config_stripe_secret_key");
  assert.equal((await appel(`/cle?session_id=${session}`, undefined, { ...ENV, PRODUITS: "{pas du json" })).corps.erreur, "config_produits");
  const mauvaiseCle = await appel(`/cle?session_id=${session}`, undefined, { ...ENV, STRIPE_SECRET_KEY: "rk_test_autre" });
  assert.equal(mauvaiseCle.status, 500);
  assert.equal(mauvaiseCle.corps.erreur, "cle_stripe_refusee");
  stripe.etat.interdits.push("/v1/checkout/sessions");
  const permission = await appel(`/cle?session_id=${session}`);
  assert.equal(permission.corps.erreur, "cle_stripe_refusee");
  assert.match(permission.corps.detail, /required permissions/);
  // Pour les logiciels, une erreur de configuration reste un 5xx : « hors ligne », jamais « licence désactivée ».
  const { cle } = await acheter();
  assert.equal((await appel("/verifier", { cle, produit: "chasseur-de-sites", machine: PC1 }, { ...ENV, STRIPE_SECRET_KEY: "" })).status, 500);
});

test("produit inconnu et session absente : le détail dit quoi corriger", async () => {
  const autre = stripe.payer({ produit: "prod_AutreChose" });
  assert.match((await appel(`/cle?session_id=${autre.session}`)).corps.detail, /prod_AutreChose/);
  assert.match((await appel("/cle?session_id=cs_test_inexistante0")).corps.detail, /mode test/);
  assert.match((await appel("/cle?session_id=")).corps.detail, /CHECKOUT_SESSION_ID/);
});

test("CORS : plusieurs adresses, « / » final et majuscules tolérés", async () => {
  const env = { ...ENV, ORIGINE_SITE: "https://Ptabountchikoff.fr/, https://www.ptabountchikoff.fr" };
  const depuis = async (origine) => (await worker.fetch(new Request("https://licences.test/", { headers: { Origin: origine } }), env))
    .headers.get("access-control-allow-origin");
  assert.equal(await depuis("https://ptabountchikoff.fr"), "https://ptabountchikoff.fr");
  assert.equal(await depuis("https://www.ptabountchikoff.fr"), "https://www.ptabountchikoff.fr");
  assert.equal(await depuis("https://pirate.example"), "https://ptabountchikoff.fr");
  const ouvert = await worker.fetch(new Request("https://licences.test/", { headers: { Origin: "https://x.fr" } }), { ...ENV, ORIGINE_SITE: "" });
  assert.equal(ouvert.headers.get("access-control-allow-origin"), "*");
});

test("diagnostic : variables, permissions Stripe et produits des derniers paiements, sans secret", async () => {
  stripe.payer({ produit: CDS });
  const inconnu = stripe.payer({ produit: "prod_Oublie" });
  stripe.sessions.get(inconnu.session).success_url = "https://ptabountchikoff.fr/merci.html";
  stripe.etat.interdits.push("/v1/charges");
  const { status, corps } = await appel("/diagnostic");
  assert.equal(status, 200);
  assert.equal(corps.STRIPE_SECRET_KEY, "présente (mode test)");
  assert.equal(corps.LICENCE_SECRET, "présente");
  assert.equal(corps.PRODUITS.length, 2);
  assert.equal(corps.stripe["Checkout Sessions (Read)"], "ok");
  assert.match(corps.stripe["Charges (Read)"], /^REFUSÉ/);
  assert.equal(corps.derniers_paiements[0].produit, "prod_Oublie");
  assert.match(corps.derniers_paiements[0].reconnu, /^NON/);
  assert.match(corps.derniers_paiements[0].redirection, /SANS \?session_id/);
  assert.equal(corps.derniers_paiements[1].reconnu, "chasseur-de-sites");
  assert.match(corps.derniers_paiements[1].redirection, /session_id ok/);
  const texte = JSON.stringify(corps);
  for (const secret of [ENV.STRIPE_SECRET_KEY, ENV.LICENCE_SECRET, "cs_test_", "contact@"]) assert.ok(!texte.includes(secret), secret);
});

test("PRODUITS accepté en type JSON (objet) ou avec des guillemets typographiques", async () => {
  for (const PRODUITS of [JSON.parse(ENV.PRODUITS), ENV.PRODUITS.replaceAll('"', "”")]) {
    const { session } = stripe.payer({ produit: BTL });
    const r = await appel(`/cle?session_id=${session}`, undefined, { ...ENV, PRODUITS });
    assert.equal(r.status, 200);
    assert.match(r.corps.cle, /^BTL-/);
  }
});

test("achat groupé des deux logiciels : une clé par logiciel, 2 ordinateurs chacun", async () => {
  const { session, pi } = stripe.payer({ produit: [CDS, BTL] });
  const { status, corps } = await appel(`/cle?session_id=${session}`);
  assert.equal(status, 200);
  assert.deepEqual(corps.licences.map((l) => l.produit), ["chasseur-de-sites", "bridgetoleads"]);
  const [cds, btl] = corps.licences.map((l) => l.cle);
  assert.match(cds, /^CDS-/);
  assert.match(btl, /^BTL-/);
  assert.equal(corps.cle, cds); // anciennes pages Merci : la première clé
  assert.equal(stripe.paiements.get(pi).metadata.licence_cle, `${cds} , ${btl}`);
  // Limites séparées : 2 PC pour Chasseur de sites ET 2 PC pour BridgeToLeads
  for (const machine of [PC1, PC2]) {
    assert.equal((await appel("/activer", { cle: cds, produit: "chasseur-de-sites", machine })).corps.valide, true);
    assert.equal((await appel("/activer", { cle: btl, produit: "bridgetoleads", machine })).corps.valide, true);
  }
  assert.equal((await appel("/activer", { cle: btl, produit: "bridgetoleads", machine: PC3 })).corps.statut, "limite");
  // Une clé ne vaut que pour son logiciel
  assert.equal((await appel("/activer", { cle: cds, produit: "bridgetoleads", machine: PC1 })).corps.statut, "autre_produit");
  // Remboursement partiel d'un seul logiciel : blocage manuel via la métadonnée « bloquer »
  stripe.paiements.get(pi).metadata.bloquer = "bridgetoleads";
  assert.equal((await appel("/verifier", { cle: btl, produit: "bridgetoleads", machine: PC1 })).corps.statut, "desactivee");
  assert.equal((await appel("/verifier", { cle: cds, produit: "chasseur-de-sites", machine: PC1 })).corps.statut, "active");
  // Remboursement total : les deux désactivées
  stripe.rembourser(pi);
  assert.equal((await appel("/verifier", { cle: cds, produit: "chasseur-de-sites", machine: PC1 })).corps.statut, "desactivee");
});

test("clés émises avant les achats groupés : leurs ordinateurs déjà activés restent reconnus", async () => {
  const { cle, pi } = await acheter();
  Object.assign(stripe.paiements.get(pi).metadata, { instances: PC1, produit: "chasseur-de-sites" });
  assert.equal((await appel("/verifier", { cle, produit: "chasseur-de-sites", machine: PC1 })).corps.statut, "active");
});

test("un produit inconnu dans le panier n'empêche pas la clé du logiciel reconnu", async () => {
  const { session } = stripe.payer({ produit: ["prod_Goodies", BTL] });
  const { corps } = await appel(`/cle?session_id=${session}`);
  assert.deepEqual(corps.licences.map((l) => l.produit), ["bridgetoleads"]);
});
