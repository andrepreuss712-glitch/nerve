"""
services/prompt_pipeline.py
────────────────────────────────────────────────────────────────────
Phase 08 Shared Prompt-Pipeline-Utilities (wiederverwendbar fuer 08.5).

Exports:
  - resolve_prompt_version(module, user_id)   → A/B-Routing mit ENV-Override
  - build_profile_context(user_id, mode, sid) → 9-Sektionen Voll-Profil-Kontext (D-01)
  - invalidate_resolver_cache()               → Cache-Clear nach prompt_versions Aenderung

Side-effect-free beim Import: keine I/O, keine DB-Zugriffe.
Alle DB-Imports sind LAZY innerhalb der Funktionen.
Live-loop-Garantie: Keine der Funktionen wirft Exceptions.
"""
from __future__ import annotations

import os
from typing import Any


# ── Modul-Level Caches ──────────────────────────────────────────────────────
# Eigene Caches, unabhaengig von anderen Modulen. Cache-Key (module, user_id)
# verhindert Cross-User-Variant-Leakage (W-7).
_RESOLVER_CACHE: dict = {}     # {(module, user_id): version_string}
_VARIANTS_CACHE: dict = {}     # {module: [version_string, ...]}


# ── A/B-Router: resolve_prompt_version ─────────────────────────────────────

def resolve_prompt_version(module: str, user_id: int) -> str:
    """Resolve prompt-version for (module, user_id).

    Priority:
      1. ENV-Override: ``PROMPT_{MODULE}_VERSION_OVERRIDE`` (D-24 Safety-Net)
      2. Deterministic routing: variants[user_id % len(variants)] (D-23)
      3. Fallback: ``'unknown'`` when no variants in DB.

    Cache per (module, user_id) after first resolve. Invalidate via
    :func:`invalidate_resolver_cache` after prompt_versions changes.

    MUST NOT raise — fail-open to ``'unknown'`` on any DB error.
    """
    # STEP 1: ENV-Override (D-24) — First Check, beats everything.
    env_key = f'PROMPT_{module.upper()}_VERSION_OVERRIDE'
    env_override = os.environ.get(env_key)
    if env_override:
        return env_override

    # STEP 2: Per-User cache hit.
    cache_key = (module, user_id)
    if cache_key in _RESOLVER_CACHE:
        return _RESOLVER_CACHE[cache_key]

    # STEP 3: Load active variants for this module (lazy, cached).
    if module not in _VARIANTS_CACHE:
        variants = _load_active_variants(module)
        _VARIANTS_CACHE[module] = variants

    variants = _VARIANTS_CACHE[module]
    if not variants:
        # Empty list should never happen (loader always returns at least ['unknown']),
        # but defend-in-depth:
        _RESOLVER_CACHE[cache_key] = 'unknown'
        return 'unknown'

    # STEP 4: Deterministic routing — mod-based, scales to N variants.
    resolved = variants[user_id % len(variants)]
    _RESOLVER_CACHE[cache_key] = resolved
    return resolved


def _load_active_variants(module: str) -> list[str]:
    """Load sorted list of active version-strings for ``module``.

    On DB error: return ``['unknown']`` so resolver keeps working.
    """
    try:
        from database.db import SessionLocal
        from database.models import PromptVersion
        db = SessionLocal()
        try:
            rows = (db.query(PromptVersion)
                    .filter_by(module=module, is_active=True)
                    .order_by(PromptVersion.version)
                    .all())
            versions = [r.version for r in rows]
            if not versions:
                print(f"[Pipeline] variants empty module={module} fallback=unknown")
                return ['unknown']
            print(f"[Pipeline] variants loaded module={module} count={len(versions)}")
            return versions
        finally:
            db.close()
    except Exception as e:
        print(f"[Pipeline] variants load failed module={module}: {e}")
        return ['unknown']


def invalidate_resolver_cache() -> None:
    """Clear both caches. Call after prompt_versions table changes.

    NOT called from live-loop — admin/test utility only.
    """
    _RESOLVER_CACHE.clear()
    _VARIANTS_CACHE.clear()
    print("[Pipeline] resolver cache invalidated")


