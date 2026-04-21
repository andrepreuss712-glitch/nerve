---
quick_task: 260421-lpx
type: execute
wave: 1
depends_on: []
files_modified:
  - scripts/migrate_polish_38_counters.py
  - routes/app_routes.py
autonomous: true
requirements:
  - POLISH-38
  - POLISH-29
tags: [polish-38, einwaende-counter, objection-events, migration, central-point-fix]
---

<objective>
POLISH-38 Haupt-Bug fix: `ConversationLog.einwaende_gesamt` und `einwaende_behandelt`
werden zuverlaessig aus der ObjectionEvent-Tabelle abgeleitet (Single-Source-of-Truth),
nicht aus fluechtigen In-Memory-Listen.

**Problem:** Commit `cf38589` aenderte `einwaende_gesamt=len(ewb_clicks)` (korrekt),
aber UAT zeigt weiterhin Counter=0. Zwei Root-Causes identifiziert:

1. **Falsche Quelle fuer `einwaende_behandelt`:** Zeile 423 in `routes/app_routes.py`
   berechnet `einwaende_behandelt=len([x for x in ga_details if x.get('erfolgreich') is True])`.
   `ga_details` kommt aus `ls.gegenargument_log`, das vom AI-analyse_loop befuellt wird —
   Cold-Call hat keine Analyse, also ist `ga_details` leer, egal wie viele EWB-Klicks
   passierten. POLISH-29 User-Definition: "EWB-Button gedrueckt = Einwand behandelt"
   (success-Flag auf ObjectionEvent, nicht AI-Erfolg). `einwaende_behandelt` muss aus
   `ObjectionEvent.success=True`-Rows abgeleitet werden.

2. **Potentielle Stale-List-Risiken bei `ewb_clicks`:** Der `cf38589`-Fix liest
   `ls.state['ewb_clicks']` vor dem ConversationLog-Insert — aber ist anfaellig
   gegen jede zukuenftige Race-Condition oder State-Reset-Reihenfolge-Aenderung.
   Zuverlaessigste Quelle ist die DB-Tabelle `objection_events` selbst (sie wird
   direkt nach dem ConversationLog-Insert committed, Line 454-460).

**Fix-Strategie — Central-Point-Fix in `/api/beenden`:**
Nach dem ObjectionEvent-Bulk-Insert (Zeile 461-462) werden die Counter aus der DB
re-aggregiert und auf die `conv`-Row geschrieben. Der bestehende `cf38589`-Fix bleibt
als defensiver Fallback erhalten (falls aus irgendeinem Grund 0 ObjectionEvents
committed wurden, wird der Initial-Wert aus `len(ewb_clicks)` nicht ueberschrieben).

