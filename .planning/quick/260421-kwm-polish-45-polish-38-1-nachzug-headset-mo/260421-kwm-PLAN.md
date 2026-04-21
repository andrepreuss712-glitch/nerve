---
phase: quick-260421-kwm
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - templates/base.html
  - services/deepgram_service.py
autonomous: true
requirements: [POLISH-45, POLISH-38.1]
must_haves:
  truths:
    - "Nach Logout und Re-Login sieht der User das Headset-Confirm-Modal erneut beim ersten Cold-Call-Klick (DSGVO per-Session-Bestaetigung)"
    - "Ein manual_ewb Socket.IO-Event schreibt ObjectionEvent mit success=True wenn der Claude-Haiku-Stream erfolgreich gestartet wurde; success=False wenn der Stream-Start scheitert"
  artifacts:
    - path: "templates/base.html"
      provides: "Inline-Script im public-Block (kein g.user) das sessionStorage.removeItem('headsetConfirmed') beim Rendern jeder public-Page ausfuehrt"
      contains: "sessionStorage.removeItem"
    - path: "services/deepgram_service.py"
      provides: "handle_manual_ewb setzt success=True nach erfolgreichem start_background_task, success=False bei Exception im _run-Pfad"
      contains: "record_ewb_click"
  key_links:
    - from: "templates/base.html (public-Zweig, ohne g.user)"
      to: "sessionStorage.headsetConfirmed"
      via: "Inline <script> das bei jeder Page ohne User-Session gelesen wird"
      pattern: "sessionStorage\\.removeItem\\('headsetConfirmed'\\)"
    - from: "services/deepgram_service.py handle_manual_ewb"
      to: "ObjectionEvent.success (via record_ewb_click)"
      via: "success=True im Erfolgsfall, success=False im Fehlerfall"
      pattern: "record_ewb_click\\(.*success=True"
---

<objective>
Zwei kleine Bug-Fix-Nachzuege aus Phase 07.4 Debug-Cluster. Beide sind eigenstaendige 15-Min-Fixes, die atomic-committed und gepusht werden.

1. **POLISH-45 — Headset-Modal-Reset bei Logout.**
   Aktuell persistiert der `sessionStorage.headsetConfirmed`-State ueber einen Logout/Re-Login-Zyklus im selben Browser-Tab hinweg. Ein User kann sich ausloggen, wieder einloggen, und umgeht dann das DSGVO-relevante Consent-Modal beim naechsten Cold-Call.
   Fix: Inline-`<script>`-Block im public-Zweig von `templates/base.html` (also dort wo `g.user` None ist, also bei allen logged-out-Renderings — z.B. `/?modal=login` nach `/logout`-Redirect) der `sessionStorage.removeItem('headsetConfirmed')` ausfuehrt. Damit wird die Consent-Bestaetigung garantiert pro Login-Session neu gefordert.

2. **POLISH-38.1 — `manual_ewb` success-Flag.**
   Der `@sio.on('manual_ewb')`-Handler in `services/deepgram_service.py` (User klickt PiP-EWB-Button → `manual_ewb`-Socket-Event, OHNE Claude-Auto-Detection) ruft aktuell `record_ewb_click(typ, success=False)` hardcoded — d.h. alle manuell getriggerten Einwaende werden als "nicht gemeistert" persistiert. User-Definition (POLISH-29): "EWB-Button gedrueckt = Einwand behandelt". Fix: success=True setzen im Normalfall (Gegenargument-Stream wird erfolgreich gestartet), success=False nur wenn der Stream-Start scheitert (Exception beim Spawn des background task).

Purpose: DSGVO-Compliance sicherstellen (POLISH-45) + Metrik-Praezision fuer "Einwaende behandelt" (POLISH-38.1) korrigieren.
Output: 2 atomic commits auf main, danach `git push origin main`.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@CLAUDE.md
@.planning/STATE.md
@.planning/backlog.md

<interfaces>
<!-- Relevante bestehende Interfaces. Executor braucht keine Codebase-Erkundung. -->

