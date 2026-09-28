// Chasseur de sites : glisser-déposer du fichier et agrandissement des captures.
(function () {
  "use strict";

  // Glisser-déposer : le fichier déposé est placé dans le champ, ce qui déclenche l'aperçu (htmx).
  function preparerDepot() {
    var zone = document.getElementById("zone-depot");
    var champ = document.getElementById("fichier");
    if (!zone || !champ) return;
    ["dragenter", "dragover"].forEach(function (evt) {
      zone.addEventListener(evt, function (e) { e.preventDefault(); zone.classList.add("survol"); });
    });
    ["dragleave", "drop"].forEach(function (evt) {
      zone.addEventListener(evt, function (e) { e.preventDefault(); zone.classList.remove("survol"); });
    });
    zone.addEventListener("drop", function (e) {
      if (!e.dataTransfer || !e.dataTransfer.files.length) return;
      champ.files = e.dataTransfer.files;
      champ.dispatchEvent(new Event("change", { bubbles: true }));
    });
    zone.addEventListener("keydown", function (e) {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); champ.click(); }
    });
    zone.tabIndex = 0;
  }

  // Captures : un clic sur une miniature l'ouvre en grand ; Échap ou × pour fermer.
  document.addEventListener("click", function (e) {
    var bouton = e.target.closest("[data-agrandir]");
    var visionneuse = document.getElementById("visionneuse");
    if (!bouton || !visionneuse) return;
    visionneuse.querySelector("img").src = bouton.getAttribute("data-agrandir");
    visionneuse.showModal();
  });
  document.addEventListener("click", function (e) {
    var visionneuse = document.getElementById("visionneuse");
    if (visionneuse && e.target === visionneuse) visionneuse.close();
  });

  // Messages : bouton « Copier » et compteur de caractères (SMS).
  document.addEventListener("click", function (e) {
    var bouton = e.target.closest("[data-copier]");
    if (!bouton) return;
    var zone = document.getElementById(bouton.getAttribute("data-copier"));
    if (!zone) return;
    function confirme() {
      var texte = bouton.textContent;
      bouton.textContent = "Copié ✓";
      setTimeout(function () { bouton.textContent = texte; }, 1500);
    }
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(zone.value).then(confirme);
    } else {
      zone.select();
      document.execCommand("copy");
      confirme();
    }
  });
  document.addEventListener("input", function (e) {
    var compteur = document.querySelector('[data-compteur="' + e.target.id + '"]');
    if (compteur) compteur.textContent = e.target.value.length + " caractères";
  });

  // Résultats : case « tout cocher » pour la génération groupée des rapports.
  document.addEventListener("change", function (e) {
    if (!e.target.matches("#tout-cocher")) return;
    document.querySelectorAll('input[name="ids"]').forEach(function (c) { c.checked = e.target.checked; });
  });

  document.addEventListener("DOMContentLoaded", preparerDepot);
})();
