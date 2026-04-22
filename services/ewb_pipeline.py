"""
services/ewb_pipeline.py
────────────────────────────────────────────────────────────────────
Phase 08 EWB-Modul-spezifische Prompt-Assembly.

Exports:
  - build_ewb_prompt(profile_data, anrede, version, user_id) -> str

Laedt Prompt-Template aus prompt_versions-DB (module='ewb', version=X).
Fallback _FALLBACK_V1_PROMPT wenn DB-Load scheitert oder Version unbekannt.

Nutzt services.prompt_pipeline.build_profile_context fuer Shared-Profil-Kontext.
Keine Side-Effects beim Import.
"""
from __future__ import annotations

from typing import Optional

from services.prompt_pipeline import build_profile_context


# ── Fallback-Prompt (wenn DB-Load scheitert) ───────────────────────────────
_FALLBACK_V1_PROMPT = (
    "Du bist NERVE, ein Vertriebs-KI-Assistent im Live-Call.\n\n"
    "Wenn ein Einwand kommt, liefere EINE konkrete, sofort vorlesbare "
    "Gegenargumentation in 2-3 Saetzen. Kein Fachjargon, keine Floskeln. "
    "Ende mit Gegenfrage.\n"
)


def build_ewb_prompt(profile_data: Optional[dict] = None,
                     anrede: str = 'Sie',
                     version: str = 'v1-legacy',
                     user_id: int = 0) -> str:
    """Assemble kompletten EWB-System-Prompt fuer Haiku-Call.

    Args:
        profile_data: (optional) pre-loaded Profile JSON — currently unused,
            build_profile_context reads directly from live_session.
            Kept fuer API-Symmetrie mit Plan 03 Consumer.
        anrede: 'Du' oder 'Sie' — verwendet in Fallback-Kontext wenn keine
            aktive Session/Profile-Anrede vorhanden.
        version: prompt_versions.version-String (module='ewb').
            'v1-legacy', 'v2-modular' oder beliebig — unbekannte Werte
            fuehren zu Fallback.
        user_id: Session-User (fuer Logging / Router-Integration Plan 03).

    Returns:
        System-Prompt-String fuer Claude.messages.create(system=...).
    """
    template_text = _load_prompt_template(version)

    # Kontext-Block via Shared-Utils (Phase 08 D-40).
    context_block = build_profile_context(user_id=user_id)
    if not context_block:
        # Fallback fuer Unit-Tests oder leere Session:
        # Anrede-Constraint manuell mit WORTWOERTLICH-Gate D-15.
        context_block = (
            f'Anrede: {anrede}. WICHTIG: Nutze konsequent {anrede}-Form. '
            f'Wechsle NIEMALS innerhalb einer Antwort zwischen Du und Sie.'
        )

    parts = [template_text, '\n--- AKTIVES VERKAUFSPROFIL ---', context_block]
    prompt = '\n'.join(parts)
    print(f"[EWB] v{version} assembled user_id={user_id} len={len(prompt)}")
    return prompt


def _load_prompt_template(version: str) -> str:
    """Load prompt_text fuer module='ewb' + version aus prompt_versions.

    On miss or DB-error → return _FALLBACK_V1_PROMPT. MUST NOT raise.
    """
    try:
        from database.db import SessionLocal
        from database.models import PromptVersion
        db = SessionLocal()
        try:
            row = (db.query(PromptVersion)
                   .filter_by(module='ewb', version=version, is_active=True)
                   .first())
            if row and row.prompt_text:
                return row.prompt_text
            print(f"[EWB] template miss version={version} — using fallback")
        finally:
            db.close()
    except Exception as e:
        print(f"[EWB] template load failed version={version}: {e}")
    return _FALLBACK_V1_PROMPT