From services/live_session.py (Helper der schon existiert):
```python
def record_ewb_click(einwand_typ: str, success: bool = False):
    """Erfasst einen EWB-Button-Klick im Session-State (thread-safe)."""
    import datetime as _dt
    with state_lock:
        state.setdefault('ewb_clicks', []).append({
            'einwand_typ': einwand_typ,
            'success':     bool(success),
            'ts':          _dt.datetime.utcnow().isoformat(),
        })
```

From database/models.py (ObjectionEvent — success-Spalte ist NOT NULL default False):
```python
class ObjectionEvent(Base):
    __tablename__ = 'objection_events'
    id                  = Column(Integer, primary_key=True)
    user_id             = Column(Integer, ForeignKey('users.id'), nullable=False)
    org_id              = Column(Integer, ForeignKey('organisations.id'), nullable=True)
    conversation_log_id = Column(Integer, ForeignKey('conversation_logs.id'), nullable=False)
    einwand_typ         = Column(String(100), nullable=False)
    success             = Column(Boolean, default=False, nullable=False)  # nicht nullable!
    created_at          = Column(DateTime, default=utcnow, nullable=False)
```

From services/deepgram_service.py:400-448 (manual_ewb-Handler — aktueller Zustand):
```python
@sio.on('manual_ewb')
def handle_manual_ewb(data=None, sid=None):
    from flask import request
    _sid = request.sid if sid is None else sid
    if not isinstance(data, dict):
        return
    typ = (data.get('text') or '').strip()
    if not typ:
        return
    print(f"[PiP] manual_ewb (sid={_sid}): {typ[:80]}")
    import services.live_session as ls
    try:
        ls.record_ewb_click(typ, success=False)   # <— HARDCODED False
    except Exception as e:
        print(f"[PiP] record_ewb_click error (sid={_sid}): {e}")

    # ... Profil + Kontext-Aufbereitung ...

    def _run():
        try:
            streame_manual_ewb_variante(typ, profile_einwand or {}, kontext, _sid, slot=1)
        except Exception as ex:
            print(f"[PiP] manual_ewb variante error (sid={_sid}): {ex}")
            try:
                sio.emit('pip_stream_error', {'slot': 1, 'error': str(ex)}, room=_sid)
            except Exception:
                pass

    sio.start_background_task(_run)
```

From routes/auth.py:232-251 (Logout-Flow — server-side session clear):
```python
@auth_bp.route('/logout')
def logout():
    auto = request.args.get('auto')
    # Audit vor session.clear()
    if 'user_id' in session:
        try:
            _uid = session.get('user_id')
            _oid = session.get('org_id')
            _db = get_session()
            try:
                log_action(_db, _uid, _oid, 'logout',
                           target_type='user', target_id=_uid, request=request)
            finally:
                _db.close()
        except Exception:
            pass
    session.clear()                         # ← Flask-Cookie-Session weg
    if auto:
        flash('Du wurdest automatisch ausgeloggt.', 'info')
    return redirect(url_for('auth.login'))  # ← → /login → redirect auf /?modal=login
```

Flask-Session ist danach leer, aber **sessionStorage.headsetConfirmed im Browser-Tab ueberlebt**.

From templates/base.html:83+135 (bestehende partial-Loesung):
```html
{% if g.user %}   <!-- Sidebar nur wenn eingeloggt -->
  ...
  <a href="/logout" class="popup-item popup-item-logout"
     onclick="try{sessionStorage.removeItem('headsetConfirmed')}catch(e){}">Abmelden</a>
  ...
{% endif %}
```

Diese onclick-Loesung feuert NUR beim Klick auf genau diesen Dropdown-Link. Sie feuert NICHT bei:
- `/logout?auto=1` (Session-Timeout-Redirect)
- Direkt-URL-Navigation zu `/logout`
- `session.clear()` serverseitig durch anderen Flow (401-Redirect, forced logout)
- Anderen Browser-Tabs

Deshalb: zusaetzlich ein `{% if not g.user %}`-Block mit Inline-Script, der auf ALLEN logged-out-Pages einmal laeuft und sessionStorage.headsetConfirmed cleared.

From static/pip-launcher.js:814 (Headset-Gate — lesendes Pendant):
```javascript
if (state.mode === 'cold_call' && !sessionStorage.getItem('headsetConfirmed')) {
  _showHeadsetModal(function () {
    startCall(setProfile);
  });
  return;
}
```

