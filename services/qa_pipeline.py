"""
services/qa_pipeline.py
────────────────────────────────────────────────────────────────────
Phase 08.5 QA-Pipeline: Klassifikator + FAQ-Match + Unknown-Einwand-Generierung.

Exports:
  - classify_utterance(text, kontext, user_id) -> dict
      Returns {"kategorie": str, "confidence": float, "einwand_zitat": str|None}
      Kategorien: einwand_unknown | frage | smalltalk_none | einwand_known
      MUST NOT raise — fail-open zu smalltalk_none/0.0.

  - generate_qa_response(utterance, category, profile_data, anrede, version, user_id) -> str
      Haiku-Response fuer einwand_unknown oder frage.
      MUST NOT raise — returns "" on error.

  - match_faq(utterance, faqs, threshold=0.75) -> Optional[dict]
      Semantic FAQ match via sentence-transformers (local, DSGVO-safe).
      MUST NOT raise — returns None on error.

  - apply_tabu_filter(text, tabu_begriffe) -> bool
      Case-insensitive substring match. True = text contains forbidden term.

Haiku-only constraint (CLAUDE.md). Thread-safety: stateless functions;
embedding model lazy-init with threading.Lock.
"""
from __future__ import annotations
from typing import Optional
import threading as _threading

from services.prompt_pipeline import (
    build_profile_context, resolve_prompt_version, log_pipeline_event
)

# ── Fallback prompts (used wenn prompt_versions lookup miss) ─────────────
_FALLBACK_CLASSIFIER_PROMPT = (
    "Du bist ein Echtzeit-Klassifikator fuer Verkaufsgespraeche. "
    "Analysiere die letzte Kunden-Aeusserung und klassifiziere in EINE Kategorie:\n"
    "- einwand_unknown: Kunde bringt einen Einwand (nicht bereits durch Keyword erfasst)\n"
    "- frage: Kunde stellt eine direkte Frage\n"
    "- smalltalk_none: Zustimmung, Smalltalk, oder Berater liest einen fertigen Vertriebs-Satz vor\n"
    "- einwand_known: Einwand bereits durch Keyword-Matcher erkannt\n\n"
    "Regeln:\n"
    "- Antworte NUR als JSON: {\"kategorie\": \"...\", \"confidence\": 0.00, \"einwand_zitat\": \"...\"|null}\n"
    "- confidence: 0.0-1.0\n"
    "- einwand_zitat: konkreter Satz des Kunden (nur bei einwand_unknown/frage)\n"
    "- Bei Unsicherheit zwischen einwand_unknown und frage: frage hat Vorrang\n"
    "- Wenn der Sprecher einen fertigen Vertriebs-Satz vorliest: smalltalk_none"
)

_FALLBACK_QA_RESPONSE_PROMPT = (
    "Du beantwortest unbekannte Einwaende oder offene Fragen eines Kunden im Verkaufsgespraech.\n"
    "Anrede: {anrede} (konsequent, niemals wechseln).\n"
    "Profil-Kontext:\n{profile_context}\n\n"
    "Regeln:\n"
    "- Max. 45 Woerter\n"
    "- Niemals apologetisch\n"
    "- Niemals halluzinieren — wenn Daten fehlen, allgemein formulieren\n"
    "- Antworte NUR als Klartext (keine JSON-Wrapper)"
)

# ── Embedding Model Lazy-Init (sentence-transformers, local, DSGVO-safe) ─
_MODEL = None
_MODEL_LOCK = _threading.Lock()


def _get_embedding_model():
    """Lazy-init sentence-transformers model. MUST NOT raise into live-loop."""
    global _MODEL
    if _MODEL is None:
        with _MODEL_LOCK:
            if _MODEL is None:
                try:
                    from sentence_transformers import SentenceTransformer
                    _MODEL = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
                    print("[QA] embedding model loaded (paraphrase-multilingual-MiniLM-L12-v2)")
                except Exception as e:
                    print(f"[QA] embedding model load failed: {e}")
                    _MODEL = False  # sentinel: failed, don't retry per call
    return _MODEL if _MODEL else None


# ── Prompt template loader (analog ewb_pipeline._load_prompt_template) ───
def _load_qa_template(module: str, version: str) -> str:
    """Load prompt_text fuer module + version aus prompt_versions.
    Fallback auf _FALLBACK_CLASSIFIER_PROMPT oder _FALLBACK_QA_RESPONSE_PROMPT.
    MUST NOT raise."""
    try:
        from database.db import SessionLocal
        from database.models import PromptVersion
        db = SessionLocal()
        try:
            row = (db.query(PromptVersion)
                   .filter_by(module=module, version=version, is_active=True)
                   .first())
            if row and row.prompt_text:
                return row.prompt_text
            print(f"[QA] template miss module={module} version={version} — using fallback")
        finally:
            db.close()
    except Exception as e:
        print(f"[QA] template load failed module={module} version={version}: {e}")
    if module == 'classifier':
        return _FALLBACK_CLASSIFIER_PROMPT
    if module == 'qa_response':
        return _FALLBACK_QA_RESPONSE_PROMPT
    return ""


