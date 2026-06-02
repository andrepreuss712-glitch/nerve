// ── NERVE PiP Launcher ─────────────────────────────────────────────────────
// Self-contained IIFE. No dependency on app.js.
// Exposes window.NerveLauncher = { open, close, isActive }
(function () {
  'use strict';

  // ── CSRF-Token Helper ─────────────────────────────────────────────────────
  function getCsrfToken() {
    var m = document.querySelector('meta[name="csrf-token"]');
    return m ? m.getAttribute('content') : '';
  }

  // ── sanitizeErrorMsg: Defense-in-Depth — filtert Python-Tracebacks aus Fehlermeldungen ──
  function sanitizeErrorMsg(msg) {
    if (!msg) return 'Fehler aufgetreten.';
    if (msg.includes('Traceback') || msg.includes('File "') || msg.includes('  File ')) {
      return 'Interner Fehler. Bitte Seite neu laden.';
    }
    return msg;
  }

  // ── lastSessionAnrede: persisted across calls via localStorage (D-10) ─────
  var _lastSessionAnradeInit = null;
  try { _lastSessionAnradeInit = localStorage.getItem('nerve_last_anrede') || null; } catch (_) {}

  // ── State ──────────────────────────────────────────────────────────────────
  var state = {
    step: 1,              // 1=mode, 2=precall-option, 3=precall-form, 4=precall-result, 45=vorwissen, 5=skript, 6=live
    mode: null,           // 'cold_call' | 'meeting'
    lastSessionAnrede: _lastSessionAnradeInit,
    vorwissenLevel: null, // D-05: null | 'niedrig' | 'mittel' | 'hoch'
    profiles: [],
    activeProfileId: null,
    profileDaten: {},
    precallVerfuegbar: false,
    precallBriefing: null,
    precallFormData: null,  // saved form values for "back" navigation
    skripte: [],
    openerItems: [],
    selectedSkriptId: null,
    selectedOpenerId: null,
    selectedErlaubnisId: null,  // Andre-Decision: 1 Auswahl pro Reiter, eigene Variable
    selectedPitchId: null,      // Andre-Decision: 1 Auswahl pro Reiter, eigene Variable
    activeTab: null,            // D-06: 'opener' | 'erlaubnis' | 'pitch' | 'skript'; null → Default 'opener'
    socket: null,
    micStream: null,
    audioCtx: null,
    workletNode: null,
    micStarted: false,
    pipWindow: null,
    timerInterval: null,
    sessionSeconds: 0,
    lastConvId: null,
    pipTabLocked: null,
    // Phase 06: dual-slot streaming state
    pipSlots: [
      { streaming: false, text: '', result: null, contextKey: null },
      { streaming: false, text: '', result: null, contextKey: null }
    ],
    consentDone: false,
    teleprompterBlocks: [],
    teleprompterActiveIdx: -1,
    teleprompterManualOverride: false,
    teleprompterOverrideTimer: null,
    // D-16: Mic-Indikator state
    micAnalyser: null,
    micLevelRafId: null,
    micMuted: false,
    // Phase 08.20.3: Modus-B Briefing Tab state
    briefingTabExpandedAtStreamStart: false, // guard for PiP tab auto-collapse (D-05)
    _personalizedSkriptText: null,           // KI result buffer for renderStep4c
    _personalizeAbortController: null,       // AbortController for renderStep4b cancel
    // Phase 08.23.2.C: gatekeeper toggle — mirrors server default (init_session_state)
    contactCategory: 'gatekeeper'
  };

  // ── Helpers ────────────────────────────────────────────────────────────────
  function escHtml(str) {
    return String(str || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  // Simple markdown to HTML (handles ##, **, -, no external lib needed)
  function mdToHtml(md) {
    return String(md || '')
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/^## (.+)$/gm, '<h2>$1</h2>')
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/^- (.+)$/gm, '<li>$1</li>')
      .replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>')
      .replace(/\n{2,}/g, '<br>')
      .replace(/\n/g, ' ');
  }

  // Resolve element in PiP window first, fall back to main document
  function pipEl(id) {
    if (state.pipWindow && !state.pipWindow.closed) {
      return state.pipWindow.document.getElementById(id) || document.getElementById(id);
    }
    return document.getElementById(id);
  }

  function modal() { return document.getElementById('launcherModal'); }
  function content() { return document.getElementById('launcherContent'); }

  // ── Modal Management ───────────────────────────────────────────────────────
  function open() {
    var m = modal();
    if (!m) return;
    // Reset to step 1 if not mid-call
    if (!state.micStarted) {
      state.step = 1;
      state.mode = null;
      state.precallBriefing = null;
      state.precallFormData = null;
    }
    m.classList.add('open');
    // Wire close button
    var closeBtn = document.getElementById('launcherClose');
    if (closeBtn) closeBtn.onclick = close;
    // Close on backdrop click
    m.onclick = function (e) { if (e.target === m) close(); };

    // Fetch init data then render
    fetch('/api/launcher/init', {
      headers: { 'X-CSRFToken': getCsrfToken() }
    })
      .then(function (r) {
        if (!r.ok) throw new Error('init failed: ' + r.status);
        return r.json();
      })
      .then(function (data) {
        state.profiles = data.profiles || [];
        state.activeProfileId = data.active_profile_id || null;
        state.profileDaten = data.profile_daten || {};
        state.precallVerfuegbar = !!data.precall_verfuegbar;
        state.skripte = data.skripte || [];
        state.openerItems = data.opener || [];
        renderStep();
      })
      .catch(function () {
        var c = content();
        if (c) c.innerHTML = '<div style="color:#f87171;text-align:center;padding:20px">Fehler beim Laden. Bitte Seite neu laden.</div>';
      });
  }

  function close() {
    var m = modal();
    if (m) m.classList.remove('open');
  }

  // ── Step Renderer ──────────────────────────────────────────────────────────
  function renderStep() {
    // Phase 08.20.3: string pseudo-steps — switch() === only matches numbers
    if (state.step === '4b') { renderStep4b(); return; }
    if (state.step === '4c') { renderStep4c(); return; }
    switch (state.step) {
      case 1: renderStep1(); break;
      case 2: renderStep2(); break;
      case 3: renderStep3(); break;
      case 4: renderStep4(); break;
      case 5: renderStep5(); break;
      default: renderStep1();
    }
  }

  // ── Step 1: Mode Selection ─────────────────────────────────────────────────
  function renderStep1() {
    var c = content();
    if (!c) return;
    c.innerHTML = [
      '<div class="launcher-step">',
      '<div class="nav-live-title">Gesprächsmodus wählen</div>',
      '<div class="nav-live-sub">Wähle den passenden Modus. Der Modus kann während des Calls nicht gewechselt werden.</div>',
      '<div class="nav-live-cards">',
      '<div class="nav-live-card" id="lnr-card-cold">',
      '<div class="nav-live-card-icon">',
      '<svg width="40" height="40" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">',
      '<path d="M13 8C13 8 11 8 10 10C9 12 8 15 10 18C12 21 14 23 16 25C18 27 20 29 23 31C26 33 29 32 31 31C33 30 33 28 33 28L29 24C29 24 27 25 26 25C25 25 24 24 22 22C20 20 19 19 19 18C19 17 20 15 20 15L16 11C16 11 15 8 13 8Z" stroke="#00D4AA" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>',
      '</svg></div>',
      '<div class="nav-live-card-title">Cold Call</div>',
      '<div class="nav-live-card-desc">Nur deine Stimme wird analysiert.<br>Kein Kunden-Audio verarbeitet.<br>EWB-Buttons für manuelle Einwand-Trigger.</div>',
      '</div>',
      '<div class="nav-live-card" id="lnr-card-meeting">',
      '<div class="nav-live-card-icon">',
      '<svg width="40" height="40" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">',
      '<circle cx="15" cy="13" r="4" stroke="#00D4AA" stroke-width="2.2"/>',
      '<circle cx="25" cy="13" r="4" stroke="#00D4AA" stroke-width="2.2"/>',
      '<path d="M6 30C6 25 10 22 15 22" stroke="#00D4AA" stroke-width="2.2" stroke-linecap="round"/>',
      '<path d="M34 30C34 25 30 22 25 22" stroke="#00D4AA" stroke-width="2.2" stroke-linecap="round"/>',
      '<path d="M15 22C17 21 19 21 20 21C21 21 23 21 25 22" stroke="#00D4AA" stroke-width="2.2" stroke-linecap="round"/>',
      '</svg></div>',
      '<div class="nav-live-card-title">Meeting</div>',
      '<div class="nav-live-card-desc">Volle Analyse beider Sprecher.<br>Einwilligung des Gesprächspartners erforderlich.<br>Automatische Einwanderkennung + EWB.</div>',
      '</div>',
      '</div>',
      '</div>'
    ].join('');

    document.getElementById('lnr-card-cold').onclick = function () {
      state.mode = 'cold_call';
      if (state.precallVerfuegbar) {
        state.step = 2;
      } else {
        state.step = 5;
      }
      renderStep();
    };
    document.getElementById('lnr-card-meeting').onclick = function () {
      state.mode = 'meeting';
      if (state.precallVerfuegbar) {
        state.step = 2;
      } else {
        state.step = 5;
      }
      renderStep();
    };
  }

  // ── Step 2: PreCall Option ─────────────────────────────────────────────────
  function renderStep2() {
    var c = content();
    if (!c) return;
    c.innerHTML = [
      '<div class="launcher-step">',
      '<div class="nav-live-title">PreCall-Analyse</div>',
      '<div class="launcher-hint">',
      'Wird empfohlen, damit die KI besser auf Einwände eingehen kann. ',
      'Du gibst den Firmennamen ein und NERVE recherchiert Kontext automatisch.',
      '</div>',
      '<div class="launcher-actions" style="flex-direction:column;gap:10px">',
      '<button class="launcher-btn-primary" id="lnr-precall-yes" style="width:100%">Zur PreCall-Analyse</button>',
      '<button class="launcher-btn-ghost" id="lnr-precall-skip" style="width:100%">Überspringen und zur Opener/Skript-Auswahl</button>',
      '</div>',
      '<div class="launcher-actions" style="justify-content:flex-start">',
      '<button class="launcher-btn-ghost" id="lnr-step2-back">&#8592; Zurück</button>',
      '</div>',
      '</div>'
    ].join('');

    document.getElementById('lnr-precall-yes').onclick = function () {
      state.step = 3;
      renderStep();
    };
    document.getElementById('lnr-precall-skip').onclick = function () {
      state.step = 5;
      renderStep();
    };
    document.getElementById('lnr-step2-back').onclick = function () {
      state.step = 1;
      renderStep();
    };
  }

  // ── Step 3: PreCall Research Form ─────────────────────────────────────────
  function renderStep3() {
    var c = content();
    if (!c) return;
    var saved = state.precallFormData || {};
    c.innerHTML = [
      '<div class="launcher-step">',
      '<div class="nav-live-title">Firmenrecherche</div>',
      '<input type="text" class="launcher-form-input" id="lnr-firma" placeholder="Firmenname *" maxlength="200" value="' + escHtml(saved.firma || '') + '">',
      '<input type="text" class="launcher-form-input" id="lnr-ort" placeholder="Ort (optional)" maxlength="200" value="' + escHtml(saved.ort || '') + '">',
      '<input type="text" class="launcher-form-input" id="lnr-branche" placeholder="Branche (optional)" maxlength="200" value="' + escHtml(saved.branche || '') + '">',
      '<input type="text" class="launcher-form-input" id="lnr-person" placeholder="Ansprechpartner (optional)" maxlength="200" value="' + escHtml(saved.person || '') + '">',
      '<textarea class="launcher-form-input" id="lnr-optinfo" placeholder="Optionale Infos (optional)" maxlength="500" rows="2" style="resize:none">' + escHtml(saved.optinfo || '') + '</textarea>',
      '<div id="lnr-precall-loading" style="display:none">',
      '<div style="font-size:13px;color:var(--page-text-muted);margin-bottom:8px">Recherche läuft... (~30 Sekunden)</div>',
      '<div class="launcher-loading-bar"><div class="launcher-loading-bar-inner"></div></div>',
      '</div>',
      '<div id="lnr-precall-error" style="display:none;color:#f87171;font-size:13px"></div>',
      // ── Phase 08.5 D-09: Anrede-Wahl wurde in Step 5 verschoben ──
      '<div class="launcher-actions">',
      '<button class="launcher-btn-ghost" id="lnr-step3-back">&#8592; Zurück</button>',
      '<button class="launcher-btn-ghost" id="lnr-step3-skip">Überspringen</button>',
      '<button class="launcher-btn-primary" id="lnr-step3-run">Analyse durchführen</button>',
      '</div>',
      '</div>'
    ].join('');

    document.getElementById('lnr-step3-back').onclick = function () {
      saveFormData();
      state.step = 2;
      renderStep();
    };
    document.getElementById('lnr-step3-skip').onclick = function () {
      saveFormData();
      // Confirmation
      if (!confirm('Sind Sie sicher, dass Sie die PreCall-Analyse überspringen möchten?')) return;
      state.precallBriefing = null;
      state.step = 5;
      renderStep();
    };
    document.getElementById('lnr-step3-run').onclick = function () {
      runPrecall();
    };
  }

  function saveFormData() {
    // Phase 08 D-14: preserve anrede across step-back navigation.
    var prevAnrede = (state.precallFormData && state.precallFormData.anrede) || 'Sie';
    state.precallFormData = {
      firma: (document.getElementById('lnr-firma') || {}).value || '',
      ort: (document.getElementById('lnr-ort') || {}).value || '',
      person: (document.getElementById('lnr-person') || {}).value || '',
      branche: (document.getElementById('lnr-branche') || {}).value || '',
      optinfo: (document.getElementById('lnr-optinfo') || {}).value || '',
      anrede: prevAnrede
    };
  }

  function runPrecall() {
    var firma = (document.getElementById('lnr-firma') || {}).value || '';
    if (!firma || firma.trim().length < 3) {
      var errEl = document.getElementById('lnr-precall-error');
      if (errEl) { errEl.textContent = 'Firmenname ist Pflicht (mind. 3 Zeichen).'; errEl.style.display = 'block'; }
      return;
    }
    saveFormData();
    var loading = document.getElementById('lnr-precall-loading');
    var errEl2 = document.getElementById('lnr-precall-error');
    var runBtn = document.getElementById('lnr-step3-run');
    if (loading) loading.style.display = 'block';
    if (errEl2) errEl2.style.display = 'none';
    if (runBtn) { runBtn.disabled = true; runBtn.textContent = 'Läuft...'; }

    var ort = (document.getElementById('lnr-ort') || {}).value || '';
    var person = (document.getElementById('lnr-person') || {}).value || '';
    var branche = (document.getElementById('lnr-branche') || {}).value || '';
    var optinfo = (document.getElementById('lnr-optinfo') || {}).value || '';

    // Build enriched firmenname with location for better search results
    var searchName = firma.trim();
    if (ort.trim()) searchName += ' ' + ort.trim();

    // Build enriched branche with optional info
    var searchBranche = branche.trim();
    if (optinfo.trim()) searchBranche = (searchBranche ? searchBranche + ' ' : '') + optinfo.trim();

    fetch('/api/precall/research', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
      body: JSON.stringify({
        firmenname: searchName,
        ansprechpartner: person.trim() || null,
        branche: searchBranche || null
      })
    })
      .then(function (r) {
        if (!r.ok) {
          return r.text().then(function (t) {
            try { var j = JSON.parse(t); throw new Error(j.error || 'Server-Fehler (' + r.status + ')'); }
            catch (e) { if (e.message) throw e; throw new Error('Server-Fehler (' + r.status + ')'); }
          });
        }
        return r.json();
      })
      .then(function (data) {
        if (loading) loading.style.display = 'none';
        if (runBtn) { runBtn.disabled = false; runBtn.textContent = 'Analyse durchführen'; }
        if (data.error) {
          var errMsg = typeof data.error === 'string' ? data.error : JSON.stringify(data.error);
          if (errEl2) { errEl2.textContent = sanitizeErrorMsg(errMsg); errEl2.style.display = 'block'; }
          return;
        }
        if (data.briefing) {
          state.precallBriefing = data.briefing;
          state.precallResult = data.briefing;
        } else {
          state.precallBriefing = null;
          state.precallResult = null;
        }
        state.step = 4;
        renderStep();
      })
      .catch(function (err) {
        if (loading) loading.style.display = 'none';
        if (runBtn) { runBtn.disabled = false; runBtn.textContent = 'Analyse durchführen'; }
        var msg = (err && err.message) ? err.message : String(err);
        if (errEl2) { errEl2.textContent = sanitizeErrorMsg(msg); errEl2.style.display = 'block'; }
      });
  }

  // ── Step 4: PreCall Result ─────────────────────────────────────────────────
  function renderStep4() {
    var c = content();
    if (!c) return;
    var briefingObj = state.precallBriefing || null;
    var fields = briefingObj ? (briefingObj.fields || {}) : {};
    var briefingText = briefingObj ? (briefingObj.text || '') : '';
    var empfehlungen = briefingObj ? (briefingObj.empfehlungen || '') : '';
    var hasAnyData = !!(briefingText || Object.keys(fields).length > 0);

    // ── Build Pflichtfeld-Karte (Sektion A) ─────────────────────────
    var FIELD_LABELS = {
      geschaeftsfuehrer: 'Geschäftsführer',
      branche: 'Branche',
      mitarbeiterzahl: 'Mitarbeiter',
      hauptprodukt: 'Hauptprodukt'
    };
    var CONFIDENCE_ICONS = { high: '✓', medium: '~', not_found: '—' };
    var REQUIRED_KEYS = ['geschaeftsfuehrer', 'branche', 'mitarbeiterzahl', 'hauptprodukt'];

    function buildFieldCell(key) {
      var f = fields[key] || { value: 'not_found', source_url: null, confidence: 'not_found' };
      var conf = f.confidence || 'not_found';
      var icon = CONFIDENCE_ICONS[conf] || '—';
      var label = FIELD_LABELS[key] || key;
      var displayVal = (conf === 'not_found') ? 'Nicht gefunden' : escHtml(String(f.value || ''));
      return '<div class="precall-field-cell confidence-' + escHtml(conf) + '">' +
        '<div class="precall-field-label"><i class="precall-field-icon">' + icon + '</i>' + escHtml(label) + '</div>' +
        '<div class="precall-field-value">' + displayVal + '</div>' +
        '</div>';
    }

    var gridHtml = '<div class="precall-fields-grid">' +
      REQUIRED_KEYS.map(buildFieldCell).join('') +
      '</div>';

    // ── Build Fließtext (Sektion B) ──────────────────────────────────
    var textHtml = briefingText
      ? '<div class="precall-section-label">Analyse</div>' +
        '<div class="launcher-briefing-html" id="lnr-briefing-view">' + mdToHtml(briefingText) + '</div>' +
        '<textarea class="launcher-briefing" id="lnr-briefing-edit" style="display:none">' + escHtml(briefingText) + '</textarea>'
      : '';

    // ── Build Empfehlungen (Sektion C) ───────────────────────────────
    // mdToHtml sanitizes — safe: mdToHtml() escapes &, <, > before converting markdown
    var empfHtml = empfehlungen
      ? '<div class="precall-section-label">Gesprächs-Empfehlungen</div>' +
        '<div class="launcher-briefing-html">' + mdToHtml(empfehlungen) + '</div>'
      : '';

    c.innerHTML = [
      '<div class="launcher-step">',
      '<div class="nav-live-title">' + (hasAnyData ? 'Recherche-Ergebnis' : 'Keine Daten gefunden') + '</div>',
      hasAnyData
        ? ('<div class="precall-section-label">Eckdaten</div>' + gridHtml + textHtml + empfHtml)
        : '<div style="color:var(--page-text-muted);font-size:13px;padding:12px 0">Für diese Firma konnten keine öffentlichen Informationen gefunden werden. Du kannst trotzdem fortfahren.</div>',
      hasAnyData ? '<div style="margin-top:10px;padding:8px 10px;background:rgba(239,68,68,0.08);border:1px solid rgba(239,68,68,0.25);border-radius:6px;font-size:11px;color:#EF4444;line-height:1.5">⚠️ KI-Recherche kann veraltete oder ungenaue Daten enthalten. Eckdaten (insb. Personennamen &amp; Daten) bitte cross-checken vor Kundenkontakt.</div>' : '',
      '<div class="launcher-actions" style="flex-wrap:wrap;gap:8px;margin-top:16px">',
      '<button class="launcher-btn-ghost" id="lnr-step4-back">&#8592; Zurück</button>',
      (hasAnyData && briefingText) ? '<button class="launcher-btn-ghost" id="lnr-step4-edit">Analyse anpassen</button>' : '',
      '<button class="launcher-btn-ghost" id="lnr-step4-new">Neue Analyse</button>',
      '<button class="launcher-btn-primary" id="lnr-step4-confirm">Briefing übernehmen</button>',
      '</div>',
      '</div>'
    ].join('');

    document.getElementById('lnr-step4-back').onclick = function () {
      state.step = 3;
      renderStep();
    };
    document.getElementById('lnr-step4-new').onclick = function () {
      state.precallBriefing = null;
      state.precallResult = null;
      state.step = 3;
      renderStep();
    };
    var editBtn = document.getElementById('lnr-step4-edit');
    if (editBtn) {
      editBtn.onclick = function () {
        var view = document.getElementById('lnr-briefing-view');
        var edit = document.getElementById('lnr-briefing-edit');
        if (!view || !edit) return;
        var isEditing = edit.style.display !== 'none';
        view.style.display = isEditing ? '' : 'none';
        edit.style.display = isEditing ? 'none' : '';
        editBtn.textContent = isEditing ? 'Analyse anpassen' : 'Vorschau';
      };
    }
    // Phase 08.19.5.6.2: 1-Button "Briefing übernehmen" — EWB + PiP-Tab automatisch
    document.getElementById('lnr-step4-confirm').onclick = function () {
      var ta = document.getElementById('lnr-briefing-edit');
      if (ta && state.precallBriefing) state.precallBriefing.text = ta.value;
      state.step = 5;
      renderStep();
    };
  }

  // ── Step 4b: KI-Personalisierungs-Ladescreen ─────────────────────────────
  function renderStep4b() {
    var c = content();
    if (!c) return;
    if (state._personalizeAbortController) {
      try { state._personalizeAbortController.abort(); } catch (_) {}
    }
    state._personalizeAbortController = new AbortController();

    var isMeeting4b = state.mode === 'meeting';
    var title4b   = isMeeting4b ? 'Skript wird personalisiert…' : 'Opener wird personalisiert…';
    var subText4b = isMeeting4b ? 'KI passt dein Skript auf den Lead an (~5–10 Sekunden)' : 'KI passt deinen Opener auf den Lead an (~5–10 Sekunden)';
    c.innerHTML = [
      '<div class="launcher-step">',
      '<div class="nav-live-title">' + title4b + '</div>',
      '<div style="font-size:13px;color:var(--page-text-muted);margin-bottom:12px">',
      subText4b,
      '</div>',
      '<div class="launcher-loading-bar"><div class="launcher-loading-bar-inner"></div></div>',
      '<div id="lnr-4b-error" style="display:none;color:#f87171;font-size:13px;margin-top:8px"></div>',
      '<div class="launcher-actions" style="margin-top:16px">',
      '<button class="launcher-btn-ghost" id="lnr-step4b-cancel">Abbrechen</button>',
      '</div>',
      '</div>'
    ].join('');

    document.getElementById('lnr-step4b-cancel').onclick = function () {
      if (state._personalizeAbortController) {
        try { state._personalizeAbortController.abort(); } catch (_) {}
      }
      state._personalizeAbortController = null;
      state._personalizedSkriptText = null;
      state.step = 5;
      renderStep();
    };

    fetch('/api/precall/personalize', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken()
      },
      body: JSON.stringify(
        state.mode === 'meeting'
          ? { skript_id: state.selectedSkriptId,  call_mode: state.mode, briefing: state.precallBriefing || {} }
          : { opener_id: state.selectedOpenerId,  call_mode: state.mode || 'cold_call', briefing: state.precallBriefing || {} }
      ),
      signal: state._personalizeAbortController.signal
    })
      .then(function (r) {
        if (!r.ok) {
          return r.text().then(function (t) {
            try {
              var j = JSON.parse(t);
              throw new Error(j.error || 'Server-Fehler (' + r.status + ')');
            } catch (e) {
              if (e.message) throw e;
              throw new Error('Server-Fehler (' + r.status + ')');
            }
          });
        }
        return r.json();
      })
      .then(function (data) {
        if (data && data.error) {
          var errEl = document.getElementById('lnr-4b-error');
          if (errEl) { errEl.textContent = sanitizeErrorMsg(data.error); errEl.style.display = 'block'; }
          return;
        }
        state._personalizedSkriptText = data.personalized_text || '';
        state._personalizeAbortController = null;
        state.step = '4c';
        renderStep();
      })
      .catch(function (err) {
        if (err && err.name === 'AbortError') return;
        var errEl = document.getElementById('lnr-4b-error');
        if (errEl) {
          errEl.textContent = sanitizeErrorMsg((err && err.message) ? err.message : String(err));
          errEl.style.display = 'block';
        }
      });
  }

  // ── Step 4c: Vorher / Nachher-Vergleich ──────────────────────────────────
  function renderStep4c() {
    var c = content();
    if (!c) return;
    // Modus-abhängige Quelle: Meeting → state.skripte; Cold-Call → state.openerItems
    var originalText = '';
    if (state.mode === 'meeting') {
      var skript4c = (state.skripte || []).find(function (s) { return s.id === state.selectedSkriptId; });
      originalText = skript4c ? (skript4c.inhalt || '') : '';
    } else {
      var opener4c = (state.openerItems || []).find(function (o) { return o.id === state.selectedOpenerId; });
      originalText = opener4c ? (opener4c.inhalt || '') : '';
    }
    var personalizedText = state._personalizedSkriptText || '';

    c.innerHTML = [
      '<div class="launcher-step">',
      '<div class="nav-live-title">Vorher / Nachher</div>',
      '<div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:16px">',
      '  <div style="flex:1;min-width:180px">',
      '    <div class="precall-section-label">Original</div>',
      '    <div class="launcher-opener-preview" style="white-space:pre-wrap;font-size:12px;max-height:200px;overflow-y:auto">',
      escHtml(originalText),
      '    </div>',
      '  </div>',
      '  <div style="flex:1;min-width:180px">',
      '    <div class="precall-section-label">Personalisiert ✨</div>',
      '    <div class="launcher-opener-preview" style="white-space:pre-wrap;font-size:12px;max-height:200px;overflow-y:auto">',
      escHtml(personalizedText),
      '    </div>',
      '  </div>',
      '</div>',
      '<div id="lnr-4c-save-error" style="display:none;color:#f87171;font-size:13px;margin-bottom:8px"></div>',
      '<div class="launcher-actions" style="flex-wrap:wrap;gap:8px">',
      '<button class="launcher-btn-ghost" id="lnr-step4c-original">Original nutzen</button>',
      '<button class="launcher-btn-primary" id="lnr-step4c-save">Personalisiert nutzen</button>',
      '</div>',
      '</div>'
    ].join('');

    document.getElementById('lnr-step4c-original').onclick = function () {
      state._personalizedSkriptText = null;
      state.step = 5;
      renderStep();
    };

    document.getElementById('lnr-step4c-save').onclick = function () {
      _savePersonalizedAndStartCall();
    };
  }

  // ── Phase 08.20.3: Save personalized skript + start call ─────────────────
  function _savePersonalizedAndStartCall() {
    var saveBtn = document.getElementById('lnr-step4c-save');
    var errEl = document.getElementById('lnr-4c-save-error');
    if (saveBtn) { saveBtn.disabled = true; saveBtn.textContent = 'Speichern…'; }

    fetch('/api/precall/personalize/save', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken()
      },
      body: JSON.stringify(Object.assign(
        state.mode === 'meeting'
          ? { skript_id: state.selectedSkriptId }
          : { opener_id: state.selectedOpenerId },
        {
          call_mode: state.mode || 'cold_call',
          personalized_text: state._personalizedSkriptText || '',
          firmenname: (state.precallBriefing && state.precallBriefing.firmenname) || ''
        }
      ))
    })
      .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
      .then(function (data) {
        if (data && data.cap_exceeded) {
          _showCapSubModal(data.items || []);
          if (saveBtn) { saveBtn.disabled = false; saveBtn.textContent = 'Personalisiert nutzen'; }
          return;
        }
        if (data && data.error) {
          if (errEl) { errEl.textContent = sanitizeErrorMsg(data.error); errEl.style.display = 'block'; }
          if (saveBtn) { saveBtn.disabled = false; saveBtn.textContent = 'Personalisiert nutzen'; }
          return;
        }
        // R-04: Zurück zu Step-5-4-Reiter-Ansicht statt startCall(true)
        // _editedText bereinigen (nicht mehr benötigt — personalisierter Text ist jetzt in DB)
        state._personalizedSkriptText = null;
        state._personalizeAbortController = null;

        // MEDIUM (Cross-AI-Fix): Loading-State anzeigen (saveBtn aus Funktionskopf, ID='lnr-step4c-save')
        var saveBtnOrigText = saveBtn ? saveBtn.textContent : '';
        if (saveBtn) { saveBtn.textContent = 'Lädt…'; }

        // Neuestes personalisiertes Item laden und selektieren
        fetch('/api/launcher/profile/' + state.activeProfileId)
          .then(function (r) {
            if (!r.ok) throw new Error('profile load failed: ' + r.status);
            return r.json();
          })
          .then(function (profileData) {
            // openerItems und skripte aktualisieren
            state.openerItems = profileData.opener || [];
            state.skripte     = profileData.skripte || [];

            if (state.mode === 'meeting') {
              var persSkripte = (profileData.skripte || []).filter(function (s) { return s.is_personalized; });
              persSkripte.sort(function (a, b) { return b.id - a.id; });
              // FIX doppel-save: Null-Guard navigiert zu Step 5 statt Button re-enablen
              // Save war bereits erfolgreich (200 OK) — re-enable wuerde zweiten Save-Klick ermoeglichen
              if (persSkripte.length === 0) {
                console.error('[Personalize] Reload fand kein personalisiertes Skript — stiller Backend-Fehler?');
                if (typeof _showToast === 'function') _showToast('Personalisierung gespeichert, aber Reload fehlgeschlagen — bitte Profil neu laden.', 'warning');
                state.step = 5;
                renderStep5();
                return;
              }
              state.selectedSkriptId = persSkripte[0].id;
              state.activeTab = 'skript';
            } else {
              var persOpener = (profileData.opener || []).filter(function (o) {
                return o.type === 'opener' && o.is_personalized;
              });
              persOpener.sort(function (a, b) { return b.id - a.id; });
              // FIX doppel-save: Null-Guard navigiert zu Step 5 statt Button re-enablen
              // Save war bereits erfolgreich (200 OK) — re-enable wuerde zweiten Save-Klick ermoeglichen
              if (persOpener.length === 0) {
                console.error('[Personalize] Reload fand keinen personalisierten Opener — stiller Backend-Fehler?');
                if (typeof _showToast === 'function') _showToast('Personalisierung gespeichert, aber Reload fehlgeschlagen — bitte Profil neu laden.', 'warning');
                state.step = 5;
                renderStep5();
                return;
              }
              state.selectedOpenerId = persOpener[0].id;
              state.activeTab = 'opener';
            }
            state.step = 5;
            renderStep5(); // Button ist nach renderStep5 nicht mehr sichtbar — kein explizites re-enable nötig
          })
          .catch(function () {
            // Fallback: renderStep5() auch ohne Reload — kein startCall(true)
            if (saveBtn) { saveBtn.disabled = false; saveBtn.textContent = saveBtnOrigText; }
            state.activeTab = state.mode === 'meeting' ? 'skript' : 'opener';
            state.step = 5;
            renderStep5();
          });
      })
      .catch(function (err) {
        if (errEl) {
          errEl.textContent = sanitizeErrorMsg((err && err.message) ? err.message : 'Fehler beim Speichern');
          errEl.style.display = 'block';
        }
        if (saveBtn) { saveBtn.disabled = false; saveBtn.textContent = 'Personalisiert nutzen'; }
      });
  }

  // ── Phase 08.20.3: Cap Sub-Modal ─────────────────────────────────────────
  function _showCapSubModal(items) {
    var c = content();
    if (!c) return;

    var itemRows = items.map(function (item) {
      return '<label style="display:flex;align-items:flex-start;gap:8px;font-size:12px;margin-bottom:6px;cursor:pointer">' +
        '<input type="checkbox" name="cap-delete-item" value="' + item.id + '" style="margin-top:2px"> ' +
        escHtml(item.name || '') +
        ' <span style="opacity:0.6;font-size:11px">(' + escHtml(String(item.weeks_old || 0)) + ' Wochen alt)</span>' +
        '</label>';
    }).join('');

    c.innerHTML = [
      '<div class="launcher-step">',
      '<div class="nav-live-title">Speicherplatz für personalisierte Skripte voll</div>',
      '<div style="font-size:13px;color:var(--page-text-muted);margin-bottom:12px">',
      'Du hast bereits die maximale Anzahl personalisierter Skripte erreicht. ',
      'Bitte wähle ein oder mehrere aus, die du löschen möchtest.',
      '</div>',
      '<div id="cap-items-list" style="max-height:240px;overflow-y:auto;margin-bottom:12px">',
      itemRows,
      '</div>',
      '<div id="lnr-cap-error" style="display:none;color:#f87171;font-size:13px;margin-bottom:8px"></div>',
      '<div class="launcher-actions" style="flex-wrap:wrap;gap:8px">',
      '<button class="launcher-btn-ghost" id="lnr-cap-cancel">Abbrechen</button>',
      '<button class="launcher-btn-primary" id="lnr-cap-delete-save">Auswahl löschen + Personalisieren →</button>',
      '</div>',
      '</div>'
    ].join('');

    document.getElementById('lnr-cap-cancel').onclick = function () {
      state.step = '4c';
      renderStep();
    };

    document.getElementById('lnr-cap-delete-save').onclick = function () {
      var checkboxes = c.querySelectorAll('input[name="cap-delete-item"]:checked');
      var deleteIds = Array.prototype.slice.call(checkboxes).map(function (cb) {
        return parseInt(cb.value, 10);
      });
      if (deleteIds.length === 0) {
        var capErrEl = document.getElementById('lnr-cap-error');
        if (capErrEl) { capErrEl.textContent = 'Bitte mindestens ein Skript auswählen.'; capErrEl.style.display = 'block'; }
        return;
      }
      var delBtn = document.getElementById('lnr-cap-delete-save');
      if (delBtn) { delBtn.disabled = true; delBtn.textContent = 'Löschen…'; }

      fetch('/api/precall/personalize/save', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify(Object.assign(
          state.mode === 'meeting'
            ? { skript_id: state.selectedSkriptId }
            : { opener_id: state.selectedOpenerId },
          {
            call_mode: state.mode || 'cold_call',
            personalized_text: state._personalizedSkriptText || '',
            firmenname: (state.precallBriefing && state.precallBriefing.firmenname) || '',
            delete_ids: deleteIds
          }
        ))
      })
        .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
        .then(function (data) {
          if (data && data.cap_exceeded) {
            // Race condition: another tab created an item — re-show cap modal with fresh list
            _showCapSubModal(data.items || []);
            if (delBtn) { delBtn.disabled = false; delBtn.textContent = 'Auswahl löschen + Personalisieren →'; }
            return;
          }
          if (data && data.error) {
            var capErrEl = document.getElementById('lnr-cap-error');
            if (capErrEl) { capErrEl.textContent = sanitizeErrorMsg(data.error); capErrEl.style.display = 'block'; }
            if (delBtn) { delBtn.disabled = false; delBtn.textContent = 'Auswahl löschen + Personalisieren →'; }
            return;
          }
          // Modus-abhängig: Meeting → _editedSkriptText; Cold-Call → _editedOpenerText
          if (state.mode === 'meeting') {
            state._editedSkriptText = state._personalizedSkriptText || "";
          } else {
            state._editedOpenerText = state._personalizedSkriptText || "";
          }
          state._personalizedSkriptText = null;
          _collectEditedTexts();
          startCall(true);
        })
        .catch(function (err) {
          var capErrEl = document.getElementById('lnr-cap-error');
          if (capErrEl) {
            capErrEl.textContent = sanitizeErrorMsg((err && err.message) ? err.message : 'Fehler');
            capErrEl.style.display = 'block';
          }
          if (delBtn) { delBtn.disabled = false; delBtn.textContent = 'Auswahl löschen + Personalisieren →'; }
        });
    };
  }

  // ── Tab-Switch: Step 5 ────────────────────────────────────────────────────
  function switchTab5(tab) { state.activeTab = tab; renderStep5(); }
  window.switchTab5 = switchTab5;

  // ── Step 5: Gesprächsvorbereitung (4-Tab-UI) ──────────────────────────────
  function renderStep5() {
    var c = content();
    if (!c) return;

    // D-06: Tab-Guard — Default-Tab ist 'opener'
    if (!state.activeTab) state.activeTab = 'opener';

    // Phase 08.5 D-10: Anrede-Vorauswahl — last call > profile default > 'Sie'
    var savedAnrede5 = state.lastSessionAnrede
                    || (state.profileDaten && state.profileDaten.ki && state.profileDaten.ki.ansprache)
                    || 'Sie';
    // Preset anrede so anredeForSession has a valid value even if user never clicks
    if (!state.precallFormData) state.precallFormData = {};
    if (!state.precallFormData.anrede) state.precallFormData.anrede = savedAnrede5;

    // Phase 08.5 D-10 edge-case: single-script → auto-select but keep Step 5 visible (mandatory Anrede)
    if ((state.skripte || []).length === 1 && !state.selectedSkriptId) {
      state.selectedSkriptId = state.skripte[0].id;
    }

    var profileOptions = state.profiles.map(function (p) {
      var sel = p.id === state.activeProfileId ? ' selected' : '';
      return '<option value="' + p.id + '"' + sel + '>' + escHtml(p.name) + '</option>';
    }).join('');

    // ── Tab-Nav (D-02: inline onclick) ──
    var tabNavHtml = '<nav class="fcd-tabs" style="margin-bottom:12px">'
      + '<button class="fcd-tab' + (state.activeTab === 'opener'    ? ' active' : '') + '" onclick="window.switchTab5(\'opener\')">Opener</button>'
      + '<button class="fcd-tab' + (state.activeTab === 'erlaubnis' ? ' active' : '') + '" onclick="window.switchTab5(\'erlaubnis\')">Erlaubnisfrage</button>'
      + '<button class="fcd-tab' + (state.activeTab === 'pitch'     ? ' active' : '') + '" onclick="window.switchTab5(\'pitch\')">Pitch</button>'
      + '<button class="fcd-tab' + (state.activeTab === 'skript'    ? ' active' : '') + '" onclick="window.switchTab5(\'skript\')">Skript</button>'
      + '</nav>';

    // ── Modus-Logik für modus-abhängigen Personalisieren-Button ──
    // state.mode === 'meeting'   → Button nur im Skript-Tab
    // state.mode === 'cold_call' → Button nur im Opener-Tab (oder kein mode)
    var isMeeting = (state.mode === 'meeting');

    // ── Tab-Content ──
    var tabContentHtml;

    if (state.activeTab === 'opener') {
      var openerItems = (state.openerItems || []).filter(function (o) { return o.type === 'opener'; });
      if (openerItems.length === 0) {
        tabContentHtml = '<div style="color:var(--page-text-muted);font-size:13px">Noch kein Opener hinterlegt — <a href="/profiles" style="color:var(--btn-primary-bg-from)">Profil bearbeiten</a></div>';
      } else {
        var opSel5 = openerItems.find(function (o) { return o.id === state.selectedOpenerId; });
        var opOpts = '<option value=""' + (state.selectedOpenerId === null ? ' selected' : '') + '>— kein Opener —</option>'
          + openerItems.map(function (o) {
              return '<option value="' + o.id + '"' + (o.id === state.selectedOpenerId ? ' selected' : '') + '>' + escHtml(o.name) + '</option>';
            }).join('');
        var opPrev = opSel5 ? escHtml(opSel5.inhalt || '') : '';
        tabContentHtml =
          '<select class="launcher-select" id="lnr-opener-select">' + opOpts + '</select>'
          + '<div class="launcher-opener-preview" id="lnr-opener-preview" style="white-space:pre-wrap' + (opPrev ? '' : ';color:var(--page-text-muted);font-style:italic') + '">' + (opPrev || 'Opener auswählen für Vorschau') + '</div>'
          + '<textarea class="launcher-briefing" id="lnr-opener-textarea" style="display:none;margin-top:4px" rows="3"></textarea>'
          + '<button type="button" class="launcher-inline-edit-btn" id="lnr-opener-edit-btn">Bearbeiten</button>'
          // Personalisieren-Button: nur im Opener-Tab wenn Cold-Call-Modus (oder kein Modus)
          + (!isMeeting ? '<button class="launcher-btn-ghost" id="lnr-step5-personalize">✨ Personalisieren + Call ▶</button>' : '');
      }

    } else if (state.activeTab === 'erlaubnis') {
      var erlaubnisItems = (state.openerItems || []).filter(function (o) { return o.type === 'erlaubnis'; });
      if (erlaubnisItems.length === 0) {
        tabContentHtml = '<div style="color:var(--page-text-muted);font-size:13px">Noch keine Erlaubnisfrage hinterlegt — <a href="/profiles" style="color:var(--btn-primary-bg-from)">Profil bearbeiten</a></div>';
      } else {
        var erlSel5 = erlaubnisItems.find(function (o) { return o.id === state.selectedErlaubnisId; });
        var erlOpts = '<option value=""' + (state.selectedErlaubnisId === null ? ' selected' : '') + '>— keine Erlaubnisfrage —</option>'
          + erlaubnisItems.map(function (o) {
              return '<option value="' + o.id + '"' + (o.id === state.selectedErlaubnisId ? ' selected' : '') + '>' + escHtml(o.name) + '</option>';
            }).join('');
        var erlPrev = erlSel5 ? escHtml(erlSel5.inhalt || '') : '';
        tabContentHtml =
          '<select class="launcher-select" id="lnr-opener-select">' + erlOpts + '</select>'
          + '<div class="launcher-opener-preview" id="lnr-opener-preview" style="white-space:pre-wrap' + (erlPrev ? '' : ';color:var(--page-text-muted);font-style:italic') + '">' + (erlPrev || 'Erlaubnisfrage auswählen für Vorschau') + '</div>'
          + '<textarea class="launcher-briefing" id="lnr-opener-textarea" style="display:none;margin-top:4px" rows="3"></textarea>'
          + '<button type="button" class="launcher-inline-edit-btn" id="lnr-opener-edit-btn">Bearbeiten</button>';
          // Kein Personalisieren-Button in Erlaubnisfrage-Tab
      }

    } else if (state.activeTab === 'pitch') {
      var pitchItems = (state.openerItems || []).filter(function (o) { return o.type === 'pitch'; });
      if (pitchItems.length === 0) {
        tabContentHtml = '<div style="color:var(--page-text-muted);font-size:13px">Noch kein Pitch hinterlegt — <a href="/profiles" style="color:var(--btn-primary-bg-from)">Profil bearbeiten</a></div>';
      } else {
        var pitchSel5 = pitchItems.find(function (o) { return o.id === state.selectedPitchId; });
        var pitchOpts = '<option value=""' + (state.selectedPitchId === null ? ' selected' : '') + '>— keinen Pitch —</option>'
          + pitchItems.map(function (o) {
              return '<option value="' + o.id + '"' + (o.id === state.selectedPitchId ? ' selected' : '') + '>' + escHtml(o.name) + '</option>';
            }).join('');
        var pitchPrev = pitchSel5 ? escHtml(pitchSel5.inhalt || '') : '';
        tabContentHtml =
          '<select class="launcher-select" id="lnr-opener-select">' + pitchOpts + '</select>'
          + '<div class="launcher-opener-preview" id="lnr-opener-preview" style="white-space:pre-wrap' + (pitchPrev ? '' : ';color:var(--page-text-muted);font-style:italic') + '">' + (pitchPrev || 'Pitch auswählen für Vorschau') + '</div>'
          + '<textarea class="launcher-briefing" id="lnr-opener-textarea" style="display:none;margin-top:4px" rows="3"></textarea>'
          + '<button type="button" class="launcher-inline-edit-btn" id="lnr-opener-edit-btn">Bearbeiten</button>';
          // Kein Personalisieren-Button in Pitch-Tab
      }

    } else {  // 'skript' (default fallback)
      if ((state.skripte || []).length === 0) {
        tabContentHtml = '<div style="color:var(--page-text-muted);font-size:13px">Noch kein Skript hinterlegt — <a href="/profiles" style="color:var(--btn-primary-bg-from)">Profil bearbeiten</a></div>';
      } else {
        var skSel5 = state.skripte.find(function (s) { return s.id === state.selectedSkriptId; });
        var skOpts = '<option value=""' + (state.selectedSkriptId === null ? ' selected' : '') + '>— kein Skript —</option>'
          + state.skripte.map(function (s) {
              return '<option value="' + s.id + '"' + (s.id === state.selectedSkriptId ? ' selected' : '') + '>' + escHtml(s.name) + '</option>';
            }).join('');
        var skPrev = skSel5 ? escHtml(skSel5.inhalt || '') : '';
        tabContentHtml =
          '<select class="launcher-select" id="lnr-skript-select">' + skOpts + '</select>'
          + '<div class="launcher-opener-preview" id="lnr-skript-preview" style="white-space:pre-wrap' + (skPrev ? '' : ';color:var(--page-text-muted);font-style:italic') + '">' + (skPrev || 'Skript auswählen für Vorschau') + '</div>'
          + '<textarea class="launcher-briefing" id="lnr-skript-textarea" style="display:none;margin-top:4px" rows="4"></textarea>'
          + '<button type="button" class="launcher-inline-edit-btn" id="lnr-skript-edit-btn">Bearbeiten</button>'
          // Personalisieren-Button: nur im Skript-Tab wenn Meeting-Modus (NEU v3)
          + (isMeeting ? '<button class="launcher-btn-ghost" id="lnr-step5-personalize">✨ Personalisieren + Call ▶</button>' : '');
      }
    }

    // ── R-05: Hint-Box — Gesprächsvorbereitung Reihenfolge-Erklärung ──
    var hintBoxHtml = '<div class="launcher-hint-box">'
      + '<span class="launcher-hint-icon">ⓘ</span>'
      + '<span>Reihenfolge im Teleprompter: <strong>Opener → Erlaubnisfrage → Pitch/Skript</strong>. '
      + 'Skript hat Vorrang vor Pitch. '
      + 'Mit „— kein/e …" diesen Teil überspringen.</span>'
      + '</div>';

    // ── innerHTML zusammensetzen ──
    c.innerHTML = [
      '<div class="launcher-step">',
      '<div class="nav-live-title">Gesprächsvorbereitung</div>',

      // Profil-Picker
      state.profiles.length > 0
        ? '<label style="font-size:11px;color:var(--page-text-muted);margin-bottom:2px;display:block">Profil</label><select class="launcher-select" id="lnr-profile-select">' + profileOptions + '</select>'
        : '<div style="color:var(--page-text-muted);font-size:13px">Noch kein Profil angelegt. <a href="/profiles" style="color:var(--btn-primary-bg-from)">Profil erstellen</a></div>',

      // R-05: Hint-Box vor Tab-Nav
      hintBoxHtml,

      // Tab-Nav
      tabNavHtml,

      // Tab-Content
      tabContentHtml,

      // ── Anrede (immer sichtbar, kein Conditional auf precallBriefing) ── R5
      '<div class="launcher-form-label" style="margin-top:12px;font-size:13px;color:var(--page-text-muted)">Anrede im Gespräch *</div>',
      '<div class="launcher-anrede-row" id="lnr-anrede-row5">',
      '<button type="button" class="launcher-anrede-btn' + (savedAnrede5 === 'Du' ? ' active' : '') + '" data-val="Du" onclick="window.NerveLauncher._setAnrede(\'Du\')">Du</button>',
      '<button type="button" class="launcher-anrede-btn' + (savedAnrede5 === 'Sie' ? ' active' : '') + '" data-val="Sie" onclick="window.NerveLauncher._setAnrede(\'Sie\')">Sie</button>',
      '</div>',

      // ── Vorwissen-Picker (immer sichtbar, kein Conditional auf precallBriefing) ── R5
      '<div class="launcher-form-label" style="margin-top:12px;font-size:13px;color:var(--page-text-muted)">Lead-Vorwissen (optional)</div>',
      '<div class="launcher-anrede-row" id="lnr-vorwissen-row5" style="gap:8px;flex-wrap:wrap">',
      '<button type="button" class="launcher-anrede-btn' + (state.vorwissenLevel === 'niedrig' ? ' active' : '') + '" data-val="niedrig" onclick="window.NerveLauncher._setVorwissen(\'niedrig\')">Wenig Ahnung</button>',
      '<button type="button" class="launcher-anrede-btn' + (state.vorwissenLevel === 'mittel'  ? ' active' : '') + '" data-val="mittel"  onclick="window.NerveLauncher._setVorwissen(\'mittel\')">Vertraut damit</button>',
      '<button type="button" class="launcher-anrede-btn' + (state.vorwissenLevel === 'hoch'    ? ' active' : '') + '" data-val="hoch"    onclick="window.NerveLauncher._setVorwissen(\'hoch\')">Kennt uns gut</button>',
      '<button type="button" class="launcher-anrede-btn' + (!state.vorwissenLevel              ? ' active' : '') + '" data-val="null"    onclick="window.NerveLauncher._setVorwissen(null)">Weiß nicht</button>',
      '</div>',

      // ── Navigation ──
      '<div class="launcher-actions">',
      '<button class="launcher-btn-ghost" id="lnr-step5-back">&#8592; Zurück</button>',
      '<button class="launcher-btn-ghost" id="lnr-step5-skip">Überspringen</button>',
      '<button class="launcher-btn-primary" id="lnr-step5-start">Call starten &#9654;</button>',
      '</div>',
      '</div>'
    ].join('');

    // ── R-03: Tab-Switch Preview-Trigger — sofort den ersten/selektierten Item-Text anzeigen ──
    (function () {
      var tab = state.activeTab;
      var previewId, items, selId;
      if (tab === 'skript') {
        previewId = 'lnr-skript-preview';
        items = state.skripte || [];
        selId = state.selectedSkriptId;
      } else {
        previewId = 'lnr-opener-preview';
        items = (state.openerItems || []).filter(function (o) { return o.type === tab; });
        selId = tab === 'erlaubnis' ? state.selectedErlaubnisId
              : tab === 'pitch'    ? state.selectedPitchId
              :                      state.selectedOpenerId;
      }
      var previewEl = document.getElementById(previewId);
      if (!previewEl || items.length === 0) return;
      // Selektiertes Item anzeigen; wenn null → Hint-Text italic, NICHT items[0] (D-03)
      var item = selId ? items.find(function (i) { return i.id === selId; }) : null;
      if (item && item.inhalt) {
        previewEl.textContent = item.inhalt;
        previewEl.style.fontStyle = 'normal';
        previewEl.style.color = '';
      } else {
        var hint = tab === 'skript'    ? 'Skript auswählen für Vorschau'
                 : tab === 'erlaubnis' ? 'Erlaubnisfrage auswählen für Vorschau'
                 : tab === 'pitch'     ? 'Pitch auswählen für Vorschau'
                 :                       'Opener auswählen für Vorschau';
        previewEl.textContent = hint;
        previewEl.style.fontStyle = 'italic';
        previewEl.style.color = 'var(--page-text-muted)';
      }
    })();

    // ── Event Wiring nach innerHTML ──

    // Profile-Change (reset activeTab + alle 4 Selection-Variablen beim Profil-Wechsel)
    var profileSel5 = document.getElementById('lnr-profile-select');
    if (profileSel5) {
      profileSel5.onchange = function () {
        var pid = parseInt(profileSel5.value);
        if (!pid) return;
        fetch('/api/launcher/profile/' + pid)
          .then(function (r) {
            if (!r.ok) throw new Error('profile load failed: ' + r.status);
            return r.json();
          })
          .then(function (data) {
            state.activeProfileId     = data.id;
            state.profileDaten        = data.daten || {};
            state.skripte             = data.skripte || [];
            state.openerItems         = data.opener || [];
            state.selectedSkriptId    = null;
            state.selectedOpenerId    = null;
            state.selectedErlaubnisId = null;
            state.selectedPitchId     = null;
            state.activeTab           = null;  // reset to opener-default on profile change
            renderStep5();
          })
          .catch(function (err) {
            console.warn('[Launcher] Profil laden fehlgeschlagen:', err);
          });
      };
    }

    // Opener/Erlaubnisfrage/Pitch-Select — Tab-aware: schreibt in tab-spezifische Variable
    var openerSel5 = document.getElementById('lnr-opener-select');
    if (openerSel5) {
      openerSel5.onchange = function () {
        var id = parseInt(openerSel5.value) || null;
        if      (state.activeTab === 'opener')   state.selectedOpenerId    = id;
        else if (state.activeTab === 'erlaubnis') state.selectedErlaubnisId = id;
        else if (state.activeTab === 'pitch')     state.selectedPitchId     = id;
        var preview = document.getElementById('lnr-opener-preview');
        if (preview) {
          var tab   = state.activeTab;
          var items = (state.openerItems || []).filter(function (o) { return o.type === tab; });
          var selId = tab === 'erlaubnis' ? state.selectedErlaubnisId
                    : tab === 'pitch'     ? state.selectedPitchId
                    :                       state.selectedOpenerId;
          var op5 = items.find(function (o) { return o.id === selId; });
          preview.textContent    = op5 ? op5.inhalt : (tab + ' auswählen für Vorschau');
          preview.style.fontStyle = op5 ? 'normal' : 'italic';
          preview.style.color     = op5 ? '' : 'var(--page-text-muted)';
        }
      };
    }

    // Skript-Select (nur Skript-Tab)
    var skriptSel5 = document.getElementById('lnr-skript-select');
    if (skriptSel5) {
      skriptSel5.onchange = function () {
        state.selectedSkriptId = parseInt(skriptSel5.value) || null;
        var preview = document.getElementById('lnr-skript-preview');
        if (preview) {
          var sk5 = state.skripte.find(function (s) { return s.id === state.selectedSkriptId; });
          preview.textContent    = sk5 ? sk5.inhalt : 'Skript auswählen für Vorschau';
          preview.style.fontStyle = sk5 ? 'normal' : 'italic';
          preview.style.color     = sk5 ? '' : 'var(--page-text-muted)';
        }
      };
    }

    // Inline-Edit Wiring (je aktiver Tab) — pass tab-specific itemId to avoid wrong-ID bug
    if (state.activeTab === 'skript') {
      _wireInlineEdit('lnr-skript-edit-btn', 'lnr-skript-preview', 'lnr-skript-textarea', 'skript');
    } else if (state.activeTab === 'erlaubnis') {
      _wireInlineEdit('lnr-opener-edit-btn', 'lnr-opener-preview', 'lnr-opener-textarea', 'opener', state.selectedErlaubnisId);
    } else if (state.activeTab === 'pitch') {
      _wireInlineEdit('lnr-opener-edit-btn', 'lnr-opener-preview', 'lnr-opener-textarea', 'opener', state.selectedPitchId);
    } else {
      _wireInlineEdit('lnr-opener-edit-btn', 'lnr-opener-preview', 'lnr-opener-textarea', 'opener', state.selectedOpenerId);
    }

    // Navigation: Back
    var backBtn5 = document.getElementById('lnr-step5-back');
    if (backBtn5) {
      backBtn5.onclick = function () {
        if (state.precallBriefing)        { state.step = 4; }
        else if (state.precallVerfuegbar) { state.step = 2; }
        else                              { state.step = 1; }
        renderStep();
      };
    }

    // Navigation: Skip
    var skipBtn5 = document.getElementById('lnr-step5-skip');
    if (skipBtn5) {
      skipBtn5.onclick = function () { _collectEditedTexts(); startCall(false); };
    }

    // Navigation: Start
    var startBtn5 = document.getElementById('lnr-step5-start');
    if (startBtn5) {
      startBtn5.onclick = function () {
        var s5 = document.getElementById('lnr-profile-select');
        if (s5 && s5.value) state.activeProfileId = parseInt(s5.value);
        _collectEditedTexts();
        startCall(true);
      };
    }

    // Personalisieren-Button (existiert nur wenn modus-passendem Tab aktiv)
    var personalizeBtn5 = document.getElementById('lnr-step5-personalize');
    if (personalizeBtn5) {
      personalizeBtn5.onclick = function () {
        // Modus-abhängig: Meeting → selectedSkriptId; Cold-Call → selectedOpenerId
        if (state.mode === 'meeting') {
          var skSel = document.getElementById('lnr-skript-select');
          if (skSel && skSel.value) state.selectedSkriptId = parseInt(skSel.value, 10) || null;
          if (!state.selectedSkriptId) {
            alert('Bitte erst ein Skript auswählen, bevor du personalisierst.');
            return;
          }
        } else {
          var opSel = document.getElementById('lnr-opener-select');
          if (opSel && opSel.value) state.selectedOpenerId = parseInt(opSel.value, 10) || null;
          if (!state.selectedOpenerId) {
            alert('Bitte erst einen Opener auswählen, bevor du personalisierst.');
            return;
          }
        }
        state.step = '4b';
        renderStep();
      };
    }
  }

  function _wireInlineEdit(btnId, previewId, textareaId, type, overrideItemId) {
    var btn = document.getElementById(btnId);
    if (!btn) return;
    btn.onclick = function () {
      var preview = document.getElementById(previewId);
      var ta = document.getElementById(textareaId);
      if (!ta) return;
      if (ta.style.display === 'none') {
        // Switch to edit mode — populate textarea with current preview text
        var currentText = preview ? preview.textContent : '';
        if (currentText && currentText !== 'Skript auswählen für Vorschau' && currentText !== 'Opener auswählen für Vorschau' && currentText !== 'Kein Opener hinterlegt') {
          ta.value = currentText;
        }
        if (preview) preview.style.display = 'none';
        ta.style.display = 'block';
        ta.style.borderColor = '#00D4AA';
        ta.focus();
        btn.textContent = 'Fertig';
      } else {
        // Save edit — ask if profile should be updated
        var newText = ta.value;
        var itemId = type === 'skript' ? state.selectedSkriptId : (overrideItemId !== undefined ? overrideItemId : state.selectedOpenerId);
        if (preview) {
          preview.textContent = newText;
          preview.style.display = 'block';
          preview.style.fontStyle = 'normal';
          preview.style.color = '';
        }
        ta.style.display = 'none';
        btn.textContent = 'Bearbeiten';

        // Update local state for this call
        if (type === 'skript') state._editedSkriptText = newText;
        // WR-02: Nur setzen wenn wirklich der Opener-Tab aktiv ist (nicht erlaubnis/pitch — die übergeben auch type='opener')
        if (type === 'opener' && state.activeTab === 'opener') state._editedOpenerText = newText;

        // Ask: save to profile too?
        if (itemId) {
          _showSaveToProfileDialog(type, itemId, newText);
        }
      }
    };
  }

  function _showSaveToProfileDialog(type, itemId, newText) {
    var label = type === 'skript' ? 'Skript' : 'Opener';
    var endpoint = '/profiles/' + state.activeProfileId + '/' + (type === 'skript' ? 'skripte' : 'opener') + '/' + itemId;

    // Create overlay
    var overlay = document.createElement('div');
    overlay.style.cssText = 'position:fixed;inset:0;z-index:10001;background:rgba(0,0,0,0.6);display:flex;align-items:center;justify-content:center';
    overlay.innerHTML = '<div style="background:var(--page-bg,#fff);border:1.5px solid var(--glass-border);border-radius:12px;padding:24px;max-width:400px;width:90%;text-align:center">'
      + '<div style="font-size:15px;font-weight:700;margin-bottom:12px">' + label + ' auch im Profil ändern?</div>'
      + '<div style="font-size:13px;color:var(--page-text-muted);margin-bottom:16px">Die Änderung gilt sonst nur für diesen Call.</div>'
      + '<div style="display:flex;gap:10px;justify-content:center">'
      + '<button id="lnr-save-no" style="padding:8px 20px;border:1.5px solid var(--glass-border);border-radius:8px;background:none;color:var(--page-text-color);cursor:pointer;font-size:13px">Nur dieser Call</button>'
      + '<button id="lnr-save-yes" style="padding:8px 20px;border:none;border-radius:8px;background:#00D4AA;color:var(--btn-primary-text);cursor:pointer;font-weight:700;font-size:13px">Im Profil speichern</button>'
      + '</div></div>';
    document.body.appendChild(overlay);

    document.getElementById('lnr-save-no').onclick = function () { overlay.remove(); };
    document.getElementById('lnr-save-yes').onclick = function () {
      fetch(endpoint, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
        body: JSON.stringify({ inhalt: newText })
      }).catch(function () {});
      // Update local state too
      var list = type === 'skript' ? state.skripte : state.openerItems;
      var item = list.find(function (i) { return i.id === itemId; });
      if (item) item.inhalt = newText;
      overlay.remove();
    };
    overlay.onclick = function (e) { if (e.target === overlay) overlay.remove(); };
  }

  // ── Consent-Modal (Meeting-Modus DSGVO Einwilligung) ──────────────────────
  var CONSENT_DEFAULT_TEXT = 'Kurz vorab \u2014 ich lasse mich gerade von einem Assistenzsystem unterstützen, das unser Gespräch mitliest und mir hilft, keine Audioaufnahme. Passt das für Sie?';

  function _showConsentModal(callback) {
    var overlay = document.getElementById('consent-overlay');
    var scriptEl = document.getElementById('consent-script');
    var acceptBtn = document.getElementById('consent-btn-accept');
    var rejectBtn = document.getElementById('consent-btn-reject');
    var cancelBtn = document.getElementById('consent-btn-cancel');
    if (!overlay || !scriptEl || !acceptBtn || !rejectBtn || !cancelBtn) {
      console.error('[NerveLauncher] Consent modal DOM elements missing');
      callback('cancelled');
      return;
    }

    // Phase 08.19: D-04 read-path — consent_text jetzt in daten.meta.consent_text
    // Fallback auf top-level consent_text fuer Profile die noch nicht migriert sind
    var _meta = state.profileDaten && state.profileDaten.meta;
    var text = (_meta && _meta.consent_text)
      ? _meta.consent_text
      : ((state.profileDaten && state.profileDaten.consent_text)
          ? state.profileDaten.consent_text
          : CONSENT_DEFAULT_TEXT);
    // Replace [Name] token with precallFormData.person if available
    if (state.precallFormData && state.precallFormData.person) {
      text = text.replace('[Name]', state.precallFormData.person);
    }
    scriptEl.textContent = text;

    overlay.classList.add('open');

    var previousFocus = document.activeElement;
    setTimeout(function () { acceptBtn.focus(); }, 50);

    var focusables = [cancelBtn, rejectBtn, acceptBtn];

    function closeModal() {
      overlay.classList.remove('open');
      acceptBtn.removeEventListener('click', onAccept);
      rejectBtn.removeEventListener('click', onReject);
      cancelBtn.removeEventListener('click', onCancel);
      document.removeEventListener('keydown', onKeydown);
      if (previousFocus && previousFocus.focus) {
        try { previousFocus.focus(); } catch (e) {}
      }
    }

    function onAccept() { closeModal(); callback('accepted'); }
    function onReject() { closeModal(); callback('rejected'); }
    function onCancel() { closeModal(); callback('cancelled'); }

    function onKeydown(e) {
      if (e.key === 'Escape') {
        e.preventDefault();
        onCancel();
        return;
      }
      if (e.key === 'Tab') {
        var idx = -1;
        for (var i = 0; i < focusables.length; i++) {
          if (focusables[i] === document.activeElement) { idx = i; break; }
        }
        if (e.shiftKey) {
          if (idx <= 0) {
            e.preventDefault();
            focusables[focusables.length - 1].focus();
          }
        } else {
          if (idx >= focusables.length - 1 || idx === -1) {
            e.preventDefault();
            focusables[0].focus();
          }
        }
      }
    }

    acceptBtn.addEventListener('click', onAccept);
    rejectBtn.addEventListener('click', onReject);
    cancelBtn.addEventListener('click', onCancel);
    document.addEventListener('keydown', onKeydown);
  }

  function _collectEditedTexts() {
    // If user edited inline, store the edited text for the session
    // Guard: only store if textarea has a value (Cross-AI-Finding #2 — don't overwrite with empty)
    var skTa = document.getElementById('lnr-skript-textarea');
    if (skTa && skTa.style.display !== 'none' && skTa.value) state._editedSkriptText = skTa.value;
    var opTa = document.getElementById('lnr-opener-textarea');
    if (opTa && opTa.style.display !== 'none' && opTa.value) state._editedOpenerText = opTa.value;
  }

  // ── Headset-Pflicht-Modal (DSGVO § 201 StGB) ───────────────────────────────
  function _showHeadsetModal(callback) {
    var overlay = document.getElementById('headset-overlay');
    var checkbox = document.getElementById('headset-checkbox');
    var confirmBtn = document.getElementById('headset-confirm');
    var cancelBtn = document.getElementById('headset-cancel');
    var whyLink = document.getElementById('headset-why-link');
    var legalHint = document.getElementById('headset-legal-hint');
    if (!overlay || !checkbox || !confirmBtn || !cancelBtn) return;

    // Reset state
    checkbox.checked = false;
    confirmBtn.disabled = true;
    legalHint.classList.remove('open');

    // Open modal
    overlay.classList.add('open');

    // Store previous focus to restore later
    var previousFocus = document.activeElement;

    // Focus checkbox on open
    setTimeout(function () { checkbox.focus(); }, 50);

    // Focusable elements for trap
    var focusables = [checkbox, cancelBtn, confirmBtn, whyLink];

    // ── Event handlers (stored for cleanup) ──
    function onCheckboxChange() {
      confirmBtn.disabled = !checkbox.checked;
    }

    function closeModal() {
      overlay.classList.remove('open');
      // Remove all listeners
      checkbox.removeEventListener('change', onCheckboxChange);
      confirmBtn.removeEventListener('click', onConfirm);
      cancelBtn.removeEventListener('click', onCancel);
      whyLink.removeEventListener('click', onWhyClick);
      document.removeEventListener('keydown', onKeydown);
      // Restore focus
      if (previousFocus && previousFocus.focus) {
        try { previousFocus.focus(); } catch (e) {}
      }
    }

    function onConfirm() {
      try { sessionStorage.setItem('headsetConfirmed', 'true'); } catch (e) {}
      closeModal();
      callback();
    }

    function onCancel() {
      closeModal();
      // No callback — call does NOT start
    }

    function onWhyClick() {
      legalHint.classList.toggle('open');
    }

    function onKeydown(e) {
      // Escape = Cancel
      if (e.key === 'Escape') {
        e.preventDefault();
        onCancel();
        return;
      }
      // Enter = Confirm (only when checkbox checked)
      if (e.key === 'Enter' && checkbox.checked) {
        e.preventDefault();
        onConfirm();
        return;
      }
      // Focus trap
      if (e.key === 'Tab') {
        var idx = -1;
        for (var i = 0; i < focusables.length; i++) {
          if (focusables[i] === document.activeElement) { idx = i; break; }
        }
        if (e.shiftKey) {
          if (idx <= 0) {
            e.preventDefault();
            focusables[focusables.length - 1].focus();
          }
        } else {
          if (idx >= focusables.length - 1 || idx === -1) {
            e.preventDefault();
            focusables[0].focus();
          }
        }
      }
    }

    // Wire listeners
    checkbox.addEventListener('change', onCheckboxChange);
    confirmBtn.addEventListener('click', onConfirm);
    cancelBtn.addEventListener('click', onCancel);
    whyLink.addEventListener('click', onWhyClick);
    document.addEventListener('keydown', onKeydown);
  }

  // ── Start Call ─────────────────────────────────────────────────────────────
  // CRITICAL: called from click handler (user gesture for getUserMedia + PiP)
  function startCall(setProfile) {
    // Phase 08.23.2.D Hotfix 2026-05-27 — lastCallId beim Call-START zuruecksetzen.
    // Sonst feuert state.socket.on('connect') -> /api/calls/latest_outcome mit der
    // ALTEN call_id, holt das alte outcome (oder null), rendert PostCall-UX direkt
    // beim Call-START. Plan-06-Reconnect-Fallback war fuer Mid-PostCall-Reconnect
    // gedacht, nicht fuer normalen Call-Beginn.
    state.lastCallId = null;
    state.lastConvId = null;

    // ── Headset-Pflicht-Gate (Cold Call only, per D-01/POLISH-16) ──
    if (state.mode === 'cold_call' && !sessionStorage.getItem('headsetConfirmed')) {
      _showHeadsetModal(function () {
        startCall(setProfile);
      });
      return;
    }

    // ── Consent-Gate (Meeting only, per Phase 06.5 / POLISH-16 follow-up) ──
    if (state.mode === 'meeting' && !state.consentDone) {
      _showConsentModal(function (result) {
        if (result === 'accepted') {
          state.consentDone = true;
          startCall(setProfile);
        } else if (result === 'rejected') {
          state.mode = 'cold_call';
          state.consentDone = true;
          startCall(setProfile);
        }
        // result === 'cancelled' -> do nothing, user stays on Step 5
      });
      return;
    }

    // OD-01 Option A: Pitch/Skript-Priorität für Teleprompter-Übergabe an _openPipAndMic()
    // selectedSkriptId gesetzt → _openPipAndMic() nutzt eigene Auflösung (state._editedSkriptText > skripte)
    // nur selectedPitchId gesetzt (kein Skript) → Pitch-Inhalt als Fallback vorberechnen
    // Ergebnis in state._resolvedTeleprompterSkript — _openPipAndMic() liest es zuerst und löscht es
    if (!state.selectedSkriptId && state.selectedPitchId) {
      var selPitch = (state.openerItems || []).find(function (o) { return o.id === state.selectedPitchId; });
      if (selPitch) {
        state._resolvedTeleprompterSkript = { id: state.selectedPitchId, inhalt: selPitch.inhalt || '' };
      }
    }
    // wenn selectedSkriptId gesetzt: _resolvedTeleprompterSkript nicht setzen
    // → _openPipAndMic() nutzt dann seine eigene Auflösung via state._editedSkriptText / selectedSkriptId

    close();

    // Set profile server-side if changed (fire and forget)
    if (setProfile && state.activeProfileId) {
      fetch('/api/set_profile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
        body: JSON.stringify({ profile_id: state.activeProfileId })
      }).catch(function () {});
    }

    // Load Socket.IO CDN if not already loaded, then proceed
    _ensureSocketIO(function () {
      _openPipAndMic();
    });
  }

  function _ensureSocketIO(cb) {
    if (typeof io !== 'undefined') { cb(); return; }
    var script = document.createElement('script');
    // Phase 06.6 / POLISH-19: Lokal gehostet statt CDN (DSGVO: keine Third-Party-Requests).
    // Version 4.7.2 ist byte-identisch zum früheren cdnjs-Load.
    script.src = '/static/vendor/socket.io.min.js';
    script.onload = function () { cb(); };
    script.onerror = function () { console.error('[NerveLauncher] Socket.IO local load failed'); };
    document.head.appendChild(script);
  }

  // Called after Socket.IO is ready — still within the click handler call stack
  function _openPipAndMic() {
    // Connect socket — 06.1-r2 PERF-1: WebSocket-Upgrade erlaubt. Vorher
    // erzwang transports:['polling'] bei jedem 100ms audio_chunk einen HTTP-POST
    // (+ server long-poll GETs) = ~170 req/min. Mit WS-Upgrade: 1 persistente
    // Connection, Audio-Chunks als WS-Frames, fast null Overhead.
    state.socket = io({
      reconnectionAttempts: 3,
      reconnectionDelay: 2000,
      transports: ['websocket', 'polling']
    });

    _registerSocketEvents();

    // MUST be sequential: PiP first (consumes user gesture), then mic
    // Both need user activation but PiP is stricter about it
    if (!window.documentPictureInPicture) {
      console.warn('[NerveLauncher] Document PiP not supported');
      // Fallback: start mic without PiP
      _startMicOnly();
      return;
    }

    window.documentPictureInPicture.requestWindow({ width: 480, height: 900 })
      .then(function (pipWindow) {
        state.pipWindow = pipWindow;
        _setupPipWindow(pipWindow);
        // NOW start mic — after PiP is open
        _startMicOnly();
      })
      .catch(function (err) {
        console.error('[NerveLauncher] PiP requestWindow error:', err);
        // Fallback: start mic without PiP
        _startMicOnly();
      });
  }

  function _startMicOnly() {
    navigator.mediaDevices.getUserMedia({ audio: true })
      .then(function (stream) {
        state.micStream = stream;
        _startAudio();
        // Phase 06: No polling — streaming events arrive via state.socket automatically (D-09)
      })
      .catch(function (err) {
        console.error('[NerveLauncher] getUserMedia error:', err);
        alert('Mikrofon-Zugriff verweigert. Bitte Berechtigung erteilen und erneut versuchen.');
        _cleanup();
      });
  }

  async function _startAudio() {
    try {
      var audioCtx = new AudioContext({ sampleRate: 16000 });
      if (audioCtx.state === 'suspended') await audioCtx.resume();
      await audioCtx.audioWorklet.addModule('/static/audio-processor.js');
      var source = audioCtx.createMediaStreamSource(state.micStream);
      var workletNode = new AudioWorkletNode(audioCtx, 'audio-processor');
      workletNode.port.onmessage = function (e) {
        if (state.micStarted && state.socket) {
          state.socket.emit('audio_chunk', e.data);
        }
      };
      source.connect(workletNode);
      workletNode.connect(audioCtx.destination);
      // D-16: AnalyserNode parallel zum Worklet — für Mic-Level-Bars, stoert Worklet-Streaming nicht
      var analyser = audioCtx.createAnalyser();
      analyser.fftSize = 256;
      analyser.smoothingTimeConstant = 0.7;
      source.connect(analyser);
      state.micAnalyser = analyser;
      state.micMuted = false;
      _startMicLevelLoop();
      state.audioCtx = audioCtx;
      state.workletNode = workletNode;
      state.micStarted = true;
      var briefingText = (state.precallBriefing && state.precallBriefing.text) ? state.precallBriefing.text : null;
      // Get skript content for backend teleprompter context
      var skriptInhalt = '';
      var skriptBlöcke = [];
      // OD-01: Pitch-Fallback-Inhalt aus startCall() (nur wenn kein selectedSkriptId + selectedPitchId gesetzt war)
      if (state._resolvedTeleprompterSkript) {
        skriptInhalt = state._resolvedTeleprompterSkript.inhalt || '';
        state._resolvedTeleprompterSkript = null;
      } else if (state._editedSkriptText) {
        skriptInhalt = state._editedSkriptText;
      } else if (state.selectedSkriptId && state.skripte.length > 0) {
        var sk = state.skripte.find(function (s) { return s.id === state.selectedSkriptId; });
        if (sk && sk.inhalt) skriptInhalt = sk.inhalt;
      }
      if (skriptInhalt) {
        skriptBlöcke = skriptInhalt.split(/\n\n+/).filter(function (b) { return b.trim(); });
      }
      // D-03: Opener als Block 0, damit KI-Position-Erkennung (skript_position) Phase 0 = Opener kennt
      var openerFuerKi = '';
      if (state._editedOpenerText) openerFuerKi = state._editedOpenerText;
      else if (state.selectedOpenerId && state.openerItems) {
        var selOp2 = state.openerItems.find(function (o) { return o.id === state.selectedOpenerId; });
        if (selOp2) openerFuerKi = selOp2.inhalt;
      }
      if (openerFuerKi) skriptBlöcke = [openerFuerKi].concat(skriptBlöcke);

      // Phase 08 D-14: Anrede aus precallFormData (Default 'Sie') im session-start-payload.
      // Backend-Whitelist {'Du', 'Sie'} filtert ungueltige Werte server-side.
      var anredeForSession = (state.precallFormData && state.precallFormData.anrede === 'Du') ? 'Du' : 'Sie';
      state.socket.emit('start_live_session', {
        mode: state.mode || 'cold_call',
        precall_briefing: briefingText,
        skript_inhalt: skriptInhalt || null,
        skript_bloecke: skriptBlöcke.length > 0 ? skriptBlöcke : null,
        anrede: anredeForSession,
        vorwissen_level: state.vorwissenLevel || null  // D-05: Vorwissen-Picker value
      });
      console.log('[NerveLauncher] Mic started, mode:', state.mode);
    } catch (err) {
      console.error('[NerveLauncher] Audio worklet error:', err);
    }
  }

  function _startMicLevelLoop() {
    var analyser = state.micAnalyser;
    if (!analyser) return;
    var buffer = new Uint8Array(analyser.frequencyBinCount);
    var lastTick = 0;
    var N = 4;
    var perBar = Math.floor(buffer.length / N);
    function tick(ts) {
      if (!state.micAnalyser) return;  // gestoppt
      if (ts - lastTick >= 60) {  // ~16 fps Drosselung (D-16)
        lastTick = ts;
        analyser.getByteFrequencyData(buffer);
        var bars = new Array(N);
        for (var i = 0; i < N; i++) {
          var sum = 0;
          for (var j = 0; j < perBar; j++) sum += buffer[i * perBar + j];
          bars[i] = (sum / perBar) / 255;  // normalisiert 0..1
        }
        _updateMicBarsDom(bars);
      }
      state.micLevelRafId = requestAnimationFrame(tick);
    }
    state.micLevelRafId = requestAnimationFrame(tick);
  }

  function _updateMicBarsDom(bars) {
    // Bei Mute: Balken bleiben flach (15%), nicht animiert
    if (state.micMuted) return;
    for (var i = 0; i < bars.length; i++) {
      var el = pipEl('pip-mic-bar-' + i);
      if (el) el.style.height = (Math.max(0.15, bars[i]) * 100) + '%';
    }
  }

  function _toggleMicMute() {
    if (!state.micStream) return;
    var tracks = state.micStream.getAudioTracks();
    if (!tracks.length) return;
    var nowMuted = tracks[0].enabled;  // wenn aktuell enabled → wir muten
    tracks.forEach(function (t) { t.enabled = !nowMuted; });
    state.micMuted = nowMuted;
    // 06.2: Backend über Mute-Zustand informieren, damit Keyword-Matcher pausiert
    if (state.socket && state.socket.connected) {
      state.socket.emit('mute_mic', { muted: !!state.micMuted });
    }
    _updateMicIndicatorState();
    console.log('[NerveLauncher] Mic ' + (state.micMuted ? 'muted' : 'unmuted') + ' (track.enabled toggle, no session restart)');
  }

  function _updateMicIndicatorState() {
    var indicator = pipEl('pip-mic-indicator');
    if (!indicator) return;
    indicator.classList.toggle('pip-mic-muted', !!state.micMuted);
    if (state.micMuted) {
      for (var i = 0; i < 4; i++) {
        var b = pipEl('pip-mic-bar-' + i);
        if (b) b.style.height = '15%';
      }
    }
  }

  function _setupPipWindow(pipWindow) {
    pipWindow.document.title = 'NERVE — Live';

    // Copy stylesheets
    Array.from(document.styleSheets).forEach(function (ss) {
      try {
        var rules = Array.from(ss.cssRules).map(function (r) { return r.cssText; }).join('');
        var style = pipWindow.document.createElement('style');
        style.textContent = rules;
        pipWindow.document.head.appendChild(style);
      } catch (e) {
        if (ss.href) {
          var link = pipWindow.document.createElement('link');
          link.rel = 'stylesheet';
          link.href = ss.href;
          pipWindow.document.head.appendChild(link);
        }
      }
    });

    // Body styles — 06.1-r2 CLEANUP: Slider raus, solide slate-50 Background wieder
    var body = pipWindow.document.body;
    body.style.margin = '0';
    body.style.background = 'var(--pip-bg)';
    body.style.color = 'var(--page-text-color,#e8ecf4)';
    body.style.fontFamily = "'Inter',sans-serif";
    body.style.display = 'flex';
    body.style.flexDirection = 'column';
    body.style.height = '100vh';
    body.style.overflow = 'hidden';

    // Move pip-live-window into PiP
    var liveWin = document.getElementById('pip-live-window');
    if (liveWin) {
      liveWin.style.display = 'flex';
      liveWin.style.flexDirection = 'column';
      liveWin.style.height = '100%';
      pipWindow.document.body.appendChild(liveWin);
    }

    // Load Lucide in PiP (POLISH-19: lokal statt CDN)
    var lucide = pipWindow.document.createElement('script');
    lucide.src = '/static/vendor/lucide.min.js';
    lucide.onload = function () {
      if (pipWindow.lucide) pipWindow.lucide.createIcons();
    };
    pipWindow.document.head.appendChild(lucide);

    // Force PiP size — requestWindow hints werden von Chrome manchmal ignoriert
    try { pipWindow.resizeTo(480, 900); } catch(e) {}

    // Wire PiP button events
    _wirePipButtons(pipWindow);

    // Initialize content
    _initPipLive();

    // Start timer
    _startTimer();

    // On PiP close: move content back
    // BUG-11 FIX: pagehide fires async after pipWindow.close() and can race against
    // the next call already being started. Guard: only stop mic if state.pipWindow
    // still points to THIS window. If _cleanup()/nextCall() already ran,
    // state.pipWindow is null or points to the new call's window -- skip mic teardown.
    pipWindow.addEventListener('pagehide', function () {
      var el = pipWindow.document.getElementById('pip-live-window');
      if (el) {
        el.style.display = 'none';
        document.body.appendChild(el);
      }
      // Only clean up mic/state if this pagehide is for the currently-active PiP.
      // If state.pipWindow !== pipWindow, _cleanup() already ran (nextCall path) or
      // a new call is already live -- touching mic state here would abort the new call.
      if (state.pipWindow === pipWindow) {
        state.pipWindow = null;
        if (state.micStarted) {
          _stopMic();
        }
      }
    });
  }

  function _wirePipButtons(pipWindow) {
    // 06.1-r2 round3: EVENT-DELEGATION am pip-Document-Level — bulletproof gegen
    // alle DOM-Re-Renders und PiP-Context-Quirks. EIN Listener fängt alle Klicks
    // auf Beenden und EWB-Buttons per .closest()-Matching.
    pipWindow.document.addEventListener('click', function (ev) {
      var t = ev.target;
      if (!t || typeof t.closest !== 'function') return;

      // 08.23.2.D.UX.4 (B-02/F10): Single-Click auf Beenden beendet NICHT mehr —
      // der Call endet ausschliesslich ueber 600ms Press-and-Hold (Pointer-Delegation
      // unten) bzw. Keyboard-2nd-Press. Den click-Zweig hier nur noch konsumieren
      // (preventDefault), damit kein Default-Verhalten feuert; KEIN endCall().
      var beenden = t.closest('#nlp-btn-beenden');
      if (beenden) {
        ev.preventDefault();
        ev.stopPropagation();
        return;
      }

      var ewb = t.closest('.pip-ewb-btn');
      if (ewb) {
        ev.preventDefault();
        ev.stopPropagation();
        var typ = ewb.getAttribute('data-typ');
        console.log('[NerveLauncher] EWB click (delegation):', typ);
        ewb.classList.add('pip-ewb-flashing');
        setTimeout(function () { ewb.classList.remove('pip-ewb-flashing'); }, 400);
        try { _triggerEwb(typ, ewb); } catch (e) { console.error('[NerveLauncher] EWB err:', e); }
        return;
      }

      var mic = t.closest('#pip-mic-indicator');
      if (mic) {
        ev.preventDefault();
        _toggleMicMute();
        return;
      }

      var nextBtn = t.closest('#nlp-btn-next-call');
      if (nextBtn) {
        // BUG-11 r5 SAFETY: Nur akzeptieren wenn Postcall-Section wirklich sichtbar ist.
        // Defense-in-depth falls eine stale endCall-Response die Section während eines
        // laufenden Calls unsichtbar über die Live-UI legt (der Haupt-Fix sitzt im
        // endCall-fetch-handler per callGen-Guard).
        var postcallEl = pipEl('nlp-section-postcall');
        if (!postcallEl || postcallEl.style.display === 'none' || state.micStarted) {
          console.log('[NerveLauncher] nextBtn match ignoriert — Postcall nicht aktiv oder Call läuft');
          ev.preventDefault();
          return;
        }
        ev.preventDefault();
        nextCall();
        return;
      }

      var detailsBtn = t.closest('#nlp-btn-details');
      if (detailsBtn) { ev.preventDefault(); showDetails(); return; }

      // Phase 08.20.3: Briefing Tab toggle
      if (ev.target.closest('[data-briefing-toggle]')) {
        var tabBody = pipEl('pip-briefing-tab-body');
        if (tabBody) {
          var isExpanded = _isBriefingTabExpanded();
          if (isExpanded) {
            _collapseBriefingTab();
          } else {
            // Cancel education hint timer if still running
            var tabHeader = pipEl('pip-briefing-tab-header');
            if (tabHeader && tabHeader._introTimer) {
              clearTimeout(tabHeader._introTimer);
              tabHeader._introTimer = null;
              localStorage.setItem('nerve.seen_briefing_tab_intro', '1');
            }
            _expandBriefingTab();
          }
        }
        ev.stopPropagation();
        return;
      }

      // Phase 08.19.5.6.3: Analyse-Fließtext toggle
      if (ev.target.closest('[data-analyse-toggle]')) {
        var analyseBody = pipEl('pip-analyse-body');
        var analyseIcon = pipEl('pip-analyse-icon');
        if (analyseBody) {
          // Browser normalisiert maxHeight beim Auslesen zu '0px' — numerischer Check robuster
          var analyseExpanded = parseFloat(analyseBody.style.maxHeight) > 0;
          if (analyseExpanded) {
            analyseBody.style.maxHeight = '0';
            if (analyseIcon) { analyseIcon.textContent = '▶'; }
          } else {
            analyseBody.style.maxHeight = '999px';
            if (analyseIcon) { analyseIcon.textContent = '▼'; }
          }
        }
        ev.stopPropagation();
        return;
      }

      // Bug fix: Empfehlungen-Fliesstext toggle (analog data-analyse-toggle)
      if (ev.target.closest('[data-empfehlungen-toggle]')) {
        var empfBody = pipEl('pip-empfehlungen-body');
        var empfIcon = pipEl('pip-empfehlungen-icon');
        if (empfBody) {
          // Browser normalisiert maxHeight beim Auslesen zu '0px' — numerischer Check robuster
          var empfExpanded = parseFloat(empfBody.style.maxHeight) > 0;
          if (empfExpanded) {
            empfBody.style.maxHeight = '0';
            if (empfIcon) { empfIcon.textContent = '▶'; }
          } else {
            empfBody.style.maxHeight = '999px';
            if (empfIcon) { empfIcon.textContent = '▼'; }
          }
        }
        ev.stopPropagation();
        return;
      }

      // BUG2 FIX: Anrede toggle — data-anrede on pip-anrede-du / pip-anrede-sie
      // onlick attrs removed from base.html (fired in PiP-window scope without access
      // to window.pipSetAnrede on main window). Event delegation runs in main-window
      // closure where state/socket are available.
      var anredeBtn = t.closest('[data-anrede]');
      if (anredeBtn) {
        ev.preventDefault();
        var anrede = anredeBtn.getAttribute('data-anrede');
        var duBtn = pipEl('pip-anrede-du');
        var sieBtn = pipEl('pip-anrede-sie');
        var badge = pipEl('pip-anrede-badge');
        if (duBtn) duBtn.classList.toggle('active', anrede === 'du');
        if (sieBtn) sieBtn.classList.toggle('active', anrede === 'sie');
        if (badge) badge.style.display = 'none';
        if (state.socket && state.socket.connected) {
          state.socket.emit('set_anrede', { anrede: anrede });
        }
        console.log('[NerveLauncher] Anrede set:', anrede);
        return;
      }

      // BUG2 FIX: Vorwissen indicator click (opens edit panel)
      var vorwissenEditTrigger = t.closest('[data-vorwissenedit]');
      if (vorwissenEditTrigger) {
        ev.preventDefault();
        var indicator = pipEl('pip-vorwissen-indicator');
        var edit = pipEl('pip-vorwissen-edit');
        if (indicator) indicator.style.display = 'none';
        if (edit) edit.style.display = 'block';
        console.log('[NerveLauncher] Vorwissen edit opened');
        return;
      }

      // BUG2 FIX: Vorwissen pill selection — data-val on .pip-vorwissen-pill
      var vorwissenPill = t.closest('.pip-vorwissen-pill');
      if (vorwissenPill) {
        ev.preventDefault();
        var val = vorwissenPill.getAttribute('data-val');
        var labels = { niedrig: 'Wenig', mittel: 'Vertraut', hoch: 'Kennt uns', 'null': 'Weiß nicht' };
        var labelEl = pipEl('pip-vorwissen-label');
        var editPanel = pipEl('pip-vorwissen-edit');
        var indicatorPanel = pipEl('pip-vorwissen-indicator');
        if (labelEl) labelEl.textContent = labels[val] || 'Weiß nicht';
        if (editPanel) editPanel.style.display = 'none';
        if (indicatorPanel) indicatorPanel.style.display = 'flex';
        var _pipDoc = (state.pipWindow && !state.pipWindow.closed) ? state.pipWindow.document : document;
        _pipDoc.querySelectorAll('#pip-vorwissen-edit .pip-vorwissen-pill').forEach(function (btn) {
          btn.classList.toggle('active', btn.dataset.val === (val || 'null'));
        });
        if (state.socket && state.socket.connected) {
          state.socket.emit('set_vorwissen', { level: val === 'null' ? null : val });
        }
        console.log('[NerveLauncher] Vorwissen set:', val);
        return;
      }
    }, true);  // capture phase — vor allen anderen Handlern
    console.log('[NerveLauncher] PiP click-delegation wired');

    // ── 08.23.2.D.UX.4 (B-02/F10) — Beenden Hold-to-end, rebuild-sicher ─────────
    // Pointer-Delegation auf dem PiP-Document (closest('#nlp-btn-beenden')) — ueberlebt
    // jeden PiP-Rebuild (der Button-Knoten wird neu erzeugt, der Document-Listener nicht).
    // KEIN one-time addEventListener auf dem Button-Element (F10). Hold-State in der
    // _wirePipButtons-Closure, damit Doppel-Trigger (Click+Hold) ausgeschlossen ist.
    var holdTimer = null;
    var holdFired = false;
    var keyArmedAt = 0;
    var keyResetTimer = null;

    function _beendenLabelEl() {
      // Label-Span im Button ODER der Button selbst (Text wird ueberschrieben + restauriert)
      var b = pipEl('nlp-btn-beenden');
      return b || null;
    }
    function _resetHoldVisual() {
      var b = pipEl('nlp-btn-beenden');
      if (b) {
        b.classList.remove('pip-beenden-holding');
        b.textContent = 'Beenden';
      }
    }
    function _fireEndCall() {
      if (holdFired) return;
      holdFired = true;
      _resetHoldVisual();
      try { endCall(); } catch (e) { console.error('[NerveLauncher] endCall err:', e); }
    }

    pipWindow.document.addEventListener('pointerdown', function (ev) {
      var t = ev.target;
      if (!t || typeof t.closest !== 'function') return;
      if (!t.closest('#nlp-btn-beenden')) return;
      ev.preventDefault();
      holdFired = false;
      var b = pipEl('nlp-btn-beenden');
      if (b) {
        b.classList.add('pip-beenden-holding');
        b.textContent = 'Halten zum Beenden…';
      }
      if (holdTimer) { clearTimeout(holdTimer); }
      holdTimer = setTimeout(function () {
        holdTimer = null;
        // 120ms solid-hover-Flash, dann endCall
        var bb = pipEl('nlp-btn-beenden');
        if (bb) bb.classList.add('pip-beenden-holding');
        setTimeout(_fireEndCall, 120);
      }, 600);
    }, true);

    function _cancelHold(ev) {
      var t = ev && ev.target;
      // pointerup/leave/cancel: nur abbrechen wenn noch nicht gefeuert
      if (holdTimer) { clearTimeout(holdTimer); holdTimer = null; }
      if (!holdFired) { _resetHoldVisual(); }
    }
    pipWindow.document.addEventListener('pointerup', _cancelHold, true);
    pipWindow.document.addEventListener('pointerleave', _cancelHold, true);
    pipWindow.document.addEventListener('pointercancel', _cancelHold, true);

    // Keyboard-Aequivalent (B-02): Enter/Space auf fokussiertem Beenden -> 2nd-Press binnen 2s.
    pipWindow.document.addEventListener('keydown', function (ev) {
      var t = ev.target;
      if (!t || typeof t.closest !== 'function') return;
      if (!t.closest('#nlp-btn-beenden')) return;
      if (ev.key !== 'Enter' && ev.key !== ' ' && ev.key !== 'Spacebar') return;
      ev.preventDefault();
      var now = Date.now();
      if (keyArmedAt && (now - keyArmedAt) <= 2000) {
        // 2. Druck binnen 2s -> beenden
        keyArmedAt = 0;
        if (keyResetTimer) { clearTimeout(keyResetTimer); keyResetTimer = null; }
        holdFired = false;
        _fireEndCall();
        return;
      }
      // 1. Druck: armen + Hinweis-Label
      keyArmedAt = now;
      var b = pipEl('nlp-btn-beenden');
      if (b) b.textContent = 'Nochmal drücken zum Beenden';
      if (keyResetTimer) { clearTimeout(keyResetTimer); }
      keyResetTimer = setTimeout(function () {
        keyArmedAt = 0;
        keyResetTimer = null;
        var bb = pipEl('nlp-btn-beenden');
        if (bb) bb.textContent = 'Beenden';
      }, 2000);
    }, true);
    console.log('[NerveLauncher] PiP beenden hold-delegation wired (B-02/F10)');
  }

  function _initPipLive() {
    // Set mode badge
    var badge = pipEl('nlp-mode-badge');
    if (badge) badge.textContent = state.mode === 'meeting' ? 'Meeting' : 'Cold Call';

    // Phase 06.5: Consent ist jetzt Launcher-Gate (vor Call-Start). PiP startet immer direkt im Live-View.
    _showPipLive();

    // Render EWB buttons
    _renderEwbButtons();

    // ── Phase 08.19.5.6.2: PiP Briefing Tab (automatisch wenn Briefing vorhanden) ──
    var briefingTab = pipEl('pip-briefing-tab');
    if (briefingTab) {
      if (state.precallBriefing &&
          state.precallBriefing.firmenname) {
        // Show tab and set title
        briefingTab.style.display = 'block';
        var titleEl = pipEl('pip-briefing-tab-title');
        if (titleEl) titleEl.textContent = state.precallBriefing.firmenname;
        // Phase 08.19.5.6.3: Cheat-Sheet render (Eckdaten + Empfehlungen + kollabierter Fließtext)
        var contentEl = pipEl('pip-briefing-tab-content');
        if (contentEl) {
          var cheatHtml = '';
          // ── Sektion 1: Eckdaten-Block (R-01) ──
          var briefingFields = state.precallBriefing.fields || {};
          var fieldDefs = [
            { key: 'geschaeftsfuehrer', label: 'GF' },
            { key: 'branche',           label: 'Branche' },
            { key: 'mitarbeiterzahl',   label: 'MA' },
            { key: 'hauptprodukt',      label: 'Produkt' }
          ];
          var eckdatenRows = '';
          for (var fi = 0; fi < fieldDefs.length; fi++) {
            var fd = fieldDefs[fi];
            var f = briefingFields[fd.key];
            // Bug fix: always show all 4 Eckdaten fields — use '—' when not_found
            var fVal = (f && f.confidence !== 'not_found' && f.value) ? f.value : '—';
            eckdatenRows += '<div class="pip-cheat-row"><span>' + fd.label + ':</span><span>' + fVal + '</span></div>';
          }
          if (eckdatenRows) {
            cheatHtml += eckdatenRows;
          }
          // ── Sektion 2: Empfehlungen-Block (R-02) ──
          var empf = state.precallBriefing.empfehlungen || '';
          if (empf && empf.trim()) {
            cheatHtml += '<hr class="pip-cheat-sep">';
            // Bug fix: strip leading H1 that duplicates the section heading
            var empfClean = empf.replace(/^#[^\n]*\n?/m, '');
            // Bug fix: collapsible Empfehlungen section (default expanded)
            cheatHtml += '<button class="pip-analyse-toggle" data-empfehlungen-toggle="1"><span id="pip-empfehlungen-icon">▼</span> Empfehlungen</button>';
            cheatHtml += '<div id="pip-empfehlungen-body" style="max-height:999px;overflow:hidden;transition:max-height 200ms ease;">';
            cheatHtml += mdToHtml(empfClean);
            cheatHtml += '</div>';
          }
          // ── Sektion 3: Fließtext kollabiert (R-03) ──
          var analyseText = state.precallBriefing.text || '';
          cheatHtml += '<hr class="pip-cheat-sep">';
          cheatHtml += '<button class="pip-analyse-toggle" data-analyse-toggle="1"><span id="pip-analyse-icon">▶</span> Analyse aufklappen</button>';
          cheatHtml += '<div id="pip-analyse-body" style="max-height:0;overflow:hidden;transition:max-height 200ms ease;">';
          cheatHtml += mdToHtml(analyseText);
          cheatHtml += '</div>';
          contentEl.innerHTML = cheatHtml;
        }
        // Education hint: first Modus-B call
        if (!localStorage.getItem('nerve.seen_briefing_tab_intro')) {
          setTimeout(function () {
            _expandBriefingTab();
            var introTimer = setTimeout(function () {
              _collapseBriefingTab();
              localStorage.setItem('nerve.seen_briefing_tab_intro', '1');
            }, 3000);
            // Cancel if user interacts with tab within 3s
            var tabHeader = pipEl('pip-briefing-tab-header');
            if (tabHeader) {
              tabHeader._introTimer = introTimer;
            }
          }, 500);
        }
      } else {
        briefingTab.style.display = 'none';
      }
    }
  }

  // ── Phase 08.20.3: Briefing Tab toggle helpers ─────────────────────────────
  function _expandBriefingTab() {
    var body = pipEl('pip-briefing-tab-body');
    var icon = pipEl('pip-briefing-tab-icon');
    if (body) { body.style.maxHeight = '300px'; body.style.overflowY = 'auto'; }
    if (icon) { icon.textContent = '▼'; }
  }

  function _collapseBriefingTab() {
    var body = pipEl('pip-briefing-tab-body');
    var icon = pipEl('pip-briefing-tab-icon');
    if (body) { body.style.maxHeight = '0'; body.style.overflowY = 'hidden'; }
    if (icon) { icon.textContent = '▶'; }
  }

  function _isBriefingTabExpanded() {
    var body = pipEl('pip-briefing-tab-body');
    if (!body) return false;
    var mh = body.style.maxHeight;
    // Bug-D fix: browsers return '0px' (not '0') for inline style max-height:0.
    // Without this, first click sees isExpanded=true and collapses (no-op). Needs 2 clicks.
    return mh !== '' && mh !== '0' && mh !== '0px';
  }

  function _showPipLive() {
    // Belt-and-suspenders: reset all live UI state first. Even if endCall() already
    // called _resetLiveState(), this guarantees a clean start for call N+1 regardless
    // of how we arrived here (nextCall, consent-accept path, etc.).
    _resetLiveState();
    var liveSection = pipEl('pip-section-live');
    var beendenBtn = pipEl('nlp-btn-beenden');
    // 06.1-r2 BUG-13: Postcall-Section explizit verstecken — verhindert dass die
    // alte "Kein Gespräch erkannt"-View auf dem neuen Call liegen bleibt.
    var postcallSection = pipEl('nlp-section-postcall');
    if (postcallSection) postcallSection.style.display = 'none';
    // 08.23.2.D.UX.4: Ladebalken-1-View des vorherigen Calls verstecken.
    var lb1 = pipEl('pip-ladebalken1');
    if (lb1) lb1.style.display = 'none';
    if (liveSection) liveSection.style.display = 'flex';
    if (beendenBtn) beendenBtn.style.display = 'inline-block';
    // 06.1-r2 BUG-13: Header wieder einblenden (Beenden wurde in _showPostcallRaw versteckt).
    var pipHeader = pipEl('pip-header');
    if (pipHeader) pipHeader.style.display = '';
    // Score-Display zurücksetzen falls Empty-State das :none gesetzt hat
    var scoreEl = pipEl('nlp-postcall-score');
    if (scoreEl) scoreEl.style.display = '';
    var detailsBtn = pipEl('nlp-btn-details');
    if (detailsBtn) detailsBtn.style.display = '';

    // BUG-A FIX: _showPostcallRaw() setzt nlp-ewb-row display:none.
    // _renderEwbButtons() setzt nur innerHTML, nicht display — hier zurücksetzen
    // damit die EWB-Leiste im nächsten Call sichtbar ist.
    var ewbRow = pipEl('nlp-ewb-row');
    if (ewbRow) ewbRow.style.display = '';

    // D-13: Mic-Indikator einschalten (erst im Live-Zustand sichtbar)
    var micBtnShow = pipEl('pip-mic-indicator');
    if (micBtnShow) micBtnShow.style.display = 'inline-flex';

    // D-03: Opener wandert in den Teleprompter als Block 0 — Slot A bleibt leer für erste KI-Antwort
    // (keine Slot-0-Zuweisung mehr; beide Slots starten mit "Warte auf Gesprächsinhalt..." Default-Markup)

    // Initialize teleprompter (D-11, D-12)
    _initTeleprompter();
  }

  function _renderEwbButtons() {
    var row = pipEl('nlp-ewb-row');
    if (!row) return;
    // R1-fix: Phase 08.20 schema v4 uses einwaende_detail; fall back to einwaende for v3 profiles.
    var einwaende = (state.profileDaten && (state.profileDaten.einwaende_detail || state.profileDaten.einwaende)) || [];
    if (!einwaende.length) { row.innerHTML = ''; return; }
    // 06.1-r2 BUG-14c final: Button-Label = kurzlabel ODER kategorie (nur diese zwei).
    // Kein Truncation, kein name/einwand-Fallback. Dedup per Label (case-insensitive) —
    // mehrere Einwände ohne kurzlabel mit gleicher Kategorie kollabieren bewusst zu
    // einem Button (Fix: kurzlabel im Profil pflegen für distinkte Buttons).
    // data-typ = Label, matched gegen dieselbe Chain in _triggerEwb + Backend.
    var seen = {};
    var items = [];
    for (var i = 0; i < einwaende.length && items.length < 5; i++) {
      var e = einwaende[i];
      var label;
      if (typeof e === 'string') {
        label = e.trim();
      } else {
        label = ((e.kurzlabel || e.short_label || e.kategorie || '').trim());
      }
      if (!label) continue;
      var key = label.toLowerCase();
      if (seen[key]) continue;
      seen[key] = true;
      items.push(label);
    }
    var html = items.map(function (label) {
      return '<button type="button" class="pip-ewb-btn" data-typ="' + escHtml(label) + '">' + escHtml(label) + '</button>';
    }).join('');
    row.innerHTML = html;
    // Klicks werden über Event-Delegation im pip-Document gefangen (_wirePipButtons).
  }

  function _triggerEwb(typ, btn) {
    // 06.1-r2 r3: Manual-EWB = deterministisch aus profile.einwaende rendern.
    // Keine Claude-Call-Latenz, keine leeren Slots wenn Claude einwand=False meldet.
    // Backend bekommt 'manual_ewb' nur noch für Klick-Tracking (postcall-Analytics).
    console.log('[NerveLauncher] EWB trigger:', typ);
    // R1-fix: Phase 08.20 schema v4 uses einwaende_detail; fall back to einwaende for v3 profiles.
    var einwaende = (state.profileDaten && (state.profileDaten.einwaende_detail || state.profileDaten.einwaende)) || [];
    var match = null;
    var typL = (typ || '').toLowerCase().trim();
    // 06.1-r2 BUG-14c: Match gegen kurzlabel ODER kategorie — gleiche Chain wie _renderEwbButtons.
    for (var i = 0; i < einwaende.length; i++) {
      var e = einwaende[i];
      if (typeof e === 'string') { if (e.toLowerCase() === typL) { match = { kategorie: e }; break; } continue; }
      var label = (e.kurzlabel || e.short_label || e.kategorie || '').toLowerCase().trim();
      if (label === typL) { match = e; break; }
    }
    var fake = {
      einwand: true,
      typ: typ,
      gegenargument_1: (match && (match.gegenargument_1 || match.gegenargument || match.text)) || ('Kein hinterlegtes Gegenargument f\u00fcr "' + typ + '" im Profil.'),
    };
    var body = pipEl('pip-slot-body-0');
    if (body) body.classList.remove('pip-streaming');
    _renderSlotResult(0, fake);

    // 06.1-r2 r4: Slot 1 bekommt gleich Placeholder bis Haiku-Variante streamt.
    var slot1Body = pipEl('pip-slot-body-1');
    if (slot1Body) {
      slot1Body.textContent = 'Variante wird gebaut\u2026';
      slot1Body.classList.add('pip-streaming');
    }
    // Klick + Variante-Request ans Backend. Backend loggt Klick (ewb_clicks für
    // postcall-Analytics) UND streamt kontextbezogene Haiku-Variante in Slot 1.
    if (state.socket && state.socket.connected) {
      state.socket.emit('manual_ewb', { text: typ, line_id: 'ewb_pip_' + Date.now(), slot: 1 });
    }
  }

  // ── Socket Events (Phase 06: streaming replaces polling) ─────────────────
  function _registerSocketEvents() {
    if (!state.socket) return;

    state.socket.on('transcript', function (d) {
      if (d && d.type === 'final' && d.text) {
        state.lastTranscript = d.text;
      }
    });

    // Phase 06: Streaming event handlers (per D-08, D-09)
    state.socket.on('pip_stream_start', function (d) {
      if (!d) return;
      var slot = d.slot || 0;
      // 06.2: Latenz-Log für Slot 1 (erstes Token nach keyword_einwand_match)
      if (slot === 1 && state.slot0LastKeywordAt) {
        var slot1Delta = Date.now() - state.slot0LastKeywordAt;
        console.log('[Latency] Slot1 first token', slot1Delta, 'ms after keyword_einwand_match');
      }
      var body = pipEl('pip-slot-body-' + slot);
      var container = pipEl('pip-slot-' + slot);
      if (body) {
        body.textContent = '';
        body.classList.add('pip-streaming');
      }
      if (container) container.classList.add('pip-slot-streaming');
      state.pipSlots[slot].streaming = true;
      state.pipSlots[slot].text = '';
      state.pipSlots[slot].result = null;
      // 06.1-r2 r4: raw_text-Mode — Plain-Text-Stream (manual_ewb-Variante), kein JSON,
      // pip_token darf die Tokens direkt im Slot anzeigen statt 'Analysiere...'.
      // Phase 08.20.3: save briefing tab state for auto-collapse guard (D-05)
      state.briefingTabExpandedAtStreamStart = _isBriefingTabExpanded();
      state.pipSlots[slot].rawText = !!d.raw_text;
      // Update label
      var label = pipEl('pip-slot-label-' + slot);
      if (label) label.textContent = d.replace_all ? 'ANTWORT' : (slot === 0 ? 'ANTWORT A' : 'ANTWORT B');
      // D-03 topic switch: if replace_all, clear both slots
      if (d.replace_all) {
        [0, 1].forEach(function (s) {
          var b = pipEl('pip-slot-body-' + s);
          if (b) { b.textContent = ''; b.classList.remove('pip-streaming'); }
          var c = pipEl('pip-slot-' + s);
          if (c) c.classList.remove('pip-slot-streaming');
          state.pipSlots[s] = { streaming: false, text: '', result: null, contextKey: null };
        });
        // Re-init the target slot
        if (body) { body.textContent = ''; body.classList.add('pip-streaming'); }
        if (container) container.classList.add('pip-slot-streaming');
        state.pipSlots[slot].streaming = true;
      }
    });

    state.socket.on('pip_token', function (d) {
      if (!d) return;
      var slot = d.slot || 0;
      if (!state.pipSlots[slot].streaming) return; // discard if slot was cleared (topic switch)
      state.pipSlots[slot].text += d.token;
      var body = pipEl('pip-slot-body-' + slot);
      if (!body) return;
      // 06.1-r2 r4: raw_text-Mode (manual_ewb-Variante) — Plain-Text live streamen.
      // Sonst: Haiku streamt JSON (analyse_loop), wir zeigen 'Analysiere...' bis done.
      if (state.pipSlots[slot].rawText) {
        body.textContent = state.pipSlots[slot].text;
      } else if (body.textContent !== 'Analysiere\u2026') {
        body.textContent = 'Analysiere\u2026';
      }
    });

    state.socket.on('pip_token_done', function (d) {
      if (!d) return;
      var slot = d.slot || 0;
      state.pipSlots[slot].streaming = false;
      state.pipSlots[slot].result = d.result || {};
      var body = pipEl('pip-slot-body-' + slot);
      var container = pipEl('pip-slot-' + slot);
      if (body) body.classList.remove('pip-streaming');
      if (container) container.classList.remove('pip-slot-streaming');

      // 06.2: Keyword-Match-Schutz für Slot 0.
      // Wenn keyword_einwand_match bereits innerhalb der letzten 3s Slot 0 gerendert hat
      // UND Claude denselben Einwand-Typ erkennt, bleibt der Profil-Text stehen.
      // Bei abweichendem Typ: normale Render-Logik (Claude korrigiert Keyword-Falscherkennung).
      if (slot === 0 && state.slot0LastKeywordTyp && state.slot0LastKeywordAt) {
        var msSinceKeyword = Date.now() - state.slot0LastKeywordAt;
        if (msSinceKeyword < 3000) {
          var claudeTyp = (d.result && d.result.typ) ? String(d.result.typ).toLowerCase().trim() : '';
          var keywordTyp = String(state.slot0LastKeywordTyp).toLowerCase().trim();
          if (claudeTyp === keywordTyp || claudeTyp === '') {
            // Gleicher Typ (oder kein Typ von Claude) — Profil-Text bleibt, kein Re-Render
            console.log('[NerveLauncher] pip_token_done Slot0 ignoriert — Keyword-Match dominiert (typ:', state.slot0LastKeywordTyp, ', delta:', msSinceKeyword, 'ms)');
            // D-13 und D-02 trotzdem ausführen (kein Render-Impact)
            if (d.result && typeof d.result.skript_position === 'number') {
              _updateTeleprompterPosition(d.result.skript_position);
            }
            return;
          }
          // Anderer Typ: Claude hat neue Erkenntnis — normaler Render-Pfad
          console.log('[NerveLauncher] pip_token_done Slot0: Claude-Typ "' + claudeTyp + '" ueberschreibt Keyword-Typ "' + keywordTyp + '"');
        }
      }

      // Render formatted result
      _renderSlotResult(slot, d.result || {});
      // D-13: update teleprompter position if skript_position present
      if (d.result && typeof d.result.skript_position === 'number') {
        _updateTeleprompterPosition(d.result.skript_position);
      }
      // D-02: if no einwand, show proactive content in the OTHER slot
      if (d.result && !d.result.einwand) {
        _showProactiveContent(1 - slot, d.result);
      }
      // Phase 08.20.3: auto-collapse briefing tab if it was expanded at stream start
      if (state.briefingTabExpandedAtStreamStart) {
        _collapseBriefingTab();
        state.briefingTabExpandedAtStreamStart = false;
      }
    });

    state.socket.on('pip_stream_error', function (d) {
      if (!d) return;
      var slot = d.slot || 0;
      state.pipSlots[slot].streaming = false;
      var body = pipEl('pip-slot-body-' + slot);
      var container = pipEl('pip-slot-' + slot);
      // 06.1-r2 r6: Server schickt bereits eine user-freundliche Message
      // (z.B. 'KI aktuell ausgelastet — nimm die Standard-Antwort oben.').
      // Falls nicht vorhanden: generischer Fallback.
      var friendly = (d.error && typeof d.error === 'string' && d.error.length < 200) ? d.error : 'KI-Variante aktuell nicht verf\u00fcgbar';
      if (body) { body.textContent = friendly; body.classList.remove('pip-streaming'); }
      if (container) container.classList.remove('pip-slot-streaming');
    });

    // Coaching-Listener entfernt (Phase 06.6). Backend emittet den Event nicht mehr
    // und die Live-Anzeige im PiP war kontraproduktiv — Coaching-Tipps wurden über
    // die EWB-Antwort in Slot 1 geschrieben ("TIPP"-Label ueberschrieb "ANTWORT A").
    // Coaching-Daten bleiben für Post-Call-Scoring erhalten (conversation_log +
    // ft_assistant_events DB-Write server-seitig).

    state.socket.on('disconnect', function () {
      console.log('[NerveLauncher] Socket disconnected');
    });

    state.socket.on('dg_error', function (d) {
      console.error('[NerveLauncher] Deepgram error:', d);
    });

    // ── D-06: Anrede-Wechsel-Detection (Phase 08.20) ────────────────────────
    state.socket.on('anrede_switch_detected', function () {
      if (window.pipShowAnredeToast) window.pipShowAnredeToast();
    });

    // ── Auto-Einwand Keyword Match (Phase 06.2) ──────────────────────────────
    // Backend emitiert dieses Event <150ms nach Deepgram-Interim-Treffer.
    // Slot 0 wird SOFORT mit dem Profil-Gegenargument belegt (kein Claude-Roundtrip).
    state.socket.on('keyword_einwand_match', function (d) {
      if (!d) return;
      if (state.micMuted) {
        console.log('[NerveLauncher] keyword match ignoriert — mic muted');
        return;
      }
      var t0 = performance.now();

      var typ = d.typ || (d.profile_einwand && (d.profile_einwand.kurzlabel || d.profile_einwand.kategorie)) || 'Einwand';
      var pe = d.profile_einwand || {};
      var ga = (pe.gegenargument_1 || pe.gegenargument || '').trim();
      if (!ga) return;  // kein Profil-Gegenargument -> kein Render

      console.log('[NerveLauncher] keyword einwand match:', typ);

      // Slot 0: laufenden Haiku-Stream abbrechen (falls aktiv) und direkt rendern
      state.pipSlots[0].streaming = false;
      state.pipSlots[0].text = '';
      state.pipSlots[0].rawText = false;
      var body0 = pipEl('pip-slot-body-0');
      var container0 = pipEl('pip-slot-0');
      if (body0) body0.classList.remove('pip-streaming');
      if (container0) container0.classList.remove('pip-slot-streaming');

      // Render via bestehenden Einwand-Render-Pfad (Profile-Swap in _renderSlotResult)
      var fake = { einwand: true, typ: typ, gegenargument_1: ga };
      _renderSlotResult(0, fake);

      // EWB-Button hervorheben (ähnlich wie bei manual-click)
      _highlightEwbButton(typ);

      // State-Marker: pip_token_done soll diesen Slot-0-Render NICHT ueberschreiben
      // wenn Claude denselben typ innerhalb 3s liefert (Profil-Text bleibt autoritativ)
      state.slot0LastKeywordTyp = typ;
      state.slot0LastKeywordAt = Date.now();

      console.log('[Latency] Slot0 render took', (performance.now() - t0).toFixed(1), 'ms');
    });

    // ── Phase 08.5: Universal Response Loop events ──────────────────────────
    // qa_slot1: full Haiku-generated response for Slot 1 (unknown objection / FAQ / Rückfrage)
    state.socket.on('qa_slot1', function (d) {
      try {
        var txt = (d && d.text) ? String(d.text) : '';
        if (!txt) return;
        var body = pipEl('pip-slot-body-1');
        if (body) {
          // textContent only — XSS-safe (T-08.5-03-03)
          body.textContent = txt;
          // Rückfrage visual differentiation (Phase 08.5 Korrektur 3)
          if (txt.indexOf('Frag nach:') === 0) {
            body.classList.add('pip-rueckfrage');
          } else {
            body.classList.remove('pip-rueckfrage');
          }
          body.classList.remove('pip-streaming');
          var container = pipEl('pip-slot-1');
          if (container) container.classList.remove('pip-slot-streaming');
          var label = pipEl('pip-slot-label-1');
          if (label) label.textContent = txt.indexOf('Frag nach:') === 0 ? 'RÜCKFRAGE' : 'ANTWORT';
          console.log('[QA] qa_slot1 rendered len=' + txt.length);
        }
      } catch (e) {
        console.warn('[QA] qa_slot1 handler error', e);
      }
    });

    // qa_soft_hint: Phase 08.5 Korrektur 3 — Soft-Hint removed.
    // Low-confidence now always produces a Rückfrage from the backend.
    // If legacy event still emitted, render as normal answer (never silent).
    state.socket.on('qa_soft_hint', function (d) {
      try {
        var txt = (d && d.text) ? String(d.text) : '';
        if (!txt) return; // no text → ignore silently (backend now always sends text)
        var body = pipEl('pip-slot-body-1');
        if (body) {
          body.textContent = txt;
          // Add pip-rueckfrage class for visual differentiation if text is a Rückfrage
          if (txt.indexOf('Frag nach:') === 0) {
            body.classList.add('pip-rueckfrage');
          } else {
            body.classList.remove('pip-rueckfrage');
          }
          body.classList.remove('pip-streaming');
          var container = pipEl('pip-slot-1');
          if (container) container.classList.remove('pip-slot-streaming');
          console.log('[QA] qa_soft_hint (Rückfrage) rendered len=' + txt.length);
        }
      } catch (e) {
        console.warn('[QA] qa_soft_hint handler error', e);
      }
    });

    // ── Phase 08.23.2.C.R — Gatekeeper Socket-Subscriptions ─────────────────
    state.socket.on('contact_category_update', function (data) {
      _updateContactCategory(data.category, data.mode);
    });

    state.socket.on('phase_change', function (data) {
      console.log('[pip] phase_change', data);
    });

    state.socket.on('trigger_phrase_hint', function (data) {
      // Phase 08.23.2.C Req-7 — MVP: nur Console-Log.
      console.log('[pip] trigger_phrase_hint', data);
    });

    state.socket.on('manual_mode_toggle_ack', function (data) {
      if (data && !data.ok) {
        console.warn('[pip] manual_mode_toggle_ack error:', data.error);
      }
    });

    // -- Phase 08.23.2.D REQ-D-4 - outcome_ready Handler (dreistufige UX) ----
    state.socket.on('outcome_ready', function (d) {
      try {
        if (!d || !d.call_id) return;
        if (state.lastCallId && String(state.lastCallId) !== String(d.call_id)) {
          return; // Event fuer anderen Call - ignorieren
        }
        _renderOutcomeUx(d);
      } catch (e) {
        console.error('[PhaseD] outcome_ready Handler Fehler:', e);
      }
    });

    // -- Phase 08.23.2.D REQ-D-7 - audio_health_warning Handler -----------
    state.socket.on('audio_health_warning', function (d) {
      try {
        _showAudioWarning(d && d.score);
      } catch (e) {
        console.error('[PhaseD] audio_health_warning Handler Fehler:', e);
      }
    });

    // -- Phase 08.23.2.D D-04e - Reconnect-Fallback-Pull -----------------
    state.socket.on('connect', function () {
      if (state.lastCallId) {
        // Nur abfragen wenn aktuell keine UX im PostCall-Overlay aktiv (F5: PiP-aware)
        var sec = pipEl('pip-outcome-section');
        if (sec && sec.dataset.outcomeRendered === '1') return;
        fetch('/api/calls/latest_outcome?call_id=' + encodeURIComponent(state.lastCallId))
          .then(function (r) { return r.ok ? r.json() : null; })
          .then(function (json) {
            // Phase 08.23.2.D Hotfix 2026-05-27 — Reconnect-Fallback nur rendern wenn
            // Backend tatsaechlich einen Outcome-Stand hat. Sonst wuerde {outcome:null,
            // source:null} als <70%-Korrektur-Modal interpretiert -> Modal springt
            // beim Call-START auf wenn lastCallId noch von vorherigem Call gesetzt war.
            // D.UX.1 (LANDMINE 7): kein (outcome||source)-Skip mehr — _decideModalState
            // entscheidet (auch user_corrected -> 'final' read-only auf Reconnect, F1).
            if (json && json.ok && json.call_id) {
              _renderOutcomeUx({
                outcome: json.outcome,
                confidence: json.confidence,
                source: json.source,
                call_id: json.call_id,
              });
            }
          })
          .catch(function () { /* silent */ });
      }
    });
  }

  // ── Phase 08.23.2.C — Gatekeeper-Modus-Funktionen ────────────────────────

  function _updateContactCategory(category, mode) {
    state.contactCategory = category;
    state.currentMode = mode;
    var indicator = pipEl('pip-mode-indicator');
    if (indicator) {
      indicator.dataset.mode = mode;
      var label = (mode === 'gatekeeper') ? 'Sekretär' : (mode === 'meeting') ? 'Meeting' : 'Entscheider';
      var _lbl = indicator.querySelector('.pip-toggle-label');
      if (_lbl) { _lbl.textContent = label; } else { indicator.textContent = label; }
      // Dynamisches aria-label zeigt Ziel-Modus (D-03b): "Modus wechseln zu X"
      indicator.setAttribute('aria-label',
        'Modus wechseln zu ' + ((mode === 'gatekeeper') ? 'Entscheider' : 'Sekretär'));
    }
    if (category === 'gatekeeper') {
      _renderGatekeeperButtons();
    } else {
      _renderStandardEwbButtons();
    }
  }

  function _renderGatekeeperButtons() {
    var row = pipEl('nlp-ewb-row');
    if (!row) return;
    fetch('/api/gatekeeper/phrases?sid=' + encodeURIComponent(state.sid || ''))
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (!data || !data.buttons) return;
        var ORDER = [
          'gatekeeper_verbuendeten_bitte',
          'gatekeeper_insider_antwort',
          'gatekeeper_voss_label',
          'gatekeeper_vornamen_pause',
        ];
        var LABELS = {
          'gatekeeper_verbuendeten_bitte': 'Verbündeten-Bitte',
          'gatekeeper_insider_antwort': 'Insider-Antwort',
          'gatekeeper_voss_label': 'Voss-Label',
          'gatekeeper_vornamen_pause': 'Vornamen-Pause',
        };
        var html = ORDER.map(function (key) {
          var variants = data.buttons[key] || [];
          if (variants.length === 0) return '';
          var firstText = variants[0].filled_text || variants[0].text;
          return '<button type="button" class="pip-ewb-btn" data-mode-button="gatekeeper" data-typ="'
               + escHtml(key) + '" data-phrase="' + escHtml(firstText) + '">' + escHtml(LABELS[key]) + '</button>';
        }).join('');
        row.innerHTML = html;
      })
      .catch(function (e) { console.error('[pip] Fehler beim Laden Gatekeeper-Phrases', e); });
  }

  function _renderStandardEwbButtons() {
    // Zurueck zu den Standard-EWB-Buttons aus dem Profil
    _renderEwbButtons();
  }

  function _renderSlotResult(slot, result) {
    var body = pipEl('pip-slot-body-' + slot);
    if (!body) return;
    var label = pipEl('pip-slot-label-' + slot);

    // 06.1-r2 BUG-4: Claude liefert unterschiedliche Result-Shapes
    // ({einwand, gegenargument_1}, {poin:{einwand,text}}, {text}, ...).
    // Wir extrahieren in normalisierte Felder, damit nie rohes JSON zum User kommt.
    var r = result || {};
    // Unwrap {poin:{...}} / {point:{...}} — Haiku nutzt diese Schlüssel in Round-2 Tests
    var inner = r.poin || r.point || null;
    var isEinwand = !!(r.einwand || (inner && inner.einwand));
    var typ = r.typ || (inner && inner.typ) || '';
    var argument = r.gegenargument_1 || r.gegenargument || (inner && (inner.gegenargument_1 || inner.gegenargument)) || '';
    var text = r.text || (inner && inner.text) || '';

    // BUG-10: Für Slot 0 bei erkanntem Einwand das PROFIL-gegenargument bevorzugen
    // (exakter Text aus profile.einwaende statt Haiku-formuliert) — gibt dem Berater
    // die autorisierte Antwort. Slot 1 bleibt die Haiku-Kontext-Variante unberuehrt.
    if (slot === 0 && isEinwand && typ) {
      var typL = String(typ).toLowerCase().trim();
      var prof = (state.profileDaten && (state.profileDaten.einwaende_detail || state.profileDaten.einwaende)) || [];
      for (var pi = 0; pi < prof.length; pi++) {
        var pe = prof[pi];
        if (!pe || typeof pe !== 'object') continue;
        var cat1 = (pe.kurzlabel || '').toLowerCase().trim();
        var cat2 = (pe.kategorie || '').toLowerCase().trim();
        var cat3 = (pe.typ || '').toLowerCase().trim();
        if (cat1 === typL || cat2 === typL || cat3 === typL) {
          var profileGA = (pe.gegenargument_1 || pe.gegenargument || '').trim();
          if (profileGA) argument = profileGA;
          break;
        }
      }
    }

    // Wenn kein nutzbares Feld vorliegt: fällt der Slot in den "Warte..."-Default statt JSON anzuzeigen
    if (!argument && !text && !isEinwand) {
      body.textContent = 'Warte auf Gespr\u00e4chsinhalt\u2026';
      return;
    }

    body.innerHTML = '';
    var doc = body.ownerDocument || document;

    if (isEinwand && (argument || text)) {
      // 06.1-r2 DESIGN-11: Typ-Badge entfernt — aktiver EWB-Button zeigt bereits
      // welcher Einwand gemeint ist. Slot zeigt nur noch das Gegenargument pur.
      if (label) label.textContent = (typ || 'EINWAND').toUpperCase();
      body.textContent = argument || text;
      _highlightEwbButton(typ);
    } else {
      // Kein Einwand: nur Text/Gegenargument, Label zurück auf Antwort-Slot
      if (label && (label.textContent === '' || /^\s*$/.test(label.textContent))) {
        label.textContent = slot === 0 ? 'ANTWORT A' : 'ANTWORT B';
      }
      body.textContent = argument || text;
    }
  }

  function _getTypBadgeStyle(typ) {
    var colors = {
      'Preis': 'background:rgba(107,114,128,0.15);color:#6B7280',
      'Kein Bedarf': 'background:rgba(248,113,113,0.15);color:#f87171',
      'Vertrauen': 'background:rgba(96,165,250,0.15);color:#60a5fa',
      'Konkurrenz': 'background:rgba(168,85,247,0.15);color:#a855f7',
      'Timing': 'background:rgba(107,114,128,0.15);color:#6B7280'
    };
    return (colors[typ] || 'background:var(--badge-default-bg);color:var(--badge-default-text)') + ';font-size:11px;padding:2px 8px;border-radius:9999px';
  }

  function _highlightEwbButton(typ) {
    var row = pipEl('nlp-ewb-row');
    if (!row) return;
    row.querySelectorAll('.pip-ewb-btn').forEach(function (btn) {
      btn.classList.toggle('pip-ewb-ai-selected', btn.getAttribute('data-typ') === typ);
    });
  }

  function _showProactiveContent(slot, result) {
    // D-02: Between einwaende, show contextual tips
    if (result.phase) {
      _showProactiveTipp(slot, 'Phase wechselt: ' + result.phase);
      var label = pipEl('pip-slot-label-' + slot);
      if (label) label.textContent = 'PHASE';
    }
    if (typeof result.kb === 'number') {
      var trend = result.kb >= 50 ? 'steigend' : 'fallend';
      var trendColor = result.kb >= 50 ? '#00D4AA' : '#f87171';
      var body = pipEl('pip-slot-body-' + slot);
      if (body) {
        body.innerHTML = '<span class="pip-slot-kb" style="color:' + trendColor + '">' + result.kb + '%</span> Kaufbereitschaft \u2014 ' + trend;
      }
      var label2 = pipEl('pip-slot-label-' + slot);
      if (label2) label2.textContent = 'KAUFBEREITSCHAFT';
    }
  }

  function _showProactiveTipp(slot, tipp) {
    var body = pipEl('pip-slot-body-' + slot);
    if (body) body.textContent = tipp;
    var label = pipEl('pip-slot-label-' + slot);
    if (label && label.textContent === 'ANTWORT A' || label && label.textContent === 'ANTWORT B') {
      label.textContent = 'TIPP';
    }
  }

  function _initTeleprompter() {
    var container = pipEl('pip-teleprompter');
    if (!container) return;

    // Get script content — from edited text, selected skript, or empty
    var inhalt = '';
    if (state._editedSkriptText) {
      inhalt = state._editedSkriptText;
    } else if (state.selectedSkriptId && state.skripte.length > 0) {
      var sk = state.skripte.find(function (s) { return s.id === state.selectedSkriptId; });
      if (sk && sk.inhalt) inhalt = sk.inhalt;
    }
    // WR-01: Pitch als Fallback wenn kein Skript selektiert
    if (!inhalt && !state.selectedSkriptId && state.selectedPitchId) {
      var selPitch = (state.openerItems || []).find(function (o) { return o.id === state.selectedPitchId; });
      if (selPitch) inhalt = selPitch.inhalt || '';
    }

    // R-01: Opener oder Erlaubnisfrage vorhanden auch ohne Skript/Pitch?
    var hasOpener = !!(state._editedOpenerText || state.selectedOpenerId);
    var hasErlaubnis = !!state.selectedErlaubnisId;
    var hasPitch = !!state.selectedPitchId;

    if (!inhalt || !inhalt.trim()) {
      // Kein Skript/Pitch — aber Opener, Erlaubnisfrage oder Pitch können trotzdem gezeigt werden
      if (!hasOpener && !hasErlaubnis && !hasPitch) {
        container.innerHTML = '<div class="tp-empty">Kein Skript hinterlegt — Profil bearbeiten</div>';
        state.teleprompterBlocks = [];
        return;
      }
      // Nur Opener/Erlaubnis/Pitch ohne Skript — weiter mit leerem inhalt, skriptBlocks = []
    }

    // R-01: Block-Sequenz [openerText?, erlaubnisText?, skriptOrPitchBlocks?]
    // Opener (Block 0)
    var openerText = '';
    if (state._editedOpenerText) {
      openerText = state._editedOpenerText;
    } else if (state.selectedOpenerId && state.openerItems && state.openerItems.length > 0) {
      var selOp = state.openerItems.find(function (o) { return o.id === state.selectedOpenerId; });
      if (selOp) openerText = selOp.inhalt || '';
    }

    // Erlaubnisfrage (Block 1) — R-01: selectedErlaubnisId aus openerItems (type='erlaubnis')
    var erlaubnisText = '';
    if (state.selectedErlaubnisId && state.openerItems && state.openerItems.length > 0) {
      var selErl = state.openerItems.find(function (o) {
        return o.id === state.selectedErlaubnisId && o.type === 'erlaubnis';
      });
      if (selErl) erlaubnisText = selErl.inhalt || '';
    }

    // Skript-oder-Pitch-Blöcke (OD-01 bleibt erhalten via inhalt-Variable oben)
    // inhalt: _editedSkriptText > selectedSkriptId > selectedPitchId (WR-01 fix, s.o.)
    // LOW (Cross-AI-Fix): Defensiv initialisieren — leeres Array wenn inhalt leer/null
    var skriptBlocks = (inhalt && inhalt.trim())
      ? inhalt.split(/\n+/).filter(function (b) { return b.trim(); })
      : [];

    // Blöcke zusammensetzen — robuster gegen undefined
    var openerBlocks    = (openerText    && openerText.trim())    ? [openerText.trim()]    : [];
    var erlaubnisBlocks = (erlaubnisText && erlaubnisText.trim()) ? [erlaubnisText.trim()] : [];
    var blocks = openerBlocks.concat(erlaubnisBlocks).concat(skriptBlocks);
    state.teleprompterBlocks = blocks;
    state.teleprompterActiveIdx = 0;

    _renderTeleprompterBlocks(0);

    // Wire manual scroll override (D-13)
    container.addEventListener('scroll', function () {
      state.teleprompterManualOverride = true;
      if (state.teleprompterOverrideTimer) clearTimeout(state.teleprompterOverrideTimer);
      state.teleprompterOverrideTimer = setTimeout(function () {
        state.teleprompterManualOverride = false;
      }, 8000);
    }, { passive: true });

    // Click on block = manual override to that position
    container.addEventListener('click', function (e) {
      var blockEl = e.target.closest ? e.target.closest('.tp-block') : null;
      if (blockEl && blockEl.dataset.blockIdx !== undefined) {
        var idx = parseInt(blockEl.dataset.blockIdx);
        state.teleprompterActiveIdx = idx;
        state.teleprompterManualOverride = true;
        if (state.teleprompterOverrideTimer) clearTimeout(state.teleprompterOverrideTimer);
        state.teleprompterOverrideTimer = setTimeout(function () {
          state.teleprompterManualOverride = false;
        }, 8000);
        _renderTeleprompterBlocks(idx);
      }
    });
  }

  function _renderTeleprompterBlocks(activeIdx) {
    var container = pipEl('pip-teleprompter');
    if (!container || !state.teleprompterBlocks.length) return;
    var doc = container.ownerDocument || document;
    container.innerHTML = '';
    state.teleprompterBlocks.forEach(function (block, idx) {
      var div = doc.createElement('div');
      div.className = 'tp-block' + (idx === activeIdx ? ' tp-block-active' : '');
      div.dataset.blockIdx = idx;
      div.textContent = block.trim();
      container.appendChild(div);
    });
    // Scroll active block into view (D-14: smooth auto-scroll)
    var activeEl = container.querySelector('.tp-block-active');
    if (activeEl) {
      activeEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }

  function _updateTeleprompterPosition(newIdx) {
    // D-13: respect manual override
    if (state.teleprompterManualOverride) {
      // Update internal tracking but do not scroll
      state.teleprompterActiveIdx = newIdx;
      return;
    }
    if (newIdx === state.teleprompterActiveIdx) return;
    state.teleprompterActiveIdx = newIdx;
    _renderTeleprompterBlocks(newIdx);
  }

  // ── Timer ──────────────────────────────────────────────────────────────────
  function _startTimer() {
    // BUG-11b FIX: clear any existing interval before starting a new one.
    // Without this guard, a leaked old interval causes the clock to tick unevenly.
    _stopTimer();
    state.sessionSeconds = 0;
    state.timerInterval = setInterval(function () {
      state.sessionSeconds++;
      var el = pipEl('nlp-timer');
      if (el) {
        var m = Math.floor(state.sessionSeconds / 60);
        var s = state.sessionSeconds % 60;
        el.textContent = String(m).padStart(2, '0') + ':' + String(s).padStart(2, '0');
      }
    }, 1000);
  }

  function _stopTimer() {
    if (state.timerInterval) { clearInterval(state.timerInterval); state.timerInterval = null; }
  }

  // ── Live-State Reset — single source of truth for post-call/pre-call cleanup ─────
  // Called from TWO places (belt-and-suspenders pattern):
  //   1. endCall()      — AFTER _stopTimer+_stopMic, BEFORE _showPostcallLoading
  //   2. _showPipLive() — AT THE VERY TOP (guarantees fresh state even if prior cleanup missed something)
  // MUST NOT touch: state.lastConvId (needed for Details-link), state.profileDaten,
  //                 state.skripte, state.selectedSkriptId, state.precallFormData, state.socket.
  function _resetLiveState() {
    // 08.23.2.D.UX.4 (NEW-5): Postcall-/Call-Zustand nullen, damit nichts in den
    // naechsten Call leckt. lastCallId wurde bisher nur am Call-START genullt (Z.1449);
    // pendingPostcall (neu in dieser Phase) wurde NIRGENDS genullt.
    state.pendingPostcall = null;
    state.lastCallId = null;
    // 1. Timer: stop interval AND reset DOM to 00:00 immediately (fixes 1s display lag)
    _stopTimer();
    state.sessionSeconds = 0;
    var timerEl = pipEl('nlp-timer');
    if (timerEl) timerEl.textContent = '00:00';

    // 2. Slots: reset body text, labels, streaming class for both slots
    [0, 1].forEach(function (s) {
      var body = pipEl('pip-slot-body-' + s);
      if (body) {
        body.innerHTML = '';
        body.textContent = 'Warte auf Gesprächsinhalt…';
        body.classList.remove('pip-streaming');
      }
      var label = pipEl('pip-slot-label-' + s);
      if (label) label.textContent = s === 0 ? 'ANTWORT A' : 'ANTWORT B';
    });

    // 3. Slot state objects
    state.pipSlots = [
      { streaming: false, text: '', result: null, contextKey: null },
      { streaming: false, text: '', result: null, contextKey: null }
    ];

    // 4. EWB buttons: remove stale highlight and flashing classes
    var ewbRow = pipEl('nlp-ewb-row');
    if (ewbRow) {
      ewbRow.querySelectorAll('.pip-ewb-btn').forEach(function (btn) {
        btn.classList.remove('pip-ewb-ai-selected', 'pip-ewb-flashing');
      });
    }

    // 5. Teleprompter: reset active position and clear override timer
    state.teleprompterActiveIdx = -1;
    state.teleprompterManualOverride = false;
    if (state.teleprompterOverrideTimer) { clearTimeout(state.teleprompterOverrideTimer); state.teleprompterOverrideTimer = null; }
    var tpContainer = pipEl('pip-teleprompter');
    if (tpContainer) {
      tpContainer.querySelectorAll('.tp-block-active').forEach(function (el) {
        el.classList.remove('tp-block-active');
      });
    }

    // 6. Mic muted flag (hardware already stopped by _stopMic — just clear the flag)
    state.micMuted = false;
    // NOTE: micAnalyser and micLevelRafId are _stopMic's responsibility — do NOT reset here.
    console.log('[NerveLauncher] _resetLiveState() complete');
  }

  // ── Mic Stop ───────────────────────────────────────────────────────────────
  function _stopMic() {
    if (state.micLevelRafId) { cancelAnimationFrame(state.micLevelRafId); state.micLevelRafId = null; }
    if (state.micAnalyser) { try { state.micAnalyser.disconnect(); } catch(e){} state.micAnalyser = null; }
    state.micMuted = false;
    state.micStarted = false;
    if (state.socket) state.socket.emit('stop_live_session');
    if (state.workletNode) { state.workletNode.disconnect(); state.workletNode = null; }
    if (state.audioCtx) { state.audioCtx.close(); state.audioCtx = null; }
    if (state.micStream) { state.micStream.getTracks().forEach(function (t) { t.stop(); }); state.micStream = null; }
    // BUG-11b DEBUG: trace caller so regressions are instantly debuggable
    console.log('[NerveLauncher] Mic stopped');
    console.trace('[NerveLauncher] _stopMic caller trace');
  }

  // ── End Call ───────────────────────────────────────────────────────────────
  // 08.23.2.D.UX.4 (LB-01) — Ladebalken 1: ehrlicher unbestimmter Spinner statt
  // Score-Skeleton. PiP-aware (Container via pipEl). KEIN Prozentbalken.
  function _showLadebalken1() {
    // FIX (Bug pip-score-empty-after-confirm): #nlp-section-postcall ist der SICHTBARE
    // Container, in den Ladebalken 1 UND der Outcome-Screen (_renderOutcomeUx-Host) gerendert
    // werden. Frueher wurde die ganze Section auf display:none gesetzt -> Ladebalken + Outcome-
    // Screen unsichtbar -> User kann Bestaetigen nie klicken -> leeres PiP. Jetzt: Section
    // SICHTBAR schalten, aber nur die Score-Karten-Kinder (Zahl/Label/Actions) bis Confirm
    // verstecken (L-01/F9 — kein vorlaeufiger Score). Leere Kinder (trend/sparkline/quickstats/
    // tags) blendet CSS :empty bereits aus.
    var sps = pipEl('nlp-section-postcall');
    if (sps) {
      sps.style.display = 'flex';
      var _scNum = pipEl('nlp-postcall-score'); if (_scNum) _scNum.style.display = 'none';
      var _scLbl = sps.querySelector('.pip-postcall-label'); if (_scLbl) _scLbl.style.display = 'none';
      var _scAct = sps.querySelector('.pip-postcall-actions'); if (_scAct) _scAct.style.display = 'none';
    }
    // Live-Controls verstecken, Header verstecken — analog _showPostcallRaw, aber
    // ohne die Postcall-Section aufzudecken.
    ['nlp-btn-beenden', 'nlp-ewb-row', 'pip-section-live'].forEach(function (id) {
      var el = pipEl(id);
      if (el) el.style.display = 'none';
    });
    var pipHeader = pipEl('pip-header');
    if (pipHeader) pipHeader.style.display = 'none';
    // Ladebalken-1-View in den Live-Container-Host rendern (PiP-Fenster).
    var doc = (state.pipWindow && !state.pipWindow.closed) ? state.pipWindow.document : document;
    var host = pipEl('pip-postcall') || pipEl('nlp-section-postcall') || doc.body;
    var lb = pipEl('pip-ladebalken1');
    if (!lb) {
      lb = doc.createElement('div');
      lb.id = 'pip-ladebalken1';
      lb.className = 'pip-ladebalken1';
      if (host) host.appendChild(lb);
    }
    lb.style.display = 'flex';
    lb.innerHTML = '<div class="pip-loading-spinner" aria-label="Auswertung laeuft"></div>'
      + '<div class="pip-ladebalken1-text">KI wertet das Gespräch aus…</div>';
  }
  function _hideLadebalken1() {
    var lb = pipEl('pip-ladebalken1');
    if (lb) lb.style.display = 'none';
  }

  function endCall() {
    _stopTimer();
    _stopMic();
    // B-01: Mic stoppt sofort, Live-UI sofort weg.
    _resetLiveState();

    // 08.23.2.D.UX.4 (LB-01): ehrlicher Ladebalken 1 statt Score-Skeleton.
    // Score-Render kommt erst nach Confirm (Task 2/3). Postcall-Section bleibt
    // versteckt (F9 — _showLadebalken1 setzt display:none).
    _showLadebalken1();

    var endCallGen = (state.callGen = (state.callGen || 0) + 1);
    fetch('/api/beenden', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
      body: JSON.stringify({
        session_mode: state.mode || 'cold_call',
        precall_briefing: state.precallBriefing,
        precall_fields: (state.precallBriefing && state.precallBriefing.fields) ? state.precallBriefing.fields : null
      })
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (state.callGen !== endCallGen || state.micStarted) {
          console.log('[NerveLauncher] Beenden response stale (neue Session läuft) — verworfen');
          return;
        }
        if (!data.ok) { console.error('[NerveLauncher] Beenden error:', data.error); _hideLadebalken1(); _showPostcallEmpty(); return; }
        state.lastConvId = data.conv_id || null;
        state.lastCallId = data.call_id || null; // Phase 08.23.2.D REQ-D-4: Fallback-Pull
        // 08.23.2.D.UX.4 (S-03): Postcall NICHT mehr hier rendern — zwischenspeichern,
        // Basis-Analytics erscheinen zusammen mit dem Score nach Confirm (Task 3).
        // HINWEIS: nur auf dem Erfolgs-/Non-Stale-Pfad gesetzt; bei Timeout/Stale/Race
        // bleibt es undefined -> Task 3 rendert KPI null-safe.
        state.pendingPostcall = data.postcall || null;

        var _pc = data.postcall || {};

        // 08.23.2.D.UX.4 (NEW-2 / Option 3): Sonnet-Lernkarten im HINTERGRUND triggern,
        // unabhaengig vom spaeteren Confirm. Response wird VERWORFEN (kein PiP-Render).
        // So persistieren LearningCards auch wenn der User den Outcome-Screen abbricht.
        if (state.lastConvId && state.lastCallId) {
          fetch('/api/postcall_cards', {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
            body: JSON.stringify({
              conv_id: state.lastConvId,
              call_id: state.lastCallId,
              einwaende: _pc.einwaende || [],
              painpoints: _pc.painpoints || [],
              kb_start: _pc.kb_start || 30,
              kb_end: _pc.kb_end || 30,
              redeanteil_berater: _pc.redeanteil_berater || 50,
              redeanteil_kunde: _pc.redeanteil_kunde || 50,
              dauer_sek: _pc.dauer_sek || _pc.dauer || 0,
              skript_abdeckung: _pc.skript_abdeckung || 0,
              ga_details: _pc.ga_details || [],
              kaufsignale: _pc.kaufsignale || []
            })
          })
            .then(function () {})  // Response bewusst verworfen (Option 3)
            .catch(function () {});
        }

        // 08.23.2.D.UX.4 (LB-02 + HIGH-2 + F5): 9s-Timeout VOR dem Outcome-Fetch armen.
        var haikuTimedOut = false;
        var lb1Timeout = setTimeout(function () {
          if (state.callGen !== endCallGen) return;            // Stale-Guard (Landmine 2)
          haikuTimedOut = true;
          _hideLadebalken1();
          _renderOutcomeUx({ outcome: null, confidence: 0, source: null, call_id: state.lastCallId });
          // HIGH-2 Defence-in-depth: Timeout-Screen sofort idempotent gegen Late-Haiku.
          // F5: KORREKTE ID 'pip-outcome-section', PiP-aware via pipEl (NICHT bare,
          // NICHT 'nlp-outcome-section').
          try {
            var _sec = pipEl('pip-outcome-section');
            if (_sec) _sec.dataset.outcomeRendered = '1';
          } catch (_e) {}
        }, 9000);

        // 08.23.2.D.UX.4 (Plan 02): schneller Haiku-Outcome statt postcall_analysis-Monolith.
        if (state.lastConvId && state.lastCallId) {
          fetch('/api/postcall_outcome', {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
            body: JSON.stringify({
              conv_id: state.lastConvId,
              call_id: state.lastCallId,
              einwaende: _pc.einwaende || [],
              painpoints: _pc.painpoints || [],
              kb_start: _pc.kb_start || 30,
              kb_end: _pc.kb_end || 30,
              redeanteil_berater: _pc.redeanteil_berater || 50,
              redeanteil_kunde: _pc.redeanteil_kunde || 50,
              dauer_sek: _pc.dauer_sek || _pc.dauer || 0,
              skript_abdeckung: _pc.skript_abdeckung || 0,
              ga_details: _pc.ga_details || [],
              kaufsignale: _pc.kaufsignale || []
            })
          })
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (paResult) {
              clearTimeout(lb1Timeout);
              if (state.callGen !== endCallGen) return;   // Stale-Guard (Landmine 2)
              if (haikuTimedOut) return;                  // Late-Haiku darf Timeout-Screen NICHT ueberschreiben (Landmine 1)
              _hideLadebalken1();
              if (paResult && paResult.call_id) {
                _renderOutcomeUx({
                  outcome: paResult.outcome,
                  confidence: paResult.confidence,
                  source: paResult.source,
                  call_id: paResult.call_id
                });
              }
            })
            .catch(function (e) { console.log('[NerveLauncher] postcall_outcome Trigger Fehler (non-fatal):', e); });
        } else {
          clearTimeout(lb1Timeout);
        }
      })
      .catch(function (err) {
        if (state.callGen !== endCallGen || state.micStarted) {
          console.log('[NerveLauncher] Beenden fetch error ignoriert — neue Session läuft');
          return;
        }
        console.error('[NerveLauncher] Beenden fetch error:', err);
        _hideLadebalken1();
        _showPostcallEmpty();
      });
  }

  // ── PostCall Display ───────────────────────────────────────────────────────
  function _calcScore(postcall) {
    var kb = postcall.kb_end || 30;
    var total = (postcall.berater_words || 0) + (postcall.kunde_words || 0);
    var redeanteil = total > 0 ? Math.round((postcall.berater_words || 0) / total * 100) : 50;
    var gaDetails = postcall.ga_details || [];
    var behandelt = gaDetails.filter(function (x) { return x && x.erfolgreich === true; }).length;
    var einwTotal = (postcall.einwaende || []).length;
    var behandeltRate = einwTotal > 0 ? behandelt / einwTotal : 0.5;
    var skript = (postcall.skript_abdeckung || {}).gesamt_prozent || 0;
    var redeScore = Math.max(0, 100 - Math.abs(redeanteil - 40) * 2);
    return Math.min(100, Math.max(0, Math.round(kb * 0.4 + behandeltRate * 100 * 0.3 + redeScore * 0.2 + skript * 0.1)));
  }

  function _buildTags(postcall) {
    var tags = [];
    var kb = postcall.kb_end || 0;
    var kbStart = postcall.kb_start || 30;
    var total = (postcall.berater_words || 0) + (postcall.kunde_words || 0);
    var redeanteil = total > 0 ? Math.round((postcall.berater_words || 0) / total * 100) : 50;
    var gaDetails = postcall.ga_details || [];
    var behandelt = gaDetails.filter(function (x) { return x && x.erfolgreich === true; }).length;
    var einwTotal = (postcall.einwaende || []).length;
    var behandeltRate = einwTotal > 0 ? behandelt / einwTotal : -1;
    var dauer = postcall.dauer_sek || 0;
    if (kb >= 70) tags.push({ text: 'Starke Kaufbereitschaft', color: 'teal' });
    if (kb - kbStart >= 20) tags.push({ text: 'KB deutlich gestiegen', color: 'teal' });
    if (behandeltRate >= 0.8 && einwTotal > 0) tags.push({ text: 'Einwände gemeistert', color: 'teal' });
    if (redeanteil > 65) tags.push({ text: 'Redeanteil zu hoch', color: 'neutral' });
    if (redeanteil > 0 && redeanteil < 25) tags.push({ text: 'Zu wenig gesprochen', color: 'neutral' });
    if (dauer > 0 && dauer < 120) tags.push({ text: 'Sehr kurzer Call', color: 'neutral' });
    if (behandeltRate >= 0 && behandeltRate < 0.4 && einwTotal > 0) tags.push({ text: 'Einwände offen', color: 'red' });
    var pos = tags.filter(function (t) { return t.color === 'teal'; });
    var neg = tags.filter(function (t) { return t.color !== 'teal'; });
    var result = pos.slice(0, 2);
    if (result.length < 3 && neg.length > 0) result.push(neg[0]);
    return result.slice(0, 3);
  }

  function _showPostcall(postcall) {
    // POLISH-41: Guard prüft MEHRERE "conversation happened"-Signale, nicht nur
    // berater/kunde/einwaende. In Cold Call fehlt Speaker-Diarization strukturell
    // (berater_words=0, kunde_words=0 by design — Phase 07.1 DEVIATIONS OBS-02),
    // und Claude-detektierte einwaende weichen häufig von EWB-Klicks ab
    // (POLISH-43). Empty-State darf nur feuern, wenn ALLE Signale leer sind.
    // 06.1-r2 BUG-10-Rationale ("45% für leere Calls verwirrt") bleibt
    // für echte Empty-Calls (User beendet sofort) erhalten.
    var berater = (postcall && postcall.berater_words) || 0;
    var kunde = (postcall && postcall.kunde_words) || 0;
    var einwTotal = ((postcall && postcall.einwaende) || []).length;
    var painTotal = ((postcall && postcall.painpoints) || []).length;
    var kaufTotal = ((postcall && postcall.kaufsignale) || []).length;
    var gaTotal = ((postcall && postcall.ga_details) || []).length;
    var kbTotal = ((postcall && postcall.kb_verlauf) || []).length;
    var hasConversation = (
      berater > 0 || kunde > 0 ||
      einwTotal > 0 || painTotal > 0 || kaufTotal > 0 ||
      gaTotal > 0 || kbTotal > 0
    );
    if (!hasConversation) {
      _showPostcallEmpty();
      return;
    }
    // D-W3-04: Score-Sektion initial verstecken bis Outcome-Confirm (F5/NEW-1: PiP-aware).
    var scoreSection = pipEl('nlp-section-postcall');
    if (scoreSection) scoreSection.style.display = 'none';
    // 08.23.2.D.UX.4 (L-01): KEIN vorlaeufiger _calcScore mehr im Render-Pfad.
    // Der angezeigte Score kommt ausschliesslich aus der correct_outcome-Response nach
    // Confirm (S-01). Hier nur Tags/Sparkline/QuickStats; KEIN _fetchAndRenderTrend(score)
    // mit dem _calcScore-Wert (F9 — der Trend-Feed sitzt jetzt im confirm-handler mit final_score).
    var tags = _buildTags(postcall);
    _showPostcallRaw('', tags);
    // POLISH-22: Trend + Sparkline + QuickStats zusätzlich rendern
    _renderQuickStats(postcall);
    _renderSparkline(postcall);
  }

  // ── POLISH-22 v2: Kaufbereitschafts-Chart mit Achsen + Gitterlinien ─────
  function _renderSparkline(postcall) {
    var el = pipEl('nlp-postcall-sparkline');
    if (!el) return;
    var kbVerlauf = (postcall && postcall.kb_verlauf) || [];
    if (kbVerlauf.length < 2) {
      el.innerHTML = '<div class="pip-postcall-sparkline-title">Kaufbereitschafts-Verlauf</div>'
        + '<div class="pip-postcall-sparkline-empty">Nicht genug Datenpunkte für Verlauf</div>';
      return;
    }
    // Datenpunkte als {t_sec, wert} normalisieren
    var dauerSek = (postcall && postcall.dauer_sek) || 0;
    var points = kbVerlauf.map(function (p, i) {
      if (typeof p === 'object') {
        // p.t kann z.B. ISO-Timestamp, Sekunden, oder irgendwas sein — wir nutzen den Index als Fallback fuer die X-Position
        var tSec;
        if (typeof p.t === 'number') tSec = p.t;
        else tSec = (i / (kbVerlauf.length - 1)) * Math.max(1, dauerSek);
        return { t: tSec, wert: p.wert || 0 };
      }
      return { t: (i / (kbVerlauf.length - 1)) * Math.max(1, dauerSek), wert: p };
    });
    var values = points.map(function (p) { return p.wert; });
    var startV = values[0];
    var endV = values[values.length - 1];

    // SVG-Geometrie: viewBox 300x110, innerer Chart-Bereich begrenzt von Padding
    var W = 300, H = 110;
    var PAD_L = 26;  // Y-Achsen-Labels
    var PAD_R = 8;
    var PAD_T = 8;
    var PAD_B = 20;  // X-Achsen-Labels
    var innerW = W - PAD_L - PAD_R;
    var innerH = H - PAD_T - PAD_B;

    // Y-Achse fix 0..100% (Kaufbereitschaft ist immer in %)
    function yPos(v) { return PAD_T + (1 - v / 100) * innerH; }
    // X-Achse: erste -> letzte X-Position im Inner-Bereich
    var tMax = points[points.length - 1].t;
    var tMin = points[0].t;
    var tRange = Math.max(1, tMax - tMin);
    function xPos(t) { return PAD_L + ((t - tMin) / tRange) * innerW; }

    // Chart-Punkte (Linie)
    var linePts = points.map(function (p) {
      return xPos(p.t).toFixed(1) + ',' + yPos(p.wert).toFixed(1);
    }).join(' ');
    // Area-Fill: Line + nach unten zur 0%-Linie + zurueck zum Start
    var areaPath = 'M ' + xPos(points[0].t).toFixed(1) + ',' + yPos(0).toFixed(1)
      + ' L ' + points.map(function (p) {
          return xPos(p.t).toFixed(1) + ',' + yPos(p.wert).toFixed(1);
        }).join(' L ')
      + ' L ' + xPos(points[points.length - 1].t).toFixed(1) + ',' + yPos(0).toFixed(1)
      + ' Z';
    var lastX = xPos(points[points.length - 1].t);
    var lastY = yPos(endV);

    // X-Achsen-Zeitlabels (Start, Mitte, Ende) — dauer_sek in mm:ss format
    function fmtTime(sec) {
      sec = Math.max(0, Math.round(sec));
      var m = Math.floor(sec / 60), s = sec % 60;
      return m + ':' + (s < 10 ? '0' + s : s);
    }
    var xLabelStart = fmtTime(tMin);
    var xLabelMid = fmtTime((tMin + tMax) / 2);
    var xLabelEnd = fmtTime(tMax);

    var svg = [
      '<svg viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="xMidYMid meet" aria-label="Kaufbereitschafts-Verlauf" role="img">',
      // Gitterlinien horizontal bei 0%, 50%, 100%
      '<line class="pip-sparkline-grid" x1="' + PAD_L + '" y1="' + yPos(100).toFixed(1) + '" x2="' + (W - PAD_R) + '" y2="' + yPos(100).toFixed(1) + '"/>',
      '<line class="pip-sparkline-grid" x1="' + PAD_L + '" y1="' + yPos(50).toFixed(1) + '" x2="' + (W - PAD_R) + '" y2="' + yPos(50).toFixed(1) + '"/>',
      '<line class="pip-sparkline-grid" x1="' + PAD_L + '" y1="' + yPos(0).toFixed(1) + '" x2="' + (W - PAD_R) + '" y2="' + yPos(0).toFixed(1) + '"/>',
      // Y-Achsen-Labels
      '<text class="pip-sparkline-axis-text" x="' + (PAD_L - 4) + '" y="' + (yPos(100) + 3) + '" text-anchor="end">100%</text>',
      '<text class="pip-sparkline-axis-text" x="' + (PAD_L - 4) + '" y="' + (yPos(50) + 3) + '" text-anchor="end">50%</text>',
      '<text class="pip-sparkline-axis-text" x="' + (PAD_L - 4) + '" y="' + (yPos(0) + 3) + '" text-anchor="end">0%</text>',
      // Area-Fill unter der Linie (soft teal)
      '<path d="' + areaPath + '" fill="rgba(0,212,170,0.12)" stroke="none"/>',
      // Kurve
      '<polyline points="' + linePts + '" fill="none" stroke="#00D4AA" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>',
      // Endpoint-Marker
      '<circle cx="' + lastX.toFixed(1) + '" cy="' + lastY.toFixed(1) + '" r="3.5" fill="#00D4AA" stroke="#FFFFFF" stroke-width="1.5"/>',
      // X-Achsen-Labels
      '<text class="pip-sparkline-axis-text" x="' + xPos(tMin) + '" y="' + (H - 6) + '" text-anchor="start">' + xLabelStart + '</text>',
      '<text class="pip-sparkline-axis-text" x="' + (PAD_L + innerW / 2) + '" y="' + (H - 6) + '" text-anchor="middle">' + xLabelMid + '</text>',
      '<text class="pip-sparkline-axis-text" x="' + xPos(tMax) + '" y="' + (H - 6) + '" text-anchor="end">' + xLabelEnd + '</text>',
      '</svg>'
    ].join('');
    el.innerHTML = '<div class="pip-postcall-sparkline-title">Kaufbereitschaft im Verlauf</div>'
      + '<div class="pip-postcall-sparkline-chart">' + svg + '</div>';
  }

  function _renderQuickStats(postcall) {
    var el = pipEl('nlp-postcall-quickstats');
    if (!el) return;
    var pc = postcall || {};
    // Dauer
    var dauer = pc.dauer_sek || 0;
    var mins = Math.floor(dauer / 60);
    var secs = dauer % 60;
    var dauerStr = mins + ':' + (secs < 10 ? '0' + secs : secs);
    // POLISH-22 v5: Einwände gesamt (nicht mehr X/Y)
    // Rationale: Anzahl der Einwände im Gespräch als Overview-KPI.
    // Weniger Einwände ueber Zeit = vorausschauendes Argumentieren erkennbar.
    var einwTotal = (pc.einwaende || []).length;
    var einwStr = einwTotal > 0 ? String(einwTotal) : '–';
    // POLISH-22 v5+v6: Redeanteil als 2-Spalten-Layout (Vertriebler / Kunde)
    // Cold Call: NERVE hoert per Design nur den Berater — Backend zaehlt die Wörter aber
    // nur wenn Speaker-Diarization 'Berater'/'Kunde' zuweist. Im Cold Call bleibt das leer.
    // Setze daher im Cold Call einen fixen 100/0-Split (Vertriebler=100%, Kunde=0%),
    // damit die Kachel nicht sinnlos '–' zeigt. Meeting nutzt echte Zählung.
    var isColdCall = (state.mode === 'cold_call');
    var total = (pc.berater_words || 0) + (pc.kunde_words || 0);
    var redeB, redeK, hasRede;
    if (isColdCall) {
      redeB = 100;
      redeK = 0;
      hasRede = true;
    } else {
      redeB = total > 0 ? Math.round((pc.berater_words || 0) / total * 100) : 0;
      redeK = total > 0 ? (100 - redeB) : 0;
      hasRede = total > 0;
    }
    // Skript-Abdeckung
    var skript = (pc.skript_abdeckung || {}).gesamt_prozent || 0;
    var skriptStr = skript > 0 ? skript + '%' : '–';
    var skriptAccent = skript >= 80;
    // 08.23.2.D.UX.4 (S-03): Kaufbereitschaft (kb_end) als Basis-Analytics-Tile.
    var kbEnd = (typeof pc.kb_end === 'number') ? pc.kb_end : null;
    var kbStr = (kbEnd !== null) ? kbEnd + '%' : '–';

    el.innerHTML = [
      '<div class="pip-quickstat"><div class="pip-quickstat-value">' + escHtml(kbStr) + '</div><div class="pip-quickstat-label">Kaufbereitschaft</div></div>',
      '<div class="pip-quickstat"><div class="pip-quickstat-value">' + escHtml(dauerStr) + '</div><div class="pip-quickstat-label">Dauer</div></div>',
      '<div class="pip-quickstat"><div class="pip-quickstat-value">' + escHtml(einwStr) + '</div><div class="pip-quickstat-label">Einwände</div></div>',
      '<div class="pip-quickstat pip-quickstat-split">'
        + '<div class="pip-quickstat-label pip-quickstat-label-top">Redeanteil</div>'
        + '<div class="pip-quickstat-split-row">'
          + '<div class="pip-quickstat-split-col"><div class="pip-quickstat-value">' + (hasRede ? redeB + '%' : '–') + '</div><div class="pip-quickstat-sublabel">Vertriebler</div></div>'
          + '<div class="pip-quickstat-split-col"><div class="pip-quickstat-value">' + (hasRede ? redeK + '%' : '–') + '</div><div class="pip-quickstat-sublabel">Kunde</div></div>'
        + '</div>'
      + '</div>',
      '<div class="pip-quickstat"><div class="pip-quickstat-value' + (skriptAccent ? ' accent' : '') + '">' + escHtml(skriptStr) + '</div><div class="pip-quickstat-label">Skript-Abdeckung</div></div>'
    ].join('');
  }

  function _fetchAndRenderTrend(currentScore) {
    var el = pipEl('nlp-postcall-trend');
    if (!el) return;
    el.className = 'pip-postcall-trend';
    el.textContent = '';
    fetch('/api/postcall/trend?n=5', { credentials: 'include' })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (!data || !data.ok) return;
        if (!data.sample_size || data.avg_score === null || data.avg_score === undefined) {
          el.textContent = 'Erster Call-Score';
          return;
        }
        var diff = currentScore - data.avg_score;
        var sign = diff > 0 ? '▲ +' : (diff < 0 ? '▼ ' : '● ');
        var absDiff = Math.abs(diff);
        var label = data.sample_size === 1 ? 'vs letzter Call' : 'vs Schnitt letzte ' + data.sample_size;
        el.textContent = sign + absDiff + '% ' + label;
        if (diff > 0) el.className = 'pip-postcall-trend up';
        else if (diff < 0) el.className = 'pip-postcall-trend down';
      })
      .catch(function () {
        el.textContent = '';
      });
  }

  function _showPostcallLoading() {
    _showPostcallRaw('\u2026', []);
    // POLISH-23: Score-Bereich zeigt rotierenden Spinner statt statisches "…"
    var scoreEl = pipEl('nlp-postcall-score');
    if (scoreEl) scoreEl.innerHTML = '<div class="pip-score-spinner" aria-label="Auswertung wird erstellt"></div>';
    var tagsEl = pipEl('nlp-postcall-tags');
    if (tagsEl) tagsEl.innerHTML = '<span class="pip-postcall-loading">Call wird ausgewertet\u2026</span>';
    // POLISH-22: Zusätzliche Elemente im Loading leer halten
    var trendEl = pipEl('nlp-postcall-trend');
    if (trendEl) { trendEl.textContent = ''; trendEl.className = 'pip-postcall-trend'; }
    var sparkEl = pipEl('nlp-postcall-sparkline');
    if (sparkEl) sparkEl.innerHTML = '';
    var qsEl = pipEl('nlp-postcall-quickstats');
    if (qsEl) qsEl.innerHTML = '';
    // POLISH-23: Auswertung-Button disabled solange keine conv_id aus /api/beenden-Response da ist.
    // Verhindert dass User auf /logs-Fallback navigiert weil state.lastConvId noch null.
    var detailsBtn = pipEl('nlp-btn-details');
    if (detailsBtn) { detailsBtn.disabled = true; detailsBtn.style.display = ''; }
  }

  function _showPostcallEmpty() {
    _showPostcallRaw('', []);
    var scoreEl = pipEl('nlp-postcall-score');
    if (scoreEl) scoreEl.style.display = 'none';
    var labelEls = pipEl('nlp-section-postcall');
    // Ersetze den Score-Bereich durch einen Empty-State
    var tagsEl = pipEl('nlp-postcall-tags');
    if (tagsEl) tagsEl.innerHTML = '<div class="pip-postcall-empty">Kein Gespräch erkannt.<br>Direkt nächsten Call starten?</div>';
    // POLISH-22: Zusätzliche Elemente im Empty leer halten
    var trendEl = pipEl('nlp-postcall-trend');
    if (trendEl) { trendEl.textContent = ''; trendEl.className = 'pip-postcall-trend'; }
    var sparkEl = pipEl('nlp-postcall-sparkline');
    if (sparkEl) sparkEl.innerHTML = '';
    var qsEl = pipEl('nlp-postcall-quickstats');
    if (qsEl) qsEl.innerHTML = '';
    // Details-Button im Empty-State ausblenden (nichts zu zeigen)
    var detailsBtn = pipEl('nlp-btn-details');
    if (detailsBtn) detailsBtn.style.display = 'none';
  }

  function _showPostcallRaw(scoreText, tags) {
    var postcallSection = pipEl('nlp-section-postcall');
    if (postcallSection) postcallSection.style.display = 'flex';
    // Hide live controls
    ['nlp-btn-beenden', 'nlp-ewb-row', 'pip-section-live'].forEach(function (id) {
      var el = pipEl(id);
      if (el) el.style.display = 'none';
    });
    var pipHeader = pipEl('pip-header');
    if (pipHeader) pipHeader.style.display = 'none';

    var scoreEl = pipEl('nlp-postcall-score');
    if (scoreEl) { scoreEl.style.display = ''; scoreEl.textContent = scoreText; }
    // Details-Button in Filled-State wieder einblenden (Empty-State hatte ihn versteckt)
    // POLISH-23: plus enablen sobald echter Score da ist (disabled-state aus _showPostcallLoading aufheben)
    var detailsBtn = pipEl('nlp-btn-details');
    if (detailsBtn && scoreText && scoreText !== '\u2026') {
      detailsBtn.style.display = '';
      detailsBtn.disabled = false;
    }

    var tagsEl = pipEl('nlp-postcall-tags');
    if (tagsEl) {
      tagsEl.innerHTML = tags.map(function (t) {
        return '<span class="pip-tag pip-tag-' + t.color + '">' + escHtml(t.text) + '</span>';
      }).join('');
    }
  }

  // ── PostCall Actions ───────────────────────────────────────────────────────
  function nextCall() {
    // BUG-11b FIX: null state.pipWindow BEFORE calling .close() so the pagehide
    // guard (state.pipWindow === pipWindow) always evaluates false for the old window.
    // BUG-11 r5: callGen++ invalidiert auch noch ausstehende endCall-fetches, deren
    // .then()-Handler würden sonst _showPostcall in die Live-UI der neuen Session blasen.
    state.callGen = (state.callGen || 0) + 1;
    var oldWin = state.pipWindow;
    state.pipWindow = null;
    if (oldWin && !oldWin.closed) oldWin.close();
    _cleanup();
    open();
  }

  function showDetails() {
    // BUG-11b FIX: same null-first approach as nextCall()
    var oldWin = state.pipWindow;
    state.pipWindow = null;
    if (oldWin && !oldWin.closed) oldWin.close();
    // BUG-B FIX: state.lastConvId muss VOR _cleanup() gespeichert werden —
    // _cleanup() setzt state.lastConvId = null, weshalb die Weiterleitung
    // immer auf /logs (statt /logs/{id}) landete (Regression von BUG-11).
    var convId = state.lastConvId;
    _cleanup();
    if (convId) {
      // POLISH-23 FIX: Route heißt '/session/<id>', NICHT '/logs/<id>' —
      // letztere existiert in routes/logs_routes.py gar nicht. Der alte
      // BUG-08-Fix hat nur die convId-Storage gefixt, aber weiter auf die
      // falsche URL gezeigt. Session-Detail liegt in routes/dashboard.py.
      window.location.href = '/session/' + convId;
    } else {
      window.location.href = '/logs';
    }
  }

  // ── Cleanup ────────────────────────────────────────────────────────────────
  function _cleanup() {
    _stopTimer();
    if (state.micStarted) _stopMic();
    if (state.socket) { state.socket.disconnect(); state.socket = null; }
    // Phase 08.5 D-10: persist last Anrede for next call (sticky UX)
    var lastAnrede = state.precallFormData && state.precallFormData.anrede;
    if (lastAnrede === 'Du' || lastAnrede === 'Sie') {
      state.lastSessionAnrede = lastAnrede;
      try { localStorage.setItem('nerve_last_anrede', lastAnrede); } catch (_) {}
    }
    state.micStarted = false;
    state.pipWindow = null;
    state.sessionSeconds = 0;
    state.pipTabLocked = null;
    state.lastConvId = null;
    state.pipSlots = [
      { streaming: false, text: '', result: null, contextKey: null },
      { streaming: false, text: '', result: null, contextKey: null }
    ];
    state.consentDone = false;
    state.teleprompterBlocks = [];
    state.teleprompterActiveIdx = -1;
    state.teleprompterManualOverride = false;
    if (state.teleprompterOverrideTimer) { clearTimeout(state.teleprompterOverrideTimer); state.teleprompterOverrideTimer = null; }
  }

  // ── Phase 08 D-14: _setAnrede helper (whitelist Du/Sie) ──────────────────
  function _setAnrede(anrede) {
    if (anrede !== 'Du' && anrede !== 'Sie') return;
    state.precallFormData = state.precallFormData || {};
    state.precallFormData.anrede = anrede;
    // Toggle active class across both buttons in the PiP window OR main doc.
    try {
      var docs = [document];
      if (state.pipWindow && state.pipWindow.document) docs.push(state.pipWindow.document);
      docs.forEach(function(d) {
        d.querySelectorAll('.launcher-anrede-btn').forEach(function(b) {
          b.classList.toggle('active', b.dataset.val === anrede);
        });
      });
    } catch (e) { /* DOM query failed — silently ignore */ }
  }

  // ── Phase 08.20 D-05: _setVorwissen helper ───────────────────────────────
  function _setVorwissen(val) {
    var allowed = ['niedrig', 'mittel', 'hoch', null];
    if (allowed.indexOf(val) === -1) val = null;
    state.vorwissenLevel = val;
    // Update active class in both step 4b row and step 5 row (Issue 3)
    ['#lnr-vorwissen-row', '#lnr-vorwissen-row5'].forEach(function (rowSel) {
      try {
        document.querySelectorAll(rowSel + ' .launcher-anrede-btn').forEach(function (btn) {
          btn.classList.toggle('active', btn.dataset.val === (val || 'null'));
        });
      } catch (e) { /* DOM query failed — silently ignore */ }
    });
  }

  // ── Public API ─────────────────────────────────────────────────────────────
  window.NerveLauncher = {
    open: open,
    close: close,
    isActive: function () { return state.micStarted; },
    _setAnrede: _setAnrede,
    _setVorwissen: _setVorwissen,
    stopForNavigation: function () { if (state.micStarted) _stopMic(); }
  };

  // ── Phase 08.23.2.D Test-Hook (2026-05-27) ───────────────────────────────
  // Nur aktiv wenn URL-Param ?test=1 oder &test=1 — sonst unsichtbar (kein
  // Production-Test-Pfad-Leak). Erlaubt UX-Tests aus Browser-Console ohne
  // SID-Lookup oder Server-Manipulation. Pflicht weil outcome_ready/audio_health_warning
  // Server->Client Push-Events sind, die vom Client nicht simulierbar sind.
  if (window.location.search.indexOf('test=1') >= 0) {
    window.__phaseDTest = {
      renderOutcome: function (d) {
        try { _renderOutcomeUx(d); console.log('[PhaseD-Test] renderOutcome OK', d); }
        catch (e) { console.error('[PhaseD-Test] renderOutcome Fehler:', e); }
      },
      showAudioWarn: function (score) {
        try { _showAudioWarning(score); console.log('[PhaseD-Test] showAudioWarn OK score=' + score); }
        catch (e) { console.error('[PhaseD-Test] showAudioWarn Fehler:', e); }
      }
    };
    console.log('[PhaseD-Test] Hook aktiv. Befehle:');
    console.log("  window.__phaseDTest.renderOutcome({outcome:'meeting_booked', confidence:0.95, source:'ai_auto', call_id:'test'})");
    console.log("  window.__phaseDTest.renderOutcome({outcome:'callback', confidence:0.80, source:'ai_auto_unsicher', call_id:'test'})");
    console.log("  window.__phaseDTest.renderOutcome({outcome:null, confidence:0.55, source:null, call_id:'test'})");
    console.log("  window.__phaseDTest.showAudioWarn(0.55)");
  }

  // ── Phase 08.20 D-06: PiP Du/Sie toggle + Vorwissen override (global fns) ─
  // These run in the PiP window context; nerveSio / currentSid are set by pip-launcher.
  window.pipSetAnrede = function (anrede) {
    // R3-fix: elements live in pipWindow.document after _setupPipWindow moves them -- use pipEl().
    var duBtn = pipEl('pip-anrede-du');
    var sieBtn = pipEl('pip-anrede-sie');
    var badge = pipEl('pip-anrede-badge');
    if (duBtn) duBtn.classList.toggle('active', anrede === 'du');
    if (sieBtn) sieBtn.classList.toggle('active', anrede === 'sie');
    if (badge) badge.style.display = 'none';
    if (state.socket && state.socket.connected) {
      state.socket.emit('set_anrede', { anrede: anrede });
    }
  };

  window.pipVorwissenEdit = function () {
    // R4-fix: elements live in pipWindow.document after _setupPipWindow -- use pipEl().
    var indicator = pipEl('pip-vorwissen-indicator');
    var edit = pipEl('pip-vorwissen-edit');
    if (indicator) indicator.style.display = 'none';
    if (edit) edit.style.display = 'block';
  };

  window.pipSetVorwissen = function (val) {
    // R4-fix: elements live in pipWindow.document after _setupPipWindow -- use pipEl().
    var labels = { niedrig: 'Wenig', mittel: 'Vertraut', hoch: 'Kennt uns', 'null': 'Weiß nicht' };
    var labelEl = pipEl('pip-vorwissen-label');
    var edit = pipEl('pip-vorwissen-edit');
    var indicator = pipEl('pip-vorwissen-indicator');
    if (labelEl) labelEl.textContent = labels[val] || 'Weiß nicht';
    if (edit) edit.style.display = 'none';
    if (indicator) indicator.style.display = 'flex';
    var _pipDoc = (state.pipWindow && !state.pipWindow.closed) ? state.pipWindow.document : document;
    _pipDoc.querySelectorAll('#pip-vorwissen-edit .pip-vorwissen-pill').forEach(function (btn) {
      btn.classList.toggle('active', btn.dataset.val === (val || 'null'));
    });
    if (state.socket && state.socket.connected) {
      state.socket.emit('set_vorwissen', { level: val });
    }
  };

  // D-06: Du/Sie detection toast (shown on server anrede_switch_detected event)
  var _anredeToastActive = false;
  var _anredeToastDebounceMs = 60000;
  var _anredeLastToastTime = 0;

  window.pipShowAnredeToast = function () {
    var now = Date.now();
    if (_anredeToastActive || (now - _anredeLastToastTime) < _anredeToastDebounceMs) return;
    _anredeToastActive = true;
    _anredeLastToastTime = now;
    var badge = document.getElementById('pip-anrede-badge');
    if (badge) badge.style.display = 'inline-block';
    var toast = document.getElementById('pip-anrede-toast');
    if (toast) toast.style.display = 'block';
    setTimeout(function () { window.pipAnredeToastDismiss(); }, 15000);
  };

  window.pipAnredeToastAccept = function () {
    window.pipSetAnrede('du');
    _anredeToastActive = false;
    var toast = document.getElementById('pip-anrede-toast');
    if (toast) toast.style.display = 'none';
    setTimeout(function () {
      var badge = document.getElementById('pip-anrede-badge');
      if (badge) badge.style.display = 'none';
    }, 3000);
  };

  window.pipAnredeToastDismiss = function () {
    _anredeToastActive = false;
    var toast = document.getElementById('pip-anrede-toast');
    if (toast) toast.style.display = 'none';
    var badge = document.getElementById('pip-anrede-badge');
    if (badge) badge.style.display = 'none';
    if (window.nerveSio) {
      window.nerveSio.emit('anrede_switch_rejected', { sid: window.currentSid || '' });
    }
  };

  // Window-exposed for cross-file usage:
  //   window.mdToHtml — used by inline scripts for PiP briefing tab (Phase 08.20.3 Modus B)
  //   window.pipSetAnrede / pipVorwissenEdit / pipSetVorwissen — PiP onclick handlers
  window.mdToHtml = mdToHtml;

  // Nav-Guard: Custom-Modal bei Link-Klick mit aktivem Call (08.19.5.2 Scope-Update)
  // beforeunload bleibt als Fallback fuer Tab-Close / Browser-Zurueck / URL-Eingabe.
  var _pendingNavUrl = null;

  // ── Nav-Guard: Click-Interceptor + Modal-Steuerung (Phase 08.19.5.4) ──────────
  // Event-Delegation auf document — DOM-Timing-sicher (kein querySelector bei IIFE-Load).
  // beforeunload bleibt als Fallback fuer Tab-Close / Browser-Zurueck / URL-Eingabe.

  // IIFE-Scope-Hinweis: window._nerveNavConfirm wird auf window zugewiesen damit
  // onclick="_nerveNavConfirm(false/true)" in base.html aus dem globalen Scope auflösbar ist.
  // Alle anderen Helfer (_nerveNavOpenModal, _nerveNavCleanupListeners, _nerveNavOnKeydown)
  // bleiben als IIFE-lokale Variablen — kein window.-Prefix noetig.

  window._nerveNavConfirm = function(confirm) {
    var overlay = document.getElementById('nerveNavModal');
    if (confirm === true) {
      // "Call beenden & verlassen" — Mic stoppen dann navigieren
      if (overlay) overlay.classList.remove('open');
      _nerveNavCleanupListeners();
      _stopMic();
      if (_pendingNavUrl) {
        window.location.href = _pendingNavUrl;
      }
      _pendingNavUrl = null;
    } else {
      // "Hier bleiben" — Modal schliessen, keine Navigation
      if (overlay) overlay.classList.remove('open');
      _nerveNavCleanupListeners();
      _pendingNavUrl = null;
    }
  };

  // ESC-Handler (gespeichert fuer removeEventListener)
  var _nerveNavOnKeydown = null;

  function _nerveNavCleanupListeners() {
    if (_nerveNavOnKeydown) {
      document.removeEventListener('keydown', _nerveNavOnKeydown);
      _nerveNavOnKeydown = null;
    }
  }

  function _nerveNavOpenModal(targetUrl) {
    _pendingNavUrl = targetUrl;
    var overlay = document.getElementById('nerveNavModal');
    if (!overlay) return;
    overlay.classList.add('open');

    // ESC-Taste: schliesst Modal ohne Navigation (== "Hier bleiben")
    _nerveNavOnKeydown = function (e) {
      if (e.key === 'Escape') {
        e.preventDefault();
        window._nerveNavConfirm(false);
      }
    };
    document.addEventListener('keydown', _nerveNavOnKeydown);

    // Overlay-Klick ausserhalb .n-modal-card: schliesst Modal ohne Navigation
    overlay.onclick = function (e) {
      if (e.target === overlay) {
        window._nerveNavConfirm(false);
      }
    };
  }

  // Click-Interceptor: Event-Delegation auf document (DOM-Timing-sicher)
  // Selector D-01 (SPEC gesperrt): '.n-nav-item, a.popup-item-logout'
  // Bedingung: state.micStarted truthy (konsistent mit beforeunload-Handler)
  // capture:true: Listener faeuert in Capture-Phase -- vor element-level onclick-Handlern.
  // Manueller Fallback: Lucide-SVG-Kind-Elemente koennen closest() zum HTML-Ancestor
  // in seltenen Browser-Faellen nicht traversieren -- parentElement-Loop als Absicherung.
  document.addEventListener('click', function (e) {
    if (!state.micStarted) return; // Kein aktiver Call -- normale Navigation
    var el = e.target.closest('.n-nav-item, a.popup-item-logout');
    // Fallback: manuelles Traversieren fuer SVG-zu-HTML-Grenzfaelle (Lucide-Icons)
    if (!el) {
      var node = e.target;
      while (node && node !== document) {
        if (node.matches && node.matches('.n-nav-item, a.popup-item-logout')) {
          el = node;
          break;
        }
        node = node.parentElement;
      }
    }
    if (!el) return;
    var href = el.getAttribute('href');
    if (!href || href === '#' || href.indexOf('javascript:') === 0) return; // Programmatic nav, kein Page-Load
    e.preventDefault();
    e.stopPropagation();
    _nerveNavOpenModal(href);
  }, true); // capture:true -- sichert Prioritaet gegenueber element-level Handlern

  window.addEventListener('beforeunload', function(e) {
    if (state.micStarted) {
      e.preventDefault();
      e.returnValue = '';
    }
  });

  // ── Phase 08.23.2.C.R: Klick-Handler fuer pip-mode-indicator Toggle-Button (300ms Throttle) ──
  var _modeBtnThrottle = 0;
  var _modeBtn = document.getElementById('pip-mode-indicator');
  if (_modeBtn) {
    _modeBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      var _now = Date.now();
      if (_now - _modeBtnThrottle < 300) { return; }
      _modeBtnThrottle = _now;
      var newCategory = (state.contactCategory === 'gatekeeper') ? 'target' : 'gatekeeper';
      if (state.socket && state.socket.emit) {
        state.socket.emit('manual_mode_toggle', { category: newCategory });
      }
    });
  }

  // ── Phase 08.23.2.D - Outcome-UX Hilfsfunktionen ─────────────────────────

  function _showAudioWarning(score) {
    var host = document.querySelector('.pip-header-mic-area') || document.querySelector('.pip-header') || document.body;
    var existing = document.getElementById('pip-audio-warn');
    if (existing) existing.remove();
    var el = document.createElement('span');
    el.id = 'pip-audio-warn';
    el.className = 'pip-audio-warn';
    el.setAttribute('data-tip', 'Audio-Qualität schlecht');
    el.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="1" y1="1" x2="23" y2="23"/><path d="M9 9v3a3 3 0 0 0 5.12 2.12M15 9.34V4a3 3 0 0 0-5.94-.6M17 16.95A7 7 0 0 1 5 12v-2m14 0v2a7 7 0 0 1-.11 1.23"/></svg>';
    host.appendChild(el);
    setTimeout(function () { if (el && el.parentNode) el.parentNode.removeChild(el); }, 5000);
  }

  // ── Outcome-Flow Helpers (Phase 08.23.2.D.UX-05 — D-W3-01/02/06) ──────────

  var _OUTCOME_OPTS = [
    ['meeting_booked',     'Termin gebucht'],
    ['callback',           'Rückruf vereinbart'],
    ['send_info',          'Infos zusenden'],
    ['wrong_person',       'Falsche Person'],
    ['gatekeeper_blocked', 'Gatekeeper blockt'],
    ['no_interest',        'Kein Interesse'],
    ['contract_signed',    'Abschluss'],
  ];

  var _FOLLOWUP_MAP = {
    meeting_booked:     'meeting',
    callback:           'callback',
    send_info:          'send_info',
    gatekeeper_blocked: 'retry_internal',
  };

  function _deriveFollowupIntent(outcome) {
    return _FOLLOWUP_MAP[outcome] || 'none';
  }

  // ── Phase 08.23.2.D.UX.1 — zentrale 5-Zustand-Entscheidung (DC-01/DC-02 + F1) ──
  // Single source of truth = static/outcome-modal-state.js (UMD: Browser-Global +
  // Node-Export). pip-launcher.js kann nicht unter Node geladen werden (window-Zugriff
  // auf Top-Level), daher die Extraktion in ein DOM-freies Helper-Modul (Plan 04
  // BLOCKER-2 Fallback). Alle drei Call-Sites rendern ueber _renderOutcomeUx -> _decideModalState.
  var _decideModalState = (typeof window !== 'undefined' && window.NerveOutcomeModalState)
    ? window.NerveOutcomeModalState._decideModalState
    : function () { return 'unsicher'; };  // defensiver Fallback falls Helper-Script fehlt

  function _renderOutcomeUx(data) {
    // NEW-1/F5 (BLOCKER): alle Lookups + Section-Erzeugung PiP-aware. Bare document
    // trifft im PiP-Modus das Haupt-Fenster -> Outcome-Screen waere fuer den User unsichtbar.
    var _doc = (state.pipWindow && !state.pipWindow.closed) ? state.pipWindow.document : document;
    var sec = pipEl('pip-outcome-section');
    if (!sec) {
      var host = pipEl('pip-postcall') || _doc.querySelector('#nlp-section-postcall') || _doc.body;
      sec = _doc.createElement('div');
      sec.id = 'pip-outcome-section';
      sec.className = 'n-glass pip-outcome-section';
      host.appendChild(sec);
    }
    // Idempotenz-Guard (D.UX constraint — beibehalten, jetzt auf der PiP-sec)
    if (sec.dataset.outcomeRendered === '1') return;
    sec.innerHTML = '';

    var haikuOutcome = data.outcome;
    var conf = +data.confidence || 0;
    var callId = data.call_id;

    if (!callId) return;

    // D.UX.1: zentrale Zustands-Entscheidung — treibt Badge/Hint/Vorauswahl/Confirm
    var modalState = _decideModalState(data);

    // ── Header ───────────────────────────────────────────────────────────────
    var header = _doc.createElement('div');
    header.className = 'pip-outcome-header';
    header.textContent = 'Call wirklich beenden?';   // B-01: der Screen IST die Bestaetigung
    sec.appendChild(header);

    // HIGH-2: outcomeRendered='1' BRANCH-UNABHAENGIG setzen — sodass auch der
    // kein_versuch-/Timeout-Branch ihn setzt und ein Late-Haiku-Socket-Emit den
    // bereits gerenderten Screen NICHT mehr ueberschreibt. NICHT in einen state-Zweig packen.
    sec.dataset.outcomeRendered = '1';

    // ── Zustand 5 'final' (F1): Reconnect auf bereits finalisierten Call ──────
    // Read-only Anzeige des vom User gewaehlten Outcomes. KEIN Disclaimer, kein erneuter Confirm.
    if (modalState === 'final') {
      var finalSummary = _doc.createElement('div');
      finalSummary.className = 'pip-outcome-summary';  // Teal — wiederverwendet (WARN-1, kein neuer Style)
      finalSummary.textContent = '✓ ' + escHtml(_outcomeLabelDe(haikuOutcome));
      sec.appendChild(finalSummary);
      return;
    }

    // State: welches Outcome gerade fuer Confirm ausgewaehlt ist — NUR bei 'sicher'.
    var selectedOutcome = (modalState === 'sicher' && haikuOutcome) ? haikuOutcome : null;
    // U-01: bei 'unsicher' wird der Haiku-Vorschlag ROT vorausgewaehlt (Optik), zaehlt
    // aber NICHT als bestaetigbar — Confirm bleibt disabled bis aktiver Tap.
    var presetUnsicher = (modalState === 'unsicher' && haikuOutcome) ? haikuOutcome : null;

    // ── Disclaimer nur bei 'unsicher' (U-01) ─────────────────────────────────
    // Ersetzt den alten Teal-Outline-Badge 'KI unsicher — bitte wählen' (U-04 supersedes D.UX.1).
    if (modalState === 'unsicher') {
      var disclaimer = _doc.createElement('div');
      disclaimer.className = 'pip-outcome-disclaimer';  // var(--btn-danger-text), Token-only (Task 3)
      disclaimer.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" '
        + 'viewBox="0 0 24 24" fill="none" stroke="#f87171" stroke-width="2" stroke-linecap="round" '
        + 'stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/>'
        + '<path d="M12 9v4"/><path d="M12 17h.01"/></svg>'
        + '<span>KI unsicher, bitte prüfen</span>';
      sec.appendChild(disclaimer);
    }

    // ── Hint nur bei Zustand 1 ('kein_versuch', confidence===0) ──────────────
    if (modalState === 'kein_versuch') {
      var hint = _doc.createElement('div');
      hint.className = 'pip-outcome-hint';  // var(--page-text-secondary) — kein inline Color (WARN-1)
      hint.textContent = 'Automatische Erkennung nicht verfügbar';
      sec.appendChild(hint);
    }

    // ── 7 Buttons ────────────────────────────────────────────────────────────
    var grid = _doc.createElement('div');
    grid.className = 'pip-outcome-btn-grid';
    var btnEls = {};
    var confirmBtn; // forward-ref fuer click-Handler

    _OUTCOME_OPTS.forEach(function(pair) {
      var btn = _doc.createElement('button');
      btn.type = 'button';
      btn.className = 'n-btn-ghost pip-outcome-btn';
      btn.dataset.value = pair[0];
      btn.textContent = escHtml(pair[1]);
      btn.style.minHeight = '44px';  // Touch-Target min 44px

      // 'sicher': teal Vorauswahl (bestaetigbar).
      if (pair[0] === selectedOutcome) {
        btn.classList.add('pip-outcome-btn--selected');
      }
      // 'unsicher': ROTE Vorauswahl (Optik) — NICHT bestaetigbar bis aktiver Tap (U-01).
      if (pair[0] === presetUnsicher) {
        btn.classList.add('pip-outcome-btn--selected-unsicher');
      }

      btn.addEventListener('click', function() {
        // Deselect alle (BEIDE Vorauswahl-Klassen) — der aktive Tap ist der "bewusste Klick" (U-02).
        Object.keys(btnEls).forEach(function(k) {
          btnEls[k].classList.remove('pip-outcome-btn--selected');
          btnEls[k].classList.remove('pip-outcome-btn--selected-unsicher');
        });
        btn.classList.add('pip-outcome-btn--selected');  // immer teal nach aktivem Tap
        selectedOutcome = pair[0];
        // Disclaimer-Zeile entfernen (falls vorhanden) — Unsicherheit ist aufgeloest.
        var _dc = sec.querySelector('.pip-outcome-disclaimer');
        if (_dc && _dc.parentNode) _dc.parentNode.removeChild(_dc);
        if (confirmBtn) {
          confirmBtn.disabled = false;
          confirmBtn.classList.remove('pip-outcome-btn--disabled');
        }
      });
      btnEls[pair[0]] = btn;
      grid.appendChild(btn);
    });
    sec.appendChild(grid);

    // ── Bestätigen-Button ─────────────────────────────────────────────────────
    confirmBtn = _doc.createElement('button');
    confirmBtn.type = 'button';
    confirmBtn.className = 'n-btn-primary pip-outcome-confirm-btn';
    confirmBtn.textContent = 'Bestätigen';
    confirmBtn.style.minHeight = '44px';
    // Disabled wenn kein bestaetigbares Outcome (unsicher/kein_versuch bis Tap); sofort aktiv bei 'sicher'.
    if (!selectedOutcome) {
      confirmBtn.disabled = true;
      confirmBtn.classList.add('pip-outcome-btn--disabled');
    }

    confirmBtn.addEventListener('click', function() {
      if (confirmBtn.disabled) return;  // Doppelklick-Guard
      if (!selectedOutcome) return;
      // MEDIUM-3 Submit-Lock: SOFORT sperren vor dem fetch — kein Double-Submit.
      confirmBtn.disabled = true;
      confirmBtn.classList.add('pip-outcome-btn--disabled');

      // outcome_source Mapping per D-W3-06 (three-way logic):
      // State A (conf >= 0.90 + AI-Vorschlag): ai_auto
      // State B (0.70 <= conf < 0.90 + AI-Vorschlag bestaetigt): ai_auto_unsicher
      // Everything else: user_corrected
      var outcomeSource;
      if (conf >= 0.90 && selectedOutcome === haikuOutcome) {
        outcomeSource = 'ai_auto';
      } else if (conf >= 0.70 && selectedOutcome === haikuOutcome) {
        outcomeSource = 'ai_auto_unsicher';
      } else {
        outcomeSource = 'user_corrected';
      }

      var followupIntent = _deriveFollowupIntent(selectedOutcome);

      // In-flight-Label (UI-SPEC)
      confirmBtn.textContent = 'Bewertung wird berechnet…';

      // CSRF null-check PFLICHT (TypeError wenn meta-Tag fehlt)
      var csrfMeta = document.querySelector('meta[name="csrf-token"]');
      var csrfToken = csrfMeta ? csrfMeta.getAttribute('content') : '';

      fetch('/api/calls/' + encodeURIComponent(callId) + '/correct_outcome', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken,
        },
        body: JSON.stringify({
          outcome: selectedOutcome,
          followup_intent: followupIntent,
          outcome_source: outcomeSource,
        }),
      })
      .then(function(r) { return r.ok ? r.json() : null; })
      .then(function(json) {
        if (!json || !json.ok) {
          // MEDIUM-3: Hard-Error -> Button wieder freigeben fuer erneuten Versuch.
          confirmBtn.textContent = 'Konnte nicht speichern – bitte erneut auf Bestätigen tippen.';
          confirmBtn.disabled = false;
          confirmBtn.classList.remove('pip-outcome-btn--disabled');
          return;
        }
        state.lastOutcome = json.outcome || selectedOutcome;

        // ── S-03 (Task 3): Score + Basis-Analytics SOFORT zusammen, PiP-aware + null-safe.
        // Reveal der postcall-Section ist der EINZIGE Ort (F9 — Score-Hide-Owner).
        var _scoreSec = pipEl('nlp-section-postcall');
        if (_scoreSec) _scoreSec.style.display = '';
        // FIX: Score-Karten-Kinder wieder einblenden, die _showLadebalken1 bis Confirm versteckt hatte.
        if (_scoreSec) {
          var _actEl = _scoreSec.querySelector('.pip-postcall-actions'); if (_actEl) _actEl.style.display = '';
        }

        // Score aus json.final_score (S-01, kein _calcScore). Haengt NICHT an pendingPostcall.
        if (json.final_score !== undefined && json.final_score !== null) {
          var scoreEl = pipEl('nlp-postcall-score');
          if (scoreEl) {
            scoreEl.style.display = '';
            scoreEl.textContent = String(json.final_score) + '%';
            var _fs = +json.final_score;
            scoreEl.style.color = (_fs >= 70) ? 'var(--session-score-high)'
              : (_fs >= 40) ? 'var(--session-score-mid)'
              : 'var(--session-score-low)';
            // Score-Label auf den UI-SPEC-Copy-Contract setzen (PiP-aware via Sibling).
            var _lbl = scoreEl.parentNode ? scoreEl.parentNode.querySelector('.pip-postcall-label') : null;
            if (_lbl) { _lbl.style.display = ''; _lbl.textContent = 'Coaching-Score'; }
          }
          var detailsBtn = pipEl('nlp-btn-details');
          if (detailsBtn) { detailsBtn.style.display = ''; detailsBtn.disabled = false; }
          // F9: Trend mit dem BESTAETIGTEN final_score fuettern (nicht _calcScore).
          _fetchAndRenderTrend(json.final_score);
        }

        // Basis-Analytics (Kaufbereitschaft / Redeanteil / Einwaende) — NULL-SAFE.
        // state.pendingPostcall kann am Confirm-Zeitpunkt undefined sein (Timeout/Race/Stale).
        var _pp = state.pendingPostcall;
        if (_pp) {
          _renderQuickStats(_pp);   // PiP-aware, zeigt Einwaende/Redeanteil/Dauer/Skript-Tiles
          _renderSparkline(_pp);
        } else {
          // Fallback: Score-Karte allein, KPI-Block uebersprungen — KEIN Throw, KEIN undefined-Deref.
          var _qs = pipEl('nlp-postcall-quickstats');
          if (_qs) _qs.innerHTML = '';
        }

        // Outcome-Sektion zu 1-Zeiler kollabieren (terminaler Screen, B-03 — kein Back-to-Call).
        sec.innerHTML = '';
        var summary = _doc.createElement('div');
        summary.className = 'pip-outcome-summary';
        summary.textContent = '✓ ' + escHtml(_outcomeLabelDe(json.outcome || selectedOutcome));
        sec.appendChild(summary);

        // MM-03 (G-MEET Plan 05): Meeting-Form ERST nach dem Score-Screen — nicht im rohen
        // meeting_booked-Branch. selectedOutcome ist im Closure. renderMeetingForm mountet in
        // einen eigenen Child-Node (#meeting-form-mount), clobbert den Score-Screen NICHT.
        if (selectedOutcome === 'meeting_booked') {
          try { renderMeetingForm(json); } catch (_mfe) { console.error('[G-MEET] renderMeetingForm:', _mfe); }
        }
      })
      .catch(function(e) {
        console.error('[PhaseD.UX] correct_outcome POST Fehler:', e);
        // MEDIUM-3: Re-Enable im catch — erneuter Versuch moeglich, kein Double-Submit waehrend POST.
        confirmBtn.textContent = 'Konnte nicht speichern – bitte erneut auf Bestätigen tippen.';
        confirmBtn.disabled = false;
        confirmBtn.classList.remove('pip-outcome-btn--disabled');
      });
    });
    sec.appendChild(confirmBtn);
  }

  // ── Meeting-Merk-Fenster (Phase 08.23.2.G-MEET Plan 05) ──────────────────────
  // Mountet NACH dem D.UX.4 Score-Screen (MM-03) in einen eigenen Child-Node im
  // PiP-Postcall-Host. Konsumiert die live Plan-04-Routen. ALLE Lookups via pipEl.

  // MM-01: tz-NAIVER datetime-local-Wert -> offset-tragende ISO-8601 (Backend lehnt
  // offset-lose Werte mit 400 ab). Lokale Browser-Wandzeit + expliziter Offset.
  function _toIsoWithOffset(localVal) {
    if (!localVal) return null;
    var d = new Date(localVal);                 // als LOKALE Browser-Zeit interpretiert
    if (isNaN(d.getTime())) return null;
    var off = -d.getTimezoneOffset();           // Minuten, z.B. +120 fuer MESZ
    var sign = off >= 0 ? '+' : '-';
    var abs = Math.abs(off);
    function p(n) { return String(n).padStart(2, '0'); }
    var hh = p(Math.floor(abs / 60));
    var mm = p(abs % 60);
    return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate())
         + 'T' + p(d.getHours()) + ':' + p(d.getMinutes()) + ':' + p(d.getSeconds())
         + sign + hh + ':' + mm;                // z.B. "2026-06-03T10:00:00+02:00"
  }

  // datetime-local default: naechster Werktag 10:00 (Sa->Mo, So->Mo), client-side.
  function _nextBusinessDay1000Value() {
    var d = new Date();
    d.setDate(d.getDate() + 1);
    while (d.getDay() === 0 || d.getDay() === 6) { d.setDate(d.getDate() + 1); }  // 0=So,6=Sa
    d.setHours(10, 0, 0, 0);
    function p(n) { return String(n).padStart(2, '0'); }
    return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate())
         + 'T' + p(d.getHours()) + ':' + p(d.getMinutes());                       // naiv (datetime-local)
  }

  var _MEETING_WEEKDAYS_DE = ['Sonntag', 'Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag'];
  function _formatBriefingDate(iso) {
    if (!iso) return '';
    var d = new Date(iso);
    if (isNaN(d.getTime())) return '';
    function p(n) { return String(n).padStart(2, '0'); }
    return _MEETING_WEEKDAYS_DE[d.getDay()] + ', ' + p(d.getDate()) + '.' + p(d.getMonth() + 1) + '. · '
         + p(d.getHours()) + ':' + p(d.getMinutes());
  }

  function _meetingMount() {
    var host = pipEl('nlp-section-postcall');
    if (!host) return null;
    var mount = host.querySelector('#meeting-form-mount');
    if (!mount) {
      mount = (host.ownerDocument || document).createElement('div');
      mount.id = 'meeting-form-mount';
      host.appendChild(mount);                  // MM-03: eigener Child-Node, NICHT host.innerHTML
    }
    return mount;
  }

  function _closeMeetingForm() {
    var mount = pipEl('meeting-form-mount');
    if (mount && mount.parentNode) mount.parentNode.removeChild(mount);
  }

  function renderMeetingForm() {
    var mount = _meetingMount();
    if (!mount) return;
    mount.innerHTML = '';                        // MM-03: NUR den eigenen Mount clearen, nie den Host

    // User-facing Copy mit echten Umlauten; HTML-ids/Klassen ASCII.
    // Firma = Pflichtfeld (André-Direktive 2026-06-02): sichtbare Markierung + required.
    var dtDefault = _nextBusinessDay1000Value();
    mount.innerHTML =
      '<div class="n-meeting-card">'
    +   '<div class="n-meeting-title">Termin festhalten</div>'
    +   '<div class="n-meeting-subline">Schnell sichern, bevor du den nächsten Call startest.</div>'
    +   '<div class="n-meeting-context">'
    +     '<span class="n-meeting-context-time">Anruf beendet</span>'
    +     '<span class="n-meeting-chip"><i data-lucide="calendar-check"></i>Termin gebucht</span>'
    +   '</div>'
    +   '<div class="n-meeting-field-row">'
    +     '<div class="n-meeting-field">'
    +       '<label class="n-label" for="meeting-person">Ansprechpartner</label>'
    +       '<input class="n-input" id="meeting-person" type="text" autocomplete="off">'
    +     '</div>'
    +     '<div class="n-meeting-field" id="meeting-firma-field">'
    +       '<label class="n-label" for="meeting-firma">Firma'
    +         '<span class="n-meeting-required-mark" aria-hidden="true">*</span></label>'
    +       '<input class="n-input" id="meeting-firma" type="text" required aria-required="true" autocomplete="off">'
    +       '<span class="n-meeting-error" id="meeting-firma-error" role="alert"></span>'
    +     '</div>'
    +   '</div>'
    +   '<div class="n-meeting-field">'
    +     '<label class="n-label" for="meeting-datetime">Datum &amp; Uhrzeit</label>'
    +     '<input class="n-input" id="meeting-datetime" type="datetime-local" value="' + dtDefault + '">'
    +   '</div>'
    +   '<div class="n-meeting-field">'
    +     '<label class="n-label" for="meeting-notes">Worum geht’s?</label>'
    +     '<input class="n-input" id="meeting-notes" type="text" placeholder="z. B. Angebot vorstellen, Konditionen klären…" autocomplete="off">'
    +   '</div>'
    +   '<div class="n-meeting-checkbox" id="meeting-autosave" role="checkbox" aria-checked="false" tabindex="0">'
    +     '<span class="n-meeting-checkbox-box"><i data-lucide="check"></i></span>'
    +     '<span>'
    +       '<span class="n-meeting-checkbox-label">Solche Termine künftig automatisch merken</span>'
    +       '<span class="n-meeting-checkbox-hint">Merkt sich deine Auswahl für später. Jederzeit abschaltbar.</span>'
    +     '</span>'
    +   '</div>'
    +   '<div class="n-meeting-privacy">'
    +     '<i data-lucide="shield-check"></i>'
    +     '<span>Kontaktdaten werden als B2B-Geschäftskontakt gespeichert (berechtigtes Interesse, Art. 6 Abs. 1 f DSGVO), um dir beim nächsten Anruf ein Briefing zu zeigen.</span>'
    +   '</div>'
    +   '<span class="n-meeting-error" id="meeting-error" role="alert"></span>'
    +   '<div class="n-meeting-actions">'
    +     '<button type="button" class="n-btn-primary" id="meeting-save-btn"><i data-lucide="bookmark-check"></i> Termin merken</button>'
    +     '<button type="button" class="n-btn-ghost" id="meeting-skip-btn">Überspringen</button>'
    +   '</div>'
    + '</div>';

    // DSGVO-Checkbox: default IMMER unchecked (Art. 25 Abs. 2). Toggle persistiert die Auswahl.
    var cb = pipEl('meeting-autosave');
    function _setCb(on) {
      if (!cb) return;
      cb.classList.toggle('on', !!on);
      cb.setAttribute('aria-checked', on ? 'true' : 'false');
    }
    function _toggleCb() {
      var on = !cb.classList.contains('on');
      _setCb(on);
      // Nur Persistenz der Auswahl (KEINE honor-Logik — MM-02 deferred -> Backlog 999.3).
      try {
        fetch('/crm/preferences', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
          body: JSON.stringify({ auto_save_meeting: on })
        });
      } catch (_) {}
    }
    if (cb) {
      cb.addEventListener('click', _toggleCb);
      cb.addEventListener('keydown', function (e) {
        if (e.key === ' ' || e.key === 'Enter') { e.preventDefault(); _toggleCb(); }
      });
    }
    // Spiegelung eines ZUVOR explizit gewaehlten Opt-in (Nutzer-Wille, NICHT default-on).
    try {
      fetch('/crm/preferences').then(function (r) { return r.json(); }).then(function (d) {
        if (d && d.auto_save_meeting === true) _setCb(true);
      }).catch(function () {});
    } catch (_) {}

    var saveBtn = pipEl('meeting-save-btn');
    if (saveBtn) saveBtn.addEventListener('click', _onSaveMeeting);
    var skipBtn = pipEl('meeting-skip-btn');
    if (skipBtn) skipBtn.addEventListener('click', _closeMeetingForm);

    if (typeof lucide !== 'undefined' && lucide.createIcons) {
      try { lucide.createIcons(); } catch (_) {}
    }
  }

  function _onSaveMeeting() {
    var saveBtn = pipEl('meeting-save-btn');
    var firmaEl = pipEl('meeting-firma');
    var firma = (firmaEl && firmaEl.value || '').trim();

    // Firma = Pflichtfeld (André-Direktive 2026-06-02): client-seitig blocken, Eingaben ERHALTEN.
    var firmaField = pipEl('meeting-firma-field');
    var firmaErr = pipEl('meeting-firma-error');
    if (!firma) {
      if (firmaField) firmaField.classList.add('n-meeting-field--error');
      if (firmaErr) firmaErr.textContent = 'Firma ist Pflicht.';
      if (firmaEl) firmaEl.focus();
      return;                                   // KEIN POST, KEIN disable -> Felder behalten Werte
    }
    if (firmaField) firmaField.classList.remove('n-meeting-field--error');
    if (firmaErr) firmaErr.textContent = '';

    if (saveBtn) saveBtn.disabled = true;       // MM-05: vor fetch sperren (Doppel-Submit-Schutz)
    fetch('/crm/meetings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
      body: JSON.stringify({
        firma: firma,
        ansprechpartner: (pipEl('meeting-person') || {}).value || '',
        scheduled_at: _toIsoWithOffset((pipEl('meeting-datetime') || {}).value),  // MM-01 offset-ISO
        notes: (pipEl('meeting-notes') || {}).value || '',
        call_id: state.lastCallId || null
      })
    }).then(function (r) { return r.json(); }).then(function (data) {
      if (data && data.ok) {
        renderMeetingConfirm(data);             // Bestaetigung in-place (im Mount)
      } else {
        if (saveBtn) saveBtn.disabled = false;  // MM-05 re-enable
        showMeetingError(sanitizeErrorMsg(data && data.error));
      }
    }).catch(function () {
      if (saveBtn) saveBtn.disabled = false;     // MM-05 re-enable
      showMeetingError('Konnte nicht gespeichert werden. Nochmal versuchen?');
    });
  }

  function showMeetingError(msg) {
    var errEl = pipEl('meeting-error');
    if (errEl) errEl.textContent = msg || 'Konnte nicht gespeichert werden. Nochmal versuchen?';
    // Felder werden NIE geleert (Input-Erhalt, UI-SPEC Error-State).
  }

  function renderMeetingConfirm(data) {
    var mount = pipEl('meeting-form-mount');
    if (!mount) return;
    var firma = (data && data.firma) || '';
    var datePart = _formatBriefingDate(data && data.scheduled_at);   // "Mittwoch, 03.06. · 10:00"
    var thema = ((data && data.thema) || '').trim();
    // MM-06a: kein dangling " · " wenn thema leer.
    var briefingLine = thema ? (thema + ' · ' + datePart) : datePart;
    mount.innerHTML =
      '<div class="n-meeting-card n-meeting-confirm">'
    +   '<div class="n-meeting-confirm-ring"><i data-lucide="bookmark-check"></i></div>'
    +   '<div class="n-meeting-confirm-title">Termin gemerkt</div>'
    +   '<div class="n-meeting-confirm-body">Beim nächsten Anruf von <strong>' + escHtml(firma) + '</strong> zeige ich dir das.</div>'
    +   '<div class="n-meeting-briefing">'
    +     '<i data-lucide="sparkles"></i>'
    +     '<span class="n-meeting-briefing-line">' + escHtml(briefingLine) + '</span>'
    +   '</div>'
    +   '<button type="button" class="n-btn-primary" id="meeting-weiter-btn">Weiter <i data-lucide="arrow-right"></i></button>'
    + '</div>';
    var weiter = pipEl('meeting-weiter-btn');
    if (weiter) weiter.addEventListener('click', _closeMeetingForm);
    if (typeof lucide !== 'undefined' && lucide.createIcons) {
      try { lucide.createIcons(); } catch (_) {}
    }
  }

  function _outcomeLabelDe(val) {
    var m = {
      meeting_booked:     'Termin gebucht',
      callback:           'Rückruf vereinbart',
      send_info:          'Infos zusenden',
      wrong_person:       'Falsche Person',
      gatekeeper_blocked: 'Gatekeeper blockt',
      no_interest:        'Kein Interesse',
      contract_signed:    'Abschluss',
      unknown:            'Unklar',
    };
    return m[val] || (val || '-');
  }

  // _submitOutcomeCorrection() entfernt (Phase 08.23.2.D.UX-05 D-W3-05)
  // Ersetzt durch inline Logik in _renderOutcomeUx() confirmBtn-Handler

})();