# ── Profil-Kontext-Assembly: build_profile_context ─────────────────────────

def build_profile_context(user_id: int, mode: str = 'cold_call', sid: str = None,
                          profile_id: int = None, return_blocks: bool = False):
    """Build a 9-section Markdown profile-context string for system-prompts (D-01).

    9-section canonical order (LOCKED — cache stability):
      1. ## Branche
      2. ## Basis        (incl. Opener from _profile_cache — no DB in hot path)
      3. ## Zielkunde
      4. ## Schmerzen
      5. ## Einwände     (einwaende_detail as Markdown list)
      6. ## Phasen       (numbered list)
      7. ## KI-Verhalten
      8. ## PreCall-Briefing  (volatile — per-SID)
      9. ## Lead-Kontext      (volatile — per-SID)

    HOT PATH (sid + warm _profile_cache):  0 DB queries, < 5ms (HIGH-3 fix).
    FALLBACK (sid=None or cache absent):   lightweight DB query for opener/FAQ.

    profile_id (optional): when provided, loads this specific profile instead of
      user.active_profile_id. Used by the EWB-Preview API (D-08) to render any
      profile in the org, not just the active one.

    Empty sections: NEVER skipped — rendered with:
      - Fields not filled:  (noch nicht ausgefüllt)
      - PreCall not done:   (noch nicht erstellt)
      - Lead-Kontext:       Anrede: Sie / Vorwissen-Level: nicht angegeben

    MUST NOT raise — fail-open to empty string on any import error.
    BUG-B fix: FAQ reads from _profile_cache, NOT from ls.state['active_profile_id'].
    """
    try:
        import services.live_session as ls
    except Exception as e:
        print(f"[Pipeline] live_session import failed: {e}")
        return ('', '') if return_blocks else ''

    lines: list[str] = []

    # ── Load profile data ────────────────────────────────────────────────────
    # Hot path: per-SID in-memory profile (no DB)
    _, pdata = ls.get_profile_for_sid(sid) if sid else ('', {})
    if not pdata and user_id:
        # Fallback: HTTP paths, preview endpoint, QA without session
        # If profile_id is provided, load that specific profile (EWB-Preview D-08).
        # Otherwise fall back to user.active_profile_id.
        try:
            from database.db import SessionLocal as _SL_fb
            from database.models import User as _User_fb, Profile as _Profile_fb
            _db_fb = _SL_fb()
            try:
                if profile_id:
                    _p_fb = _db_fb.query(_Profile_fb).filter_by(id=profile_id).first()
                else:
                    _u_fb = _db_fb.query(_User_fb).filter_by(id=user_id).first()
                    _pid_fb = getattr(_u_fb, 'active_profile_id', None) if _u_fb else None
                    _p_fb = _db_fb.query(_Profile_fb).filter_by(id=_pid_fb).first() if _pid_fb else None
                if _p_fb:
                    import json as _json_fb
                    _raw = getattr(_p_fb, 'daten', None) or '{}'
                    pdata = _json_fb.loads(_raw) if isinstance(_raw, str) else (_raw or {})
            finally:
                _db_fb.close()
        except Exception as _fb_e:
            print(f"[Pipeline] pdata fallback failed: {_fb_e}")
            pdata = {}

    # ── Load _profile_cache (opener, faqs) ──────────────────────────────────
    # HOT PATH: read from _session_state[sid]['_profile_cache'] — NO DB queries
    # FALLBACK (sid=None or cache absent): lightweight DB query
    _profile_cache: dict = {}
    if sid:
        with ls._session_state_lock:
            _profile_cache = ls._session_state.get(sid, {}).get('_profile_cache', {})

    _opener_content = _profile_cache.get('opener_content')   # None if not loaded
    _faqs = _profile_cache.get('faqs', [])
    # Issue 1 fix: Profile.branche moved to DB column in Phase 08.19.1 — read from cache
    _profile_branche = _profile_cache.get('profile_branche') or ''

    # If cache absent (sid=None or session pre-init), fall back to DB for opener + FAQ
    # When profile_id is given, use it directly; otherwise resolve via user.active_profile_id.
    # Note: ProfileOpener uses 'inhalt' (not 'content'); no is_active column in this schema.
    if _opener_content is None and user_id:
        try:
            from database.db import SessionLocal as _SL_op
            from database.models import User as _User_op, ProfileOpener as _PO_op, ProfileFaq as _FAQ_op
            _db_op = _SL_op()
            try:
                if profile_id:
                    _pid_op = profile_id
                else:
                    _u_op = _db_op.query(_User_op).filter_by(id=user_id).first()
                    _pid_op = getattr(_u_op, 'active_profile_id', None) if _u_op else None
                if _pid_op:
                    # ORDER BY id LIMIT 1 — deterministic, cache-stable (MEDIUM fix)
                    _op_row = _db_op.query(_PO_op).filter_by(
                        profile_id=_pid_op
                    ).order_by(_PO_op.id).limit(1).first()
                    _opener_content = getattr(_op_row, 'inhalt', None) if _op_row else None
                    try:
                        _faq_rows = _db_op.query(_FAQ_op).filter_by(
                            profile_id=_pid_op
                        ).limit(20).all()
                        for f in _faq_rows:
                            _q = getattr(f, 'frage_muster', '') or ''
                            _a = getattr(f, 'antwort', '') or ''
                            if _q and _a:
                                _faqs.append({'q': _q, 'a': _a})
                    except Exception:
                        pass
                    # Issue 1 fallback: load Profile.branche if not already in cache
                    if not _profile_branche:
                        try:
                            from database.models import Profile as _Prof_op
                            _p_br = _db_op.query(_Prof_op).filter_by(id=_pid_op).first()
                            _profile_branche = getattr(_p_br, 'branche', None) or ''
                        except Exception:
                            pass
            finally:
                _db_op.close()
        except Exception as _op_e:
            print(f"[Pipeline] Opener/FAQ fallback failed: {_op_e}")

    # ── Extract profile sub-dicts ────────────────────────────────────────────
    basis = (pdata.get('basis') or {}) if isinstance(pdata, dict) else {}
    ki = (pdata.get('ki') or {}) if isinstance(pdata, dict) else {}
    zielkunde = (pdata.get('zielkunde') or {}) if isinstance(pdata, dict) else {}
    schmerzen = (pdata.get('schmerzen') or {}) if isinstance(pdata, dict) else {}
    phasen_raw = (pdata.get('phasen') or []) if isinstance(pdata, dict) else []
    einwaende_detail = (pdata.get('einwaende_detail') or []) if isinstance(pdata, dict) else []
    anrede = _resolve_anrede(ls, ki, sid)   # compute once — used in Sektionen 7 + 9

    # ── Sektion 1: ## Branche ────────────────────────────────────────────────
    try:
        lines.append('## Branche')
        # Issue 1: prefer DB-column (_profile_branche) over daten JSON (08.19.1 migration)
        branche = _profile_branche or basis.get('branche') or ''
        branche_kontext = basis.get('branche_kontext') or ''
        if branche:
            lines.append(branche)
        else:
            lines.append('(noch nicht ausgefüllt)')
        if branche_kontext:
            lines.append(branche_kontext)
    except Exception as _e:
        print(f"[Pipeline] Branche-Block skip: {_e}")

    # ── Sektion 2: ## Basis ──────────────────────────────────────────────────
    try:
        lines.append('## Basis')
        for _fld, _label in [
            ('unternehmen',         'Unternehmen'),
            ('produktbeschreibung', 'Produkt'),
            ('preismodell',         'Preismodell'),
            ('konsequenz',          'Konsequenz'),
        ]:
            _val = basis.get(_fld)
            lines.append(f'{_label}: {_val}' if _val else f'{_label}: (noch nicht ausgefüllt)')
        _usps = basis.get('usps') or []
        if _usps:
            lines.append('USPs:')
            for _u in (_usps if isinstance(_usps, list) else [_usps]):
                lines.append(f'- {_u}')
        else:
            lines.append('USPs: (noch nicht ausgefüllt)')
        for _fld, _label in [
            ('eigene_formulierungen', 'Eigene Formulierungen'),
            ('beweise',               'Beweise / Referenzen'),
        ]:
            _items = basis.get(_fld) or []
            if _items:
                lines.append(f'{_label}:')
                for _item in (_items if isinstance(_items, list) else [_items]):
                    lines.append(f'- {_item}')
        # Opener from _profile_cache (canonical source — D-01 / HIGH-3 fix: no DB here)
        if _opener_content:
            lines.append(f'Opener: {_opener_content}')
    except Exception as _e:
        print(f"[Pipeline] Basis-Block skip: {_e}")

    # ── Sektion 3: ## Zielkunde ──────────────────────────────────────────────
    try:
        lines.append('## Zielkunde')
        _any = False
        for _fld, _label in [
            ('unternehmensgroesse', 'Unternehmensgröße'),
            ('buying_committee',    'Buying Committee'),
            ('statusquo',           'Status quo'),
            ('zeithorizont',        'Zeithorizont'),
        ]:
            _val = zielkunde.get(_fld)
            if _val:
                lines.append(f'{_label}: {_val}')
                _any = True
        zielgruppe = (pdata.get('zielgruppe') or {}) if isinstance(pdata, dict) else {}
        for _fld, _label in [
            ('vorwissen',              'Vorwissen (Profil-Default)'),
            ('entscheidungsverhalten', 'Entscheidungsverhalten'),
        ]:
            _val = zielgruppe.get(_fld)
            if _val:
                lines.append(f'{_label}: {_val}')
                _any = True
        if not _any:
            lines.append('(noch nicht ausgefüllt)')
    except Exception as _e:
        print(f"[Pipeline] Zielkunde-Block skip: {_e}")

    # ── Sektion 4: ## Schmerzen ──────────────────────────────────────────────
    try:
        lines.append('## Schmerzen')
        _schmerzen_items = []
        if isinstance(schmerzen, dict):
            for _k, _v in sorted(schmerzen.items()):   # sorted() for determinism
                if not _v:
                    continue
                if isinstance(_v, list):
                    for _s in _v:
                        if not _s:
                            continue
                        if isinstance(_s, dict):
                            _sit  = _s.get('situation') or ''
                            _kern = _s.get('kern') or ''
                            _vst  = _s.get('verstaerken') or _s.get('verstärken') or ''
                            _parts = []
                            if _sit:  _parts.append(f'**Situation:** {_sit}')
                            if _kern: _parts.append(f'**Kern:** {_kern}')
                            if _vst:  _parts.append(f'**Verstärken:** {_vst}')
                            if _parts:
                                _schmerzen_items.append('- ' + '\n  '.join(_parts))
                        else:
                            _schmerzen_items.append(f'- {_s}')
                else:
                    _schmerzen_items.append(f'- {_v}')
        elif isinstance(schmerzen, list):
            for _s in schmerzen:
                if not _s:
                    continue
                if isinstance(_s, dict):
                    _sit  = _s.get('situation') or ''
                    _kern = _s.get('kern') or ''
                    _vst  = _s.get('verstaerken') or _s.get('verstärken') or ''
                    _parts = []
                    if _sit:  _parts.append(f'**Situation:** {_sit}')
                    if _kern: _parts.append(f'**Kern:** {_kern}')
                    if _vst:  _parts.append(f'**Verstärken:** {_vst}')
                    if _parts:
                        _schmerzen_items.append('- ' + '\n  '.join(_parts))
                else:
                    _schmerzen_items.append(f'- {_s}')
        if _schmerzen_items:
            lines.extend(_schmerzen_items)
        else:
            lines.append('(noch nicht ausgefüllt)')
    except Exception as _e:
        print(f"[Pipeline] Schmerzen-Block skip: {_e}")

    # ── Sektion 5: ## Einwände ───────────────────────────────────────────────
    try:
        lines.append('## Einwände')
        if einwaende_detail:
            for _ew in einwaende_detail:
                if isinstance(_ew, dict):
                    lines.append(
                        f"- {_ew.get('einwand') or ''} "
                        f"({_ew.get('einwand_typ') or 'unbekannt'}) "
                        f"| {_ew.get('gegenargument') or ''}"
                    )
        else:
            lines.append('(noch nicht ausgefüllt)')
    except Exception as _e:
        print(f"[Pipeline] Einwaende-Block skip: {_e}")

    # ── Sektion 6: ## Phasen ────────────────────────────────────────────────
    try:
        lines.append('## Phasen')
        if phasen_raw:
            for _i, _ph in enumerate(phasen_raw, 1):
                if isinstance(_ph, dict):
                    _name = _ph.get('name') or _ph.get('phase') or str(_ph)
                else:
                    _name = str(_ph)
                lines.append(f'{_i}. {_name}')
        else:
            lines.append('(noch nicht ausgefüllt)')
    except Exception as _e:
        print(f"[Pipeline] Phasen-Block skip: {_e}")

    # ── Sektion 7: ## KI-Verhalten ──────────────────────────────────────────
    try:
        lines.append('## KI-Verhalten')
        lines.append(f'Anrede: {anrede}. WICHTIG: Nutze konsequent {anrede}-Form. '
                     f'Wechsle NIEMALS innerhalb einer Antwort zwischen Du und Sie.')
        for _fld, _label in [('ton', 'Ton'), ('zusatz', 'Zusatz')]:
            _val = ki.get(_fld)
            if _val:
                lines.append(f'{_label}: {_val}')
        if not any(ki.get(f) for f in ('ton', 'zusatz')):
            lines.append('(noch nicht ausgefüllt)')
    except Exception as _e:
        print(f"[Pipeline] KI-Verhalten-Block skip: {_e}")

    # ── FAQ Block (BUG-B fix: reads from _profile_cache, NOT ls.state) ──────
    try:
        if _faqs:
            lines.append('## FAQ')
            for _f in _faqs:
                lines.append(f"F: {_f['q']}")
                lines.append(f"A: {_f['a']}")
    except Exception as _faq_e:
        print(f"[Pipeline] FAQ-Block skip: {_faq_e}")

    # ── Tabu-Instruction Block (Phase 08.5 — nur wenn pdata vorhanden) ───────
    try:
        if pdata:
            from services.qa_pipeline import build_tabu_instruction
            tabu_block = build_tabu_instruction(pdata)
            if tabu_block:
                lines.append(tabu_block)
    except Exception as _e:
        print(f"[Pipeline] build_tabu_instruction skipped: {_e}")

    # ── Sektion 8: ## PreCall-Briefing (volatile — per-SID) ─────────────────
    try:
        lines.append('## PreCall-Briefing')
        _briefing = ls.get_briefing_for_sid(sid) if sid else None
        lines.append(_briefing if _briefing else '(noch nicht erstellt)')
    except Exception as _e:
        print(f"[Pipeline] PreCall-Briefing-Block skip: {_e}")
        lines.append('(noch nicht erstellt)')

    # ── Sektion 9: ## Lead-Kontext (volatile — per-SID) ─────────────────────
    try:
        lines.append('## Lead-Kontext')
        _vorwissen = None
        _sid_anrede = None
        if sid:
            with ls._session_state_lock:
                _sid_state = ls._session_state.get(sid, {})
            _vorwissen = _sid_state.get('vorwissen_level')
            _sid_anrede = _sid_state.get('session_anrede')
        lines.append(f'Anrede: {_sid_anrede or anrede}')
        _vw_display = {
            'niedrig': 'niedrig',
            'mittel': 'mittel',
            'hoch': 'hoch',
        }.get(_vorwissen, 'nicht angegeben') if _vorwissen else 'nicht angegeben'
        lines.append(f'Vorwissen-Level: {_vw_display}')
    except Exception as _e:
        print(f"[Pipeline] Lead-Kontext-Block skip: {_e}")

    if return_blocks:
        # ── Block-Split (TAXO3 P1-01, Gemini HIGH-Fix) ──────────────────────
        # Trenn-Grenze = Text-Anker '## PreCall-Briefing' (erste volatile Sektion),
        # NICHT eine hartcodierte Sektions-Nummer. Alles davor = stabil, ab dort =
        # volatil. Fehlt der Anker (z.B. sid=None ohne volatile Sektionen) →
        # volatil = '' , alles stabil (fail-open, kein raise).
        try:
            _split_idx = lines.index('## PreCall-Briefing')
        except ValueError:
            _split_idx = len(lines)
        _stable_lines = lines[:_split_idx]
        _volatile_lines = lines[_split_idx:]
        # ANTI-CACHE-POISON (Gemini HIGH): die per-SID Anrede-Zeile aus Sektion 7
        # (:402, 'Anrede: ... WICHTIG: Nutze konsequent ...') darf NICHT in den
        # Stabil-Block (Cache-Prefix) — Anrede bleibt ausschliesslich volatil in
        # Sektion 9. Der Alt-String-Pfad (return_blocks=False) behaelt sie.
        _stable_lines = [
            _l for _l in _stable_lines
            if not (_l.startswith('Anrede: ') and 'WICHTIG: Nutze konsequent' in _l)
        ]
        return '\n'.join(_stable_lines), '\n'.join(_volatile_lines)

    return '\n'.join(lines)