Gate triggered Modal, wenn Key fehlt. Nach Clear ist Key weg → Modal erscheint wieder.
</interfaces>

<key_backlog_excerpts>
**POLISH-45** (backlog.md Line 140-149):
> Headset-Modal (Phase 06.4 DSGVO-Hardening) persistiert User-Wahl ueber Session-Grenze hinweg. [...] LocalStorage-Key oder Session-Cookie behaelt Headset-Confirm-State und wird bei neuem `/live`-Aufruf nicht zurueckgesetzt. Sollte pro Session (nicht pro Browser-Installation) neu bestaetigt werden.

**POLISH-38.1** (backlog.md Line 152-161):
> `manual_ewb`-Events (User-Klick ohne Claude-Auto-Detection) haben aktuell kein `success`-Flag [...] Post-Call-Scoring-Heuristik kann daher nur "versucht behandelt" tracken, nicht "erfolgreich".

**POLISH-29 User-Definition** (backlog.md Line 104-113):
> **"EWB-Button gedrueckt = Einwand behandelt."** Das ist die verbindliche Standard-Definition fuer alle Metriken, UI-Labels und Post-Call-Analysen.
</key_backlog_excerpts>
</context>

<tasks>

<task type="auto">
  <name>Task 1 (POLISH-45): Headset-Confirm-State bei jedem logged-out-Page-Render cleanen</name>
  <files>templates/base.html</files>
  <action>
Fuege in `templates/base.html` einen neuen `{% if not g.user %}`-Block mit einem kleinen Inline-`<script>`-Tag ein, der `sessionStorage.removeItem('headsetConfirmed')` ausfuehrt. Der Block soll genau dann laufen, wenn **keine Flask-Session aktiv ist** (also nach erfolgreichem Logout — ob manuell, auto, oder direkt-URL — weil `session.clear()` bewirkt, dass `g.user` None ist).

**Platzierung:** Direkt nach der bestehenden `{% if g.user %}...{% endif %}`-Sidebar (die Zeile `{% endif %}` um Zeile ~139). Der neue Block soll im `<head>` oder am Anfang des `<body>` stehen, damit er fruehzeitig feuert — aber da `base.html` Sidebar im Body hat und der File vom `{% block content %}`-Pattern lebt, ist die sauberste Stelle **VOR dem schliessenden `</body>`-Tag** am Ende von `base.html` (oder direkt nach dem `{% endif %}` der Sidebar, damit die Logik zusammen mit dem bestehenden Logout-Link-onclick sitzt).

Wenn du dich unsicher bist wo `</body>` ist, fuege den Block direkt **nach** Zeile 139 ein (nach dem `</nav>`-Tag bzw. dem `{% endif %}` der Sidebar).

**Exakt einzufuegender Code:**

```html
{% if not g.user %}
<script>
  // POLISH-45: Headset-Confirm-State pro Login-Session neu anfordern (DSGVO).
  // Feuert auf allen logged-out-Pages — deckt ALLE Logout-Pfade ab
  // (manuell, /logout?auto=1, Session-Timeout, direkt-URL-Nav).
  try { sessionStorage.removeItem('headsetConfirmed'); } catch (e) {}
</script>
{% endif %}
```

**Nicht vergessen:**
- Der bestehende `onclick="try{sessionStorage.removeItem('headsetConfirmed')}catch(e){}"`-Handler auf dem Abmelden-Link in Zeile 135 bleibt unveraendert (belt-and-suspenders, schadet nicht).
- Keine Aenderung am pip-launcher.js / app.js noetig — Lesepfad ist `sessionStorage.getItem('headsetConfirmed')` und bekommt `null` nach dem removeItem → Modal triggered wieder.

**Anti-pattern-Check (nicht tun):**
- KEINEN `localStorage.removeItem` hinzufuegen (state ist in sessionStorage, nicht localStorage).
- KEINEN window.onload-Wrap — das Script ist so klein dass es sofort synchron laufen soll.
- KEIN Jinja-Template-Var einlesen — `g.user` None reicht als Signal.

