"""
services/qa_pipeline.py
────────────────────────────────────────────────────────────────────
Phase 08.5 QA-Pipeline: Klassifikator + FAQ-Match + Unknown-Einwand-Generierung.

Exports:
  - classify_utterance(text, kontext, user_id) -> dict
      Returns {"kategorie": str, "confidence": float, "einwand_zitat": str|None}
      Kategorien: einwand_unknown | frage | smalltalk_none | einwand_known
      MUST NOT raise — fail-open zu smalltalk_none/0.0.

  - generate_qa_response(utterance, category, profile_data, anrede, confidence,
                         version, user_id) -> str
      Haiku-Response fuer einwand_unknown oder frage.
      confidence >= 0.80  → direct answer (Tabu-Alternatives applied)
      confidence <  0.80  → Rückfrage-branch, prefix "Frag nach:"
      NEVER silent, NEVER halluzinated. MUST NOT raise — fallback Rückfrage.

  - match_faq(utterance, faqs, threshold=0.75) -> Optional[dict]
      Semantic FAQ match via sentence-transformers (local, DSGVO-safe).
      MUST NOT raise — returns None on error.

  - build_tabu_instruction(profile: dict) -> str
      Returns system-prompt block for prompt_pipeline. Empty string if no complete pairs.

  - apply_tabu_safety_net(text: str, tabu_pairs: list[dict]) -> str
      Post-generation defensive substitution. Word-boundary regex replace.

  - apply_tabu_filter(text, tabu_begriffe) -> bool
      Legacy: Case-insensitive substring match. True = text contains forbidden term.

Haiku-only constraint (CLAUDE.md). Thread-safety: stateless functions;
embedding model lazy-init with threading.Lock.
"""
from __future__ import annotations
import re
from typing import Optional
import threading as _threading
import config

from services.prompt_pipeline import (
    build_profile_context, resolve_prompt_version, answer_system_content
)

# ── Confidence threshold (Korrektur 3) ───────────────────────────────────────
CONFIDENCE_THRESHOLD = 0.80

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

# TAXO3 P1-02: _SYSTEM_PROMPT_QA ENTFERNT (Selbstbau tot). Der System-Prompt kommt
# jetzt aus build_answer_context (via answer_system_content) — EINE Quelle fuer alle
# 3 Antwort-Pfade. Die drueckerische Formulierung ("...die den Kunden zur
# Konkretisierung ZWINGT") + die hartcodierten "Frag nach:"-Beispiele (Few-Shot) sind
# damit weg; das Paradigma (offene Frage statt Druck) + die Grounding-Regel (fehlt Fakt
# -> ehrlich sagen + Rueckfrage vorschlagen) ersetzen sie inhaltlich sauberer.
# Die Low-Confidence-Mechanik (klaerende Rueckfrage im user_msg + "Frag nach:"-Prefix
# als FE-Format-Kontrakt) bleibt strukturell erhalten (siehe generate_qa_response).

_FALLBACK_RUECKFRAGE = "Frag nach: Wie meinen Sie das genau?"

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


