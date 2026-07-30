# Verklemmung `_session_state_lock` — Beweis-Akte (2026-07-30)

**Status:** Wurzel belegt, Halter UNBEKANNT. Fix = Phase `08.23.2.LOCK-1`.
**Roher Stapel-Abzug:** `2026-07-30_lock-deadlock_py-spy-dump.txt.gz` (14.326 Zeilen, `py-spy dump --pid 2335884`).
**DSGVO-geprüft:** keine Gesprächsinhalte, keine Zugangsdaten — ausschließlich Stapel-Rahmen (grep auf `transkript|berater|kunde:|einwand_zitat|gegenargument|api_key|password|secret|token=` → 0 Treffer).

Diese Akte existiert, weil die Frage **„wer nahm den Riegel?"** offen ist. Der Abzug ist die einzige
Momentaufnahme des verklemmten Zustands; er lag zuvor nur unter `root@prod:/root/` und wäre bei jedem
Server-Neuaufbau verloren gewesen.

---

## Vorfall

Anruf `5Y-0MFlm_ITb1cupAAAB`, 30.07.2026, Prod (`da7834e`). Log-Zeitstempel sind seit dem 28.07.
verlässlich (`PYTHONUNBUFFERED=1`).

```
09:26:34  Anruf startet (Profil 6, cold_call)
09:26:35  counterpart_switch: gatekeeper → decision_maker    ✅ COUNTERPART-Umbau funktioniert
09:26:35  counterpart_switch: decision_maker → gatekeeper    ✅ (5 Wechsel, beide Richtungen)
09:27:38  manual_ewb "Zu teuer"  → [PiP-Variante] ENTRY → DONE (4 s, 244 Zeichen)
09:27:51  [Claude-1] Analysiere (line 9)
09:27:56  [Claude-2] letzter Coaching-Tipp
─────────────── ab hier absolute Stille ───────────────
09:28:07  manual_ewb "Hat Partner"  → kein ENTRY, kein Fehler, keine Emission
09:29:11  manual_ewb "Keine Zeit"   → dito
09:29:55  manual_ewb "Kein Bedarf"  → dito
09:30:07  manual_ewb "Hat Partner"  → dito
09:30:18  stop_live_session + [Beenden] ENTRY → danach nichts mehr
```

**Falsifikations-Prüfung bestanden:** ab `09:28:07` **null** Treffer für `[Claude-1]`, `[Claude-2]`,
`[KW]`, `[MOMENT]`, `[COUNTERPART]`. Die gesamte Sitzungs-Verarbeitung war tot. Der Prozess lief
ununterbrochen seit `09:11:33` — die blockierten Fäden lebten beim Abzug noch.

**Was der Nutzer sah:** „Keine KI-Variante erhalten — es gilt die Antwort oben." Das ist der
browser-seitige 10-Sekunden-Rückfall aus dem SOFORT-PAKET (FIX 5), **nicht** die Server-Fehlermeldung
(`claude_service.py:1005`). Der Rückfall hat also funktioniert — er hat einen Dauerhänger in eine
verständliche Meldung verwandelt, ohne die Ursache zu kennen.

---

## Stapel-Abzug: Frame-Häufigkeit

| Anzahl | Rahmen | Bedeutung |
|---|---|---|
| **1415** | `services/live_session.py:107` | `with _session_state_lock:` in `get_sid_paused` |
| **1414** | `services/deepgram_service.py:864` | `handle_audio_chunk` → ruft `get_sid_paused` bei **jedem** Ton-Brocken |
| 4 | `services/deepgram_service.py:966` | `handle_manual_ewb` — die vier toten Knopfdrücke |
| 1 | `routes/app_routes.py:171` | `api_beenden` — das Auflegen |
| 1 | `services/deepgram_service.py:845` | `handle_stop_live_session` |
| 1 | `services/deepgram_service.py:548` | `_close_deepgram_connection` — **die Umklammerung** |
| 1 | `services/live_session.py:313` | `coaching_loop` → `get_anonymisierer` |
| 1 | `services/claude_service.py:1322` | `analyse_loop` |
| 1 | `services/deepgram_service.py:85` | `on_message` (Deepgram-Lausch-Faden) |
| 1 | `services/deepgram_service.py:877` | `handle_disconnect` |

**Keine** `anonymization` / `gliner` / `torch`-Rahmen im gesamten Abzug.

### Die Umklammerung (wörtlich aus dem Abzug)

