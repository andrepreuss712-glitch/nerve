"""Phase 08.23.2.SOFORT-2 Plan 07 (D-04) — Runtime-Waechter fuer das gestaffelte Verhalten
bei Zeitueberschreitung.

Der statische Waechter aus Plan 05 (tests/test_live_timeout_coverage.py) sieht
Schluesselwoerter im Syntaxbaum. Dieser hier sieht VERHALTEN: er ruft die Helfer wirklich auf,
wirft echte anthropic.APITimeoutError-Ausnahmen durch echten Produktionscode und prueft
Zustandsaenderungen.

RESTLUECKEN
-----------
1. ABGEDECKT: dass der except-Zweig ERREICHBAR ist, dass Stufe 2 genau bei der konfigurierten
   Schwelle einmal feuert, dass ein Erfolg die Serie zuruecksetzt, dass der Zaehler per-sid
   getrennt ist und dass der Founder-Zaehler keine Nutzerdaten haelt.

2. ⚠ NICHT ABGEDECKT: dass ein ECHTER Timeout die Ausnahme wirklich bis zum Loop durchreicht.
   Der Test wirft sie selbst. Die drei durchreichenden Funktionen (analysiere_mit_claude,
   analysiere_und_klassifiziere, analysiere_coaching) haben ihren try erst HINTER
   messages.create; classify_phase und infer_customer_state fangen selbst und reichen nur
   ueber den ausdruecklichen Durchreiche-Zweig (SOFORT-2 c1) weiter. Ob diese Eigenschaften
   erhalten bleiben, sieht dieser Test NICHT — geht eine verloren, wird die Ausnahme weiter
   unten verschluckt und der Test bleibt gruen. Zweite Schicht dafuer: die AST-Acceptance in
   Plan 07 Task 1 (VERDECKT []), der echte Test-Anruf (D-06) und die Sicht ins Protokoll.
   ⚠ Teil-Entschaerfung: test_timeout_zweig_ist_erreichbar prueft die zwei Durchreicher
   (classify_phase / infer_customer_state) am ECHTEN Code — dort wird die Ausnahme unterhalb
   von messages.create geworfen und muss oben ankommen. Fuer die drei anderen Funktionen gilt
   die Luecke unveraendert.

3. ⚠ DER BESTANDS-WAECHTER HILFT HIER NICHT: tests/test_no_live_global_state.py wuerde einen
   modul-globalen per-sid-Zaehler in services/claude_service.py NICHT fangen — sein Regex zielt
   nur auf `ls.<attr> =` und `ls.state['key'] =`. Sein Gruen waere an dieser Stelle wahr und
   wertlos zugleich. Der Zaehler liegt per-sid, WEIL ES RICHTIG IST, nicht weil ein Test es
   erzwingt; test_zaehler_haelt_keine_nutzerdaten und test_per_sid_zaehler_ist_wirklich_per_sid
   sind der Ersatz fuer das fehlende Netz.

4. STRUKTURELL UNSICHTBAR — zwei Faelle:
   (a) Die Stream-Pfade. Sie zaehlen bewusst NICHT in Stufe 2 (sie liegen nicht in den Loops
       und haben mit pip_stream_error einen eigenen Kanal); ihre Timeouts zahlen nur in den
       Founder-Zaehler ein. Ob DIESE Buchung passiert, prueft hier nichts.
       ⚠ Nachtrag des Executors (D-02, gemeldet als R-12): sie passiert heute GAR NICHT —
       Plan 07 baut in den Stream-Pfaden keinen Timeout-Zweig, und die Abnahme-Zahl 6 laesst
       auch keinen zu. Die Aussage in (a) beschreibt die Absicht, nicht den Ist-Stand.
   (b) services/qa_pipeline.py::classify_utterance hat seinen try VOR messages.create mit
       einem breiten except Exception. Seine Zeitueberschreitungen erreichen WEDER den
       per-sid- NOCH den Founder-Zaehler — sie bleiben still, obwohl der Aufruf ein Zeitlimit
       aus D-03 traegt. Bewusst nicht aufgemacht: es ist ein dritter Live-Pfad ausserhalb der
       zwei Loops, und der Fix waere derselbe Durchreiche-Zweig wie in SOFORT-2 c1 — aber ohne
       einen Loop, der ihn faengt, braeuchte es zusaetzlich eine Entscheidung, WER dort
       Stufe 1/2 meldet. Gemeldet statt stillschweigend uebergangen (D-02).

5. HEURISTIK, zweischneidig: der Emit wird ueber einen Fake auf sio.emit abgefangen. Wird der
   Emit spaeter ueber einen anderen Weg gefuehrt (Wrapper, Queue), meldet der Test faelschlich
   rot (Falschtreffer). Umgekehrt beweist ein gefangener Emit nicht, dass der Browser ihn
   rendert (Durchrutscher) — dafuer ist der echte Test-Anruf da.

6. GEPRUEFT UND GESCHLOSSEN:
   - Die Vererbungs-Falle (APITimeoutError als Unterklasse von APIConnectionError):
     geschlossen durch test_timeout_zweig_ist_erreichbar plus die AST-Acceptance in Plan 07
     Task 1 (VERDECKT []).
   - "Takt statt Runde": geschlossen, weil _timeout_stufen AUSSCHLIESSLICH aus einem
     except-Zweig gerufen wird — ein Takt ohne LLM-Versuch erreicht ihn nie.
   - Blinken bei jeder weiteren Ueberschreitung: geschlossen durch die Pruefung auf den
     naechsten Aufruf nach der Schwelle ohne weiteren Emit.
   - Nutzerbezug im Founder-Zaehler: geschlossen durch test_zaehler_haelt_keine_nutzerdaten.

ZWEITE SCHICHT DARUNTER
-----------------------
Der echte Test-Anruf aus D-06 (Plan 08) plus der Founder-Zaehler im Dashboard (Soll 0). Steht
dort nach einem normalen Anruf eine Zahl, hat ein Aufruf sein Limit gerissen — das ist die
einzige Schicht, die aus echtem Betrieb heraus spricht.
"""
from __future__ import annotations

