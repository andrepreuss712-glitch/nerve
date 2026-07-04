"""
services/intent_payload.py
────────────────────────────────────────────────────────────────────
Phase 08.23.2.PERSID Plan 02 — Waechter (a), PERSID Req 9.

Reine Auslagerung von build_intent_payload() aus intent_event_writer.py:100-118
(die EINE abgenickte Nicht-Isolations-Naht; CONTEXT §spec_lock).

KEIN Verhaltens-Change: der Dict-Literal + extra_payload-Merge ist identisch
zur origin. TAXO3-b bringt schema_version additiv als MIRROR_SCHEMA_VERSION —
hier noch NICHT drin.

taxonomy_version (Intent-Taxonomie, Pflicht non-null) != schema_version (Payload-Form,
TAXO3-b). Diese Datei verwaltet NUR taxonomy_version.
"""
from __future__ import annotations

from services.intent_taxonomy import TAXONOMY_VERSION


def build_intent_payload(
    source: str,
    inference_basis: str,
    abstained: bool,
    speaker_role: str,
    speaker_id: str,
    is_simulation: bool,
    origin_type: str,
    triggering_text,
    extra_payload: dict | None = None,
) -> dict:
    """Baut den payload_jsonb-Dict fuer einen IntentEvent-INSERT.

    Parameter entsprechen den 9 Pflichtfeldern aus PERSID-RESEARCH §4(a):
      source, inference_basis, taxonomy_version, abstained, speaker_role,
      speaker_id, is_simulation, origin_type, triggering_text.

    taxonomy_version wird automatisch aus TAXONOMY_VERSION-Konstante gesetzt
    (non-null, Pflicht).

    extra_payload: optionale zusaetzliche Keys (z.B. Kontext-Felder). Werden
    in den Dict gemergt — MUSS in Whitelist (_ALLOWED in test_intent_payload_guard.py)
    stehen, sonst roetet der Watcher-Test.

    KEIN schema_version (TAXO3-b, additiv als MIRROR_SCHEMA_VERSION).
    """
    payload = {
        'source': source,
        'inference_basis': inference_basis,
        'taxonomy_version': TAXONOMY_VERSION,
        'abstained': bool(abstained),
        'speaker_role': speaker_role,
        'speaker_id': speaker_id,
        'is_simulation': bool(is_simulation),
        'origin_type': origin_type,
        # Anonymisierter Ausloeser-Wortlaut (denormalisiert, TAXO2/3-Fundament).
        # Roh-PII kommt hier NIE an — Aufrufer anonymisieren via anonymize_output
        # + Sentinel->None VOR dem Aufruf. IMMER gesetzt (auch None) — symmetrisch
        # zu inference_basis. JSON-Key in payload_jsonb, KEINE Schema-Migration.
        'triggering_text': triggering_text,
    }
    if extra_payload:
        for _k, _v in extra_payload.items():
            payload[_k] = _v
    return payload
