# Phase 08.13 — Deferred Items

## DEFERRED-01: claude_service.py + training_service.py Refactoring

**Status:** Deferred post-Block-E (Anti-Scope-Creep)
**Scope:** claude_service.py (1400+ Zeilen), training_service.py (1200+ Zeilen)
**Befund:** Beide Dateien sind zu gross fuer wartbaren Code. Fix-vs-Rebuild-Entscheidung steht aus.
**Warum jetzt nicht:** Block E ist Cost+Caching+Sonnet. Ein kompletter Rebuild wuerde den Scope sprengen und Launch-Kritisches verzoegern.
**Wann:** Separates Refactoring-Ticket nach Launch (Milestone 2 oder Block N post-launch).
**Empfehlung:** claude_service.py aufteilen in: claude_live_service.py (EWB/Analyse), claude_postcall_service.py (PostCall/CRM), claude_training_service.py (Training).
**Bestaetigt durch:** Gemini Cross-AI Review 2026-04-26 (REVIEWS.md, Point 4).
