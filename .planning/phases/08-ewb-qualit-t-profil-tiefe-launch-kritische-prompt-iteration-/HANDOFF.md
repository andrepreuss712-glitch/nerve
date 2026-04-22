# Phase 08 Handoff — 2026-04-22 Abend

**Pausiert am:** 2026-04-22 Abend (Europe/Berlin)
**Resume:** morgen früh — `/gsd-resume-work 08` oder direkt Browser-Smokes durchlaufen und `approved` melden.

## Status

| Layer | Status |
|-------|--------|
| Code durch alle 6 Waves | ✓ Abgeschlossen, 34 Commits auf main |
| Claudian-Tooltip-Review (Plan 04 Task 3) | ✓ approved nach 2,3x-ROI-Fix (commit `4cef4b1`) |
| Test-Isolation (Seed-Leak) | ✓ gefixt (commit `66d1007`) — 229/231 Suite-Tests grün |
| Code-Review (08-REVIEW.md) | 18 advisory findings (2 Critical pre-launch must-fix, 9 Warning, 7 Info) — NICHT gefixt |
| Programmatische Verification | ✓ 6/6 must-haves VERIFIED (08-VERIFICATION.md) |
| Browser-Visual-Smoke | ⏸ pending — 8 Items in 08-HUMAN-UAT.md, ~15 Min |
| Wave 7 Offline (Quality-Gate Messung) | ⏸ pending — 15 Training-Sessions + 5 echte Calls + 100 EWB-Ratings, kommende Tage |
| Phase-Status in ROADMAP/STATE | `in_progress` (nicht auf complete gesetzt) |

## Morgen als Erstes

1. `python app.py` starten, localhost:5000 öffnen
2. 8 Browser-Smoke-Items aus `08-HUMAN-UAT.md` durchlaufen (~15 Min)
3. Entweder:
   - **Alle grün** → "approved" melden → Phase 08 wird in ROADMAP/STATE als complete markiert
   - **Issues gefunden** → Fix-Liste zurückmelden → `/gsd-plan-phase 08 --gaps` erstellt Gap-Closure-Phase

## Nach Phase-08-Completion (zeitlich flexibel)

### Pre-Launch Must-Fix (aus 08-REVIEW.md, vor Early-Access-Go-Live):

- **CR-01** Thread-Safety: `ls.state['session_anrede']` + `ls.state['user_id']` in `services/prompt_pipeline.py:196-204` und `services/claude_service.py:659,722` ohne `state_lock` gelesen
- **CR-02** Anrede-Whitelist matcht nur exakt `('Du', 'Sie')` — Mixed-Case/Whitespace fällt silent auf Profile-Default zurück

Route: `/gsd-code-review-fix 08`

### Wave 7 Offline (Quality-Gate-Messung)

- 15 Training-Session-Recordings
- 5 echte Calls mit neuer EWB-Pipeline
- 100 EWB-Ratings (Mindest-Zielwert aus Plan)
- **Ziel:** 80% sofort-vorlesbar, Varianz-Range <30 über Szenarien A/B/C
- **Tooling:** `/admin/ewb/rating-template` für strukturiertes Rating, `/admin/ewb/quality` für Gate-Status

### Backlog (separates Ticket)

- `/gsd-quick` "fix exchange_rates test failures (pre-existing from Phase 4.7.2, blocker für saubere CI)" — 2 Failures in `tests/test_exchange_rates.py`, nicht durch Phase 08 verursacht

## Offene advisory-Issues in 08-REVIEW.md (nicht-blockierend, nicht gefixt)

Siehe Report für volle Liste. Highlights:
- **WR-04** `<path:einwand_key>` im Admin-Routing bricht bei Einwand-Keys mit Slashes (`'Zeit/Aufschub'`, `'Entscheidungsträger'`) — real-world impact sobald Andre diese Kategorien manuell ratet
- **WR-03** 3 verschiedene Profile-Einwand-Match-Strategien in `handle_manual_ewb`, `api_ewb_trigger`, `_build_system_prompt` — Konsistenz-Risiko
- **WR-05** `_seed_ewb_v2` + Block-E-Backfill setzen is_default=1 auf beide ewb-Varianten bei jedem Start — A/B-Semantik subtle broken

## Operator-Action (Deploy-Tag, separat)

- `python scripts/migrate_branche_to_enum.py --run` auf Prod-DB (nur `--dry-run` bisher ausgeführt, 4 Profile in lokaler DB würden migrieren)
- Pre-Deploy-Backup: `cp database/nerve.db database/nerve.db.bak_YYYYMMDD`
- Post-Deploy: `journalctl -u nerve | grep 'EWB.*v2-modular'` um A/B-Routing-Traffic zu sehen
