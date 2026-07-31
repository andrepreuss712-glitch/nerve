"""Waechter 1 (Verklemmungs-Test) — Phase 08.23.2.LOCK-1.

WAS AM 30.07. PASSIERT IST (Zeitachse aus dem Journal, verbatim):
    09:28:07  manual_ewb — keine Reaktion
    09:29:11  manual_ewb — keine Reaktion
    09:29:55  manual_ewb — keine Reaktion
    09:30:07  manual_ewb — keine Reaktion
    09:30:18  [Beenden] ENTRY  — und danach NICHTS mehr.
Vier Knopfdruecke und ein Auflegen hingen STUMM. Es stand KEIN 504 im Log, keine
Fehlermeldung, keine Anzeige. Der Nutzer sah einen ewigen Ladebalken; Transkript,
Auswertung und Kostenzeile des Anrufs waren weg.

WARUM DIESER WAECHTER AUF EIN EREIGNIS ASSERTIERT UND NICHT AUF RUECKKEHR (P-4):
"die Funktion ist zurueckgekehrt" beweist hier NICHTS. Zwei Breitband-Klammern im
Knopf-Pfad fangen jede Exception weg — deepgram_service.py:1000 (`except Exception
as _btn_emit_e`) und :1041 (`except Exception as _btn_log_e`). Im Auflege-Pfad tut
routes/app_routes.py:177 dasselbe und setzt `_beenden_sid = None`, was ohne
geposteten call_id in `reason='no_session'` mit Status 200 endet — die MASKIERTE
Variante des Fehlers. Eine tiefer geworfene Zeitueberschreitung wuerde dort still
verschluckt. Deshalb assertiert dieser Waechter auf ein BEOBACHTBARES Ereignis:
Prueflung A auf ein `pip_stream_error`-Emit, Prueflung B auf Status 503 +
`reason='state_locked'`.

ERST ROT: am Stand vor Plan 03 muessen die beiden VERKLEMMUNGS-Tests fehlschlagen.
Die zwei gepaarten Frei-Fall-Kontrolltests sind schon heute GRUEN und sollen es sein —
sie sind der Anti-Stub-Gegenpol (ohne sie waere eine Implementierung, die IMMER
absagt, gruen). Wer "1 failed" als halben Waechter liest und den gruenen Kontrolltest
"repariert", zerstoert genau diese Absicherung.

LOKAL WIRD DIE api_beenden-HAELFTE UEBERSPRUNGEN. Die zwei api_beenden-Tests brauchen
die `client`-Fixture und damit `TEST_DATABASE_URL`; fehlt sie, ruft tests/conftest.py:824-827
`pytest.skip`. Ein `skipped` ist KEIN Beleg. Der Rot-Beleg fuer diese Haelfte stammt
deshalb aus einem DIREKTEN pytest-Lauf AUF DEM PROD-SERVER gegen eine frisch
provisionierte Wegwerf-`nerve_test`, den CLAUDIAN faehrt (SSH-Mandat) — NICHT aus einem
`deploy.sh`-Gate-Lauf; `deploy.sh:79-80` laedt das tar VOR dem Gate hoch, Produktion
bekaeme Dateien auf die Platte, die fuer den Beweis nicht gebraucht werden. Befehlsblock
siehe Plan 01, Abschnitt `<erst_rot_pflicht>` ("Rot-Beleg II").

WARUM _extract_handler UND throwaway KOPIERT SIND (aus tests/test_mode_switch_event.py:23-39
bzw. tests/test_stabil1_beenden_guard.py:101-195): conftest.py ist gemeinsame Infrastruktur
fuer die ganze Suite; eine Aenderung dort riskiert alles und erzeugt einen Datei-Konflikt
mit den anderen Plaenen dieser Phase. Bekannte Grenze: driften die Originale, driften die
Kopien nicht mit.

Kein pytest-Marker: deploy.sh:221 fahrt `-m "not live and not perf"` — ein Marker wuerde
diesen Waechter aus dem Abnahme-Gate ausschliessen.
"""
import threading
import uuid
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import text
from werkzeug.security import generate_password_hash

