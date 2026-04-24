"""
services/profile_migration.py
────────────────────────────────────────────────────────────────────
Phase 08.5 Korrektur 1: Tabu-Begriffe Migration Helper.

Exports:
  - TABU_DEFAULT_PAIRS — 13 default (Begriff, Alternative) tuples
  - migrate_tabu_begriffe(profile_daten: dict) -> dict
      Migrates tabu_begriffe field from any shape to List-of-Objects.
      Idempotent. Modifies profile_daten in-place and returns it.

Shape contract:
  Old (string list): ["Kosten", "Problem", ...]
  New (object list): [{"begriff": "Kosten", "alternative": "Investition"}, ...]
  Empty / missing   → 13 default pairs seeded
"""
from __future__ import annotations

# ── 13 Default-Pairs (German user-facing text — echte Umlaute) ───────────────
TABU_DEFAULT_PAIRS: list[tuple[str, str]] = [
    ("Kosten", "Investition"),
    ("Problem", "Herausforderung"),
    ("günstig", "effizient"),
    ("billig", "preis-attraktiv"),
    ("Risiko", "Absicherung"),
    ("Schwäche", "Entwicklungspotenzial"),
    ("Nachteil", "Unterschied"),
    ("verkaufen", "helfen"),
    ("müssen", "können"),
    ("alt", "etabliert"),
    ("kompliziert", "strukturiert"),
    ("verlieren", "absichern"),
    ("Konkurrenz", "Mitbewerber"),
]

_DEFAULT_OBJECTS: list[dict] = [
    {"begriff": b, "alternative": a} for b, a in TABU_DEFAULT_PAIRS
]


def _normalize_entry(entry) -> dict | None:
    """Normalize a single tabu entry to {begriff, alternative}.

    - str  → {"begriff": str, "alternative": ""}
    - dict → ensure both keys exist, default missing to ""
    - None/other → skip (return None)
    """
    if isinstance(entry, str):
        s = entry.strip()
        if not s:
            return None
        return {"begriff": s, "alternative": ""}
    if isinstance(entry, dict):
        begriff = str(entry.get("begriff") or "").strip()
        alternative = str(entry.get("alternative") or "").strip()
        if not begriff:
            return None
        return {"begriff": begriff, "alternative": alternative}
    return None


def migrate_tabu_begriffe(profile_daten: dict) -> dict:
    """Migrate tabu_begriffe field in profile_daten to List-of-Objects shape.

    Rules:
      1. If list is empty or missing → seed 13 TABU_DEFAULT_PAIRS
      2. If list contains strings → convert each to {"begriff": s, "alternative": ""}
      3. If list contains objects → pass through (ensure both keys exist)
      4. Mixed list → each entry normalized per its type
      5. Idempotent — running N times === running 1 time

    Modifies profile_daten dict in-place and returns it.
    """
    if not isinstance(profile_daten, dict):
        profile_daten = {}

    # Ensure basis key exists
    if not isinstance(profile_daten.get("basis"), dict):
        profile_daten["basis"] = {}

    basis = profile_daten["basis"]
    raw = basis.get("tabu_begriffe")

    # Empty or missing → seed defaults
    if not raw:
        basis["tabu_begriffe"] = list(_DEFAULT_OBJECTS)
        return profile_daten

    if not isinstance(raw, list):
        basis["tabu_begriffe"] = list(_DEFAULT_OBJECTS)
        return profile_daten

    # Normalize each entry
    normalized: list[dict] = []
    for entry in raw:
        obj = _normalize_entry(entry)
        if obj is not None:
            normalized.append(obj)

    # If all entries were invalid → seed defaults
    if not normalized:
        basis["tabu_begriffe"] = list(_DEFAULT_OBJECTS)
        return profile_daten

    basis["tabu_begriffe"] = normalized
    return profile_daten
