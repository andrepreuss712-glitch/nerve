# GEMINI.md — NERVE Cross-AI-Reviewer Context

> Dieser Kontext lädt automatisch wenn Gemini-CLI aus dem salesnerve-Repo aufgerufen wird (z.B. via `/gsd-review --gemini`). Kompakter Brief damit Reviews fokussiert sind.

## Was du gerade reviewst

NERVE — ein KI-gestützter SaaS-Vertriebsassistent für Cold-Calls (Deutsch, DACH-Markt, Pre-Launch). Solo-Founder-Projekt von André Preuß. Aktuell **Stabilisierungs-Phase** vor EA-Launch (50 Plätze, 50% Gründerrabatt).

## Stack (du musst die Codebase nicht raten)

- **Backend:** Python Flask (mit SocketIO für Live-Streaming)
- **STT:** Deepgram (EU-Endpoint, Streaming-Mode)
- **LLM:** Claude API — aktuell Haiku 4.5 live, Sonnet 4.5 für Post-Call. Sonnet-Upgrade + Prompt-Caching geplant in Block E.
- **TTS:** ElevenLabs (EU-Region) — nur im Training, nicht in Live-Calls
- **DB:** SQLite (dev) → PostgreSQL (geplant)
- **Hosting:** Hetzner CX22 (Nürnberg), nginx, Domain getnerve.app
- **Deployment:** systemd-Service `nerve`, Push-to-Deploy via `deploy.sh`

## Reset-Story (kritisch zum Verstehen)

Im April 2026 wurde nach einem Phase-08.5-"Nudelcode"-Fund (Tabu-System wirkungslos im QA-Pfad, Feature-Fakes, Test-False-Greens) eine **vollständige Stabilisierungs-Phase** gestartet:

- **MASTER-AUDIT-v2** (`.planning/audits/MASTER-AUDIT-v2.md`) ist die Wahrheits-Quelle
- 13 Launch-Blocker, 31 HIGH, 45+ MEDIUM Findings dokumentiert
- 14 Reparatur-Blöcke (A-N), in der Roadmap nach Komplexität sortiert (🟢 trivial / 🟡 mittel / 🔴 komplex)
- **6/14 abgeschlossen** (A, H, I, C, F, B) — Stand 2026-04-25 spätabends nach Block-B-Live-Deploy

## Architektur-Pflöcke (NICHT in Frage stellen)

- **NERVE speichert KEIN Audio.** Ephemeral Processing — Audio rein, Analyse, sofort gelöscht. DSGVO-USP.
- **Cold Call:** KI hört NUR Berater-Stimme (Headset-Pflicht). EWB-Buttons statt Kunden-Stimme-Erkennung. Anonymisiertes Transkript.
- **Meeting:** Pop-up mit Consent-Vorlesetext. Mit Consent → volle Analyse. Ohne → Fallback Cold Call.
- **Alle Dienste auf EU-Servern:** Deepgram EU, Claude AWS Bedrock Frankfurt, ElevenLabs EU, Hetzner Nürnberg.
- **Call-Logs sind heilig** — Transkripte, EWB-Events, Objection-Events bleiben für Post-Call-Analyse + zukünftiges Fine-Tuning.

## Was wir von dir als Reviewer wollen

**Du bist Cross-AI-Plan-Reviewer.** Plan wurde von Claude geschrieben, du gibst frische Augen.

**Fokus auf:**
- **Übersehene Edge-Cases** im konkreten Plan (z.B. "Was passiert mit Multi-Worker-Setup?", "Localhost ohne HTTPS?", "Bestehende DB-Daten?")
- **Threat-Modeling-Lücken** (besonders bei Security-/DSGVO-Plänen): Welcher Angriffs-Vektor ist nicht abgedeckt?
- **Backwards-Compatibility-Risiken** (bestehende User-Daten, OAuth-Sessions, Config-Files)
- **Schema-/Pattern-Drift** (verschiebt der Plan etwas das später wieder angefasst werden muss?)
- **Test-Strategie** (testet der Plan tatsächliche Integration oder nur Source-Presence?)
- **Dependencies zwischen Tasks** (Reihenfolge im Plan korrekt?)

