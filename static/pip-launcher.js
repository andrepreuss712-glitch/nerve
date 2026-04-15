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
    pipBgOpacity: 1.0,
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
      '<div class="nav-live-title">Gespraechsmodus waehlen</div>',
      '<div class="nav-live-sub">Waehle den passenden Modus. Der Modus kann waehrend des Calls nicht gewechselt werden.</div>',
      '<div class="nav-live-cards">',
      '<div class="nav-live-card" id="lnr-card-cold">',
      '<div class="nav-live-card-icon">',
      '<svg width="40" height="40" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">',
      '<path d="M13 8C13 8 11 8 10 10C9 12 8 15 10 18C12 21 14 23 16 25C18 27 20 29 23 31C26 33 29 32 31 31C33 30 33 28 33 28L29 24C29 24 27 25 26 25C25 25 24 24 22 22C20 20 19 19 19 18C19 17 20 15 20 15L16 11C16 11 15 8 13 8Z" stroke="#00D4AA" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>',
      '</svg></div>',
      '<div class="nav-live-card-title">Cold Call</div>',
      '<div class="nav-live-card-desc">Nur deine Stimme wird analysiert.<br>Kein Kunden-Audio verarbeitet.<br>EWB-Buttons fuer manuelle Einwand-Trigger.</div>',
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
      '<div class="nav-live-card-desc">Volle Analyse beider Sprecher.<br>Einwilligung des Gespraechspartners erforderlich.<br>Automatische Einwanderkennung + EWB.</div>',
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
      // Show consent step inline before precall/skript
      renderConsentStep();
    };
  }

  // ── Meeting Consent (inline, replaces modal content temporarily) ───────────
  function renderConsentStep() {
    var c = content();
    if (!c) return;
    c.innerHTML = [
      '<div class="launcher-step">',
      '<div class="nav-consent-title">Einwilligung des Gespraechspartners</div>',
      '<div class="nav-consent-pflicht">Pflicht — laut vorlesen</div>',
      '<div class="nav-consent-script">',
      '&#8222;Ist es okay wenn eine KI mithoert damit wir die Qualitaet unseres Service verbessern koennen?&#8220;',
      '</div>',
      '<div class="nav-consent-tipp">Tipp: &#8222;Dabei werden keine vollen Aufzeichnungen gemacht, nur Stichpunkte.&#8220;</div>',
      '<div class="nav-consent-actions">',
      '<button class="nav-consent-btn nav-consent-reject" id="lnr-consent-reject">Abgelehnt</button>',
      '<button class="nav-consent-btn nav-consent-accept" id="lnr-consent-accept">Stattgegeben</button>',
      '</div>',
      '</div>'
    ].join('');

    document.getElementById('lnr-consent-reject').onclick = function () {
      // Fall back to cold call
      state.mode = 'cold_call';
      if (state.precallVerfuegbar) {
        state.step = 2;
      } else {
        state.step = 5;
      }
      renderStep();
    };
    document.getElementById('lnr-consent-accept').onclick = function () {
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
      'Wird empfohlen, damit die KI besser auf Einwaende eingehen kann. ',
      'Du gibst den Firmennamen ein und NERVE recherchiert Kontext automatisch.',
      '</div>',
      '<div class="launcher-actions" style="flex-direction:column;gap:10px">',
      '<button class="launcher-btn-primary" id="lnr-precall-yes" style="width:100%">Zur PreCall-Analyse</button>',
      '<button class="launcher-btn-ghost" id="lnr-precall-skip" style="width:100%">Ueberspringen und zur Opener/Skript-Auswahl</button>',
      '</div>',
      '<div class="launcher-actions" style="justify-content:flex-start">',
      '<button class="launcher-btn-ghost" id="lnr-step2-back">&#8592; Zurueck</button>',
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
      '<div style="font-size:13px;color:var(--page-text-muted);margin-bottom:8px">Recherche laeuft... (~30 Sekunden)</div>',
      '<div class="launcher-loading-bar"><div class="launcher-loading-bar-inner"></div></div>',
      '</div>',
      '<div id="lnr-precall-error" style="display:none;color:#f87171;font-size:13px"></div>',
      '<div class="launcher-actions">',
      '<button class="launcher-btn-ghost" id="lnr-step3-back">&#8592; Zurueck</button>',
      '<button class="launcher-btn-ghost" id="lnr-step3-skip">Ueberspringen</button>',
      '<button class="launcher-btn-primary" id="lnr-step3-run">Analyse durchfuehren</button>',
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
      if (!confirm('Sind Sie sicher, dass Sie die PreCall-Analyse ueberspringen moechten?')) return;
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
    if (runBtn) { runBtn.disabled = true; runBtn.textContent = 'Laeuft...'; }

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
        if (runBtn) { runBtn.disabled = false; runBtn.textContent = 'Analyse durchfuehren'; }
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
        if (runBtn) { runBtn.disabled = false; runBtn.textContent = 'Analyse durchfuehren'; }
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
        : '<div style="color:var(--page-text-muted);font-size:13px;padding:12px 0">Fuer diese Firma konnten keine oeffentlichen Informationen gefunden werden. Du kannst trotzdem fortfahren.</div>',
      '<div class="launcher-actions" style="flex-wrap:wrap;gap:8px">',
      '<button class="launcher-btn-ghost" id="lnr-step4-back">&#8592; Zurueck</button>',
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
      '<div class="nav-live-title">Skript & Opener waehlen</div>',

      // Profil
      state.profiles.length > 0
        ? '<label style="font-size:11px;color:var(--page-text-muted);margin-bottom:2px;display:block">Profil</label><select class="launcher-select" id="lnr-profile-select">' + profileOptions + '</select>'
        : '<div style="color:var(--page-text-muted);font-size:13px">Noch kein Profil angelegt. <a href="/profiles" style="color:#00D4AA">Profil erstellen</a></div>',

      // Skript
      state.skripte.length > 0
        ? '<label style="font-size:11px;color:var(--page-text-muted);margin-top:8px;margin-bottom:2px;display:block">Skript</label><select class="launcher-select" id="lnr-skript-select">' + skriptOptions + '</select>'
        : '',
      '<div class="launcher-opener-preview" id="lnr-skript-preview" style="white-space:pre-wrap;max-height:80px;overflow-y:auto' + (skriptPreview ? '' : ';color:var(--page-text-muted);font-style:italic') + '">' + (skriptPreview || (state.skripte.length > 0 ? 'Skript auswaehlen fuer Vorschau' : '')) + '</div>',
      '<textarea class="launcher-briefing" id="lnr-skript-textarea" style="display:none;margin-top:4px" rows="4"></textarea>',
      state.skripte.length > 0
        ? '<button type="button" id="lnr-skript-edit-btn" style="font-size:11px;color:#00D4AA;background:none;border:none;cursor:pointer;padding:2px 0;margin-top:2px">Bearbeiten</button>'
        : '',

      // Opener
      state.openerItems.length > 0
        ? '<label style="font-size:11px;color:var(--page-text-muted);margin-top:8px;margin-bottom:2px;display:block">Opener</label><select class="launcher-select" id="lnr-opener-select">' + openerOptions + '</select>'
        : '',
      '<div class="launcher-opener-preview" id="lnr-opener-preview" style="white-space:pre-wrap' + (openerPreview ? '' : ';color:var(--page-text-muted);font-style:italic') + '">'
        + (openerPreview || (state.openerItems.length > 0 ? 'Opener auswaehlen fuer Vorschau' : (legacyOpener ? escHtml(legacyOpener) : 'Kein Opener hinterlegt'))) + '</div>',
      '<textarea class="launcher-briefing" id="lnr-opener-textarea" style="display:none;margin-top:4px" rows="3"></textarea>',
      (state.openerItems.length > 0 || legacyOpener)
        ? '<button type="button" id="lnr-opener-edit-btn" style="font-size:11px;color:#00D4AA;background:none;border:none;cursor:pointer;padding:2px 0;margin-top:2px">Bearbeiten</button>'
        : '',

      '<div class="launcher-actions">',
      '<button class="launcher-btn-ghost" id="lnr-step5-back">&#8592; Zurueck</button>',
      '<button class="launcher-btn-ghost" id="lnr-step5-skip">Ueberspringen</button>',
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
          preview.textContent = sk ? sk.inhalt : 'Skript auswaehlen fuer Vorschau';
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
          preview.textContent = op ? op.inhalt : 'Opener auswaehlen fuer Vorschau';
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
        if (currentText && currentText !== 'Skript auswaehlen fuer Vorschau' && currentText !== 'Opener auswaehlen fuer Vorschau' && currentText !== 'Kein Opener hinterlegt') {
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
      + '<div style="font-size:15px;font-weight:700;margin-bottom:12px">' + label + ' auch im Profil aendern?</div>'
      + '<div style="font-size:13px;color:var(--page-text-muted);margin-bottom:16px">Die Aenderung gilt sonst nur fuer diesen Call.</div>'
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

  function _collectEditedTexts() {
    // If user edited inline, store the edited text for the session
    var skTa = document.getElementById('lnr-skript-textarea');
    if (skTa && skTa.style.display !== 'none') state._editedSkriptText = skTa.value;
    var opTa = document.getElementById('lnr-opener-textarea');
    if (opTa && opTa.style.display !== 'none') state._editedOpenerText = opTa.value;
  }

  // ── Start Call ─────────────────────────────────────────────────────────────
  // CRITICAL: called from click handler (user gesture for getUserMedia + PiP)
  function startCall(setProfile) {
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
    script.src = 'https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.min.js';
    script.onload = function () { cb(); };
    script.onerror = function () { console.error('[NerveLauncher] Socket.IO CDN load failed'); };
    document.head.appendChild(script);
  }

  // Called after Socket.IO is ready — still within the click handler call stack
  function _openPipAndMic() {
    // Connect socket
    state.socket = io({
      reconnectionAttempts: 3,
      reconnectionDelay: 2000,
      transports: ['polling']
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

    window.documentPictureInPicture.requestWindow({ width: 480, height: 760 })
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
      // D-16: AnalyserNode parallel zum Worklet — fuer Mic-Level-Bars, stoert Worklet-Streaming nicht
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
      var skriptBloecke = [];
      if (state._editedSkriptText) {
        skriptInhalt = state._editedSkriptText;
      } else if (state.selectedSkriptId && state.skripte.length > 0) {
        var sk = state.skripte.find(function (s) { return s.id === state.selectedSkriptId; });
        if (sk && sk.inhalt) skriptInhalt = sk.inhalt;
      }
      if (skriptInhalt) {
        skriptBloecke = skriptInhalt.split(/\n\n+/).filter(function (b) { return b.trim(); });
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
      if (openerFuerKi) skriptBloecke = [openerFuerKi].concat(skriptBloecke);

      state.socket.emit('start_live_session', {
        mode: state.mode || 'cold_call',
        precall_briefing: briefingText,
        skript_inhalt: skriptInhalt || null,
        skript_bloecke: skriptBloecke.length > 0 ? skriptBloecke : null
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

    // Body styles
    // 06.1-r2 BUG-6b: html+body transparent — damit der Slider via --pip-bg-alpha echte
    // Durchsicht auf CRM/Desktop ergibt. Der Farbton (slate-50) sitzt jetzt auf
    // .pip-live-split/.pip-header/.pip-ki-slot via rgba(...,var(--pip-bg-alpha,1)) und
    // wird kaskadiert transparent. D-16 gewahrt: Text/Icons/Buttons bleiben 100% opak.
    pipWindow.document.documentElement.style.background = 'transparent';
    var body = pipWindow.document.body;
    body.style.margin = '0';
    body.style.background = 'transparent';
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

    // Load Lucide in PiP
    var lucide = pipWindow.document.createElement('script');
    lucide.src = 'https://unpkg.com/lucide@latest';
    lucide.onload = function () {
      if (pipWindow.lucide) pipWindow.lucide.createIcons();
    };
    pipWindow.document.head.appendChild(lucide);

    // Wire PiP button events
    _wirePipButtons(pipWindow);

    // Initialize content
    _initPipLive();

    // Start timer
    _startTimer();

    // On PiP close: move content back
    pipWindow.addEventListener('pagehide', function () {
      var el = pipWindow.document.getElementById('pip-live-window');
      if (el) {
        el.style.display = 'none';
        document.body.appendChild(el);
      }
      state.pipWindow = null;
      if (state.micStarted) {
        _stopMic();
      }
    });
  }

  function _wirePipButtons(pipWindow) {
    // Beenden
    var beendenBtn = pipWindow.document.getElementById('nlp-btn-beenden');
    if (beendenBtn) beendenBtn.onclick = function () { endCall(); };

    // Next call (postcall)
    var nextBtn = pipWindow.document.getElementById('nlp-btn-next-call');
    if (nextBtn) nextBtn.onclick = function () { nextCall(); };

    // Details (postcall)
    var detailsBtn = pipWindow.document.getElementById('nlp-btn-details');
    if (detailsBtn) detailsBtn.onclick = function () { showDetails(); };

    // D-15: Mic-Mute-Toggle
    var micBtn = pipEl('pip-mic-indicator');
    if (micBtn) micBtn.onclick = function () { _toggleMicMute(); };
  }

  function _initPipLive() {
    // Set mode badge
    var badge = pipEl('nlp-mode-badge');
    if (badge) badge.textContent = state.mode === 'meeting' ? 'Meeting' : 'Cold Call';

    // D-05/D-07: Show consent screen for meeting mode, skip for cold_call
    if (state.mode === 'meeting' && !state.consentDone) {
      _showPipConsent();
    } else {
      _showPipLive();
    }

    // Render EWB buttons
    _renderEwbButtons();
  }

  function _showPipConsent() {
    var consentSection = pipEl('pip-section-consent');
    var liveSection = pipEl('pip-section-live');
    var beendenBtn = pipEl('nlp-btn-beenden');
    if (consentSection) consentSection.style.display = 'flex';
    if (liveSection) liveSection.style.display = 'none';
    if (beendenBtn) beendenBtn.style.display = 'none';

    // Hide opacity slider during consent
    var slider = pipEl('pip-opacity-slider');
    var sliderLabel = pipEl('pip-opacity-label');
    if (slider) slider.style.display = 'none';
    if (sliderLabel) sliderLabel.style.display = 'none';

    // D-06: Load consent text from profile (or use default)
    var consentText = (state.profileDaten && state.profileDaten.consent_text)
      ? state.profileDaten.consent_text
      : 'Herr/Frau [Name], kurzer Hinweis \u2014 ich mache mir w\u00e4hrend unseres Gespr\u00e4chs digitale Notizen. Ist das f\u00fcr Sie in Ordnung?';
    // Replace [Name] with kundendaten name if available
    if (state.precallFormData && state.precallFormData.person) {
      consentText = consentText.replace('[Name]', state.precallFormData.person);
    }
    var textEl = pipEl('pip-consent-text');
    if (textEl) textEl.textContent = consentText;

    // Wire consent buttons
    var acceptBtn = pipEl('pip-consent-accept');
    var rejectBtn = pipEl('pip-consent-reject');
    if (acceptBtn) {
      acceptBtn.onclick = function () {
        state.consentDone = true;
        // Stay in meeting mode
        _showPipLive();
      };
    }
    if (rejectBtn) {
      rejectBtn.onclick = function () {
        state.consentDone = true;
        state.mode = 'cold_call'; // D-05: fallback to cold_call
        // Update mode badge
        var b = pipEl('nlp-mode-badge');
        if (b) b.textContent = 'Cold Call';
        // Notify backend of mode change
        if (state.socket) state.socket.emit('update_mode', { mode: 'cold_call' });
        _showPipLive();
      };
    }
  }

  function _showPipLive() {
    var consentSection = pipEl('pip-section-consent');
    var liveSection = pipEl('pip-section-live');
    var beendenBtn = pipEl('nlp-btn-beenden');
    if (consentSection) consentSection.style.display = 'none';
    if (liveSection) liveSection.style.display = 'flex';
    if (beendenBtn) beendenBtn.style.display = 'block';

    // Show opacity slider (D-15: only visible in live state)
    var slider = pipEl('pip-opacity-slider');
    var sliderLabel = pipEl('pip-opacity-label');
    if (slider) slider.style.display = 'block';
    if (sliderLabel) sliderLabel.style.display = 'block';

    // D-13: Mic-Indikator einschalten (erst im Live-Zustand sichtbar)
    var micBtnShow = pipEl('pip-mic-indicator');
    if (micBtnShow) micBtnShow.style.display = 'inline-flex';

    // Initialize opacity from localStorage (D-17)
    _initOpacitySlider();

    // D-03: Opener wandert in den Teleprompter als Block 0 — Slot A bleibt leer fuer erste KI-Antwort
    // (keine Slot-0-Zuweisung mehr; beide Slots starten mit "Warte auf Gespraechsinhalt..." Default-Markup)

    // Initialize teleprompter (D-11, D-12)
    _initTeleprompter();
  }

  function _renderEwbButtons() {
    var row = pipEl('nlp-ewb-row');
    if (!row) return;
    var einwaende = (state.profileDaten && state.profileDaten.einwaende) ? state.profileDaten.einwaende : [];
    if (!einwaende.length) { row.innerHTML = ''; return; }
    var html = einwaende.slice(0, 5).map(function (e) {
      var typ = typeof e === 'string'
        ? e
        : (e.kategorie || e.typ || e.name || e.einwand || '');
      if (!typ) return '';  // skip rather than render [object Object]
      return '<button type="button" class="pip-ewb-btn" data-typ="' + escHtml(typ) + '">' + escHtml(typ) + '</button>';
    }).join('');
    row.innerHTML = html;
    // 06.1-r2 BUG-5b: addEventListener + stopPropagation + Capture — robuster im PiP-Document
    // als direct onclick-Assignment, und erlaubt mehrfache Handler ohne Override.
    row.querySelectorAll('.pip-ewb-btn').forEach(function (btn) {
      btn.addEventListener('click', function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        var typ = btn.getAttribute('data-typ');
        console.log('[NerveLauncher] EWB click:', typ);
        _triggerEwb(typ, btn);
      });
    });
  }

  function _triggerEwb(typ, btn) {
    // EWB triggers analysis — result arrives via pip_stream_start/pip_token/pip_token_done
    // 06.1-r2 BUG-5b: credentials:'include' damit Session-Cookie im PiP-Document-Kontext
    // mitgesendet wird. response.ok/Status pruefen und bei Fehler sichtbar machen.
    console.log('[NerveLauncher] EWB trigger:', typ);
    if (btn) btn.classList.add('pip-ewb-ai-selected');  // sofortiges visuelles Feedback
    fetch('/api/analyse_line', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: typ, line_id: 'ewb_pip_' + Date.now() })
    }).then(function (res) {
      console.log('[NerveLauncher] EWB fetch status:', res.status);
      if (!res.ok) {
        console.error('[NerveLauncher] EWB fetch failed:', res.status, res.statusText);
      }
    }).catch(function (err) {
      console.error('[NerveLauncher] EWB fetch error:', err);
    });
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
      // 06.1-r2 BUG-4: Claude streamt rohes JSON — niemals rohe Tokens rendern.
      // Placeholder "Analysiere…" bis pip_token_done die parsed result liefert.
      var body = pipEl('pip-slot-body-' + slot);
      if (body && body.textContent !== 'Analysiere\u2026') body.textContent = 'Analysiere\u2026';
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
      if (body) { body.textContent = 'KI-Fehler \u2014 bitte erneut versuchen'; body.classList.remove('pip-streaming'); }
      if (container) container.classList.remove('pip-slot-streaming');
    });

    // Coaching via streaming now (not separate event) — but keep listener for backward compat
    state.socket.on('coaching', function (d) {
      if (!d) return;
      var tipp = d.tipp || d.text || '';
      if (tipp && !state.pipSlots[1].streaming) {
        _showProactiveTipp(1, tipp);
      }
    });

    state.socket.on('disconnect', function () {
      console.log('[NerveLauncher] Socket disconnected');
    });

    state.socket.on('dg_error', function (d) {
      console.error('[NerveLauncher] Deepgram error:', d);
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
    // Unwrap {poin:{...}} / {point:{...}} — Haiku nutzt diese Schluessel in Round-2 Tests
    var inner = r.poin || r.point || null;
    var isEinwand = !!(r.einwand || (inner && inner.einwand));
    var typ = r.typ || (inner && inner.typ) || '';
    var argument = r.gegenargument_1 || r.gegenargument || (inner && (inner.gegenargument_1 || inner.gegenargument)) || '';
    var text = r.text || (inner && inner.text) || '';

    // Wenn kein nutzbares Feld vorliegt: faellt der Slot in den "Warte..."-Default statt JSON anzuzeigen
    if (!argument && !text && !isEinwand) {
      body.textContent = 'Warte auf Gespr\u00e4chsinhalt\u2026';
      return;
    }

    body.innerHTML = '';
    var doc = body.ownerDocument || document;

    if (isEinwand && (argument || text)) {
      // Einwand-Render: Typ-Badge + Gegenargument/Text
      if (label) label.textContent = (typ || 'EINWAND').toUpperCase();
      var badge = doc.createElement('span');
      badge.className = 'pip-slot-typ-badge';
      badge.textContent = typ || 'Einwand';
      badge.style.cssText = _getTypBadgeStyle(typ);
      body.appendChild(badge);
      var textNode = doc.createElement('div');
      textNode.style.cssText = 'margin-top:6px;font-size:14px;line-height:1.5;color:#1a1a1a';
      textNode.textContent = argument || text;
      body.appendChild(textNode);
      _highlightEwbButton(typ);
    } else {
      // Kein Einwand: nur Text/Gegenargument, Label zurueck auf Antwort-Slot
      if (label && (label.textContent === '' || /^\s*$/.test(label.textContent))) {
        label.textContent = slot === 0 ? 'ANTWORT A' : 'ANTWORT B';
      }
      body.textContent = argument || text;
    }
  }

  function _getTypBadgeStyle(typ) {
    var colors = {
      'Preis': 'background:rgba(212,168,83,0.15);color:#d4a853',
      'Kein Bedarf': 'background:rgba(248,113,113,0.15);color:#f87171',
      'Vertrauen': 'background:rgba(96,165,250,0.15);color:#60a5fa',
      'Konkurrenz': 'background:rgba(168,85,247,0.15);color:#a855f7',
      'Timing': 'background:rgba(251,191,36,0.15);color:#fbbf24'
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

    // D-03: Opener als erster Teleprompter-Block (Phase 0 = Opener fuer KI-Position-Erkennung)
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

  // D-17: iOS-style Slider Fill — setzt --pip-slider-pct auf dem input-Element
  function _updateSliderFill(slider) {
    if (!slider) return;
    var min = parseFloat(slider.min) || 0;
    var max = parseFloat(slider.max) || 100;
    var val = parseFloat(slider.value);
    if (!isFinite(val)) val = max;
    var pct = ((val - min) / (max - min)) * 100;
    pct = Math.min(100, Math.max(0, pct));
    slider.style.setProperty('--pip-slider-pct', pct + '%');
  }

  function _initOpacitySlider() {
    var slider = pipEl('pip-opacity-slider');
    if (!slider) return;
    // D-17 JS: Clamp gespeicherten Wert auf [10, 100] (T-06.1-03 Mitigation gegen getampertes localStorage)
    var stored = null;
    try { stored = localStorage.getItem('nerve_pip_opacity'); } catch (e) {}
    var parsed = parseInt(stored, 10);
    if (!isFinite(parsed)) parsed = 100;
    parsed = Math.min(100, Math.max(10, parsed));
    slider.value = String(parsed);
    _setPipBgOpacity(parsed / 100);
    _updateSliderFill(slider);  // D-17: initial fill-pct setzen

    // D-16: input event for live feedback
    var debounceTimer = null;
    slider.addEventListener('input', function () {
      var v = parseInt(slider.value, 10);
      if (!isFinite(v)) v = 100;
      v = Math.min(100, Math.max(10, v));
      state.pipBgOpacity = v / 100;
      _setPipBgOpacity(v / 100);
      _updateSliderFill(slider);  // D-17: fill-pct bei jedem Move updaten
      // Debounce localStorage write (200ms)
      if (debounceTimer) clearTimeout(debounceTimer);
      debounceTimer = setTimeout(function () {
        try { localStorage.setItem('nerve_pip_opacity', String(v)); } catch (e) {}
      }, 200);
    });
  }

  function _setPipBgOpacity(value) {
    // D-16 + 06.1-r2 BUG-6: Alpha auf pip-live-window (umfasst Header + Live-Split) setzen,
    // damit --pip-bg-alpha auch an .pip-header, .pip-ki-slot, .pip-ewb-btn vererbt wird.
    // Text/Buttons/Icons bleiben 100% (CSS nutzt Alpha nur auf background-color).
    var wrapEl = pipEl('pip-live-window');
    if (wrapEl) {
      wrapEl.style.setProperty('--pip-bg-alpha', String(value));
    }
  }

  // ── Timer ──────────────────────────────────────────────────────────────────
  function _startTimer() {
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
    console.log('[NerveLauncher] Mic stopped');
  }

  // ── End Call ───────────────────────────────────────────────────────────────
  function endCall() {
    _stopTimer();
    _stopMic();

    fetch('/api/beenden', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_mode: state.mode || 'cold_call',
        precall_briefing: state.precallBriefing
      })
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (!data.ok) { console.error('[NerveLauncher] Beenden error:', data.error); return; }
        state.lastConvId = data.conv_id || null;
        if (data.postcall) {
          _showPostcall(data.postcall);
        } else {
          _showPostcallRaw('--', []);
        }
      })
      .catch(function (err) {
        console.error('[NerveLauncher] Beenden fetch error:', err);
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
    if (behandeltRate >= 0.8 && einwTotal > 0) tags.push({ text: 'Einwaende gemeistert', color: 'teal' });
    if (redeanteil > 65) tags.push({ text: 'Redeanteil zu hoch', color: 'yellow' });
    if (redeanteil > 0 && redeanteil < 25) tags.push({ text: 'Zu wenig gesprochen', color: 'yellow' });
    if (dauer > 0 && dauer < 120) tags.push({ text: 'Sehr kurzer Call', color: 'yellow' });
    if (behandeltRate >= 0 && behandeltRate < 0.4 && einwTotal > 0) tags.push({ text: 'Einwaende offen', color: 'red' });
    var pos = tags.filter(function (t) { return t.color === 'teal'; });
    var neg = tags.filter(function (t) { return t.color !== 'teal'; });
    var result = pos.slice(0, 2);
    if (result.length < 3 && neg.length > 0) result.push(neg[0]);
    return result.slice(0, 3);
  }

  function _showPostcall(postcall) {
    var score = _calcScore(postcall);
    var tags = _buildTags(postcall);
    _showPostcallRaw(score + '%', tags);
  }

  function _showPostcallRaw(scoreText, tags) {
    var postcallSection = pipEl('nlp-section-postcall');
    if (postcallSection) postcallSection.style.display = 'flex';
    // Hide live controls
    ['nlp-btn-beenden', 'nlp-ewb-row', 'pip-section-live', 'pip-section-consent'].forEach(function (id) {
      var el = pipEl(id);
      if (el) el.style.display = 'none';
    });
    var pipHeader = pipEl('pip-header');
    if (pipHeader) pipHeader.style.display = 'none';

    var scoreEl = pipEl('nlp-postcall-score');
    if (scoreEl) scoreEl.textContent = scoreText;

    var tagsEl = pipEl('nlp-postcall-tags');
    if (tagsEl) {
      tagsEl.innerHTML = tags.map(function (t) {
        return '<span class="pip-tag pip-tag-' + t.color + '">' + escHtml(t.text) + '</span>';
      }).join('');
    }
  }

  // ── PostCall Actions ───────────────────────────────────────────────────────
  function nextCall() {
    if (state.pipWindow && !state.pipWindow.closed) state.pipWindow.close();
    _cleanup();
    open();
  }

  function showDetails() {
    if (state.pipWindow && !state.pipWindow.closed) state.pipWindow.close();
    _cleanup();
    if (state.lastConvId) {
      window.location.href = '/logs/' + state.lastConvId;
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
    state.pipBgOpacity = 1.0;
  }

  // ── Public API ─────────────────────────────────────────────────────────────
  window.NerveLauncher = {
    open: open,
    close: close,
    isActive: function () { return state.micStarted; }
  };

})();
