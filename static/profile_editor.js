// ══ Phase 08.5: FAQ CRUD + Tabu-Begriffe (2-column UI) ══════════════════════
// profile_editor.js — FAQ-Datenbank (sec-faqs) + Tabu-Begriffe (sec-tabu)
// Loaded after the main inline script in profile_editor.html.
// Relies on: window.PROFILE_ID (already set by inline script)

(function () {
  'use strict';

  function getProfileId() {
    return window.PROFILE_ID || null;
  }

  // ── FAQs ──────────────────────────────────────────────────────────────────
  var faqsContainer = document.getElementById('profile-faqs-list');
  var faqAddBtn = document.getElementById('btn-faq-add');
  var faqTpl = document.getElementById('tpl-faq-row');

  function renderFaqRow(faq) {
    if (!faqTpl || !faqsContainer) return;
    var frag = faqTpl.content.cloneNode(true);
    var row = frag.querySelector('.faq-row');
    row.setAttribute('data-faq-id', faq.id || '');
    row.querySelector('.faq-frage').value = faq.frage_muster || '';
    row.querySelector('.faq-antwort').value = faq.antwort || '';
    row.querySelector('.faq-kategorie').value = faq.kategorie || 'Sonstiges';
    var usedEl = row.querySelector('.faq-used-count');
    if (usedEl) usedEl.textContent = (faq.used_count || 0) + '\u00d7';

    // Autosave on blur/change
    var fields = ['.faq-frage', '.faq-antwort', '.faq-kategorie'];
    fields.forEach(function (sel) {
      var el = row.querySelector(sel);
      if (el) {
        el.addEventListener('blur', function () { persistFaq(row); });
        el.addEventListener('change', function () { persistFaq(row); });
      }
    });

    var delBtn = row.querySelector('.faq-delete');
    if (delBtn) delBtn.addEventListener('click', function () { deleteFaq(row); });

    faqsContainer.appendChild(frag);
  }

  function loadFaqs() {
    var pid = getProfileId();
    if (!pid || !faqsContainer) return;
    faqsContainer.innerHTML = '';
    fetch('/profiles/api/profile/' + pid + '/faqs', { credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        (data.faqs || []).forEach(renderFaqRow);
      })
      .catch(function (e) { console.warn('[FAQ] load failed', e); });
  }

  function persistFaq(row) {
    var id = row.getAttribute('data-faq-id');
    var frageEl = row.querySelector('.faq-frage');
    var antwortEl = row.querySelector('.faq-antwort');
    var kategorieEl = row.querySelector('.faq-kategorie');
    if (!frageEl || !antwortEl || !kategorieEl) return;

    var payload = {
      frage_muster: frageEl.value.trim(),
      antwort: antwortEl.value.trim(),
      kategorie: kategorieEl.value,
    };
    // Show/hide incomplete hint on the row
    var hint = row.querySelector('.faq-hint');
    if (!hint) {
      hint = document.createElement('span');
      hint.className = 'faq-hint';
      hint.style.cssText = 'font-size:11px;color:#e05c5c;margin-left:6px;';
      row.appendChild(hint);
    }
    // Require both frage and antwort before persisting
    if (!payload.frage_muster || !payload.antwort) {
      hint.textContent = 'Kundenfrage und Antwort ausfüllen';
      return;
    }
    hint.textContent = '';

    var pid = getProfileId();
    if (!pid) return;

    if (id) {
      // Update existing row
      fetch('/profiles/api/profile/faqs/' + id, {
        method: 'PUT',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      }).catch(function (e) { console.warn('[FAQ] update failed', e); });
    } else if (!row.getAttribute('data-faq-creating')) {
      // Create new row — guard against concurrent blur events causing duplicates
      row.setAttribute('data-faq-creating', '1');
      fetch('/profiles/api/profile/' + pid + '/faqs', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
        .then(function (r) { return r.ok ? r.json() : Promise.reject(r.status); })
        .then(function (data) {
          if (data && data.id) row.setAttribute('data-faq-id', String(data.id));
        })
        .catch(function (e) { console.warn('[FAQ] create failed', e); })
        .finally(function () { row.removeAttribute('data-faq-creating'); });
    }
  }

  function deleteFaq(row) {
    var id = row.getAttribute('data-faq-id');
    if (!id) { row.remove(); return; }
    if (!confirm('FAQ wirklich löschen?')) return;
    fetch('/profiles/api/profile/faqs/' + id, {
      method: 'DELETE',
      credentials: 'same-origin',
    })
      .then(function () { row.remove(); })
      .catch(function (e) { console.warn('[FAQ] delete failed', e); });
  }

  if (faqAddBtn) {
    faqAddBtn.addEventListener('click', function () {
      renderFaqRow({ id: '', frage_muster: '', antwort: '', kategorie: 'Sonstiges', used_count: 0 });
    });
  }

  // ── Phase 08.5 Nachbesserung (260424-fo0): 13 Default-Paare (mirror services/profile_migration.py) ──
  var TABU_DEFAULT_PAIRS = [
    { begriff: 'Kosten',      alternative: 'Investition' },
    { begriff: 'Problem',     alternative: 'Herausforderung' },
    { begriff: 'günstig',     alternative: 'effizient' },
    { begriff: 'billig',      alternative: 'preis-attraktiv' },
    { begriff: 'Risiko',      alternative: 'Absicherung' },
    { begriff: 'Schwäche',    alternative: 'Entwicklungspotenzial' },
    { begriff: 'Nachteil',    alternative: 'Unterschied' },
    { begriff: 'verkaufen',   alternative: 'helfen' },
    { begriff: 'müssen',      alternative: 'können' },
    { begriff: 'alt',         alternative: 'etabliert' },
    { begriff: 'kompliziert', alternative: 'strukturiert' },
    { begriff: 'verlieren',   alternative: 'absichern' },
    { begriff: 'Konkurrenz',  alternative: 'Mitbewerber' },
  ];

  // Helper: case-insensitive lookup of a default Alternative by Begriff.
  function findDefaultAlternative(begriff) {
    if (!begriff) return '';
    var needle = begriff.trim().toLowerCase();
    for (var i = 0; i < TABU_DEFAULT_PAIRS.length; i++) {
      if (TABU_DEFAULT_PAIRS[i].begriff.toLowerCase() === needle) {
        return TABU_DEFAULT_PAIRS[i].alternative;
      }
    }
    return '';
  }

  // ── Tabu-Begriffe 2-column UI ─────────────────────────────────────────────
  // Phase 08.5 Korrektur 2: Tag-chip-input replaced by 2-column rows
  // (Begriff + Alternative + Delete). Save button disabled while any row
  // has exactly one field filled (incomplete state).

  var tabuRowsContainer = document.getElementById('tabu-rows');
  var tabuAddBtn = document.getElementById('tabu-add-btn');
  var tabuHidden = document.getElementById('vi_tabu_begriffe');
  var mainSaveBtn = document.getElementById('main-save-btn');

  // ── validateTabuRows: run on every input/change ───────────────────────────
  function validateTabuRows() {
    if (!tabuRowsContainer) return;
    var rows = tabuRowsContainer.querySelectorAll('.tabu-row');
    var hasIncomplete = false;

    rows.forEach(function (row) {
      var begriffEl = row.querySelector('.tabu-begriff');
      var alternativeEl = row.querySelector('.tabu-alternative');
      var hintEl = row.querySelector('.tabu-hint');
      if (!begriffEl || !alternativeEl) return;

      var b = begriffEl.value.trim();
      var a = alternativeEl.value.trim();

      if (hintEl) hintEl.hidden = true;

      if (b && !a) {
        // Begriff filled, alternative missing
        if (hintEl) { hintEl.textContent = 'Alternative fehlt'; hintEl.hidden = false; }
        hasIncomplete = true;
      } else if (!b && a) {
        // Alternative filled, Begriff missing
        if (hintEl) { hintEl.textContent = 'Begriff fehlt'; hintEl.hidden = false; }
        hasIncomplete = true;
      }
      // Both empty → neutral (will be silently ignored on save)
      // Both filled → valid
    });

    // Disable/enable main save button
    if (mainSaveBtn) {
      if (hasIncomplete) {
        mainSaveBtn.disabled = true;
        mainSaveBtn.title = 'Tabu-Zeile unvollständig';
        mainSaveBtn.style.opacity = '0.45';
        mainSaveBtn.style.cursor = 'not-allowed';
      } else {
        mainSaveBtn.disabled = false;
        mainSaveBtn.title = '';
        mainSaveBtn.style.opacity = '';
        mainSaveBtn.style.cursor = '';
      }
    }

    return !hasIncomplete;
  }

  // ── renderTabuRow: render one 2-column row ────────────────────────────────
  function renderTabuRow(pair) {
    if (!tabuRowsContainer) return;
    var row = document.createElement('div');
    row.className = 'tabu-row';
    row.style.cssText = 'display:flex;gap:8px;align-items:flex-start;margin-bottom:6px;';

    var begriffInput = document.createElement('input');
    begriffInput.type = 'text';
    begriffInput.className = 'tabu-begriff fi';
    begriffInput.placeholder = 'Tabu-Begriff';
    begriffInput.value = (pair && pair.begriff) || '';
    begriffInput.maxLength = 80;
    begriffInput.style.cssText = 'flex:1;min-width:0;';

    var alternativeInput = document.createElement('input');
    alternativeInput.type = 'text';
    alternativeInput.className = 'tabu-alternative fi';
    alternativeInput.placeholder = 'Alternative (stattdessen nutzen)';
    alternativeInput.value = (pair && pair.alternative) || '';
    alternativeInput.maxLength = 80;
    alternativeInput.style.cssText = 'flex:1;min-width:0;';

    var delBtn = document.createElement('button');
    delBtn.type = 'button';
    delBtn.className = 'tabu-del-btn';
    delBtn.textContent = '\u00d7';
    delBtn.style.cssText = 'background:transparent;border:none;color:#9CA3AF;cursor:pointer;font-size:18px;padding:4px 6px;line-height:1;flex-shrink:0;';
    delBtn.addEventListener('click', function () {
      row.remove();
      validateTabuRows();
      syncTabuHidden();
    });

    var hintSpan = document.createElement('span');
    hintSpan.className = 'tabu-hint';
    hintSpan.hidden = true;
    hintSpan.style.cssText = 'font-size:11px;color:#e05c5c;display:block;margin-top:2px;';

    // Wire validation on input
    [begriffInput, alternativeInput].forEach(function (el) {
      el.addEventListener('input', function () {
        validateTabuRows();
        syncTabuHidden();
      });
    });

    row.appendChild(begriffInput);
    row.appendChild(alternativeInput);
    row.appendChild(delBtn);
    row.appendChild(hintSpan);
    tabuRowsContainer.appendChild(row);
  }

  // ── syncTabuHidden: keep hidden input in sync for buildAndSubmit ──────────
  function syncTabuHidden() {
    if (!tabuHidden || !tabuRowsContainer) return;
    var rows = tabuRowsContainer.querySelectorAll('.tabu-row');
    var pairs = [];
    rows.forEach(function (row) {
      var b = (row.querySelector('.tabu-begriff') || {}).value || '';
      var a = (row.querySelector('.tabu-alternative') || {}).value || '';
      b = b.trim(); a = a.trim();
      if (b || a) {
        pairs.push({ begriff: b, alternative: a });
      }
    });
    tabuHidden.value = JSON.stringify(pairs);
  }

  // ── mergeDefaultPairs: dedupe-merge 13 defaults into existing in-memory rows ──
  // Stats: added (new row), completed (empty alt filled with default), already (begriff matched and alt already had user value)
  function mergeDefaultPairs() {
    if (!tabuRowsContainer) return;
    var rows = tabuRowsContainer.querySelectorAll('.tabu-row');

    // Build index of existing begriffe (case-insensitive) → row element
    var existing = {};
    rows.forEach(function (row) {
      var bEl = row.querySelector('.tabu-begriff');
      if (!bEl) return;
      var key = (bEl.value || '').trim().toLowerCase();
      if (key) existing[key] = row;
    });

    var added = 0, completed = 0, already = 0;

    TABU_DEFAULT_PAIRS.forEach(function (pair) {
      var key = pair.begriff.toLowerCase();
      var row = existing[key];
      if (row) {
        var altEl = row.querySelector('.tabu-alternative');
        if (!altEl) return;
        var currentAlt = (altEl.value || '').trim();
        if (!currentAlt && pair.alternative) {
          altEl.value = pair.alternative;
          completed++;
        } else {
          already++;
        }
      } else {
        renderTabuRow({ begriff: pair.begriff, alternative: pair.alternative });
        added++;
      }
    });

    syncTabuHidden();
    validateTabuRows();

    // Feedback message
    var fb = document.getElementById('tabu-seed-feedback');
    if (fb) {
      var parts = [];
      if (added)     parts.push(added + ' hinzugefügt');
      if (completed) parts.push(completed + ' ergänzt');
      if (already)   parts.push(already + ' schon vollständig');
      fb.textContent = parts.length ? parts.join(', ') : '0 Änderungen';
      // Clear after 6s
      if (fb._fbTimer) clearTimeout(fb._fbTimer);
      fb._fbTimer = setTimeout(function () { fb.textContent = ''; }, 6000);
    }
  }

  // ── saveTabuToServer: POST list-of-objects to API ─────────────────────────
  function saveTabuToServer() {
    var pid = getProfileId();
    if (!pid || !tabuRowsContainer) return;
    var rows = tabuRowsContainer.querySelectorAll('.tabu-row');
    var pairs = [];
    rows.forEach(function (row) {
      var b = (row.querySelector('.tabu-begriff') || {}).value || '';
      var a = (row.querySelector('.tabu-alternative') || {}).value || '';
      b = b.trim(); a = a.trim();
      if (b && a) {
        pairs.push({ begriff: b, alternative: a });
      }
      // completely empty rows are silently ignored (no error)
    });
    fetch('/profiles/api/profile/' + pid + '/tabu', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tabu_begriffe: pairs }),
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.ignored && data.ignored.length > 0) {
          console.warn('[Tabu] ' + data.ignored.length + ' unvollständige Zeile(n) ignoriert');
        }
      })
      .catch(function (e) { console.warn('[Tabu] save failed', e); });
  }

  // ── loadTabu: seed from PROFILE_DATEN (already migrated by server) ────────
  function loadTabu() {
    if (!tabuRowsContainer) return;
    tabuRowsContainer.innerHTML = '';
    var pairs = [];
    try {
      if (
        window.PROFILE_DATEN &&
        window.PROFILE_DATEN.basis &&
        Array.isArray(window.PROFILE_DATEN.basis.tabu_begriffe)
      ) {
        pairs = window.PROFILE_DATEN.basis.tabu_begriffe;
      } else if (tabuHidden && tabuHidden.value) {
        var parsed = JSON.parse(tabuHidden.value);
        if (Array.isArray(parsed)) pairs = parsed;
      }
    } catch (_) {
      pairs = [];
    }
    pairs.forEach(function (p) { renderTabuRow(p); });
    syncTabuHidden();
    validateTabuRows();
  }

  // ── tabu-add-btn click ────────────────────────────────────────────────────
  if (tabuAddBtn) {
    tabuAddBtn.addEventListener('click', function () {
      renderTabuRow({ begriff: '', alternative: '' });
      // New empty row → save disabled (incomplete, both empty → neutral,
      // but if user adds without filling → will be ignored on save)
      validateTabuRows();
      syncTabuHidden();
    });
  }

  // ── tabu-seed-btn click ───────────────────────────────────────────────────
  var tabuSeedBtn = document.getElementById('tabu-seed-btn');
  if (tabuSeedBtn) {
    tabuSeedBtn.addEventListener('click', function () {
      mergeDefaultPairs();
    });
  }

  // ── Override buildAndSubmit to also POST tabu before form save ────────────
  // Hook into window.buildAndSubmit (defined in profile_editor.html inline script)
  // by wrapping it after DOMContentLoaded.
  function wrapBuildAndSubmit() {
    var originalBuildAndSubmit = window.buildAndSubmit;
    if (typeof originalBuildAndSubmit !== 'function') return;
    window.buildAndSubmit = function () {
      if (!validateTabuRows()) return; // blocked by incomplete rows
      syncTabuHidden();
      originalBuildAndSubmit();
    };
  }

  // ── Init on DOMContentLoaded or immediately if already loaded ─────────────
  function init() {
    loadFaqs();
    loadTabu();
    wrapBuildAndSubmit();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
