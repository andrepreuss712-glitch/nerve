---
slug: post-call-false-negative
status: root_cause_found
trigger: "POLISH-41 LAUNCH-KRITISCH — Post-Call-Screen zeigt 'Kein Gespräch erkannt' auch bei Sessions die komplett in DB erfasst sind (Einwände, Painpoints, kb_end=74 etc.)"
created: 2026-04-21
updated: 2026-04-21
priority: launch-critical
cluster: "Live-Assistent Pipeline-Fix Session 2 of 4 (after POLISH-48 verified)"
related: [POLISH-48, POLISH-43, POLISH-38]
---

## Symptoms

**Expected behavior:** Nach "Beenden"-Klick zeigt der Post-Call-Screen/Overlay eine Kurz-Zusammenfassung (Score, "Gespräch analysiert"-Bestätigung, CTA "Vollständige Auswertung ansehen" → Navigation zu `/session/<id>`). Session-Daten sind zu diesem Zeitpunkt bereits persistiert (commit in `/api/beenden`).

**Actual behavior:** Post-Call-Screen rendert **"Kein Gespräch erkannt"** obwohl die Session komplett in DB liegt — alle Einwände, Painpoints, Skript-Abdeckung, kb_end=74 sind in `ConversationLog` und `ObjectionEvent` persistiert. User denkt der Call sei verloren, navigiert NICHT zu Detail-Seite, verliert Vertrauen.

**Error messages:** Kein expliziter Error. Falsche negative Interpretation im Frontend — User sieht Empty-State statt Summary.

**Timeline:** Cold-Call-UAT Phase 07.2 UAT-R2 (2026-04-20 / -21). Tritt bei **Cold Call** reproduzierbar auf. Meeting-Mode ebenfalls betroffen (gleicher Post-Call-Code-Pfad). Training-Mode: Post-Call-Overlay wurde in Phase 07.2 Wave 3 entfernt — stattdessen direkter Redirect auf `/session/<id>` (KEIN Post-Call-Overlay). **Also: POLISH-41 betrifft nur Live-Modi (Cold Call + Meeting).**