def _resolve_anrede(ls: Any, ki: dict, sid: str = None) -> str:
    """Anrede priority: session_anrede (per-sid top-level) > ki.ansprache > 'Sie'.

    PERSID Plan 03 B2: liest AUSSCHLIESSLICH per-SID (_session_state[sid]['session_anrede'],
    top-level, lazy). Der globale ls.state-Fallback ist entfernt (B2-Split-Brain-Fix).
    Faellt auf ki.ansprache / 'Sie' zurueck wenn sid=None oder kein Eintrag.
    """
    # Per-SID session state (einzige kanonische Quelle, top-level)
    if sid:
        try:
            lock = getattr(ls, '_session_state_lock', None)
            ss = getattr(ls, '_session_state', None)
            if isinstance(ss, dict) and lock is not None:
                with lock:
                    _sid_anrede = ss.get(sid, {}).get('session_anrede')
                if _sid_anrede:
                    return _sid_anrede
        except Exception:
            pass
    return ki.get('ansprache') or 'Sie'


# ── TAXO3 P1-01: Antwort-Versorgung (Weg 3, Andock-Stelle + EINE Quelle) ─────
# Foundation-Code-Register: 'TAXO3 answer-config Andock-Stelle (Weg 3)'.
# load_answer_config ist der EINE dokumentierte Naht-Punkt: heute Datei-Default
# (answer_paradigm.py), spaeter klinkt hier die Coach-Tuer-DB ein — build_answer_context
# wird dafuer NICHT umgebaut.

