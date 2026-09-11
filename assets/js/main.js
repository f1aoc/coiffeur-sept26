/* =========================================================================
   L'Hair d'Aujourd'hui — interactions & animations
   Vanilla JS, aucune dépendance. Tout s'éteint proprement si l'utilisateur
   a demandé « moins d'animations » dans son système.
   ========================================================================= */
(function () {
  'use strict';

  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var $ = function (s, c) { return (c || document).querySelector(s); };
  var $$ = function (s, c) { return Array.prototype.slice.call((c || document).querySelectorAll(s)); };
  var clamp = function (v, a, b) { return Math.max(a, Math.min(b, v)); };

  /* ---------------------------------------------------------------- rideau */
  var loader = $('#loader');
  function lift() {
    if (!loader) return;
    loader.classList.add('is-gone');
    setTimeout(function () { loader.remove(); }, 1100);
  }
  if (reduced && loader) { loader.remove(); }
  else {
    window.addEventListener('load', function () { setTimeout(lift, 420); });
    setTimeout(lift, 2600); // filet de sécurité
  }

  /* ------------------------------------------------- découpage des titres */
  function split(el) {
    var out = [];
    Array.prototype.forEach.call(el.childNodes, function (node) {
      if (node.nodeType === 3) {
        node.textContent.split(/(\s+)/).forEach(function (chunk) {
          if (!chunk) return;
          if (/^\s+$/.test(chunk)) { out.push(document.createTextNode(' ')); return; }
          // la ponctuation ne part jamais seule en début de ligne :
          // on la recolle au mot précédent
          var prev = out[out.length - 1];
          if (/^[,.;:!?…»)\]]+$/.test(chunk) && prev && prev.nodeType === 1) {
            prev.firstChild.appendChild(document.createTextNode(chunk));
            return;
          }
          var w = document.createElement('span');
          w.className = 'word';
          var i = document.createElement('span');
          i.className = 'word__in';
          i.textContent = chunk;
          w.appendChild(i);
          out.push(w);
        });
      } else if (node.nodeType === 1) {
        var w2 = document.createElement('span');
        w2.className = 'word';
        var i2 = document.createElement('span');
        i2.className = 'word__in';
        i2.appendChild(node.cloneNode(true));
        w2.appendChild(i2);
        out.push(w2);
      }
    });
    el.innerHTML = '';
    out.forEach(function (n) { el.appendChild(n); });
    $$('.word__in', el).forEach(function (n, i) {
      n.style.transitionDelay = (i * 55) + 'ms';
    });
  }
  if (!reduced) $$('[data-split]').forEach(split);

  /* ------------------------------------------------------- tracé des SVG */
  $$('[data-draw] path').forEach(function (p) {
    try {
      var len = Math.ceil(p.getTotalLength());
      p.style.setProperty('--len', len);
    } catch (e) { /* navigateur sans getTotalLength */ }
  });

  /* --------------------------------------------------- apparition au scroll */
  var revealables = $$('[data-rise],[data-split],[data-draw],.mark');
  if ('IntersectionObserver' in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (!e.isIntersecting) return;
        var el = e.target;
        var d = parseInt(el.getAttribute('data-delay') || '0', 10);
        setTimeout(function () { el.classList.add('is-in'); }, d);
        io.unobserve(el);
      });
    }, { rootMargin: '0px 0px -8% 0px', threshold: 0.08 });
    revealables.forEach(function (el) { io.observe(el); });
  } else {
    revealables.forEach(function (el) { el.classList.add('is-in'); });
  }

  /* ------------------------------------------------------------- compteurs */
  function countUp(el) {
    var target = parseFloat(el.getAttribute('data-count'));
    var dec = parseInt(el.getAttribute('data-decimals') || '0', 10);
    var t0 = null, dur = 1400;
    function step(t) {
      if (!t0) t0 = t;
      var p = clamp((t - t0) / dur, 0, 1);
      var eased = 1 - Math.pow(1 - p, 3);
      el.textContent = (target * eased).toFixed(dec).replace('.', ',');
      if (p < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }
  var counters = $$('[data-count]');
  if (counters.length && !reduced && 'IntersectionObserver' in window) {
    var cio = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (!e.isIntersecting) return;
        countUp(e.target);
        cio.unobserve(e.target);
      });
    }, { threshold: 0.6 });
    counters.forEach(function (el) { cio.observe(el); });
  }

  /* ------------------------------------------------------- barre de progrès */
  var bar = $('#progress i');
  var navwrap = $('.navwrap');
  var lastY = window.scrollY;
  var velocity = 0;

  function onScroll() {
    var y = window.scrollY;
    var h = document.documentElement.scrollHeight - window.innerHeight;
    if (bar) bar.style.transform = 'scaleX(' + (h > 0 ? clamp(y / h, 0, 1) : 0) + ')';

    if (navwrap) {
      navwrap.classList.toggle('is-stuck', y > 24);
      navwrap.classList.toggle('is-hidden', y > 420 && y > lastY + 4 && !menuOpen);
    }
    velocity = y - lastY;
    lastY = y;
  }

  /* ------------------------------------------------------------- parallaxe */
  var parallaxed = $$('[data-parallax]');
  function onFrameParallax() {
    if (reduced) return;
    parallaxed.forEach(function (el) {
      var r = el.getBoundingClientRect();
      if (r.bottom < -200 || r.top > window.innerHeight + 200) return;
      var amount = parseFloat(el.getAttribute('data-parallax')) || 0.1;
      var shift = (window.scrollY - (r.top + window.scrollY)) * amount;
      el.style.transform = 'translate3d(-50%,' + shift.toFixed(1) + 'px,0)';
    });
  }

  /* --------------------------------------------------------- bandeau défilant */
  var track = $('[data-marquee]');
  var mx = 0, mWidth = 0;
  if (track) {
    var original = track.innerHTML;
    track.innerHTML = original + original + original;
    var measureMarquee = function () { mWidth = track.scrollWidth / 3; };
    measureMarquee();
    window.addEventListener('resize', measureMarquee);
  }

  /* ------------------------------------------------ galerie horizontale */
  var galerie = $('#galerie');
  var rail = $('#rail');
  var railTrack = $('#rail-track');
  var pinned = false, pinTop = 0, pinHead = 0, pinDist = 0;

  function setupRail() {
    if (!galerie || !rail || !railTrack) return;
    var wide = window.innerWidth > 860 && !reduced;
    if (!wide) {
      pinned = false;
      galerie.classList.remove('is-pinned');
      galerie.style.height = '';
      railTrack.style.transform = '';
      return;
    }
    galerie.classList.add('is-pinned');
    galerie.style.height = '';
    pinHead = rail.offsetTop;
    pinDist = Math.max(0, railTrack.scrollWidth - window.innerWidth + 48);
    galerie.style.height = (pinHead + window.innerHeight + pinDist) + 'px';
    pinTop = galerie.getBoundingClientRect().top + window.scrollY;
    pinned = true;
  }

  function onFrameRail() {
    if (!pinned) return;
    var p = clamp((window.scrollY - pinTop - pinHead) / (pinDist || 1), 0, 1);
    railTrack.style.transform = 'translate3d(' + (-pinDist * p).toFixed(1) + 'px,0,0)';
  }

  /* ------------------------------------------------------------ boucle rAF */
  var ticking = false;
  function frame() {
    if (track) {
      var speed = reduced ? 0 : 0.55 + clamp(Math.abs(velocity) * 0.06, 0, 5) * (velocity < 0 ? -1 : 1);
      mx -= speed;
      if (mWidth && mx <= -mWidth) mx += mWidth;
      if (mx > 0) mx -= mWidth;
      track.style.transform = 'translate3d(' + mx.toFixed(2) + 'px,0,0)';
    }
    onFrameParallax();
    onFrameRail();
    velocity *= 0.9;
    requestAnimationFrame(frame);
  }

  window.addEventListener('scroll', function () {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(function () { onScroll(); ticking = false; });
  }, { passive: true });

  window.addEventListener('resize', function () { setupRail(); onScroll(); });
  window.addEventListener('load', function () { setupRail(); onScroll(); });
  setupRail();
  onScroll();
  requestAnimationFrame(frame);

  /* ------------------------------------------------------- curseur maison */
  var cursor = $('#cursor');
  if (cursor && !reduced && window.matchMedia('(hover:hover) and (pointer:fine)').matches) {
    var cx = window.innerWidth / 2, cy = window.innerHeight / 2, rx = cx, ry = cy;
    var dot = $('.cursor__dot', cursor), ring = $('.cursor__ring', cursor), label = $('.cursor__label', cursor);
    document.addEventListener('mousemove', function (e) {
      cx = e.clientX; cy = e.clientY;
      cursor.classList.add('is-on');
      dot.style.transform = 'translate(' + cx + 'px,' + cy + 'px) translate(-50%,-50%)';
    });
    (function ringLoop() {
      rx += (cx - rx) * 0.16; ry += (cy - ry) * 0.16;
      ring.style.left = rx + 'px'; ring.style.top = ry + 'px';
      requestAnimationFrame(ringLoop);
    })();
    document.addEventListener('mouseover', function (e) {
      var t = e.target.closest('a,button,[data-tilt],.shot');
      if (!t) { cursor.classList.remove('is-hover', 'is-label'); return; }
      var shot = e.target.closest('.shot');
      if (shot) { label.textContent = 'voir'; cursor.classList.add('is-label'); cursor.classList.remove('is-hover'); }
      else { cursor.classList.add('is-hover'); cursor.classList.remove('is-label'); }
    });
    document.addEventListener('mouseleave', function () { cursor.classList.remove('is-on'); });
  }

  /* ------------------------------------------------------ boutons magnétiques */
  if (!reduced && window.matchMedia('(hover:hover)').matches) {
    $$('[data-magnetic]').forEach(function (el) {
      el.addEventListener('mousemove', function (e) {
        var r = el.getBoundingClientRect();
        var dx = (e.clientX - (r.left + r.width / 2)) * 0.22;
        var dy = (e.clientY - (r.top + r.height / 2)) * 0.3;
        el.style.transform = 'translate(' + dx.toFixed(1) + 'px,' + dy.toFixed(1) + 'px)';
      });
      el.addEventListener('mouseleave', function () { el.style.transform = ''; });
    });

    /* cartes inclinables */
    $$('[data-tilt]').forEach(function (el) {
      el.addEventListener('mousemove', function (e) {
        var r = el.getBoundingClientRect();
        var px = (e.clientX - r.left) / r.width - 0.5;
        var py = (e.clientY - r.top) / r.height - 0.5;
        el.style.transform = 'perspective(900px) rotateX(' + (-py * 5).toFixed(2) + 'deg) rotateY(' + (px * 6).toFixed(2) + 'deg) translateY(-6px)';
      });
      el.addEventListener('mouseleave', function () { el.style.transform = ''; });
    });
  }

  /* ------------------------------------------------------------- accordéon */
  $$('.presta__head').forEach(function (head) {
    head.addEventListener('click', function () {
      var item = head.parentElement;
      var open = item.classList.contains('is-open');
      $$('.presta__item.is-open').forEach(function (o) {
        o.classList.remove('is-open');
        $('.presta__head', o).setAttribute('aria-expanded', 'false');
      });
      if (!open) {
        item.classList.add('is-open');
        head.setAttribute('aria-expanded', 'true');
      }
    });
  });

  /* ------------------------------------------------------------ menu mobile */
  var burger = $('#burger');
  var mobile = $('#nav-mobile');
  var menuOpen = false;
  if (burger && mobile) {
    burger.addEventListener('click', function () {
      menuOpen = !menuOpen;
      burger.setAttribute('aria-expanded', String(menuOpen));
      mobile.hidden = !menuOpen;
    });
    $$('a', mobile).forEach(function (a) {
      a.addEventListener('click', function () {
        menuOpen = false;
        burger.setAttribute('aria-expanded', 'false');
        mobile.hidden = true;
      });
    });
  }

  /* -------------------------------------------------- lien de nav actif */
  var sections = $$('main section[id]');
  if ('IntersectionObserver' in window && sections.length) {
    var nio = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (!e.isIntersecting) return;
        $$('.nav__links a').forEach(function (a) {
          a.classList.toggle('is-active', a.getAttribute('href') === '#' + e.target.id);
        });
      });
    }, { rootMargin: '-45% 0px -50% 0px' });
    sections.forEach(function (s) { nio.observe(s); });
  }

  /* -------------------------------------------- horaires : ouvert / fermé */
  var HORAIRES = { 0: null, 1: null, 2: [9, 19], 3: [9, 19], 4: [9, 19], 5: [9, 19], 6: [9, 18] };
  var JOURS = ['dimanche', 'lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi'];

  function parisNow() {
    var f = new Intl.DateTimeFormat('fr-FR', {
      timeZone: 'Europe/Paris', weekday: 'short', hour: '2-digit', minute: '2-digit', hour12: false
    });
    var parts = {};
    f.formatToParts(new Date()).forEach(function (p) { parts[p.type] = p.value; });
    var map = { dim: 0, lun: 1, mar: 2, mer: 3, jeu: 4, ven: 5, sam: 6 };
    var key = (parts.weekday || '').toLowerCase().replace('.', '').slice(0, 3);
    return {
      day: key in map ? map[key] : new Date().getDay(),
      hour: parseInt(parts.hour, 10) + parseInt(parts.minute, 10) / 60
    };
  }

  var now = parisNow();
  var statut = $('#statut-ouverture');
  if (statut) {
    var today = HORAIRES[now.day];
    if (today && now.hour >= today[0] && now.hour < today[1]) {
      statut.textContent = 'Ouvert aujourd’hui jusqu’à ' + today[1] + 'h';
      statut.classList.add('is-open');
    } else {
      var d = now.day, tries = 0, next = null;
      while (tries < 8) {
        d = (d + 1) % 7; tries++;
        if (HORAIRES[d]) { next = d; break; }
      }
      if (today && now.hour < today[0]) {
        statut.textContent = 'Ouvre aujourd’hui à ' + today[0] + 'h';
      } else if (next !== null) {
        statut.textContent = 'Fermé — réouverture ' + JOURS[next] + ' à ' + HORAIRES[next][0] + 'h';
      }
    }
  }
  var todayRow = $('#hours [data-day="' + now.day + '"]');
  if (todayRow) todayRow.classList.add('is-today');

  var annee = $('#annee');
  if (annee) annee.textContent = new Date().getFullYear();
})();