# ── Public: build_tabu_instruction ───────────────────────────────────────────
def build_tabu_instruction(profile: dict) -> str:
    """Returns system-prompt block for prompt_pipeline. Empty string if no complete pairs.

    Reads profile.daten.basis.tabu_begriffe (list-of-objects shape).
    Filters to complete pairs only (both Begriff and Alternative non-empty).
    Returns empty string if no complete pairs → no prompt bloat.
    """
    try:
        daten = profile.get('daten') or {}
        if not isinstance(daten, dict):
            # profile_data may be the daten dict directly (caller dependent)
            daten = profile
        basis = (daten.get('basis') or {}) if isinstance(daten, dict) else {}
        tabu = basis.get('tabu_begriffe') or []
        if not isinstance(tabu, list) or not tabu:
            return ''

        complete = []
        for p in tabu:
            if not isinstance(p, dict):
                continue
            b = str(p.get('begriff') or '').strip()
            a = str(p.get('alternative') or '').strip()
            if b and a:
                complete.append(f'{b} \u2192 {a}')

        if not complete:
            return ''

        pairs_joined = ', '.join(complete)
        return (
            f'TABU-ALTERNATIVEN \u2014 kontext-abh\u00e4ngig anwenden:\n\n'
            f'Nutze bevorzugt die Alternative WENN es um UNSER Angebot geht\n'
            f'(Preis, Feature, Vorteil):\n'
            f'[{pairs_joined}]\n\n'
            f'BEHALTE das Tabu-Wort BEWUSST wenn:\n'
            f'- Es um Schaden/Verlust beim Kunden geht\n'
            f'  (z.B. "Was kostet Sie ein verlorener Deal?")\n'
            f'- Der Satz bewusst Problem-Awareness beim Kunden erzeugt\n'
            f'- Das User-eigene Gegenargument das Tabu-Wort bereits bewusst einsetzt\n\n'
            f'Default bei Unklarheit: Alternative nutzen.\n\n'
            f'Respekt vor User-Gegenargumenten: Wenn das User-Profil-Gegenargument ein\n'
            f'Tabu-Wort enth\u00e4lt, ist das meist bewusst gesetzt. Respektiere diese\n'
            f'Formulierung. Paraphrasiere NUR wenn wirklich n\u00f6tig und \u00e4ndere NIE\n'
            f'bewusst gesetzte Tabu-W\u00f6rter im User-Gegenargument.'
        )
    except Exception as e:
        print(f"[QA] build_tabu_instruction failed: {e}")
        return ''


# ── Public: build_protected_words ────────────────────────────────────────────
def build_protected_words(profile: dict, tabu_begriffe: list) -> set:
    """Returns lowercased set of Tabu-Begriffe that appear in any
    User-Gegenargument within the profile. These words were deliberately
    placed by the user (e.g. "Was kostet Sie ein verlorener Deal?") and
    MUST NOT be substituted by the safety-net.

    MUST NOT raise — returns empty set on any error.

    Profile shape: reads profile.daten.einwaende[]. For each einwand,
    extracts text from 'gegenargument' / 'gegenargument_1' / 'text'
    (mirrors services.einwand_keyword_matcher._profile_gegenargument
    fallback chain).
    """
    protected: set = set()
    try:
        if not tabu_begriffe:
            return protected
        daten = profile.get('daten') if isinstance(profile, dict) else None
        if not isinstance(daten, dict):
            daten = profile if isinstance(profile, dict) else {}
        einwaende = daten.get('einwaende_detail') or daten.get('einwaende') or []
        if not isinstance(einwaende, list):
            return protected

        # Collect all user-counter-argument texts
        texts_lower: list[str] = []
        for e in einwaende:
            if not isinstance(e, dict):
                continue
            for field in ('gegenargument', 'gegenargument_1', 'text'):
                v = e.get(field)
                if isinstance(v, str) and v.strip():
                    texts_lower.append(v.lower())

        if not texts_lower:
            return protected

        for p in tabu_begriffe:
            if isinstance(p, dict):
                b = str(p.get('begriff') or '').strip()
            elif isinstance(p, str):
                b = p.strip()
            else:
                continue
            if not b:
                continue
            b_low = b.lower()
            # Stem-prefix match: check if any word in the Gegenargument starts
            # with the Begriff (handles German inflections: "Kosten" matches
            # "kostet", "kosten", "kostete" etc.).
            # Use the full Begriff as prefix anchor with word-boundary start.
            stem = b_low[:-1] if len(b_low) > 3 else b_low
            pattern = re.compile(rf'\b{re.escape(stem)}')
            for t in texts_lower:
                if pattern.search(t):
                    protected.add(b_low)
                    break
    except Exception as e:
        print(f"[QA] build_protected_words failed: {e}")
    return protected


# ── Public: apply_tabu_safety_net ────────────────────────────────────────────
def apply_tabu_safety_net(text: str, tabu_pairs: list,
                          protected_words: set | None = None) -> str:
    """Post-generation defensive substitution with protected-words gate.

    For each complete pair (begriff, alternative):
      - if begriff.lower() is in protected_words: skip (user deliberately
        placed this word in a Gegenargument — respect it)
      - else: replace all word-boundary occurrences of Begriff with
        Alternative (case-insensitive) — existing behavior.

    Backward compatible: protected_words defaults to None -> behaves as before.
    """
    if not tabu_pairs or not text:
        return text
    pw = protected_words or set()
    for p in tabu_pairs:
        if not isinstance(p, dict):
            continue
        b = str(p.get('begriff') or '').strip()
        a = str(p.get('alternative') or '').strip()
        if not (b and a):
            continue
        if b.lower() in pw:
            # User deliberately placed this Tabu-Wort in a Gegenargument
            # -> do not substitute.
            continue
        text = re.sub(rf'\b{re.escape(b)}\b', a, text, flags=re.IGNORECASE)
    return text


