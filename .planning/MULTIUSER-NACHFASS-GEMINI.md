# NACHFASS — deine vorige Antwort wurde beim Speichern gekuerzt

Du hast mir gerade die Mehrnutzer-Analyse fuer NERVE geliefert (Python/Flask, EIN Gunicorn-Worker mit 64 Threads, Live-Zustand im RAM, drei sequentielle Daemon-Schleifen ueber alle Sitzungen, ein globaler Riegel mit 105 Erwerbsstellen, kein Zeitlimit auf LLM-Aufrufen, Socket.IO ohne message_queue, redis nicht angebunden). Die Live-Engine wird neu gebaut (FastAPI/asyncio), die Post-Call-Auswertung kommt mit hinein.

**Angekommen ist bei mir:**
- Bau-Regel 1: Zustandslosigkeits-Gebot (kein Zustand im lokalen RAM, alles in externen Store)
- Bau-Regel 2 (abgeschnitten): Pub/Sub-Zwang, O(N)-Schleifen ueber alle Sitzungen verboten, Benachrichtigungen ueber ein Mes...[hier bricht der Text ab]
- Punkt 5 teilweise: die vier Einbahnstrassen (Session-State, Socket.IO ohne Broker, DB-Verbindungsgrenze/PgBouncer, Mandantentrennung)
- Punkt 6: dein Widerspruch (Software-Architektur zustandslos ja, Infrastruktur-Overkill nein — sauberer zustandsloser Monolith + Postgres + Redis)
- Punkt 7: synthetische Test-Clients bauen, BEVOR die Engine neu gebaut wird

**Es fehlen mir — bitte NUR diese, kompakt, ohne Wiederholung des Obigen:**

1. **Bau-Regel 2 vollstaendig** (der Satz bricht bei "ueber ein Mes..." ab)
2. **Bau-Regeln 3, 4 und 5** — im selben Stil: klarer Ausloeser, klare Verbots- oder Gebotsformulierung, so dass man einen fertigen Plan dagegen pruefen kann
3. **Zu jeder der fuenf Regeln: laesst sie sich automatisch pruefen?** Wenn ja, wie ungefaehr — statische Analyse (welches Muster?), Test (welche Art?), oder Deploy-Tor. Wenn nein, sag es klar. Wir wollen keine Regel, die nur an Disziplin haengt, ohne dass wir das wissen.

**Halte dich kurz.** Stichpunkte reichen. Deine letzte Antwort wurde beim Speichern gekappt, deshalb bitte diesmal knapper.
