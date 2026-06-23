"""
FOLD A-2 / Req 11 (ANON-LIVE-ANSWER) — Plan 08.23.2.TAXO2-09.

Beweist den Live-roh-vs-Storage-anon-Vertrag + die NER-Ueber-Schaerfe-Balance:
  - Die dem Berater LIVE gezeigte Auto-Varianten-Antwort traegt ECHTE Namen.
  - Die separate Storage-Version (_storage_text) ist anonymisiert ([PERSON_*]).
  - anonymize_for_storage ist nie roh, nie verloren, Notweg geloggt (auch cache=None).
  - PRONOMEN_WHITELIST-Ergaenzung: 'Ihnen' bleibt, ein echter Name bleibt geschwaerzt.

CLAUDE.md Test-Qualitaets-Regel: NUR Runtime-Behavior (Function-Call-/State-Assertion,
Funktions-Rueckgabe, sio.emit-Spy). KEIN inspect.getsource(), kein open('file').read().

Hinweis: Die NER-abhaengigen Tests (Stopword + cache=None-Frisch-Saeuberung) brauchen die
geladene Anonymisierungs-Pipeline (spaCy/GLiNER) — Acceptance laeuft server-seitig
(CLAUDE.md HART: kein lokales pytest als Acceptance).
"""
import pytest

import services.claude_service as cs
import services.anonymization as anon_module
from services.anonymization import (
    AnrufAnonymisierer,
    anonymize,
    anonymize_for_storage,
)


# ── Fixtures / Fakes ──────────────────────────────────────────────────────────

@pytest.fixture
def filled_cache():
    """Per-SID-Cache mit registriertem Test-Namen (wie nach Transkript-Input)."""
    c = AnrufAnonymisierer()
    c.get_or_assign_token('Mueller', 'PERSON')  # -> '[PERSON_A]'
    return c


@pytest.fixture(autouse=True)
def reset_pipeline_health():
    original = anon_module.is_pipeline_healthy
    anon_module.is_pipeline_healthy = True
    with anon_module._error_lock:
        anon_module._error_timestamps.clear()
    yield
    anon_module.is_pipeline_healthy = original
    with anon_module._error_lock:
        anon_module._error_timestamps.clear()


class _FakeStream:
    """Minimaler Stand-in fuer anthropic messages.stream(...)-Kontextmanager."""
    def __init__(self, text):
        self._text = text

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    @property
    def text_stream(self):
        for tok in self._text.split(' '):
            yield tok + ' '

    def get_final_message(self):
        # Cost-Hook ist try/except-gekapselt; usage=None -> alle Guards greifen.
        return type('M', (), {'usage': None})()


class _FakeMessages:
    def __init__(self, text):
        self._text = text

    def stream(self, **kw):
        return _FakeStream(self._text)


class _FakeClient:
    def __init__(self, text):
        self.messages = _FakeMessages(text)


class _SioRecorder:
    def __init__(self):
        self.events = []

    def emit(self, event, data=None, **kw):
        self.events.append((event, data))

    def start_background_task(self, fn, *a, **kw):
        return None


def _run_auto_variante(monkeypatch, answer_text, cache):
    """Treibt streame_auto_variante mit gefaktem Claude-Stream + sio-Spy + Per-SID-Cache."""
    import extensions
    sio_rec = _SioRecorder()
    monkeypatch.setattr(extensions, 'socketio', sio_rec, raising=False)
    monkeypatch.setattr(cs, 'claude_client', _FakeClient(answer_text), raising=False)

    import services.live_session as ls
    monkeypatch.setattr(ls, 'get_anonymisierer', lambda _sid: cache, raising=False)

    result = cs.streame_auto_variante(
        neuer_text="Das ist mir zu teuer.",
        einwaende=[],
        kontext="",
        sid="sid-test-09",
        slot=1,
        trigger="analyse_loop",
    )
    return result, sio_rec


# ── Test 1: Live-Anzeige behaelt echte Namen ───────────────────────────────────

