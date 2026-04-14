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
    socket: null,
    micStream: null,
    audioCtx: null,
    workletNode: null,
    micStarted: false,
    pipWindow: null,
    timerInterval: null,
    sessionSeconds: 0,
    lastConvId: null,
    pipTabLocked: null
  };

  // ── Helpers ────────────────────────────────────────────────────────────────
  function escHtml(str) {
    return String(str || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
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
      '<input type="text" class="launcher-form-input" id="lnr-person" placeholder="Ansprechpartner (optional)" maxlength="200" value="' + escHtml(saved.person || '') + '">',
      '<input type="text" class="launcher-form-input" id="lnr-branche" placeholder="Branche / Kontext (optional)" maxlength="200" value="' + escHtml(saved.branche || '') + '">',
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

    var person = (document.getElementById('lnr-person') || {}).value || '';
    var branche = (document.getElementById('lnr-branche') || {}).value || '';

    fetch('/api/precall/research', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ firmenname: firma.trim(), ansprechpartner: person.trim() || null, branche: branche.trim() || null })
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (loading) loading.style.display = 'none';
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
        if (errEl2) { errEl2.textContent = 'Verbindungsfehler: ' + err.message; errEl2.style.display = 'block'; }
      });
  }

  // ── Step 4: PreCall Result ─────────────────────────────────────────────────
  function renderStep4() {
    var c = content();
    if (!c) return;
    var briefing = state.precallBriefing || '';
    var found = !!briefing;

    c.innerHTML = [
      '<div class="launcher-step">',
      '<div class="nav-live-title">' + (found ? 'Recherche-Ergebnis' : 'Keine Daten gefunden') + '</div>',
      found
        ? '<textarea class="launcher-briefing" id="lnr-briefing-edit" readonly>' + escHtml(briefing) + '</textarea>'
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
      // Save edited briefing if textarea was made editable
      var ta = document.getElementById('lnr-briefing-edit');
      if (ta) state.precallBriefing = ta.value || state.precallBriefing;
      state.step = 5;
      renderStep();
    };

    var editBtn = document.getElementById('lnr-step4-edit');
    if (editBtn) {
      editBtn.onclick = function () {
        var ta = document.getElementById('lnr-briefing-edit');
        if (ta) {
          ta.removeAttribute('readonly');
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

    var opener = (state.profileDaten && state.profileDaten.opener) ? state.profileDaten.opener : '';

    c.innerHTML = [
      '<div class="launcher-step">',
      '<div class="nav-live-title">Skript & Opener waehlen</div>',
      state.profiles.length > 0
        ? '<select class="launcher-select" id="lnr-profile-select">' + profileOptions + '</select>'
        : '<div style="color:var(--page-text-muted);font-size:13px">Noch kein Profil angelegt. <a href="/profiles" style="color:#00D4AA">Profil erstellen</a></div>',
      opener
        ? '<div style="font-size:12px;color:var(--page-text-muted);margin-bottom:4px">Opener-Vorschau:</div><div class="launcher-opener-preview" id="lnr-opener-preview">' + escHtml(opener) + '</div>'
        : '<div class="launcher-opener-preview" id="lnr-opener-preview" style="color:var(--page-text-muted);font-style:italic">Kein Opener im Profil hinterlegt</div>',
      '<div class="launcher-actions">',
      state.precallVerfuegbar
        ? '<button class="launcher-btn-ghost" id="lnr-step5-back">&#8592; Zurueck</button>'
        : '<button class="launcher-btn-ghost" id="lnr-step5-back">&#8592; Zurueck</button>',
      '<button class="launcher-btn-ghost" id="lnr-step5-skip">Ueberspringen</button>',
      '<button class="launcher-btn-primary" id="lnr-step5-start">Call starten &#9654;</button>',
      '</div>',
      '</div>'
    ].join('');

    // Profile change: fetch opener data
    var sel = document.getElementById('lnr-profile-select');
    if (sel) {
      sel.onchange = function () {
        var pid = parseInt(sel.value);
        if (!pid) return;
        fetch('/api/launcher/profile/' + pid)
          .then(function (r) { return r.json(); })
          .then(function (data) {
            state.activeProfileId = data.id;
            state.profileDaten = data.daten || {};
            var preview = document.getElementById('lnr-opener-preview');
            if (preview) {
              var op = (data.daten && data.daten.opener) ? data.daten.opener : '';
              preview.textContent = op || 'Kein Opener im Profil hinterlegt';
              preview.style.fontStyle = op ? 'normal' : 'italic';
              preview.style.color = op ? '' : 'var(--page-text-muted)';
            }
          })
          .catch(function () {});
      };
    }

    document.getElementById('lnr-step5-back').onclick = function () {
      if (state.precallVerfuegbar) {
        state.step = 2;
      } else {
        state.step = 1;
      }
      renderStep();
    };
    document.getElementById('lnr-step5-skip').onclick = function () {
      startCall(false);
    };
    document.getElementById('lnr-step5-start').onclick = function () {
      // Update profile selection before starting
      var s = document.getElementById('lnr-profile-select');
      if (s && s.value) state.activeProfileId = parseInt(s.value);
      startCall(true);
    };
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

    window.documentPictureInPicture.requestWindow({ width: 380, height: 440 })
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
        // Start polling for AI results (like app.js does)
        _startPolling();
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
      state.audioCtx = audioCtx;
      state.workletNode = workletNode;
      state.micStarted = true;
      state.socket.emit('start_live_session', { mode: state.mode || 'cold_call' });
      console.log('[NerveLauncher] Mic started, mode:', state.mode);
    } catch (err) {
      console.error('[NerveLauncher] Audio worklet error:', err);
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
    var body = pipWindow.document.body;
    body.style.margin = '0';
    body.style.background = 'rgba(6,6,10,0.85)';
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
    // Tab buttons
    ['opener', 'einwand', 'coaching', 'ewb'].forEach(function (tab) {
      var btn = pipWindow.document.getElementById('nlp-tab-' + tab);
      if (btn) {
        btn.onclick = function () { _switchPipTab(tab); };
      }
    });

    // Beenden
    var beendenBtn = pipWindow.document.getElementById('nlp-btn-beenden');
    if (beendenBtn) beendenBtn.onclick = function () { endCall(); };

    // Next call
    var nextBtn = pipWindow.document.getElementById('nlp-btn-next-call');
    if (nextBtn) nextBtn.onclick = function () { nextCall(); };

    // Details
    var detailsBtn = pipWindow.document.getElementById('nlp-btn-details');
    if (detailsBtn) detailsBtn.onclick = function () { showDetails(); };
  }

  function _initPipLive() {
    // Set mode badge
    var badge = pipEl('nlp-mode-badge');
    if (badge) badge.textContent = state.mode === 'meeting' ? 'Meeting' : 'Cold Call';

    // Set opener text
    var openerText = (state.profileDaten && state.profileDaten.opener) ? state.profileDaten.opener : 'Kein Opener im Profil hinterlegt';
    var openerEl = pipEl('nlp-opener-text');
    if (openerEl) openerEl.textContent = openerText;

    // Render EWB buttons
    _renderEwbButtons();
  }

  function _renderEwbButtons() {
    var row = pipEl('nlp-ewb-row');
    if (!row) return;
    var einwaende = (state.profileDaten && state.profileDaten.einwaende) ? state.profileDaten.einwaende : [];
    if (!einwaende.length) { row.innerHTML = ''; return; }
    var html = einwaende.slice(0, 5).map(function (e) {
      var typ = typeof e === 'string' ? e : (e.typ || e.name || String(e));
      return '<button class="pip-ewb-btn" data-typ="' + escHtml(typ) + '">' + escHtml(typ) + '</button>';
    }).join('');
    row.innerHTML = html;
    // Wire clicks
    row.querySelectorAll('.pip-ewb-btn').forEach(function (btn) {
      btn.onclick = function () { _triggerEwb(btn.getAttribute('data-typ')); };
    });
  }

  function _triggerEwb(typ) {
    // EWB uses POST /api/analyse_line (same as app.js triggerEwb)
    fetch('/api/analyse_line', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: typ, line_id: 'ewb_pip_' + Date.now() })
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.ergebnis && data.ergebnis.gegenargument_1) {
          var el = pipEl('nlp-einwand-text');
          if (el) el.textContent = data.ergebnis.gegenargument_1;
          if (!state.pipTabLocked) _switchPipTab('einwand');
        }
      })
      .catch(function (err) { console.error('[NerveLauncher] EWB error:', err); });
    console.log('[NerveLauncher] EWB trigger:', typ);
  }

  // ── Socket Events (transcript + coaching come via socket) ─────────────────
  function _registerSocketEvents() {
    if (!state.socket) return;

    state.socket.on('transcript', function (d) {
      if (d && d.type === 'final' && d.text) {
        // Store for context
        state.lastTranscript = d.text;
      }
    });

    state.socket.on('coaching', function (d) {
      if (!d) return;
      var tipp = d.tipp || d.text || '';
      if (tipp) {
        var coachEl = pipEl('nlp-coaching-text');
        if (coachEl) coachEl.textContent = tipp;
        if (!state.pipTabLocked) _switchPipTab('coaching');
      }
    });

    state.socket.on('disconnect', function () {
      console.log('[NerveLauncher] Socket disconnected');
    });

    state.socket.on('dg_error', function (d) {
      console.error('[NerveLauncher] Deepgram error:', d);
    });
  }

  // ── Polling for AI results (same pattern as app.js pollErgebnis) ──────────
  var _pollVersion = 0;
  state.pollingActive = false;

  function _startPolling() {
    state.pollingActive = true;
    _pollVersion = 0;
    _pollLoop();
  }

  function _stopPolling() {
    state.pollingActive = false;
  }

  function _pollLoop() {
    if (!state.pollingActive) return;
    fetch('/api/ergebnis')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.version > _pollVersion && data.ergebnis !== null) {
          _pollVersion = data.version;
          _handleErgebnis(data.ergebnis);
        }
        if (state.pollingActive) setTimeout(_pollLoop, 500);
      })
      .catch(function () {
        if (state.pollingActive) setTimeout(_pollLoop, 2000);
      });
  }

  function _handleErgebnis(e) {
    if (!e) return;
    // Einwand detected — show gegenargument
    if (e.einwand && (e.gegenargument_1 || e.gegenargument)) {
      var el = pipEl('nlp-einwand-text');
      if (el) el.textContent = e.gegenargument_1 || e.gegenargument || '';
      if (!state.pipTabLocked) _switchPipTab('einwand');
    }
    // Update KB score bar if available
    if (typeof e.kb !== 'undefined') {
      var scoreEl = pipEl('nlp-kb-score');
      if (scoreEl) scoreEl.textContent = e.kb + '%';
      var barEl = pipEl('nlp-kb-bar-inner');
      if (barEl) barEl.style.width = e.kb + '%';
    }
    // Update phase if available
    if (e.phase) {
      var phaseEl = pipEl('nlp-phase-text');
      if (phaseEl) phaseEl.textContent = e.phase;
    }
  }

  // ── Tab Management ─────────────────────────────────────────────────────────
  function _switchPipTab(tabName) {
    var tabs = ['opener', 'einwand', 'coaching', 'ewb'];
    tabs.forEach(function (t) {
      var btn = pipEl('nlp-tab-' + t);
      var panel = pipEl('nlp-panel-' + t);
      if (btn) btn.classList.toggle('pip-tab-active', t === tabName);
      if (panel) panel.style.display = t === tabName ? 'block' : 'none';
    });
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

    // Short/empty session guard
    if (state.sessionSeconds < 5) {
      _showPostcallRaw('--', [{ text: 'Kein Gespraech erkannt', color: 'yellow' }]);
      return;
    }

    _stopPolling();
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
    // Hide live elements, show postcall
    var liveWin = pipEl('pip-live-window');
    if (liveWin) {
      // Hide live-specific children, show postcall section
      var postcallSection = pipEl('nlp-section-postcall');
      if (postcallSection) {
        postcallSection.style.display = 'flex';
      }
      // Hide live controls
      ['nlp-btn-beenden', 'nlp-ewb-row'].forEach(function (id) {
        var el = pipEl(id);
        if (el) el.style.display = 'none';
      });
      var pipHeader = liveWin.querySelector ? liveWin.querySelector('.pip-header') : null;
      if (pipHeader) pipHeader.style.display = 'none';
      var pipTabs = liveWin.querySelector ? liveWin.querySelector('.pip-tabs') : null;
      if (pipTabs) pipTabs.style.display = 'none';
      var pipContent = liveWin.querySelector ? liveWin.querySelector('.pip-content') : null;
      if (pipContent) pipContent.style.display = 'none';
    }

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
    _stopPolling();
    if (state.micStarted) _stopMic();
    if (state.socket) { state.socket.disconnect(); state.socket = null; }
    state.micStarted = false;
    state.pipWindow = null;
    state.sessionSeconds = 0;
    state.pipTabLocked = null;
    state.lastConvId = null;
  }

  // ── Public API ─────────────────────────────────────────────────────────────
  window.NerveLauncher = {
    open: open,
    close: close,
    isActive: function () { return state.micStarted; }
  };

})();
