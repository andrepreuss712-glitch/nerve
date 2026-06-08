---
slug: phase-classify-int-str-fix
status: complete
date: 2026-06-08
commit: 8db6278
---

# Summary: phase_classify '>' int vs str

## Was geändert
`services/deepgram_service.py:902` (handle_manual_mode_toggle):
`st['current_phase'] = 'opener' if new_mode == 'cold_call' else 'greeting'`
→ `st['current_phase'] = 1`

1 Zeile (+ Erklär-Kommentar). Sonst nichts.

## Warum (Root Cause an der Quelle, kein Pflaster)
`current_phase` ist kanonisch **INT 1-6** — alle Reader (claude_service.py:992/1061/1085)
und Consumer (detect_phase, classify_phase, PHASE_BUTTONS) erwarten int. Der EINZIGE
abweichende Writer war der manual_mode_toggle-Handler, der ein Display-Label
('opener' für cold_call, 'greeting' für gatekeeper) hineinschrieb. Beides ist das Label
für **Phase 1** (_PHASE_NAMES_COLD_CALL[1]='opener', _PHASE_NAMES_GATEKEEPER[1]='greeting').
Danach: detect_phase (ki_logik.py:178) `raw_phase > current_phase` → `int > 'opener'`
→ `'>' not supported between instances of 'int' and 'str'` → Phasen-Klassifikation tot
(8x live in 14 Tagen). Fix setzt int 1 → Single-Source-of-State, Label kommt weiterhin
aus _PHASE_NAMES_BY_MODE. Kein Cast an der Vergleichsstelle.

## Verifikation
- Prod-Tests `test_phase_classifier.py`: 3 passed, 2 skipped ✓
- Datei live auf Prod (deepgram_service.py:906 = `st['current_phase'] = 1`) ✓
- Service neu gestartet 2026-06-08 12:47 UTC, `systemctl is-active` = active, /api/health = 200 ✓

## Deploy-Notiz (wichtig)
`bash deploy.sh production` lief, aber der **pytest-Gate wurde von ~120 pre-existing,
unrelated Failures abgebrochen** (SQLite-in-memory kann Postgres-Schema `crm.` nicht
anlegen → `unknown database crm` in test_ft_seed/test_tenant_orgs/test_revenue_webhook/…).
Das ist die in CLAUDE.md Stufe 2 dokumentierte bekannte Schwäche. Der Gate kommt nie bis
zum Restart. → Fix wurde nach André-Freigabe per **manuellem `sudo systemctl restart nerve`**
live gebracht. Der Deploy-Test-Gate-Defekt bleibt offen (separate Aufgabe, nicht dieser Bug).

## Offen / Follow-up
- Test-Gate-Fix (crm-Schema in SQLite-Tests) als eigene Aufgabe — blockiert sonst jeden
  künftigen `deploy.sh production`-Restart.
- André-Verifikation ausstehend: kurzer Test-Call **mit manual_mode_toggle** (der Trigger),
  dann `journalctl -u nerve | grep phase_classify` → loop-error muss weg sein, stattdessen
  `[phase_classify] X→Y`-Übergänge.