import services.live_session as ls
from database.db import get_session
from database.models import AuditLog, Call, ConversationLog, Organisation, User
from tests.conftest import cleanup_rows


_PRUEFLING_TIMEOUT_S = 10.0   # Praezedenz test_live_session_ghost_sid.py:36
_HOLDER_NOTBREMSE_S = 30.0
_HELD_READY_S = 5.0
_SID_EWB = 'lock1-w1-ewb-001'


def _extract_handler(event_name):
    """Extrahiert einen registrierten SocketIO-Handler aus register_audio_handlers.

    Bewusste Kopie aus tests/test_mode_switch_event.py:23-39 (siehe Modul-Docstring).
    """
    registered = {}

    mock_sio = MagicMock()
    # sio.on(event) gibt einen Decorator zurueck der fn registriert und unveraendert zurueckgibt
    mock_sio.on = lambda event: (lambda fn: registered.__setitem__(event, fn) or fn)

    from services.deepgram_service import register_audio_handlers
    register_audio_handlers(mock_sio)

    return registered[event_name], mock_sio


@pytest.fixture
def ewb_sid_aufraeumen():
    """Raeumt die Wegwerf-sid _SID_EWB weg — NACH der Riegel-Freigabe.

    LOAD-BEARING, deshalb eine Fixture und kein `finally` im Test: _cleanup_sid nimmt
    selbst den _session_state_lock. Stuende es im Test-Koerper, blockierte das Aufraeumen
    am noch gehaltenen Riegel und der Test liefe bis zur 30s-Notbremse (gemessen: 30.01s
    statt 10s). Als Fixture VOR held_session_state_lock in der Parameter-Liste wird es
    ZULETZT abgebaut — da ist der Riegel frei.
    """
    yield
    _cleanup_sid(_SID_EWB)


@pytest.fixture
def held_session_state_lock():
    """Haelt _session_state_lock in einem Daemon-Faden, solange der Test laeuft.

    Liefert eine Anmelde-Funktion. Jeder Pruefling-Faden meldet sich direkt nach start()
    an und wird NACH der Riegel-Freigabe eingesammelt. Das ist hier PFLICHT, nicht Kosmetik:
    im ROT-Lauf steht der Pruefling nach dem gescheiterten Assert noch am Riegel und liefe
    sonst mitten in den throwaway-Teardown hinein (der ruft _clear_leaked_sessions_for_user,
    das denselben Riegel nimmt).
    """
    _nachzuegler = []
    held = threading.Event()
    release = threading.Event()

    def _halte():
        with ls._session_state_lock:
            held.set()
            # Notbremse: selbst bei kaputtem Teardown ist der Riegel nach 30s frei.
            # deploy.sh:221 hat KEINEN pytest-Timeout -> ein Haenger haengt den Deploy.
            release.wait(timeout=_HOLDER_NOTBREMSE_S)

    h = threading.Thread(target=_halte, daemon=True, name='LOCK1-holder')
    h.start()
    assert held.wait(timeout=_HELD_READY_S), 'Halter-Faden hat den Riegel nicht genommen'

    def registriere_pruefling(t):
        _nachzuegler.append(t)

    try:
        yield registriere_pruefling
    finally:
        release.set()
        h.join(timeout=5.0)
        for _t in _nachzuegler:
            _t.join(timeout=5.0)


def _emit_aufrufe(mock_sio, event):
    """Alle mock_sio.emit-Aufrufe mit args[0] == event, als Liste von (args, kwargs)."""
    treffer = []
    for _call in mock_sio.emit.call_args_list:
        _args, _kwargs = _call
        if _args and _args[0] == event:
            treffer.append((_args, _kwargs))
    return treffer


