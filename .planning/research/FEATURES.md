# Feature Research

**Domain:** AI real-time sales coaching SaaS — DACH B2B, v1 launch (Milestone 1)
**Researched:** 2026-03-30
**Confidence:** MEDIUM — WebSearch and WebFetch were unavailable; findings are based on training knowledge (cutoff Aug 2025) of the sales coaching SaaS ecosystem (Gong, Chorus, Salesloft, Outreach, Mindtickle, Highspot, CloseAI). Patterns cited are stable and well-documented as of that date. Flagged where recency matters.

---

## Context: What NERVE Already Has

This is a subsequent-milestone research file. NERVE v0.9.4 ships with: live objection handling, buying readiness tracking, speech analytics, phase tracking, post-call analysis + PDF, CRM export, GDPR mode, script teleprompter, compact mode, AI training mode (ElevenLabs voice, 4 difficulty levels, 9 languages, scoring), profile system, dashboard with gamification, coach platform, onboarding (5 steps), early access waitlist with referrals.

The research question is: **What must still be true at launch** for onboarding, pricing UI/UX, and training scenarios in the DACH B2B context?

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete or untrustworthy.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Pricing page with clear tier comparison** | SaaS norm since ~2015; DACH buyers are especially price-conscious and comparison-oriented | LOW | Three tiers (69/59/49€) must be visible on a single page with feature diff table |
| **Annual/monthly billing toggle** | Standard on every serious SaaS pricing page; absence signals immaturity | LOW | Toggle must be present even if only monthly is active at launch — show the discount teaser |
| **Fair-use limits stated explicitly** | DACH B2B buyers read fine print; opaque limits erode trust immediately | LOW | "1,000 min live / 50 trainings per month — no hard cutoff" must appear on pricing and in app |
| **Onboarding wizard (step-by-step)** | Enterprise-adjacent B2B tools with profile setup must guide users; empty forms cause drop-off | MEDIUM | Already have 5-step onboarding; needs generic placeholders and dashboard style selection |
| **Progress indicator during onboarding** | Users need to know how far they are; reduces abandonment | LOW | Step X of Y, or visual stepper — likely already present but needs verification |
| **Contextual empty states** | First-time users see dashboards with no data; blank screens feel broken | MEDIUM | Dashboard heatmap, achievements, call history — all need "get started" prompts when empty |
| **In-app "what's next" after onboarding** | Users who complete setup but don't know what to do churn within 48h | LOW | A single CTA card: "Start your first training" or "Run a live call" |
| **Account/profile edit screen with clear labels** | Users expect to update what they entered during onboarding | LOW | Already exists; issue is demo-content placeholders leaking into generic accounts |
| **Training scenario library (browseable)** | Any coaching tool must offer pre-built scenarios; expecting users to create from scratch is friction | MEDIUM | 11 standard scenarios needed; must be categorized by industry/difficulty |
| **Free + Guided training mode distinction** | Power users need max-difficulty mode; beginners need scaffolding — both groups exist | LOW | Mode selection at training start; UI must clearly describe the trade-off (points vs. help) |
| **Post-call summary that's shareable/exportable** | B2B users share call notes with managers or CRM; PDF is minimum | LOW | Already built; ensure PDF looks professional (no NERVE internal branding artifacts) |
| **GDPR/legal disclosure before microphone use** | Legal requirement in DACH; also trust signal | LOW | GDPR banner fix is already in scope; must appear on first live session start |
| **Billing/subscription management in-app** | Users must be able to cancel, downgrade, see invoices without contacting support | MEDIUM | Stripe customer portal covers this; must be linked from account settings |
| **Error messages that explain what to do** | Microphone permission denied, API timeout, connection loss — all must be user-readable | LOW | Especially critical for live mode; a failed live session with a cryptic error destroys trust |

---

### Differentiators (Competitive Advantage)

