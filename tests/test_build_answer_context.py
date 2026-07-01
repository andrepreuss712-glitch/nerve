"""
tests/test_build_answer_context.py
────────────────────────────────────────────────────────────────────
Pure-Logic-Tests fuer die TAXO3-P1-01-Antwort-Versorgung (Weg 3):
  - services.answer_paradigm.get_answer_config (NERVE-Standard)
  - services.prompt_pipeline.load_answer_config (Andock-Stelle)
  - services.prompt_pipeline.build_answer_context (EINE Quelle, Block-Liste)
  - services.prompt_pipeline._profile_blocks (Block-Split, Anti-Cache-Poison)

Runtime-Verhalten (kein Source-Presence): Funktions-Aufruf + Assertion auf
Rueckgabe. Kein DB, kein Live-Pfad (monkeypatch auf In-Memory).
"""
from __future__ import annotations

import inspect
import threading

import pytest


# ── answer_paradigm: NERVE-Standard-Struktur + keine Beispielsaetze ──────────

def test_answer_config_structure_and_no_technique_vocab():
    from services import answer_paradigm as ap
    cfg = ap.get_answer_config()
    assert isinstance(cfg['paradigm'], list) and 6 <= len(cfg['paradigm']) <= 10
    assert {'gatekeeper', 'interessent', 'meeting'} <= set(cfg['roles'].keys())
    assert isinstance(cfg['grounding'], str) and len(cfg['grounding']) > 20
    assert isinstance(cfg['intent_hints'], dict) and cfg['intent_hints']
    # KEINE Technik-Vokabel im vorzulesenden Text (SPEC Req 2 / D-02)
    full = ' '.join(cfg['paradigm']) + ' ' + ' '.join(cfg['roles'].values()) + ' ' + cfg['grounding']
    for tech in ('Reframe', 'ANKER', 'Einwand überwinden', 'Beispiel:'):
        assert tech not in full, f'Technik-Vokabel/Beispiel im Standard-Text: {tech}'
    # 3 harte Tabus (D-02) im Paradigma erkennbar
    paradigm_text = ' '.join(cfg['paradigm'])
    assert 'Dringlichkeits' in paradigm_text or 'Druck' in paradigm_text      # kein Druck-Sprech
    assert 'Produkt-Versprechen' in paradigm_text or 'erfinden' in paradigm_text  # kein falsches Versprechen
    assert 'kurz' in paradigm_text.lower()                                    # keine Mini-Romane


# ── build_answer_context: Block-Form (stabil vor volatil) ────────────────────

def test_block_form_stable_before_volatile(monkeypatch):
    import services.prompt_pipeline as pp
    monkeypatch.setattr(pp, '_profile_blocks', lambda *a, **k: ('STABIL_PROFIL', 'VOLATIL_PROFIL'))
    blocks = pp.build_answer_context(
        user_id=1, sid='s', primary_intent='echter_einwand',
        mode='cold_call', confidence=0.9, role='interessent',
    )
    assert isinstance(blocks, list) and len(blocks) >= 2
    assert blocks[0]['_layer'] == 'stable'
    assert blocks[1]['_layer'] == 'volatile'
    assert 'STABIL_PROFIL' in blocks[0]['text']
    assert 'VOLATIL_PROFIL' in blocks[1]['text']


# ── fail-open: kein raise ohne Profil/Config, Paradigma + Grounding da ──────

def test_fail_open_no_profile(monkeypatch):
    import services.prompt_pipeline as pp
    monkeypatch.setattr(pp, '_profile_blocks', lambda *a, **k: ('', ''))
    blocks = pp.build_answer_context(
        user_id=0, sid=None, primary_intent='UNKNOWN_XYZ',
        mode='cold_call', confidence=None,
    )
    text = '\n'.join(b['text'] for b in blocks)
    assert 'Ziel ist verstehen und echt helfen' in text     # Paradigma vorhanden
    assert 'gegebenen Wissen' in text                        # Grounding-Regel vorhanden


# ── EIN Intent: Signatur nimmt genau einen; unbekannter Key -> Default-Hinweis

def test_single_intent_signature():
    import services.prompt_pipeline as pp
    params = inspect.signature(pp.build_answer_context).parameters
    assert 'primary_intent' in params
    assert 'primary_intents' not in params      # kein list/top-2
    # keyword-only Signatur (kein positionaler Intent-Salat)
    assert params['primary_intent'].kind == inspect.Parameter.KEYWORD_ONLY


def test_unknown_intent_key_default_hint(monkeypatch):
    import services.prompt_pipeline as pp
    monkeypatch.setattr(pp, '_profile_blocks', lambda *a, **k: ('', ''))
    blocks = pp.build_answer_context(user_id=1, sid='s', primary_intent='does_not_exist')
    assert 'unklarer Punkt' in blocks[1]['text']    # _DEFAULT_INTENT_HINT register, kein KeyError


# ── Rolle als Parameter (kein if-Zweig) ─────────────────────────────────────