def _cleanup_sid(sid):
    with ls._session_state_lock:
        ls._session_state.pop(sid, None)


def _clear_leaked_sessions_for_user(user_id):
    """Session-Isolation: entfernt VOR einem no-op/guard-POST alle _session_state-Eintraege
    des throwaway-Users, damit der Stufe-2 user_id-Scan (app_routes.py:164-171) NICHTS findet
    -> _bs bleibt None -> der Guard (:206) feuert tatsaechlich. Kopie aus
    tests/test_stabil1_beenden_guard.py:106-115."""
    with ls._session_state_lock:
        stale_sids = [s for s, st in ls._session_state.items() if st.get('user_id') == user_id]
        for s in stale_sids:
            ls._session_state.pop(s, None)


# ── Prueflung A: handle_manual_ewb ────────────────────────────────────────────

def test_manual_ewb_kehrt_mit_fehler_zurueck(ewb_sid_aufraeumen, held_session_state_lock):
    """Der Knopfdruck muss bei klemmendem Riegel MIT FEHLER zurueckkehren, nicht stumm haengen.

    Parameter-Reihenfolge LOAD-BEARING: `ewb_sid_aufraeumen` steht VORNE und wird deshalb
    ZULETZT abgebaut — erst dann ist der Riegel frei und _cleanup_sid kann ihn nehmen.
    """
    handler, mock_sio = _extract_handler('manual_ewb')
    c = threading.Thread(target=lambda: handler({'text': 'zu_teuer'}, sid=_SID_EWB),
                         daemon=True, name='LOCK1-pruefling-A')
    c.start()
    held_session_state_lock(c)   # Nachzuegler-Anmeldung, Schicht 4 Punkt 3b
    c.join(timeout=_PRUEFLING_TIMEOUT_S)
    assert not c.is_alive(), (
        f"handle_manual_ewb kehrte mit gehaltenem _session_state_lock nicht innerhalb "
        f"{_PRUEFLING_TIMEOUT_S}s zurueck. Vier Riegel-Nahmen liegen im synchronen Pfad: "
        f"deepgram_service.py:966, :982 (get_anonymisierer), :1011, :1027. "
        f"Am 30.07. hingen genau so vier Klicks stumm (09:28:07/09:29:11/09:29:55/09:30:07).")
    _fehler = _emit_aufrufe(mock_sio, 'pip_stream_error')
    assert _fehler, (
        "handle_manual_ewb kehrte zurueck, aber OHNE Fehler-Ereignis. Genau das ist die "
        "Falle: die Breitband-Klammern dg:1000/:1041 verschlucken jede Exception, der "
        "Handler laeuft weiter und der Nutzer sieht wieder nichts.")
    assert any('blockiert' in str(_a) for _a in _fehler), \
        f"pip_stream_error ohne verstaendliche Begruendung: {_fehler!r}"
    assert not mock_sio.start_background_task.called, (
        "handle_manual_ewb hat trotz blockiertem Riegel den Haiku-Hintergrund-Task "
        "gestartet — es wurde also nicht frueh zurueckgekehrt.")


def test_manual_ewb_laeuft_mit_freiem_riegel_normal_durch(ewb_sid_aufraeumen):
    """Anti-Stub-Gegenpol: mit FREIEM Riegel muss der Handler bis zum Hintergrund-Task durchlaufen.

    KEINE Halter-Fixture — sonst prueft dieser Test nichts.

    Die drei Patches halten Netz, DB und spaCy aus dem Weg: emit_intent_event schreibt
    sonst eine intent_event-Zeile, anonymize/anonymize_output ziehen sonst das
    Anonymisierungs-Modell. Alle drei werden im Handler FUNKTIONSLOKAL importiert, der
    Patch am Quell-Modul greift also. sio.start_background_task ist ein MagicMock ->
    _run laeuft NIE -> weder Haiku noch record_ewb_click werden erreicht.
    """
    handler, mock_sio = _extract_handler('manual_ewb')
    with patch('services.intent_event_writer.emit_intent_event'), \
         patch('services.anonymization.anonymize', return_value=('zu_teuer', {})), \
         patch('services.anonymization.anonymize_output', return_value='zu_teuer'):
        handler({'text': 'zu_teuer'}, sid=_SID_EWB)
    assert mock_sio.start_background_task.called, (
        "Mit FREIEM Riegel muss der Handler bis zum Hintergrund-Task durchlaufen. "
        "Laeuft er nicht durch, ist die Riegel-Probe eine Blanko-Absage (Anti-Stub).")
    assert not any('blockiert' in str(_a)
                   for _a in _emit_aufrufe(mock_sio, 'pip_stream_error'))