Features that set NERVE apart from CloseAI, Gong, Chorus, and generic coaching tools.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Live objection coaching (not post-call)** | Gong/Chorus are post-call analytics; NERVE acts in the moment — core USP | HIGH (already built) | The positioning must be explicit on pricing/onboarding: "During the call, not after" |
| **GDPR-first as selling point** | CloseAI has poor GDPR perception; SalesEcho is US-only; NERVE can own "DACH-compliant AI coaching" | LOW (already built) | Must be on pricing page and in onboarding — not buried in footer |
| **Flat-rate pricing with fair-use (not per-seat credits)** | Sales managers hate credit-based billing; flat-rate feels safe to use heavily | LOW (pricing design) | Competitor Gong is notoriously opaque on pricing; NERVE's transparency is a trust signal |
| **ROI tracker in dashboard** | Connects feature usage to business outcome ("saved 3 deals this month"); reduces churn by making value visible | MEDIUM (new build) | Show estimated deal value retained based on objections handled; needs configurable average deal size input |
| **Post-training "what NERVE would have shown" preview** | Cross-sells live mode to training users; makes value of upgrade concrete | MEDIUM (new build) | Show 2-3 example coaching cards from the simulated call; CTA to activate live mode |
| **Training mode with AI voice customer (ElevenLabs)** | Most coaching tools use text-only roleplay; voice creates realistic pressure | HIGH (already built) | Differentiator must be shown in onboarding — demo the training voice before they start |
| **Coach platform with methodology transfer** | Teams can share objection libraries; coach can push scripts — unique in SME segment | HIGH (already built) | Not a v1 marketing focus (target is individual salesperson), but keep as upsell anchor |
| **9-language training** | DACH salespeople often sell in German, English, French; no competitor offers multilingual training at this price | MEDIUM (already built) | Feature must appear in training scenario setup; don't hide it in settings |
| **Compact 380px floating panel** | Fits on second screen or beside video call without covering content; CloseAI panel is reportedly intrusive | LOW (already built) | Show this in onboarding via screenshot/demo — it's a UX differentiator |
| **Genuine/real objection detection** | Distinguishes "vorwand" (stalling tactic) from real objection — affects which counter-argument to use | HIGH (already built) | Name this feature explicitly in UI; "We detected this as a price objection, not a stall" |

---

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create scope creep, technical risk, or strategic dilution for a solo-founder v1 launch.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Call recording / playback** | "Can I review the full call later?" — natural ask from sales managers | Requires audio storage, consent flows, data retention policies, GDPR Article 17 right-to-erasure — massive scope; also conflicts with GDPR-default-off positioning | Post-call summary PDF + CRM export covers 80% of the use case without storing audio |
| **Team leaderboard visible to colleagues** | Managers want it; makes coaching social | Creates political problems in sales teams ("why is my rank visible?"); discourages struggling reps from using the tool | Keep gamification private to the individual; coach platform has aggregate view |
| **Slack/Teams notification integration** | "Push my call summary to our Slack" — reasonable ask | Adds OAuth flows, webhook reliability, support burden; not a launch blocker | CRM export + email covers this; add Slack in v1.x when demand is confirmed |
| **Custom AI voice for training** | "I want my coach's voice" — ElevenLabs makes this feasible | Voice cloning consent, storage cost, UX complexity; solo-founder cannot support this | 9 pre-built language/gender combinations already provide adequate variety |
| **Free trial without credit card** | Growth-hacking standard | Bootstrap constraints + API costs (Deepgram, ElevenLabs) mean unlimited free trials will cost money immediately; also attracts low-intent users | Early Access with 50% Founder Discount + 14-day money-back is credible alternative |
| **In-app video tutorials / library** | Users want to learn the tool | Video production is time-consuming; tool must be self-explanatory at launch | Good onboarding wizard + contextual tooltips + one loom walkthrough linked from help icon |
| **AI-generated training scenarios on demand** | Power users want infinite custom scenarios | Requires prompt engineering, quality control, and scenario validation pipeline — not v1 scope | 11 standard scenarios + ability to describe a custom scenario in the profile covers 90% of needs |
| **Mobile app** | "Use it on my phone during field sales" | NERVE is a desktop overlay tool; mobile audio processing is architecturally different | Explicitly out of scope per PROJECT.md; positioning is "for phone/video calls at your desk" |
| **Hard usage block at fair-use limit** | Simpler to implement | Destroys trust when a rep is mid-call and gets cut off; DACH B2B buyers will churn immediately | Soft warning at 80% usage + "you're over limit, we'll discuss next month" — no hard stop |

---

## Feature Dependencies

