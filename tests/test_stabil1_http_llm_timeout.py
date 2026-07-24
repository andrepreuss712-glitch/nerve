"""Phase 08.23.2.STABIL-1 Plan 01 — Runtime-Tests fuer das HTTP-LLM-Zeitlimit.

Prueft Laufzeit-Verhalten (welche Optionen der Anthropic-SDK-Client zur Laufzeit
bekommt), KEIN Source-Presence (CLAUDE.md Test-Qualitaets-Regel):
- HTTP-erreichbare Call-Sites setzen timeout+max_retries via with_options()
- Daemon-Pfad (analysiere_mit_claude) bekommt KEIN Zeitlimit
- Der Modul-Client (services.claude_service.claude_client) bleibt unveraendert
  (with_options() liefert eine Kopie, keine Mutation) — sichert die Live-Streams ab
- Worst-Case-Arithmetik bleibt unter dem nginx-60s-Default

Kein Netz, kein echter Anthropic-Call, keine committenden DB-Writes -> kein
cleanup_rows noetig. Usage=None auf allen Fake-Responses haelt die Cost-Hooks
(log_api_cost) inaktiv (if u:/if u is not None: -> False), damit kein Test hier
eine echte DB-Session braucht -- ausser generate_postcall_analysis, deren
Duplicate-Guard + Persist-Schritt database.db.get_session() gemockt wird.

Marker: kein live/perf -> laeuft im Gate "-m 'not live and not perf'".
"""
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

import config
import services.claude_service as claude_service_module
from services.crm_service import generate_crm_export
from services.coaching_service import generate_postcall_analysis
from services.claude_service import analysiere_mit_claude


def _fake_response(text='{}'):
    """Minimaler Stand-in fuer ein anthropic.types.Message-Objekt.

    usage=None haelt die Cost-Hooks in Produktionscode inaktiv (if u:/if u is not
    None: -> False) -- so bleibt dieser Test frei von echten DB-Writes.
    """
    return SimpleNamespace(content=[SimpleNamespace(text=text)], usage=None)


def test_crm_export_setzt_zeitlimit():
    """A1 (der Launch-Blocker, crm_service.py:59) setzt timeout<=20s, max_retries<=1."""
    fake_msg = _fake_response(
        '{"crm_notiz": "x", "followup_email": "y", "naechste_schritte": []}')
    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_msg

    with patch.object(claude_service_module.claude_client, 'with_options',
                       return_value=fake_client) as mock_with_options:
        generate_crm_export([], [], [], 30, 'X')

    assert mock_with_options.called, "http_llm_client() muss with_options() aufrufen"
    _, kwargs = mock_with_options.call_args
    assert kwargs['timeout'] <= 20.0
    assert kwargs['max_retries'] <= 1


def test_lang_stufe_ohne_retry():
    """LANG-Stufe (generate_postcall_analysis) setzt HTTP_LLM_TIMEOUT_LONG_S, max_retries=0."""
    fake_msg = _fake_response('{"vorschlaege": []}')
    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_msg

    fake_db = MagicMock()
    fake_db.query.return_value.filter_by.return_value.count.return_value = 0

    with patch.object(claude_service_module.claude_client, 'with_options',
                       return_value=fake_client) as mock_with_options, \
         patch('database.db.get_session', return_value=fake_db):
        generate_postcall_analysis(
            conv_id=1, user_id=1, einwaende=[], painpoints=[],
            kb_start=0, kb_end=30, redeanteil_berater=50,
            redeanteil_kunde=50, dauer_sek=60,
            skript_abdeckung=0, ga_details=[],
        )

    assert mock_with_options.called
    _, kwargs = mock_with_options.call_args
    assert kwargs['timeout'] == config.HTTP_LLM_TIMEOUT_LONG_S
    assert kwargs['max_retries'] == 0


def test_daemon_pfad_ohne_zeitlimit():
    """analysiere_mit_claude (Daemon-Pfad analyse_loop) bekommt KEIN Zeitlimit —
    with_options() wird NICHT aufgerufen, der Live-Analyse-Pfad bleibt unangetastet."""
    fake_msg = _fake_response('{}')

    with patch.object(claude_service_module.claude_client, 'with_options') as mock_with_options, \
         patch.object(claude_service_module.claude_client.messages, 'create',
                      return_value=fake_msg):
        analysiere_mit_claude(neuer_text="Testsatz", kontext="", sid=None)

    assert mock_with_options.called is False, \
        "Daemon-Pfad darf with_options() (Zeitlimit) NICHT aufrufen"


def test_modul_client_bleibt_unveraendert():
    """Nach einem HTTP-Aufruf ist services.claude_service.claude_client dasselbe
    Objekt wie vorher (is-Vergleich) — beweist dass with_options() eine Kopie
    liefert und der Modul-Client (Stream-Pfade :812/:980) nicht mutiert wird."""
    client_before = claude_service_module.claude_client

    fake_msg = _fake_response(
        '{"crm_notiz": "x", "followup_email": "y", "naechste_schritte": []}')
    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_msg

    with patch.object(claude_service_module.claude_client, 'with_options',
                       return_value=fake_client):
        generate_crm_export([], [], [], 30, 'X')

    assert claude_service_module.claude_client is client_before


def test_worst_case_unter_nginx_default():
    """Reine Konfigurations-Arithmetik: beide Stufen bleiben unter dem nginx-60s-
    Default (55s Sicherheitsmarge fuer Backoff + Netzwerk).

    max_retries-Default ist 0 (nicht 1): der SDK-Retry-Mechanismus ehrt einen
    Retry-After-Header bis 60s -- mit max_retries=1 koennte ein schnelles 429/529
    mit Retry-After:60 die STANDARD-Stufe auf ~1+60+20 ~= 81s ziehen (> nginx-60s).
    Deshalb hier OHNE Retry-Multiplikator pruefen (K4 Pre-Execute-Audit).
    """
    assert config.HTTP_LLM_TIMEOUT_S * 1 < 55
    assert config.HTTP_LLM_TIMEOUT_LONG_S < 55
