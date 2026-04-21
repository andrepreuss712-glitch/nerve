---
phase: quick-260421-mwy
plan: 01
type: execute
wave: 1
depends_on: []
requirements:
  - POLISH-54
files_modified:
  - routes/app_routes.py
commits:
  - 497350d
metrics:
  tasks: 1
  files: 1
  lines_added: 54
  lines_removed: 0
  duration_min: 10
completed_date: 2026-04-21
---

# Quick Task 260421-mwy: POLISH-54 einwaende_liste Aggregation Summary

**One-liner:** Merge ObjectionEvent-Rows into `postcall['einwaende']` after POLISH-38-Reconcile so Cold-Call-Postcall-Kachel zeigt die echte EWB-Klick-Anzahl statt "-".

## Problem

Seit Phase 06.3-Entkoppelung laeuft im Cold-Call-Modus kein Analyse-Loop mehr.
Die lokale `einwaende_liste` (Z.305-313) wird aber nur aus `log_entries` mit
`type=='analyse' AND einwand==True` gebaut -- also leer im Cold-Call. Das
Frontend (`pip-launcher.js:1881`) liest `postcall.einwaende.length` und zeigte
"-" (em-dash) in der Postcall-Kachel "Einwaende", obwohl im DB bereits
ObjectionEvent-Rows fuer jeden EWB-Klick persistiert waren. Inkonsistent zur
Session-Detail-Page, die direkt aus DB las und die korrekten Zahlen zeigte.

## Solution

Merge-Block (54 Zeilen, neue Addition, 0 Deletions) nach dem POLISH-38-
Counter-Reconcile-Block (Z.488) und vor dem FT-Logging-Block (Z.544). Innerhalb
des outer `try:`-Scopes bei Z.412, damit `conv`, `db_conv`, `postcall` in Scope.

### Algorithmus

1. Query `ObjectionEvent`-Rows fuer die gerade committete `conv.id` (sortiert
   nach `created_at`, damit Dedup deterministisch bei Kollisionen).
2. Baue Dedup-Set `(typ_lower, ts_bucket_5s)` aus existierenden
   `postcall['einwaende']`-Entries (wichtig fuer Meeting-Mode-Kompatibilitaet:
   wenn Analyse-Loop UND EWB-Klick binnen 5s denselben Typ registrieren,
   nur 1 Entry).
3. Fuer jeden ObjectionEvent: skip wenn `(typ_lower, ts_bucket_5s)` bereits
   im Set, sonst Entry mit Default-Werten bauen: `{typ, zitat:'',
   intensitaet:'mittel', ts: iso-string}`. ObjectionEvent-Schema hat kein
   `text`/`zitat`/`intensitaet`-Feld -- daher Defaults.
4. Falls neue Entries gefunden: `postcall['einwaende']` mit konkateniertem
   Array ueberschreiben + Log-Print `[POLISH-54] einwaende merged ... added=N
   total=M`.
5. Defensive `try/except` um den gesamten Block -- DB-Fehler crashen
   `/api/beenden` nicht, Fallback ist unveraenderte `einwaende_liste`.

### Was unangetastet bleibt

- Lokale `einwaende_liste`-Variable (Z.305-313 Build) -- nicht beruehrt.
- CRM-Export (`services.crm_service.generate_crm_export`, Z.352) bekommt
  weiter die lokale `einwaende_liste`.
- `run_postcall_engine` (Z.626) bekommt weiter `einwaende=einwaende_liste`.
- Keine DB-Schema-Aenderung, keine Migration.
- Kein Frontend-Touch (`pip-launcher.js` liest bereits `.length` und ist
  damit blind fuer interne Dict-Struktur).

## Recon-Ergebnis vs. Plan-Spec

| Plan-Spec | Tatsaechlich im Code | Match |
|-----------|----------------------|-------|
| Z.305-313 `einwaende_liste`-Build | Z.305-315 | Yes |
| Z.335-345 `postcall`-Assign | Z.335-345 | Yes |
| Z.402-403 `ewb_clicks`-Read | Z.402-403 | Yes |
| Z.450-462 ObjectionEvent-Bulk-Insert | Z.450-462 | Yes |
| Z.464-488 POLISH-38-Reconcile | Z.464-488 | Yes |
| Insert-Position: Z.490 (`# FT logging...`) | Z.490 (vor Edit) -> Z.544 (nach Edit) | Yes |
| CRM-Export Z.352 | Z.352 | Yes |
| run_postcall_engine Z.572 | Z.626 (+54 wegen Insert) | Yes (verschoben) |