# ── Prueflung B: POST /api/beenden ────────────────────────────────────────────

def _post_beenden_in_eigenem_kontext(user_id, ergebnis):
    """POST /api/beenden mit einem EIGENEN Test-Client, vollstaendig in DIESEM Faden.

    WARUM NICHT DER `client` DER FIXTURE (Gate-Befund 2026-07-31):
    `flask.app_ctx` ist eine ContextVar und damit faden-lokal. Der Kontextmanager-Client
    (`with flask_app.test_client() as c`, tests/conftest.py:843) haelt den Request-Kontext
    nach dem Aufruf fest und raeumt ihn beim Verlassen des `with` ab — im HAUPT-Faden.
    Laeuft der Aufruf in einem ZWEITEN Faden, ist die ContextVar dort gesetzt und im
    Haupt-Faden leer: `LookupError: ContextVar 'flask.app_ctx'` (flask/ctx.py:264), der
    Teardown bricht ab BEVOR er aufraeumt, und es leaken Zeilen in users/organisations/
    profiles. Das war KEIN Produktiv-Fehler — der Riegel-Fix wirkte im selben Lauf
    nachweislich (`[LOCKWATCH] api_beenden abgebrochen`) — sondern ein Mangel im Testaufbau.

    Deshalb: eigener Client OHNE Kontextmanager (`preserve_context` bleibt False, es wird
    also gar nichts ueber den Aufruf hinaus festgehalten), Sitzungs-Cookie in diesem Faden
    gesetzt. Push UND Pop passieren damit beide hier. Der Client der Fixture wird von
    diesem Faden nicht angefasst.
    """
    from app import app as flask_app   # erst NACH der conftest-Umbindung importieren
    tc = flask_app.test_client()
    with tc.session_transaction() as sess:
        sess['user_id'] = user_id
    ergebnis.append(tc.post('/api/beenden', json={'session_mode': 'cold_call'}))

