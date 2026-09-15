/* L'Hair d'Aujourd'hui — un seul comportement : le nuancier se déploie
   quand il entre à l'écran. Tout le reste du site fonctionne sans JS. */

(function () {
  'use strict';

  // Marque le document : le CSS ne cache les pigments que si JS peut les révéler.
  document.documentElement.classList.add('js');

  var nuancier = document.querySelector('.nuancier');
  if (!nuancier) return;

  var reduit = window.matchMedia('(prefers-reduced-motion: reduce)');

  function reveler() {
    nuancier.classList.add('nuancier--visible');
  }

  if (reduit.matches || !('IntersectionObserver' in window)) {
    reveler();
    return;
  }

  // Décalage progressif d'un pigment à l'autre.
  var pigments = nuancier.querySelectorAll('.pigment__couleur');
  for (var i = 0; i < pigments.length; i++) {
    pigments[i].style.setProperty('--retard', i * 70 + 'ms');
  }

  var observateur = new IntersectionObserver(function (entrees) {
    entrees.forEach(function (entree) {
      if (entree.isIntersecting) {
        reveler();
        observateur.disconnect();
      }
    });
  }, { threshold: 0.2 });

  observateur.observe(nuancier);
})();
