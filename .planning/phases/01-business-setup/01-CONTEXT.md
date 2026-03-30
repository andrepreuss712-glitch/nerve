# Phase 1: Business Setup - Context

**Gathered:** 2026-03-30
**Status:** Ready for planning
**Mode:** Auto (--auto flag — all decisions chosen at recommended defaults)

<domain>
## Phase Boundary

Register the legal business entity (Gewerbeanmeldung), open a dedicated business bank account, file for USt-IdNr, and engage a tax advisor — all prerequisite administrative work that must be done before Stripe can be verified and payments accepted. This phase has no code. It runs in parallel with Phase 2 (Product Fixes).

**Hard gate:** Phase 4 (Payments & Legal) depends on this phase — Stripe account verification requires both a registered business and a business bank account.

</domain>

<decisions>
## Implementation Decisions

### Task Sequencing

- **D-01:** Gewerbeanmeldung is the first action — file this week (online at Stadt Iserlohn portal or in person at Gewerbeamt). Everything else unblocks from here.
- **D-02:** Geschäftskonto opens after Gewerbeanmeldung is confirmed (Kontist and Finom both require proof of registration). Target: same week if online, otherwise within 3-5 days.
- **D-03:** USt-IdNr application (Bundeszentralamt für Steuern) is filed as soon as Gewerbeanmeldung confirmation is in hand — this takes 2-4 weeks to arrive, so file early.
- **D-04:** count.tax first call can happen this week in parallel to Gewerbeanmeldung — no dependency.
- **D-05:** Stripe account signup can begin immediately (personal account, begin KYC); finalize business verification after Geschäftskonto is open. Do not wait for Stripe before starting other BIZ tasks.

### Bank Account Choice

- **D-06:** Use **Kontist** as the business bank account. Rationale: DATEV-compatible exports (makes count.tax work easier), established track record for German Einzelunternehmer/Freiberufler, real IBAN, no monthly fee at base tier, Stripe payouts supported. Finom is an alternative if Kontist rejects (newer, also solid) — but try Kontist first.

### Tax Advisor Scope (count.tax First Call)

- **D-07:** First call with count.tax should cover: (1) Kleinunternehmerregelung entscheidung — skip it, NERVE is building toward >22.000€ revenue, regular USt is correct from day 1; (2) §14 UStG invoice requirements for SaaS subscriptions (Stripe generates invoices — confirm this satisfies DE requirements); (3) how to handle Anthropic/Deepgram/ElevenLabs as Betriebsausgaben; (4) income treatment for Early Access vs regular subscriptions.
- **D-08:** Do NOT ask count.tax to set up bookkeeping yet — too early, too few transactions. Agree on a check-in at first €1k MRR.

### Stripe Account Approach

- **D-09:** Register Stripe account under personal identity initially; add business details (Gewerbeanmeldung, Geschäftskonto IBAN) as they become available. Stripe verification is non-blocking for account creation — blocking only for payouts.
- **D-10:** Use **Stripe Payments Europe, Ltd.** as the contracting entity (EU) — this is automatic for German registrations but verify in Stripe dashboard after account creation.

### Claude's Discretion

- Exact Kontist plan tier (free vs paid) — choose free tier unless a specific paid feature is required for Stripe integration.
- Exact wording of Gewerbeanmeldung business description — "Entwicklung und Betrieb von Software als Dienstleistung (SaaS)" is standard.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Context
- `.planning/PROJECT.md` — Business constraints, bootstrap philosophy, Einzelunternehmer → UG transition trigger
- `.planning/REQUIREMENTS.md` — BIZ-01, BIZ-02, BIZ-03, BIZ-04 acceptance criteria

### Research
- `.planning/research/PITFALLS.md` — Pitfall 12: Business setup as critical path blocker (3-5 week lead time details)
- `.planning/research/STACK.md` — Section on DSGVO/AVV requirements; Stripe EU entity notes

No external specs — business setup is procedural, no ADRs required.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- None — this phase has no code deliverables.

### Established Patterns
- None applicable.

### Integration Points
- Phase 1 output (verified Stripe account + Geschäftskonto) feeds directly into Phase 4 (Payments & Legal). Phase 4 planner should be aware that Stripe account may be in different states (personal registered, business unverified, fully verified) depending on timing.

</code_context>

<specifics>
## Specific Ideas

- André is in Iserlohn → Gewerbeamt Iserlohn, Stadthaus, Werner Hellweg 101 (confirm current address).
- Steuerberater: count.tax specifically chosen (mentioned in GSD Init document).
- Bank: Kontist preferred (Finom as fallback).
- USt-IdNr: Takes 2-4 weeks — this is the longest single item. File immediately after Gewerbeanmeldung.
- Rechtsform: Einzelunternehmer now → UG/GmbH planned at 3-5k€ MRR (from PROJECT.md). count.tax should advise on trigger timing.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 01-business-setup*
*Context gathered: 2026-03-30*
