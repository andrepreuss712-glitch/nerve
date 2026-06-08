---
slug: engine-json-extract-block2-3
created: 2026-06-08
type: quick
---

# Quick Fix: Block 2+3 json_extract → Postgres (Folge-Pass)

Folge zu 20260608-ewb-json-extract-postgres-fix. Schließt den dort dokumentierten
Blast-Radius: die restlichen zwei json_extract-Blöcke in services/integration_engine.py.

## Scope
- Block 2 Call-Schwaeche-Check (Z.186-194, run_postcall_engine)
- Block 3 Training-Schwaeche-Check (Z.254-261, run_posttraining_engine) — inkl. Boolean-Sonderfall
NUR diese zwei Blöcke. Siehe SUMMARY.md für Details + Verifikation.
