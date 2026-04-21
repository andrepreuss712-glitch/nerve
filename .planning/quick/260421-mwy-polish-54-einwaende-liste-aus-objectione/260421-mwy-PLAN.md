---
phase: quick-260421-mwy
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - routes/app_routes.py
autonomous: true
requirements:
  - POLISH-54
user_setup: []

must_haves:
  truths:
    - "Cold-Call Session mit 3 EWB-Klicks: PiP-Postcall-Kachel 'Einwände' zeigt '3' (nicht '–')"
    - "Session-Detail-Page zeigt weiterhin die korrekte ObjectionEvent-Count (keine Regression zu 29c8b71)"
    - "Meeting-Call mit Analyse-Einwänden + optionalen EWB-Klicks zeigt gemergte Zahl ohne Duplikate"
    - "`postcall['einwaende']` ist eine Liste von Dicts mit ASCII-dict-keys (typ, zitat, intensitaet, ts)"
    - "CRM-Export-Pfad und run_postcall_engine-Pfad bleiben unverändert (additiv: nur Payload wird angereichert)"
  artifacts:
    - path: "routes/app_routes.py"
      provides: "Merge-Block der ObjectionEvent-Rows in postcall['einwaende'] nach dem POLISH-38-Counter-Reconcile"
      contains: "ObjectionEvent merge nach Counter-Reconcile"
  key_links:
    - from: "routes/app_routes.py /api/beenden"
      to: "postcall['einwaende']"
      via: "DB-Query auf ObjectionEvent + Merge mit log_entries-Analyse-Einwänden"
      pattern: "ObjectionEvent.*conversation_log_id == conv.id"
    - from: "postcall['einwaende']"
      to: "pip-launcher.js:1881 einwTotal"
      via: "Flask JSON-Response -> Frontend postcall-Rendering"
      pattern: "postcall && postcall.einwaende"
---

<objective>
POLISH-54: `postcall['einwaende']` wird im Cold-Call-Modus nach Phase 06.3-Entkoppelung
leer an den Client zurückgegeben, weil `einwaende_liste` nur aus `log_entries`
mit `type=='analyse' AND einwand=True` gebaut wird — und Cold Call hat keinen
Analyse-Loop mehr. Frontend (`pip-launcher.js:1881`) liest die Länge und zeigt
"–" (em-dash) in der Postcall-Kachel "Einwände".

