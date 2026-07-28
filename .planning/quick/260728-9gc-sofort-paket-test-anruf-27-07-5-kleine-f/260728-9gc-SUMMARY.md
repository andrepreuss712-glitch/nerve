# 260728-9gc — SOFORT-PAKET nach Test-Anruf 27.07. — SUMMARY

**Status:** ✅ komplett gebaut, 5 atomare Commits, alle Waechter gruen, keine Regression.
**Basis-Commit:** `f71e63f` · **HEAD danach:** `6742030` · **Branch:** `main` (nicht gepusht, kein Deploy — wie beauftragt)

---

## Die fuenf Commits

| # | Commit | Titel | Dateien |
|---|---|---|---|
| FIX 1 | `185f576` | `fix(logs): PYTHONUNBUFFERED in beiden systemd-Units -- zeilenweises Log-Flushing` | `deploy/nerve.service`, `deploy/nerve-staging.service`, `tests/test_service_unit_unbuffered.py` (+56) |
| FIX 2 | `56aba39` | `fix(beenden): ENTRY-Log als erste Aktion in api_beenden` | `routes/app_routes.py`, `tests/test_stabil1_beenden_guard.py` (+44) |
| FIX 3 | `f2830d1` | `fix(deepgram): Keepalive-Client-Option -- verhindert 1011-Abbruch bei kurzem Ton-Stau` | `services/deepgram_service.py`, `tests/test_deepgram_keepalive.py` (+87/-1) |
| FIX 4 | `3b1001c` | `fix(deepgram): stille Fehl-Sendung sichtbar machen (send-Rueckgabewert auswerten)` | `services/deepgram_service.py`, `tests/test_deepgram_send_failure_log.py` (+130/-4) |
| FIX 5 | `6742030` | `fix(pip): Slot-1-Platzhalter kann nicht mehr ewig haengen (10s-Rueckfall + pip_stream_error im Fehlerpfad)` | `static/pip-launcher.js`, `static/nerve.css`, `services/claude_service.py`, `services/deepgram_service.py`, `tests/test_pip_variante_fallback.py` (+105) |

Jeder Commit enthaelt Code **und** seinen Waechter-Test. Kein Commit enthaelt eine Datei
ausserhalb seines Fixes. Kein `git push`, kein Deploy, keine Migration, kein Schema-Anfassen.
`.claude/settings.local.json`, `_design_export/` und die `.planning/`-Artefakte sind bewusst
NICHT committet.

---

## Testergebnis der vollen Offline-Suite (Deploy-Gate-Kommando)

```
pytest -m "not live and not perf" -q --ignore=tests/test_ft_seed.py
→ 6 failed, 772 passed, 240 skipped, 5 deselected
```

**Vergleich gegen den Basis-Commit `f71e63f`** (identischer Lauf gegen den ausgecheckten
Basis-Baum in einem Scratch-Verzeichnis):

```
→ 6 failed, 761 passed, 239 skipped, 5 deselected
```

**Bewertung: keine Regression.** +11 neu bestandene Tests (die neuen Waechter),
+1 Skip (der neue Beenden-Waechter, PG-only), **exakt dieselben 6 Fehlschlaege wie vorher**:

| Fehlschlag | Ursache | vorher schon rot? |
|---|---|---|
| `test_api_rate_seed_liste.py` (5×) | `sqlite3.OperationalError: unknown database crm` — lokal ohne echtes Postgres kann SQLite das `crm.*`-Schema nicht anlegen | ✅ ja, identisch am Basis-Commit |
| `test_anonymization_reid.py::test_reid_with_gliner_below_5_percent` | GLiNER-/NER-Modell-Qualitaetstest, beruehrt keine der geaenderten Dateien | ✅ ja, identisch am Basis-Commit |

Zusaetzlich: `tests/test_ft_seed.py` bricht schon beim **Einsammeln** ab (dieselbe
`unknown database crm`-SQLite-Ursache) — das ist der in CLAUDE.md dokumentierte
„test_ft_seed Pre-existing Failure" und ebenfalls am Basis-Commit vorhanden. Deshalb
`--ignore`, sonst laesst pytest die ganze Suite gar nicht erst starten.

### Waechter einzeln