@pytest.fixture
def throwaway(client):
    """Throwaway Organisation + User (ORM) — NIE die geschuetzte Baseline id=1 anfassen.

    Kopie aus tests/test_stabil1_beenden_guard.py:119-195 INKLUSIVE des vollstaendigen
    Teardowns (scoped audit_log-Trigger-Bypass + cleanup_rows). Ohne den vollstaendigen
    Teardown blockiert der POST-SUITE-Check deploy.sh:225-228.
    """
    db = client._test_session
    org = Organisation(name=f"[LOCK1-TEST] org {uuid.uuid4().hex[:8]}", plan='starter')
    db.add(org)
    db.flush()  # feuert trg_mk_tenant_org -> tenant_orgs-Row automatisch
    user = User(
        email=f"lock1-{uuid.uuid4().hex[:8]}@nerve.local",
        passwort_hash=generate_password_hash('pw'),
        rolle='owner', org_id=org.id, aktiv=True, onboarding_done=True,
    )
    db.add(user)
    db.commit()
    org_id, user_id = org.id, user.id

    tenant_org_row = db.execute(
        text("SELECT id FROM tenant_orgs WHERE legacy_org_id = :o"), {"o": org_id}
    ).first()
    tenant_org_id = tenant_org_row[0] if tenant_org_row else None

    with client.session_transaction() as sess:
        sess['user_id'] = user_id

    tracker = {'user_id': user_id, 'org_id': org_id, 'call_ids': [], 'conv_ids': []}
    yield tracker

    # Das Zeilen-Aufraeumen MUSS auch dann laufen, wenn ein Schritt davor wirft
    # (Gate-Befund 2026-07-31): sonst reisst JEDER kuenftige Teardown-Fehler dieselbe
    # Zeilen-Spur in users/organisations/profiles auf, der BASELINE-AUTO-FIX muss
    # hinterherraeumen und Folge-Tests laufen auf verschmutzter DB. Ein Wegwerf-Test,
    # der die Baseline verdreckt, ist ein echter Mangel — kein "ist ja nur der Teardown".
    try:
        _clear_leaked_sessions_for_user(user_id)
    except Exception as _sess_e:   # noqa: BLE001 - Diagnose-Pfad, darf nie das Aufraeumen kosten
        print(f"[LOCK1-TEST] _clear_leaked_sessions_for_user fehlgeschlagen: {_sess_e!r}; "
              f"Zeilen-Aufraeumen laeuft trotzdem weiter")

    call_ids = [c for c in tracker['call_ids'] if c]
    conv_ids = [c for c in tracker['conv_ids'] if c]

    cleanup_db = get_session()
    try:
        # audit_log traegt trg_audit_log_immutable (Migration 0026, BEFORE DELETE -> RAISE),
        # der AUCH fuer den Owner feuert. nerve_app OWNT audit_log -> Trigger SCOPED
        # deaktivieren, ALLE audit_log-Rows dieses Wegwerf-Users/-Orgs loeschen, Trigger im
        # finally IMMER reaktivieren. Drei getrennte committete TX.
        # Auch dieser Block darf das Zeilen-Aufraeumen nicht kosten (Gate-Befund 2026-07-31):
        # scheitert er, bleiben audit_log-Zeilen liegen und cleanup_rows stallt an den
        # NO-ACTION-FKs — aber der VERSUCH ist allemal besser als ein uebersprungenes Delete.
        try:
            cleanup_db.execute(text(
                "ALTER TABLE public.audit_log DISABLE TRIGGER trg_audit_log_immutable"))
            cleanup_db.commit()
            try:
                cleanup_db.query(AuditLog).filter(
                    (AuditLog.user_id == user_id) | (AuditLog.org_id == org_id)
                ).delete(synchronize_session=False)
                cleanup_db.commit()
            finally:
                cleanup_db.execute(text(
                    "ALTER TABLE public.audit_log ENABLE TRIGGER trg_audit_log_immutable"))
                cleanup_db.commit()
        except Exception as _audit_e:   # noqa: BLE001 - Diagnose-Pfad
            cleanup_db.rollback()       # CLAUDE.md DB-Regel: nie stiller except ohne rollback
            print(f"[LOCK1-TEST] audit_log-Aufraeumen fehlgeschlagen: {_audit_e!r}; "
                  f"cleanup_rows laeuft trotzdem")

        spec = {}
        if call_ids:
            spec[Call] = call_ids
        if conv_ids:
            spec[ConversationLog] = conv_ids
        spec[User] = [user_id]
        if tenant_org_id:
            spec['public.tenant_orgs'] = [tenant_org_id]
        spec[Organisation] = [org_id]
        cleanup_rows(cleanup_db, spec)
    finally:
        cleanup_db.close()


