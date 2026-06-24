# Backlog

**Purpose:** Bug-Fix und Polish-Items, die außerhalb aktiver GSD-Phasen entdeckt wurden und auf eine spätere dedizierte Bug-Fix-Phase warten. Jeder Eintrag enthält ID, Severity, Kontext und vermutete Root-Cause-Hinweise.

**Convention:** IDs folgen dem POLISH-XX Schema (kontinuierlich mit REQUIREMENTS.md POLISH-24..37). Schweregrade: `critical` (blockiert User-Flow), `high` (fehlerhafte Daten), `medium` (Metriken/Persistenz), `low` (Kosmetik).

---

## Open

### ANON-OVER-AGGRESSIVE — Anonymisierung schwärzt Normal-Wörter (z.B. "Ihnen" → [PERSON_A]), vergiftet DB + Live-Vorschlag

- **Severity:** high (Daten-Qualität für Training/Auswertung + Live-Antwort-Lesbarkeit)
- **Entdeckt:** André 2026-06-22 (TAXO1-Live-Test + Vorschlags-Erfassungs-Diskussion). Beleg: `intent_event.triggering_text` = "Verstehe, [PERSON_A] ist das gerade zu teuer" — das normale Wort "Ihnen" wurde fälschlich als Person erkannt + geschwärzt.
- **Zwei getrennte Schichten (beide gehören gefixt):**
  - **(1) Anonymisierer ist ÜBER-AGGRESSIV:** markiert Nicht-PII (Anrede-/Normal-Wörter wie "Ihnen", "Sie") als Person → vergiftet alle gespeicherten Trainings-/Auswertungs-Daten (DPO-Korpus + Coaching). Erkennungs-Tuning nötig (services/anonymization.py — Schwellen/Modell/Whitelist gängiger Anrede-/Funktionswörter).
  - **(2) André-Direktive: der LIVE-Vorschlag an den Berater darf GAR NICHT anonymisiert sein.** Der Berater hat die echten Namen eh gehört; "[PERSON_A]" im vorgelesenen Vorschlag liest sich "komplett scheiße". → Live-Vorschlag mit ECHTEN Namen anzeigen; NUR die gespeicherte Kopie wird (sauber) anonymisiert, und zwar WÄHREND des Calls (Mapping noch aktiv), nicht am Call-Ende.
- **Verwandt:** ANON-LIVE-ANSWER (dieselbe Wurzel — anonymisierter Text im Live-Pfad). Zusammen behandeln.
- **Routing:** TAXO3 (Antwort-Qualität / Live-Pfad) + eigener Anonymisierungs-Tuning-Pass für Schicht (1). Wirkt auch auf die TAXO2-Vorschlags-Erfassung (Plan 08): gespeicherte suggestion_text-Kopie muss SAUBER anonymisiert sein, nicht über-geschwärzt.

### NAME-FILL — NERVE setzt echten Namen in Vorschläge ein (gesprochener Name schlägt Briefing)

- **Severity:** low (UX/Lesbarkeit — heute zeigt NERVE den Platzhalter wörtlich)
- **Entdeckt:** André 2026-06-24 (Plan-09-Live-Test, Nebenbefund). Der vermeintliche `[PERSON_A]`-Bug war KEIN Anonymisierungs-Leak (Logging zeigte alle Anzeige-Zeilen `anon=false`), sondern ein **wörtlicher Profil-Platzhalter** „[Name des Entscheiders]" / „[Name VL]" in den Gatekeeper-Vorschlägen (sieht aus wie ein Anonymisierungs-Token, ist aber eine Vorlagen-Lücke).
- **Soll (André, kanonisch in Vault `Soll-Verhalten §2`):** NERVE darf den echten Namen statt des Platzhalters einsetzen — liest sich angenehmer. ABER die Wahrheit ist der im Call **GESPROCHENE** Name, NICHT stur der PreCall-Briefing-Name: nennt der Berater/Sekretär im Gespräch einen anderen Namen (oder lag das Briefing falsch) → gesprochener Name gewinnt, NERVE stellt um. NIE Briefing-Name über den im Call gehörten.
- **Routing:** TAXO3 (Antwort-Qualität / `build_answer_context` — Namens-Slot, Quelle im-Call-Name > Briefing) + Sekretär→Entscheider-Übergabe (Roadmap Phase I `context_notes`). Nutzt den ohnehin pro Call geführten Anonymisierer-Namens-Bestand. Nicht launch-blockierend.

### ANSWER-ECHO — NERVE-Vorschlag wiederholt die Quittung, die der Berater schon gesagt hat

