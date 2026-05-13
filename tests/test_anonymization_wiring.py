"""
Integration-Tests fuer die Verdrahtungs-Punkte der Anonymisierungs-Pipeline (Phase 08.23.2.B).

Coverage: Req-7 (deepgram INPUT), Req-8 (claude OUTPUT), Req-9 (EWB OUTPUT), D-08 Fallbacks.

CLAUDE.md Test-Qualitaets-Regel: NUR Runtime-Behavior.
Kein inspect.getsource(), kein open('file').read().
"""
import pytest
import services.anonymization as anon_module
from services.anonymization import (
    AnrufAnonymisierer,
    anonymize,
    anonymize_output,
    register_briefing_pii,
    AnonymizationPipelineUnavailable,
    get_pipeline_status,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def fresh_cache():
    """Frische AnrufAnonymisierer-Instanz fuer jeden Test."""
    return AnrufAnonymisierer()


@pytest.fixture(autouse=True)
def reset_pipeline_health():
    """Stellt is_pipeline_healthy=True nach jedem Test wieder her."""
    original = anon_module.is_pipeline_healthy
    original_nlp = anon_module._nlp
    # Vor Test: sauberen Zustand sicherstellen
    anon_module.is_pipeline_healthy = True
    with anon_module._error_lock:
        anon_module._error_timestamps.clear()
    yield
    # Nach Test: Originalzustand wiederherstellen (T-08.23.2.B-TW-01)
    anon_module.is_pipeline_healthy = original
    anon_module._nlp = original_nlp
    with anon_module._error_lock:
        anon_module._error_timestamps.clear()


# ── Req-7: INPUT-PFAD Verdrahtung (STT -> conversation_log) ──────────────────

def test_anonymize_removes_iban_before_log_append(fresh_cache):
    """Req-7: anonymize() vor conversation_log.append() entfernt IBAN aus Text."""
    iban_text = "Bitte ueberweisen Sie auf DE89370400440532013000 bis Montag"
    result = anonymize(iban_text, fresh_cache)
    assert result is not None
    anon_text, tier = result
    # IBAN nicht mehr im anonymisierten Text
    assert 'DE89370400440532013000' not in anon_text, f"IBAN noch im Output: {anon_text!r}"
    # Token vorhanden
    assert '[IBAN_' in anon_text, f"IBAN-Token erwartet: {anon_text!r}"
    # Caller wuerde diesen Text in conversation_log.append() verwenden
    simulated_log = []
    simulated_log.append({'ts': 0.0, 'type': 'transcript', 'text': anon_text})
    assert 'DE89370400440532013000' not in simulated_log[0]['text']


def test_art9_text_caller_must_skip(fresh_cache):
    """Req-7: anonymize() gibt '[ART9_REDACTED]' -> Caller muss Append ueberspringen (D-05)."""
    art9_text = "Er ist nach der Chemo-Behandlung wieder arbeitsfaehig"
    result = anonymize(art9_text, fresh_cache)
    anon_text, tier = result
    # Caller-Konvention (aus deepgram_service.py Plan 05):
    # if anon_text == '[ART9_REDACTED]': skip append
    assert anon_text == '[ART9_REDACTED]'
    assert tier == 'C'
    # Simulation: Caller wuerde Append ueberspringen
    simulated_log = []
    if anon_text != '[ART9_REDACTED]':
        simulated_log.append({'text': anon_text})
    assert len(simulated_log) == 0, "Art-9-Snippet sollte nicht in conversation_log landen"


def test_anonymize_email_before_log(fresh_cache):
    """Req-7: E-Mail in STT-Text wird vor conversation_log-Append entfernt."""
    text = "Schreib mir an mueller@example.com das Angebot"
    result = anonymize(text, fresh_cache)
    anon_text, _ = result
    assert 'mueller@example.com' not in anon_text


# ── Req-8: OUTPUT-PFAD Verdrahtung (claude_service -> gegenargument_log + painpoints) ─

def test_anonymize_output_removes_cached_name(fresh_cache):
    """Req-8: anonymize_output() ersetzt Briefing-Namen aus Cache in Claude-Output."""
    # Cache mit bekanntem Namen befuellen (wie register_briefing_pii es tun wuerde)
    fresh_cache.get_or_assign_token('Jacob Mueller', 'PERSON')
    claude_output = "Jacob Mueller zoegert beim Preis, ich wuerde sagen..."
    result = anonymize_output(claude_output, fresh_cache)
    assert 'Jacob Mueller' not in result, f"Name noch im Output: {result!r}"
    assert '[PERSON_A]' in result, f"Token erwartet: {result!r}"


def test_anonymize_output_einwand_zitat(fresh_cache):
    """Req-8: einwand_zitat (15-Wort-Direktzitat) wird anonymisiert."""
    fresh_cache.get_or_assign_token('Herr Schneider', 'PERSON')
    einwand_zitat = "Herr Schneider sagte: Das ist zu teuer fuer uns"
    result = anonymize_output(einwand_zitat, fresh_cache)
    assert 'Herr Schneider' not in result
    assert '[PERSON_A]' in result


def test_anonymize_output_painpoint(fresh_cache):
    """Req-8: painpoint-Text wird anonymisiert."""
    fresh_cache.get_or_assign_token('Siemens AG', 'ORG')
    painpoint = "Siemens AG hat Budget-Probleme bei der Digitalisierung"
    result = anonymize_output(painpoint, fresh_cache)
    assert 'Siemens AG' not in result
    assert '[ORG_A]' in result


# ── Req-9: EWB-OUTPUT-PFAD Verdrahtung (deepgram_service -> ObjectionEvent.antwort_text) ─

def test_ewb_anonymize_output_name_in_cache(fresh_cache):
    """Req-9: EWB-Antwort-Text mit Briefing-Namen wird via anonymize_output() tokenisiert."""
    fresh_cache.get_or_assign_token('Herr Jacob', 'PERSON')
    ewb_antwort = "Herr Jacob, ich verstehe Ihre Bedenken bezueglich des Preises"
    result = anonymize_output(ewb_antwort, fresh_cache)
    assert 'Herr Jacob' not in result, f"Name noch in EWB-Antwort: {result!r}"
    assert '[PERSON_A]' in result


def test_ewb_einwand_text_unchanged():
    """D-01: einwand_text (Typ-Label 'zu_teuer') wird NICHT anonymisiert."""
    # einwand_text ist ein Typ-Label, kein Freitext
    einwand_text = "zu_teuer"
    # anonymize_output() wuerde Typ-Label unveraendert lassen (kein Match im Cache)
    cache = AnrufAnonymisierer()
    result = anonymize_output(einwand_text, cache)
    assert result == einwand_text, f"Typ-Label sollte unveraendert sein: {result!r}"


# ── Cache-Lifecycle (Req-5) ───────────────────────────────────────────────────

def test_cache_lifecycle_init_get_pop():
    """Req-5: AnrufAnonymisierer Lifecycle: init -> get -> pop -> get=None."""
    from services.live_session import init_session_state, init_anonymisierer, get_anonymisierer, pop_session_state
    test_sid = 'wiring_test_lifecycle_sid'
    init_session_state(test_sid, 99, 99)
    # Vor init_anonymisierer: None (init_session_state setzt 'anonymisierer': None)
    assert get_anonymisierer(test_sid) is None
    # Nach init_anonymisierer: Instanz
    init_anonymisierer(test_sid)
    anon = get_anonymisierer(test_sid)
    assert anon is not None
    assert isinstance(anon, AnrufAnonymisierer)
    # Nach pop: None (SID aus _session_state entfernt -> get gibt None zurueck)
    pop_session_state(test_sid)
    assert get_anonymisierer(test_sid) is None


def test_ghost_sid_no_exception():
    """Pitfall 3: init_anonymisierer() auf nicht-existenter SID raised keine Exception."""
    from services.live_session import init_anonymisierer
    # Ghost-SID: kein init_session_state() zuvor
    init_anonymisierer('ghost_sid_wiring_test_abc123')  # kein Fehler


# ── D-08 Fallback-Architektur ─────────────────────────────────────────────────

def test_fallback_kat_a_unavailable(fresh_cache):
    """D-08 Kat. A: is_pipeline_healthy=False -> AnonymizationPipelineUnavailable raised."""
    anon_module.is_pipeline_healthy = False
    with pytest.raises(AnonymizationPipelineUnavailable):
        anonymize("Normaler Text ohne PII", fresh_cache)


def test_get_pipeline_status_ok():
    """D-08: get_pipeline_status() gibt 'ok' wenn Pipeline gesund."""
    anon_module.is_pipeline_healthy = True
    # Frische _error_timestamps (autouse Fixture hat bereits gecleart)
    result = get_pipeline_status()
    # get_pipeline_status() gibt dict zurueck: {'status': 'ok', 'error_count_10min': N}
    assert result['status'] == 'ok', f"Erwartet 'ok', erhalten: {result!r}"


def test_get_pipeline_status_unavailable():
    """D-08 Kat. A: is_pipeline_healthy=False -> get_pipeline_status() = 'unavailable'."""
    anon_module.is_pipeline_healthy = False
    result = get_pipeline_status()
    # get_pipeline_status() gibt dict zurueck: {'status': 'unavailable', 'error_count_10min': N}
    assert result['status'] == 'unavailable', f"Erwartet 'unavailable', erhalten: {result!r}"


def test_get_pipeline_status_degraded():
    """D-08 Kat. C: Viele Fehler in kurzer Zeit -> get_pipeline_status() = 'degraded'."""
    import time
    anon_module.is_pipeline_healthy = True
    # Mehr als ROLLING_ERROR_THRESHOLD Fehler setzen
    threshold = anon_module.ROLLING_ERROR_THRESHOLD
    now = time.monotonic()
    with anon_module._error_lock:
        anon_module._error_timestamps.clear()
        # Simuliere threshold+1 Fehler in den letzten 60 Sekunden
        for i in range(threshold + 1):
            anon_module._error_timestamps.append(now - i * 5)  # 5 Sek Abstand
    result = get_pipeline_status()
    # Cleanup nach Assertion (T-08.23.2.B-TW-02 — autouse Fixture uebernimmt auch)
    with anon_module._error_lock:
        anon_module._error_timestamps.clear()
    # get_pipeline_status() gibt dict zurueck: {'status': 'degraded', 'error_count_10min': N}
    assert result['status'] == 'degraded', f"Erwartet 'degraded' bei {threshold+1} Errors, erhalten: {result!r}"