def load_answer_config(user_id: int, sid: str | None = None) -> dict:
    """Andock-Stelle fuer die Antwort-Konfiguration (Weg 3, Foundation).

    HEUTE: der NERVE-Standard aus answer_paradigm.get_answer_config() (reiner
    Speicher-Zugriff, 0 DB — Latenz-Garantie Punkt 25).
    SPAETER (Coach-Tuer, eigene Scheibe): hier laedt die method_packs/pack_assignments-DB
    (pack_assignment -> pack -> stiller NERVE-Default); dann per-User cachen wie
    _profile_cache. build_answer_context bleibt unveraendert.
    Fail-open: jede Stoerung -> Minimal-NERVE-Standard (nie raise, Live-Loop-Garantie).
    """
    try:
        from services.answer_paradigm import get_answer_config
        return get_answer_config()
    except Exception as _e:
        print(f"[AnswerConfig] load fail-open -> minimal default: {type(_e).__name__}")
        return {
            'paradigm': ['Verstehen und helfen, nie druecken.'],
            'roles': {},
            'grounding': 'Nur aus gegebenem Wissen; fehlt der Fakt -> sagen + Follow-up.',
            'intent_hints': {},
            'default_intent_hint': {'register': '', 'hebel': ''},
        }


def _profile_blocks(user_id: int, mode: str = 'cold_call', sid: str | None = None,
                    profile_id: int | None = None) -> tuple[str, str]:
    """Schmaler Wrapper: (stabil_text = Sek. 1–7, volatil_text = Sek. 8–9) getrennt.

    Nutzt build_profile_context(..., return_blocks=True) — KEIN Neubau. Split am
    Text-Anker '## PreCall-Briefing'; die per-SID Anrede-Zeile (Sek. 7) ist aus dem
    Stabil-Block entfernt (Anti-Cache-Poison). Fail-open: jede Stoerung -> ('', '').
    """
    try:
        result = build_profile_context(user_id, mode, sid, profile_id, return_blocks=True)
        if isinstance(result, tuple) and len(result) == 2:
            return result
        # Defensive: sollte build_profile_context je einen String liefern
        return (str(result), '')
    except Exception as _e:
        print(f"[Pipeline] _profile_blocks fail-open: {type(_e).__name__}")
        return ('', '')