**Reproduction (mit Session #121 als frischem Test-Case):**
1. Login getnerve.app
2. `/live` → "Cold Call" (oder "Meeting")
3. Sprechen, EWB-Klicks, ≥60s Dauer
4. "Beenden"
5. Post-Call-Overlay erscheint — rendert "Kein Gespräch erkannt"-Empty-State
6. DB-Inspect (Session #117, #121 etc.): komplette Daten vorhanden

## Current Focus

hypothesis: **CONFIRMED.** Der "Kein Gespräch erkannt"-Empty-State wird im `NerveLauncher` PiP-Flow in `static/pip-launcher.js:1871-1880` (Funktion `_showPostcall`) getriggert. Der Guard prüft ausschließlich `berater_words === 0 && kunde_words === 0 && einwaende.length === 0`. Im Cold Call bleiben `berater_words` und `kunde_words` strukturell bei 0 (siehe Phase 07.1 DEVIATIONS Section D — "Cold Call hat keine Speaker-Diarization"). Wenn Claude-Analyse in derselben Session keine Einwände detektiert (z.B. weil der Customer-Audio-Input nicht vom Deepgram erfasst wird, nur Salesperson-Mic), dann `einwaende_liste == []` → alle 3 Bedingungen True → `_showPostcallEmpty()` → "Kein Gespräch erkannt" trotz aktiver EWB-Klicks, KB-Verlauf, Skript-Abdeckung etc.

test: Code-Trace vollständig. Guard-Location und Bedingung identifiziert. Phase 07.1 DEVIATIONS bestätigt "berater_words=0, kunde_words=0 in Cold Call" als architektonisch korrektes Verhalten. POLISH-43 (Post-Call zeigt 1 Einwand vs Session-Detail 4 Einwände) bestätigt zusätzlich: `einwaende_liste` (Claude-Analyse) und `ObjectionEvent` (EWB-Klicks) sind ZWEI getrennte Datenquellen — Claude detektiert in Cold Call-Szenarien oft weniger (oder gar keine) Einwände weil nur Salesperson-Speech analysiert wird.

expecting: Fix ist eine Bedingungs-Erweiterung in `_showPostcall()` — Guard akzeptiert mehrere Signale die "es hat ein Gespräch stattgefunden" belegen. Ca. 10-15 Zeilen JS-Änderung, ein File.

next_action: Fix applicieren, deployen, mit nächster Cold-Call-Session verifizieren.

reasoning_checkpoint: Die historische Guard-Entwicklung spiegelt diese Lücke: Phase 03.2 Guards in `app.js` beenden() checken `sessionSeconds < 10 || words < 20` (Client-Timer + Transcript-Wordcount — beides unabhängig von Speaker-Diarization). Der spätere PiP-Launcher (Phase 06.1 BUG-10, `_showPostcall`) übernahm NICHT dieselbe Logik sondern baute eine eigene Guard auf Backend-Response-Feldern — und wählte genau die zwei Felder (berater_words, kunde_words), die in Cold Call nicht gefüllt werden können. Phase 07.1 hat dann das Redeanteil-Display in `_renderQuickStats` Cold-Call-aware gemacht (siehe pip-launcher.js:1998-2013), aber die Empty-State-Guard in `_showPostcall` vergessen.

## Evidence

- timestamp: 2026-04-21T14:30
  finding: Grep `"Kein Gespräch erkannt"` trifft 3 aktive Code-Stellen
  details: |
    - `static/app.js:630` — Guard in full-page `beenden()` (nur aktiv wenn User auf `/live` ohne PiP): Bedingung `sessionSeconds < 10 || words < 20`. Diese Guard schützt Client-seitig VOR `/api/beenden`-Call.
    - `static/app.js:1663` — Guard in `pipBeendenCall()` (legacy PiP-Flow in app.js): Bedingung `sessionSeconds < 10`.
    - `static/pip-launcher.js:2086` — Empty-State-Renderer `_showPostcallEmpty()` (aktiver NerveLauncher-Flow).

- timestamp: 2026-04-21T14:40
  finding: Der aktive Post-Call-Path in Production ist `NerveLauncher.endCall()` → `_showPostcall(data.postcall)` (pip-launcher.js:1871-1888). Dort Guard:
  details: |
    Lines 1874-1880:
    ```js
    var berater = (postcall && postcall.berater_words) || 0;
    var kunde = (postcall && postcall.kunde_words) || 0;
    var einwTotal = ((postcall && postcall.einwaende) || []).length;
    if (berater === 0 && kunde === 0 && einwTotal === 0) {
      _showPostcallEmpty();
      return;
    }
    ```
    Der Guard-Kommentar (06.1-r2 BUG-10) erwähnt als Rationale "leerer Call, 45% für leere Calls verwirrt" — war für echte Empty-Calls gedacht, nicht für Cold-Call-by-design-0-Words.

- timestamp: 2026-04-21T14:50
  finding: Root-Cause-Verifikation via Phase 07.1 DEVIATIONS.md (`.planning/phases/07.1-polish-24-.../DEVIATIONS.md:57-67`, Section D — OBS-02)
  details: |
    "Cold-Call-Sessions zeigten 'Du redest nur 0% — zu wenig' Recommendation, obwohl Cold Call keine Speaker-Diarization hat (**berater_words=0, kunde_words=0** → redeanteil_avg=0.0)."
    Das bestätigt: `berater_words` und `kunde_words` sind in Cold Call IMMER 0. Der Fix für OBS-02 war in `_derive_practice_recommendations`. Der gleiche Architektur-Fakt wirkt sich auf `_showPostcall`-Guard aus — dort wurde der Fix aber vergessen.

- timestamp: 2026-04-21T15:00
  finding: Code-Trace `berater_words`/`kunde_words`-Increment in `services/live_session.py:271-282`
  details: |
    ```python
    with speech_lock:
        if sp_name == 'Berater':
            berater_words += word_count
            ...
        elif sp_name == 'Kunde':
            kunde_words += word_count
    ```
    `sp_name` wird NUR auf `'Berater'` oder `'Kunde'` gesetzt wenn `roles_confirmed == True` (services/deepgram_service.py:77-80). `roles_confirmed` erfordert `_second_sp_seen == True` (line 50) — also dass Deepgram mindestens einmal `speaker == 1` emittiert hat. Im Cold Call mit lokalem Mic (nur Salesperson) bleibt das aus → `sp_name = 'Sprecher'` → KEINE speech_lock-Increments → `berater_words = kunde_words = 0`.

- timestamp: 2026-04-21T15:05
  finding: POLISH-43 (Einwand-Count-Diskrepanz 1 vs 4) cross-bestätigt
  details: |
    `.planning/backlog.md:78-87`: "Post-Call-Overlay-Screen zeigt `1 Einwand`, Session-Detail-Seite zeigt für dieselbe Session `4 Einwände`". Das liefert den Hinweis, dass in realen Sessions Claude oft deutlich WENIGER Einwände detektiert als der User via EWB-Button anklickt. Im Extremfall (Cold Call, kurze eigene Antworten, keine sichtbare Customer-Speech): Claude-`einwaende_liste == []`. Damit ALLE drei Guard-Bedingungen (berater=0, kunde=0, einwaende=[]) True → Empty-State.

- timestamp: 2026-04-21T15:10
  finding: `/api/beenden`-Response-Schema enthält bereits genug Alternativ-Signale für robuste "has_conversation"-Detection
  details: |
    `routes/app_routes.py:322-332, 547`:
    ```python
    postcall = {
        'einwaende': einwaende_liste,      # list — Claude-detected
        'kaufsignale': kaufsignale_liste,  # list — Claude-detected
        'painpoints': [...],               # list — Claude-detected
        'berater_words': bw,
        'kunde_words': kw,
        'kb_start': ..., 'kb_end': kb_end,
        'kb_verlauf': kb_verlauf,          # list — KB-Änderungen über Zeit
        'skript_abdeckung': {...},
        'dauer_sek': dauer_sek,
    }
    postcall['ga_details'] = ga_details     # list — EWB-Button-Klicks mit KB-Deltas
    ```
    → Für "Conversation happened" reicht JEDES dieser Signale ≠ 0/leer:
    einwaende, kaufsignale, painpoints, ga_details, oder kb_verlauf > 0 Einträge,
    oder berater/kunde_words > 0.

## Eliminated

- **Hypothesis: Response-Schema hat sich in 07.2 geändert (Feld entfernt/renamed)** — FALSE. Die Response enthält `postcall` immer (line 565 im Routen-Handler: `return jsonify({'ok': True, 'filename': ..., 'postcall': postcall, 'conv_id': ...})`). Das Feld `postcall` ist ALWAYS gesetzt wenn `ok: True`.
- **Hypothesis: Frontend liest falsches Response-Feld (z.B. `data.has_conversation`)** — FALSE. Der aktive Code-Pfad liest `data.postcall` (line 1816) und dann `postcall.berater_words/kunde_words/einwaende` (line 1874-1876). Alle drei Felder EXISTIEREN in der Response; sie sind nur strukturell 0/leer in Cold Call-Szenarien.
- **Hypothesis: `data.transcript_text`-Check** — FALSE. Der Frontend-Guard liest `transcript_text` NICHT. DSGVO-"kein Transkript persistieren"-Regel ist irrelevant für diesen spezifischen Guard.
- **Hypothesis: Backend-Race-Condition (Response kommt vor DB-Commit)** — FALSE. Die Response wird NACH `db_conv.commit()` (line 428) und `db_conv.close()` zurückgegeben. `saved_conv_id` ist dann bereits gesetzt, alle postcall-Felder sind final.

## Test Session Available

- Session #121 (frisch, Cold Call, 4 Einwände + Painpoint + kb_verlauf) aus POLISH-48 Deploy-Verify — kann als Reproduce-Target genutzt werden.
- Session #117 (älter, Cold Call, 4 Einwände, kb_end=74) ebenfalls DB-persistiert.

## Related Files (to investigate)

- `routes/app_routes.py` — `/api/beenden` Response-Builder ✓ inspected, kein Backend-Change nötig
- `static/pip-launcher.js` — Post-Call-Overlay-Rendering im PiP-Modus ✓ Root-Cause lokalisiert, Fix hier
- `static/app.js` — Post-Call-Overlay im Full-Page-Modus ✓ inspected, existiert aber sekundär, kein Priority-Fix
- `templates/base.html` — `#nlp-section-postcall` DOM (line 489-502) ✓ keine Änderung nötig

## Proposed Fix

**File:** `static/pip-launcher.js`
**Function:** `_showPostcall(postcall)` (lines 1871-1888)
**Change:** Guard-Condition erweitern um alternative Conversation-Evidence-Signale

**Rationale:** Der aktuelle Guard (3 AND-Bedingungen auf berater_words/kunde_words/einwaende) ist nicht Cold-Call-aware. In Cold Call bleibt Speaker-Diarization strukturell aus → berater/kunde_words IMMER 0. Der Guard muss andere Signale akzeptieren die "es fand ein echtes Gespräch statt" belegen: Claude-Painpoints, Claude-Kaufsignale, EWB-Button-Klicks (ga_details), KB-Verlauf-Änderungen, ODER die klassischen berater/kunde_words (weiterhin relevant für Meeting-Mode).

**Diff (conceptually):**
```js
// VORHER (lines 1871-1880):
function _showPostcall(postcall) {
  var berater = (postcall && postcall.berater_words) || 0;
  var kunde = (postcall && postcall.kunde_words) || 0;
  var einwTotal = ((postcall && postcall.einwaende) || []).length;
  if (berater === 0 && kunde === 0 && einwTotal === 0) {
    _showPostcallEmpty();
    return;
  }
  ...
}

// NACHHER:
function _showPostcall(postcall) {
  // POLISH-41: Empty-State-Guard akzeptiert mehrere Signale für "Gespräch hat stattgefunden".
  // Im Cold Call bleiben berater_words/kunde_words strukturell 0 (keine Speaker-Diarization,
  // siehe Phase 07.1 DEVIATIONS Section D). Guard muss alternative Content-Signale einbeziehen.
  var pc = postcall || {};
  var einwTotal = (pc.einwaende || []).length;
  var ppTotal = (pc.painpoints || []).length;
  var ksTotal = (pc.kaufsignale || []).length;
  var gaTotal = (pc.ga_details || []).length;
  var kbSteps = (pc.kb_verlauf || []).length;
  var berater = pc.berater_words || 0;
  var kunde = pc.kunde_words || 0;
  var hasConversation =
    einwTotal > 0 ||   // Claude-Einwand detektiert
    ppTotal > 0 ||     // Claude-Painpoint detektiert
    ksTotal > 0 ||     // Claude-Kaufsignal detektiert
    gaTotal > 0 ||     // EWB-Button geklickt (expliziter User-Einwand-Beleg)
    kbSteps > 0 ||     // KB-Verlauf hat Einträge (KB wurde mindestens einmal aktualisiert)
    berater > 0 ||     // Meeting-Mode: Salesperson-Words gezählt
    kunde > 0;         // Meeting-Mode: Customer-Words gezählt
  if (!hasConversation) {
    _showPostcallEmpty();
    return;
  }
  ...
}
```

**Test-Plan:**
1. Deploy auf getnerve.app VPS
2. Cold Call starten, ≥30s sprechen, 1-2 EWB-Buttons klicken, Beenden
3. Erwartung: Post-Call zeigt Score + Quickstats (NICHT "Kein Gespräch erkannt")
4. DB-Check: neue ConversationLog-Row mit EWB-ObjectionEvents ↔ Post-Call-Overlay zeigt passende Anzahl
5. Edge-Case: Cold Call starten, sofort Beenden (2s) — erwartet: Empty-State korrekt angezeigt (weil `kb_verlauf` leer, keine EWB-Klicks, keine Claude-Analyse)
6. Meeting-Mode (falls verfügbar): Cross-Verify dass berater_words-Increment weiterhin funktioniert und Empty-State korrekt nicht-triggert

**Risiko-Assessment:** Low.
- Change ist rein additiv (Guard lässt mehr Calls DURCH als vorher).
- Keine Backend-Änderungen nötig.
- Keine Schema-Änderungen.
- Edge-Case "Empty-Call mit 2s Dauer" wird weiterhin korrekt als Empty-State angezeigt (kb_verlauf, ga_details etc. alle leer).

## Cluster Plan (Status)

- Session 1 POLISH-48 (Meeting-Transcription) — ✓ RESOLVED, runtime-verified in Session #121
- Session 2 POLISH-41 (this) — **ROOT CAUSE FOUND**, fix proposed
- Session 3 POLISH-38/39/40/42 (Backend-Persistenz-Bundle) — pending
- Session 4 POLISH-46 (Auto-Einwand-Erkennung + Keyword-Matcher-Flexion) — pending