```
tests/test_service_unit_unbuffered.py     2 passed
tests/test_deepgram_keepalive.py          2 passed
tests/test_deepgram_send_failure_log.py   6 passed
tests/test_pip_variante_fallback.py       1 passed
tests/test_stabil1_beenden_guard.py       8 skipped (lokal, s. Annahme 2)
tests/test_stt_model_parity.py            1 passed  (Nachbarschaft FIX 3)
tests/test_no_live_global_state.py        6 passed  (Nachbarschaft FIX 4)
```

Kein Waechter traegt einen `live`/`perf`-Marker — alle fuenf laufen im Deploy-Gate.

---

## Getroffene Annahmen (keine Rueckfrage moeglich)

1. **FIX 3 — `is_keep_alive_enabled()` gibt `'true'` zurueck, nicht `True`.**
   Der Plan schrieb als Assertion `captured_config.is_keep_alive_enabled() is True`.
   Am **installierten SDK 3.10.0 verifiziert** (`options.py:98-104` gibt den ROHEN
   Options-Wert per `.get()` zurueck):
   ```
   >>> DeepgramClientOptions(url=..., options={'keepalive':'true'}).is_keep_alive_enabled()
   'true'
   ```
   Ein `is True`-Vergleich waere also **sofort rot** gewesen. Der Waechter prueft daher
   Truthiness (`assert captured_config.is_keep_alive_enabled()`) — mit Kommentar im Test.
   Das SDK selbst prueft ebenfalls nur Truthiness (`if self._config.is_keep_alive_enabled():`),
   die Semantik ist also identisch. *(Deviation-Regel 1 — Bug im Plan-Wortlaut, inline gefixt.)*

2. **FIX 2 — Waechter laeuft lokal nicht, nur im Deploy-Gate.**
   `tests/test_stabil1_beenden_guard.py` haengt an der `client`-Fixture, die per Design
   echtes Postgres (`TEST_DATABASE_URL` / `nerve_test`) verlangt und ohne SQLite-Fallback
   skippt (Req-2/D-07). Lokal: 8 skipped (inkl. dem neuen Test). Der Beweis kommt beim
   `deploy.sh production`-Gate auf dem Server. Der Test ist substanziell (echter HTTP-POST
   → echte Ausgabe → **Ordnungs**-Assertion ENTRY vor Guard-Zeile), kein Source-Presence-Test.

3. **FIX 5 — Waechter beweisbar scharf (RED-Gegenprobe gemacht).**
   Ich habe `services/claude_service.py` kurzzeitig auf den Vor-Fix-Stand zurueckgesetzt
   und den neuen Waechter laufen lassen → **FAILED**. Danach wiederhergestellt → passed.
   Der Test ist also kein Schein-Gruen.

4. **FIX 5 — `extensions.socketio` ist ausserhalb der App `None`** (`extensions.py:4`).
   Der Plan sah `monkeypatch.setattr(extensions.socketio, 'emit', _sammler)` vor — das
   wirft `AttributeError: None has no attribute 'emit'`. Der Waechter ersetzt daher das
   **ganze Objekt** (`monkeypatch.setattr(extensions, 'socketio', _SammelSocketIO())`).
   Fachlich identisch: `streame_manual_ewb_variante` bindet `sio` erst zur Laufzeit
   (`from extensions import socketio as sio`), der Patch greift. *(Deviation-Regel 3.)*

5. **FIX 5 — keine JS-Testinfrastruktur im Repo** (kein `package.json`/`jest`/`vitest`).
   Fuer den 10s-Browser-Timer wurde bewusst **kein** pytest-Waechter geschrieben — ein
   `open('pip-launcher.js').read() + assert 'setTimeout' in src` waere ein
   Source-Presence-False-Green (CLAUDE.md, hartes Verbot). Die Begruendung steht als
   Kommentar im Docstring von `tests/test_pip_variante_fallback.py`.
   → **Diese Haelfte verifiziert André im Live-Test** (s. unten).

6. **FIX 5 — `pip_stream_error`-Listener raeumt `pip-hinweis` nicht ab.** Kommt der Fehler
   NACH dem 10s-Hinweis (>10s), wird die Fehlermeldung in der gedaempften Hinweis-Optik
   gerendert. Das ist kosmetisch, stand nicht im Plan → nicht gebaut (Punkt 17, kein
   Refactor nebenbei). Falls es stoert: eine Zeile `body.classList.remove('pip-hinweis')`
   im Fehler-Listener. `pip_stream_start` raeumt die Klasse bereits ab (Plan-Punkt a4).