- **Severity:** medium (Antwort-Qualität / Gesprächs-Fluss — Kernfeature Live-Assistent)
- **Entdeckt:** André 2026-06-24 (Plan-08-Live-Test). Erfasste Vorschläge starteten mit „Verstehe ich, gerade ist viel los…" / „Verstehe ich total. Gerade läuft viel…" — NERVE quittiert den Einwand nochmal, den der Berater gerade SELBST quittiert hat („Ich verstehe Herr Meier, Sie haben keine Zeit"). Doppelt, stört den Fluss, klingt nach Papagei.
- **Soll (kanonisch Vault Soll-Verhalten §2):** NERVE wiederholt NICHT die Berater-Quittung, sondern knüpft AN — der nächste Zug (offene Gegenfrage/Haken), nicht die Empathie, die der Berater schon geliefert hat. Bsp: Berater „ich verstehe Herr Meier, keine Zeit" → NERVE „Darf ich kurz fragen: …".
- **Mechanik:** Antwort-Engine hat `triggering_text` + Berater-Äußerung → prüft ob der Berater den Einwand schon quittiert hat → überspringt die Quittung.
- **Routing:** TAXO3 (`build_answer_context`, Paradigma-Reset §4.5 — „verstehen+helfen statt Floskel"). Verwandt: POSTCALL-COACH-QUALITY (schwache/floskelhafte Antworten).

### DEPLOY-TAR-NO-DELETE — deploy.sh entfernt gelöschte Dateien NICHT auf dem Server (Datei-Leichen)

- **Severity:** medium (Deploy-Korrektheit — bricht den Test-Gate bei jeder Datei-Löschung + lässt toten Code live)
- **Entdeckt:** TAXO1 Welle-6 Cleanup-Deploy (2026-06-18). Cleanup löschte lokal `services/ewb_pipeline.py` + `tests/test_ewb_pipeline.py`; beide blieben als Leichen auf Prod (`/opt/nerve/app/...`), die stale Test-Datei (importiert entferntes `_seed_ewb_v2`) ließ den ersten `deploy.sh production`-Gate-Lauf ROT (ImportError). Manuell per `ssh rm` entfernt, dann grün.
- **Root-Cause:** `deploy.sh:78-79` überträgt den Code per `tar -cf - ./ | ssh 'tar -xf - -C $APP_DIR'` — Extract ÜBERSCHREIBT vorhandene Dateien, **löscht aber nie** Dateien, die lokal entfernt wurden (kein `--delete`/rsync-Semantik). Folge: jede künftige Datei-Löschung lässt eine Leiche auf dem Server; importiert ein lebender Test die Leiche → Gate rot; sonst stiller toter Code.
- **Fix-Richtung:** Delete-bewusster Sync — entweder `rsync --delete` (wenn auf dem Win-Git-Bash-Pfad verfügbar) ODER vor dem Extract die relevanten Ziel-Verzeichnisse (mind. `tests/`, `services/`) server-seitig leeren, ODER ein git-basierter Deploy (`git fetch + reset --hard`) statt tar-Overlay. Achtung: `.db`/Logs/venv sind heute via `tar --exclude` ausgenommen — Delete-Logik darf die nicht treffen.
- **Routing:** Deploy-Härtung, STAGING-Stufe-2-Familie (zusammen mit Auto-Alembic-Lücke + DEPLOY-CREATE-ALL-CRASH). Nicht launch-blockierend, aber beißt bei jeder Lösch-Phase → bald.

### AUDIT-TRIGGER-SYNTAX — Audit-Log-Trigger-Setup scheitert bei JEDEM Boot (SQL-Syntaxfehler)

- **Severity:** medium (Tracking-Säule fehlt + DSGVO-nah — Änderungs-Protokollierung wird nicht installiert)
- **Entdeckt:** TAXO1 Welle-6 Cleanup-Deploy-Sanity-Log (2026-06-18). `[DB] Audit-Log Trigger setup failed: (psycopg2.errors.SyntaxError) syntax error at or near "NOT"` bei JEDEM Boot (verifiziert: trat auch im Boot 09:32 VOR dem Cleanup-Deploy auf → **pre-existing, unabhängig vom Cleanup**). Dienst läuft trotzdem (Trigger-Setup ist non-fatal gefangen).
- **Vermutete Root-Cause:** Trigger-DDL nutzt vermutlich `CREATE TRIGGER ... IF NOT EXISTS` o.ä. — Postgres unterstützt `IF NOT EXISTS` bei `CREATE TRIGGER` nicht (anders als bei TABLE/INDEX). `grep` nach dem Trigger-Setup-Code (Boot-Pfad, `[DB] Audit-Log Trigger`) + Syntax gegen Postgres-Version prüfen.
- **Folge:** die DB-seitigen Audit-Log-Trigger werden NICHT installiert → Änderungs-Protokollierung (CLAUDE.md Punkt-12-Tracking-Säule, DSGVO-Nachvollziehbarkeit) greift evtl. nicht wie gedacht. Verifizieren ob Audit-Events anderweitig (App-seitig) geschrieben werden oder ob hier eine echte Lücke klafft.
- **Routing:** eigenes Thema, vor Launch prüfen (Tracking/DSGVO). Erst diagnostizieren (greift Audit-Logging überhaupt?), dann Fix-Größe entscheiden.

### TZ-DISPLAY — Dashboard zeigt UTC statt lokaler Zeit (Europe/Berlin) — eigene kleine Phase nach TAXO1

- **Severity:** low (Kosmetik/UX — gespeichert wird korrekt in UTC, nur Anzeige rechnet nicht um)
- **Entdeckt:** TAXO1 Welle-3 Live-Test-Anruf (2026-06-17). André machte den Call ~12:12 lokal, Dashboard + Auswertung zeigen 10:12 (UTC, -2h CEST).
- **Root-Cause:** Templates rendern Zeitstempel direkt via `.strftime(...)` OHNE Zeitzonen-Umrechnung. Betrifft ALLE Zeit-Anzeigen (analytics.html:22 `started_at`, admin/crm_overview, ewb_rating, coach_firma, changelog etc. — `grep -rn "strftime" templates/`).
- **Fix-Richtung:** Anzeige-Zeitpunkte vor `strftime` nach Europe/Berlin konvertieren (zentral, z.B. Jinja-Filter `localtime`/`localdt`), Speicherung bleibt UTC. Eine kleine fokussierte Phase (viele Templates, aber mechanisch).
- **Routing (André 2026-06-17):** eigener kleiner Fix BALD, nach TAXO1. Kein Daten-Schaden, nicht launch-blockierend.

### PHASE-CLOSE-DETECT — Phasen-Erkennung erkennt Abschluss/Termin nicht → in Welle 4 (TAXO1-04) falten

- **Severity:** medium (Erkennungs-Qualität — Kern-Feature Live-Erkennung)
- **Entdeckt:** TAXO1 Welle-3 Live-Test-Anruf (2026-06-17). Termin am Call-Ende gelegt, Phase blieb auf „Bedarfsanalyse" (3). `classify_phase` erkannte den Abschluss nicht als Phase 5/6 (oder conf < 0.7 → von detect_phase-Hysterese geblockt). KEIN Trigger-Bug (läuft jede 5. Runde, claude_service.py:994), KEIN Welle-3-Regress (Welle 3 hat Phase überhaupt erst beweglich gemacht: 1→3 statt stuck-on-1).
- **Scope für Welle 4 (TAXO1-04 Live-Cutover Taxonomie/Erkennung):** (1) Phasen-Erkennung muss Abschluss/Terminvereinbarung als Phase 5/6 erkennen (Prompt + Konfidenz-Schwelle prüfen). (2) Nebenbefund: `_phase_cycle_counter` ist noch GLOBAL (auf der `analyse_loop`-Funktion, claude_service.py:992) statt per-SID → bei Parallel-Anrufen erratischer Phasen-Takt; in die per-SID-Konsolidierung mitnehmen.
- **Routing (André 2026-06-17):** in Welle 4 falten, kein separater Vorab-Fix.
- **UPDATE 2026-06-18 (MEDFIX-Test-Anruf):** Addition-B-Prompt wirkt (analysiere erfasst „Dienstag 14 Uhr + Zustimmung" korrekt), ABER die Phase blieb auf 3 — **Wurzel ist der TAKT, nicht der Prompt:** classify_phase läuft nur jede 5. Analyse-Runde (claude_service.py:994), der bestätigte Termin kam am Call-Ende → kein Takt mehr → Phase-6-Label zog nicht. Fix-Richtung für Welle 4/TAXO: Phasen-Takt am Call-Ende/bei Abschluss-Signal verdichten (z.B. event-getrieben bei zustimmung/naechster_schritt statt nur alle 5 Runden) + der schon notierte per-SID-Takt-Zähler.

### POSTCALL-COACH-QUALITY — Coaching-Tipps + Post-Call-Auswertung schwach/verwirrend (TAXO2/TAXO3)

- **Severity:** medium (Kern-Erlebnis-Qualität, kein Defekt)
- **Entdeckt:** MEDFIX-Test-Anrufe (2026-06-17/18, André).
- **Befunde:** (1) Live-Tipps schlagen Beispiel-Termine vor („morgen oder Donnerstag?"), die nicht zum echten ausgemachten Termin passen → wirkt wie „NERVE hat den Termin falsch". Transkript+analysiere haben den echten Termin (Dienstag) korrekt — reines Tipp-Formulierungs-Thema. (2) Antworten generell schwach/Pitch-floskelig + kein Profil-Bezug (schon ANON-LIVE-ANSWER + frühere Befunde). (3) „Redeanteil 100%"-Tipp feuert im Cold-Call sinnlos (NERVE hört nur den Berater → immer 100%; der Tipp gehört im Cold-Call unterdrückt).
- **Routing:** Antwort-/Tipp-Qualität = **TAXO3** (Wissensversorgung, Paradigma-Reset). Redeanteil-Cold-Call-Artefakt = kleiner Fix (Tipp im Single-Speaker-Cold-Call unterdrücken) — TAXO2 (Scoring/Proration K2) oder eigener kleiner Fix.

### STT-QUALITY — Worterkennung fragmentiert/ungenau (eigener Pass)

- **Severity:** medium (beeinflusst alle Downstream-Erkennung)
- **Entdeckt:** MEDFIX-Test-Anrufe (André: „Worterkennung nicht so prall"). Transkript fragmentiert (Chunking + Wiederholungen), teils ungenau.
- **Kontext:** Deepgram STT (EU-Endpoint). Mögliche Hebel: Chunk-/Endpointing-Parameter, Modell-Variante, Interim-vs-Final-Handling. Eigener STT-Tuning-Pass (nicht TAXO-Kern), aber Qualitäts-relevant weil alle Erkennung darauf aufbaut.

### DEPLOY-CREATE-ALL-CRASH — Start-`create_all` crasht bei Migrations-Deploy in falscher Reihenfolge (Prozess-Lehre + Fix-Kandidat)

- **Severity:** medium (Deploy-Robustheit — Crash-Fenster bei jedem Tabellen-anlegenden/-umbenennenden Deploy)
- **Entdeckt:** TAXO1-Welle-5-Deploy (2026-06-18). Beim Neustart crash-loopte der Worker 3×: `permission denied for schema public — CREATE TABLE zombie_ewb_ratings` → „Worker failed to boot". Selbst-geheilt, sobald die Prod-Migration (Rename) durch war.
- **Root-Cause:** `app.py:709` ruft beim Start `Base.metadata.create_all()`. Als `nerve_app` (kein CREATE-Recht auf public) ist das ein No-Op WENN alle Tabellen existieren — aber ein CRASH, wenn ein Model-Tabelle fehlt (z.B. im Fenster zwischen Code-Restart und Prod-Migration). Bei 0017 deployt-DANN-migriert → neuer Code (Model=zombie_ewb_ratings) sah die noch-nicht-umbenannte Tabelle als „fehlend" → CREATE → permission denied → Crash bis Migration durch.
- **PROZESS-LEHRE (sofort befolgen):** Bei JEDER Migration (Tabelle anlegen/umbenennen) die **Prod-Migration VOR dem deploy.sh-Restart** fahren (so lief 0016 sauber: scp Migrations-Datei → alembic upgrade head Prod → DANN deploy.sh). NICHT „erst deploy, dann migrate" (= Crash-Fenster). **Gilt für TAXO2 (rubric_score = neue Tabelle) + alle künftigen Migrations-Deploys.**
- **FIX-KANDIDAT (robuster als Disziplin):** `create_all()` auf Postgres abschalten (wie `_migrate` schon, app.py:137) — auf Postgres ist Schema = Alembic, `create_all` kann als nerve_app eh nichts anlegen → entweder No-Op oder Crash, beides unerwünscht. Gehört zur „Auto-Alembic"-Lücke (STAGING-Stufe-2) — dort mitfixen ODER eigener kleiner Fix vor TAXO2.

### HANDLING-RECOGNITION — „behandelt" ≠ Knopfdruck: echte Behandlungs-Erkennung via Vorschlags-Nutzung (TAXO2, André-Insight 2026-06-18)

- **Severity:** high (Mess-Korrektheit eines Kern-Zählers — „erfolgreich behandelt")
- **André-Insight (2026-06-18, beim Welle-5-Brücken-Discuss):** Ein Knopfdruck (oder NERVE-Spracherkennung) bedeutet NUR „Einwand ERKANNT" → der „erkannt"-Zähler darf hoch. Es bedeutet NICHT „Einwand BEHANDELT". Für „behandelt/erfolgreich" braucht es eine eigene Erkennung: **NERVE gibt einen Vorschlag → NERVE prüft anhand dessen, was der Berater DANACH sagt, ob er den Vorschlag (so oder so ähnlich) tatsächlich aufgegriffen/vorgelesen hat.** Erst das ist „behandelt".
- **Zwei getrennte Zähler (heute fälschlich vermischt, vgl. POLISH-38):** (1) `erkannt` = Detektion (Knopf ODER KI-Erkennung) → korrekt befüllbar. (2) `behandelt/erfolgreich` = braucht Vorschlags-Nutzungs-Erkennung (Abgleich Berater-Gesagtes ↔ NERVE-Vorschlag) + Behandlungs-Qualität.
- **Wo es hingehört (TAXO2):** das ist genau `handling_score` (Behandlungs-Note 1-3) + `suggestion_reactions`/Vorschlags-Nutzung aus dem TAXO-Gerüst. André's „Lese-Erkennung" = der suggestion-usage-Abgleich. TAXO2-Plan MUSS: „behandelt" NICHT aus Knopfdruck ableiten, sondern aus erkannter Vorschlags-Nutzung + Behandlungs-Note. Verbindet mit LERN-VON-DEN-BESTEN (Outcome-verankert) + Active-Learning-Flywheel.
- **Folge für Welle 5 (Brücke):** die Brücke hält nur die HEUTIGEN (bereits ungenauen, POLISH-38) Zähler am Leben während des Umbaus — sie macht „behandelt" NICHT richtig + soll nicht so tun. Die echte Behandlungs-Erkennung ist TAXO2.

### ANON-LIVE-ANSWER — Live-Antwort wird auf anonymisiertem Text gebaut → Unsinn im Ohr → TAXO3-Anforderung + 🔴 DSGVO-Entscheidung

- **Severity:** high (Live-Antwort-Qualität — KI coacht mit [PERSON_A]/[ORG_B] statt echten Namen → inkohärente Antworten)
- **Entdeckt:** TAXO1 Welle-3 Live-Test-Anruf (2026-06-17, André). Cold-Call-Antworten enthielten [ORG_B] (NERVEs eigener Kontext geschwärzt); Meeting-Antworten NICHT anonymisiert (Inkonsistenz). Log-Beleg: `[Claude-1] Analysiere (line 9): [PERSON_A], Sie arbeiten schon mit einem anderen Anbieter` — die Live-KI bekommt bereits ANONYMISIERTEN Text als EINGABE.
- **Root-Cause (empirisch):** im Cold-Call wird der Transkript-Text anonymisiert BEVOR er an die Live-Antwort-KI geht (nicht erst beim Speichern). → die KI generiert ihre Live-Antwort auf Token-Basis.
- **André-Argument:** der Berater hat die echten Namen im Gespräch gehört — das sind keine DSGVO-Geheimnisse, sondern Info „die man sich auf einen Zettel schreiben könnte". Die Live-Antwort (flüchtig, nicht gespeichert) sollte echte Namen nutzen; anonymisiert wird nur die SPEICHERUNG/Trainings-Kopie.
- **🔴 DSGVO-Spannung (NICHT schnell schießen):** berührt den Fundament-Pfeiler „anonymisieren VOR KI-Verarbeitung" ([[04 Entscheidungen/NERVE DSGVO Analyse]]). Roh-Text an die Claude-API (AWS Bedrock Frankfurt) zu geben ist eine bewusste Architektur-Entscheidung, kein Bug-Fix.
- **Routing (André 2026-06-17):** in TAXO3-Scope als explizite Anforderung (Live-Antwort = echter Text, Anonymisierung storage-only) + DSGVO-Doc-Abgleich + Gemini-Gegencheck. Auch die Cold-Call/Meeting-Inkonsistenz dort klären.
- **Verwandt:** slot1-busy-Drossel unterdrückt Folge-Antworten (`[QA-INT] slot1 busy skip`) — Slot-Timing/Dedup ist ohnehin TAXO3-Scope (TAXO3-05, Slot B per line_id). Dort mitprüfen ob die Drossel zu aggressiv ist (Fragen gehen verloren wenn Slot belegt).

### ART17-PURGE — Echte Art.17-Löschung (Hard-Delete + Cascade aufwecken) — 🔴 START-BLOCKER vor EA-Launch

- **Severity:** critical (DSGVO-Pflicht, Launch-Blocker) — eigene 🔴-Phase mit Threat-Model, NICHT als Polish-Fix
- **Entdeckt / entschieden:** Phase 08.23.2.D.UX.1 (2026-05-30), Andre-Entscheidung Option A (Soft-Delete + Audit jetzt, Hard-Purge verschoben)
- **Kontext:** `settings.py::delete_account` ist heute ein Soft-Delete (`aktiv=False`, keine Zeilen-Löschung). Die `ON DELETE CASCADE` auf `transcript_segments.conversation_log_id` (DD-01, seit D.UX.1 live) ist scharf aber **schlafend** — sie feuert nie aus App-Code. D.UX.1 hat nur den Audit-Eintrag (`user_deletion_request`) als Grundlage gebaut. Echte Löschung fehlt.
- **Scope (Andre-Vorgabe 2026-05-30) — alle drei Punkte Pflicht:**
  1. **Hard-Delete** `conversation_logs`-Zeilen → CASCADE über alle Fremdschlüssel-Tabellen (ewb_ratings, learning_cards, objection_events, phrases, calls, transcript_segments). Cascade aufwecken ist aufwendiger als es aussieht: Lock-Verhalten während Löschung + bis dahin neu hinzugekommene FK-Tabellen mitdenken.
  2. **Backup-Retention-Doku** in AVV/TOMs/Datenschutzerklärung: Live-Löschung sofort, unveränderliche (WORM-)Backups max. 30 Tage.
  3. **Restore-Re-Delete-Skript:** liest `user_deletion_request` aus `audit_log` und wendet Hard-Deletes nach jedem Backup-Restore erneut an. Pflicht: deletion-request-IDs stabil + nicht-recycelt halten (das D.UX.1-Audit-Log ist die Grundlage).
- **Cascade-Falle (LANDMINE 6):** `transcript_expires_at` liegt auf `calls`, der Cascade hängt aber an `conversation_logs`. Lösch-/Ablauf-Pfad MUSS über `calls.conversation_log_id → conversation_logs.id → transcript_segments` laufen, sonst Waisen-Zeilen.
- **Betrifft:** `routes/settings.py`, neue Migration evtl., `scripts/` (Restore-Re-Delete), AVV/TOMs/Privacy-Doku.
- **Trigger:** vor EA-Launch (50 Early-Access-Plätze) — sobald ein externer User existiert ist echte Löschung Pflicht.

---

### OUTCOME-ORDER — Score läuft vor Outcome-Bestätigung (Reihenfolge/Timing)

- **Severity:** high (UX/Flow — D.UX-Direktive "Outcome-Pflicht-Schritt VOR Score")
- **Entdeckt:** Phase 08.23.2.D.UX.1 Live-Test (2026-05-30, andre-test@nerve.local)
- **Symptom:** Nach Auflegen erscheint das Outcome-Modal jetzt zuverlässig (Bug C gefixt), ABER der Score/die Auswertung läuft/erscheint bereits BEVOR der User das Gesprächsergebnis bestätigt hat. Die D.UX-Direktive verlangt: erst Outcome-Pflicht-Wahl, dann Score aufdecken.
- **Abgrenzung:** Das ist KEIN Bug-C-Render-Fehler (Modal erscheint). Es ist ein Reihenfolge-/Timing-Problem im Zusammenspiel Modal ↔ Score-Aufdeckung. D.UX hatte ein Score-Gate (`nlp-section-postcall display:none` bis Bestätigen) — vermutlich greift das Gate im neuen Force-Wahl-Pfad (Zustand 1/3, Bestätigen ausgegraut) nicht oder der Score wird auf einem anderen Pfad früher gerendert.
- **Betrifft:** `static/pip-launcher.js` (_renderOutcomeUx Score-Gate + postcall-Render-Reihenfolge), evtl. Socket-Reihenfolge outcome_ready vs. postcall_analysis-Response.
- **Planung:** eigene Folge-Phase (Andre-Entscheidung 2026-05-30 — bewusst NICHT in D.UX.1 reingezogen). Klein, fokussiert (🟡).

---

### POLISH-38 — `ConversationLog.einwaende_gesamt` wird nicht hochgezählt

- **Severity:** medium
- **Entdeckt:** Phase 07.2 UAT-R2 Cold-Call-Checkpoint (2026-04-20), refined in Cold-Call-UAT-R2-Approval (2026-04-21) mit Session #117
- **Symptom:** Sektion 4 "Einwand-Timeline" zeigt 4 ObjectionEvent-Einträge, Metrik "Einwände behandelt" zeigt konkret `0/1` statt `0/4` (d.h. der Counter erfasst nur genau 1 Einwand, nicht alle in der Timeline aufgeführten Events). Ursprünglich beobachtet mit `0/0`-Anzeige bei 3 Events — aktuelle Reproduktion Session #117 Cold-Call-UAT-R2: 4 Timeline-Events vs. `0/1`-Metrik.
- **Vermutete Root-Cause:** Beim `ObjectionEvent`-Insert (wahrscheinlich in `routes/app_routes.py` `/api/ewb` Handler oder in `services/live_session.py` EWB-Klick-Persistenz) fehlt die parallele Inkrement-Logik für `ConversationLog.einwaende_gesamt`. Die Bulk-Insert-Schleife aus Phase 04.7 zählt Events, aber der ConversationLog-Zähler wird nicht synchron hochgezählt. Der aktuelle Counter-Wert `1` legt nahe, dass nur der allererste EWB-Klick den Zähler erhöht (oder nur der letzte ObjectionEvent committed wird) — Folge-Klicks werden ignoriert.
- **Impact:** Score-Hero-Breakdown "Einwände behandelt" prozentualer Anteil falsch. Post-Call-Analytics (Admin-Dashboard) zeigen systematisch zu wenige Einwände für alle Live-Sessions.
- **Betrifft:** `/api/beenden` Handler, `services/live_session.py`, evtl. `database/models.py` falls trigger-basiert.
- **Fix-Skizze:** Nach ObjectionEvent-Bulk-Insert in `api_beenden` (Phase 04.7) ein `conv.einwaende_gesamt = len(ewb_clicks)` setzen und mit `db.add(conv); db.commit()` persistieren. Alternativ SQL-Trigger auf `objection_events` Insert.
- **Repro-Referenz:** Session #117 aus Cold-Call-UAT-R2 — 4 ObjectionEvents in Sektion 4 Timeline, Metrik `0/1`.

---

### POLISH-39 — `ConversationLog.phasen_details` bleibt NULL trotz aktiver Phasen-Klassifikation

- **Severity:** medium
- **Entdeckt:** Phase 07.2 UAT-R2 Cold-Call-Checkpoint (2026-04-20)
- **Symptom:** Session #117 lief 77 Sekunden, Backend loggt explizit `[phase_classify] 1→2 (Qualifizierung) conf=0.85`, aber `ConversationLog.phasen_details` ist NULL nach Session-Ende. Sektion 5 "Phasen-Strip" bleibt leer trotz ausreichender Dauer.
- **Vermutete Root-Cause:** Phase-Classifier (in `services/claude_service.py` oder ähnlich) hält die Klassifikationen im Runtime-State (`live_session.state`) aber die `api_beenden`-Persist-Logik liest diesen State nicht in `phasen_details` zurück. Es gibt einen Disconnect zwischen Runtime-Tracking und DB-Write.
- **Impact:** Phasen-Strip-Section (Sektion 5) permanent leer bei Live-Sessions. OBS-02 Recidiv-Risiko, obwohl Backend-Intelligence funktioniert.
- **Betrifft:** `routes/app_routes.py` `/api/beenden`-Handler, `services/live_session.py` state-Extraktion.
- **Fix-Skizze:** In `api_beenden` vor dem Commit: `conv.phasen_details = json.dumps(live_session.state.get('phasen_klassifikationen', []))`. Prüfen ob Payload-Format mit Template-Rendering übereinstimmt.

---

### POLISH-40 — `ConversationLog.precall_briefing` bleibt NULL trotz generiertem Briefing

- **Severity:** medium
- **Entdeckt:** Phase 07.2 UAT-R2 Cold-Call-Checkpoint (2026-04-20)
- **Symptom:** Log zeigt `[DG] PreCall-Briefing gespeichert (1540 Zeichen)` — Briefing wurde generiert und im Runtime-State abgelegt. Nach Session-Ende ist `ConversationLog.precall_briefing` NULL. Collapsible "PreCall-Briefing" im Session-Detail bleibt leer.
- **Vermutete Root-Cause:** Analog zu POLISH-39. `services/precall_service.py` oder `routes/app_routes.py` `/api/precall/recherche` schreibt Ergebnis in `live_session.state['precall_briefing']`, aber `/api/beenden` liest diesen Key nicht aus und persistiert ihn nicht.
- **Impact:** User verliert Zugriff auf die PreCall-Vorbereitung nach Session-Ende. Knowledge-Retention für Coaching-Review kaputt.
- **Betrifft:** `routes/app_routes.py` `/api/beenden`-Handler, `services/live_session.py`, evtl. `services/precall_service.py`.
- **Fix-Skizze:** In `api_beenden`: `conv.precall_briefing = live_session.state.get('precall_briefing') or None` vor Commit. Evtl. Hash/Ref statt Volltext für DB-Size-Kontrolle.

---

### POLISH-41 — Post-Call-Screen zeigt "Kein Gespräch erkannt" trotz kompletter Session-Persistenz (KRITISCH)

- **Severity:** critical
- **Entdeckt:** Phase 07.2 UAT-R2 Cold-Call-Checkpoint (2026-04-20)
- **Symptom:** Cold-Call Session #117 wird korrekt beendet — alle Einwände, Painpoints, Skript-Abdeckung, `kb_end=74` sind in der DB. Nach "Beenden"-Klick zeigt der Post-Call-Overlay-Screen jedoch "Kein Gespräch erkannt". User denkt der Call sei verloren und navigiert nicht zur Detail-Seite. Session ist aber via `/analytics` → Session-Detail vollständig abrufbar.
- **Vermutete Root-Cause:** Frontend-Bug im Post-Call-Overlay-Rendering in `static/app.js` oder PiP-Launcher (`static/pip-launcher.js`). Die "Kein Gespräch erkannt"-Guard prüft vermutlich falsche Indikatoren (z.B. `words < 20` oder `sessionSeconds < 10`), obwohl Backend-Response `log_id` korrekt zurückliefert. Cold-Call hat keine Speaker-Diarization → `berater_words` kann 0 bleiben trotz aktivem Call. Der Guard ist nicht typ-aware (analog OBS-02 Redeanteil-Regel in `_derive_practice_recommendations`).
- **Impact:** KRITISCHER User-Flow-Blocker. User verliert Vertrauen in die Session-Erfassung. Kein Redirect auf `/session/<id>` bei Cold-Call in der Praxis → gesamter Phase-07.2-Konsolidierungs-Flow kaputt für Cold-Call.
- **Betrifft:** `static/app.js` (No-Conversation-Guard), `static/pip-launcher.js` (Post-Call-Screen), evtl. `/api/beenden` Response-Payload.
- **Fix-Skizze:** No-Conversation-Guard typ-aware machen: bei `session_mode === 'cold_call'` nur `sessionSeconds < 10` prüfen (keine Word-Count-Guard, da single-speaker). Alternativ: Guard auf Server-Seite verlagern und Frontend nur auf `log_id`-Rückgabe reagieren. Regression-Test mit kurzer Cold-Call-Session (~15s).

---

### POLISH-42 — Skript-Abdeckung zeigt konstant 17% unabhängig vom Gesprächsverlauf

- **Severity:** medium
- **Entdeckt:** Phase 07.2 Cold-Call-UAT-R2 (2026-04-21, User-Meldung nach B1-Approval)
- **Symptom:** Live-Breakdown-Block Row "Skript-Abdeckung" zeigt konstant `17%` unabhängig davon, welche Skript-Punkte im Gespräch tatsächlich angesprochen werden. Mehrere Test-Sessions mit unterschiedlichem Verlauf liefern denselben Wert.
- **Vermutete Root-Cause:** Hardcoded Default-Wert oder fehlerhafte Berechnungslogik in `services/claude_service.py` / `services/live_session.py` / `routes/app_routes.py`. Möglichkeiten:
  - Eine Konstante `SKRIPT_ABDECKUNG_DEFAULT = 17` o.ä. wird als Fallback gerendert statt des berechneten Werts.
  - Claude-Haiku-Analyse liefert den Wert nicht, der Reducer fängt das silent ab und fällt auf einen Legacy-Default zurück.
  - Division durch `len(profile['skript_punkte'])` mit einem festen Nenner (z.B. 6) und Zähler `1` → ≈17%.
- **Impact:** Metrik verliert komplett ihre Aussagekraft. User vertraut der Score-Hero-Breakdown nicht mehr.
- **Betrifft:** `services/claude_service.py` (analysiere-Call), `services/live_session.py` (State-Update), `routes/app_routes.py` (/api/beenden Response), evtl. `templates/session_detail.html` (Render-Fallback).
- **Fix-Skizze:** Debug-Log bei `skript_abdeckung`-Update ergänzen, Wert-Fluss Backend-→-Template tracen. Prüfen ob `17` eine hardcoded Konstante ist oder das Ergebnis einer deterministischen Division (1/6 ≈ 16.67 → gerundet 17). Nach Root-Cause-Identifikation: echten Wert aus Haiku-Response persistieren.

---

### POLISH-43 — Einwand-Count-Diskrepanz zwischen Post-Call-Quick-Scoring und Session-Detail

- **Severity:** medium
- **Entdeckt:** Phase 07.2 Cold-Call-UAT-R2 (2026-04-21)
- **Symptom:** Post-Call-Overlay-Screen zeigt `1 Einwand`, Session-Detail-Seite zeigt für dieselbe Session `4 Einwände`. Beide Werte stammen vom selben Call, zeigen aber unterschiedliche Counts.
- **Vermutete Root-Cause:** Zwei verschiedene Datenquellen werden konsumiert:
  - Post-Call-Overlay liest vermutlich Runtime-State (`live_session.coaching_buffer` oder `state['einwand_counter']`) bevor der Bulk-Insert vollständig committed ist.
  - Session-Detail liest persistierte `ObjectionEvent`-Records aus der DB (korrekter Wert).
  - Mögliche Race-Condition: Overlay rendert bevor `/api/beenden` den finalen Commit abgeschlossen hat.
- **Impact:** User bekommt widersprüchliche Zahlen in derselben Session. Vertrauen in die Auswertung leidet. Verstärkt POLISH-41-Eindruck ("wurde überhaupt etwas erfasst?").
- **Betrifft:** `static/app.js` oder `static/pip-launcher.js` (Post-Call-Overlay-Render), `routes/app_routes.py` `/api/beenden` Response-Payload, Timing der Bulk-Insert-Sequenz.
- **Fix-Skizze:** Overlay-Render verzögern bis `api_beenden` fertig committed (await auf `log_id`-Response), dann `einwaende_gesamt` aus Response-Payload statt aus Runtime-State lesen. Alternativ: Overlay direkt eliminieren zugunsten des Redirects auf `/session/<id>` (siehe POLISH-41-Fix-Scope).
- **Related:** POLISH-38 (einwaende_gesamt-Counter-Bug), POLISH-41 (Post-Call-Overlay "Kein Gespräch erkannt").

---

### POLISH-44 — Recommendation-Text zu generisch ("mit weniger Druck festigen")

- **Severity:** low (Content-Polish)
- **Entdeckt:** Phase 07.2 Cold-Call-UAT-R2 (2026-04-21)
- **Symptom:** `_derive_practice_recommendations()` Live-Rules erzeugen zu generische `explanation`-Strings wie "mit weniger Druck festigen", ohne Bezug auf den konkreten Einwand-Typ (Preis/Zeit/Entscheider/Bedarf/Vertrauen). Die Einwand-Typ-Information ist im Input-State vorhanden, wird aber im Explanation-Template nicht genutzt.
- **Vermutete Root-Cause:** `_derive_practice_recommendations()` in `routes/dashboard.py` (oder analoger Service) verwendet generische Template-Strings ohne Einwand-Typ-Branching. Beispiel aus bisheriger Implementation: `return {'label': '...', 'explanation': 'mit weniger Druck festigen'}` statt `return {'label': '...', 'explanation': f'{einwand_typ}-Einwände mit weniger Druck festigen'}`.
- **Impact:** Sektion 14 "Verbesserungspotenzial" wirkt beliebig und hilft dem User nicht, konkrete nächste Schritte abzuleiten. Coaching-Value sinkt.
- **Betrifft:** `routes/dashboard.py` `_derive_practice_recommendations()`, evtl. `services/recommendations_service.py` falls extrahiert.
- **Fix-Scope:** **Phase 08** (Content-Pass) — einwand-typ-spezifische Templates für Recommendation-`explanation`. Nicht in Phase 07.2 inline-fixen, da reiner Content-/UX-Polish ohne funktionale Blocker.
- **Fix-Skizze:** Mapping-Dict `EINWAND_TYP_EXPLANATIONS = {'preis': '...', 'zeit': '...', ...}` anlegen, in `_derive_practice_recommendations()` pro Event den Typ lookup'en und in den Output-String interpolieren.

---

### POLISH-29 — Einwand-Behandlungs-Definition standardisieren (EWB-Button-gedrückt = behandelt)

- **Severity:** low (Konzeptuelle Klarstellung, keine Code-Änderung zwingend)
- **Entdeckt:** Ursprünglich früher (exakte Herkunft nicht in aktuellem `.planning/`-Tree auffindbar — siehe Grep-Ergebnis: kein anderer POLISH-29-Eintrag im Repo). Refined 2026-04-21 im Kontext von Phase 07.2 Cold-Call-UAT-R2.
- **User-Definition (Produkt-Entscheidung):** **"EWB-Button gedrückt = Einwand behandelt."** Das ist die verbindliche Standard-Definition für alle Metriken, UI-Labels und Post-Call-Analysen. Keine heuristische Metrik (z.B. "Einwand behandelt wenn innerhalb von 15s ein Gegenargument im Transkript"), sondern die explizite User-Aktion.
- **Impact:** Aktuelle Metriken/Counter (z.B. "Einwände behandelt X/N") müssen diese Definition konsistent anwenden. POLISH-38-Fix muss `ewb_clicks` als Grundlage für `einwaende_gesamt`-Increment nutzen (nicht automatische Heuristik).
- **Betrifft:** Dokumentation (`.planning/REQUIREMENTS.md` falls Metrik-Definition dort), `routes/app_routes.py` `/api/beenden`-Counter-Logik, `services/live_session.py` EWB-State-Tracking, `templates/session_detail.html` Label-Text bei Sektion 4.
- **Fix-Skizze:** Keine eigenständige Code-Change — diese Definition ist die Reference für POLISH-38. Separater Eintrag dient als zitierbare Produkt-Entscheidung für zukünftige Planungsphasen und zur Vermeidung von Re-Diskussionen.
- **Cross-Reference:** Falls in älteren Phase-Dokumenten (z.B. Phase-04.x DEVIATIONS oder pre-GSD-Vault) ein älterer POLISH-29-Eintrag mit abweichender Definition existiert, überschreibt diese User-Definition den Altstand. Siehe Grep 2026-04-21: kein Match in `.planning/**`.

---

### POLISH-49 — `DEEPGRAM_HOST` Environment-Variable wird nicht gelesen (DSGVO-EU-Region inaktiv)

- **Severity:** **critical** (Launch-Blocker für DACH/DSGVO-Compliance)
- **Entdeckt:** Debug-Session POLISH-48 (2026-04-21), Bonus-Finding im `services/deepgram_service.py`-Review
- **Symptom:** `.env.example` deklariert `DEEPGRAM_HOST=api.eu.deepgram.com` (EU-Endpoint für DSGVO-konforme Audio-Verarbeitung), aber der Code liest diese Variable nirgends. `DeepgramClient(DEEPGRAM_API_KEY)` in `services/deepgram_service.py:181` wird ohne Host-Override instanziiert → Default-Host ist `api.deepgram.com` (US-Endpoints).
- **Impact:** **DSGVO-Architektur-Bruch.** NERVE sendet aktuell alle Live-Audio-Chunks an US-Endpoints, obwohl CLAUDE.md-Constraint explizit fordert: "DSGVO: Pflicht von Tag 1 — Server in Deutschland (Hetzner), kein wörtliches Mitschneiden default." Muss vor Launch gefixt werden — sonst Datenschutz-Verstoss bei jeder Live-Session.
- **Betrifft:** `config.py` (Env-Variable laden), `services/deepgram_service.py:181` (ClientOptions mit `url="https://api.eu.deepgram.com"` instanziieren), `.env` (Deploy-Key setzen auf Hetzner-VPS).
- **Fix-Skizze:** In `config.py`: `DEEPGRAM_HOST = os.getenv("DEEPGRAM_HOST", "api.eu.deepgram.com")`. In `deepgram_service.py`: `DeepgramClient(DEEPGRAM_API_KEY, config=DeepgramClientOptions(url=f"https://{DEEPGRAM_HOST}"))`. Deploy auf VPS mit `DEEPGRAM_HOST=api.eu.deepgram.com` in `.env`. Runtime-verify: Netzwerk-Check zeigt Requests an `eu`-Host.
- **Cross-Reference:** Deepgram-SDK `DeepgramClientOptions(url=...)` Pattern siehe SDK v3.10.0.

---

### POLISH-50 — Client-Side Audio-Chunk Start-Race (audio_chunk emittet vor start_live_session)

- **Severity:** low (wenige Frames betroffen, mode-unabhängig)
- **Entdeckt:** Debug-Session POLISH-48 (2026-04-21), Bonus-Finding in `static/pip-launcher.js:877-965`
- **Symptom:** In `_startAudio()` wird der AudioWorklet angelegt (Zeile 923) und emittet sofort `audio_chunk`-Frames. DANACH erst, am Ende von `_startAudio()` (Zeile 965), wird `start_live_session` emittet. Wenige Worklet-Frames zwischen Setup (L920-929) und `start_live_session`-Emit (L965) werden vom Server silent dropped, weil `_deepgram_sessions.get(_sid)` noch `None` zurückgibt.
- **Impact:** Minimaler Audio-Verlust am Session-Start (wenige Millisekunden, typischerweise Stille oder Atem). Nicht user-wahrnehmbar, aber unsauber.
- **Betrifft:** `static/pip-launcher.js:877-965`, `static/app.js:55-57`, Server-Side `handle_audio_chunk` in `services/deepgram_service.py`.
- **Fix-Skizze:** Entweder (a) `start_live_session` VOR der Worklet-Instanziierung emittet und auf Ack warten, oder (b) Server-Side die ersten N Chunks nach `start_live_session` buffern bis Deepgram-Connection ready ist. Option (a) ist sauberer.
- **Gilt für alle Modi** (Cold Call + Meeting) — nicht mode-spezifisch.

---

### POLISH-45 — Headset-Modal-Reset (15-Min-Fix)

- **Severity:** medium (UX-Polish, User-Flow)
- **Entdeckt:** Phase 07.4 Debug-Cluster-UAT (2026-04-21)
- **Symptom:** Headset-Modal (Phase 06.4 DSGVO-Hardening) persistiert User-Wahl über Session-Grenze hinweg. Wenn der User bei einer Session "Headset bestätigt" klickt und später ohne Headset eine neue Session startet, wird das Modal nicht erneut gezeigt — gefährdet DSGVO-Compliance-Nachweis.
- **Vermutete Root-Cause:** LocalStorage-Key oder Session-Cookie behält Headset-Confirm-State und wird bei neuem `/live`-Aufruf nicht zurückgesetzt. Sollte pro Session (nicht pro Browser-Installation) neu bestätigt werden.
- **Fix-Skizze:** Headset-Confirm-State bei `/live`-Route-Start clearen (z.B. `localStorage.removeItem('headset_confirmed')` oder Session-scoped State in `sessionStorage`). Alternativ Server-Side per-Session-Flag.
- **Fix-Aufwand:** ~15 Min (Frontend-One-Liner + Test).
- **Scope:** separate kleine Phase (POLISH-38-Teilfix + POLISH-45 bundled) nach Phase 07.4.

---

### POLISH-38.1 — Teilfix: success-Flag bei manual_ewb (10-Min-Fix, Ergänzung zu POLISH-38)

- **Severity:** low (Metrik-Präzision)
- **Entdeckt:** Phase 07.4 Debug-Cluster-UAT (2026-04-21)
- **Parent:** POLISH-38 Counter-Fix in Commit `cf38589` behob `einwaende_gesamt` (zählt jetzt `len(ewb_clicks)`). Offen bleibt: `manual_ewb`-Events (User-Klick ohne Claude-Auto-Detection) haben aktuell kein `success`-Flag — Metriken "erfolgreich behandelt" können nicht zwischen EWB-Klick (counted) und tatsächlich erfolgreicher Behandlung (via Claude-Scoring) diskriminieren.
- **Vermutete Root-Cause:** `ObjectionEvent.success` wird beim manual_ewb-Insert nicht gesetzt (Default vermutlich NULL). Post-Call-Scoring-Heuristik kann daher nur "versucht behandelt" tracken, nicht "erfolgreich".
- **Fix-Skizze:** In `routes/app_routes.py` beim manual_ewb-Insert `success=None` explizit setzen oder per Claude-Re-Evaluation im Post-Call-Flow setzen.
- **Fix-Aufwand:** ~10 Min.
- **Scope:** bundled mit POLISH-45 in einer kleinen Follow-up-Phase.

---

### POLISH-53 — EWB-Feed-Redesign (Phase-07.5-Kandidat)

- **Severity:** medium (UX, löst Slot-Dominanz-Problem)
- **Entdeckt:** Phase 07.4 Debug-Cluster-UAT (2026-04-21)
- **Symptom:** Aktueller EWB-Bereich hat nur 2 Slots die bei neuen Einwänden die alten Einwände überschreiben. User verlieren kontext bei schnellen Gesprächen mit vielen Einwänden. "Slot-Dominanz" — die zuerst angezeigten Einwände verdrängen sich gegenseitig ohne History.
- **Redesign-Idee:** Scrollbarer EWB-Feed statt 2-Slot-Overwrite — aktive + bereits behandelte Einwände in chronologischer Liste. Löst Slot-Dominanz, gibt User historischen Kontext über das Gespräch.
- **Scope-Impact:** nicht-trivial — neue Komponenten-Architektur, UX-Spec-Runde, Template + CSS + JS-State-Management. Gehört als **Phase 07.5** separat geplant (nicht Teil von 07.4).
- **Planung:** via `/gsd-plan-phase 07.5` sobald 07.4-Follow-up abgeschlossen.

---

## Referenzen

- Phase 07.2 UAT-R2 Cold-Call-Checkpoint: 2026-04-20, Session #117 als Test-Referenz
- Phase 07.2 Cold-Call-UAT-R2-Approval: 2026-04-21 (nach B1-Fix: POLISH-42/43/44 neu, POLISH-38 refined, POLISH-29 konsolidiert)
- B1 aus UAT-R2 (Sektion 14 Dubletten) wurde in Phase 07.2 inline gefixt (Commit `e040ee7`)
- POLISH-35, POLISH-36, POLISH-37 bleiben deferred aus Phase 07.1 (siehe ROADMAP.md Zeile 711-717)
- POLISH-44 Fix-Scope ausdrücklich Phase 08 (Content-Pass), nicht Phase 07.2
- Phase 07.4 Debug-Cluster (2026-04-21): POLISH-48/41/49/38/40/39/42/51/52/46 resolved + deploy-verified in Session #124. POLISH-45/-38.1/-53 als Follow-ups herausgelöst.
