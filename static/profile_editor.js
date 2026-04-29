// ══ Phase 08.5: FAQ CRUD + Tabu-Begriffe (2-column UI) ══════════════════════
// profile_editor.js — FAQ-Datenbank (sec-faqs) + Tabu-Begriffe (sec-tabu)
// Loaded after the main inline script in profile_editor.html.
// Relies on: window.PROFILE_ID (already set by inline script)

/* ── Confirm-Delete Modal (C2X) ───────────────────────── */
(function ensureConfirmModal() {
  if (document.getElementById('confirm-delete-modal')) return;
  var el = document.createElement('div');
  el.id = 'confirm-delete-modal';
  el.innerHTML = [
    '<div class="confirm-delete-box">',
    '  <h3>Wirklich löschen?</h3>',
    '  <p id="confirm-delete-label">Dieser Eintrag wird entfernt.</p>',
    '  <div class="confirm-delete-actions">',
    '    <button type="button" class="btn-secondary" id="confirm-delete-cancel">Abbrechen</button>',
    '    <button type="button" class="btn-destructive" id="confirm-delete-ok">Löschen</button>',
    '  </div>',
    '</div>'
  ].join('');
  document.body.appendChild(el);
  document.getElementById('confirm-delete-cancel').addEventListener('click', function () {
    el.classList.remove('active');
    el._callback = null;
  });
  el.addEventListener('click', function (e) {
    if (e.target === el) { el.classList.remove('active'); el._callback = null; }
  });
})();

/**
 * Zeigt einen Modal-Confirm-Dialog.
 * @param {Function} callback  — wird bei Bestätigung aufgerufen
 * @param {string}   label     — optionaler Beschreibungstext (z.B. "Einwand")
 */
function confirmDelete(callback, label) {
  var modal = document.getElementById('confirm-delete-modal');
  var labelEl = document.getElementById('confirm-delete-label');
  if (labelEl && label) {
    labelEl.textContent = label + ' wird entfernt.';
  } else if (labelEl) {
    labelEl.textContent = 'Dieser Eintrag wird entfernt.';
  }
  modal._callback = callback;
  var okBtn = document.getElementById('confirm-delete-ok');
  // Remove previous listener to avoid stacking
  var newOk = okBtn.cloneNode(true);
  okBtn.parentNode.replaceChild(newOk, okBtn);
  newOk.addEventListener('click', function () {
    modal.classList.remove('active');
    if (modal._callback) modal._callback();
    modal._callback = null;
  });
  modal.classList.add('active');
}

