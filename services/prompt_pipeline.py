"""
services/prompt_pipeline.py
────────────────────────────────────────────────────────────────────
Phase 08 Shared Prompt-Pipeline-Utilities (wiederverwendbar fuer 08.5).

Exports:
  - resolve_prompt_version(module, user_id)   → A/B-Routing mit ENV-Override
  - build_profile_context(user_id, mode)      → standardisierter Profil-Kontext-String
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

def build_profile_context(user_id: int, mode: str = 'cold_call', sid: str = None) -> str:
    """Build a standardized profile-context string for system-prompts.

    Reads from services.live_session.get_profile_for_sid(sid) (Phase 08.19.4)
    or get_active_profile() as deprecated fallback for HTTP callers without SID.
    Returns empty string when no active profile (caller is responsible for an
    Anrede-fallback string).

    Fields included (Phase 08):
      - basis.unternehmen / produktbeschreibung / usps / konsequenz
      - basis.branche_kontext (D-11 NEW)
      - basis.eigene_formulierungen list (D-07 NEW)
      - basis.beweise list (D-08 NEW)
      - Anrede resolution: session_anrede > ki.ansprache > 'Sie' (D-15)
        Contains WORTWOERTLICH the phrase 'Wechsle NIEMALS' per D-15 lock.

    MUST NOT raise — fail-open to empty string on any error.
    """
    try:
        import services.live_session as ls
    except Exception as e:
        print(f"[Pipeline] live_session import failed: {e}")
        return ''

    try:
        # D-05: get_active_profile() deprecated fallback entfernt (Phase 08.19.4 Plan 04)
        # HTTP-Caller ohne SID erhalten leeren Profil-Kontext (korrekt — kein WS-Kontext)
        _, pdata = ls.get_profile_for_sid(sid) if sid else ('', {})
    except Exception as e:
        print(f"[Pipeline] get_profile failed user_id={user_id}: {e}")
        return ''

    if not pdata:
        return ''

    lines: list[str] = []

    basis = (pdata.get('basis') or {}) if isinstance(pdata, dict) else {}
    ki = (pdata.get('ki') or {}) if isinstance(pdata, dict) else {}

    # ── Basis-Felder (bestehend, siehe _build_system_prompt lines 274-283) ──
    if basis.get('unternehmen'):
        lines.append(f'Unternehmen: {basis["unternehmen"]}')
    if basis.get('produktbeschreibung'):
        lines.append(f'Produkt: {basis["produktbeschreibung"]}')
    if basis.get('preismodell'):
        lines.append(f'Preismodell: {basis["preismodell"]}')
    usps = basis.get('usps') or []
    if usps:
        lines.append(f'Alleinstellungsmerkmale (USPs): {", ".join(usps)}')
    if basis.get('konsequenz'):
        lines.append(f'Konsequenz wenn Kunde nicht kauft: {basis["konsequenz"]}')

    # ── Phase 08 D-11: branche_kontext ──────────────────────────────────────
    if basis.get('branche_kontext'):
        lines.append(f'Branchen-Kontext: {basis["branche_kontext"]}')

    # ── Phase 08 D-07: eigene_formulierungen ────────────────────────────────
    eigene = basis.get('eigene_formulierungen') or []
    if eigene:
        lines.append('\nEigene Formulierungen (User-Stil imitieren, nicht generisches Vertriebs-Sprech):')
        for f in eigene:
            lines.append(f'- "{f}"')

    # ── Phase 08 D-08: beweise ──────────────────────────────────────────────
    beweise = basis.get('beweise') or []
    if beweise:
        lines.append('\nBeweise (in Baustein "Beweis" einsetzen):')
        for b in beweise:
            lines.append(f'- {b}')

    # ── Phase 08.19.3 D-09: FAQ Q+A-Block (alle Modi) ────────────────────
    try:
        _faq_profile_id = None
        try:
            with ls.state_lock:
                _faq_profile_id = ls.state.get('active_profile_id')
        except Exception:
            pass
        if _faq_profile_id:
            from database.db import SessionLocal as _SL
            from database.models import ProfileFaq as _PF
            _fdb = _SL()
            try:
                # Cap: max 20 FAQs to prevent LLM-lost-in-middle degradation and token budget blowout.
                # Sorted by used_count DESC so most-relevant FAQs are included first.
                _faqs = _fdb.query(_PF).filter_by(profile_id=_faq_profile_id).order_by(_PF.used_count.desc()).limit(20).all()
                if len(_faqs) == 20:
                    print(f"[Pipeline] FAQ-Cap reached for profile {_faq_profile_id} (count 20+)")
                if _faqs:
                    lines.append('\nHaeufig gestellte Fragen + Muster-Antworten:')
                    for _f in _faqs:
                        lines.append(f'- F: {_f.frage_muster}')
                        lines.append(f'  A: {_f.antwort}')
            finally:
                _fdb.close()
    except Exception as _faq_e:
        print(f"[Pipeline] FAQ-Block skip: {_faq_e}")

    # ── Ton/Stil (bestehendes Feld) ────────────────────────────────────────
    if ki.get('ton'):
        lines.append(f'\nTon/Stil: {ki["ton"]}')

    # ── Anrede-Resolution (D-15 wortwoertlich): Session > Profile > 'Sie' ──
    anrede = _resolve_anrede(ls, ki)
    lines.append(
        f'\nAnrede: {anrede}. WICHTIG: Nutze konsequent {anrede}-Form. '
        f'Wechsle NIEMALS innerhalb einer Antwort zwischen Du und Sie.'
    )

    # ── Phase 08.5 Korrektur 1: Tabu-Instruction-Block ─────────────────────
    try:
        from services.qa_pipeline import build_tabu_instruction
        tabu_block = build_tabu_instruction(pdata)
        if tabu_block:
            lines.append(f'\n{tabu_block}')
    except Exception as _e:
        print(f"[Pipeline] build_tabu_instruction skipped: {_e}")

    return '\n'.join(lines)


def _resolve_anrede(ls: Any, ki: dict) -> str:
    """Anrede priority: session_anrede > ki.ansprache > 'Sie' (D-14 + D-15).

    Reads `ls.state['session_anrede']` under `ls.state_lock` — deepgram_service
    writes it under the same lock (CR-01 thread-safety).
    """
    try:
        session_anrede = None
        state = getattr(ls, 'state', None)
        lock = getattr(ls, 'state_lock', None)
        if isinstance(state, dict):
            if lock is not None:
                with lock:
                    session_anrede = state.get('session_anrede')
            else:
                session_anrede = state.get('session_anrede')
        if session_anrede:
            return session_anrede
    except Exception:
        pass
    return ki.get('ansprache') or 'Sie'