import anthropic
import httpx
import pytest

import config
import services.claude_service as cs
import services.live_session as ls


def _timeout_ausnahme() -> anthropic.APITimeoutError:
    """Eine echte SDK-Ausnahme, keine Attrappe — sonst prueft der Test seine eigene Klasse."""
    return anthropic.APITimeoutError(
        request=httpx.Request('POST', 'https://api.anthropic.com/v1/messages')
    )


@pytest.fixture
def sauberer_sitzungszustand():
    """Snapshot/Restore von _session_state und _per_sid_transcript — kein DB-Zugriff.

    Die Tests schreiben in prozess-globalen RAM-Zustand; ohne Restore wuerden sie sich
    gegenseitig und andere Testdateien vergiften.
    """
    with ls._session_state_lock:
        alt_state = dict(ls._session_state)
    with ls._per_sid_transcript_lock:
        alt_buf = dict(ls._per_sid_transcript)
    cs.reset_live_timeout_counts()
    try:
        yield
    finally:
        with ls._session_state_lock:
            ls._session_state.clear()
            ls._session_state.update(alt_state)
        with ls._per_sid_transcript_lock:
            ls._per_sid_transcript.clear()
            ls._per_sid_transcript.update(alt_buf)
        cs.reset_live_timeout_counts()


def _sid_anlegen(sid: str) -> None:
    with ls._session_state_lock:
        ls._session_state[sid] = {
            'state': {},
            'analysiert_bisher': [],
            'mode': 'meeting',
        }


class _SchleifeAnhalten(BaseException):
    """Sentinel zum Verlassen des `while True` in analyse_loop.

    BaseException, damit ihn kein `except Exception` im Loop-Rumpf abfaengt. Er wird ohnehin
    am Schleifenkopf geworfen (ls.analyse_trigger.wait), also ausserhalb jedes try.
    """


class _FakeTrigger:
    """Ersatz fuer ls.analyse_trigger: laesst GENAU EINEN Schleifendurchlauf zu."""

    def __init__(self):
        self.aufrufe = 0

    def wait(self, timeout=None):
        self.aufrufe += 1
        if self.aufrufe > 1:
            raise _SchleifeAnhalten()
        return True

    def clear(self):
        pass

    def set(self):
        pass


