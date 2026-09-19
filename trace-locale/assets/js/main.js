/* =========================================================
   Trace Locale — script unique, sans dépendance
   1. Configuration     2. Jeu de démonstration
   3. Tableau filtrable 4. Thème  5. Formulaire liste d'attente
   ========================================================= */

(function () {
  "use strict";

  /* ---------------------------------------------------------
     1. CONFIGURATION — les deux seules valeurs à renseigner
     --------------------------------------------------------- */
  var CONFIG = {
    // URL du service qui reçoit les inscriptions (Formspree, Tally, Brevo,
    // Google Forms, ou votre propre endpoint). Laissée vide, le formulaire
    // bascule sur un email pré-rempli vers CONFIG.contact : aucune
    // inscription n'est perdue, mais la collecte n'est pas automatique.
    endpoint: "",

    // Adresse de repli et de contact affichée aux inscrits.
    contact: "contact@tracelocale.fr"
  };

  /* ---------------------------------------------------------
     2. JEU DE DÉMONSTRATION
     Lignes illustratives, figées au bulletin du 19/09/2026.
     Les noms de domaine sont volontairement tronqués : `stem`
     est la partie visible, `mask` le nombre de caractères
     masqués. Aucune de ces lignes ne désigne un établissement
     réel — elles montrent la forme de la donnée, pas la donnée.
     --------------------------------------------------------- */
  var DEMO = [
    { stem: "garage-des-t",  mask: 6, tld: "fr",  cat: "Garage automobile",     ville: "Avignon",     dep: "84", avis: 118, note: 4.6, ref: 37,  exp: "24/08/2026", libre: "23/09/2026", j: 4  },
    { stem: "boulangerie-l", mask: 7, tld: "com", cat: "Boulangerie-pâtisserie", ville: "Nantes",      dep: "44", avis: 264, note: 4.8, ref: 61,  exp: "31/08/2026", libre: "30/09/2026", j: 11 },
    { stem: "plomberie-r",   mask: 8, tld: "fr",  cat: "Plombier",               ville: "Lille",       dep: "59", avis: 73,  note: 4.4, ref: 22,  exp: "02/09/2026", libre: "02/10/2026", j: 13 },
    { stem: "le-comptoir-d", mask: 5, tld: "com", cat: "Restaurant",             ville: "Bordeaux",    dep: "33", avis: 512, note: 4.5, ref: 94,  exp: "26/08/2026", libre: "25/09/2026", j: 6  },
    { stem: "immo-p",        mask: 9, tld: "fr",  cat: "Agence immobilière",     ville: "Lyon",        dep: "69", avis: 89,  note: 4.2, ref: 48,  exp: "06/09/2026", libre: "06/10/2026", j: 17 },
    { stem: "osteo-c",       mask: 7, tld: "fr",  cat: "Cabinet d'ostéopathie",  ville: "Toulouse",    dep: "31", avis: 141, note: 4.9, ref: 18,  exp: "25/08/2026", libre: "24/09/2026", j: 5  },
    { stem: "coiffure-a",    mask: 6, tld: "com", cat: "Salon de coiffure",      ville: "Rennes",      dep: "35", avis: 96,  note: 4.7, ref: 15,  exp: "09/09/2026", libre: "09/10/2026", j: 20 },
    { stem: "menuiserie-s",  mask: 8, tld: "fr",  cat: "Menuisier",              ville: "Strasbourg",  dep: "67", avis: 54,  note: 4.8, ref: 29,  exp: "29/08/2026", libre: "28/09/2026", j: 9  },
    { stem: "autoecole-m",   mask: 6, tld: "fr",  cat: "Auto-école",             ville: "Marseille",   dep: "13", avis: 187, note: 3.9, ref: 26,  exp: "23/08/2026", libre: "22/09/2026", j: 3  },
    { stem: "fleurs-d",      mask: 7, tld: "com", cat: "Fleuriste",              ville: "Nice",        dep: "06", avis: 78,  note: 4.6, ref: 12,  exp: "11/09/2026", libre: "11/10/2026", j: 22 },
    { stem: "studio-ph",     mask: 9, tld: "fr",  cat: "Photographe",            ville: "Paris",       dep: "75", avis: 203, note: 4.9, ref: 133, exp: "27/08/2026", libre: "26/09/2026", j: 7  },
    { stem: "pizzeria-v",    mask: 6, tld: "com", cat: "Pizzeria",               ville: "Montpellier", dep: "34", avis: 341, note: 4.3, ref: 40,  exp: "04/09/2026", libre: "04/10/2026", j: 15 },
    { stem: "elec-b",        mask: 8, tld: "fr",  cat: "Électricien",            ville: "Brest",       dep: "29", avis: 62,  note: 4.5, ref: 19,  exp: "30/08/2026", libre: "29/09/2026", j: 10 },
    { stem: "cave-des-c",    mask: 7, tld: "fr",  cat: "Caviste",                ville: "Dijon",       dep: "21", avis: 129, note: 4.7, ref: 33,  exp: "07/09/2026", libre: "07/10/2026", j: 18 }
  ];

  /* ---------------------------------------------------------
     3. TABLEAU FILTRABLE
     --------------------------------------------------------- */

  var $ = function (sel) { return document.querySelector(sel); };

  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  function dots(n) { return new Array(n + 1).join("•"); }

  /* Classe d'urgence : une semaine ou moins = fenêtre chaude. */
  function urgency(j) {
    if (j <= 7) return "j--hot";
    if (j >= 15) return "j--ok";
    return "";
  }

  function rowHTML(d) {
    return "" +
      '<tr>' +
        '<td class="dom">' + esc(d.stem) + '<b>' + dots(d.mask) + '</b>.' + esc(d.tld) + '</td>' +
        '<td><span class="biz">' + esc(d.cat) + '</span></td>' +
        '<td class="city">' + esc(d.ville) + ' <i>(' + esc(d.dep) + ')</i></td>' +
        '<td class="num">' + d.avis + '</td>' +
        '<td class="num">' + d.note.toFixed(1).replace(".", ",") + '</td>' +
        '<td class="num">' + d.ref + '</td>' +
        '<td><span class="when"><time>' + esc(d.libre) + '</time>' +
          '<span class="j ' + urgency(d.j) + '">J−' + d.j + '</span></span></td>' +
      '</tr>';
  }

  function initTable() {
    var tbody = $("#rows");
    if (!tbody) return;

    var q = $("#q"), cat = $("#cat"), tld = $("#tld"), tri = $("#tri");
    var count = $("#count"), empty = $("#empty");

    /* Remplit les listes déroulantes depuis les données, pas à la main. */
    function fill(select, values, label) {
      values.sort(function (a, b) { return a.localeCompare(b, "fr"); });
      values.forEach(function (v) {
        var o = document.createElement("option");
        o.value = v;
        o.textContent = label ? label(v) : v;
        select.appendChild(o);
      });
    }
    var cats = [], tlds = [];
    DEMO.forEach(function (d) {
      if (cats.indexOf(d.cat) === -1) cats.push(d.cat);
      if (tlds.indexOf(d.tld) === -1) tlds.push(d.tld);
    });
    fill(cat, cats);
    fill(tld, tlds, function (t) { return "." + t; });

    var sorters = {
      drop: function (a, b) { return a.j - b.j; },
      avis: function (a, b) { return b.avis - a.avis; },
      ref:  function (a, b) { return b.ref - a.ref; },
      note: function (a, b) { return b.note - a.note; }
    };

    function render() {
      var term = q.value.trim().toLowerCase();
      var list = DEMO.filter(function (d) {
        if (cat.value && d.cat !== cat.value) return false;
        if (tld.value && d.tld !== tld.value) return false;
        if (!term) return true;
        return (d.cat + " " + d.ville + " " + d.dep + " " + d.tld).toLowerCase().indexOf(term) !== -1;
      });

      list.sort(sorters[tri.value] || sorters.drop);

      tbody.innerHTML = list.map(rowHTML).join("");
      empty.hidden = list.length !== 0;
      count.textContent = list.length === DEMO.length
        ? DEMO.length + " domaines au bulletin"
        : list.length + " sur " + DEMO.length + " domaines";
    }

    [q, cat, tld, tri].forEach(function (el) {
      el.addEventListener("input", render);
      el.addEventListener("change", render);
    });
    render();
  }

  /* ---------------------------------------------------------
     4. THÈME
     Respecte le système par défaut ; le bouton force un choix,
     mémorisé localement quand le navigateur l'autorise.
     --------------------------------------------------------- */
  function initTheme() {
    var btn = $("#themebtn");
    if (!btn) return;
    var label = btn.querySelector(".themebtn__label");
    var root = document.documentElement;

    function store(v) {
      try { v ? localStorage.setItem("tl-theme", v) : localStorage.removeItem("tl-theme"); }
      catch (e) { /* mode privé ou stockage bloqué : sans conséquence */ }
    }
    function read() {
      try { return localStorage.getItem("tl-theme"); } catch (e) { return null; }
    }
    function isDark() {
      var set = root.getAttribute("data-theme");
      if (set) return set === "dark";
      return window.matchMedia("(prefers-color-scheme: dark)").matches;
    }
    function paint() {
      var dark = isDark();
      btn.setAttribute("aria-pressed", String(dark));
      label.textContent = dark ? "Thème clair" : "Thème sombre";
    }

    var saved = read();
    if (saved === "dark" || saved === "light") root.setAttribute("data-theme", saved);
    paint();

    btn.addEventListener("click", function () {
      var next = isDark() ? "light" : "dark";
      root.setAttribute("data-theme", next);
      store(next);
      paint();
    });
  }

  /* ---------------------------------------------------------
     5. FORMULAIRE LISTE D'ATTENTE
     --------------------------------------------------------- */
  function initForm() {
    var form = $("#form");
    if (!form) return;
    var status = $("#status"), submit = $("#submit");

    function say(msg, kind) {
      status.textContent = msg;
      status.className = "form__status" + (kind ? " is-" + kind : "");
    }

    form.addEventListener("submit", function (e) {
      e.preventDefault();

      if (!form.checkValidity()) {
        say("Prénom, email et consentement sont nécessaires pour vous inscrire.", "err");
        var bad = form.querySelector(":invalid");
        if (bad) bad.focus();
        return;
      }

      var data = {};
      new FormData(form).forEach(function (v, k) { data[k] = v; });
      data.source = "liste-attente";

      /* Sans endpoint configuré : email pré-rempli, rien n'est perdu. */
      if (!CONFIG.endpoint) {
        var corps = Object.keys(data).map(function (k) { return k + " : " + data[k]; }).join("\n");
        window.location.href = "mailto:" + CONFIG.contact +
          "?subject=" + encodeURIComponent("Liste d'attente Trace Locale") +
          "&body=" + encodeURIComponent(corps);
        say("Votre logiciel de messagerie s'ouvre avec le message pré-rempli. Envoyez-le pour valider l'inscription.");
        return;
      }

      submit.disabled = true;
      say("Envoi…");

      fetch(CONFIG.endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json", "Accept": "application/json" },
        body: JSON.stringify(data)
      }).then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        form.reset();
        say("C'est noté. Vous recevrez un email dès que votre département est couvert.", "ok");
      }).catch(function () {
        say("L'envoi a échoué. Écrivez-nous à " + CONFIG.contact + ", on vous inscrit à la main.", "err");
      }).then(function () {
        submit.disabled = false;
      });
    });
  }

  initTable();
  initTheme();
  initForm();
})();