**Commit:** `fix(POLISH-45): clear headset confirm state on logout`
  </action>
  <verify>
    <automated>bash -c "grep -cE 'sessionStorage\.removeItem\(.headsetConfirmed.\)' templates/base.html | awk '{ if (\$1 >= 2) print \"OK: \" \$1 \" occurrences (expected >=2 after insert)\"; else { print \"FAIL: \" \$1 \" occurrences\"; exit 1 } }' && grep -A1 '{% if not g.user %}' templates/base.html | grep -q 'headsetConfirmed' && echo OK || echo FAIL"</automated>
  </verify>
  <done>
- `templates/base.html` enthaelt MINDESTENS 2 Vorkommen von `sessionStorage.removeItem('headsetConfirmed')` (alt: onclick-Handler in Zeile ~135, neu: `{% if not g.user %}`-Block).
- Der neue Block ist syntaktisch valides Jinja + HTML (kein Fehler beim Flask-Render).
- Commit `fix(POLISH-45): clear headset confirm state on logout` existiert (nur templates/base.html im diff).
  </done>
</task>

<task type="auto">
  <name>Task 2 (POLISH-38.1): manual_ewb Handler setzt success=True/False passend zum Stream-Start-Erfolg</name>
  <files>services/deepgram_service.py</files>
  <action>
Aendere `handle_manual_ewb` in `services/deepgram_service.py` (um Zeile 400-448) so, dass der `record_ewb_click`-Call **NACH** dem `sio.start_background_task(_run)` platziert wird, und das `success`-Flag auf Basis des Spawn-Ergebnisses setzt.

**Aktueller Code (Zeile ~410-414):**
```python
import services.live_session as ls
try:
    ls.record_ewb_click(typ, success=False)
except Exception as e:
    print(f"[PiP] record_ewb_click error (sid={_sid}): {e}")
```

**Neuer Code (ersetze den try-record_ewb_click-Block komplett mit einem Flag, und rufe record_ewb_click am ENDE des Handlers auf):**

Schritt-fuer-Schritt:

1. Entferne das existierende `try: ls.record_ewb_click(typ, success=False)`-Block (Zeilen ~411-414). Behalte nur die `import services.live_session as ls`-Zeile oben.

2. Am ENDE des Handlers (nach dem `sio.start_background_task(_run)`-Call) fuege ein:
```python
        # POLISH-38.1: success=True wenn Stream-Start erfolgreich (= User hat Gegenargument
        # erhalten → EWB-Klick = Einwand behandelt per POLISH-29 User-Definition).
        # success=False nur wenn start_background_task selbst fehlschlaegt (Spawn-Error).
        _ewb_success = True
        try:
            sio.start_background_task(_run)
        except Exception as _spawn_err:
            _ewb_success = False
            print(f"[PiP] manual_ewb spawn error (sid={_sid}): {_spawn_err}")
        try:
            ls.record_ewb_click(typ, success=_ewb_success)
        except Exception as e:
            print(f"[PiP] record_ewb_click error (sid={_sid}): {e}")
```

3. Entferne die alte `sio.start_background_task(_run)`-Zeile am Ende (die wird jetzt durch den Block oben ersetzt).

**Final-Struktur des Handlers nach Fix:**

