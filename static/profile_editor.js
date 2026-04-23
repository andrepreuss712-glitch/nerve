// ══ Phase 08.5: FAQ CRUD + Tabu-Begriffe ═══════════════════════════════════
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
    // Require both frage and antwort before persisting
    if (!payload.frage_muster || !payload.antwort) return;

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
    } else {
      // Create new row
      fetch('/profiles/api/profile/' + pid + '/faqs', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data && data.id) row.setAttribute('data-faq-id', String(data.id));
        })
        .catch(function (e) { console.warn('[FAQ] create failed', e); });
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

  // ── Tabu-Begriffe ─────────────────────────────────────────────────────────
  var tabuContainer = document.getElementById('tabu-tags-container');
  var tabuInput = document.getElementById('tabu-tag-input');
  var tabuHidden = document.getElementById('vi_tabu_begriffe');
  var tabuList = [];

  function renderTabuChip(term) {
    if (!tabuContainer) return;
    var chip = document.createElement('span');
    chip.className = 'tag-chip';
    var textNode = document.createTextNode(term);
    chip.appendChild(textNode);
    var x = document.createElement('button');
    x.type = 'button';
    x.className = 'tag-rm';
    x.textContent = '\u00d7';
    x.setAttribute('aria-label', 'Entfernen');
    x.addEventListener('click', function () {
      tabuList = tabuList.filter(function (t) { return t !== term; });
      chip.remove();
      saveTabu();
    });
    chip.appendChild(x);
    tabuContainer.appendChild(chip);
  }

  function saveTabu() {
    var pid = getProfileId();
    if (!pid) return;
    if (tabuHidden) tabuHidden.value = JSON.stringify(tabuList);
    fetch('/profiles/api/profile/' + pid + '/tabu', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tabu_begriffe: tabuList }),
    }).catch(function (e) { console.warn('[Tabu] save failed', e); });
  }

  function loadTabu() {
    // Read from window.PROFILE_DATEN.basis.tabu_begriffe if available
    try {
      if (
        window.PROFILE_DATEN &&
        window.PROFILE_DATEN.basis &&
        Array.isArray(window.PROFILE_DATEN.basis.tabu_begriffe)
      ) {
        tabuList = window.PROFILE_DATEN.basis.tabu_begriffe.slice();
      } else if (tabuHidden && tabuHidden.value) {
        var parsed = JSON.parse(tabuHidden.value);
        if (Array.isArray(parsed)) tabuList = parsed;
      }
    } catch (_) {
      tabuList = [];
    }
    if (tabuContainer) {
      tabuContainer.innerHTML = '';
      tabuList.forEach(renderTabuChip);
    }
    if (tabuHidden) tabuHidden.value = JSON.stringify(tabuList);
  }

  if (tabuInput) {
    tabuInput.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.keyCode === 13) {
        e.preventDefault();
        var term = (tabuInput.value || '').trim();
        if (!term || term.length > 80) { tabuInput.value = ''; return; }
        var lower = term.toLowerCase();
        if (tabuList.some(function (t) { return t.toLowerCase() === lower; })) {
          tabuInput.value = '';
          return;
        }
        if (tabuList.length >= 50) { alert('Max 50 Tabu-Begriffe'); return; }
        tabuList.push(term);
        renderTabuChip(term);
        tabuInput.value = '';
        saveTabu();
      }
    });
  }

  // ── Init on DOMContentLoaded or immediately if already loaded ─────────────
  function init() {
    loadFaqs();
    loadTabu();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
