---
audit: deep-dive-app-routes-rest
erstellt: 2026-04-24
scope: routes/app_routes.py (1462 Zeilen) — alle Routes + Helfer, AUSSER /api/frage (1118-1160) und /api/ewb_trigger (1163-1272) die bereits in MASTER-AUDIT H-12/H-13/H-14/H-15 analysiert sind
autor: Deep-Dive-Agent (Welle 3)
basiert_auf:
  - Code-Lesung app_routes.py Z.1-1117 + 1273-1462
  - Cross-Grep in static/*.js + templates/*.html fuer Frontend-Usage
  - Abgleich gegen MASTER-AUDIT.md (LB-1..LB-8, H-1..H-15)
---

# Deep-Dive: routes/app_routes.py (Rest)

## TL;DR

**app_routes.py ist das zentrale Live-Call-Backend** (Setup, Ergebnis-Polling, Session-Ende, PostCall, Quick-Actions, EWB, PreCall, Feedback). Neben den bereits dokumentierten `/api/frage` + `/api/ewb_trigger`-Problemen (H-12..H-15) finden sich im Rest:

1. **Ein weiterer inline-Anthropic-Client ohne Cost-Tracking** — `/api/postcall_insights` (`app_routes.py:1322-1354`). Dritter Callsite mit Pattern `_ant.Anthropic(api_key=...)` + hardcoded `claude-haiku-4-5-20251001`. **Erhoeht LB-4-Impact und H-12-Pattern-Count** (jetzt 3 Inline-Clients statt 2 in MASTER-AUDIT).
2. **Zwei Routes silent-swallowen Exceptions** ohne Log — `api_postcall_insights` returnt `{'ok': True, 'bullets': ['Keine Insights verfuegbar.', '', '']}` bei jedem Fehler (Malformed LLM Response, Rate-Limit, API-Down) — **User sieht "OK" obwohl Feature kaputt**. Selbes Muster wie H-10 (_parse_json).
3. **`api_set_phase` validiert nichts** — akzeptiert jeden Integer als `phase_index`, inkl. Out-of-Bounds oder negativ. Covered_phases-Set kann mit Muell gefuellt werden. Skript-Abdeckungs-Prozent in PostCall/DB wird korrumpiert.
4. **`/api/skripte` ist mutmasslich dead/orphan** — kein Caller in static/*.js. Die aktive Frontend-Kette nutzt `/api/launcher/init` + `/api/launcher/profile/<pid>` die skripte inline ausliefern. `/api/skripte` wurde in Phase 06.1 gebaut, Phase 06.2+ hat aber auf die Launcher-Routes umgestellt. **Endpoint wirkt live, existiert aber nur in Tests.**
5. **`api_beenden` schreibt 2 neue `ls.state`-Writes** die in MASTER-AUDIT noch nicht dokumentiert sind: `ls.state['ft_session_id'] = None` (OK — Cleanup) und **liest** `session_anrede`, `ewb_clicks`, `ft_session_id`. `session_anrede` hat einen Writer (siehe unten). `ewb_clicks` ist ein Array — wird 2x gelesen in derselben Route mit separatem Lock-Acquire (Z.407 und Z.564), zwischen denen beliebiger Code laeuft → **potenzielles TOCTOU-Race** bei parallelem EWB-Click-Append waehrend Beenden-Flow.
6. **Profil-Feld-Drift `pdata.get("produkt")` bestaetigt sich NICHT ausserhalb der 2 bekannten Routes** — restliche Routes lesen entweder ueberhaupt kein `pdata` oder korrekt `pdata.get('phasen')` / `pdata.get('einwaende')`. H-13 bleibt auf `/api/frage` + `/api/ewb_trigger` beschraenkt.
7. **Keine SocketIO-Emits in app_routes.py.** Ganze Datei ist HTTP-only. SocketIO-Emits kommen aus `services/deepgram_service.py` + `services/live_session.py`. Fuer Cross-Module-Audit relevant: Polling-basiertes `/api/ergebnis` (Z.134) ist das eine, Socket-Events sind das andere — **2 parallele Push-Mechanismen fuer denselben State**. Frontend polled `/api/ergebnis` (app.js:780), SocketIO liefert ebenfalls Updates. Redundanz oder Legacy? Nicht in dieser Datei zu klaeren.
8. **Kein Auth-Decorator fehlt** — alle 20 Routes tragen `@login_required`. Kein CSRF-Schutz sichtbar (wie ueberall in der Codebase — Standard-Flask-Session-Auth ohne CSRF-Token).

---

## Route-Tabelle

| Route | Methoden | Auth | Frontend-Caller | Status | Auffaelligkeiten |
|---|---|---|---|---|---|
| `/live` | GET | `@login_required` | Direkt-Navigation | LIVE | Fair-Use-Reset-Block; laedt Profile; schreibt `ls.set_active_profile`. OK. |
| `/api/ergebnis` | GET | ja | app.js:780 (polling chain) | LIVE | Liest 11 ls.state-Felder. `ewb_top2` legacy-Kommentar bestaetigt MASTER-AUDIT. |
| `/api/analyse_line` | POST | ja | app.js:427 | LIVE | Ruft `analysiere_mit_claude` direkt. **Kein Cost-Hook in dieser Call-Site** (aber analysiere_mit_claude hat intern einen — per Welle 1). |
| `/api/log_correction` | POST | ja | app.js:420, 441 | LIVE | Trivial. OK. |
| `/api/pause` | POST | ja | app.js:573 | LIVE | OK. |
| `/api/swap_roles` | POST | ja | — | **ORPHAN** | Kein Frontend-Caller. Dead Route oder Admin-Only? |
| `/api/status` | GET | ja | — | **ORPHAN** | Kein Frontend-Caller. Kandidat fuer Dead-Code-Prune. |
| `/api/log` | GET | ja | app.js:689 | LIVE | Download-Button. OK. |
| `/api/beenden` | POST | ja | app.js:646, 1670, pip-launcher.js:1885 | LIVE | 420 Zeilen (258-682), siehe Findings. |
| `/api/keepalive` | POST | ja | — | **ORPHAN** | 1-Line-Stub, kein Caller. Heartbeat ungenutzt. |
| `/api/postcall/trend` | GET | ja | pip-launcher.js:2138 | LIVE | OK. 20-Query-Limit. `_calc_call_score` dupliziert JS-Formel — siehe Finding M-03. |
| `/api/set_profile` | POST | ja | app.js:1624, pip-launcher.js:869 | LIVE | OK. |
| `/api/launcher/init` | GET | ja | pip-launcher.js:103 | LIVE | Liefert profiles + skripte + opener. |
| `/api/launcher/profile/<pid>` | GET | ja | pip-launcher.js:512 | LIVE | OK. |
| `/api/set_phase` | POST | ja | — (vermutlich pip-launcher inline) | LIVE | **Keine Validation** — siehe H-20. |
| `/api/log_gegenargument_wahl` | POST | ja | app.js:832 | LIVE | OK. Primitiv. |
| `/api/frage` | POST | ja | app.js:877 | LIVE | **Bereits in H-12..H-15 dokumentiert.** |
| `/api/ewb_trigger` | POST | ja | app.js:317 | LIVE | **Bereits in H-12..H-15 dokumentiert.** |
| `/api/feedback` | POST | ja | app.js:1330, feedback.js:11 | LIVE | Ruft `log_learning_event`. Siehe M-04. |
| `/api/postcall_insights` | POST | ja | app.js:1091 | LIVE | **INLINE-ANTHROPIC + Silent-Swallow** — H-16. |
| `/api/skripte` | GET | ja | — | **ORPHAN** | Kein Frontend-Caller (nur Tests). H-17. |
| `/api/precall/research` | POST | ja | app.js:144, 1589, pip-launcher.js:311 | LIVE | OK. Fehler-Handling differenziert 400/502. |
| `/api/ewb/<id>/rate` | POST | ja | templates/session_detail.html:469 | LIVE | Strict `isinstance(value, bool)` sauber. Ownership-Check korrekt. OK. |

---

## Findings (Severity-sortiert)

### HIGH-16: `/api/postcall_insights` — Dritter inline-Anthropic-Client ohne Cost-Tracking + Silent-Swallow

**Evidence:** `app_routes.py:1322-1354`.

```python
client = _ant.Anthropic(api_key=ANTHROPIC_API_KEY)
msg    = client.messages.create(
    model='claude-haiku-4-5-20251001', max_tokens=300,
    messages=[{'role': 'user', 'content': prompt}]
)
...
except Exception as e:
    return jsonify({'ok': True, 'bullets': ['Keine Insights verfuegbar.', '', '']})
```

**Probleme — 3 auf einmal:**
1. **Inline `_ant.Anthropic` statt geteilter `claude_service.claude_client`** — selbes Muster wie H-12 fuer `/api/frage` und `/api/ewb_trigger`. **Erweitert H-12-Count von 2 auf 3 Inline-Clients, Hardcoded-Model-Count von 11 auf 12.**
2. **Kein `log_api_cost`** → Post-Call-Insights-Kosten fehlen im Founder-Cost-Dashboard. Jedes Call-Ende triggert einen unsichtbaren Haiku-Call.
3. **Silent-Swallow mit `{'ok': True, ...}`** — **jede** Exception (JSON-Parse-Error, API-Timeout, Rate-Limit, Malformed-Response) liefert `ok:true` + Platzhalter-Bullets. **Kein Logging**, keine Metric. User sieht im UI "Keine Insights verfuegbar." ohne Indiz ob Feature kaputt oder wirklich leer.

**Folge:** Feature degradiert unsichtbar. Kombination mit `claude-haiku-4-5-20251001` hardcoded = 3. Hardcoded-Instanz in einer Route.

**Fix-Aufwand:** ~1h — Client-Share + `log_api_cost(user_id=g.user.id, ...)` + Logger statt silent.

---

### HIGH-17: `/api/skripte` ist orphan — Duplikat zu `/api/launcher/*`

**Evidence:**
- `app_routes.py:1358-1380`: Route existiert mit org_id-JOIN-Security (T-06-01).
- `grep -r "api/skripte" static/` → 0 Treffer. Einziger Caller: `tests/test_ewb_rate_api.py` (indirekt via andere Tests).
- Phase 06.1 hat die Route gebaut. Phase 06.2+ hat auf `/api/launcher/init` (liefert `skripte`-Array inline) und `/api/launcher/profile/<pid>` umgestellt.
- `pip-launcher.js:103` + `:512` holt skripte via Launcher-Routes. Kein JS ruft mehr `/api/skripte`.

**Folge:** 22 Zeilen Dead Route. Security-Annotation T-06-01 ist korrekt, aber leer-wirkend weil niemand die Route ruft. Test-False-Green moeglich (wird geprueft aber nicht live genutzt).

**Fix-Aufwand:** 15 min. Route entfernen + Test-Referenzen pruefen + SUMMARY.md-Referenzen in Phase 06 ggf. markieren.

---

### HIGH-18: `api_postcall_insights` Prompt-Injection-Vektor

**Evidence:** `app_routes.py:1332-1340`:
```python
prompt = f"""...
Erkannte Einwaende ({len(einwaende)}): {', '.join(e.get('typ','?') for e in einwaende) or 'keine'}
Painpoints: {', '.join(p.get('text','') for p in painpoints) or 'keine'}
...
"""
```

`einwaende` und `painpoints` kommen direkt aus `request.get_json()` **ohne Validation**. Jeder Authenticated-User kann ueber das POST-Body Strings einschleusen die den System-Prompt abbrechen / neu instruieren. Klassischer f-String-Injection-Pattern.

**Entschaerft durch:**
- Login-Required (nur eigene Nutzer, nicht public).
- Kein Tool-Use, kein DB-Zugriff aus dem Prompt heraus → Angreifer kann maximal Bullets beeinflussen.

**Verschaerft durch:**
- Silent-Swallow (Finding H-16) macht es schwer Angriffe zu erkennen.

**Severity-Argument:** HIGH statt CRITICAL weil Blast-Radius begrenzt ist, aber Pattern-Mismatch zur restlichen Codebase (andere Prompt-Builder escaped Input).

**Fix-Aufwand:** 30 min — Whitelist-Sanitize der Felder (`re.sub(r'[^\w\s.-]', '', ...)[:200]`).

---

### HIGH-19: `api_beenden` TOCTOU auf `ewb_clicks`

**Evidence:** `app_routes.py:406` + `:564`:
```python
# Z.406
with ls.state_lock:
    ewb_clicks = list(ls.state.get('ewb_clicks', []))
...
# Z.563 (im FT-logging-Block)
with ls.state_lock:
    ft_session_id = ls.state.get('ft_session_id')
    buttons_pressed = len(ls.state.get('ewb_clicks') or [])
```

Zwischen Z.406 und Z.564 liegen **~160 Zeilen** mit DB-Commits, CRM-Export, Audit-Log, Postcall-Engine-Call. In der Zeit kann `ls.state['ewb_clicks']` **weitermutiert werden** (paralleler EWB-Trigger via `record_ewb_click`). → `einwaende_gesamt` (Z.434) und `buttons_pressed` (Z.564) **basieren auf unterschiedlichen Snapshots** desselben Arrays.

**Folge:** Session-Ende bei aktivem Letzten-Sekunden-EWB-Click → ConversationLog speichert n=5 Klicks, `FtCallSession.buttons_pressed` = 6. Discrepancy auf DB-Ebene, schwer debugbar weil beide aus derselben ls.state-Quelle geholt werden.

**Mitigation bereits vorhanden:** POLISH-38-Reconcile (Z.485-503) re-queried ObjectionEvent aus DB — das faengt die einwaende-Drift. Aber `buttons_pressed` bleibt auf zweitem Snapshot.

**Fix-Aufwand:** 15 min — `ewb_clicks` einmal am Anfang lesen, durchreichen.

---

### HIGH-20: `api_set_phase` keine Validation — Skript-Abdeckung korrumpierbar

**Evidence:** `app_routes.py:1081-1102`:
```python
data = request.get_json(force=True)
idx  = data.get('phase_index', 0)
phase_name = data.get('phase_name', str(idx))
...
with ls.phase_lock:
    ls.aktive_phase_idx = int(idx)
with ls.covered_phases_lock:
    ls.covered_phases.add(int(idx))
```

Akzeptiert:
- Negative Integers (`int(-5)` → covered_phases{-5})
- Integers > len(phasen) (`int(9999)` → covered_phases{9999})
- `None` / Strings → ValueError → 500 an User

**Folge am Session-Ende:**
`api_beenden:334` berechnet `abgedeckt_count / len(phasen_list) * 100`. Wenn covered_phases{0,1,9999,-5} und phasen_list hat 4 Eintraege → `abgedeckt_count = sum(i in cp for i in range(4)) = 2` (0 und 1) → 50% korrekt, glueck gehabt. ABER: die Korrumpierung wandert in `ls.phasen_log` (Z.1092) und via Z.451 in DB (`conv.phasen_details`) — Nudelcode-Vektor in FT-Daten.

**Fix-Aufwand:** 15 min — Range-Check gegen `len(pdata['phasen'])`.

---

### MEDIUM-01: `api_beenden` Riesen-Funktion — 420 Zeilen, 7 try/except-Bloecke

**Evidence:** Z.258-682.

- 3 separate Exception-Handler die `print(f"[...] Fehler: {e}")` schreiben (Z.363, 393, 503, 557, 580, 632, 645, 647). **Alle silent-swallowen**, Session-Ende laeuft weiter. Das ist bei CRM/Points/FT-Logging korrekt — bei `ConversationLog.add` + `db_conv.commit` (Z.647) nicht: **wenn DB-Commit failt, gibt es keinen 500 an User**, nur `postcall`-Objekt wird zurueckgegeben mit `conv_id=None`. Frontend zeigt PostCall-Screen, User denkt "gespeichert" — in Wahrheit **Datenverlust**.
- `saved_conv_id = None` bleibt bei DB-Fehler None → Points-Block (Z.597) + Post-Call-Engine (Z.634) arbeiten mit None → weitere silent failures kaskadieren.

**Fix-Aufwand:** 2-3h — Kritischen DB-Commit (ConversationLog) isoliert mit explicit 500-Response bei Fehler. Nur Nice-to-Have-Bloecke silent swallowen.

---

### MEDIUM-02: `_letzte_gemeldete_version` Dict — Memory-Leak ohne Eviction

**Evidence:** `app_routes.py:13-14`:
```python
_letzte_gemeldete_version = {}  # user_id -> last_version
_MAX_VERSION_CACHE = 500        # safety cap — clear whole dict if exceeded
```

Bei >500 gleichzeitigen Usern wird das gesamte Dict geleert (Z.159). Gut gegen OOM, schlecht fuer Log-Konsistenz — alle Polling-Requests melden `payload['version'] > 0` dann faelschlich als "Neues Ergebnis". 500 User ist fuer EA mit 50 Plaetzen kein Problem, aber bei Wachstum ein Wartezeit-Bomb.

**Fix-Aufwand:** 30 min — LRU mit `functools.lru_cache`-aehnlicher Struktur oder `OrderedDict.popitem(last=False)`.

---

### MEDIUM-03: `_calc_call_score` Server-JS-Formel-Duplikat

**Evidence:** `app_routes.py:690-700` — Kommentar sagt "Spiegelung der client-seitigen `_calcScore()`-Formel in pip-launcher.js". 2 Source-of-Truth fuer Score-Berechnung. Drift unvermeidbar bei Aenderung nur einseitig. Selbes Anti-Pattern wie `profile_migration.TABU_DEFAULT_PAIRS` vs `profile_editor.js:131` (MEDIUM-Liste MASTER-AUDIT).

**Fix-Aufwand:** 1-2h — Formel nur einmal berechnen (Server-Side) und via Payload ausliefern, JS-Kopie entfernen.

---

### MEDIUM-04: `/api/feedback` fehlt `log_action` fuer Audit

**Evidence:** `app_routes.py:1275-1319`. Ruft `log_learning_event` (Z.1309) aber **kein `audit.log_action('feedback', ...)`**. MASTER-AUDIT H-8 Liste der 6 geloggten Action-Types enthaelt "feedback" — Evidenz passt nicht. **Claudian hat sich geirrt** oder Dispatch laeuft indirekt?

Grep nach `log_action.*feedback` in routes/:
- `app_routes.py`: 0 Treffer fuer feedback-Audit-Call
- `routes/feedback.py` (separate Blueprint, 67 Z.): zu pruefen ob DORT geloggt wird

→ Wahrscheinlich **Audit-Coverage-Gap zusaetzlich zu H-8**, nicht im MASTER-AUDIT gezaehlt.

**Fix-Aufwand:** 15 min falls confirmed — `log_action(db, g.user.id, g.org.id, 'feedback', target_type='feedback_event', target_id=fb.id, details={'stars': stars}, request=request)` nach Commit.

---

### MEDIUM-05: `api_feedback` kein Rollback bei Constraint-Violation

**Evidence:** `app_routes.py:1287-1300`:
```python
fb = FeedbackEvent(...)
db.add(fb)
...
latest.sterne = int(stars)
latest.kommentar = comment
db.commit()
```

Kein `try/except SQLAlchemyError: db.rollback()`. Bei Constraint-Violation (z.B. session_log_id > 255 Chars bei String-Column) crasht der Request mit 500 und die halb-geschriebene Transaction bleibt offen bis Session-Close. **MASTER-AUDIT-Medium-Punkt `create_feedback` ohne Rollback** trifft auch hier zu (zwei Routes, beide Muster).

**Fix-Aufwand:** 15 min.

---

### MEDIUM-06: `api_postcall_insights` akzeptiert unvalidierte Typen

**Evidence:** `app_routes.py:1328-1331`:
```python
einwaende = data.get('einwaende', [])
painpoints = data.get('painpoints', [])
kb_start  = data.get('kb_start', 30)
kb_end    = data.get('kb_end', 30)
```

Wenn `kb_start` oder `kb_end` ein String oder dict ist → f-String-Interpolation akzeptiert alles, aber Prompt wird potentiell 10kb gross. Rate-Limit/Cost-Explosion per Request trivial.

**Fix-Aufwand:** 15 min zusammen mit H-18.

---

### LOW-01: 3 Orphan-Routes (`/api/swap_roles`, `/api/status`, `/api/keepalive`)

Keine Frontend-Caller gefunden. Moegliches Dead-Code. Evtl. Admin-Tool oder Legacy-Reste. Entscheidung: loeschen oder behalten.

**Fix-Aufwand:** 30 min Entscheidung + Cleanup.

---

### LOW-02: Doppelte `import json as _json` im selben Funktions-Body

Z.98, 104, 110 in `/live`. Z.990 in `api_set_profile`. Z.1022 in `api_launcher_init`. Kosmetik, aber Noise-Indikator fuer fehlende Refactor-Disziplin.

---

### LOW-03: `api_beenden` mischt `datetime.now()` und `int(_time.monotonic() - _st)`

Z.307 nutzt `monotonic` fuer Dauer (korrekt), Z.414 nutzt `datetime.now()` als "approximation fuer Start-Zeit". Kommentar Z.414 selbstkritisch: "real start tracked via session_start_time". Kleine Datenungenauigkeit in `started_at`-Column.

---

## Cross-Module-Hypothesen

### CH-01: Hardcoded-Model-Count jetzt 12, nicht 11

**Evidence:** MASTER-AUDIT H-12 zaehlt 11 Instanzen (9 in claude_service + 2 in app_routes.py `/api/frage` + `/api/ewb_trigger`). **Uebersehen:** `app_routes.py:1344` in `api_postcall_insights` = 12. Bei Model-Upgrade (Haiku 4.5 → 4.6) muessen 12 Zeilen editiert werden.

**Empfehlung fuer Block 2 (Dead-Code + Struktur):** Konstante `CLAUDE_HAIKU_MODEL` in config.py + 12 Usages migrieren. 30 min Arbeit, verhindert Wochen spaetere Abriebe.

---

### CH-02: `/api/postcall_insights` + `run_postcall_engine` + `generate_postcall_analysis` — 3 verschiedene PostCall-LLM-Pfade

Im Session-Ende-Flow laufen:
1. **`api_beenden` Z.634** → `run_postcall_engine` (DB-Events + Muster).
2. **`api_beenden` Z.595+** (vermutet, nicht in gelesenem Bereich) → async `generate_postcall_analysis` via Sonnet (siehe MASTER-AUDIT H-6 — profil-blind).
3. **`api_postcall_insights`** — separater Frontend-Call nach Session-Ende, Haiku generiert 3 Bullets (siehe H-16).

Keine der drei kennt die jeweils andere. Potential fuer Konsolidierung — heute 3 separate LLM-Roundtrips pro PostCall (Haiku Bullets + Sonnet Analyse + Engine-Events). **Cost-Impact und User-Wait-Time:** 3x API-Latenz.

**Empfehlung fuer Profil-Redesign-Phase:** PostCall-Pipeline konsolidieren.

---

### CH-03: Polling + SocketIO = 2 Push-Paths fuer State

`/api/ergebnis` wird im Polling-Loop von app.js:780 alle paar Sekunden abgefragt. Gleichzeitig liefert SocketIO (`deepgram_service.py`) Live-Updates. Beide beschreiben denselben `ls.state`. **Konsistenz nicht verifiziert.** Mindestens eines muesste primary/authoritative sein — nicht dokumentiert welches.

**Relevanz fuer Nudelcode-Praevention:** Klassisches Dual-Source-Muster das in spaeteren Phasen fuer Mysterien sorgt ("warum zeigt UI einen Wert und API einen anderen?").

---

### CH-04: `ls.state.get('session_anrede')` — Writer verifizieren

`api_beenden:420` liest `session_anrede` fuer `ConversationLog.anrede`. Kommentar behauptet "gesetzt in deepgram_service.py handle_start_live_session bei whitelist-Werten 'Du'|'Sie'". Nicht in diesem Audit verifiziert, aber Kandidat fuer naechstes Welle-3-Scan in `deepgram_service.py` (bereits Welle-1 Fokus).

---

### CH-05: `ObjectionEvent` vs `FtObjectionEvent` Parallelismus

`api_beenden:466` schreibt `ObjectionEvent`-Rows aus `ewb_clicks`.
`api_ewb_trigger:1250` schreibt parallel `FtObjectionEvent`-Rows beim EWB-Klick (live, nicht Session-Ende).

**Zwei Tabellen fuer dasselbe konzeptuelle Event.** ObjectionEvent = User-Facing (ownership, Dashboard-Aggregate), FtObjectionEvent = FT-Trainingsdaten. Schema-OK per Design, aber **Duplicate-Log-Risiko** bestaetigt H-14 aus MASTER-AUDIT. Beide Pfade koennen bei Bug divergieren — POLISH-38-Reconcile (Z.485) aggregiert ObjectionEvent, nicht FtObjectionEvent. FT-Training-Daten waren stale wenn POLISH-38 Korrektur notwendig war.

---

## Prioritaetsvorschlag fuer Fixes

**In Block 1 (Launch-Blocker) aufnehmen:**
- H-16 (+H-12-Erweiterung): Inline-Anthropic-Clients konsolidieren inkl. `/api/postcall_insights` — +30 min zum bestehenden H-12-Budget.
- H-18: Prompt-Injection-Sanitize in `postcall_insights` — 30 min.

**In Block 2 (Dead-Code-Prune) aufnehmen:**
- H-17: `/api/skripte` loeschen — 15 min.
- LOW-01: 3 Orphan-Routes entscheiden — 30 min.
- CH-01: Hardcoded-Model-Konstante extrahieren (12 Stellen) — 30 min.

**Neue Candidaten fuer Block 2:**
- H-19: `api_beenden` TOCTOU-Fix — 15 min.
- H-20: `api_set_phase` Validation — 15 min.
- M-04: `/api/feedback` Audit-Event — 15 min.
- M-05: Rollback in `api_feedback` — 15 min.

**Gesamt-Budget-Impact auf MASTER-AUDIT:** +~3-4h fuer HIGH-Fixes, +~1h fuer MEDIUM.

---

## Datei-Gesundheit

| Dimension | Status | Kommentar |
|---|---|---|
| Auth-Coverage | GRUEN | Alle 20 Routes `@login_required`. |
| CSRF | ORANGE | Kein CSRF-Token, wie in ganzer Codebase. |
| Cost-Tracking | ROT | 3 inline-LLM-Calls ohne Hook. |
| Exception-Handling | ROT | 7+ silent-swallows in api_beenden allein, 1 in postcall_insights. |
| Schema-Validation | ROT | set_phase + postcall_insights + ewb_trigger akzeptieren untypisierte Eingaben. |
| Dead-Routes | ORANGE | 4 Orphan-Kandidaten (api/skripte, api/status, api/swap_roles, api/keepalive). |
| SocketIO-Emits | GRAU | Keine in dieser Datei. Parallel zu Polling — CH-03. |
| Test-Coverage | UNGEPRUEFT | Nur api/ewb/rate direkt in tests/test_ewb_rate_api.py gesehen. |

---

*Ende Deep-Dive app_routes.py. Stand: 2026-04-24.*