def test_auto_variante_display_keeps_real_names(monkeypatch, filled_cache):
    """Die ANZEIGE (pip_token_done) der Auto-Variante traegt den echten Namen, kein [PERSON_*]."""
    answer = "Herr Mueller, das verstehe ich gut."
    result, sio_rec = _run_auto_variante(monkeypatch, answer, filled_cache)

    done = [d for (e, d) in sio_rec.events if e == 'pip_token_done']
    assert done, "pip_token_done wurde nicht emittiert"
    shown = done[-1]['result']['gegenargument_1']
    assert 'Mueller' in shown, f"Live-Anzeige muss echten Namen tragen: {shown!r}"
    assert '[PERSON_' not in shown, f"Live-Anzeige darf NICHT anonymisiert sein: {shown!r}"
    # Das Anzeige-Payload darf die Storage-Version nicht mit ausliefern
    assert '_storage_text' not in done[-1]['result'], "Anzeige-Payload leakt _storage_text"


# ── Test 2: Storage-Version ist anonymisiert ────────────────────────────────────

def test_auto_variante_storage_is_anonymized(monkeypatch, filled_cache):
    """Die Storage-Version (_storage_text, Vertrag fuer Plan 08) traegt [PERSON_*]."""
    answer = "Herr Mueller, das verstehe ich gut."
    result, _ = _run_auto_variante(monkeypatch, answer, filled_cache)

    storage = result.get('_storage_text')
    assert storage is not None, "Plan-08-Vertrag _storage_text fehlt"
    assert '[PERSON_A]' in storage, f"Storage muss anonymisiert sein: {storage!r}"
    assert 'Mueller' not in storage, f"Storage darf keinen rohen Namen tragen: {storage!r}"


# ── Test 3: Storage-Fallback — nie roh, nie verloren, geloggt (cache=None) ──────

def test_storage_fallback_no_raw_no_loss(monkeypatch, capsys):
    """anonymize_for_storage mit cache=None: keine rohen Namen, NICHT leer-verworfen, Log emittiert."""
    import services.live_session as ls
    monkeypatch.setattr(ls, 'get_anonymisierer', lambda _sid: None, raising=False)

    out = anonymize_for_storage("Herr Mueller hat angerufen", sid="sid-ghost")

    assert out, "Storage-Fallback darf die Zeile nicht leer-verwerfen"
    assert 'Mueller' not in out, f"Frische Saeuberung muss den Namen entfernen: {out!r}"
    logged = capsys.readouterr().out
    assert 'storage-fallback' in logged, "Notweg muss geloggt werden (nie still)"


# ── Test 4: NER-Stopword behaelt Funktionswoerter ('Ihnen') ─────────────────────

def test_ner_stopword_keeps_function_words(filled_cache):
    """'Wie kann ich Ihnen helfen?' -> 'Ihnen' bleibt (kein [PERSON_*])."""
    out, _tier = anonymize("Wie kann ich Ihnen helfen?", filled_cache)
    assert 'Ihnen' in out, f"Funktionswort 'Ihnen' wurde geschwaerzt: {out!r}"
    assert '[PERSON_' not in out, f"Ueber-Schaerfe: kein PERSON-Token erwartet: {out!r}"


# ── Test 5: Balance — echter Name geschwaerzt, Funktionswort bleibt ─────────────

def test_ner_stopword_still_redacts_real_name(filled_cache):
    """'Herr Mueller, wie kann ich Ihnen helfen?' -> 'Mueller' geschwaerzt UND 'Ihnen' bleibt."""
    out, _tier = anonymize("Herr Mueller, wie kann ich Ihnen helfen?", filled_cache)
    assert 'Mueller' not in out, f"Echter Name muss geschwaerzt werden (DSGVO): {out!r}"
    assert '[PERSON_' in out, f"PERSON-Token fuer echten Namen erwartet: {out!r}"
    assert 'Ihnen' in out, f"Funktionswort 'Ihnen' darf nicht geschwaerzt werden: {out!r}"
