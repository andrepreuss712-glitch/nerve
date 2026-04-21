---
quick_task: 260421-lpx
date: 2026-04-21
commits:
  - hash: 451c909
    subject: "chore(POLISH-38): migration script - reconcile ConversationLog counters with ObjectionEvent table"
  - hash: 29c8b71
    subject: "fix(POLISH-38): reconcile einwaende_gesamt/behandelt from ObjectionEvent after bulk-insert"
files_modified:
  - scripts/migrate_polish_38_counters.py (NEW)
  - routes/app_routes.py
closes: [POLISH-38]
related: [POLISH-29, POLISH-38.1, POLISH-43]
---

# Quick Task 260421-lpx - POLISH-38 Haupt-Bug-Fix

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
NICHT bei `start_live_session` erzeugt wird - erst in `/api/beenden`. Waehrend der
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

### Task 1: Migration (`451c909`)

**Neu:** `scripts/migrate_polish_38_counters.py` - aggregiert ObjectionEvents pro
`conversation_log_id` und korrigiert `einwaende_gesamt`/`einwaende_behandelt` wenn
Mismatch. Idempotent. `--dry`-Flag unterstuetzt.

**Lokal-Run-Ergebnis:** `Keine ObjectionEvent-Rows in der DB - nichts zu tun.`
(Lokale salesnerve.db hat keine Live-Session-Daten mit EWB-Klicks, erwartet.)
Script ist trotzdem korrekt — VPS-Deploy mit echter Daten-DB ist der echte Test.

**VPS-Deploy:** Nach `git push` noch auf Hetzner-VPS ausfuehren:
```bash
ssh root@nerve.app "cd /srv/nerve && git pull && python scripts/migrate_polish_38_counters.py"
```

### Task 2: Code-Fix (`29c8b71`)

**`routes/app_routes.py`:** 26 Zeilen neuer Code in `api_beenden`, direkt nach dem
ObjectionEvent-Bulk-Insert-Commit (Line 462) und vor dem FT-logging-Block (Line 490).
Wrapped in `try/except` mit Fallback auf `cf38589`-Initial-Werte. Print-Log
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
  aus derselben Quelle (ObjectionEvent) - aber Overlay rendert moeglicherweise
  VOR dem `/api/beenden`-Response. Nicht in diesem Quick-Task geloest.
- **Phase 07.5 EWB-Feed-Redesign (POLISH-53):** separate Phase, UX-Spec erforderlich.

## Verification (User)

1. Deploy auf VPS (git pull + restart + migration-run).
2. Cold-Call-Session starten, 3 EWB-Klicks (2 Haiku-Spawn-erfolgreich, 1 Spawn-Error
   simulieren falls moeglich - oder nur 3 normale Klicks).
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

- Task 1: `451c909` chore(POLISH-38): migration script - reconcile ConversationLog counters with ObjectionEvent table
- Task 2: `29c8b71` fix(POLISH-38): reconcile einwaende_gesamt/behandelt from ObjectionEvent after bulk-insert
- Task 3: `docs(quick-260421-lpx): complete POLISH-38 main fix + migration`
- Final: `git push origin main` (per CLAUDE.md Git-Regel)

## Self-Check

**Files verified:**
- `scripts/migrate_polish_38_counters.py` exists, syntax-OK, `--dry` + prod-run passed
- `routes/app_routes.py` contains POLISH-38 (Haupt-Fix) marker at line 464, reconcile block 470-488

**Commits verified:**
- `451c909` in git log (migration script commit)
- `29c8b71` in git log (code-fix commit)

**Import smoke-test:** `python -c "import app"` passes without exception.