**NICHT tun:**
- Generische "Best Practices"-Vorschläge die nicht spezifisch zum Plan passen
- "Ihr solltet auch noch X bauen" — Scope-Erweiterung. Wir haben 14 Blöcke, jeder hat klaren Scope.
- Stack-Wechsel-Vorschläge (Flask → FastAPI, SQLite → was-anderes). Stack steht fest.
- Re-Review der Audit-Findings selbst (sind in MASTER-AUDIT-v2 dokumentiert)
- Stundenangaben/Aufwandsschätzungen — werden im Projekt nicht mehr genutzt (siehe CLAUDE.md)

**Stil:**
- Direkt, klar, kurze Sätze (Anti-Berater-Stil von André)
- **Deutsch** — kein Englisch
- Konkret mit File:Line wenn möglich
- Findings priorisiert (was ist kritisch vs. nice-to-have)

## Code-Architektur-Quick-Reference

```
salesnerve/
├── routes/          ← Flask Blueprints (22 Routes)
│   ├── auth.py      ← Login/Register/OAuth
│   ├── app_routes.py ← Live-Call-Backend (/api/live, /api/beenden)
│   ├── profiles.py  ← CRUD für Sales-Profile (das User-konfigurierbare KI-Brief)
│   ├── training.py  ← Training-Modus
│   └── ...
├── services/        ← Business-Logic (20 Services)
│   ├── claude_service.py   ← LLM-Calls (Haiku live)
│   ├── qa_pipeline.py      ← Universal-Response-Pipeline (Phase 08.5)
│   ├── ewb_pipeline.py     ← Einwand-Behandlung-Pipeline
│   ├── deepgram_service.py ← STT-Streaming
│   └── ...
├── database/models.py ← SQLAlchemy 2.x ORM
├── static/           ← Frontend JS (app.js Classic, pip-launcher.js PiP)
├── templates/        ← Jinja2 Templates
├── tests/            ← pytest Suite (~266 passing nach Block C)
└── .planning/        ← GSD-Workflow-Artefakte
    ├── audits/       ← MASTER-AUDIT-v2.md ← Wahrheits-Quelle
    ├── phases/       ← Phase-Pläne + Summaries
    └── ROADMAP.md    ← GSD-Roadmap (kennt nicht unser Block-Modell)
```

## Wichtige Begriffe

- **EWB** = Einwand-Behandlung (Sales-Term)
- **PiP** = Picture-in-Picture (neuer Live-Coach-UI in Browser)
- **Classic-View** = alte Live-UI (`/live`), wird in Block F entfernt
- **Profil** = User-konfigurierbares KI-Brief mit Branche, Produkt, Einwänden, Phasen, Tabu-Begriffen
- **basis.\*-Schema** = Profil-JSON-Struktur seit Phase 08, vorher Top-Level-Keys (Schema-Drift)
- **GSD** = "Get Shit Done" Workflow-Tool (Plan-/Execute-/Review-Phasen)

## Aktive Block-Sequenz (Stand 2026-04-25 spätabends, nach Block B Live-Deploy)