```
[Pricing System (69/59/49 tiers)]
    └──requires──> [Stripe Payment Integration]
                       └──requires──> [Billing Portal in Account Settings]

[ROI Tracker in Dashboard]
    └──requires──> [Deal size config in Profile]
    └──enhances──> [Pricing System] (makes flat-rate value visible)

[Post-Training Preview "What NERVE Would Have Shown"]
    └──requires──> [Training mode completion event]
    └──enhances──> [Live Mode adoption] (cross-sell trigger)

[Free vs Guided Training Mode]
    └──requires──> [Training mode entry screen]
    └──enhances──> [11 Standard Scenarios] (both modes must work for all scenarios)

[11 Standard Scenarios]
    └──requires──> [Training mode: AI customer config per scenario]
    └──requires──> [Difficulty level system] (already built)

[Onboarding 3-Step Profile Wizard]
    └──requires──> [Profile system] (already built)
    └──enhances──> [Live Mode first run] (profile data drives AI context)
    └──enhances──> [Training quality] (product/objection data makes scenarios relevant)

[GDPR Banner in Live Mode]
    └──requires──> [Session start event]
    └──conflicts──> [Auto-start live session] (cannot auto-start without consent acknowledgment)

[Fair-Use Limits]
    └──requires──> [Usage tracking per user per month]
    └──requires──> [Soft warning notification at 80%]
    └──enhances──> [Pricing page] (stated limits make flat-rate credible)
```

### Dependency Notes

- **Stripe requires billing portal:** Without self-service cancellation, German consumer law (Fernabsatzgesetz) creates support burden. Link Stripe Customer Portal from account settings before launch.
- **ROI tracker requires deal size config:** Without a user-set average deal value, the tracker shows activity (calls handled) not outcomes (revenue retained). Deal size must be set in profile wizard.
- **Profile wizard enhances AI quality:** The 3-step wizard is not cosmetic — it populates the profile data (product, objections, industry) that the AI uses for live coaching context. Poor profile = generic coaching = perceived low AI quality.
- **Post-training preview conflicts with full NERVE-in-training:** Per PROJECT.md, "Trainingsmodus mit Live-NERVE-Antworten" is explicitly out of scope — it would devalue the live assistant. The post-training preview shows a read-only recap of what would have appeared, not a live overlay.

---

## MVP Definition

### Launch With (v1 — Milestone 1)

Minimum needed for a credible Early Access launch targeting 50 DACH B2B salespeople.

- [x] Live objection coaching (already built)
- [x] GDPR mode default ON with banner fix (fix in scope)
- [x] Compact mode working correctly (fix in scope)
- [ ] Pricing page: 3 tiers (69/59/49€), feature comparison table, fair-use limits stated — **not yet built**
- [ ] Stripe payment integration — **not yet built**
- [ ] Billing portal link in account settings — **not yet built**
- [ ] Onboarding: 3-step profile wizard with generic placeholders — **fix in scope**
- [ ] Onboarding: dashboard style selection — **fix in scope**
- [ ] 11 standard training scenarios — **not yet built**
- [ ] Free vs. Guided training mode selection — **not yet built**
- [ ] Post-training preview "What NERVE Would Have Shown" — **not yet built**
- [ ] ROI tracker in dashboard (even minimal: calls handled + estimated value retained) — **not yet built**
- [ ] Contextual empty states on dashboard (not blank heatmap/achievements on new account) — **not yet built explicitly**
- [ ] Generic profile placeholders (remove demo-content bleed) — **fix in scope**
- [ ] Fair-use usage tracking + soft warning at 80% — **not yet built**
- [ ] Impressum/AGB/Datenschutz pages — **not yet built (legal requirement)**

### Add After Validation (v1.x — after first 10 paying customers)

- [ ] Annual billing option — add when monthly retention is confirmed
- [ ] Slack integration for post-call summary — add when requested by ≥5 customers
- [ ] More training scenarios (beyond 11) — add based on which industries sign up
- [ ] Coach platform marketing — defer until individual-user base is established
- [ ] Loom walkthrough video linked from help — low effort, add in v1.1

### Future Consideration (v2+)