def test_timeout_zweig_ist_erreichbar(monkeypatch, sauberer_sitzungszustand):
    """Die wichtigste Pruefung: ist der enge except-Zweig ueberhaupt ERREICHBAR?

    anthropic.APITimeoutError ist eine UNTERKLASSE von anthropic.APIConnectionError — steht
    ein breiterer Handler zuerst, ist der Zweig unerreichbar, Stufe 1/2 feuern nie, und beide
    statischen Waechter bleiben gruen. Deshalb wird hier echter Produktionscode ausgefuehrt.

    Teil A: ein Durchlauf des analyse_loop mit einem Aufruf, der die Zeit reisst.
    Teil B: die zwei Durchreiche-Zweige (SOFORT-2 c1) in classify_phase / infer_customer_state,
            die die Ausnahme unterhalb von messages.create wieder herauslassen muessen.
    """
    sid = 'sid-erreichbar'
    _sid_anlegen(sid)
    with ls._per_sid_transcript_lock:
        ls._per_sid_transcript[sid] = [
            {'text': 'Das ist mir zu teuer.', 'line_id': 1, 't_start': 0.0},
        ]

    gerufen = []

    def _fake_stufen(_sid, funktion):
        gerufen.append((_sid, funktion))

    def _wirft(*args, **kwargs):
        raise _timeout_ausnahme()

    # Beide Aeste der MERGE_ANALYSE_QA-Weiche werfen — der Test darf nicht an einer
    # Konfigurations-Einstellung haengen.
    monkeypatch.setattr(cs, 'analysiere_und_klassifiziere', _wirft)
    monkeypatch.setattr(cs, 'analysiere_mit_claude', _wirft)
    monkeypatch.setattr(cs, '_timeout_stufen', _fake_stufen)
    monkeypatch.setattr(ls, 'analyse_trigger', _FakeTrigger())

    with pytest.raises(_SchleifeAnhalten):
        cs.analyse_loop()

    assert gerufen == [(sid, 'analyse_loop')], (
        "Der enge except anthropic.APITimeoutError im analyse_loop wurde NICHT erreicht — "
        f"gerufen: {gerufen}. Entweder faengt ein breiterer Handler vorher (Vererbungs-Falle) "
        "oder der Zweig fehlt."
    )

    # Teil B — die zwei Durchreicher. Ohne den `raise`-Zweig VOR ihrem breiten
    # `except Exception` gaeben beide still None zurueck und der Zweig im Loop waere toter Code.
    class _FakeMessages:
        def create(self, *args, **kwargs):
            raise _timeout_ausnahme()

    class _FakeClient:
        messages = _FakeMessages()

    monkeypatch.setattr(cs, 'claude_client', _FakeClient())

    with pytest.raises(anthropic.APITimeoutError):
        cs.classify_phase(['Berater: Guten Tag'], 1, 10, 'meeting', sid=sid)
    with pytest.raises(anthropic.APITimeoutError):
        cs.infer_customer_state(['Verstehe, das kann ich nachvollziehen'], 1, sid=sid)


def test_ein_erfolg_setzt_die_serie_zurueck(sauberer_sitzungszustand):
    """Ohne Ruecksetzung traegt "in Folge" nicht — dann waere Stufe 2 ein Lebenszeit-Zaehler."""
    sid = 'sid-ruecksetzung'
    _sid_anlegen(sid)
    with ls._session_state_lock:
        ls._session_state[sid][cs._SID_TIMEOUT_KEY] = 2

    cs._timeout_streak_zuruecksetzen(sid)

    with ls._session_state_lock:
        assert ls._session_state[sid][cs._SID_TIMEOUT_KEY] == 0, (
            "Ein erfolgreicher Aufruf hat die Serie nicht zurueckgesetzt."
        )

    # Kein sid (z.B. Aufruf ausserhalb einer Sitzung) darf nicht knallen — sonst faellt die
    # Ausnahme in den aeusseren except und der Ausfall waere wieder unsichtbar.
    cs._timeout_streak_zuruecksetzen(None)
    cs._timeout_streak_zuruecksetzen('gibt-es-nicht')