| Block | Status | Was |
|---|---|---|
| A | ✅ 🟢 | Quick-Wins (4 LBs weg) — Phase 08.6 |
| H | ✅ 🟢 | Test-False-Greens raus — Phase 08.7 |
| I | ✅ 🟡 | Dead-Code-Prune (~643 Zeilen weg) — Phase 08.8 |
| C | ✅ 🟡 | Schema-Drift + LB-3-Komplettfix — Phase 08.9 (pytest 265→266) |
| F | ✅ 🟡 | Classic-View-Deprecation — Phase 08.11. ~2490 Zeilen weg, live deployt + 3 Hotfix-Commits (CR-01 stale pop(), CR-02+CR-03 url_for-Endpoint dashboard.index). |
| 08.12-Hotfix | ✅ 🟢 | DB-Naming-Cleanup (alte salesnerve.db raus, .env korrigiert, Rename-Code in app.py:710 entfernt) + onboarding_done-User-Migration als idempotente app.py-Migration (Block-C-Lücke gefixt) |
| **B** | ✅ 🔴 | **Auth-Härtung — Phase 08.10 (2026-04-25 spätabends).** 6 Plans in 6 Waves + 2 CR-Fixes, live deployed. CSRF (Flask-WTF), ProxyFix(x_for=1, x_proto=1), Session-Cookies (Secure/HttpOnly/SameSite=Lax/14d), Rate-Limit /api/login 10/min + /api/register 5/min mit 429-JSON, Session-Fixation-Fix, Org-Scoping-Assertion, oauth_id UNIQUE-Index mit sys.exit(1)-STOPS, **Microsoft-OAuth Email-Hijacking-Mitigation mit ECHTEM Redirect-Block + /auth/resend-confirm Endpoint (Variante B, rate-limited 3/10min)**. Cross-AI Round 1+2 → 13 Findings adressiert. Code-Review CR-01+CR-02 (TOCTOU im OAuth-Code) gefixt vor Approval. **23/23 must-haves verified, UAT 3/4/5 PASS, UAT 1/2 DEFERRED** (Multi-Tenant Org-only Config, kein Geschäfts-MS-Account verfügbar — Follow-up: erster echter EA-Vertriebler oder Azure AD Free Tenant). |
| E | aktiv 🔴 | Cost-Tracking + Caching + Sonnet-Upgrade. Nach F nur noch 3 inline-Anthropic-Clients zu konsolidieren (statt 5) |
| D | aktiv 🔴 | DSGVO-Paket (Password-Reset + 4 DSGVO-Routen + Audit-Events). Cross-AI Pflicht. **Foundation Block B liefert Auth-Patterns.** |
| J | wartet 🟡 | Routes-Härtung. **Plus Mini-Adds:** H-39 Profile-Save Sanity-Check + api_login Wrong-Creds-Response-Code (400→401 Hygiene aus Block-B-UAT) |
| L | wartet 🟡 | Test-Coverage für LBs |
| G | wartet 🟡 | PreCall-Briefing Re-wire |
| K | wartet 🟢 | DSGVO-Frontend-Mini |
| M | wartet 🔴 | Multi-Worker-Härtung + Race-Conditions. **Plus Mini-Audits aus Cross-AI-Review:** nerve_rt-Service-Scan + .env.example Environment-Parity. **Plus aus Block-B-UAT-Defer:** MS-OAuth Live-UAT nachholen falls bis dahin kein EA-User durchgelaufen. |
| N | post-launch 🔴 | Profil-Schema-Redesign (Pydantic) |

**Cross-AI-Setup Stand 2026-04-25 spätabends:** Gemini Pro Plan aktiv (gemini-3-pro statt Flash). Cross-AI-Hit-Rate bisher: **13 substantielle Findings** über alle Phasen (5 MASTER-AUDIT + 3 Block F + 5 Block B Round 2; Round 1 Block B = 8 Findings alle in Re-Plan adressiert). **Lerneffekt aus Block B:** Cross-AI hat den TOCTOU-Bug NICHT gefangen (gleiche Blindstelle wie Plan-Author und der zweite AI-Reviewer). Post-Execute Code-Review hat ihn erwischt. Cross-AI ist komplementär zu Code-Review, kein Substitut.

---

*Dieser Kontext ist immutable während eines Reviews. Bei Detail-Fragen Bezug auf MASTER-AUDIT-v2.md nehmen.*
