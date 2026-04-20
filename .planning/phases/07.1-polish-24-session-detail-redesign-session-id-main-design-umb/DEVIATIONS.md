# Phase 07.1 — Deviations

Diese Datei dokumentiert Abweichungen vom Plan, die während Phase-07.1-Ausführung
auftraten. Quelle: automatische Rule-1/2/3-Fixes + UAT-Round-1-Findings.

---

## UAT Round 1 Findings (2026-04-18)

Wave 3 Smoke-Test auf https://getnerve.app lieferte 6 launch-blockende Bugs. Alle
atomar (1 Commit/Bug) gefixt auf `main`, dann CSS_VERSION-Bump + Re-Deploy + UAT-R2.

### A — Score-Breakdown-Labels verwirrend

- **Finding:** "Kaufbereitschaft Ende (40%)" las sich wie Metrik, nicht Gewichtung.
- **Rule:** Rule 2 — Missing usability correctness (UX-Verständlichkeit).
- **Fix:** Entfernte Gewichtungs-% aus Label-Text; Gewichtung als dezenter
  `title="Gewichtung X% im Gesamt-Score"`-Tooltip am `.n-label`. Kein Extra-Icon,
  kein Layout-Shift.
- **Files:** `templates/session_detail.html` (Section 2 Live-Breakdown, 4 Rows)
- **Commit:** `d359dc3`

### B — kb_end (20) ≠ letzter kb_verlauf-Punkt (~31)

- **Finding:** Score-Hero zeigte `conv.kb_end=20`, Chart-Endpunkt war `~31`. User
  sah Widerspruch zwischen zwei "Ende"-Werten.
- **Rule:** Rule 1 — Data-consistency bug.
- **Fix:** In `routes/dashboard.py` `session_detail` `kb_end_effective` aus
  letztem `kb_verlauf[-1].wert` abgeleitet (Fallback: `conv.kb_end`). Temporäres
  Setzen von `conv.kb_end = kb_end_effective` für `_calc_call_score`-Aufruf,
  Original danach restauriert. Template-Context um `kb_end_effective` erweitert;
  Section 1 Meta ("Result:") und Section 2 Live-Breakdown (`kb_pct`) nutzen jetzt
  den effektiven Wert.
- **Files:** `routes/dashboard.py`, `templates/session_detail.html`
- **Commit:** `8aec4af`

### C — Einwand-Timeline zeigt Empty-State (0) trotz einwaende_gesamt=1

- **Finding:** `events | length == 0` obwohl `conv.einwaende_gesamt == 1` — User
  sah "Einwand-Timeline (0)" und komplett-leeren Empty-State, obwohl KI einen
  Einwand erkannt hatte.
- **Root cause:** `ObjectionEvent` wird NUR bei EWB-Button-Klick persistiert
  (`routes/app_routes.py:437`, aus `ls.state['ewb_clicks']`). `einwaende_gesamt`
  kommt aus Claude-Analyse-Counter und ist unabhängig vom Button-State. Wenn
  Einwand erkannt aber kein Button geklickt → Delta.
- **Rule:** Rule 2 — Missing information (User sah nicht, dass Einwand erkannt wurde).
- **Fix:** Keine Query-Änderung (Query war schon ungefiltert). Template:
  - Count-Header zeigt `max(einwaende_gesamt, events|length)`
  - Zweiter Empty-State für "einwaende_gesamt > 0 aber keine Events" mit
    erklärendem Text ("erkannt, aber ohne Button-Klick beantwortet")
  - Hint-Paragraph wenn Delta vorhanden
  - `n-session-detail-timeline-row--danger` CSS-Modifier für `success=False`-Events
    (left-border rot, leichter roter Hintergrund)
- **Files:** `templates/session_detail.html` (Section 4), `static/nerve.css` (2 neue CSS-Klassen)
- **Commit:** `4e42fb7`

### D — Redeanteil 0.0% Trigger bei Cold Call (OBS-02)