def test_role_parameter(monkeypatch):
    import services.prompt_pipeline as pp
    monkeypatch.setattr(pp, '_profile_blocks', lambda *a, **k: ('', ''))
    gk = pp.build_answer_context(user_id=1, sid='s', primary_intent='gatekeeper', role='gatekeeper')
    assert 'Durchstellen' in gk[0]['text'] or 'Respekt' in gk[0]['text']
    unknown = pp.build_answer_context(user_id=1, sid='s', primary_intent='gatekeeper', role='nope')
    assert 'Diagnostizieren vor Antworten' in unknown[0]['text']     # interessent-Fallback


# ── Modus/Konfidenz als Parameter (Register-Text, kein Prompt-Zweig) ────────

def test_confidence_register_low_signals_caution(monkeypatch):
    import services.prompt_pipeline as pp
    monkeypatch.setattr(pp, '_profile_blocks', lambda *a, **k: ('', ''))
    low = pp.build_answer_context(
        user_id=1, sid='s', primary_intent='echter_einwand', mode='cold_call', confidence=0.2,
    )
    assert 'vorsichtiger' in low[1]['text']
    meeting = pp.build_answer_context(
        user_id=1, sid='s', primary_intent='echter_einwand', mode='meeting', confidence=0.9,
    )
    assert 'Meeting' in meeting[1]['text']


# ── KEIN Few-Shot/Beispielsatz im Output ────────────────────────────────────

def test_no_fewshot_in_output(monkeypatch):
    import services.prompt_pipeline as pp
    monkeypatch.setattr(pp, '_profile_blocks', lambda *a, **k: ('', ''))
    blocks = pp.build_answer_context(user_id=1, sid='s', primary_intent='echter_einwand')
    text = '\n'.join(b['text'] for b in blocks)
    assert 'Beispiel:' not in text
    assert 'z.B.:' not in text
    assert 'Reframe' not in text


# ── ANTI-CACHE-POISON + Split-Anker: echter _profile_blocks-Split ───────────

def test_anti_cache_poison_real_split(monkeypatch):
    """Gemini HIGH: die per-SID Anrede (Sek. 7) + Briefing/Lead (Sek. 8/9) duerfen
    NICHT in den Stabil-Block (Cache-Prefix, SPEC Req 9). Split am Text-Anker
    '## PreCall-Briefing'. Kein Monkeypatch von _profile_blocks — echter Split."""
    import services.live_session as ls
    import services.prompt_pipeline as pp

    sid = 'test-sid-poison'
    pdata = {'ki': {'ansprache': 'Sie', 'ton': 'freundlich'}, 'basis': {'unternehmen': 'ACME'}}
    # In-Memory statt DB: Cache mit opener_content='' verhindert den DB-Fallback.
    _state = {
        sid: {
            '_profile_cache': {'opener_content': '', 'faqs': [], 'profile_branche': ''},
            'session_anrede': 'Du',        # per-SID Anrede != Profil-Default 'Sie'
            'vorwissen_level': 'hoch',
        }
    }
    monkeypatch.setattr(ls, 'get_profile_for_sid', lambda s: ('', pdata), raising=False)
    monkeypatch.setattr(ls, 'get_briefing_for_sid', lambda s: 'Heute: Erstkontakt mit ACME', raising=False)
    monkeypatch.setattr(ls, '_session_state', _state, raising=False)
    monkeypatch.setattr(ls, '_session_state_lock', threading.Lock(), raising=False)

    stable, volatile = pp._profile_blocks(user_id=1, mode='cold_call', sid=sid)

    # Stabil-Block: Sektion 7 vorhanden, aber OHNE die per-SID Anrede-Zeile
    assert '## KI-Verhalten' in stable
    assert 'WICHTIG: Nutze konsequent' not in stable      # Anrede-Zeile (Sek.7) entfernt
    assert '## PreCall-Briefing' not in stable            # volatiler Anker nicht im Cache-Prefix
    assert 'Heute: Erstkontakt mit ACME' not in stable    # Briefing nicht stabil

    # Volatil-Block: beginnt am Text-Anker, traegt Anrede + Briefing + Lead
    assert volatile.split('\n')[0] == '## PreCall-Briefing'
    assert 'Heute: Erstkontakt mit ACME' in volatile
    assert '## Lead-Kontext' in volatile
    assert 'Du' in volatile                               # per-SID Anrede nur volatil


# ── load_answer_config: Andock-Stelle liefert den NERVE-Standard, fail-open ──

def test_load_answer_config_returns_standard():
    import services.prompt_pipeline as pp
    cfg = pp.load_answer_config(user_id=1, sid='s')
    assert 'paradigm' in cfg and cfg['paradigm']
    assert 'grounding' in cfg and cfg['grounding']
    assert 'default_intent_hint' in cfg


def test_load_answer_config_fail_open(monkeypatch):
    """Stoerung an der Andock-Stelle -> Minimal-Default, nie raise."""
    import services.prompt_pipeline as pp

    def _boom():
        raise RuntimeError('config source down')

    # get_answer_config im answer_paradigm-Modul sprengen -> load_answer_config muss fangen
    import services.answer_paradigm as ap
    monkeypatch.setattr(ap, 'get_answer_config', _boom, raising=False)
    cfg = pp.load_answer_config(user_id=1, sid='s')
    assert 'paradigm' in cfg and 'grounding' in cfg     # Minimal-Default, kein raise
