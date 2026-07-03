"""Phase 08.23.2.PERSID Plan 01 — Concurrency-Test-Skeleton (SPEC Req 12 Teil 1, D-10).

Prueft: Zwei parallele WebSocket-Sessions (User A / User B, verschiedene Orgs) tauschen
KEINE Daten aus — weder Live-Transkript noch Analyse-Ergebnis noch Session-State.

S1-Kritisch: diese Datei setzt NERVE_TESTING=1 GANZ OBEN im Modul, VOR dem `import app`.
  Grund: app.py startet Daemons (analyse_loop/coaching_loop/slow_lane_consumer) auf
  MODUL-EBENE. Wuerde der Import OHNE NERVE_TESTING=1 laufen, wuerden echte Daemon-Threads
  geweckt -> blind-gruene Tests, Flakes, Haiku/Deepgram-Aufrufe.
  app.config['TESTING'] waere zu spaet (NACH `import app` setzbar) — daher ENV-Var.

D-10 (Deploy-Contract): Voll-Assertions werden in Plan 06 (Welle E) scharfgeschaltet,
  wenn ALLE per-SID-Migrationen abgeschlossen sind. Bis dahin: Skeleton mit pytest.skip().

GEPAARTE 7 Assertion-Ziele fuer Welle E (referenz fuer Plan 06):
  1. POSITIV: User A sieht seine Analyse im State (analyse_loop lieferte Ergebnis)
  2. ISOLATION: User A sieht KEINE Daten von User B im State
  3. POSITIV: User B sieht seine Analyse
  4. ISOLATION: User B sieht KEINE Daten von User A
  5. RESET: Nach api_beenden sauberung von Seite A: B bleibt unveraendert (kein Cross-Reset)
  6. B1-SNAPSHOT-REIHENFOLGE: api_beenden VOR socket-disconnect (sonst Late-Write-Ghost-Drop)
  7. LEER-SKIP: Doppel-Feuer (handle_disconnect + api_beenden) produziert keinen leeren Call-Record

HINWEIS B1-Vorgriff (aus Plan-01-Task-4-Kommentar):
  api_beenden ist eine HTTP-Route (app_routes.py) ohne Socket-sid; der disconnect-Handler
  (deepgram_service.py:806-815) poppt _session_state[sid]. Reihenfolge im Test:
    client.post('/api/beenden')  # ERST
    client.disconnect()          # DANN
  Plan 06 haengt hieran den B1-Snapshot-Beenden-Test.
"""

# ── S1-KRITISCH: ENV VOR import app setzen ────────────────────────────────────
# Diese Zeilen MUESSEN an den Anfang des Moduls, BEVOR irgendein app-Import folgt.
# pytest sammelt Testdateien via Import — daher wirkt die ENV-Var beim Collect-Zeitpunkt.
import os as _os_testing_guard
_os_testing_guard.environ['NERVE_TESTING'] = '1'
# ─────────────────────────────────────────────────────────────────────────────

import uuid

import pytest


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope='module')
def _app():
    """Flask-App-Instanz fuer den Concurrency-Test.
    NERVE_TESTING=1 ist oben gesetzt → Daemons werden NICHT gestartet.
    Skippt in lokaler SQLite-Umgebung (CRM-Schema nicht unterstuetzt).
    """
    # Lazy-Import nach ENV-Setup
    try:
        import app as _app_module
        _app_module.app.config['TESTING'] = True
        _app_module.app.config['WTF_CSRF_ENABLED'] = False
        return _app_module.app
    except Exception as e:
        pytest.skip(f"app import fehlgeschlagen (Welle-0 Skeleton, SQLite-CRM-Limitation): {e}")


@pytest.fixture(scope='module')
def _two_clients(_app):
    """Zwei Flask-Test-Clients (User A Org 1 / User B Org 2).

    In Welle E werden diese mit echten SocketIO-Test-Clients und simulierten
    WebSocket-Sessions verbunden. Vorerst: zwei reine HTTP-Test-Clients.
    """
    if _app is None:
        pytest.skip("app nicht verfuegbar")
    client_a = _app.test_client()
    client_b = _app.test_client()
    return client_a, client_b