(function () {
  'use strict';

  // ── CSRF-Token Helper ─────────────────────────────────────────────────────
  function getCsrfToken() {
    var m = document.querySelector('meta[name="csrf-token"]');
    return m ? m.getAttribute('content') : '';
  }

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

    // ── Phase 08.19.3 D-15: mode toggle state ────────────────────────────
    var modeChk = row.querySelector('.faq-mode-toggle');
    var modeTrack = row.querySelector('.faq-mode-track');
    var modeThumb = row.querySelector('.faq-mode-thumb');
    var modeDesc = row.querySelector('.faq-mode-desc');
    var faqId = row.getAttribute('data-faq-id');
    var isKi = (faq.mode || 'ki_generated') === 'ki_generated';

    function _setModeVisual(ki) {
      if (modeTrack) modeTrack.style.background = ki ? '#00D4AA' : '#888';
      if (modeThumb) modeThumb.style.transform = ki ? 'translateX(18px)' : 'translateX(0)';
      if (modeDesc) modeDesc.textContent = ki
        ? 'KI generiert = KI nutzt deine Antwort als Wissen und formuliert situationsabhängig.'
        : 'Wortwörtlich = KI spielt deine Antwort exakt so aus wenn die Frage erkannt wird.';
    }

    if (modeChk) {
      modeChk.checked = isKi;
      _setModeVisual(isKi);

      // Ghost-toggle guard: disable toggle until FAQ has DB id (prevents PUT on undefined id).
      // Toggle is re-enabled in persistFaq() POST-success handler after data-faq-id is set.
      if (!faqId) {
        modeChk.disabled = true;
        if (modeTrack) modeTrack.style.opacity = '0.5';
      }

      // ── D-16: sofortiges PUT beim Toggle-Change mit optimistic revert ─────
      modeChk.addEventListener('change', function() {
        var currentFaqId = row.getAttribute('data-faq-id');
        if (!currentFaqId) return;  // ghost-toggle guard (belt-and-suspenders)

        // Capture old state BEFORE the optimistic update (the state before this change event)
        var prevChecked = !modeChk.checked;  // old state = inverse of new checked value
        var newMode = modeChk.checked ? 'ki_generated' : 'literal';

        // Optimistic update: apply visual change immediately
        _setModeVisual(modeChk.checked);

        // Disable toggle during fetch to prevent rapid-fire + race conditions
        modeChk.disabled = true;
        if (modeTrack) modeTrack.style.opacity = '0.5';

        function _revertAndNotify() {
          if (!document.body.contains(row)) return;  // DOM guard: row may have been removed
          // Revert checkbox and visual to previous state
          modeChk.checked = prevChecked;
          _setModeVisual(prevChecked);
          // Show toast — use existing toast function if available, else alert as fallback
          var _toastFn = (typeof showToast === 'function') ? showToast
                       : (typeof window.showToast === 'function') ? window.showToast
                       : null;
          if (_toastFn) {
            _toastFn('Speichern fehlgeschlagen — bitte erneut versuchen', 'error');
          } else {
            alert('Speichern fehlgeschlagen — bitte erneut versuchen');
          }
        }

        fetch('/profiles/api/profile/faqs/' + currentFaqId, {
          method: 'PUT',
          credentials: 'same-origin',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken()
          },
          body: JSON.stringify({ mode: newMode })
        }).then(function(r) {
          // Re-enable always (success path)
          modeChk.disabled = false;
          if (modeTrack) modeTrack.style.opacity = '';
          if (!r.ok) {
            console.warn('[FAQ] mode update failed', r.status);
            _revertAndNotify();
          }
        }).catch(function(e) {
          // Re-enable always (error path)
          modeChk.disabled = false;
          if (modeTrack) modeTrack.style.opacity = '';
          console.warn('[FAQ] mode update error', e);
          _revertAndNotify();
        });
      });
    }

    var usedEl = row.querySelector('.faq-used-count');
    if (usedEl) usedEl.textContent = (faq.used_count || 0) + '\u00d7';

    // Accordion toggle
    var hd = row.querySelector('.faq-hd');
    var lbl = row.querySelector('.faq-lbl');
    var chev = row.querySelector('.acc-chevron');
    var fullFrage = (faq.frage_muster || '').trim();
    if (lbl) {
      lbl.textContent = fullFrage || 'Frage';
      lbl.title = fullFrage;        // nativer Browser-Tooltip mit vollem Wortlaut bei Hover
    }
    if (hd) hd.title = '';            // Tooltip auf Header-Container entfernt — praeziser auf .faq-lbl
    if (hd) {
      hd.addEventListener('click', function(e) {
        if (e.target.closest('.faq-delete')) return;
        var body = row.querySelector('.faq-fields');
        if (!body) return;
        var collapsed = body.classList.toggle('collapsed');
        if (chev) chev.textContent = collapsed ? '\u25b8' : '\u25be';
      });
    }

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

    // Header-Preview live aktualisieren (sonst zeigt der eingeklappte Header alten Text bis Reload)
    var lblLive = row.querySelector('.faq-lbl');
    if (lblLive) {
      var liveTxt = (frageEl.value || '').trim();
      lblLive.textContent = liveTxt || 'Frage';
      lblLive.title = liveTxt;
    }

    var pid = getProfileId();
    if (!pid) return;

    if (id) {
      // Update existing row
      fetch('/profiles/api/profile/faqs/' + id, {
        method: 'PUT',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
        body: JSON.stringify(payload),
      })
        .then(function (r) { if (!r.ok) console.warn('[FAQ] update failed', r.status); })
        .catch(function (e) { console.warn('[FAQ] update error', e); });
    } else if (!row.getAttribute('data-faq-creating')) {
      // Create new row — guard against concurrent blur events causing duplicates
      row.setAttribute('data-faq-creating', '1');
      fetch('/profiles/api/profile/' + pid + '/faqs', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
        body: JSON.stringify(payload),
      })
        .then(function (r) { return r.ok ? r.json() : Promise.reject(r.status); })
        .then(function (data) {
          if (data && data.id) {
            row.setAttribute('data-faq-id', String(data.id));
            // Ghost-toggle guard: enable toggle now that DB id exists
            var _tog = row.querySelector('.faq-mode-toggle');
            var _trk = row.querySelector('.faq-mode-track');
            if (_tog) {
              _tog.disabled = false;
              if (_trk) _trk.style.opacity = '';
              // If server returned mode, sync toggle state
              if (data.mode) {
                _tog.checked = data.mode === 'ki_generated';
                // _setModeVisual is scoped to renderFaqRow — re-apply via track/thumb directly
                var _thm = row.querySelector('.faq-mode-thumb');
                var _dsc = row.querySelector('.faq-mode-desc');
                var _isKi = data.mode === 'ki_generated';
                if (_trk) _trk.style.background = _isKi ? '#00D4AA' : '#888';
                if (_thm) _thm.style.transform = _isKi ? 'translateX(18px)' : 'translateX(0)';
                if (_dsc) _dsc.textContent = _isKi
                  ? 'KI generiert = KI nutzt deine Antwort als Wissen und formuliert situationsabhängig.'
                  : 'Wortwörtlich = KI spielt deine Antwort exakt so aus wenn die Frage erkannt wird.';
              }
            }
          }
        })
        .catch(function (e) { console.warn('[FAQ] create failed', e); })
        .finally(function () { row.removeAttribute('data-faq-creating'); });
    }
  }

  function deleteFaq(row) {
    var id = row.getAttribute('data-faq-id');
    if (!id) { row.remove(); return; }
    confirmDelete(function () {
      fetch('/profiles/api/profile/faqs/' + id, {
        method: 'DELETE',
        credentials: 'same-origin',
        headers: { 'X-CSRFToken': getCsrfToken() },
      })
        .then(function (r) {
          if (r.ok) { row.remove(); }
          else { console.warn('[FAQ] delete failed', r.status); }
        })
        .catch(function (e) { console.warn('[FAQ] delete error', e); });
    }, 'FAQ-Eintrag');
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

    // Fix B: show 'Vorschlag: X' placeholder when Begriff matches a default and Alternative is empty
    function applyPlaceholderSuggestion() {
      var currentBegriff = begriffInput.value || '';
      var currentAlt = alternativeInput.value || '';
      if (currentAlt.trim()) {
        // user has own value — keep generic placeholder (not visible anyway)
        alternativeInput.placeholder = 'Alternative (stattdessen nutzen)';
        return;
      }
      var suggestion = findDefaultAlternative(currentBegriff);
      if (suggestion) {
        alternativeInput.placeholder = 'Vorschlag: ' + suggestion;
      } else {
        alternativeInput.placeholder = 'Alternative (stattdessen nutzen)';
      }
    }

    // Apply placeholder immediately on render
    applyPlaceholderSuggestion();

    var delBtn = document.createElement('button');
    delBtn.type = 'button';
    delBtn.className = 'btn-trash';
    delBtn.title = 'L\u00f6schen';
    delBtn.innerHTML = '<svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4h6v2"/></svg>';
    delBtn.addEventListener('click', function () {
      row.remove();
      validateTabuRows();
      syncTabuHidden();
    });

    var hintSpan = document.createElement('span');
    hintSpan.className = 'tabu-hint';
    hintSpan.hidden = true;
    hintSpan.style.cssText = 'font-size:11px;color:#e05c5c;display:block;margin-top:2px;';

    // Wire validation on input (also re-evaluate placeholder suggestion)
    [begriffInput, alternativeInput].forEach(function (el) {
      el.addEventListener('input', function () {
        applyPlaceholderSuggestion();
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
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
      body: JSON.stringify({ tabu_begriffe: pairs }),
    })
      .then(function (r) { return r.ok ? r.json() : Promise.reject(r.status); })
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