def _confidence_register(mode: str, confidence: float | None,
                         is_auto_triggered: bool) -> str:
    """EIN kurzer Register-Text aus Modus/Konfidenz — rein aus Parametern.

    KEIN 'if mode==' der einen eigenen Prompt zusammenbaut (SPEC Req 6): nur ein
    kurzer Steuer-Satz, der Vorsicht/Substanz je nach Signal-Staerke setzt.
    """
    # Konfidenz-Schwelle: niedrig = vorsichtiger + kuerzer + eher eine Frage.
    if confidence is not None and confidence < 0.5:
        return ('Register: unsicheres Signal — vorsichtiger, kuerzer, eher eine offene Frage '
                'als eine feste Antwort.')
    if mode == 'meeting':
        return ('Register: Meeting, beide Seiten hoerbar — mehr Substanz, konkret auf das '
                'tatsaechlich Gesagte.')
    # Cold-Call / Default: mittlere Vorsicht.
    return 'Register: knapp und konkret; im Zweifel lieber eine kurze Rueckfrage.'


def build_answer_context(*, user_id: int, sid: str | None, primary_intent: str | None,
                         mode: str = 'cold_call', confidence: float | None = None,
                         role: str = 'interessent', is_auto_triggered: bool = False) -> list[dict]:
    """EINE Quelle des Antwort-System-Prompts fuer Auto/Knopf/QA (SPEC Req 1).

    Rueckgabe: LISTE von System-Bloecken — STABIL vorne (Paradigma + Rollen-Ziel +
    Grounding + Profil-Stabilteil), VOLATIL hinten (EIN Intent-Hinweis +
    Modus/Konfidenz-Register + volatiler Profilteil). Strukturell cache-faehig
    getrennt (_layer-Marker), Caching NICHT aktiviert (Phase 2).

    Rolle/Modus/Konfidenz/EIN-Intent sind PARAMETER (kein if-Prompt-Zweig, Req 3/5/6).
    MUST NOT raise: jeder Teil fail-open (.get-Defaults, _profile_blocks -> ('','')).
    Kein DB-Call im Hot-Path (load_answer_config = reiner Speicher-Zugriff).

    KEIN Live-Aufrufer in P1-01 — P1-02 verdrahtet Auto/Knopf/QA auf diese Funktion.
    """
    cfg = load_answer_config(user_id, sid)
    stabil, volatil = _profile_blocks(user_id, mode, sid)

    # ── STABIL-Block: Paradigma + Rollen-Ziel + Grounding + Profil-Stabilteil ──
    role_goal = (cfg.get('roles') or {}).get(role) or (cfg.get('roles') or {}).get('interessent', '')
    _stabil_parts = list(cfg.get('paradigm') or [])
    if role_goal:
        _stabil_parts.append(f'Rolle: {role_goal}')
    if cfg.get('grounding'):
        _stabil_parts.append(cfg['grounding'])
    if stabil:
        _stabil_parts.append(stabil)
    stabil_block = '\n'.join(_stabil_parts)

    # ── VOLATIL-Block: EIN Intent-Hinweis + Register + volatiler Profilteil ────
    hint = (cfg.get('intent_hints') or {}).get(primary_intent) or cfg.get('default_intent_hint') or {}
    conf_register = _confidence_register(mode, confidence, is_auto_triggered)
    _volatil_parts = [
        f"Erkannter Punkt: {primary_intent or '(unklar)'} — "
        f"{hint.get('register', '')}; {hint.get('hebel', '')}",
        conf_register,
    ]
    if volatil:
        _volatil_parts.append(volatil)
    volatil_block = '\n'.join(_volatil_parts)

    return [
        {'role': 'system', 'text': stabil_block, '_layer': 'stable'},    # _layer -> Phase-2-Caching-Marker
        {'role': 'system', 'text': volatil_block, '_layer': 'volatile'},
    ]


