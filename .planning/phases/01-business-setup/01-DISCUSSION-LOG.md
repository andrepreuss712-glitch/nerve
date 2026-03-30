# Phase 1: Business Setup - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.

**Date:** 2026-03-30
**Mode:** Auto (--auto flag active — all selections made by Claude at recommended defaults)

---

## Area 1: Bank Account Choice

**Q:** Which bank account — Kontist or Finom?
**Options presented:** Kontist (DATEV-compatible, established for DE solo-founders), Finom (newer, also solid)
**Auto-selected:** Kontist
**Reason:** DATEV integration simplifies tax reporting with count.tax; established track record; Stripe payouts supported.

---

## Area 2: Task Sequencing

**Q:** Which tasks run in parallel vs sequentially?
**Auto-selected:** Parallel where possible
- Gewerbeanmeldung → Geschäftskonto → USt-IdNr (sequential dependency)
- count.tax first call: parallel to Gewerbeanmeldung (no dependency)
- Stripe signup: start immediately, finalize business verification after Geschäftskonto

---

## Area 3: Steuerberater Scope

**Q:** What to cover in count.tax first call?
**Auto-selected:** Kleinunternehmerregelung decision + §14 UStG SaaS invoicing + Betriebsausgaben (API costs) + income treatment. Bookkeeping setup deferred to first €1k MRR.

---

## Area 4: Stripe Timing

**Q:** When to set up Stripe relative to BIZ tasks?
**Auto-selected:** Start Stripe account immediately; complete business verification after Geschäftskonto is open.

---

*Discussion log generated automatically by --auto mode*
*2026-03-30*
