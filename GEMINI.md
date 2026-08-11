# GEMINI.md — NERVE Cross-AI-Reviewer Context

> Dieser Kontext lädt automatisch wenn Gemini-CLI aus dem salesnerve-Repo aufgerufen wird (z.B. via `/gsd-review --gemini`). Kompakter Brief damit Reviews fokussiert sind.

## Was du gerade reviewst

NERVE — ein KI-gestützter SaaS-Vertriebsassistent für Kaltakquise-Telefonate. Solo-Founder-Projekt, vor dem Start (Early Access, ~50 Plätze).

**★ MARKT: US-FIRST (beschlossen 04.07.2026).** Jede Entscheidung zielt auf den US-Markt — Server-Region, Sprache, Preise, Recht, Coaching-Inhalte. ⚠ **Bis 11.08. stand hier „Deutsch, DACH-Markt"** — wer daraus Sprache, Recht oder Inhalte ableitete, lag falsch. **Ein späterer DACH-Start ist offen, aber kein Plan-Bestandteil.**

## Stack (du musst die Codebase nicht raten)

- **Backend:** Python Flask (mit SocketIO für Live-Streaming)
- **STT:** Deepgram (Streaming-Mode)
- **LLM:** Claude API — **direkt, nicht über AWS Bedrock**
- **TTS:** ElevenLabs — nur im Training, nicht in Live-Calls
- **DB:** **PostgreSQL** (live seit 12.05.2026; die frühere Angabe „SQLite (dev) → PostgreSQL (geplant)" war seit drei Monaten falsch)
- **Hosting:** Hetzner, nginx, Domain getnerve.app
- **Deployment:** systemd-Service `nerve`, Push-to-Deploy via `deploy.sh` mit Test-Tor auf dem Server

⚠ **Modell-Namen und Regionen stehen hier bewusst NICHT** — sie ändern sich, und eine Kopie hier veraltet still. Wenn ein Plan von einem bestimmten Modell abhängt: **im Code nachsehen** (`config.py`), nicht hier ablesen.

## Reset-Story (kritisch zum Verstehen)

Im April 2026 wurde nach einem Phase-08.5-„Nudelcode"-Fund (Tabu-System wirkungslos im QA-Pfad, Feature-Fakes, Test-False-Greens) eine vollständige Stabilisierungs-Phase gestartet. Daraus stammen die harten Bau-Regeln in `CLAUDE.md`, gegen die du Pläne prüfen sollst.

⚠ **Der frühere Fortschritts-Stand („6/14 Blöcke, Stand 2026-04-25", MASTER-AUDIT-v2 als Wahrheits-Quelle) stand hier bis 11.08. und war dreieinhalb Monate alt.** Die A–N-Block-Sequenz ist nicht mehr die führende Ordnung. **Der geltende Stand steht in `.planning/ROADMAP.md`** — und die verbindliche Reihenfolge in der Sektion „📍 ALLES AUF EINEN BLICK" der Vault-Roadmap (`Nerve-Vault/01 Roadmap.md`). **Hier steht bewusst keine Momentaufnahme mehr** — jede veraltet still, genau wie die eben ersetzte.

## Architektur-Pflöcke (NICHT in Frage stellen)

- **NERVE speichert KEIN Audio.** Ephemeral Processing — Audio rein, Analyse, sofort gelöscht. DSGVO-USP.
- **Cold Call:** KI hört NUR Berater-Stimme (Headset-Pflicht). EWB-Buttons statt Kunden-Stimme-Erkennung. Anonymisiertes Transkript.
- **Meeting:** Pop-up mit Consent-Vorlesetext. Mit Consent → volle Analyse. Ohne → Fallback Cold Call.
- **★ Server-Region folgt dem MARKT — US (korrigiert 2026-08-01).** ⛔ **Hier stand bis 11.08. „Alle Dienste auf EU-Servern: Deepgram EU, Claude AWS Bedrock Frankfurt, ElevenLabs EU, Hetzner Nürnberg" — als unantastbarer Pflock.** Das war der schwerste Fund einer Drift-Suche am 11.08.: Ein Reviewer mit diesem Kontext hätte **jeden korrekten US-Region-Plan als Verstoß angemahnt.** **Geltend ist:** Claude bleibt **US-direkt**, der Umzug nach AWS Bedrock Frankfurt ist **gestrichen** (für US-Kunden die schlechteste Variante — jede Antwort zusätzlich über den Atlantik, ~0,2–0,35 s bei rund 1 s Budget). Deepgram, ElevenLabs und der Server gehen beim US-Umzug in die **US-Region**. ⚠ **Ein EU-Server war nie eine DSGVO-Anforderung** — Verarbeitung in den USA ist mit den vorhandenen Verträgen zulässig; die DSGVO-Pflichten (Löschung, Auskunft, Datenschutzerklärung) bleiben trotzdem. **Führt ein Plan EU-Residenz oder Bedrock-Frankfurt als Ziel oder Blocker: das ist Drift — bitte melden.**
- **Call-Logs sind heilig** — Transkripte, EWB-Events, Objection-Events bleiben für Post-Call-Analyse + zukünftiges Fine-Tuning.
- **★ KEINE sichtbare Note (28.06., verschärft 02.08.).** NERVE zeigt dem Verkäufer **keine Zahl, die Qualität bewertet** — keine Gesamtnote, keine Note je Dimension, kein `coaching_score` als Anzeige, keine 7-Dimensionen-Aufschlüsselung, kein Ranking. Stattdessen: ein KI-Leser liest nach dem Anruf das Protokoll und liefert **Beobachtungen mit wörtlichem Beleg-Zitat** entlang von ~4 Dimensionen, dazu **genau EINE Sache fürs nächste Mal**, die vor dem nächsten Anruf wieder erscheint. **Zählen ist erlaubt** („4 offene Fragen"), **Benoten nicht.** Vorbedingung: der Zitat-Prüfer (`services/beleg_check.py`) wird angeschlossen, **bevor** irgendeine Bewertung angezeigt wird. **Schlägt ein Plan eine Punktzahl, ein Leaderboard oder einen Team-Vergleich vor: Drift — melden.**
- **★ Die Kaufbereitschaft (`kb_delta`/`kb_end`/`kb_verlauf`) wird ABGESCHAFFT (André 07.08.)** — nicht nur aus der Note genommen. ⚠ Achtung, der Name lügt: In **Trainings**-Sitzungen enthält `conversation_logs.kb_end` gar keine Kaufbereitschaft, sondern die Trainings-Gesamtnote. Entflechten, nicht blind löschen.
- **★ Der Chef bekommt die Bewertung NICHT (02.08.)** — auch nicht optional, auch nicht mit Häkchen. Begründung: Eine Einwilligung unter Kündigungsdruck ist keine, deshalb wird die Möglichkeit gar nicht erst gebaut. Rollen regeln **Verwaltung** (Sitze, Abrechnung), **nie** Einblick in Coaching-Inhalte.
- **★ Verkauft wird an kleine bis mittlere Teams, nicht an Einzel-Berater (André 11.08.).** Mehrere Berater einer Firma telefonieren gleichzeitig — Parallelbetrieb ist damit Verkaufs-Voraussetzung.
- **★ Kein lokales Entwickeln (27.05.).** Abnahme läuft **auf dem Live-Server**: commit → push → `bash deploy.sh production` → Test-Tor auf dem Server → Live-Test. **Ein Plan, der lokales `pytest`, `python app.py` oder `flask shell` als Verifikation vorsieht, ist abzulehnen.**
- **★ Schema-Änderungen NUR als Alembic-Revision.** Das `_migrate()`-Muster ist auf dem Live-Server **wirkungslos** — `app.py` verlässt die Funktion bei Postgres sofort. Wer danach baut, schreibt eine Migration, die **nie läuft**, und merkt es nicht.
- **★ Aufwand nie in Stunden**, nur 🟢 trivial / 🟡 mittel / 🔴 komplex.

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