def test_api_beenden_kehrt_mit_fehler_zurueck(client, throwaway, held_session_state_lock):
    """Das Auflegen muss bei klemmendem Riegel MIT FEHLER zurueckkehren, nicht stumm haengen.

    Die Parameter-Reihenfolge ist LOAD-BEARING: `held_session_state_lock` steht ZULETZT,
    wird also ZUERST abgebaut. Pflicht, weil der throwaway-Teardown
    _clear_leaked_sessions_for_user ruft, das denselben Riegel nimmt — stuende die
    Halter-Fixture vorne, haenge der Teardown am gehaltenen Riegel und mit ihm der Deploy.

    _clear_leaked_sessions_for_user VOR dem Faden-Start entfaellt hier ersatzlos: es
    braeuchte den Riegel, der zu diesem Zeitpunkt schon gehalten wird. Es wird auch nicht
    gebraucht — der Wegwerf-User hat keine Session, und der Stufe-2-Scan kommt ohnehin
    nicht bis zum Ergebnis, weil er am Riegel abbricht.

    Der Flask-Test-Client ist nicht faden-sicher. Faden C benutzt deshalb NICHT den `client`
    der Fixture, sondern einen eigenen (siehe _post_beenden_in_eigenem_kontext) — sonst
    reisst die faden-lokale ContextVar `flask.app_ctx` den Teardown des Haupt-Fadens ab und
    die Wegwerf-Zeilen leaken.
    """
    antwort = []
    faden_fehler = []

    def _lauf():
        try:
            _post_beenden_in_eigenem_kontext(throwaway['user_id'], antwort)
        except BaseException as _e:       # noqa: BLE001 - Diagnose, sonst stiller Leer-Fall
            faden_fehler.append(_e)

    c = threading.Thread(target=_lauf, daemon=True, name='LOCK1-pruefling-B')
    c.start()
    held_session_state_lock(c)   # Nachzuegler-Anmeldung, Schicht 4 Punkt 3b
    c.join(timeout=_PRUEFLING_TIMEOUT_S)
    assert not c.is_alive(), (
        f"POST /api/beenden kehrte mit gehaltenem _session_state_lock nicht innerhalb "
        f"{_PRUEFLING_TIMEOUT_S}s zurueck. Drei Riegel-Nahmen liegen davor: "
        f"app_routes.py:157, :171 (der Rahmen aus dem py-spy-Abzug), :188. "
        f"Am 30.07. um 09:30:18 stand [Beenden] ENTRY im Log — und danach nichts mehr.")
    assert not faden_fehler, (
        f"Faden C ist an einer Ausnahme gestorben statt zu antworten: {faden_fehler[0]!r}. "
        f"Das ist KEIN Riegel-Befund — der Testaufbau ist kaputt.")
    assert antwort, "Faden C kam zurueck, hat aber keine Antwort abgelegt."
    r = antwort[0]
    assert r.status_code == 503, f"Erwartet 503, war {r.status_code}"
    assert (r.get_json() or {}).get('reason') == 'state_locked', (
        f"Falscher Grund: {r.get_json()!r}. 'no_session' waere die MASKIERTE Variante — "
        f"app_routes.py:177 setzt bei jeder Exception _beenden_sid=None, was ohne "
        f"geposteten call_id in reason='no_session' mit 200 endet.")


def test_api_beenden_mit_freiem_riegel_ist_kein_state_locked(client, throwaway):
    """Anti-Stub-Gegenpol: mit FREIEM Riegel ist die Antwort 200 + no_session, kein 503.

    KEINE Halter-Fixture. Ohne diesen gepaarten Positiv-Fall waere eine Implementierung,
    die IMMER 503 absagt, gruen. Bestands-Verhalten belegt in
    tests/test_stabil1_beenden_guard.py::test_beenden_ohne_session_ist_noop.
    """
    _clear_leaked_sessions_for_user(throwaway['user_id'])
    r = client.post('/api/beenden', json={'session_mode': 'cold_call'})
    assert r.status_code == 200, f"Erwartet 200, war {r.status_code}"
    assert (r.get_json() or {}).get('reason') == 'no_session', (
        f"Mit freiem Riegel darf kein Riegel-Fehler entstehen: {r.get_json()!r}")