**Warum NICHT `record_ewb_click`-Central-Point-Fix (user's first suggestion):**
Recon hat ergeben: `ConversationLog` wird NICHT bei `start_live_session` erzeugt —
sondern erst in `/api/beenden`. Es gibt waehrend der Live-Session kein `conv`-Row,
das man inkrementieren koennte. `ls.state['log_id']` existiert nicht. Der User-Hinweis
"(Normalerweise: ConversationLog wird bei start_live_session erstellt...)" ist in
diesem Codebase nicht zutreffend. Der Re-Aggregate-am-Ende-Fix liefert dieselbe
Semantik ("authoritative Quelle = DB"), ohne den Session-Lifecycle umzubauen.

**Migration (optional, aber hier sinnvoll):** Ein `scripts/migrate_polish_38_counters.py`-
Script, das alle bestehenden `ConversationLog`-Rows mit Counter=0 (oder Mismatch)
basierend auf ihren `ObjectionEvent`-Rows korrigiert. Idempotent (setzt nur wenn
Mismatch). Lokal + VPS-deploybar.

Purpose: Counter-Metriken der Session-Detail-Seite zeigen korrekte Werte nach Cold-Call-
Sessions. User-Vertrauen in Session-Erfassung wiederhergestellt.
Output: Migration-Script + Code-Fix in `/api/beenden`. 3 Commits, letzter mit Push.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
</execution_context>

<context>
@./CLAUDE.md
@.planning/STATE.md
@.planning/backlog.md

<recon_findings>
**All EWB-Klick Creation-Sites (2 Pfade):**

1. **Socket.IO `manual_ewb` (PiP-Pfad):** `services/deepgram_service.py:400-456`
   — `@sio.on('manual_ewb')` → `sio.start_background_task(_run)` → nach Spawn
   `ls.record_ewb_click(typ, success=_ewb_success)`. POLISH-38.1 hat `success=True`
   bei erfolgreichem Spawn gesetzt (Commit 585f567). Keine direkte DB-Operation;
   nur In-Memory-Append an `ls.state['ewb_clicks']`.

2. **HTTP `POST /api/ewb_trigger` (Live-Assistant-Pfad):** `routes/app_routes.py:1064-1172`
   — Nach erfolgreichem Haiku-Gegenargument: `record_ewb_click(einwand_typ=einwand_typ, success=False)`
   (Zeile 1135). Zusaetzlich `FtObjectionEvent`-Insert fuer FineTuning-Logging
   (Zeile 1150, **andere Tabelle**). Keine `ObjectionEvent`-Tabelle-Write hier —
   auch nur In-Memory-Append.

**Das bedeutet:** `ObjectionEvent`-Rows werden NUR von `/api/beenden` aus der
`ewb_clicks`-Liste erzeugt (Zeile 453-462). Es gibt genau EINE Creation-Site
fuer `ObjectionEvent`-Rows — der Bulk-Insert nach ConversationLog-Commit.

**`ConversationLog.einwaende_gesamt` Lesestellen (Auditor: Counter-Konsumenten):**
- `routes/app_routes.py:497` → `conv.einwaende_gesamt` als Audit-Log-Field
- `routes/app_routes.py:595` → `_calc_call_score()` Formel
- `routes/dashboard.py:177/259/369/469/950` → Aggregation fuer History-Seiten
- `services/coaching_service.py:418`, `services/customer_success_service.py:36`,
  `routes/performance.py:113` → diverse Auswertungen
- `templates/session_detail.html:81/133` → Session-Detail-Anzeige
→ Alle Konsumenten profitieren automatisch vom Fix (sie lesen den Counter erst NACH
`/api/beenden`-Commit).

**`einwaende_behandelt` — aktuelle Quelle:**
- `routes/app_routes.py:423` — `len([x for x in ga_details if x.get('erfolgreich') is True])`
- `ga_details` = `list(ls.gegenargument_log)` (Zeile 366), gefuellt vom analyse_loop
  in `services/claude_service.py` (nicht recon'd, aber Pattern bekannt aus Phase 04.7).
- **Cold-Call-Problem:** Cold-Call hat keinen analyse_loop, `ga_details` ist leer,
  also `einwaende_behandelt=0` garantiert. Das ist der Bug.

**`ConversationLog`-Schema relevante Spalten (`database/models.py:244-248`):**
```python
einwaende_gesamt         = Column(Integer, default=0)         # NOT NULL implizit (default=0)
einwaende_behandelt      = Column(Integer, default=0)         # NOT NULL implizit (default=0)
einwaende_fehlgeschlagen = Column(Integer, default=0)
einwaende_ignoriert      = Column(Integer, default=0)
vorwaende_erkannt        = Column(Integer, default=0)
```
`default=0` heisst SQLAlchemy setzt 0 beim Insert wenn nicht angegeben, NULL-Spalten
existieren in der Praxis nicht — gut fuer Migration-Logic (COALESCE nicht noetig).

**`ObjectionEvent`-Schema (`database/models.py:342-350`):**
```python
conversation_log_id = Column(Integer, ForeignKey('conversation_logs.id'), nullable=False)
einwand_typ         = Column(String(100), nullable=False)
success             = Column(Boolean, default=False, nullable=False)  # ← POLISH-38.1 nutzt True-Wert
created_at          = Column(DateTime, default=utcnow, nullable=False)
```
Perfekt fuer Aggregation: `COUNT(*)` = einwaende_gesamt, `SUM(CASE WHEN success THEN 1 ELSE 0 END)` = einwaende_behandelt.

**`/api/beenden` Flow (`routes/app_routes.py:254-582`):**
- L402-403: `ewb_clicks = list(ls.state.get('ewb_clicks', []))` (cf38589-Fix)
- L411-446: `db_conv.add(conv)` + `db_conv.commit()` — conv.id existiert ab hier
- L452-462: For-Schleife `db_conv.add(ObjectionEvent(...))` + `db_conv.commit()` wenn ewb_clicks
- **INSERT-POINT FIX:** Nach L462 (dem `if ewb_clicks: db_conv.commit()`-Block),
  aber VOR L464 (FT-logging) und VOR L488 (audit session_start/session_end).
  An dieser Stelle existieren alle ObjectionEvent-Rows bereits committed in der DB.

**Umlaut-Regel (CLAUDE.md):**
- Code-Identifier ASCII: `einwaende_gesamt`, `einwaende_behandelt`, `ewb_clicks`,
  `success`, `conversation_log_id` (alle bereits ASCII in Codebase)
- User-facing Text (Kommentare okay in ASCII, Log-Prints okay): keine Templates
  beruehrt in diesem Fix.

**`reset_session()` Timing (`services/live_session.py:304-404`):**
Clear von `state['ewb_clicks'] = []` passiert in einem SEPARATEN `with state_lock:`-
Block (Zeile 388-389), NACH dem Haupt-Reset-Block (Zeile 323-345). Wird aufgerufen
in `/api/beenden` Zeile 580 — NACH allen Counter-Writes, also kein Reset-Race.

**Integration-Engine (`services/integration_engine.py:129` `run_postcall_engine`):**
Liest `ewb_clicks` weiter als Parameter (Zeile 547 in app_routes.py). Das ist nach
dem ConversationLog-Commit und dem ObjectionEvent-Bulk-Insert, also unveraendert
— Engine bekommt weiterhin die vollstaendige ewb_clicks-Liste fuer Learning-Events.

**Existing POLISH-38.1 (Commit 585f567):** `handle_manual_ewb` in `deepgram_service.py`
ruft jetzt `record_ewb_click(typ, success=_ewb_success)` mit `_ewb_success=True` im
Normalfall. Das heisst: neue PiP-Sessions schreiben `success=True` in ObjectionEvent —
nutze diesen Wert fuer `einwaende_behandelt`-Zaehlung, nicht mehr `ga_details`.

**Altlasten-Verhalten (wichtig fuer Migration-Idempotenz):**
- Sessions VOR POLISH-38.1 (585f567): `ObjectionEvent.success=False` fuer manual_ewb
  (hardcodiert war `success=False`). Migration kann diese Sessions nicht rueckwirkend
  "als behandelt" markieren, da der ursprueng-User-Intent nicht wiederherstellbar ist.
  **Entscheidung:** Migration aggregiert nur Counts (`einwaende_gesamt`), plus
  `einwaende_behandelt` exakt als `SUM(success)` — alte Sessions bekommen genau den
  Wert, der in der DB steht (meist 0 fuer Pre-585f567-Sessions). Kein fabrizierter
  Retro-Fix, sondern reines Mirroring des DB-State auf den Counter.
- `/api/ewb_trigger`-Pfad schreibt immer `success=False` in `ewb_clicks` → nach
  dem Fix wird ObjectionEvent.success auch False sein → `einwaende_behandelt` zaehlt
  diese nicht als behandelt. Konsistent mit POLISH-38.1-Rationale (Flag spiegelt
  tatsaechlichen Spawn-Erfolg).
</recon_findings>

<interfaces>
Key types + code shapes the executor needs:

```python
# services/live_session.py:406
def record_ewb_click(einwand_typ: str, success: bool = False):
    """Erfasst einen EWB-Button-Klick im Session-State (thread-safe)."""
    # Nur In-Memory-Append — KEINE DB-Ops.

# routes/app_routes.py:254 — /api/beenden handler
# Relevant section (L398-462 post-cf38589, post-POLISH-38.1):

# Read ewb_clicks BEFORE ConversationLog-Insert (cf38589)
with ls.state_lock:
    ewb_clicks = list(ls.state.get('ewb_clicks', []))

# ConversationLog-Insert (L413-446)
conv = ConversationLog(
    einwaende_gesamt=len(ewb_clicks),  # cf38589 — defensiver Initial-Wert
    einwaende_behandelt=len([x for x in ga_details if x.get('erfolgreich') is True]),  # BUG
    ...
)
db_conv.add(conv); db_conv.commit()  # conv.id exists after

# ObjectionEvent bulk-insert (L452-462)
from database.models import ObjectionEvent
for click in ewb_clicks:
    db_conv.add(ObjectionEvent(
        user_id=g.user.id, org_id=g.org.id,
        conversation_log_id=conv.id,
        einwand_typ=click['einwand_typ'],
        success=click['success'],  # POLISH-38.1: True/False je nach Spawn-Erfolg
    ))
if ewb_clicks:
    db_conv.commit()

# ← INSERT-POINT: Re-aggregate from DB-truth (NEW CODE)
```

Migration pseudo-code (Task 1):
```python
# scripts/migrate_polish_38_counters.py
# For each ConversationLog row: COUNT ObjectionEvents + SUM(success),
# UPDATE conv.einwaende_gesamt + einwaende_behandelt if mismatch.
# Idempotent: only write if current value != computed value.
```
</interfaces>

</context>

<tasks>

<task type="auto">
  <name>Task 1 (MIGRATION): scripts/migrate_polish_38_counters.py erstellen + lokal laufen lassen + committen</name>
  <files>
    - scripts/migrate_polish_38_counters.py (neu)
  </files>
  <action>
Erstelle ein neues Migration-Script unter `scripts/migrate_polish_38_counters.py`.
Script aggregiert pro `ConversationLog.id` die zugehoerigen `ObjectionEvent`-Rows und
korrigiert `einwaende_gesamt` + `einwaende_behandelt` wenn Mismatch. Idempotent.

**Exakter Script-Inhalt:**

```python
#!/usr/bin/env python3
"""
POLISH-38 Migration: Reconcile ConversationLog counters with ObjectionEvent table.

Per POLISH-29 User-Definition ("EWB-Button gedrueckt = Einwand behandelt") muss
ConversationLog.einwaende_gesamt der Anzahl der ObjectionEvent-Rows fuer diese
Session entsprechen, und einwaende_behandelt der Anzahl der ObjectionEvents mit
success=True.

Bis Commit cf38589 war einwaende_gesamt=len(einwaende_liste) (AI-detected, nicht
User-Klicks). Sessions vor cf38589 haben deshalb Mismatches zwischen Counter und
tatsaechlichen ObjectionEvents. Dieses Script korrigiert sie.

Idempotent: nur Write wenn Counter != aggregierte Werte.

Usage:
    python scripts/migrate_polish_38_counters.py          # Produktions-Run
    python scripts/migrate_polish_38_counters.py --dry    # Dry-Run (zeigt nur was geaendert wuerde)
"""
import sys
import os

# Bootstrap project path so `from database.*` imports work when called from repo root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import func, case
from database.db import get_session
from database.models import ConversationLog, ObjectionEvent


def main(dry_run: bool = False) -> int:
    db = get_session()
    try:
        # Aggregiere ObjectionEvents pro conversation_log_id
        agg_q = (
            db.query(
                ObjectionEvent.conversation_log_id.label('cid'),
                func.count(ObjectionEvent.id).label('total'),
                func.sum(case((ObjectionEvent.success == True, 1), else_=0)).label('ok'),
            )
            .group_by(ObjectionEvent.conversation_log_id)
        )
        agg_map = {row.cid: (int(row.total or 0), int(row.ok or 0)) for row in agg_q.all()}

        if not agg_map:
            print("[migrate] Keine ObjectionEvent-Rows in der DB — nichts zu tun.")
            return 0

        print(f"[migrate] {len(agg_map)} ConversationLog-IDs haben ObjectionEvents — pruefe Counter...")

        updated = 0
        skipped = 0
        for cid, (total, ok) in agg_map.items():
            conv = db.get(ConversationLog, cid)
            if conv is None:
                print(f"[migrate] WARN: ObjectionEvents verweisen auf conv.id={cid}, aber ConversationLog-Row fehlt (orphan) — skip")
                continue
            cur_total = conv.einwaende_gesamt or 0
            cur_ok = conv.einwaende_behandelt or 0
            if cur_total == total and cur_ok == ok:
                skipped += 1
                continue
            print(f"[migrate] conv.id={cid}: einwaende_gesamt {cur_total}->{total}, einwaende_behandelt {cur_ok}->{ok}")
            if not dry_run:
                conv.einwaende_gesamt = total
                conv.einwaende_behandelt = ok
            updated += 1

        if dry_run:
            print(f"[migrate] DRY-RUN: {updated} Rows wuerden geaendert, {skipped} sind bereits konsistent.")
        else:
            db.commit()
            print(f"[migrate] OK: {updated} Rows korrigiert, {skipped} bereits konsistent.")
        return 0
    finally:
        db.close()


if __name__ == '__main__':
    dry = '--dry' in sys.argv
    sys.exit(main(dry_run=dry))
```

**Nach Erstellen:**

1. **Dry-Run lokal:**
   ```bash
   cd /c/Users/andre/dev/salesnerve
   python scripts/migrate_polish_38_counters.py --dry
   ```
   Erwartete Ausgabe: Liste der zu aendernden Rows (sollten Sessions aus POLISH-29-/cf38589-
   Vor-Aera sein, wo `einwaende_gesamt=len(einwaende_liste)` war). Falls Ausgabe
   `Keine ObjectionEvent-Rows` → das ist OK (lokale DB hat vielleicht keine Testdaten),
   Script ist trotzdem korrekt.

2. **Produktions-Run lokal (auf `database/salesnerve.db`):**
   ```bash
   python scripts/migrate_polish_38_counters.py
   ```

3. **Commit Migration + Run-Ergebnis gemeinsam:**
   ```
   git add scripts/migrate_polish_38_counters.py
   git commit -m "$(cat <<'EOF'
   chore(POLISH-38): migration script — reconcile ConversationLog counters with ObjectionEvent table

   Backfills einwaende_gesamt + einwaende_behandelt from the authoritative
   objection_events table for existing ConversationLog rows (pre-cf38589 sessions
   had einwaende_gesamt=len(einwaende_liste) — AI-detected — which diverged from
   the POLISH-29 user definition "EWB-Button gedrueckt = behandelt").

   Idempotent: only writes when current counter != aggregated value.
   Supports --dry flag for rehearsal.

   Ran locally against database/salesnerve.db. VPS-Deploy wird separat auf der
   live-DB ausgefuehrt.

   Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
   EOF
   )"
   ```

**Wichtig:**
- Kein `db.commit()` im Dry-Run-Branch — nur Console-Output.
- Script nutzt `database.db.get_session()` — konsistent mit restlichem Codebase.
- `sqlalchemy.case` verwendet die 2.0-Syntax `case((condition, value), else_=value)`.
- `conversation_log_id` ist `nullable=False` im Schema — kein NULL-Cluster-Risiko.
- Script committen AUCH wenn Run keine Aenderungen findet (Tool fuer VPS-Deploy).
  </action>
  <verify>
    <automated>bash -c "cd /c/Users/andre/dev/salesnerve && python -c 'import ast; ast.parse(open(\"scripts/migrate_polish_38_counters.py\").read()); print(\"syntax-OK\")' && python scripts/migrate_polish_38_counters.py --dry && git log -1 --format='%s' | grep -q 'chore(POLISH-38): migration script' && echo OK-all"</automated>
  </verify>
  <done>
`scripts/migrate_polish_38_counters.py` existiert, ist Python-valid, Dry-Run laeuft
ohne Exception durch (Output ist akzeptabel: entweder "Keine ObjectionEvent-Rows"
oder "N Rows wuerden geaendert"), Produktions-Run ohne Exception ausgefuehrt auf
lokaler salesnerve.db, Migration-Commit `chore(POLISH-38): migration script ...`
existiert mit genau dem Script-File im Diff.
  </done>
</task>

<task type="auto">
  <name>Task 2 (CODE-FIX): /api/beenden re-aggregiert Counter aus ObjectionEvent-Tabelle nach Bulk-Insert</name>
  <files>
    - routes/app_routes.py (modifiziert, ~15 Zeilen hinzugefuegt)
  </files>
  <action>
Aendere `routes/app_routes.py` `api_beenden`-Handler so, dass nach dem ObjectionEvent-
Bulk-Insert die Counter `conv.einwaende_gesamt` + `conv.einwaende_behandelt` aus
der DB re-aggregiert und geschrieben werden. Der bestehende `cf38589`-Initial-Wert
(`len(ewb_clicks)`) bleibt als defensiver Fallback stehen — nur UEBERSCHREIBEN wenn
ObjectionEvent-Rows existieren.

**Genaue Aenderung:**

1. **Finde Zeilen 461-463** in `routes/app_routes.py` (nach dem For-Loop `for click in ewb_clicks`):
   ```python
           if ewb_clicks:
               db_conv.commit()

           # FT logging: update ft_call_sessions with aggregates (Phase 04.7.1)
   ```

2. **Fuege zwischen `db_conv.commit()` und dem Kommentar `# FT logging:` folgenden
   Block ein** (exakt an dieser Stelle, weil conv.id hier existiert, ObjectionEvents
   committed sind, und vor den FT-Hooks die auf conv.id zeigen):

```python
        if ewb_clicks:
            db_conv.commit()

        # POLISH-38 (Haupt-Fix): Re-aggregate counters from ObjectionEvent (authoritative source).
        # cf38589 set einwaende_gesamt=len(ewb_clicks) initially — defensive fallback.
        # Here we overwrite with the DB-truth: einwaende_behandelt becomes SUM(success)
        # from the just-committed ObjectionEvent rows (POLISH-29: "EWB-Button gedrueckt
        # = behandelt", success-Flag aus POLISH-38.1 spiegelt erfolgreichen Haiku-Spawn).
        # Defence-in-depth: works even if ewb_clicks list had stale state.
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

        # FT logging: update ft_call_sessions with aggregates (Phase 04.7.1)
```

**Wichtig:**
- `_total > 0`-Guard schuetzt Sessions mit 0 ObjectionEvents (in diesem Fall bleibt
  der `cf38589`-Initial-Wert `len(ewb_clicks)=0` unveraendert, korrekt).
- `_sqlcase((condition, value), else_=value)` — SQLAlchemy 2.0-Syntax (konsistent mit
  Migration-Script aus Task 1).
- `ObjectionEvent` ist bereits importiert (Zeile ~452 via `from database.models import ObjectionEvent`).
  **Aber** der Import passiert INNERHALB des try-Blocks — pruefe ob Scope noch gilt,
  sonst importiere nochmal mit alias. **Loesung:** bette Import in den neuen Block ein,
  falls unklar (siehe obiger Code-Block — `ObjectionEvent` wird referenziert, nicht importiert,
  unter der Annahme dass Zeile 452 `from database.models import ObjectionEvent` bereits
  im selben try-Scope steht). **Pruefe beim Einfuegen:** ist der neue Block innerhalb
  desselben `try:`-Scopes wie Zeile 452? Falls JA: `ObjectionEvent` verfuegbar. Falls
  NEIN (separater Scope): fuege `from database.models import ObjectionEvent as _OE`
  am Anfang des neuen try-Blocks ein und benutze `_OE` statt `ObjectionEvent`.
- `try/except` umschliesst den Re-Aggregate-Block — wenn etwas schiefgeht (z.B.
  DB-Lock), bleibt der `cf38589`-Initial-Wert stehen. Kein Regression-Risiko.
- Kein `reset_session()`- oder anderer State-Touch. Rein DB-Layer.
- `print(f"[POLISH-38] ...")` fuer Deploy-Log-Monitoring (zeigt dass der Fix auf VPS greift).

**Nach Aenderung:**
```bash
# Syntax-Check
python -c "import ast; ast.parse(open('routes/app_routes.py', encoding='utf-8').read()); print('syntax-OK')"

# Grep verifiziert dass der neue Block vorhanden ist (POLISH-38-Marker eindeutig)
grep -n "POLISH-38 (Haupt-Fix)" routes/app_routes.py
grep -n "counters reconciled conv.id" routes/app_routes.py
```

**Commit:**
```
git add routes/app_routes.py
git commit -m "$(cat <<'EOF'
fix(POLISH-38): reconcile einwaende_gesamt/behandelt from ObjectionEvent after bulk-insert

Root cause: einwaende_behandelt was computed from ga_details (analyse_loop's
gegenargument_log) — always 0 for Cold-Call sessions (no analyse_loop). Per
POLISH-29 ("EWB-Button gedrueckt = behandelt"), the counter must derive from
ObjectionEvent.success=True rows.

cf38589 fixed einwaende_gesamt to use len(ewb_clicks) but kept the wrong source
for einwaende_behandelt. This commit makes the ObjectionEvent table the single
source of truth for BOTH counters.

After the ObjectionEvent bulk-insert in /api/beenden, COUNT(*) + SUM(success) are
queried and written back to conv.einwaende_gesamt + einwaende_behandelt. Guarded
by total>0 so sessions with no EWB clicks are untouched. Wrapped in try/except —
any reconcile failure falls back to cf38589's len(ewb_clicks) initial value.

Defence-in-depth: eliminates any stale-state risk in the ewb_clicks in-memory list.

Test-Repro: Cold-Call with 3 EWB clicks (2 success=True, 1 success=False) now
yields einwaende_gesamt=3, einwaende_behandelt=2. Session-detail page shows 2/3.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```
  </action>
  <verify>
    <automated>bash -c "cd /c/Users/andre/dev/salesnerve && python -c 'import ast; ast.parse(open(\"routes/app_routes.py\", encoding=\"utf-8\").read()); print(\"syntax-OK\")' && grep -nq 'POLISH-38 (Haupt-Fix)' routes/app_routes.py && grep -nq 'counters reconciled conv.id' routes/app_routes.py && grep -nq '_sqlfunc.count(ObjectionEvent.id)' routes/app_routes.py && git log -1 --format='%s' | grep -q 'fix(POLISH-38): reconcile einwaende_gesamt' && echo OK-all"</automated>
  </verify>
  <done>
`routes/app_routes.py` enthaelt den Re-Aggregate-Block mit POLISH-38-(Haupt-Fix)-
Kommentar direkt nach der ObjectionEvent-Bulk-Insert-Schleife und vor dem
FT-logging-Block. Datei ist Python-valid. Grep-Checks fuer Marker-Strings
gruen. Commit `fix(POLISH-38): reconcile einwaende_gesamt ...` existiert mit
nur `routes/app_routes.py` im Diff.
  </done>
</task>

<task type="auto">
  <name>Task 3 (SUMMARY + STATE + PUSH): SUMMARY.md + STATE.md update + git push</name>
  <files>
    - .planning/quick/260421-lpx-polish-38-haupt-bug-einwaende-gesamt-cou/260421-lpx-SUMMARY.md (neu)
    - .planning/STATE.md (modifiziert — Quick-Tasks-Eintrag hinzufuegen)
  </files>
  <action>
**1. Erstelle Summary unter `.planning/quick/260421-lpx-polish-38-haupt-bug-einwaende-gesamt-cou/260421-lpx-SUMMARY.md`:**

```markdown
---
quick_task: 260421-lpx
date: 2026-04-21
commits:
  - hash: <task1-commit>
    subject: "chore(POLISH-38): migration script — reconcile ConversationLog counters with ObjectionEvent table"
  - hash: <task2-commit>
    subject: "fix(POLISH-38): reconcile einwaende_gesamt/behandelt from ObjectionEvent after bulk-insert"
files_modified:
  - scripts/migrate_polish_38_counters.py (NEW)
  - routes/app_routes.py
closes: [POLISH-38]
related: [POLISH-29, POLISH-38.1, POLISH-43]
---

# Quick Task 260421-lpx — POLISH-38 Haupt-Bug-Fix

**One-liner:** `ConversationLog.einwaende_gesamt` + `einwaende_behandelt` werden
jetzt nach dem ObjectionEvent-Bulk-Insert in `/api/beenden` aus der DB-Tabelle
re-aggregiert (Single-Source-of-Truth), plus Migration-Script fuer bestehende
Sessions.

## Problem

**Symptom (UAT-R2, Session #117):** Cold-Call mit 4 EWB-Klicks, aber Session-Detail-
Seite Breakdown "Einwaende behandelt" zeigt `0/1` statt `2/4` (oder aehnlich).

**Root-Causes (2):**

1. **`einwaende_behandelt` aus falscher Quelle:** Zeile 423 las aus `ga_details`
   (abgeleitet vom AI-analyse_loop's `gegenargument_log`). Cold-Call hat keinen
   analyse_loop → `ga_details=[]` → `einwaende_behandelt=0` unabhaengig von EWB-
   Klicks. Widerspruch zu POLISH-29 ("EWB-Button gedrueckt = Einwand behandelt").

2. **`cf38589`-Fix nur teilweise:** `einwaende_gesamt=len(ewb_clicks)` war korrekt,
   aber anfaellig gegen jede Race/Reset-Reihenfolge-Aenderung. Authoritative Quelle
   sollte die `ObjectionEvent`-Tabelle selbst sein.

## Fix-Strategie: Central-Point-Fix in `/api/beenden`

**Warum NICHT live-Update in `record_ewb_click`:** Recon zeigte dass `ConversationLog`
NICHT bei `start_live_session` erzeugt wird — erst in `/api/beenden`. Waehrend der
Live-Session existiert kein `conv`-Row, das man inkrementieren koennte. Der User-
Hinweis zum `record_ewb_click`-Central-Point-Fix basiert auf einer Annahme, die in
diesem Codebase nicht gilt.

**Gewaehlter Ansatz:** Nach dem bestehenden ObjectionEvent-Bulk-Insert (nach
`db_conv.commit()` fuer ObjectionEvents) werden die Counter aus der DB re-aggregiert:
```sql
SELECT COUNT(*), SUM(CASE WHEN success THEN 1 ELSE 0 END)
FROM objection_events WHERE conversation_log_id = ?
```
Werte ueberschreiben `conv.einwaende_gesamt` + `einwaende_behandelt` und werden
committed. Guard `_total > 0`: Sessions ohne EWB-Klicks bleiben unberuehrt (kein
Counter-Reset auf 0).

## Aenderungen

### Task 1: Migration (`<task1-commit>`)

**Neu:** `scripts/migrate_polish_38_counters.py` — aggregiert ObjectionEvents pro
`conversation_log_id` und korrigiert `einwaende_gesamt`/`einwaende_behandelt` wenn
Mismatch. Idempotent. `--dry`-Flag unterstuetzt.

**Lokal-Run-Ergebnis:** <N> Rows korrigiert, <M> bereits konsistent.

**VPS-Deploy:** Nach `git push` noch auf Hetzner-VPS ausfuehren:
```bash
ssh root@nerve.app "cd /srv/nerve && git pull && python scripts/migrate_polish_38_counters.py"
```

### Task 2: Code-Fix (`<task2-commit>`)

**`routes/app_routes.py`:** 15 Zeilen neuer Code in `api_beenden`, direkt nach dem
ObjectionEvent-Bulk-Insert-Commit (Line ~462) und vor dem FT-logging-Block. Wrapped
in `try/except` mit Fallback auf `cf38589`-Initial-Werte. Print-Log
`[POLISH-38] counters reconciled conv.id=X gesamt=Y behandelt=Z` fuer Deploy-
Monitoring.

**Defence-in-depth:** Selbst wenn `ewb_clicks`-Liste je leer oder stale waere,
wuerde der Fix die richtigen Werte aus der DB rekonstruieren.

## Was NICHT geaendert wurde (bewusst)

- **`services/deepgram_service.py` `handle_manual_ewb`:** unveraendert. POLISH-38.1
  (Commit 585f567) hat `success=_ewb_success` bereits korrekt gesetzt. Re-Aggregate
  liest diesen Wert direkt aus ObjectionEvent.
- **`routes/app_routes.py` `api_ewb_trigger`:** unveraendert. `record_ewb_click(...success=False)`
  bleibt, `ObjectionEvent.success=False` fuer diese Klicks ist konsistent (kein
  HTTP-Haiku-Spawn-Indikator aehnlich PiP-Pfad).
- **`services/live_session.py` `record_ewb_click`:** unveraendert. Helper bleibt
  In-Memory-Append-Only. Keine DB-Seiten-Effekte.
- **`cf38589`-Fix (L422 `einwaende_gesamt=len(ewb_clicks)`):** bleibt als defensiver
  Initial-Wert stehen. Dient als Fallback falls Re-Aggregate scheitert.

## Nicht-Scope (bewusst verschoben)

- **POLISH-43 Post-Call-Overlay Diskrepanz:** Overlay liest Runtime-State, Session-
  Detail liest persistierten DB-Wert. Nach diesem Fix sind BEIDE Zahlen konsistent
  aus derselben Quelle (ObjectionEvent) — aber Overlay rendert moeglicherweise
  VOR dem `/api/beenden`-Response. Nicht in diesem Quick-Task geloest.
- **Phase 07.5 EWB-Feed-Redesign (POLISH-53):** separate Phase, UX-Spec erforderlich.

## Verification (User)

1. Deploy auf VPS (git pull + restart + migration-run).
2. Cold-Call-Session starten, 3 EWB-Klicks (2 Haiku-Spawn-erfolgreich, 1 Spawn-Error
   simulieren falls moeglich — oder nur 3 normale Klicks).
3. Session beenden.
4. Session-Detail-Seite oeffnen. Breakdown "Einwaende behandelt" zeigt `3/3` (alle
   success=True bei normalen Klicks, POLISH-38.1-Flag).
5. DB-Query: `SELECT einwaende_gesamt, einwaende_behandelt FROM conversation_logs
   WHERE id=<neue session id>` → Werte matchen `(SELECT COUNT(*) FROM objection_events
   WHERE conversation_log_id=<id>)` und `(SELECT COUNT(*) FROM objection_events
   WHERE conversation_log_id=<id> AND success=1)`.
6. VPS-Log: Zeile `[POLISH-38] counters reconciled conv.id=<id> gesamt=3 behandelt=3`
   sichtbar bei Session-Ende.

## Commits + Push

- Task 1: `chore(POLISH-38): migration script — reconcile ConversationLog counters with ObjectionEvent table`
- Task 2: `fix(POLISH-38): reconcile einwaende_gesamt/behandelt from ObjectionEvent after bulk-insert`
- Task 3: `docs(quick-260421-lpx): complete POLISH-38 main fix + migration`
- Final: `git push origin main` (per CLAUDE.md Git-Regel)
```

Ersetze `<task1-commit>` + `<task2-commit>` mit den echten SHA-Hashes aus `git log`
(via `git log --oneline -3`). Ersetze `<N>` und `<M>` mit den tatsaechlichen Werten
aus dem Migration-Produktions-Run (Task 1 Console-Output).

**2. Update `.planning/STATE.md`:**

Fuege in den "Quick Tasks Completed"-Table (aktuell Zeile 400-404) eine neue Row
hinzu:

```markdown
| 260421-lpx | POLISH-38 Haupt-Fix: re-aggregate einwaende_gesamt/behandelt from ObjectionEvent + migration | 2026-04-21 | <task1>+<task2> | [260421-lpx-polish-38-haupt-bug-einwaende-gesamt-cou](./quick/260421-lpx-polish-38-haupt-bug-einwaende-gesamt-cou/) |
```

Ersetze `<task1>` und `<task2>` mit den Short-SHAs (erste 7 Zeichen).

**3. Commit + Push:**

```bash
git add .planning/quick/260421-lpx-polish-38-haupt-bug-einwaende-gesamt-cou/260421-lpx-SUMMARY.md .planning/STATE.md
git commit -m "$(cat <<'EOF'
docs(quick-260421-lpx): complete POLISH-38 main fix + migration

Summary for two-commit fix (migration script + code-fix in /api/beenden) and
STATE.md entry for session continuity.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"

git push origin main
```
  </action>
  <verify>
    <automated>bash -c "cd /c/Users/andre/dev/salesnerve && test -f .planning/quick/260421-lpx-polish-38-haupt-bug-einwaende-gesamt-cou/260421-lpx-SUMMARY.md && grep -q '260421-lpx' .planning/STATE.md && git log -1 --format='%s' | grep -q 'docs(quick-260421-lpx)' && git log --oneline -5 && git status | grep -q 'up to date' && echo OK-all"</automated>
  </verify>
  <done>
SUMMARY.md existiert mit Commit-Hashes eingefuellt. STATE.md enthaelt die neue
Quick-Task-Row fuer 260421-lpx. 3. Commit `docs(quick-260421-lpx): complete POLISH-38 ...`
ist gepusht nach origin/main. `git status` zeigt "up to date" nach Push. `git log --oneline -5`
zeigt 3 neue Commits (migration, fix, docs) oben. Branch sauber.
  </done>
</task>

</tasks>

<verification>
End-of-plan Verification (all three must pass before considering done):

1. **Syntax + Import:** `python -c "import app; print('OK')"` laeuft ohne Exception
   — bestaetigt dass routes/app_routes.py weiterhin importierbar ist.

2. **Live-Test (User macht manuell auf VPS nach Deploy):** Cold-Call-Session mit
   3 EWB-Klicks → `einwaende_gesamt=3`, `einwaende_behandelt` entspricht Anzahl
   erfolgreich-gespawnter Haiku-Streams (normalerweise 3). Session-Detail-Seite
   zeigt korrekten Breakdown.

3. **Git-History:** `git log --oneline -5` zeigt (Reihenfolge von neuesten):
   - `docs(quick-260421-lpx): complete POLISH-38 main fix + migration`
   - `fix(POLISH-38): reconcile einwaende_gesamt/behandelt from ObjectionEvent after bulk-insert`
   - `chore(POLISH-38): migration script — reconcile ConversationLog counters with ObjectionEvent table`
   - `7dc811f docs(quick-260421-kwm): complete POLISH-45 + POLISH-38.1 nachzug` (prior)
</verification>

<success_criteria>
- [ ] `scripts/migrate_polish_38_counters.py` existiert, ist Python-valid, `--dry`
      funktioniert, Produktions-Run laeuft lokal ohne Exception.
- [ ] `routes/app_routes.py` enthaelt den Re-Aggregate-Block mit `POLISH-38 (Haupt-Fix)`-
      Marker nach dem ObjectionEvent-Bulk-Insert und vor dem FT-logging-Block.
      `try/except` mit Fallback-Logging. `_total > 0`-Guard.
- [ ] 3 atomic Commits auf `main`: chore(POLISH-38) migration, fix(POLISH-38) code,
      docs(quick-260421-lpx) summary.
- [ ] `.planning/STATE.md` Quick-Tasks-Table hat Eintrag fuer 260421-lpx.
- [ ] `.planning/quick/260421-lpx-.../260421-lpx-SUMMARY.md` existiert, Commit-
      Hashes korrekt eingefuellt, Lokal-Migration-Run-Werte eingetragen.
- [ ] `git push origin main` ausgefuehrt, Remote-Branch hat die 3 neuen Commits.
- [ ] `cf38589`-Fix (L422 `einwaende_gesamt=len(ewb_clicks)`) bleibt unberuehrt
      als defensiver Fallback — KEINE Regression.
- [ ] Kein Touch an `services/deepgram_service.py` oder `services/live_session.py` —
      Fix nur im End-of-Session-Path.
</success_criteria>

<output>
After completion:
- SUMMARY.md in `.planning/quick/260421-lpx-polish-38-haupt-bug-einwaende-gesamt-cou/260421-lpx-SUMMARY.md`
- STATE.md updated mit 260421-lpx Quick-Task-Eintrag
- 3 Commits gepusht auf origin/main
- User darf VPS-Deploy + Live-UAT durchfuehren (out of scope fuer den Plan selbst)
</output>