# ── TAXO3 P1-02: Live-Wiring der EINEN Quelle in die 3 Antwort-Pfade ─────────
# Duenne Verdrahtungs-Schicht (liest per-SID-State) um build_answer_context (rein/
# testbar). Hier, weil beide Konsumenten (claude_service, qa_pipeline) prompt_pipeline
# schon importieren — vermeidet eine qa->claude_service-Kopplung nur fuer die Prompt-
# Assembly. P1-02-Deviation: dieser Plan fasst prompt_pipeline.py mit an (nur diese
# Wiring-Helfer, build_answer_context selbst bleibt unveraendert).

def derive_answer_params(sid: str | None) -> dict:
    """Leitet user_id/Rolle/Modus/EIN-Intent/Konfidenz aus dem per-SID-State ab (Req 3/5/6).

    Rolle (Parameter, kein Code-Zweig): mode=='meeting' -> 'meeting'; sonst
    contact_category 'gatekeeper' -> 'gatekeeper', 'target' -> 'interessent'.
    primary_intent + confidence: per-SID (TAXO1-Live). Punkt 26: der Wert wird zum
    Aufruf-Zeitpunkt gelesen; laeuft der Leser dem Schreiber voraus -> None ->
    fail-open Default-Intent (NIE falscher Intent). Reiner Lese-Zugriff, nie raise.
    """
    user_id = 0
    mode = 'cold_call'
    role = 'interessent'
    primary_intent = None
    confidence = None
    try:
        import services.live_session as _ls
        _st: dict = {}
        if sid:
            with _ls._session_state_lock:
                _st = dict(_ls._session_state.get(sid) or {})
        user_id = _st.get('user_id') or 0
        mode = _st.get('mode') or 'cold_call'
        _sub = _st.get('state') or {}
        _cat = _sub.get('contact_category') or 'gatekeeper'
        role = 'meeting' if mode == 'meeting' else ('gatekeeper' if _cat == 'gatekeeper' else 'interessent')
        primary_intent = _sub.get('primary_intent')
        _conf = _sub.get('confidence')
        confidence = float(_conf) if _conf is not None else None
    except Exception as _e:
        print(f"[AnswerParams] fail-open default: {type(_e).__name__}")
    return {'user_id': user_id, 'role': role, 'mode': mode,
            'primary_intent': primary_intent, 'confidence': confidence}


