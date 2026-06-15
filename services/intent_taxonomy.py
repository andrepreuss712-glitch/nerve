"""Geteilte Intent-Taxonomie (Geruest §1, D-01). Versionierter Code-Vertrag, NICHT
user-editierbar. User-Erweiterung nur via custom_objection_*-Praefix pro Profil.
Geschrieben in intent_event.intent_type (Welle 4).

TAXO1-Welle 1: legt NUR die Quelle (Konstante + Validator) — KEIN Live-Writer,
KEINE Scoring-Logik, KEIN Import der Live-Module (abhaengigkeitsfrei).
"""

# Pflicht non-null an jedem spaeteren intent_event-Insert (Welle 4).
TAXONOMY_VERSION = "v1"

# Geruest §1 — die 11 Kern-/Gemini-Werte (ASCII-Identifier, Code-Konstante).
INTENT_TAXONOMY_V1: tuple[str, ...] = (
    "echter_einwand",
    "vorwand",
    "reflexeinwand",
    "kaufsignal",
    "aufschub",
    "info_frage",
    "gatekeeper",
    "wettbewerber_referenz",
    "hard_opt_out",
    "commitment",
    "meta_kommunikation",
)

# Profil-spezifische Erweiterung (KEIN Enum-Eintrag) via Praefix-Match.
CUSTOM_PREFIX = "custom_objection_"


def is_valid_intent_type(value: str) -> bool:
    """True wenn value ein Kern-Taxonomie-Wert ODER ein custom_objection_<x> ist."""
    return value in INTENT_TAXONOMY_V1 or (
        isinstance(value, str)
        and value.startswith(CUSTOM_PREFIX)
        and len(value) > len(CUSTOM_PREFIX)
    )


def all_core_intents() -> tuple[str, ...]:
    """Alle Kern-Intents (fuer Tests/Prompt-Bau in Welle 4)."""
    return INTENT_TAXONOMY_V1