@pytest.fixture
def _fake_analyse(monkeypatch):
    """Mock-Naht: analysiere_mit_claude → deterministisches Fake-Ergebnis.
    Kein LLM-Call, kein Netz-Aufruf.
    """
    import services.claude_service as cs

    def _fake(neuer_text, kontext, *, sid=None, **kwargs):
        return {'einwand': False, 'notiz': 'fake-analyse', 'einwand_typ': None}

    monkeypatch.setattr(cs, 'analysiere_mit_claude', _fake)


@pytest.fixture
def _fake_anon(monkeypatch):
    """Mock-Naht: anonymize/anonymize_for_storage → Identity-Funktion.
    PFLICHT (Falle a): ohne dies koennte anonymize blind-gruene Tests produzieren
    (GLiNER-Load wuerde PII-Felder veraendern, assertions failen).
    """
    import services.anonymization as anon

    def _identity(text, sid=None):
        return text, 'identity'

    monkeypatch.setattr(anon, 'anonymize', _identity, raising=False)
    monkeypatch.setattr(anon, 'anonymize_for_storage',
                        lambda text, sid=None: (text, 'identity'), raising=False)


# ── Skeleton-Tests (D-10: Voll-Assertions mit Welle E) ───────────────────────

def test_two_tenant_state_isolation_skeleton(_two_clients, _fake_analyse, _fake_anon):
    """[SKELETON] Zwei-Tenant-Isolations-Assertion — Voll-Assertions in Welle E (Plan 06).

    Prueft: User A und User B in getrennten Sessions sehen keine Daten des jeweils
    anderen. State-Isolation, Transkript-Isolation, Analyse-Isolations-Assertion.

    Assertion-Ziele fuer Welle E (7 gepaarte, siehe Modul-Docstring):
      1+2: User A Positiv + Isolation
      3+4: User B Positiv + Isolation
      5: Reset-Ueberlebens-Check (A-Reset laesst B unveraendert)
      6: B1-Snapshot-Reihenfolge (api_beenden vor disconnect)
      7: Leer-Skip-Guard bei Doppel-Feuer

    TODO (Plan 06 Task 1): MERGE_WINDOW_S -> 0.05 (Falle c); _OneShotTrigger fuer
      analyse_trigger; echte SocketIO-Test-Clients; SID-Setup via init_session_state;
      Mock-Naht _open_deepgram_connection patchen; _qa_pipeline_dispatch -> None.
    """
    pytest.skip(
        "Welle 0 Skeleton — Voll-Assertions landen mit Welle E (Plan 06, D-10). "
        "Alle 7 Assertion-Ziele sind im Modul-Docstring dokumentiert."
    )


def test_api_beenden_vor_disconnect_order_skeleton():
    """[SKELETON] B1-Snapshot-Reihenfolge: api_beenden VOR socket-disconnect.

    Scharfgeschaltet in Plan 06 Welle E. Dokumentiert die Reihenfolge-Anforderung:
      client.post('/api/beenden')  →  client.disconnect()
    Umgekehrte Reihenfolge erzeugt leeren Call-Record (handle_disconnect poppt State
    bevor api_beenden den Snapshot stashen kann — B1-Blocker-Lehre).
    """
    pytest.skip("Welle 0 Skeleton — B1-Snapshot-Reihenfolge-Test in Plan 06 (D-10).")


def test_double_fire_empty_record_guard_skeleton():
    """[SKELETON] Leer-Skip-Guard bei Doppel-Feuer (handle_disconnect + api_beenden).

    Scharfgeschaltet in Plan 06 Welle E. Assertiert: stash_ended_session macht
    Leer-Skip (handle_disconnect :810-811 setdefault erzeugt {} → wird als leer
    erkannt und NICHT als Call-Record persistiert — N-1-Blocker-Lehre).
    """
    pytest.skip("Welle 0 Skeleton — Leer-Skip-Guard in Plan 06 (D-10).")


# ── Compile-Time-Guard ────────────────────────────────────────────────────────

def test_nerve_testing_env_is_set_before_app_import():
    """Sanity-Check: NERVE_TESTING war zum Import-Zeitpunkt gesetzt.

    Prueft die ENV-Var direkt (kein app-Import noetig — laeuft in jedem Environment).
    In Welle E wird hier zusaetzlich assertiert, dass keine Daemon-Threads laufen.
    """
    assert _os_testing_guard.environ.get('NERVE_TESTING') == '1', (
        "NERVE_TESTING wurde nicht vor dem Import gesetzt (S1-Falle). "
        "Die ENV-Var muss GANZ OBEN in dieser Datei, VOR allen app-Imports, gesetzt werden."
    )