# ── Public: classify_utterance ───────────────────────────────────────────
def classify_utterance(text: str, kontext: str, user_id: int) -> dict:
    """Haiku-Call: Klassifiziert utterance in 4 Kategorien.
    Returns {"kategorie": str, "confidence": float, "einwand_zitat": str|None}.
    MUST NOT raise — fail-open zu {"kategorie": "smalltalk_none", "confidence": 0.0}.
    """
    fallback = {"kategorie": "smalltalk_none", "confidence": 0.0, "einwand_zitat": None}
    if not text or not text.strip():
        return fallback
    try:
        version = resolve_prompt_version('classifier', user_id)
        system_prompt = _load_qa_template('classifier', version)

        # Lazy-import claude_client to avoid circular deps at module load
        from services.claude_service import claude_client, _parse_json

        user_msg = (
            f"Kontext (bisheriger Gespraechsverlauf):\n{kontext or '(kein Kontext)'}\n\n"
            f"Letzte Kunden-Aeusserung:\n\"{text}\"\n\nKlassifiziere als JSON."
        )

        msg = claude_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=150,
            system=system_prompt,
            messages=[{"role": "user", "content": user_msg}]
        )
        raw = msg.content[0].text.strip()
        parsed = _parse_json(raw) or {}

        # Validate + coerce
        kat = parsed.get('kategorie', 'smalltalk_none')
        if kat not in ('einwand_unknown', 'frage', 'smalltalk_none', 'einwand_known'):
            kat = 'smalltalk_none'
        try:
            conf = float(parsed.get('confidence', 0.0))
            conf = max(0.0, min(1.0, conf))
        except Exception:
            conf = 0.0
        zitat = parsed.get('einwand_zitat')
        if zitat is not None and not isinstance(zitat, str):
            zitat = None

        result = {"kategorie": kat, "confidence": conf, "einwand_zitat": zitat}

        # FT-logging
        try:
            log_pipeline_event('classifier', 'qa', {
                'model': 'haiku-4-5',
                'prompt_version': version,
                'kategorie': kat,
                'confidence': conf,
            })
        except Exception as _e:
            print(f"[QA] log_pipeline_event classifier skipped: {_e}")

        # Cost-hook (analog claude_service.py pattern)
        try:
            from services.cost_tracker import log_api_cost
            u = getattr(msg, 'usage', None)
            if u is not None:
                in_tok = getattr(u, 'input_tokens', 0) or 0
                out_tok = getattr(u, 'output_tokens', 0) or 0
                log_api_cost('anthropic', 'haiku-4-5', user_id=None,
                             units=in_tok/1000.0, unit_type='per_1k_input_tokens',
                             context_tag='qa_classifier')
                log_api_cost('anthropic', 'haiku-4-5', user_id=None,
                             units=out_tok/1000.0, unit_type='per_1k_output_tokens',
                             context_tag='qa_classifier')
        except Exception as _e:
            print(f"[QA] cost-hook classifier skipped: {_e}")

        print(f"[QA] classify user_id={user_id} kategorie={kat} conf={conf:.2f}")
        return result
    except Exception as e:
        print(f"[QA] classify_utterance failed: {e}")
        return fallback


# ── Public: generate_qa_response ─────────────────────────────────────────
def generate_qa_response(utterance: str, category: str, profile_data: dict,
                         anrede: str, version: str, user_id: int) -> str:
    """Haiku-Response fuer einwand_unknown oder frage. MUST NOT raise — returns "" on error."""
    if not utterance or category not in ('einwand_unknown', 'frage'):
        return ""
    try:
        version = version or resolve_prompt_version('qa_response', user_id)
        template = _load_qa_template('qa_response', version)
        profile_ctx = build_profile_context(user_id, mode='live') or ""
        system_prompt = template.format(anrede=(anrede or 'Sie'), profile_context=profile_ctx)

        from services.claude_service import claude_client

        kat_hint = "unbekannten Einwand" if category == 'einwand_unknown' else "offene Frage"
        user_msg = (
            f"Kunde hat soeben diese {kat_hint} geaeussert:\n\"{utterance}\"\n\n"
            f"Formuliere eine kurze, konkrete Antwort (max. 45 Woerter)."
        )

        msg = claude_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            system=system_prompt,
            messages=[{"role": "user", "content": user_msg}]
        )
        text = msg.content[0].text.strip()

        # FT-logging
        try:
            log_pipeline_event('qa_response', 'qa', {
                'model': 'haiku-4-5',
                'prompt_version': version,
                'category': category,
                'response_len': len(text),
            })
        except Exception as _e:
            print(f"[QA] log_pipeline_event qa_response skipped: {_e}")

        # Cost-hook
        try:
            from services.cost_tracker import log_api_cost
            u = getattr(msg, 'usage', None)
            if u is not None:
                in_tok = getattr(u, 'input_tokens', 0) or 0
                out_tok = getattr(u, 'output_tokens', 0) or 0
                log_api_cost('anthropic', 'haiku-4-5', user_id=None,
                             units=in_tok/1000.0, unit_type='per_1k_input_tokens',
                             context_tag='qa_response')
                log_api_cost('anthropic', 'haiku-4-5', user_id=None,
                             units=out_tok/1000.0, unit_type='per_1k_output_tokens',
                             context_tag='qa_response')
        except Exception as _e:
            print(f"[QA] cost-hook qa_response skipped: {_e}")

        return text
    except Exception as e:
        print(f"[QA] generate_qa_response failed: {e}")
        return ""


# ── Public: match_faq (stub — Task 2 fills in full implementation) ────────
def match_faq(utterance: str, faqs: list, threshold: float = 0.75) -> Optional[dict]:
    """Placeholder — full implementation in Task 2."""
    return None


# ── Public: apply_tabu_filter ────────────────────────────────────────────
def apply_tabu_filter(text: str, tabu_begriffe: list) -> bool:
    """Returns True wenn Text einen Tabu-Begriff enthaelt (-> Antwort verwerfen).
    Case-insensitive substring match fuer v1 (D-16)."""
    if not tabu_begriffe or not text:
        return False
    text_lower = text.lower()
    for begriff in tabu_begriffe:
        if not begriff or not isinstance(begriff, str):
            continue
        if begriff.strip() and begriff.lower() in text_lower:
            return True
    return False
