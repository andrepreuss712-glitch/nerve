---
phase: quick-260424-h7u
plan: 01
subsystem: qa_pipeline
tags: [tabu-filter, safety-net, protected-words, context-aware-prompting]
key-files:
  modified:
    - services/qa_pipeline.py
decisions:
  - "Stem-prefix regex match (b_low[:-1] prefix) used for German inflection matching — 'Kosten' Begriff matches 'kostet' in Gegenargument via \\bkost prefix pattern"
  - "apply_tabu_safety_net protected_words param defaults to None for full backward compatibility — existing callers unchanged"
  - "build_protected_words placed above apply_tabu_safety_net in file to allow forward reference from call-site update"
metrics:
  completed: "2026-04-24"
  tasks: 2
  files: 1
---

# Quick Task 260424-h7u: Phase 08.5 Nachschaerfung Tabu-Filter Summary

**One-liner:** Context-aware two-section Tabu-Instruction + protected-words safety-net that respects deliberately placed Tabu-Woerter in User-Gegenargumenten.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Context-aware build_tabu_instruction | 227a9d4 | services/qa_pipeline.py |
| 2 | build_protected_words + protected-words Gate | c059e5d | services/qa_pipeline.py |

## Verification Outputs

### Task 1 verify (build_tabu_instruction):
```
OK
```
Assertions passed:
- `'BEHALTE das Tabu-Wort BEWUSST' in out` ✓
- `'UNSER Angebot' in out` ✓
- `'Respekt vor User-Gegenargumenten' in out` ✓
- `'Kosten' in out and 'Investition' in out` ✓
- `build_tabu_instruction({'daten':{'basis':{}}}) == ''` ✓

### Task 2 verify (build_protected_words + apply_tabu_safety_net):
```
OK
```
Assertions passed:
- `'kosten' in pw` (stem-prefix match on "kostet" in Gegenargument) ✓
- `'problem' not in pw` (not in any Gegenargument) ✓
- Protected "Kosten" preserved in output ✓
- Non-protected "Problem" still replaced with "Herausforderung" ✓
- Backward compat without protected_words arg: "Kosten" -> "Investition" ✓
- Empty profile returns empty set ✓
- Profile with empty einwaende returns empty set ✓

### Overall verification:
```
imports OK
```
All four function signatures unchanged (generate_qa_response, classify_utterance, match_faq, apply_tabu_filter).

## Before / After LLM Prompt Block

### Before (single-sentence):
```
WICHTIG: Bei folgenden Wörtern nutze bevorzugt die Alternative anstelle des Tabu-Begriffs:
Kosten → Investition
```

### After (two-section context-aware):
```
TABU-ALTERNATIVEN — kontext-abhängig anwenden:

Nutze bevorzugt die Alternative WENN es um UNSER Angebot geht
(Preis, Feature, Vorteil):
[Kosten → Investition]

BEHALTE das Tabu-Wort BEWUSST wenn:
- Es um Schaden/Verlust beim Kunden geht
  (z.B. "Was kostet Sie ein verlorener Deal?")
- Der Satz bewusst Problem-Awareness beim Kunden erzeugt
- Das User-eigene Gegenargument das Tabu-Wort bereits bewusst einsetzt

Default bei Unklarheit: Alternative nutzen.

Respekt vor User-Gegenargumenten: Wenn das User-Profil-Gegenargument ein
Tabu-Wort enthält, ist das meist bewusst gesetzt. Respektiere diese
Formulierung. Paraphrasiere NUR wenn wirklich nötig und ändere NIE
bewusst gesetzte Tabu-Wörter im User-Gegenargument.
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] German inflection mismatch in build_protected_words substring check**
- **Found during:** Task 2 verification
- **Issue:** Plan spec said use `b_low in t` (substring match), but "kosten" is NOT a substring of "kostet" (German verb conjugation). The plan's own verification test expected `'kosten' in pw` when the gegenargument is "Was kostet Sie ein verlorener Deal?" — which failed with pure substring check.
- **Fix:** Replaced `b_low in t` with stem-prefix regex `\b{b_low[:-1]}` (strips last char for inflection tolerance, guarded by `len > 3`). This correctly matches "kostet", "kosten", "kostete", "kosteten" etc. for Begriff "Kosten".
- **Files modified:** services/qa_pipeline.py (build_protected_words only)
- **Commit:** c059e5d

## Self-Check: PASSED

- `services/qa_pipeline.py` exists and imports cleanly ✓
- Commit 227a9d4 exists (Task 1) ✓
- Commit c059e5d exists (Task 2) ✓
- Both commits pushed to origin/main ✓
- No changes to prompt_pipeline.py (as specified — it already imports build_tabu_instruction by name) ✓
- No UI, DB, route, or template changes ✓