- [ ] English UI / US market — after DACH validation (per PROJECT.md)
- [ ] Custom TTS (Piper/Coqui replacing ElevenLabs) — at ~500 customers for margin improvement
- [ ] Fine-tuned sales AI (Llama/Mistral) — Milestone 4 per PROJECT.md
- [ ] AI-generated custom training scenarios — after standard 11 are validated
- [ ] Enterprise SSO / admin roles — only if inbound enterprise demand appears

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Pricing page (3 tiers, fair-use stated) | HIGH | LOW | P1 |
| Stripe payment integration | HIGH | MEDIUM | P1 |
| GDPR banner fix in live mode | HIGH | LOW | P1 |
| 3-step profile wizard (generic placeholders) | HIGH | LOW | P1 |
| 11 standard training scenarios | HIGH | MEDIUM | P1 |
| Free vs Guided training mode | HIGH | LOW | P1 |
| Post-training preview ("What NERVE would have shown") | HIGH | MEDIUM | P1 |
| Compact mode circle/toggle fixes | MEDIUM | LOW | P1 |
| ROI tracker in dashboard | MEDIUM | MEDIUM | P1 |
| Fair-use usage tracking + soft warning | MEDIUM | LOW | P1 |
| Contextual empty states on dashboard | MEDIUM | LOW | P1 |
| Annual billing toggle (UI only at launch) | LOW | LOW | P2 |
| Billing portal link in account settings | MEDIUM | LOW | P1 |
| Loom walkthrough video | LOW | LOW | P2 |
| Slack/Teams integration | LOW | HIGH | P3 |
| Call recording/playback | LOW | HIGH | P3 (anti-feature) |

---

## Competitor Feature Analysis

Sources: training knowledge of CloseAI, Gong, Chorus/ZoomInfo, Salesloft, Mindtickle, Highspot (as of Aug 2025). Confidence: MEDIUM.

| Feature | CloseAI (DACH) | Gong (Enterprise) | Chorus (Mid-Market) | NERVE Approach |
|---------|---------------|-------------------|---------------------|----------------|
| Live coaching during call | Yes (poor reviews for UX) | No (post-call only) | No (post-call only) | Yes — core USP, compact overlay |
| GDPR compliance | Weak (user complaints) | Complex setup required | US-centric | GDPR-first, default ON, server in DE |
| Pricing transparency | Not public | Not public (sales-led) | Not public | Fully transparent 3-tier flat-rate |
| Training mode with AI voice | Not known | Separate product | Separate product | Built-in, ElevenLabs voice |
| Flat-rate pricing | Unknown | No (per-seat + usage) | No (per-seat) | Yes — differentiation vs. all |
| DACH-language support | German | German (limited) | Limited | 9 languages including DE/AT/CH variants |
| Coach platform | Unknown | Enterprise only | Enterprise only | Built-in, multi-org |
| ROI tracker | Not known | Yes (enterprise) | Partial | To be built — links usage to deal value |
| Onboarding wizard | Unknown | Sales-assisted | Sales-assisted | Self-serve 3-step wizard |
| Post-call PDF export | Unknown | Yes | Yes | Yes — already built |

---

## DACH-Specific Considerations

These apply specifically to the target market and affect feature design decisions.

**Confidence: MEDIUM** (based on general DACH B2B SaaS market knowledge, not live research)

1. **Price anchoring matters more in DACH than US.** The 69/59/49€ ladder must show the middle tier as "recommended" with a visible discount anchor. DACH B2B buyers compare carefully — the pricing page must withstand scrutiny, not just scan.

2. **Datenschutz is a procurement concern, not a UX afterthought.** For any company with >10 employees, IT or legal may review NERVE before approving. The privacy page, data processing agreement (DPA/AVV), and the list of sub-processors (Deepgram, Anthropic, ElevenLabs) must be findable from the pricing page.

3. **"Kein Risiko" framing converts in DACH.** The "50% Gründerrabatt + 14-day money-back" early access offer should frame the money-back guarantee as the primary risk reducer, not the discount. DACH buyers are skeptical of discounts but respond to guarantees.

4. **Invoicing is expected, not optional.** DACH B2B buyers need proper Rechnungen (VAT invoices). Stripe handles this via Stripe Tax + Invoice settings, but it must be configured before launch. Missing VAT invoices will cause immediate churn from business accounts.

5. **Training scenario relevance for DACH B2B:** Software sales, industrial/manufacturing sales (Mittelstand), financial services, and logistics are the dominant DACH B2B verticals. The 11 standard scenarios should prioritize these over US-style SaaS/tech-startup scenarios.

---

## Onboarding UX: Specific Best Practices

**Confidence: HIGH** (well-established SaaS onboarding patterns, stable since 2020, consistent across Intercom, Appcues, user research)

### What works for B2B tool onboarding