def answer_system_content(sid: str | None, *, is_auto_triggered: bool,
                          primary_intent: str | None = None,
                          confidence: float | None = None) -> list[dict]:
    """System-Content-Liste (Anthropic-Format) aus build_answer_context fuer die Live-Pfade.

    PHASE 1: PLAIN Content-Bloecke [{'type':'text','text':...}] OHNE cache_control —
    Caching (cache_control-Layering auf dem stabilen Prefix) ist Phase 2 (Plan 04).
    primary_intent/confidence: explizit uebergeben (z.B. geklickter typ, QA-confidence)
    ODER aus per-SID abgeleitet (None -> derive). Fail-open: nie leer, nie raise.
    """
    p = derive_answer_params(sid)
    _intent = primary_intent if primary_intent is not None else p['primary_intent']
    _conf = confidence if confidence is not None else p['confidence']
    blocks = build_answer_context(
        user_id=p['user_id'], sid=sid, primary_intent=_intent,
        mode=p['mode'], confidence=_conf, role=p['role'],
        is_auto_triggered=is_auto_triggered,
    )
    content = [{'type': 'text', 'text': b['text']} for b in blocks if b.get('text')]
    if not content:
        content = [{'type': 'text', 'text': 'Verstehen und helfen, nie druecken.'}]
    return content