7. **`_send_fail_counts` ohne Lock** (FIX 4) — wie im Plan begruendet: reine Diagnose-Zahl,
   pro sid genau ein Audio-Strom, Latenz-Neutralitaet im Live-Pfad (Punkt 25). Die
   `.pop`-Aufraeumung liegt im bestehenden `_sessions_lock`-Block (`_close_deepgram_connection`).
   Der Punkt-28-Waechter (`test_no_live_global_state.py`) bleibt gruen — per-sid gekeyt.

---

## Was von den Plan-Vorgaben abwich

Nichts Inhaltliches. Drei mechanische Korrekturen (oben als Annahme 1/4 dokumentiert plus
die Zeilennummern, die wie erwartet verschoben waren — es wurde durchgehend gegen die
Text-Anker gegriffen, nicht gegen die Zahlen):

- `connection.send(data)` lag bei `:845`, nicht `:837`
- `DeepgramClientOptions` bei `:433` (Plan-Stand korrekt)
- `streame_manual_ewb_variante`-Aufruf bei `:1067`, nicht `:1036`
- Der Platzhalter-Text steht als Escape (`'Variante wird gebaut…'`) im Quelltext —
  das Escape ist erhalten geblieben, ebenso das `—` im neuen Hinweistext.

`templates/base.html` ist unveraendert. Keine hardcoded Farbe, kein Inline-Style: der
Hinweis haengt ausschliesslich an `.pip-slot-body.pip-hinweis { color: var(--page-text-muted); }`
in `static/nerve.css`.

---

## Was André im naechsten Live-Test pruefen muss

**Vorab: erst deployen** (`bash deploy.sh production`) — vorher wirkt nichts davon. FIX 1
greift ausserdem erst nach dem Service-**Restart**, den `deploy.sh` ohnehin faehrt.

1. **Log-Zeitstempel (FIX 1) — die wichtigste Kontrolle.**
   Waehrend eines Anrufs mitlaufen lassen:
   ```
   ssh -i ~/.ssh/nerve_vps root@178.104.82.166 'journalctl -u nerve -f'
   ```
   **Soll:** Zeilen erscheinen im Moment ihres Entstehens. **Nicht mehr:** ein ganzer
   Anruf (17:02–17:04) klumpt gebuendelt bei 17:06:02. Wenn die Zeilen weiterhin klumpen,
   ist die Ferndiagnose weiter blind — dann sofort melden, dann steckt die Pufferung woanders.

2. **Browser-Haelfte von FIX 5 — der einzige Teil ohne automatischen Waechter.**
   Im PiP einen EWB-Knopf klicken und den Fehlerfall provozieren (z.B. Netz zum Backend
   kurz unterbrechen).
   **Soll:** nach spaetestens 10 Sekunden steht in Slot 1 in ruhiger, gedaempfter,
   kursiver Schrift *„Keine KI-Variante erhalten — es gilt die Antwort oben."*
   **Nicht mehr:** „Variante wird gebaut…" bis in alle Ewigkeit.
   Gegenprobe im Normalfall: kommt die KI-Variante rechtzeitig, darf der Hinweis **nie**
   auftauchen — der Timer wird bei `pip_stream_start` / `pip_token_done` / `pip_stream_error`
   geloescht.

3. **Deepgram-Stabilitaet (FIX 3).** Im Anruf einmal bewusst 15–20 Sekunden schweigen bzw.
   einen Ton-Stau provozieren. **Soll:** die Verbindung ueberlebt, kein
   `1011 did not receive audio data` mehr im Log, das Transkript laeuft danach weiter.

4. **Neue Log-Zeilen, auf die man ab jetzt achten kann:**
   - `[Beenden] ENTRY user_id=… t=HH:MM:SS.mmm remote=…` — muss bei **jedem** Beenden-Klick
     kommen. Fehlt sie: die Anfrage kam nie am Server an (Netz/Proxy), nicht der Endpoint haengt.
   - `[DG] Send fehlgeschlagen — Verbindung tot? (sid=…, chunk=#…, fehl_sendungen=N)` —
     taucht das auf, ist die Deepgram-Verbindung tot und Ton geht verloren. **Bewusst nur
     Sichtbarkeit, kein automatischer Wiederaufbau** — der bleibt eine spaetere Phase.
   - `[PiP] Variante-Fehler (sid=…, typ=…): …` — der bisher stumm verschluckte Slot-1-Fehler.

**Nicht vergessen:** `git push origin main` steht noch aus (bewusst nicht gemacht — kein
Push war Teil des Auftrags), ebenso der Deploy.