1. **Profile wizard before first feature use.** Do not show an empty dashboard to a new user. The 3-step wizard must complete before the user reaches the dashboard. Rationale: the profile data (product, typical objections, industry) is what makes the AI useful — without it, the first impression of NERVE's coaching quality will be generic.

2. **Each step must have one clear job.** Step 1: "Tell us about your product" (name, industry, deal size). Step 2: "What objections do you face most?" (pre-filled options with free-text fallback). Step 3: "Choose your dashboard style + run a quick test." Three steps, one decision each.

3. **Example boxes are mandatory, not nice-to-have.** Placeholder text like "Enter product name" will result in entries like "asdf" from impatient users. Example boxes ("e.g. ERP software for manufacturing companies") dramatically improve data quality. This directly improves AI coaching output.

4. **Dashboard style selection should be visual, not a dropdown.** Show two thumbnail screenshots (e.g., "Compact" vs. "Full") with a single click to select. DACH users distrust dropdown menus for visual choices.

5. **Skip is acceptable but must explain consequence.** If a user skips the profile wizard, show a persistent "Your coaching is running on defaults — complete your profile to get relevant advice" banner. Urgency without blocking.

6. **The first training session is the activation event.** Not account creation, not onboarding completion — the moment a user completes their first training and sees their score is when they understand the product. Everything in onboarding should funnel toward this moment.

### What does not work

- Long forms with 12+ fields on one screen (already avoided with 12-section profile hidden behind accordion)
- "Watch a 3-minute intro video" as step 1 — DACH users skip it
- Email verification gates before exploring the product
- Forcing credit card before showing value (applies to trial model, less critical for early access model)

---

## Training Scenario Design: Expectations

**Confidence: MEDIUM** (based on Mindtickle, Highspot, and sales enablement tool patterns; NERVE's specific scenario set is novel)

### What makes a training scenario feel professional

1. **Realistic persona with backstory.** "You're calling the IT manager at a 200-person logistics company. She's been with the company 8 years and is skeptical of new software vendors." Not just "a potential customer."

2. **Scripted opening from the AI customer.** The AI customer should start the call, not wait. Opens with a realistic neutral response ("Ja, ich hab kurz Zeit, was ist das genau?") — makes the rep react, not perform.

3. **Progressive difficulty within each scenario.** Even a "Hard" scenario should start medium and escalate. Cold starts at maximum resistance cause frustration, not learning.

4. **Objection variety within scenario type.** A "Price Objection" scenario should surface price, ROI, budget timing, and competitor comparison objections — not just "it's too expensive" on repeat.

5. **Debrief with specific moment feedback.** "At minute 2:14 you said X, which was good because Y. At minute 3:01 you missed the opportunity to Z." Not just a score.

### Recommended 11 scenarios for DACH B2B launch

Based on what's most common in DACH Mittelstand sales contexts (MEDIUM confidence):

1. Cold call — IT decision maker, software skeptic
2. Cold call — procurement contact, pure price focus
3. Discovery call — engaged prospect, genuine qualification
4. Demo call — prospect is interested but comparing competitors
5. Demo call — prospect is disengaged, checking phone
6. Objection handling — "We already have a solution"
7. Objection handling — "Too expensive, no budget right now"
8. Objection handling — "We need to involve more stakeholders"
9. Closing call — prospect is warm but dragging feet
10. Closing call — last-minute price negotiation
11. Renewal/upsell — existing customer, value challenge

Each scenario should have all 4 difficulty levels, so 11 × 4 = 44 scenario-difficulty combinations total.

---

## Sources

- Training knowledge: Gong, Chorus, Salesloft, Mindtickle, Highspot, CloseAI product positioning (as of Aug 2025)
- SaaS onboarding patterns: Intercom Product Tours, Appcues best practice guides, ProductLed.com onboarding research (well-established as of 2024)
- DACH B2B SaaS market: General knowledge of DACH enterprise sales culture, GDPR Article 28 (DPA requirements), German invoicing law (§ 14 UStG)
- Feature prioritization: Derived from PROJECT.md constraints (bootstrap, solo-founder, 14 days/month, 50 early access target)
- Note: WebSearch and WebFetch were unavailable during this research session. All findings reflect training knowledge. Recency-sensitive claims (competitor pricing, specific product features) should be spot-checked before roadmap finalization.

---

*Feature research for: AI real-time sales coaching SaaS (NERVE) — DACH B2B, Milestone 1 Launch*
*Researched: 2026-03-30*