```python
@sio.on('manual_ewb')
def handle_manual_ewb(data=None, sid=None):
    from flask import request
    _sid = request.sid if sid is None else sid
    if not isinstance(data, dict):
        return
    typ = (data.get('text') or '').strip()
    if not typ:
        return
    print(f"[PiP] manual_ewb (sid={_sid}): {typ[:80]}")
    import services.live_session as ls

    # Profil + Kontext fuer Haiku-Variante aufbereiten.
    profile_daten = {}
    try:
        _pname, profile_daten = ls.get_active_profile()
    except Exception:
        profile_daten = {}
    einwaende = (profile_daten.get('einwaende') or []) if isinstance(profile_daten, dict) else []
    profile_einwand = None
    typL = typ.lower().strip()
    for e in einwaende:
        if isinstance(e, dict):
            label = (e.get('kurzlabel') or e.get('short_label') or e.get('kategorie') or '').lower().strip()
            if label == typL:
                profile_einwand = e
                break
    with ls.buffer_lock:
        kontext = " ".join(ls.analysiert_bisher[-20:])

    from services.claude_service import streame_manual_ewb_variante

    def _run():
        try:
            streame_manual_ewb_variante(typ, profile_einwand or {}, kontext, _sid, slot=1)
        except Exception as ex:
            print(f"[PiP] manual_ewb variante error (sid={_sid}): {ex}")
            try:
                sio.emit('pip_stream_error', {'slot': 1, 'error': str(ex)}, room=_sid)
            except Exception:
                pass

    # POLISH-38.1: success=True bei erfolgreichem Spawn (User erhaelt Gegenargument,
    # EWB-Klick = Einwand behandelt per POLISH-29). success=False nur bei Spawn-Error.
    _ewb_success = True
    try:
        sio.start_background_task(_run)
    except Exception as _spawn_err:
        _ewb_success = False
        print(f"[PiP] manual_ewb spawn error (sid={_sid}): {_spawn_err}")
    try:
        ls.record_ewb_click(typ, success=_ewb_success)
    except Exception as e:
        print(f"[PiP] record_ewb_click error (sid={_sid}): {e}")
```

**Rationale fuer Reihenfolge (record_ewb_click NACH start_background_task):**
Erst den Spawn, dann das Recording. Wenn der Spawn fehlschlaegt, wissen wir das und koennen success=False persistieren. Andernfalls ist success=True die korrekte Semantik (User bekommt Gegenargument → Einwand gilt als behandelt per POLISH-29).

**Was NICHT aendern:**
- Den `/api/ewb_trigger`-HTTP-Endpoint in `routes/app_routes.py` (Zeile 1064) NICHT anfassen — das ist ein **anderer** Code-Pfad (Live-Assistant-UI, nicht PiP). Scope ist **nur** der `@sio.on('manual_ewb')`-Handler in `deepgram_service.py` wie vom User beschrieben ("User klickt EWB-Button ohne Claude-Auto-Detection" = PiP-manual_ewb-Flow).
- Die DB-Schema (ObjectionEvent.success) NICHT migrieren — success ist Boolean nullable=False default=False, unser Fix nutzt nur True/False, keine None-Werte → keine Migration noetig.
- `record_ewb_click`-Helper in `live_session.py` NICHT aendern — Signatur bleibt `(einwand_typ: str, success: bool = False)`.

**Commit:** `fix(POLISH-38.1): set success flag on manual_ewb objection events`
  </action>
  <verify>
    <automated>bash -c "python -c \"import ast; src = open('services/deepgram_service.py', 'r', encoding='utf-8').read(); tree = ast.parse(src); print('syntax-OK')\" && grep -n 'record_ewb_click(typ, success=_ewb_success)' services/deepgram_service.py && grep -n '_ewb_success = True' services/deepgram_service.py && ! grep -n 'record_ewb_click(typ, success=False)' services/deepgram_service.py && echo OK-all"</automated>
  </verify>
  <done>
- `services/deepgram_service.py` parst syntaktisch als Python (ast.parse OK).
- Der Handler enthaelt `_ewb_success = True` sowie `ls.record_ewb_click(typ, success=_ewb_success)`.
- Das alte hardcoded `ls.record_ewb_click(typ, success=False)` existiert NICHT mehr im manual_ewb-Handler (grep zeigt 0 Matches in diesem Handler — falls in anderen Handlern noch success=False steht, nicht anfassen).
- Runtime-Smoke: `python -c "import services.deepgram_service as dg; print('import-OK')"` laeuft ohne Fehler.
- Commit `fix(POLISH-38.1): set success flag on manual_ewb objection events` existiert (nur services/deepgram_service.py im diff).
  </done>
</task>

<task type="auto">
  <name>Task 3: git push origin main</name>
  <files></files>
  <action>
Nach erfolgreichen atomic-Commits von Task 1 und Task 2: `git push origin main` ausfuehren (CLAUDE.md Git-Regel: "Nach jeder abgeschlossenen GSD-Phase und am Ende jeder Arbeitssession: `git push origin main` ausfuehren.").