Purpose: Cold-Call-User sehen korrekte Einwand-Zahl im Postcall-Overlay, nicht
"–" trotz dokumentierter ObjectionEvents. Fix stellt Vertrauen in die Post-Call-
Auswertung wieder her und ist konsistent mit POLISH-29 ("EWB-Button gedrückt =
Einwand behandelt"). Analog zu 29c8b71 (POLISH-38 Counter-Reconcile): DB-Truth
wird autoritative Quelle.

Output: `routes/app_routes.py` wird erweitert um einen Merge-Block NACH dem
POLISH-38-Counter-Reconcile, der ObjectionEvent-Rows in `postcall['einwaende']`
additiv einfügt (mit Dedup gegen existierende log_entries-Einwände für Meeting-
Kompatibilität).
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@./CLAUDE.md
@.planning/backlog.md

# Recon-Findings (embedded — Executor muss NICHT nochmal greppen)

## Aktueller Code in routes/app_routes.py

### Z.305-313: `einwaende_liste`-Build (nur Analyse-Loop, Cold Call leer)

```python
einwaende_liste = []
kaufsignale_liste = []
for e in log_entries:
    if e['type'] == 'analyse' and e.get('data', {}).get('einwand'):
        d = e['data']
        einwaende_liste.append({
            'typ': d.get('typ', '?'), 'intensitaet': d.get('intensitaet', '?'),
            'zitat': d.get('einwand_zitat', ''), 'ts': e.get('ts', ''),
        })
    if e['type'] == 'tipp' and e.get('kategorie') == 'signal':
        kaufsignale_liste.append({'text': e.get('text', ''), 'ts': e.get('ts', '')})
```

### Z.335-345: Wie `einwaende_liste` in `postcall` landet

```python
postcall = {
    'einwaende': einwaende_liste,   # <-- Frontend liest .length hier
    ...
}
```

### Z.402-403: `ewb_clicks` aus live_session.state

```python
with ls.state_lock:
    ewb_clicks = list(ls.state.get('ewb_clicks', []))
```

### Z.450-462: ObjectionEvent-Bulk-Insert (passiert NACH Z.305 Build, VOR Merge-Block)

```python
from database.models import ObjectionEvent
for click in ewb_clicks:
    db_conv.add(ObjectionEvent(
        user_id=g.user.id, org_id=g.org.id,
        conversation_log_id=conv.id,
        einwand_typ=click['einwand_typ'],
        success=click['success'],
    ))
if ewb_clicks:
    db_conv.commit()
```

### Z.464-488: POLISH-38 Counter-Reconcile (Referenz-Pattern für unseren Merge)

```python
# POLISH-38 (Haupt-Fix): Re-aggregate counters from ObjectionEvent (authoritative source).
try:
    from sqlalchemy import func as _sqlfunc, case as _sqlcase
    _agg = (
        db_conv.query(
            _sqlfunc.count(ObjectionEvent.id),
            _sqlfunc.sum(_sqlcase((ObjectionEvent.success == True, 1), else_=0)),
        )
        .filter(ObjectionEvent.conversation_log_id == conv.id)
        .one()
    )
    _total = int(_agg[0] or 0)
    _ok = int(_agg[1] or 0)
    if _total > 0 and (conv.einwaende_gesamt != _total or conv.einwaende_behandelt != _ok):
        conv.einwaende_gesamt = _total
        conv.einwaende_behandelt = _ok
        db_conv.commit()
        print(f"[POLISH-38] counters reconciled conv.id={conv.id} gesamt={_total} behandelt={_ok}")
except Exception as _reconcile_err:
    print(f"[POLISH-38] counter reconcile fehlgeschlagen (conv.id={conv.id}): {_reconcile_err}")
```

## database/models.py Z.342-350: ObjectionEvent-Schema

```python
class ObjectionEvent(Base):
    __tablename__ = 'objection_events'
    id                  = Column(Integer, primary_key=True)
    user_id             = Column(Integer, ForeignKey('users.id'), nullable=False)
    org_id              = Column(Integer, ForeignKey('organisations.id'), nullable=True)
    conversation_log_id = Column(Integer, ForeignKey('conversation_logs.id'), nullable=False)
    einwand_typ         = Column(String(100), nullable=False)
    success             = Column(Boolean, default=False, nullable=False)
    created_at          = Column(DateTime, default=utcnow, nullable=False)
```

**WICHTIG:** Das Schema hat KEIN `text`/`zitat`/`intensitaet`-Feld. Merge-Entries
müssen diese Felder mit Defaults füllen: `zitat=""` (leerer String),
`intensitaet="mittel"` (Default).

## Konsumenten von `postcall['einwaende']` (Frontend)

### static/pip-launcher.js:1881 (Postcall-Empty-Guard + Kachel-Count)

```javascript
var einwTotal = ((postcall && postcall.einwaende) || []).length;
// ... zeigt einwTotal als Zahl in der Postcall-Kachel
// Wenn einwTotal === 0: Kachel zeigt "–" (em-dash)
```

### Keine Regression:
- Session-Detail liest ObjectionEvent-Rows direkt aus DB (nicht `einwaende_liste`).
- Frontend erwartet Array mit `.length` — Dict-Content wird nicht ausgewertet
  (Kachel zeigt nur die Zahl).

## live_session.py Z.108-111: ewb_clicks Runtime-State-Format

```python
'ewb_clicks': [],  # Liste von dicts: {'einwand_typ': str, 'success': bool, 'ts': iso}
```

# Umlaut-Regel (CLAUDE.md)

Dict-keys MÜSSEN ASCII sein (`einwaende`, `zitat`, `intensitaet`, `typ`, `ts`) —
User-facing Text-Values dürfen Umlaute enthalten. Unsere Entries haben leere
Strings als `zitat` (kein User-Content), also kein Umlaut-Edge-Case.

# Reihenfolge-Constraint

ObjectionEvent-Bulk-Insert (Z.450-462) muss VOR unserem Merge-Block passieren —
sonst sind die Events noch nicht in der DB queryable. POLISH-38-Reconcile-Block
(Z.464-488) demonstriert dasselbe Pattern → wir platzieren DANACH.

Wichtig: `run_postcall_engine` (Z.567-575) und CRM-Export (Z.349-357) lesen
die lokale `einwaende_liste`-Variable (NICHT `postcall['einwaende']`). Wir
dürfen also `postcall['einwaende']` überschreiben OHNE dass sich CRM oder
Engine-Pfad ändert. Das ist additiv und regression-sicher.

`ls.last_postcall` wird bei Z.585 aus `postcall` gebaut — unser Überschreiben
VOR Z.585 propagiert also auch in den Postcall-Snapshot.
</context>

<tasks>

<task type="auto">
  <name>Task 1: Merge ObjectionEvent-Rows in postcall['einwaende'] nach POLISH-38-Reconcile</name>
  <files>routes/app_routes.py</files>
  <action>
In `routes/app_routes.py` direkt NACH dem POLISH-38-Counter-Reconcile-Block (nach dem `except Exception as _reconcile_err`-Handler bei ca. Z.488, VOR dem "FT logging"-Block) einen neuen Merge-Block einfügen.

**Struktur des neuen Blocks** (Pseudo-Code, exakte Syntax im Impl):

```python
# POLISH-54: Merge ObjectionEvent-Rows in postcall['einwaende'] so dass Cold-Call
# (kein Analyse-Loop seit Phase 06.3) nicht "–" in der Postcall-Kachel zeigt.
# Analog zu POLISH-38-Reconcile oben: DB ist Single Source of Truth.
# Additiv: existierende einwaende_liste (aus log_entries, Meeting-Analyse-Loop)
# bleibt erhalten, ObjectionEvent-Rows werden gemergt mit Dedup (typ+ts-Bucket).
# CRM (Z.~350) und run_postcall_engine (Z.~572) lesen die LOKALE einwaende_liste-
# Variable — nicht postcall['einwaende'] — und sind daher regression-sicher.
try:
    _oe_rows = (
        db_conv.query(ObjectionEvent)
        .filter(ObjectionEvent.conversation_log_id == conv.id)
        .order_by(ObjectionEvent.created_at.asc())
        .all()
    )
    if _oe_rows:
        # Baue Dedup-Set aus existierenden einwaende_liste-Entries.
        # Key = (typ_lower, ts_bucket_5s) — Bucket-Floor auf 5s-Fenster.
        import time as _t_polish54
        from datetime import datetime as _dt_polish54
        def _ts_bucket(iso_str):
            if not iso_str:
                return None
            try:
                # Deutliches Try-Set: unterstütze ISO mit/ohne Z/Offset
                s = iso_str.replace('Z', '+00:00') if iso_str.endswith('Z') else iso_str
                dt = _dt_polish54.fromisoformat(s)
                return int(dt.timestamp() // 5) * 5
            except Exception:
                return None
        _seen = set()
        for _ex in (postcall.get('einwaende') or []):
            _key = ((_ex.get('typ') or '').lower(), _ts_bucket(_ex.get('ts') or ''))
            if _key[0]:
                _seen.add(_key)
        # Merge ObjectionEvent-Entries (Dedup gegen existierende).
        _merged_from_oe = 0
        _new_entries = []
        for _oe in _oe_rows:
            _typ = (_oe.einwand_typ or '').strip()
            if not _typ:
                continue
            _iso = _oe.created_at.isoformat() if _oe.created_at else ''
            _key = (_typ.lower(), _ts_bucket(_iso))
            if _key in _seen:
                continue
            _seen.add(_key)
            _new_entries.append({
                'typ': _typ,
                'zitat': '',           # ObjectionEvent hat keinen Quote-Text (Schema-limitation)
                'intensitaet': 'mittel',  # Default (ObjectionEvent tracked keine Intensität)
                'ts': _iso,
            })
            _merged_from_oe += 1
        if _new_entries:
            # Überschreibe postcall['einwaende'] (NICHT die lokale einwaende_liste-
            # Variable — CRM und run_postcall_engine bleiben unangetastet).
            postcall['einwaende'] = list(postcall.get('einwaende') or []) + _new_entries
            print(f"[POLISH-54] einwaende merged from ObjectionEvent conv.id={conv.id} added={_merged_from_oe} total={len(postcall['einwaende'])}")
except Exception as _polish54_err:
    print(f"[POLISH-54] merge ObjectionEvent->postcall.einwaende fehlgeschlagen (conv.id={conv.id}): {_polish54_err}")
```

**Exakte Platzierung:**
- Der Block muss INNERHALB des outer `try:` bei Z.412 platziert werden (damit `conv` und `db_conv` in Scope sind).
- Direkt nach dem `except Exception as _reconcile_err: print(...)` bei Z.488.
- VOR dem Kommentar `# FT logging: update ft_call_sessions with aggregates (Phase 04.7.1)` bei Z.490.

**Umlaut-Regel (CLAUDE.md):**
- Dict-keys `'typ'`, `'zitat'`, `'intensitaet'`, `'ts'` sind ASCII — korrekt.
- Value-Strings sind leer oder `'mittel'` — kein Umlaut-Issue.
- `ObjectionEvent.einwand_typ` ist Content aus DB — kann Umlaute enthalten aber wird als Value übergeben, nicht als Key. Regel ist erfüllt.

**Konsistenz mit POLISH-38-Pattern:**
- Defensive `try/except` um den gesamten Block (DB-Fehler crashen /api/beenden nicht).
- Logging mit `[POLISH-54]`-Tag analog zu `[POLISH-38]`.
- `if _new_entries:`-Guard verhindert Print-Noise bei no-op (Meeting-Session ohne EWB-Klicks).

**Was NICHT geändert werden darf:**
- Die lokale `einwaende_liste`-Variable (Z.305-313 Build) bleibt unangetastet.
- Z.352 (`generate_crm_export(..., einwaende_liste, ...)`) bleibt unverändert.
- Z.572 (`run_postcall_engine(..., einwaende=einwaende_liste, ...)`) bleibt unverändert.
- Frontend-Code (`pip-launcher.js`) wird NICHT modifiziert.
- Keine DB-Schema-Änderung, keine Migration.

**Warum Option B (DB-Truth) statt Option A (Memory-ewb_clicks):**
1. Konsistenz mit 29c8b71 POLISH-38-Pattern — DB bleibt Single Source of Truth.
2. Falls ObjectionEvents aus anderen Quellen persistiert werden (zukünftige Pfade), werden sie automatisch gemergt.
3. Minimal zusätzlicher DB-Roundtrip (1 SELECT nach bereits bestehendem Bulk-Insert-Commit) — vernachlässigbar im /api/beenden-Flow.

**Self-check vor Commit:**
1. Grep `POLISH-54` in der Datei — sollte exakt 1 Block zeigen (der neue Merge-Block).
2. Grep `einwaende_liste` in der Datei — sollte unverändert 4 Hits zeigen (Build Z.305, Build Z.310, Assign Z.336, CRM Z.352, Engine Z.572) — also 5 Hits; NICHT reduziert.
3. Grep `postcall['einwaende']` — sollte 2 Hits zeigen: Z.336 (Initial-Assign) + neuer Block (Overwrite).
4. Syntax-Check: `python -c "import ast; ast.parse(open('routes/app_routes.py').read())"` — kein SyntaxError.
  </action>
  <verify>
    <automated>python -c "import ast; ast.parse(open('routes/app_routes.py').read()); print('[OK] syntax valid')"</automated>
    <manual>
Grep-Verifikation:

1. `POLISH-54`-Marker existiert exakt 1x als Kommentar + 1x als Log-Print:
   ```bash
   grep -c "POLISH-54" routes/app_routes.py  # sollte >= 2 sein
   ```

2. Merge-Block ist INSIDE des `db_conv`-try-blocks (nach POLISH-38-Reconcile, vor FT-logging):
   ```bash
   grep -n "POLISH-54" routes/app_routes.py
   # erste Zeile sollte > Z.488 ([POLISH-38] counter reconciled) sein
   # und < Z.490 (# FT logging: update ft_call_sessions)
   ```

3. Keine Regression am bestehenden Code:
   ```bash
   grep -c "einwaende_liste" routes/app_routes.py
   # sollte unverändert 5 Hits sein (Z.305, Z.310, Z.336, Z.352, Z.572)
   ```

4. End-to-End Smoke-Test (falls lokale DB verfügbar):
   - Cold-Call-Session mit 3 EWB-Klicks starten → beenden
   - Browser-DevTools Network-Tab: `/api/beenden`-Response inspizieren
   - `response.postcall.einwaende` sollte ein Array mit 3 Entries sein (nicht leer)
   - Jede Entry hat `typ` (String), `zitat` (String, evtl. leer), `intensitaet` (String),
     `ts` (ISO-String)
   - PiP-Postcall-Kachel zeigt `3`, nicht `–`

5. Meeting-Session-Regression-Check (falls testbar):
   - Meeting-Session mit Analyse-Einwand + EWB-Klick mit demselben Typ innerhalb 5s
   - Nur 1 Entry im Array (Dedup greift)
   - Bei 10s+ Abstand: 2 Entries (kein false-positive Dedup)
    </manual>
  </verify>
  <done>
- Neuer Merge-Block existiert in `routes/app_routes.py` nach POLISH-38-Reconcile.
- Block ist defensiv (try/except) und logged `[POLISH-54]`-prefix.
- Lokale `einwaende_liste`-Variable, CRM-Pfad, Engine-Pfad unverändert.
- `postcall['einwaende']` enthält additiv die ObjectionEvent-Entries mit ASCII dict-keys.
- Python-Syntax validiert erfolgreich.
- Cold-Call mit N EWB-Klicks: Postcall-Payload zeigt N Einwände im Array.
  </done>
</task>

</tasks>

<verification>
## Gesamt-Phase-Check

1. **Code-Syntax:**
   ```bash
   python -c "import ast; ast.parse(open('routes/app_routes.py').read()); print('OK')"
   ```

2. **Import-Check** (sicherstellen, dass kein neuer Import außerhalb des Merge-Blocks
   fehlt — alle Imports sind inline-local im Block, analog POLISH-38):
   ```bash
   grep -n "^from database.models import ObjectionEvent" routes/app_routes.py
   # 452 (Bulk-Insert) — nach unserem Block nicht nötig, weil lokaler Import
   ```

3. **End-to-End (Manual UAT):**
   - Cold Call starten → 3x EWB klicken → "Beenden" klicken
   - Postcall-Overlay: Kachel "Einwände" zeigt `3`, nicht `–`
   - Session-Detail-Page (via `/analytics` → Session-Link): zeigt unverändert 3/3

4. **Meeting-Regression-Check:**
   - Meeting-Session mit 2 Analyse-Einwänden (via Analyse-Loop erkannt) ohne EWB-Klick
   - Postcall zeigt `2` (aus log_entries-Pfad — Pfad unverändert, ObjectionEvent leer)

5. **Log-Inspektion:**
   ```bash
   tail -f nerve.log | grep POLISH-54
   # erwarte: "[POLISH-54] einwaende merged from ObjectionEvent conv.id=<N> added=<M> total=<M>"
   # bei Cold-Call mit EWB-Klicks
   ```
</verification>

<success_criteria>
- [ ] `routes/app_routes.py` enthält POLISH-54-Merge-Block nach POLISH-38-Reconcile
- [ ] Python-Syntax ist valide (`ast.parse` ok)
- [ ] Cold-Call mit N EWB-Klicks: `postcall.einwaende.length === N` im Response
- [ ] PiP-Postcall-Kachel "Einwände" zeigt N statt `–`
- [ ] Session-Detail zeigt weiterhin korrekte Zahl (29c8b71 Regression-Check)
- [ ] Meeting-Session mit Analyse-Einwänden zeigt unveränderte Zahl (additiv, Regression-frei)
- [ ] Dict-keys sind ASCII (Umlaut-Regel CLAUDE.md)
- [ ] Keine Änderung an CRM-Export oder run_postcall_engine-Input
- [ ] Atomic commit: `fix(POLISH-54): aggregate einwaende_liste from ObjectionEvent for cold-call postcall`
- [ ] `git push origin main` erfolgreich
</success_criteria>

<output>
After completion, create `.planning/quick/260421-mwy-polish-54-einwaende-liste-aus-objectione/260421-mwy-SUMMARY.md`
with:
- Commit-SHA
- Recon-Ergebnis (dass exakte Zeilen-Nummern übereinstimmten)
- Verifikations-Artefakte (grep-Counts, Syntax-OK)
- Offene Follow-ups (falls Meeting-Mode UAT nicht möglich)
</output>