```
Thread 2338552 (idle): "Thread-2284 (_handle_event_internal)"
    _wait_for_tstate_lock (threading.py:1167)
    join (threading.py:1147)
    finish (deepgram/clients/common/v1/abstract_sync_websocket.py:468)
    finish (deepgram/clients/listen/v1/websocket/client.py:534)
    _close_deepgram_connection (services/deepgram_service.py:548)
    handle_stop_live_session (services/deepgram_service.py:845)
```

`finish()` wartet per `join()` **unbegrenzt** auf den Deepgram-Lausch-Faden. Dieser Faden
(`Thread-14 (_listening)`) steht in `on_message` → `get_sid_paused` → **am klemmenden Riegel**.
Zwei warten aufeinander.

---

## Zwei Wurzeln

**W1 — globaler Riegel im 10-Hz-Takt.** `get_sid_paused` (`live_session.py:105-108`) nimmt
`_session_state_lock` für einen reinen Ja/Nein-Lesezugriff und wird bei jedem 100-ms-Ton-Brocken
aufgerufen. Derselbe Riegel trägt Analyse, Coaching, Umschalter, Knopfdruck und Auflegen. Klemmt er
einmal, stirbt die Sitzung — stumm, weil kein Wächter existiert. **Der Riegel ist hier überflüssig:**
die Funktion ist durchgängig mit `.get()`-Defaults geschrieben, ein riegel-freies Lesen liefert
höchstens einen um Millisekunden veralteten Wert (im 100-ms-Takt bedeutungslos), niemals einen Fehler.

**W2 — `finish()` ohne Zeitlimit** (siehe Umklammerung oben). Folge: kein `conversation_logs`-Eintrag,
kein Transkript, keine `nova-3`-Kostenzeile. **Kein 504 im App-Log**, weil die Anfrage nicht abbricht,
sondern nie endet — nginx trennt nur den Browser, und `gunicorn --timeout 120` greift bei blockierten
Arbeits-Fäden nicht (der Herzschlag kommt vom Haupt-Faden).

---

## Offen: wer nahm den Riegel?

Alle ~60 `with _session_state_lock:`-Stellen auditiert (`deepgram_service`, `claude_service`,
`live_session`, `app_routes`, `learning`, `cost_tracker`, `prompt_pipeline`,
`einwand_keyword_matcher`): jede ist ein kurzer Arbeitsspeicher-Block — kein Datenbank-, Netz-, KI-
oder `emit`-Aufruf unter dem Riegel, kein rohes `.acquire()`. Der Abzug zeigt keinen Halter mit
sichtbarem Python-Rahmen. **Statisch nicht auffindbar.**

Das ändert den Fix nicht — W1 und W2 sind unabhängig davon falsch konstruiert. LOCK-1 Teil 3
(Wachhund + `faulthandler`) benennt den Halter beim nächsten Auftreten, statt dass wieder geraten wird.

---

## Was dieser Fund rückblickend erklärt

Wahrscheinlich **eine** Wurzel statt drei getrennter Fehler aus der Vault-Fehlerliste:

- **A5** „Variante wird geladen" hängt → der Auftrag startete nie (Riegel).
- **A6** Auflegen verliert das ganze Gespräch → Umklammerung.
- **A1** Deepgram-1011 „kein Audio" trotz fließendem Ton (27.07.) → der Ton floss, kam aber nicht
  durch den Riegel zur Weiterleitung. Das Lebenszeichen-Signal aus dem SOFORT-PAKET hilft trotzdem
  (überbrückt kurze Stauungen) — am 30.07. kam kein 1011 mehr.

**Nach LOCK-1 neu bewerten**, welche Punkte der Fehlerliste überhaupt noch offen sind.

---

## Werkzeug-Notiz

`py-spy` wurde am 30.07. ins Prod-venv installiert (`/opt/nerve/venv/bin/py-spy`), **nicht** in
`requirements.txt` — es ist ein Diagnose-Werkzeug, keine App-Abhängigkeit, und `deploy.sh` entfernt
keine Extras. Ein Neuaufbau des venv verliert es. LOCK-1 Teil 3 macht es strukturell entbehrlich
(`faulthandler` mit Signal-Auslöser liefert den Abzug ohne Zusatz-Werkzeug).

**Abzug-Befehl für den nächsten Vorfall** (Worker-PID, nicht Arbiter-PID — der Arbiter zeigt nur
`wait_for_signals`):
```
PID=$(systemctl show -p MainPID --value nerve)   # Arbiter
# Worker-PID aus den Log-Zeilen: gunicorn[<PID>]
/opt/nerve/venv/bin/py-spy dump --pid <WORKER-PID>
```