**Reihenfolge der Operationen (nicht umstellen):**
1. Task 1 commit → im repo
2. Task 2 commit → im repo
3. `git log --oneline -5` zur Verifikation dass beide Commits vorhanden sind
4. `git push origin main`
5. Falls push-conflict: `git pull --rebase origin main` + nochmal pushen. Falls echte Konflikte: Stop und User melden.

**KEINE** `--force`-Pushes, keine amend-Commits, keine Git-Config-Aenderungen.
  </action>
  <verify>
    <automated>bash -c "git log --oneline -2 | grep -E 'POLISH-45|POLISH-38.1' | wc -l | awk '{ if (\$1 == 2) print \"OK: both commits present\"; else { print \"FAIL: \" \$1 \" / 2 commits found\"; exit 1 } }'"</automated>
  </verify>
  <done>
- `git log --oneline -2` zeigt beide Commits mit Prefix `fix(POLISH-45):` und `fix(POLISH-38.1):`.
- `git status` ist clean (working tree matches origin/main).
- `git push origin main` returned 0 / remote in sync.
  </done>
</task>

</tasks>

<verification>
**Phase-Level Checks (nach allen Tasks):**

1. **POLISH-45 Manual-Test (User-Verify nach Deploy):**
   - Logge dich in NERVE ein (getnerve.app).
   - Starte einen Cold-Call, bestaetige Headset-Modal.
   - Klicke Abmelden → Du landest auf / (Landing).
   - Logge dich nochmal ein (gleicher Tab).
   - Starte Cold-Call → **Headset-Modal MUSS wieder erscheinen.** (Wenn nicht: Bug. Tab nicht geschlossen, Storage nicht gecleaned.)

2. **POLISH-38.1 Manual-Test:**
   - Starte eine Live-Session mit PiP.
   - Klicke einen manual_ewb-Button im PiP-Fenster.
   - Beende die Session.
   - Oeffne DB (`sqlite3 database/salesnerve.db`) und prufe:
     ```sql
     SELECT einwand_typ, success, created_at FROM objection_events ORDER BY id DESC LIMIT 3;
     ```
     Neue Rows MUESSEN `success=1` (True) haben, falls der Stream erfolgreich startete.

3. **Syntax + Import:**
   - `python -c "import services.deepgram_service; print('OK')"` → OK
   - `python -c "from flask import Flask; a=Flask(__name__); a.jinja_env.get_template('base.html')"` (optional, Jinja parse-check)

4. **Git State:**
   - `git log --oneline -3` zeigt die 2 Fix-Commits + ggf. einen vorherigen.
   - `git status` ist clean nach push.
</verification>

<success_criteria>
- [x] **POLISH-45:** `templates/base.html` enthaelt `{% if not g.user %}`-Block mit `sessionStorage.removeItem('headsetConfirmed')`. Bestehender onclick-Handler bleibt. Commit-Message exakt `fix(POLISH-45): clear headset confirm state on logout`.
- [x] **POLISH-38.1:** `services/deepgram_service.py` `handle_manual_ewb`-Handler ruft `record_ewb_click(typ, success=_ewb_success)` NACH `sio.start_background_task`, mit `_ewb_success=True` im Normalfall und `_ewb_success=False` nur bei Spawn-Exception. Kein anderes `success=False`-Hardcoded-Match in diesem Handler. Commit-Message exakt `fix(POLISH-38.1): set success flag on manual_ewb objection events`.
- [x] **Atomic:** Task 1 und Task 2 sind 2 separate Commits (nicht zusammengefuehrt).
- [x] **Push:** `git push origin main` erfolgreich, GitHub zeigt die 2 neuen Commits auf main.
- [x] **Rechtliches:** Beide Commits referenzieren ihre POLISH-ID fuer Traceability zum backlog.md.
</success_criteria>

<output>
Nach Abschluss: `.planning/quick/260421-kwm-polish-45-polish-38-1-nachzug-headset-mo/260421-kwm-SUMMARY.md` erstellen mit:
- Commit-SHAs fuer beide Fixes
- Kurze Auflistung der geaenderten Zeilen (vorher/nachher)
- Manual-Verify-Ergebnis aus Verification-Abschnitt
- Entscheidung die User im Scope treffen kann: beide POLISH-Eintraege im backlog.md von "## Open" nach "## Done" verschieben (oder als separater Task nach Verify).
</output>