- **Finding:** Cold-Call-Sessions zeigten "Du redest nur 0% — zu wenig"
  Recommendation, obwohl Cold Call keine Speaker-Diarization hat (berater_words=0,
  kunde_words=0 → redeanteil_avg=0.0).
- **Rule:** Rule 1 — False-positive recommendation bug.
- **Fix:** In `_derive_practice_recommendations` Redeanteil-Regel geblockt wenn
  `session_mode == 'cold_call'`. Gate via `_has_diarization = (_mode != 'cold_call')`.
  Kommentar "OBS-02" im Code für Traceability.
- **Files:** `routes/app_routes.py` (`_derive_practice_recommendations`, Regel 3 Live-Branch)
- **Commit:** `b505cae`

### E — Chart-Achsen unbeschriftet

- **Finding:** Chart.js-Diagramme zeigten nur Tick-Werte ohne Achsen-Titel. User
  musste raten was Y-Achse bedeutet.
- **Rule:** Rule 2 — Missing accessibility/orientation info.
- **Fix:** `scales.x.title` + `scales.y.title` mit Chart.js `title`-Config
  ergänzt, styled wie Tick-Color (#6B7280, Inter 12px 600w):
  - Live-Chart: Y = "Kaufbereitschaft (%)", X = "Zeit (Sekunden)"
  - Training-Chart: Y = "Stimmung", X = "Turn"
  (X-Label für Training ist "Turn" statt "Zeit (Sekunden)" weil `labels = 'Turn '+e.turn`
  gemapped wird — semantisch korrekter als Sekunden.)
- **Files:** `templates/session_detail.html` (Chart.js-Init-Block)
- **Commit:** `b0e2837`

### F — Umlauten-Bug in _derive_practice_recommendations

- **Finding:** ASCII-Escapes (`Uebe`, `Fuehre`, `Gespraech`, `aehnlich`,
  `Persoenlichkeit`, `frueher`, `haeufig`, `Schwaeche`, `Zuhoeren`) in
  User-facing `observation`/`explanation`-Strings.
- **Rule:** Rule 1 + CLAUDE.md Umlauten-Regel — User-facing Text MUSS echte Umlaute
  nutzen; nur Code-Identifier (`training_focus`, `training_url`, dict-keys) bleiben
  ASCII.
- **Fix:** Alle 8 User-facing-Strings in `_derive_practice_recommendations` auf
  echte Umlaute (Übe, Führe, Gespräch, ähnlich, Persönlichkeit, früher, häufig,
  Schwäche, Zuhören). Dict-keys/Focus-Slugs/URL bleiben ASCII. Verifiziert mit
  `inspect.getsource` + Assertions (alle Umlaute vorhanden, keine Escapes mehr).
  Datei bleibt UTF-8 ohne BOM, Python-Import clean.
- **Files:** `routes/app_routes.py` (`_derive_practice_recommendations`)
- **Commit:** `1a01ff1`

---

## Abschluss (2026-04-18)

Alle 6 UAT-R1-Findings atomar committet + CSS_VERSION auf `20260418-3` gebumpt
für Browser-Cache-Invalidation. Re-Deploy via `bash deploy.sh` vorbereitet für
UAT Round 2.

**Commit-Chain (UAT-R1):**

| # | Commit   | Finding                                                         |
| - | -------- | --------------------------------------------------------------- |
| A | `d359dc3` | remove weight-% from score-breakdown labels                    |
| B | `8aec4af` | derive kb_end from kb_verlauf last point for consistency       |
| C | `4e42fb7` | show all ObjectionEvents in timeline, mark failed as danger    |
| D | `b505cae` | skip Redeanteil trigger for cold_call (OBS-02)                 |
| E | `b0e2837` | add axis titles to kb/stimmung charts                          |
| F | `1a01ff1` | fix umlaut escapes in practice-recommendations strings         |
| — | (next)   | bump CSS_VERSION to 20260418-3 + document UAT-R1 fixes         |

STATE.md / ROADMAP.md werden vom Orchestrator nach UAT-R2-Abschluss aktualisiert.
SUMMARY `07.1-03-SUMMARY.md` wird vom Orchestrator amendiert.

---

## UAT Round 2 Findings (2026-04-18)

Re-Test von Session #110 auf https://getnerve.app nach UAT-R1-Deploy lieferte
4 weitere Bugs. Alle atomar (1 Commit/Bug) auf `main`, dann CSS_VERSION-Bump +
Re-Deploy für UAT Round 3.

### G — kb_end-Sync in _derive_practice_recommendations unvollständig

- **Finding:** Template/Chart zeigten synchron kb_end=30 (aus kb_verlauf[-1]),
  Recommendation-Card zeigte weiterhin "Kaufbereitschaft Ende: 20/100" (alter
  DB-Wert). UAT-R1 Fix B war nur halb — Helper las `conv.kb_end` direkt.
- **Rule:** Rule 1 — Data-consistency bug (Follow-up zu Fix B).
- **Fix:** In `_derive_practice_recommendations` `kb_end_effective` analog zur
  Fallback-Logik in `routes/dashboard.py` und Template berechnen:
  `kb_verlauf[-1].wert` wenn vorhanden, sonst `conv.kb_end`, sonst `0`.
  Alle 3 Verwendungen (Training Regel 1 Guard+Observation, Live Regel 2
  Guard+Observation) nutzen den effektiven Wert.
- **Files:** `routes/app_routes.py` (`_derive_practice_recommendations`)
- **Commit:** `84216bf`

### H — Recommendation-String "skeptischer als gesund" sprachlich kaputt

- **Finding:** Text "Der Kunde ist am Ende skeptischer als gesund. Übe
  Qualifizierungs-Fragen." — Skepsis ist keine Gesundheits-Skala, Metapher
  unsinnig und unprofessionell.
- **Rule:** Rule 2 — Copy/UX correctness.
- **Fix:** Ersetzt durch "Der Kunde ist am Ende ungewöhnlich skeptisch. Übe
  Qualifizierungs-Fragen, um früh Vertrauen aufzubauen." — klare Beobachtung
  + konkreter Trainings-CTA. Umlaute echt (CLAUDE.md User-facing-Regel).
- **Files:** `routes/app_routes.py` (`_derive_practice_recommendations`,
  Live-Branch Regel 2)
- **Commit:** `01b63d0`

### I — Painpoint-Dedupe (Sektion 7)

- **Finding:** Zwei fast-identische Painpoints landeten in Section 7, weil
  der Backend-Analyse-Loop sie doppelt erzeugte (leichte Umformulierung
  desselben Schmerzpunkts).
- **Rule:** Rule 2 — Missing correctness (dedupe fehlt am Persistence-Rand).
- **Fix:** Neuer Helper `_dedupe_painpoints` in `routes/dashboard.py` nutzt
  `difflib.SequenceMatcher` — Ratio > 0.75 gegen bereits gesehene Einträge
  = Duplikat. Route dedupe't vor `render_template`, übergibt Liste als
  `painpoints`-Variable. Template nutzt die neue Variable mit Fallback auf
  `conv.painpoints_details | fromjson` für Legacy-Pfad-Kompatibilität.
- **Files:** `routes/dashboard.py` (Helper + session_detail),
  `templates/session_detail.html` (Section 7)
- **Commit:** `ea56a15`

### J — Phasen-Verlauf Empty-State Text erweitern

- **Finding:** Empty-State für Phasen-Verlauf erklärte nicht, warum kurze
  Test-Calls keine Phasen zeigen.
- **Rule:** Rule 2 — Missing orientation info (UX).
- **Fix:** Zweiter Paragraph im Empty-State: "Phasen-Erkennung greift erst
  ab etwa 60 Sekunden Gesprächsdauer. Bei kurzen Test-Calls bleibt diese
  Sektion leer." Reine Copy-Änderung.
- **Files:** `templates/session_detail.html` (Section 5 Phasen-Strip)
- **Commit:** `2f5b547`

---

## Abschluss UAT-R2 (2026-04-18)

Alle 4 UAT-R2-Findings atomar committet + CSS_VERSION auf `20260420-1`
gebumpt für Browser-Cache-Invalidation. Re-Deploy via `bash deploy.sh`
vorbereitet für UAT Round 3.

**Commit-Chain (UAT-R2):**

| # | Commit    | Finding                                                         |
| - | --------- | --------------------------------------------------------------- |
| G | `84216bf` | sync kb_end in recommendations helper with kb_verlauf fallback  |
| H | `01b63d0` | rewrite skepsis recommendation copy                             |
| I | `ea56a15` | dedupe near-duplicate painpoints via SequenceMatcher            |
| J | `2f5b547` | extend Phasen-Strip empty-state copy                            |
| — | (next)    | bump CSS_VERSION to 20260420-1 + document UAT-R2 fixes          |

---

## UAT Round 3 Findings (2026-04-18)

Re-Test nach UAT-R2-Deploy lieferte einen BLOCKER (Training-Seite komplett
500) plus Painpoint-Dedupe-Threshold zu strikt. Atomar auf `main` gefixt,
CSS_VERSION-Bump, Re-Deploy fuer UAT Round 4.

### K — BLOCKER: Training-Seite 500 wegen Umlaut-Identifier-Mismatch

- **Finding:** `/training` warf `jinja2.exceptions.UndefinedError:
  'sekretärin_types' is undefined` — der gesamte "Im Training üben"-Button
  aus POLISH-24 war tot.
- **Root cause:** `templates/training.html:451` nutzte die Jinja-Variable
  `sekretärin_types` (mit Umlaut), aber `routes/training.py:60` übergibt
  den Context als `sekretaerin_types` (ASCII, wie es `services/training_
  service.py` mit `SEKRETAERIN_TYPES` definiert). Jinja versuchte eine
  Python-Variable mit Umlaut aufzulösen — gibt's nicht.
- **Rule:** Rule 1 — Bug + Rule 2 — CLAUDE.md-Regel-Bruch ("ASCII-Pflicht
  für Code-Identifier, echte Umlaute nur in User-facing Text").
- **Fix:**
  1. `templates/training.html:451` — `sekretärin_types` -> `sekretaerin_types`.
  2. `templates/training.html:380` — toter Filter `{% if key != 'sekretärin' %}`
     entfernt (SCHWIERIGKEITEN hat keinen solchen Key, Check war ALWAYS
     true). Durch Jinja-Kommentar ersetzt, der die Entfernung dokumentiert.
- **Preventive scan:** Grep über alle `templates/*.html` nach Umlaut-
  Identifiern in Jinja `{{ }}` / `{% %}`-Expressions (außerhalb von
  String-Literals). Ergebnis:
  - `training.html:451` — sekretärin_types    -> FIXED
  - `training.html:380` — 'sekretärin' Literal -> REMOVED (dead)
  - `base.html:110`    — Sprach-Label-Literals -> OK (user-facing Text)
  - `app.html:1221` + `static/app.js` x5 — `window._profileEinwände`
    Identifier mit Umlaut: Konvention-Bruch, aber KEIN Runtime-Bug
    (Definition + alle 5 Read-Zugriffe konsistent). Live-kritischer Pfad
    -> Deferred als D-1 in `deferred-items.md` (P2).
- **Files:** `templates/training.html`
- **Commit:** `f238fa1`

### I-bis — Painpoint-Dedupe-Threshold zu strikt

- **Finding:** User sah weiterhin Near-Duplicate-Painpoints in Section 7,
  obwohl UAT-R2 I den `_dedupe_painpoints`-Helper mit SequenceMatcher > 0.75
  eingeführt hatte. Beispielpaar:
  - "Vertriebler wissen im Moment eines Einwands nicht, was sie sagen sollen"
  - "Vertriebler haben im Moment des Einwands keine Antwort parat"
  Gemessener Ratio: **0.656** — rutschte knapp durch den 0.75-Filter.
- **Rule:** Rule 2 — Threshold-Tuning (UX-Korrektheit, Follow-up zu UAT-R2 I).
- **Fix:** Threshold `> 0.75` -> `> 0.60` in `routes/dashboard.py`
  `_dedupe_painpoints`. 0.60 fängt das Beispielpaar ab, bleibt aber
  deutlich über 0.50 (sonst False-Positives bei inhaltlich verschiedenen
  Painpoints zum selben Thema). Docstring um Threshold-History +
  konkretes Ratio-Beispiel erweitert, Inline-Kommentare synchronisiert.
- **Files:** `routes/dashboard.py`
- **Commit:** `48af46c`

---

## Abschluss UAT-R3 (2026-04-18)

K + I-bis atomar committet + CSS_VERSION auf `20260420-2` gebumpt für
Browser-Cache-Invalidation. Re-Deploy via `bash deploy.sh` vorbereitet
für UAT Round 4.

**Commit-Chain (UAT-R3):**

| #     | Commit    | Finding                                                          |
| ----- | --------- | ---------------------------------------------------------------- |
| K     | `f238fa1` | fix Umlaut-Identifier Training crash + systematic scan           |
| I-bis | `48af46c` | lower painpoint dedupe threshold 0.75 -> 0.60                    |
| —     | (next)    | bump CSS_VERSION to 20260420-2 + document UAT-R3 fixes           |

---

## UAT Round 4 / Wave 4 Findings (2026-04-18)

Hauptscope POLISH-24 (Session-Detail-Redesign) nach UAT-R3 approved. Drei Nacharbeiten
(Training-Header-Badges, Training-Trend-Badge, errorhandler-Passthrough) blieben offen
und werden als Wave 4 atomar auf `main` gefixt, dann CSS_VERSION-Bump + Re-Deploy +
UAT-R5 (final).

### POLISH-32 — Training-Header zeigt Persoenlichkeits-Typ + Schwierigkeit als Badges

- **Finding:** Training-Session-Detail-Header (Session #113) zeigte nur "Training"
  + em-dash. `personality_type`-Badge (falls vorhanden) + `schwierigkeit`-Badge
  fehlten komplett.
- **Root cause (zweiteilig):**
  1. `routes/training.py:705` persistierte `phasen_details = json.dumps(scoring)`
     — reines Scoring-Dict OHNE `schwierigkeit`. Die `session_detail`-Route
     parste `phasen_details.schwierigkeit`, fand nie einen Wert, lieferte
     `schwierigkeit_label='—'`.
  2. Template rendete Badge unconditional mit em-dash-Platzhalter bei leerem Wert.
- **Rule:** Rule 1 — Data-completeness bug (fehlende Persistierung) +
  Rule 2 — UX-Korrektheit (em-dash-Platzhalter statt ausgeblendet).
- **Fix:**
  - `routes/training.py`: `phasen_details`-Payload um `'schwierigkeit'`-Key
    erweitert (Copy von scoring-Dict + session['schwierigkeit'], JSON-serialisiert
    mit `ensure_ascii=False`). Keine neue DB-Spalte — JSON koexistiert.
  - `routes/dashboard.py` `session_detail`: `schwierigkeit_label`-Default `None`
    statt `'—'`; Mapping-Lookup liefert `None` wenn Key unbekannt oder leer.
  - `templates/session_detail.html`: Badge-Block in `{% if schwierigkeit_label %}`
    gewrappt — kein em-dash-Platzhalter mehr.
- **Files:** `routes/training.py`, `routes/dashboard.py`, `templates/session_detail.html`
- **Commit:** `2fbb7ca`
- **Impact:** Neue Training-Sessions zeigen 3 Badges (Training + Persoenlichkeit +
  Schwierigkeit). Alte Sessions ohne persistierte `schwierigkeit` zeigen nur die
  Badges, fuer die Daten vorliegen (kein em-dash).

### POLISH-33 — Training-Trend-Badge fehlt im Score-Hero

- **Finding:** Cold-Call-Sessions zeigten im Score-Hero "+X vs Schnitt letzte 5".
  Training-Sessions (Session #113) hatten KEINE Trend-Badge.
- **Root cause:** `routes/dashboard.py` `session_detail` hatte explizites Gate
  `if conv_typ == 'live'` um den Trend-Query — `trend_avg` blieb fuer Training
  immer `None`. Zusaetzlich Template-Gate `conv.typ != 'training'` als doppelte
  Sperre.
- **Rule:** Rule 2 — Missing feature-parity (User-Erwartung: beide Session-Typen
  zeigen Trend-Indikator).
- **Fix:** Trend-Query typ-diskriminierend gemacht:
  - **Live:** `_calc_call_score`-Mittel ueber letzte 5 `typ='live'` Sessions
    (unveraendert).
  - **Training:** `kb_end`-Mittel ueber letzte 5 `typ='training'` Sessions
    (None-tolerant, None->0). Passt zum Score-Hero-Wert fuer Training
    (`score_total = kb_end_effective`).
  - Template-Gate `conv.typ != 'training'` entfernt — reines `trend_avg is not none`.
- **Files:** `routes/dashboard.py`, `templates/session_detail.html`
- **Commit:** `c61d7a1`
- **Impact:** Training-Trend-Badge rendert wenn User >=1 historische Training-Session
  hat. Cold-Call-Verhalten unveraendert.

### POLISH-21 — @app.errorhandler(Exception) schluckt HTTPException

- **Finding:** Aufruf nicht-existenter URLs (z.B. `/unknown-route`) landete im
  generic 500-Handler mit Python-Traceback im Browser statt in Flasks normaler
  404-Page. Bei UAT 2x blockierend + Security-Leak (Server-Code sichtbar).
- **Root cause:** `app.py:1309` `@app.errorhandler(Exception)` fing auch
  `werkzeug.exceptions.HTTPException` (404/403/405/...) — die tragen bereits
  einen korrekten Statuscode und sollen von Flask normal gerendert werden, nicht
  als 500er mit Traceback.
- **Rule:** Rule 1 — Bug (falsche Behandlung korrekter HTTPExceptions) +
  Rule 2 — Security correctness (Server-Code-Leak).
- **Fix:**
  - `from werkzeug.exceptions import HTTPException as _HTTPException` am
    errorhandler-Block (konsistent mit bestehendem lokalem Import-Stil).
  - Erste Zeile im Handler: `if isinstance(e, _HTTPException): return e` —
    vor jeglichem Traceback-Rendering/Logging, damit Flask die normale
    404/403/405/...-Page liefert.
- **Files:** `app.py`
- **Commit:** `19b2570`
- **Impact:** `/this-route-does-not-exist-xyz` liefert jetzt echte 404 statt
  500+Traceback. Kein Server-Code-Leak mehr.

### POLISH-34 — Gesamt-Score-Dopplung (DEFERRED zu Phase 07.2)

- **Finding:** Score-Hero + Breakdown-Row zeigen `Gesamt-Score` doppelt.
- **Entscheidung:** NICHT in Wave 4 fixen. Gehoert zur Scoring-Konsolidierung
  in Phase 07.2 (kompletter Redesign der Score-Architektur: ein kanonischer
  Score-Pfad Live vs. Training, Komponentenauswahl, Gewichtungs-Matrix).
- **Begruendung:** Ein kosmetischer Hide-der-Dopplung waere technische Schuld,
  weil die darunter-liegende Score-Semantik (zwei Werte mit gleichem Label)
  erhalten bliebe. 07.2 raeumt das strukturell auf.

**Commit-Chain (Wave 4):**

| #          | Commit    | Finding                                                        |
| ---------- | --------- | -------------------------------------------------------------- |
| POLISH-32  | `2fbb7ca` | training header shows personality + difficulty badges          |
| POLISH-33  | `c61d7a1` | add training-specific trend badge via typ-aware avg            |
| POLISH-21  | `19b2570` | pass HTTPException through generic errorhandler                |
| —          | (next)    | bump CSS_VERSION to 20260420-3 + document Wave 4 fixes         |
