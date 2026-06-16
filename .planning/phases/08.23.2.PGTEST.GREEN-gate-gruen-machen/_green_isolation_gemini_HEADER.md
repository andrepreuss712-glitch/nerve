# CROSS-AI ENTSCHEIDUNGS-REVIEW — Isolations-Mechanismus für das NERVE Postgres-Deploy-Tor

Du bist ein Senior-Datenbank/Test-Infrastruktur-Engineer und unabhängige 3. Sicht. Lies den echten Code unten und gib eine begründete Empfehlung. Du bist NICHT der Autor — sei kritisch.

## Kontext
NERVE hat ein Deploy-Tor: `deploy.sh production` baut eine Wegwerf-Postgres-DB `nerve_test` (Schema per pg_dump von Prod + alembic), läuft die volle pytest-Suite dagegen, deployt nur bei grün. Ein Baseline-Wächter (`_baseline_cleanup_guard` in conftest.py) snapshottet bei Session-Start den erlaubten public-DB-Zustand `{pk: xmin}` und asserted nach JEDEM Test, dass der Zustand == Baseline ist (fail-closed bei Drift).

## Das Problem
Die Wegwerf-DB ist über den ganzen Lauf PERSISTENT (nur am Ende geteardownt). Der globale fail-closed Wächter verlangt, dass JEDER der ~600 Tests die DB picobello hinterlässt. Aber die Suite wurde über viele Phasen gegen Wegwerf-SQLite (OHNE Wächter) geschrieben — ~600 Tests räumen NIE auf. Ergebnis: **61 Test-Files leaken über 11 public-Tabellen → ~507 Wächter-Errors** → Tor dauerhaft rot. Test-Files einzeln umzuschreiben (~600 Tests) ist mehrtägig + Abrieb.

## Die Entscheidung — 3 Kandidaten für den Isolations-Mechanismus

**Option 1 — Auto-Reset, GESPALTEN:** Der Wächter HEILT Lecks selbst: nach jedem Test werden die test-erzeugten EXTRA-Rows (alles nicht in der Session-Start-Baseline) reverse-FK gelöscht + LAUT gewarnt (nodeid + Tabelle + PKs) → 0 Errors, Lecks sichtbar, nächster Test sauber. ABER gespalten: wenn die GESCHÜTZTE Baseline FEHLT oder MUTIERT ist (ein Test hat die id=1-Seed-Row oder prompt_versions gelöscht/geändert), BLOCKT der Wächter weiter rot — das ist ein echter Bug (Base-Seed-Zerstörung), gehört in die Triage, nicht still geheilt.

**Option 2 — REINER Auto-Reset:** Wie Option 1, aber OHNE Spaltung: ALLE Drift (extra + fehlend + mutiert) wird auto-geheilt + gewarnt, nichts blockt mehr außer echten Assertion-Fails. Einfacher. ABER: ein Test, der die Base-Seed-Row id=1 löscht, würde still geheilt → verliert den Fang für 7 bekannte Base-Seed-Lösch-Bugs.

**Option 3 — Transaktions-Rollback pro Test:** Generische Tests in eine Transaktion wickeln, am Ende ROLLBACK statt COMMIT (außer Security-Tests die Real-Commit brauchen). Klassisch. ABER kehrt PGTESTs bewusste Real-Commit-Entscheidung um: der RLS `after_begin`-Hook (db.py) + der Trigger `trg_mk_tenant_org` (feuert auf COMMIT, erzeugt tenant_orgs-Rows) + die RLS-Isolations-Security-Tests brauchen echte Commits. Rollback-only würde Commit-Zeit-Verhalten verstecken. Viele Tests committen zudem auf EIGENEN Sessions (nicht der wrappbaren), z.B. der Cap-Enforcement-App-Pfad → eine umschließende Transaktion kann die nicht zurückrollen.

## DEINE AUFGABE
1. **Welche Option** ist die richtige Grundrichtung? Begründung gegen den echten Code.
2. **Risiken/Schwächen JEDER Option** — besonders: maskiert sie echte Bugs (Req-7)? Bricht sie die Isolation (Cross-Test-Vergiftung)? Versteckt sie Commit-Zeit-Verhalten?
3. **Bei Auto-Reset (1/2):** Kann der Wächter eine FEHLENDE Baseline-Row überhaupt sauber heilen (Re-Insert mit Trigger-Nebenwirkungen?), oder ist Blocken (Option 1) der ehrlichere/sicherere Weg? Was ist mit MUTIERTEN Baseline-Rows?
4. **Reverse-FK-Lösch-Reihenfolge** für das Auto-Delete der Extra-Rows über 11 Tabellen — Fallstricke?
5. **Was übersehen wir?** Edge-Cases (Tests die auf eigener Session committen, Tests die absichtlich Baseline-nahe Daten schreiben, Security-Tests, Race auf die geteilte Connection).
6. Konkrete **Umsetzungs-Wachpunkte** für die gewählte Option.

Antworte strukturiert. Sei ehrlich: wenn Option 1 (mein Favorit) eine Schwäche hat, nenne sie. Wenn eine andere Option besser ist, sag warum.

---
# UNTEN: echter Code (conftest.py Wächter+Fixtures, db.py Hook+Trigger-Kontext, test_rls_isolation.py Real-Commit-Muster) + GREEN-SPEC + PGTEST-Closeout
---