# ── Public: classify_utterance ───────────────────────────────────────────────
def classify_utterance(text: str, kontext: str, user_id: int, sid: str = None) -> dict:
    """Haiku-Call: Klassifiziert utterance in 4 Kategorien.
    Returns {"kategorie": str, "confidence": float, "einwand_zitat": str|None}.
    MUST NOT raise — fail-open zu {"kategorie": "smalltalk_none", "confidence": 0.0}.
    sid (TAXO1-03 B-B): per-SID Kosten-Attribution (org_id ueber session_id-Resolver).
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
            model=config.MODEL_ANALYSE,
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

        # Cost-hook (analog claude_service.py pattern)
        try:
            from services.cost_tracker import log_api_cost
            u = getattr(msg, 'usage', None)
            if u is not None:
                in_tok = getattr(u, 'input_tokens', 0) or 0
                out_tok = getattr(u, 'output_tokens', 0) or 0
                log_api_cost('anthropic', 'haiku-4-5', user_id=user_id or None,
                             units=in_tok/1000.0, unit_type='per_1k_input_tokens',
                             context_tag='qa_classifier', session_id=sid)
                log_api_cost('anthropic', 'haiku-4-5', user_id=user_id or None,
                             units=out_tok/1000.0, unit_type='per_1k_output_tokens',
                             context_tag='qa_classifier', session_id=sid)
        except Exception as _e:
            print(f"[QA] cost-hook classifier skipped: {_e}")

        print(f"[QA] classify user_id={user_id} kategorie={kat} conf={conf:.2f}")
        return result
    except Exception as e:
        print(f"[QA] classify_utterance failed: {e}")
        return fallback


# ── Internal: markdown sanitizer ─────────────────────────────────────────────
def _sanitize_qa_output(text: str) -> str:
    """Strip markdown artifacts the LLM may produce despite plaintext instruction.

    Removes: ```lang ... ``` code-block wrappers, --- separator lines,
    **Bold:** header markers (keeps the text after the colon), leading/trailing
    whitespace. Called on raw LLM output before any branch logic.
    """
    if not text:
        return text
    # Strip ```lang ... ``` wrappers (handles multi-line blocks)
    text = re.sub(r'```[a-zA-Z]*\n?', '', text)
    # Strip standalone --- separator lines
    text = re.sub(r'^\s*---+\s*$', '', text, flags=re.MULTILINE)
    # Strip **Label:** bold headers — keep the text after the colon
    # e.g. "**Frag nach:** foo" → "Frag nach: foo"
    text = re.sub(r'\*\*([^*]+)\*\*:', r'\1:', text)
    # Strip remaining stray ** markers
    text = text.replace('**', '')
    # Collapse multiple blank lines into one, strip surrounding whitespace
    text = re.sub(r'\n{3,}', '\n\n', text).strip()
    # Remove everything after first --- block separator if a Begründung section crept in
    # Pattern: blank line + "Begründung" or "Reasoning" section
    text = re.sub(r'\n\s*\n.*?(Begründ|Reasoning|Rationale).*', '', text,
                  flags=re.IGNORECASE | re.DOTALL)
    return text.strip()


# ── Public: generate_qa_response ─────────────────────────────────────────────
def generate_qa_response(utterance: str, category: str, profile_data: dict,
                         anrede: str, confidence: float = 1.0,
                         version: str = '', user_id: int = 0,
                         sid: str = None) -> str:
    """Haiku-Response fuer einwand_unknown oder frage.

    confidence >= CONFIDENCE_THRESHOLD (0.80) → direct answer (Tabu-Alternatives applied).
    confidence <  CONFIDENCE_THRESHOLD         → Rückfrage-branch ("Frag nach: ...")
    NEVER silent, NEVER halluzinated. MUST NOT raise — fallback Rückfrage on any error.
    """
    if not utterance or category not in ('einwand_unknown', 'frage'):
        return ""
    try:
        # ── Build Tabu instruction block ──────────────────────────────────────
        tabu_block = build_tabu_instruction(profile_data)

        # ── Get tabu pairs for safety-net ──────────────────────────────────────
        tabu_pairs: list[dict] = []
        try:
            daten = profile_data.get('daten') or profile_data or {}
            if not isinstance(daten, dict):
                daten = {}
            basis = (daten.get('basis') or {}) if isinstance(daten, dict) else {}
            tabu_raw = basis.get('tabu_begriffe') or []
            if isinstance(tabu_raw, list):
                tabu_pairs = tabu_raw
        except Exception:
            pass

        # ── Determine branch by confidence ────────────────────────────────────
        is_low_confidence = float(confidence) < CONFIDENCE_THRESHOLD

        # ── System-Prompt aus der EINEN Quelle (TAXO3 P1-02, Req 1/2/3/6/7) ────
        # build_answer_context: Paradigma + Rollen-Ziel + Grounding + Profil-Kontext,
        # Rolle/Modus/EIN-Intent/Konfidenz als Parameter (kein Selbstbau, kein "zwingt").
        # TEMPO-1: der stabile Prefix traegt cache_control (Schalter config.CACHE_ANTWORT).
        # primary_intent = per-SID (Punkt 26 fail-open); confidence durchgereicht.
        _system = answer_system_content(sid, is_auto_triggered=False, confidence=float(confidence))
        # Tabu-Instruktion (Produkt-Verbote) bleibt als eigener System-Block erhalten.
        if tabu_block:
            _system = _system + [{'type': 'text', 'text': tabu_block}]

        # ── User message ───────────────────────────────────────────────────────
        kat_hint = "unbekannten Einwand" if category == 'einwand_unknown' else "offene Frage"
        if is_low_confidence:
            confidence_hint = (
                f"\n\nHinweis: Klassifikator-Konfidenz ist niedrig ({confidence:.2f} < {CONFIDENCE_THRESHOLD}). "
                "Bevorzuge eine klärende Rückfrage ('Frag nach: ...') anstelle einer direkten Antwort."
            )
        else:
            confidence_hint = ''

        user_msg = (
            f"Kunde hat soeben diesen {kat_hint} geäußert:\n\"{utterance}\"\n"
            f"Konfidenz: {confidence:.2f}{confidence_hint}\n\n"
            f"Formuliere eine kurze, konkrete Antwort (max. 45 Wörter)."
        )

        # TEMPO-1: das cache_control-Layering sitzt jetzt in answer_system_content auf dem
        # stabilen Prefix — NICHT hier. Der Tabu-Block wird bewusst OHNE cache_control
        # HINTEN angehaengt: er ist produkt-/profilabhaengig und darf den Cache-Prefix
        # nicht mitbestimmen. anrede kommt aus dem Profil-Kontext (Volatil-Block).

        from services.claude_service import claude_client

        msg = claude_client.messages.create(
            model=config.MODEL_QA,
            max_tokens=500,  # TAXO3: Headroom gegen mid-Satz-Clipping (Laenge steuert die 2-3-Saetze-Paradigma-Regel, nicht die Kappe)
            system=_system,
            messages=[{"role": "user", "content": user_msg}]
        )
        text = _sanitize_qa_output((msg.content[0].text or '').strip())

        # ── Low-confidence: ensure "Frag nach:" prefix ────────────────────────
        if is_low_confidence:
            if not text:
                text = _FALLBACK_RUECKFRAGE
            elif not text.startswith('Frag nach:'):
                # LLM didn't follow instruction → prepend prefix
                text = f'Frag nach: {text}'
        else:
            # High-confidence: apply safety-net substitution
            if text:
                protected = build_protected_words(profile_data, tabu_pairs)
                text = apply_tabu_safety_net(text, tabu_pairs, protected)
            if not text:
                text = _FALLBACK_RUECKFRAGE

        # ── Final never-empty guard ────────────────────────────────────────────
        if not text:
            text = _FALLBACK_RUECKFRAGE

        # Cost-hook
        try:
            from services.cost_tracker import log_api_cost
            _cost_model = 'sonnet-4-5' if 'sonnet' in config.MODEL_QA else 'haiku-4-5'
            u = getattr(msg, 'usage', None)
            if u is not None:
                in_tok = getattr(u, 'input_tokens', 0) or 0
                out_tok = getattr(u, 'output_tokens', 0) or 0
                log_api_cost('anthropic', _cost_model, user_id=user_id or None,
                             units=in_tok/1000.0, unit_type='per_1k_input_tokens',
                             context_tag='qa_response', session_id=sid)
                log_api_cost('anthropic', _cost_model, user_id=user_id or None,
                             units=out_tok/1000.0, unit_type='per_1k_output_tokens',
                             context_tag='qa_response', session_id=sid)
            # Cache-Token-Logging (B1 Review-Finding)
            _cache_hits = getattr(getattr(msg, 'usage', None), 'cache_read_input_tokens', 0) or 0
            _cache_writes = getattr(getattr(msg, 'usage', None), 'cache_creation_input_tokens', 0) or 0
            if _cache_hits > 0:
                log_api_cost('anthropic', _cost_model, user_id=user_id or None,
                             units=_cache_hits/1000.0, unit_type='per_1k_cache_read_tokens',
                             context_tag='qa', call_site='qa', session_id=sid)
            if _cache_writes > 0:
                log_api_cost('anthropic', _cost_model, user_id=user_id or None,
                             units=_cache_writes/1000.0, unit_type='per_1k_cache_write_tokens',
                             context_tag='qa', call_site='qa', session_id=sid)
        except Exception as _e:
            print(f"[QA] cost-hook qa_response skipped: {_e}")

        return text
    except Exception as e:
        print(f"[QA] generate_qa_response failed: {e}")
        # Never silent — always return a Rückfrage fallback
        return _FALLBACK_RUECKFRAGE


# ── Public: match_faq ────────────────────────────────────────────────────
def match_faq(utterance: str, faqs: list, threshold: float = 0.75) -> Optional[dict]:
    """Semantic FAQ-Match via sentence-transformers (local inference, DSGVO-safe).
    faqs: list of dicts with at least 'frage_muster' key (also 'id', 'antwort', 'kategorie').
    Returns matching faq dict oder None wenn kein Match ueber threshold.
    MUST NOT raise.
    """
    if not faqs or not utterance or not utterance.strip():
        return None
    try:
        model = _get_embedding_model()
        if model is None:
            print("[QA] match_faq: embedding model unavailable, returning None")
            return None
        from sentence_transformers import util
        # WR-05: build parallel filtered list so best_idx indexes the same list as faq_texts
        filtered_faqs = [f for f in faqs if f.get('frage_muster')]
        if not filtered_faqs:
            return None
        faq_texts = [f['frage_muster'] for f in filtered_faqs]
        q_emb = model.encode(utterance, convert_to_tensor=True)
        f_embs = model.encode(faq_texts, convert_to_tensor=True)
        scores = util.cos_sim(q_emb, f_embs)[0]
        best_idx = int(scores.argmax())
        best_score = float(scores[best_idx])
        print(f"[QA] match_faq best_score={best_score:.3f} threshold={threshold}")
        if best_score >= threshold:
            return filtered_faqs[best_idx]
    except Exception as e:
        print(f"[QA] match_faq failed: {e}")
    return None


# ── Public: apply_tabu_filter (legacy, kept for backward compat) ─────────────
def apply_tabu_filter(text: str, tabu_begriffe: list) -> bool:
    """Legacy: Returns True wenn Text einen Tabu-Begriff enthaelt.
    Case-insensitive substring match. Handles both string and object shapes.
    Deprecated: use build_tabu_instruction + apply_tabu_safety_net instead."""
    if not tabu_begriffe or not text:
        return False
    text_lower = text.lower()
    for begrif in tabu_begriffe:
        if isinstance(begrif, str):
            s = begrif.strip()
            if s and s.lower() in text_lower:
                return True
        elif isinstance(begrif, dict):
            s = str(begrif.get('begriff') or '').strip()
            if s and s.lower() in text_lower:
                return True
    return False