def test_stufe_zwei_feuert_genau_bei_der_schwelle(monkeypatch, sauberer_sitzungszustand):
    """Genau EIN Emit beim Erreichen der Schwelle — und kein weiterer danach (kein Blinken)."""
    from extensions import socketio

    schwelle = config.LIVE_LLM_TIMEOUT_HINWEIS_AB
    assert schwelle >= 1

    sid = 'sid-schwelle'
    _sid_anlegen(sid)

    emits = []
    monkeypatch.setattr(
        socketio, 'emit',
        lambda event, payload=None, **kw: emits.append((event, payload, kw)),
    )

    for _ in range(schwelle - 1):
        cs._timeout_stufen(sid, 'analyse_loop')
    assert emits == [], (
        f"Stufe 2 hat VOR der Schwelle ({schwelle}) gefeuert — das waere ein Fehlalarm."
    )

    cs._timeout_stufen(sid, 'analyse_loop')
    assert len(emits) == 1, f"Stufe 2 feuerte nicht genau einmal bei der Schwelle: {emits}"
    event, payload, kw = emits[0]
    assert event == 'live_llm_timeout_warning'
    assert kw.get('room') == sid, "Die Meldung ging nicht in den Raum genau dieser sid."
    assert payload['text'] == config.LIVE_LLM_TIMEOUT_HINWEIS_TEXT
    assert payload['tip'] == config.LIVE_LLM_TIMEOUT_HINWEIS_TIP

    # Ein weiterer Aussetzer darf NICHT erneut feuern — ein Hinweis, der blinkt, ist ein Alarm.
    cs._timeout_stufen(sid, 'analyse_loop')
    assert len(emits) == 1, (
        "Nach der Schwelle wurde erneut gefeuert — die Bedingung ist wohl >= statt == ."
    )

    with ls._session_state_lock:
        assert ls._session_state[sid][cs._SID_TIMEOUT_KEY] == schwelle + 1


def test_zaehler_haelt_keine_nutzerdaten(monkeypatch, sauberer_sitzungszustand):
    """Punkt 28: der Founder-Zaehler ist prozess-global und darf NIE pro-Nutzer-Daten tragen.

    Spiegelung von tests/test_cost_skip_counter.py::test_counter_holds_no_user_data.
    """
    from extensions import socketio

    monkeypatch.setattr(socketio, 'emit', lambda *a, **kw: None)

    sid = 'ABC123'
    _sid_anlegen(sid)
    for _ in range(4):
        cs._timeout_stufen(sid, 'analyse_loop')
    cs._timeout_stufen(sid, 'coaching_loop')

    counts = cs.get_live_timeout_counts()
    assert counts, "Der Founder-Zaehler hat gar nicht gezaehlt — Soll-0-Alarm waere blind."
    blob = repr(counts)
    assert sid not in blob, (
        f"Der prozess-globale Timeout-Zaehler traegt eine Session-Kennung ({sid}) — "
        "Punkt-28-Verstoss (Cross-Tenant-Risiko im geteilten Zustand)."
    )
    assert set(counts) == {'analyse_loop', 'coaching_loop'}
    assert counts['analyse_loop'] == 4


def test_per_sid_zaehler_ist_wirklich_per_sid(monkeypatch, sauberer_sitzungszustand):
    """Ein klemmender Fremd-Call darf dem eigenen Berater keinen Ausfall melden."""
    from extensions import socketio

    schwelle = config.LIVE_LLM_TIMEOUT_HINWEIS_AB
    if schwelle < 3:
        pytest.skip(
            f"LIVE_LLM_TIMEOUT_HINWEIS_AB={schwelle}: zwei Aussetzer wuerden die Schwelle "
            "schon reissen — die Trennung waere nicht ohne Emit pruefbar."
        )

    sid_a, sid_b = 'sid-a', 'sid-b'
    _sid_anlegen(sid_a)
    _sid_anlegen(sid_b)

    emits = []
    monkeypatch.setattr(
        socketio, 'emit',
        lambda event, payload=None, **kw: emits.append(event),
    )

    cs._timeout_stufen(sid_a, 'analyse_loop')
    cs._timeout_stufen(sid_a, 'analyse_loop')
    cs._timeout_stufen(sid_b, 'coaching_loop')

    with ls._session_state_lock:
        streak_a = ls._session_state[sid_a][cs._SID_TIMEOUT_KEY]
        streak_b = ls._session_state[sid_b][cs._SID_TIMEOUT_KEY]

    assert streak_a == 2, f"sid_a haette 2 Aussetzer in Folge: {streak_a}"
    assert streak_b == 1, (
        f"sid_b traegt {streak_b} statt 1 — der Zaehler ist offenbar geteilt statt per-sid."
    )
    assert emits == [], "Unterhalb der Schwelle darf nichts gemeldet werden."
