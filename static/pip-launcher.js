// ── NERVE PiP Launcher ─────────────────────────────────────────────────────
// Self-contained IIFE. No dependency on app.js.
// Exposes window.NerveLauncher = { open, close, isActive }
(function () {
  'use strict';

  // ── State ──────────────────────────────────────────────────────────────────
  var state = {
    step: 1,              // 1=mode, 2=precall-option, 3=precall-form, 4=precall-result, 5=skript, 6=live
    mode: null,           // 'cold_call' | 'meeting'
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
    micMuted: false
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
    fetch('/api/launcher/init')
      .then(function (r) { return r.json(); })
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
    state.precallFormData = {
      firma: (document.getElementById('lnr-firma') || {}).value || '',
      ort: (document.getElementById('lnr-ort') || {}).value || '',
      person: (document.getElementById('lnr-person') || {}).value || '',
      branche: (document.getElementById('lnr-branche') || {}).value || '',
      optinfo: (document.getElementById('lnr-optinfo') || {}).value || ''
    };
  }

  function runPrecall() {
    var firma = (document.getElementById('lnr-firma') || {}).value || '';
    if (!firma || firma.trim().length < 2) {
      var errEl = document.getElementById('lnr-precall-error');
      if (errEl) { errEl.textContent = 'Firmenname ist Pflicht (mind. 2 Zeichen).'; errEl.style.display = 'block'; }
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
      headers: { 'Content-Type': 'application/json' },
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
          if (errEl2) { errEl2.textContent = errMsg; errEl2.style.display = 'block'; }
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
        if (errEl2) { errEl2.textContent = msg; errEl2.style.display = 'block'; }
      });
  }

  // ── Step 4: PreCall Result ─────────────────────────────────────────────────
  function renderStep4() {
    var c = content();
    if (!c) return;
    var briefingObj = state.precallBriefing || null;
    var briefingText = briefingObj ? (briefingObj.text || '') : '';
    var found = !!briefingText;

    c.innerHTML = [
      '<div class="launcher-step">',
      '<div class="nav-live-title">' + (found ? 'Recherche-Ergebnis' : 'Keine Daten gefunden') + '</div>',
      found
        ? '<div class="launcher-briefing-html" id="lnr-briefing-view">' + mdToHtml(briefingText) + '</div>'
          + '<textarea class="launcher-briefing" id="lnr-briefing-edit" style="display:none">' + escHtml(briefingText) + '</textarea>'
        : '<div style="color:var(--page-text-muted);font-size:13px;padding:12px 0">Für diese Firma konnten keine öffentlichen Informationen gefunden werden. Du kannst trotzdem fortfahren.</div>',
      '<div class="launcher-actions" style="flex-wrap:wrap;gap:8px">',
      '<button class="launcher-btn-ghost" id="lnr-step4-back">&#8592; Zurück</button>',
      found ? '<button class="launcher-btn-ghost" id="lnr-step4-edit">Ergebnis anpassen</button>' : '',
      '<button class="launcher-btn-ghost" id="lnr-step4-new">Neue Analyse</button>',
      '<button class="launcher-btn-primary" id="lnr-step4-accept">Ergebnis uebernehmen &#8594;</button>',
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
    document.getElementById('lnr-step4-accept').onclick = function () {
      // Save edited briefing text back into the briefing object
      var ta = document.getElementById('lnr-briefing-edit');
      if (ta && state.precallBriefing) state.precallBriefing.text = ta.value || state.precallBriefing.text;
      state.step = 5;
      renderStep();
    };

    var editBtn = document.getElementById('lnr-step4-edit');
    if (editBtn) {
      editBtn.onclick = function () {
        var view = document.getElementById('lnr-briefing-view');
        var ta = document.getElementById('lnr-briefing-edit');
        if (view) view.style.display = 'none';
        if (ta) {
          ta.style.display = 'block';
          ta.style.borderColor = '#00D4AA';
          ta.focus();
          editBtn.style.display = 'none';
        }
      };
    }
  }

  // ── Step 5: Skript & Opener Selection ─────────────────────────────────────
  function renderStep5() {
    var c = content();
    if (!c) return;

    var profileOptions = state.profiles.map(function (p) {
      var sel = p.id === state.activeProfileId ? ' selected' : '';
      return '<option value="' + p.id + '"' + sel + '>' + escHtml(p.name) + '</option>';
    }).join('');

    // Skript-Dropdown
    var skriptOptions = '<option value="">-- Kein Skript --</option>' + state.skripte.map(function (s) {
      var sel = s.id === state.selectedSkriptId ? ' selected' : '';
      return '<option value="' + s.id + '"' + sel + '>' + escHtml(s.name) + '</option>';
    }).join('');

    // Opener-Dropdown
    var openerOptions = '<option value="">-- Kein Opener --</option>' + state.openerItems.map(function (o) {
      var sel = o.id === state.selectedOpenerId ? ' selected' : '';
      return '<option value="' + o.id + '"' + sel + '>' + escHtml(o.name) + '</option>';
    }).join('');

    // Vorschauen
    var skriptPreview = '';
    if (state.selectedSkriptId) {
      var sk = state.skripte.find(function (s) { return s.id === state.selectedSkriptId; });
      if (sk) skriptPreview = escHtml(sk.inhalt);
    }
    var openerPreview = '';
    if (state.selectedOpenerId) {
      var op = state.openerItems.find(function (o) { return o.id === state.selectedOpenerId; });
      if (op) openerPreview = escHtml(op.inhalt);
    }
    // Fallback: alten Opener aus Profil-JSON verwenden wenn keine Opener-Items existieren
    var legacyOpener = (state.profileDaten && state.profileDaten.opener) ? state.profileDaten.opener : '';

    c.innerHTML = [
      '<div class="launcher-step">',
      '<div class="nav-live-title">Skript & Opener wählen</div>',

      // Profil
      state.profiles.length > 0
        ? '<label style="font-size:11px;color:var(--page-text-muted);margin-bottom:2px;display:block">Profil</label><select class="launcher-select" id="lnr-profile-select">' + profileOptions + '</select>'
        : '<div style="color:var(--page-text-muted);font-size:13px">Noch kein Profil angelegt. <a href="/profiles" style="color:#00D4AA">Profil erstellen</a></div>',

      // Skript
      state.skripte.length > 0
        ? '<label style="font-size:11px;color:var(--page-text-muted);margin-top:8px;margin-bottom:2px;display:block">Skript</label><select class="launcher-select" id="lnr-skript-select">' + skriptOptions + '</select>'
        : '',
      '<div class="launcher-opener-preview" id="lnr-skript-preview" style="white-space:pre-wrap;max-height:80px;overflow-y:auto' + (skriptPreview ? '' : ';color:var(--page-text-muted);font-style:italic') + '">' + (skriptPreview || (state.skripte.length > 0 ? 'Skript auswählen für Vorschau' : '')) + '</div>',
      '<textarea class="launcher-briefing" id="lnr-skript-textarea" style="display:none;margin-top:4px" rows="4"></textarea>',
      state.skripte.length > 0
        ? '<button type="button" id="lnr-skript-edit-btn" style="font-size:11px;color:#00D4AA;background:none;border:none;cursor:pointer;padding:2px 0;margin-top:2px">Bearbeiten</button>'
        : '',

      // Opener
      state.openerItems.length > 0
        ? '<label style="font-size:11px;color:var(--page-text-muted);margin-top:8px;margin-bottom:2px;display:block">Opener</label><select class="launcher-select" id="lnr-opener-select">' + openerOptions + '</select>'
        : '',
      '<div class="launcher-opener-preview" id="lnr-opener-preview" style="white-space:pre-wrap' + (openerPreview ? '' : ';color:var(--page-text-muted);font-style:italic') + '">'
        + (openerPreview || (state.openerItems.length > 0 ? 'Opener auswählen für Vorschau' : (legacyOpener ? escHtml(legacyOpener) : 'Kein Opener hinterlegt'))) + '</div>',
      '<textarea class="launcher-briefing" id="lnr-opener-textarea" style="display:none;margin-top:4px" rows="3"></textarea>',
      (state.openerItems.length > 0 || legacyOpener)
        ? '<button type="button" id="lnr-opener-edit-btn" style="font-size:11px;color:#00D4AA;background:none;border:none;cursor:pointer;padding:2px 0;margin-top:2px">Bearbeiten</button>'
        : '',

      '<div class="launcher-actions">',
      '<button class="launcher-btn-ghost" id="lnr-step5-back">&#8592; Zurück</button>',
      '<button class="launcher-btn-ghost" id="lnr-step5-skip">Überspringen</button>',
      '<button class="launcher-btn-primary" id="lnr-step5-start">Call starten &#9654;</button>',
      '</div>',
      '</div>'
    ].join('');

    // Profile change: reload Skripte + Opener
    var profileSel = document.getElementById('lnr-profile-select');
    if (profileSel) {
      profileSel.onchange = function () {
        var pid = parseInt(profileSel.value);
        if (!pid) return;
        fetch('/api/launcher/profile/' + pid)
          .then(function (r) { return r.json(); })
          .then(function (data) {
            state.activeProfileId = data.id;
            state.profileDaten = data.daten || {};
            state.skripte = data.skripte || [];
            state.openerItems = data.opener || [];
            state.selectedSkriptId = null;
            state.selectedOpenerId = null;
            renderStep5();
          })
          .catch(function () {});
      };
    }

    // Skript change: update preview
    var skriptSel = document.getElementById('lnr-skript-select');
    if (skriptSel) {
      skriptSel.onchange = function () {
        state.selectedSkriptId = parseInt(skriptSel.value) || null;
        var preview = document.getElementById('lnr-skript-preview');
        if (preview) {
          var sk = state.skripte.find(function (s) { return s.id === state.selectedSkriptId; });
          preview.textContent = sk ? sk.inhalt : 'Skript auswählen für Vorschau';
          preview.style.fontStyle = sk ? 'normal' : 'italic';
          preview.style.color = sk ? '' : 'var(--page-text-muted)';
        }
      };
    }

    // Opener change: update preview
    var openerSel = document.getElementById('lnr-opener-select');
    if (openerSel) {
      openerSel.onchange = function () {
        state.selectedOpenerId = parseInt(openerSel.value) || null;
        var preview = document.getElementById('lnr-opener-preview');
        if (preview) {
          var op = state.openerItems.find(function (o) { return o.id === state.selectedOpenerId; });
          preview.textContent = op ? op.inhalt : 'Opener auswählen für Vorschau';
          preview.style.fontStyle = op ? 'normal' : 'italic';
          preview.style.color = op ? '' : 'var(--page-text-muted)';
        }
      };
    }

    // Inline edit: Skript
    _wireInlineEdit('lnr-skript-edit-btn', 'lnr-skript-preview', 'lnr-skript-textarea', 'skript');
    // Inline edit: Opener
    _wireInlineEdit('lnr-opener-edit-btn', 'lnr-opener-preview', 'lnr-opener-textarea', 'opener');

    // Navigation
    document.getElementById('lnr-step5-back').onclick = function () {
      state.step = state.precallVerfuegbar ? 2 : 1;
      renderStep();
    };
    document.getElementById('lnr-step5-skip').onclick = function () {
      _collectEditedTexts();
      startCall(false);
    };
    document.getElementById('lnr-step5-start').onclick = function () {
      var s = document.getElementById('lnr-profile-select');
      if (s && s.value) state.activeProfileId = parseInt(s.value);
      _collectEditedTexts();
      startCall(true);
    };
  }

  function _wireInlineEdit(btnId, previewId, textareaId, type) {
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
        var itemId = type === 'skript' ? state.selectedSkriptId : state.selectedOpenerId;
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
        if (type === 'opener') state._editedOpenerText = newText;

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
    overlay.innerHTML = '<div style="background:var(--page-bg,#fff);border:1px solid var(--glass-border);border-radius:12px;padding:24px;max-width:400px;width:90%;text-align:center">'
      + '<div style="font-size:15px;font-weight:700;margin-bottom:12px">' + label + ' auch im Profil ändern?</div>'
      + '<div style="font-size:13px;color:var(--page-text-muted);margin-bottom:16px">Die Änderung gilt sonst nur für diesen Call.</div>'
      + '<div style="display:flex;gap:10px;justify-content:center">'
      + '<button id="lnr-save-no" style="padding:8px 20px;border:1px solid var(--glass-border);border-radius:8px;background:none;color:var(--page-text-color);cursor:pointer;font-size:13px">Nur dieser Call</button>'
      + '<button id="lnr-save-yes" style="padding:8px 20px;border:none;border-radius:8px;background:#00D4AA;color:#06060a;cursor:pointer;font-weight:700;font-size:13px">Im Profil speichern</button>'
      + '</div></div>';
    document.body.appendChild(overlay);

    document.getElementById('lnr-save-no').onclick = function () { overlay.remove(); };
    document.getElementById('lnr-save-yes').onclick = function () {
      fetch(endpoint, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
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
    if (!overlay || !scriptEl || !acceptBtn || !rejectBtn || !cancelBtn) return;

    // Resolve script text: profileDaten.consent_text > default
    var text = (state.profileDaten && state.profileDaten.consent_text)
      ? state.profileDaten.consent_text
      : CONSENT_DEFAULT_TEXT;
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
    var skTa = document.getElementById('lnr-skript-textarea');
    if (skTa && skTa.style.display !== 'none') state._editedSkriptText = skTa.value;
    var opTa = document.getElementById('lnr-opener-textarea');
    if (opTa && opTa.style.display !== 'none') state._editedOpenerText = opTa.value;
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

    close();

    // Set profile server-side if changed (fire and forget)
    if (setProfile && state.activeProfileId) {
      fetch('/api/set_profile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
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
      if (state._editedSkriptText) {
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
      } else if (state.profileDaten && state.profileDaten.opener) {
        openerFuerKi = state.profileDaten.opener;
      }
      if (openerFuerKi) skriptBlöcke = [openerFuerKi].concat(skriptBlöcke);

      state.socket.emit('start_live_session', {
        mode: state.mode || 'cold_call',
        precall_briefing: briefingText,
        skript_inhalt: skriptInhalt || null,
        skript_bloecke: skriptBlöcke.length > 0 ? skriptBlöcke : null
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
    body.style.background = '#F8FAFC';
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

      var beenden = t.closest('#nlp-btn-beenden');
      if (beenden) {
        ev.preventDefault();
        ev.stopPropagation();
        console.log('[NerveLauncher] Beenden click (delegation)');
        try { endCall(); } catch (e) { console.error('[NerveLauncher] endCall err:', e); }
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
    }, true);  // capture phase — vor allen anderen Handlern
    console.log('[NerveLauncher] PiP click-delegation wired');
  }

  function _initPipLive() {
    // Set mode badge
    var badge = pipEl('nlp-mode-badge');
    if (badge) badge.textContent = state.mode === 'meeting' ? 'Meeting' : 'Cold Call';

    // Phase 06.5: Consent ist jetzt Launcher-Gate (vor Call-Start). PiP startet immer direkt im Live-View.
    _showPipLive();

    // Render EWB buttons
    _renderEwbButtons();
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
    var einwaende = (state.profileDaten && state.profileDaten.einwaende) ? state.profileDaten.einwaende : [];
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
    var einwaende = (state.profileDaten && state.profileDaten.einwaende) || [];
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
      var prof = (state.profileDaten && state.profileDaten.einwaende) || [];
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
    return (colors[typ] || 'background:rgba(255,255,255,0.1);color:#c5c9d4') + ';font-size:11px;padding:2px 8px;border-radius:9999px';
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

    if (!inhalt || !inhalt.trim()) {
      container.innerHTML = '<div class="tp-empty">Kein Skript hinterlegt \u2014 Profil bearbeiten</div>';
      state.teleprompterBlocks = [];
      return;
    }

    // D-03: Opener als erster Teleprompter-Block (Phase 0 = Opener für KI-Position-Erkennung)
    var openerText = '';
    if (state._editedOpenerText) {
      openerText = state._editedOpenerText;
    } else if (state.selectedOpenerId && state.openerItems && state.openerItems.length > 0) {
      var selOp = state.openerItems.find(function (o) { return o.id === state.selectedOpenerId; });
      if (selOp) openerText = selOp.inhalt;
    } else if (state.profileDaten && state.profileDaten.opener) {
      openerText = state.profileDaten.opener;
    }

    // Parse blocks by double-newline, prepend opener as block[0]
    var skriptBlocks = inhalt.split(/\n\n+/).filter(function (b) { return b.trim(); });
    var blocks = openerText ? [openerText].concat(skriptBlocks) : skriptBlocks;
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
  function endCall() {
    _stopTimer();
    _stopMic();
    // Architecture fix: reset all live UI state before showing postcall section.
    // Postcall appears over a clean live-UI — eliminates stale DOM/timer/slot bleed-through
    // that caused BUG-11 alternating aborts and symptom-3 slot/timer leaks.
    _resetLiveState();

    // 06.1-r2 BUG-9: UI SOFORT umschalten mit Loading-Skeleton. Backend-Response
    // füllt Score/Tags nachträglich.
    // BUG-15b: KEIN resizeTo auf Postcall — Chrome merkt sich die zuletzt gesetzte
    // PiP-Größe und ignoriert spätere requestWindow-Hints. PiP bleibt bei 480x900,
    // Postcall-Content wird im bestehenden Fenster zentriert.
    _showPostcallLoading();

    // BUG-11 r5 ROOT CAUSE: endCall fetch kann spät resolven während bereits ein
    // neuer Call läuft. Dann würde _showPostcall die Postcall-Section über die
    // Live-UI legen, der User klickt "Nächster Call" aus altem Postcall und killt
    // so den aktiven Call. Capture-Generation beim Fetch-Start, abbrechen wenn
    // inzwischen ein neuer Call gestartet ist (micStarted wieder true).
    var endCallGen = (state.callGen = (state.callGen || 0) + 1);
    fetch('/api/beenden', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_mode: state.mode || 'cold_call',
        precall_briefing: state.precallBriefing
      })
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (state.callGen !== endCallGen || state.micStarted) {
          console.log('[NerveLauncher] Beenden response stale (neue Session läuft) — verworfen');
          return;
        }
        if (!data.ok) { console.error('[NerveLauncher] Beenden error:', data.error); _showPostcallEmpty(); return; }
        state.lastConvId = data.conv_id || null;
        if (data.postcall) {
          _showPostcall(data.postcall);
        } else {
          _showPostcallEmpty();
        }
      })
      .catch(function (err) {
        if (state.callGen !== endCallGen || state.micStarted) {
          console.log('[NerveLauncher] Beenden fetch error ignoriert — neue Session läuft');
          return;
        }
        console.error('[NerveLauncher] Beenden fetch error:', err);
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
    // 06.1-r2 BUG-10: Leerer Call (keine Wörter, keine Einwände) -> kein Score, stattdessen
    // "Kein Gespräch erkannt" — 45% für leere Calls verwirrt nur.
    var berater = (postcall && postcall.berater_words) || 0;
    var kunde = (postcall && postcall.kunde_words) || 0;
    var einwTotal = ((postcall && postcall.einwaende) || []).length;
    if (berater === 0 && kunde === 0 && einwTotal === 0) {
      _showPostcallEmpty();
      return;
    }
    var score = _calcScore(postcall);
    var tags = _buildTags(postcall);
    _showPostcallRaw(score + '%', tags);
    // POLISH-22: Trend + Sparkline + QuickStats zusätzlich rendern
    _renderQuickStats(postcall);
    _renderSparkline(postcall);
    _fetchAndRenderTrend(score);
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
    // Einwände behandelt / gesamt
    var gaDetails = pc.ga_details || [];
    var behandelt = gaDetails.filter(function (x) { return x && x.erfolgreich === true; }).length;
    var einwTotal = (pc.einwaende || []).length;
    var einwStr = einwTotal > 0 ? behandelt + ' / ' + einwTotal : '–';
    var einwAccent = einwTotal > 0 && (behandelt / einwTotal) >= 0.7;
    // Redeanteil (Berater %)
    var total = (pc.berater_words || 0) + (pc.kunde_words || 0);
    var rede = total > 0 ? Math.round((pc.berater_words || 0) / total * 100) : 0;
    var redeStr = rede > 0 ? rede + ' / ' + (100 - rede) : '–';
    // Skript-Abdeckung
    var skript = (pc.skript_abdeckung || {}).gesamt_prozent || 0;
    var skriptStr = skript > 0 ? skript + '%' : '–';
    var skriptAccent = skript >= 80;

    el.innerHTML = [
      '<div class="pip-quickstat"><div class="pip-quickstat-value">' + escHtml(dauerStr) + '</div><div class="pip-quickstat-label">Dauer</div></div>',
      '<div class="pip-quickstat"><div class="pip-quickstat-value' + (einwAccent ? ' accent' : '') + '">' + escHtml(einwStr) + '</div><div class="pip-quickstat-label">Einwände behandelt</div></div>',
      '<div class="pip-quickstat"><div class="pip-quickstat-value">' + escHtml(redeStr) + '</div><div class="pip-quickstat-label">Rede Berater / Kunde</div></div>',
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

  // ── Public API ─────────────────────────────────────────────────────────────
  window.NerveLauncher = {
    open: open,
    close: close,
    isActive: function () { return state.micStarted; }
  };

})();
