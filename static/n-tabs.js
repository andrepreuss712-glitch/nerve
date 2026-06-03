// Phase 08.23.2.D.UX.2 — n-tabs: reusable declarative tabs (deep-link + last-tab + ARIA + n-tab:activated event + hashchange)
// Vanilla-JS IIFE, kein Modul-System, kein Build-Step (Stack-Constraint: Flask + Vanilla JS).
// Deklarativer Tab-Container via data-Attributen. Jedes [data-tabs]-Element auf der Seite wird
// initialisiert (mehrfach-instanzfaehig). Bei JEDER Aktivierung (Klick, Hash, localStorage,
// Erst-Tab UND Initial-Aktivierung) feuert ein CustomEvent 'n-tab:activated' mit
// detail {tabId, container} — Konsumenten (Plan 03 session_detail, NACHTRAG) lazy-loaden darauf.
// ASCII-only Identifier (CLAUDE.md): Tab-Targets uebersicht/transkript, Event-Name n-tab:activated.
(function () {
  'use strict';

  var LS_PREFIX = 'n-tabs-last-';

  // Eindeutiger localStorage-Key pro Seite/Container.
  function pageIdFor(container) {
    return container.getAttribute('data-tabs-id') || location.pathname;
  }

  // Aktuell aktiver Tab-Target eines Containers (oder null).
  function activeTabId(container) {
    var btn = container.querySelector('.n-tab-btn[data-tab-target][aria-selected="true"]');
    return btn ? btn.getAttribute('data-tab-target') : null;
  }

  // Liste gueltiger Tab-Targets eines Containers.
  function targetsOf(container) {
    var out = [];
    var btns = container.querySelectorAll('.n-tab-btn[data-tab-target]');
    for (var i = 0; i < btns.length; i++) {
      out.push(btns[i].getAttribute('data-tab-target'));
    }
    return out;
  }

  // Kern-Aktivierung. Setzt ARIA + n-tab-btn--active + Panel-hidden-Toggle und feuert
  // AM ENDE jeder Aktivierung n-tab:activated (DUX2-03) — auf JEDEM Aktivierungs-Pfad.
  function activate(container, tabId) {
    var btns = container.querySelectorAll('.n-tab-btn[data-tab-target]');
    var panels = container.querySelectorAll('.n-tab-panel');
    var i;

    // Reset: alle Buttons deselektieren, alle Panels verstecken.
    for (i = 0; i < btns.length; i++) {
      btns[i].setAttribute('aria-selected', 'false');
      btns[i].classList.remove('n-tab-btn--active');
    }
    for (i = 0; i < panels.length; i++) {
      panels[i].hidden = true;
    }

    // Ziel aktivieren.
    for (i = 0; i < btns.length; i++) {
      if (btns[i].getAttribute('data-tab-target') === tabId) {
        btns[i].setAttribute('aria-selected', 'true');
        btns[i].classList.add('n-tab-btn--active');
      }
    }
    for (i = 0; i < panels.length; i++) {
      if (panels[i].id === tabId) {
        panels[i].hidden = false;
      }
    }

    // DUX2-03: bei JEDER Aktivierung feuern — Plan 03 haengt fire-once-Lazy-Load daran.
    container.dispatchEvent(new CustomEvent('n-tab:activated', {
      bubbles: true,
      detail: { tabId: tabId, container: container }
    }));
  }

  // Klick-Handler: aktivieren + Hash (replaceState, kein History-Spam) + last-tab merken.
  function onTabClick(container, tabId) {
    activate(container, tabId);
    try {
      history.replaceState(null, '', '#' + tabId);
    } catch (e) { /* file:// o.ae. — nicht blockierend */ }
    try {
      localStorage.setItem(LS_PREFIX + pageIdFor(container), tabId);
    } catch (e) { /* private mode / quota — nicht blockierend */ }
  }

  // Initial-Aktivierung. Prioritaet (R-03): URL-Hash > localStorage > erster Tab.
  // Laeuft ueber activate() -> feuert n-tab:activated (wichtig fuer Deep-Link-Lazy-Load Plan 03).
  function initialActivate(container) {
    var targets = targetsOf(container);
    if (!targets.length) return;

    var hash = (location.hash || '').replace(/^#/, '');
    if (hash && targets.indexOf(hash) !== -1) {
      activate(container, hash);
      return;
    }

    var stored = null;
    try {
      stored = localStorage.getItem(LS_PREFIX + pageIdFor(container));
    } catch (e) { stored = null; }
    if (stored && targets.indexOf(stored) !== -1) {
      activate(container, stored);
      return;
    }

    activate(container, targets[0]);
  }

  function initContainer(container) {
    var btns = container.querySelectorAll('.n-tab-btn[data-tab-target]');
    var panels = container.querySelectorAll('.n-tab-panel');
    // Defensiv: ohne Buttons oder Panels nichts tun (kein throw).
    if (!btns.length || !panels.length) return;

    for (var i = 0; i < btns.length; i++) {
      (function (btn) {
        btn.addEventListener('click', function () {
          onTabClick(container, btn.getAttribute('data-tab-target'));
        });
      })(btns[i]);
    }

    // Optionale Pfeiltasten-Navigation (nice-to-have, nicht blockierend).
    var bar = container.querySelector('[role="tablist"]') || container;
    bar.addEventListener('keydown', function (ev) {
      if (ev.key !== 'ArrowLeft' && ev.key !== 'ArrowRight') return;
      var targets = targetsOf(container);
      var cur = activeTabId(container);
      var idx = targets.indexOf(cur);
      if (idx === -1) return;
      var next = ev.key === 'ArrowRight'
        ? (idx + 1) % targets.length
        : (idx - 1 + targets.length) % targets.length;
      onTabClick(container, targets[next]);
      var nextBtn = container.querySelector('.n-tab-btn[data-tab-target="' + targets[next] + '"]');
      if (nextBtn) nextBtn.focus();
      ev.preventDefault();
    });

    initialActivate(container);
  }

  // hashchange-Listener (DUX2-03): In-Page-Navigation zu #<tabId> ohne Reload.
  // Loop-Schutz: der eigene replaceState('#'+tabId) aus onTabClick loest hashchange aus —
  // deshalb nur agieren wenn der neue Hash NICHT bereits der aktive Tab dieses Containers ist.
  function onHashChange() {
    var hash = (location.hash || '').replace(/^#/, '');
    if (!hash) return;
    var containers = document.querySelectorAll('[data-tabs]');
    for (var i = 0; i < containers.length; i++) {
      var c = containers[i];
      if (targetsOf(c).indexOf(hash) === -1) continue;   // Hash ist kein Target dieses Containers
      if (activeTabId(c) === hash) continue;              // schon aktiv -> Loop-Schutz no-op
      activate(c, hash);
    }
  }

  function init() {
    var containers = document.querySelectorAll('[data-tabs]');
    for (var i = 0; i < containers.length; i++) {
      initContainer(containers[i]);
    }
    window.addEventListener('hashchange', onHashChange);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