**Abweichung:** Plan-Doc erwaehnt Z.572 fuer `run_postcall_engine`, ist aber
tatsaechlich Z.626 (nach Insert Z.680, vor Insert Z.626). Plan-Doc-Zeilen
waren bereits leicht drift gegenueber aktueller Codebase; Funktionspointer
unveraendert, daher keine Anpassung am Plan-Design.

## Verifikation

### Automated (passed)

```
[OK] syntax valid   (python -c "import ast; ast.parse(...)")
[OK] import routes.app_routes succeeded
```

### Grep-Counts (passed)

| Marker | Hits | Expected |
|--------|------|----------|
| `POLISH-54` | 3 (Header-Kommentar, success-log, error-log) | >= 2 |
| `einwaende_liste` | 7 (5 Code-Referenzen unveraendert + 2 neue Kommentar-Referenzen) | 5+ Code unchanged |
| `postcall['einwaende']` | 4 (Dict-Init Z.336 via `'einwaende': einwaende_liste`, Overwrite Z.539, Log Z.540, 2 Kommentare) | 2+ Code |

### Diff-Stat

```
routes/app_routes.py | 54 ++++++++++++++++++++++++++++++++++++++++++++++++++++
1 file changed, 54 insertions(+)
```

Reine Addition -- 0 Deletions, 0 Modifikationen an bestehendem Code.

## Konsumenten & Regression-Check

| Pfad | Liest | Effekt |
|------|-------|--------|
| Frontend `pip-launcher.js:1881` | `postcall.einwaende.length` | **Cold-Call: N statt 0** / **Meeting: unchanged** (Analyse-Loop-Einwaende bereits drin + EWB-Dedup greift) |
| `services.crm_service.generate_crm_export` | `einwaende_liste` (local var) | Unveraendert |
| `services.postcall_engine.run_postcall_engine` | `einwaende_liste` (local var) | Unveraendert |
| Session-Detail-Page `session_detail()` | ObjectionEvent-Rows direct | Unveraendert (kein Regression zu 29c8b71) |
| `ls.last_postcall` Snapshot (Z.~639) | `postcall`-Dict | Auto-propagiert (merge passiert VOR Snapshot) |

## Commit

**SHA:** `497350d`
**Message:** `fix(POLISH-54): aggregate einwaende_liste from ObjectionEvent for cold-call postcall`

## Known Stubs

None -- alle Dict-Keys haben sinnvolle Defaults:
- `zitat: ''` (ObjectionEvent hat kein Zitat-Feld im Schema, leer ist korrekt).
- `intensitaet: 'mittel'` (ObjectionEvent hat kein Intensitaet-Feld, Default
  entspricht neutraler Einschaetzung).
- `ts: oe.created_at.isoformat()` (immer verfuegbar via `default=utcnow`).
- `typ: oe.einwand_typ` (immer verfuegbar, `nullable=False`).

## Open Follow-ups

1. **Meeting-Mode-UAT**: Plan fordert End-to-End-Test mit Meeting-Session
   (Analyse-Einwand + EWB-Klick desselben Typs binnen 5s -> 1 Entry; bei
   10s+ Abstand -> 2 Entries). Lokale DB + Test-Setup nicht verfuegbar in
   dieser Session -- wird im naechsten Deploy-UAT via getnerve.app verifiziert.
2. **ObjectionEvent-Schema-Extension**: Falls spaeter `zitat`, `intensitaet`
   oder `gegenargument_text` in ObjectionEvent persistiert werden soll,
   muss dieser Merge-Block aktualisiert werden, um diese Felder zu lesen
   statt der Defaults. Aktuell Scope-grenze korrekt: minimal-invasive
   Datenbereitstellung fuer Frontend-Kachel, keine Schema-Aenderung.

## Self-Check: PASSED

- [x] File exists: `routes/app_routes.py` (modified, committed as 497350d)
- [x] Commit exists: `git log --oneline | grep 497350d` -> match
- [x] Python AST valid
- [x] `from routes import app_routes` succeeds
- [x] `POLISH-54` marker in 3 locations (comment + 2 log-prints)
- [x] Lokale `einwaende_liste`-Code-Referenzen unveraendert (5 Hits)
- [x] `postcall['einwaende']`-Overwrite existiert (Z.539)
- [x] Block ist INSIDE outer-try (Scope fuer conv, db_conv, postcall)
- [x] Block ist NACH POLISH-38-Reconcile (Z.488), VOR FT-Logging (Z.544)
