---
status: investigating
trigger: "deploy.sh production POST-SUITE fail-closed: '[deploy] FEHLER: crm.* nicht leer nach Test-Lauf (2 Leak-Rows)'. Tests grün (638 passed), Prod NICHT neugestartet. triage.sh übersieht es (kein POST-SUITE-crm/training-Leak-Check). Echtes Grün = voller Gate inkl. POST-SUITE."
created: 2026-06-16
updated: 2026-06-16
phase_ref: 08.23.2.PGTEST.GREEN
---

# Debug: crm.* 2-Row-Leak nach voller Suite (POST-SUITE-Gate fail-closed)

## Current Focus
hypothesis: Ein crm-schreibender Test räumt seine crm.*-Rows im Teardown nicht (oder nur public.*) weg.
  Der in-pytest-Baseline-Wächter bewacht NUR public.* -> crm-Leak wird erst vom deploy.sh-POST-SUITE
  (scripts/_crm_leak_count.py als postgres, RLS-bypassed) gefangen. Da der Gate vorher immer known-red
  war (pytest rot), wird der POST-SUITE-Check JETZT zum ersten Mal erreicht -> langjähriger Teardown-Gap
  exponiert. Verdacht: RLS-Gruppe two_tenant_memories oder ein anderer crm-Writer (NICHT anonymizer-logic).
next_action: nerve_test wie der Gate provisionieren, volle Suite -m "not live and not perf" laufen, DANN
  als postgres crm.* inhaltlich inspizieren (name/tenant_id-Prefix zeigt den Test) BEVOR Drop.

## Prozess-Lücke (dokumentiert)
triage.sh fährt KEINEN POST-SUITE-crm/training-Leak-Check. deploy.sh schon. Ab jetzt: echtes Grün =
voller Gate inkl. crm.*==0 UND training.transcript_archive==0, nicht nur triage.sh-pytest-grün.

## Evidence
- timestamp: 2026-06-16 — deploy.sh POST-SUITE: crm.* == 2 Leak-Rows nach voller Suite. pytest selbst grün.
