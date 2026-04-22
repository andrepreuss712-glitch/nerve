#!/usr/bin/env python3
"""
scripts/migrate_branche_to_enum.py — Phase 08 D-09 Data-Migration.

Ersetzt Freitext-Branche-Werte in profiles.branche durch Enum-Werte und
konserviert den Originaltext in profiles.daten['basis']['branche_kontext'].

Heuristik: Keyword-Match mit Prioritaets-Reihenfolge (siehe HEURISTIC_MAP).
Nicht-matchende Werte -> 'sonstiges' + Originaltext in branche_kontext.

Usage:
  python scripts/migrate_branche_to_enum.py --dry-run   # zeigt nur Plan, schreibt nichts
  python scripts/migrate_branche_to_enum.py --run       # schreibt in DB

Idempotent: Schon-Enum-Werte werden skipped (kein Doppel-Mapping).

Priority-Regeln (wichtig bei mehrdeutigen Strings):
  1. saas_b2b vor beratung ("IT-Beratung" -> beratung ist OK wenn kein saas-Keyword)
  2. finanzprodukte vor beratung ("Finanzberatung" -> finanzprodukte)
  3. versicherung vor finanzprodukte (Versicherung spezifischer)
  4. Erster Match in Tabellenreihenfolge gewinnt

Umlaut-Normalisierung:
  Match-Strings sind normalisiert (lowercase + ae/oe/ue/ss). Input wird
  durch _normalize_branche gezogen bevor die Heuristik greift.

Safety:
  - --dry-run ist Default-Mode; --run muss explizit gesetzt sein.
  - Phase-01 Pre-Backup (database/nerve.db.bak_pre_v08_01) dient als
    Rollback-Path bei Daten-Disaster.
  - Originaltext IMMER in daten.basis.branche_kontext konserviert
    (appended wenn schon belegt, ' | ' Separator).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Optional

# Rule-3 Auto-fix: Sicherstellen dass der Repo-Root im sys.path liegt, damit
# `from database.db import SessionLocal` auch bei Aufruf via
# `python scripts/migrate_branche_to_enum.py` aus anderen cwds funktioniert.
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


# ── Whitelist der 8 Enum-Werte (aus RESEARCH Focus Area 7) ─────────────────
VALID_ENUMS = {
    'saas_b2b', 'maschinenbau', 'versicherung', 'finanzprodukte',
    'immobilien', 'coaching', 'beratung', 'sonstiges',
}


# Reihenfolge = Prioritaet. Erster Match gewinnt.
# Alle keyword-Strings sind bereits normalisiert (lowercase, ae/oe/ue/ss).
#
# Rule-1 Auto-fix: maschinenbau VOR finanzprodukte, weil 'Anlagenbau' sonst
# das finanz-Keyword 'anlage' treffen wuerde (Substring-Match). Die Plan-Spec
# hat versicherung vor finanzprodukte explizit gefordert; die Collision
# maschinenbau<->finanz war implizit und wird hier sauber aufgeloest.
#
# Priority-Chain:
#   1. saas_b2b        (SaaS/Cloud-Keywords, spezifisch)
#   2. versicherung    (versicher/assekuranz, spezifisch vor Finanz)
#   3. maschinenbau    (anlagenbau/werkzeugmaschin vor finanz-'anlage')
#   4. finanzprodukte  (finanz/investment/anlage etc.)
#   5. immobilien      (immobilien/makler/wohnung)
#   6. coaching        (coach/mentor)
#   7. beratung        (beratung/consulting — nur wenn keine Finanz-Keywords)
HEURISTIC_MAP = [
    ('saas_b2b',       ['saas', 'b2b', 'software', 'cloud', 'platform', 'api']),
    ('versicherung',   ['versicher', 'assekuranz', 'policen']),          # VOR finanzprodukte
    ('maschinenbau',   ['maschinenbau', 'industrie', 'produktion',
                        'fertigung', 'engineering', 'anlagenbau',
                        'werkzeugmaschin']),                              # VOR finanzprodukte ('anlage'-Collision)
    ('finanzprodukte', ['finanz', 'investment', 'anlage', 'kapital',
                        'bank', 'fonds']),
    ('immobilien',     ['immobilien', 'makler', 'grundstueck', 'wohnung']),
    ('coaching',       ['coaching', 'coach', 'mentor']),
    ('beratung',       ['beratung', 'consulting', 'berater', 'consultant']),
]


# ── Pure-Funktionen (stateless, testbar ohne DB) ──────────────────────────

def _normalize_branche(s: Optional[str]) -> str:
    """Umlaut-Ersatz + lowercase + strip. NICHT fuer Display — nur Match."""
    if not s:
        return ''
    return (s.lower()
            .replace('\u00e4', 'ae')   # ae
            .replace('\u00f6', 'oe')   # oe
            .replace('\u00fc', 'ue')   # ue
            .replace('\u00df', 'ss')   # ss
            .strip())


def _map_branche_to_enum(freitext: Optional[str]) -> str:
    """Heuristik-Mapping Freitext -> Enum. Fallback 'sonstiges'."""
    if not freitext:
        return 'sonstiges'
    # Idempotenz: schon Enum-Wert -> direkter Rueckgabe
    if freitext in VALID_ENUMS:
        return freitext
    norm = _normalize_branche(freitext)
    for enum, keywords in HEURISTIC_MAP:
        for kw in keywords:
            if kw in norm:
                return enum
    return 'sonstiges'


def _migrate_profile_branche(profile_id: int,
                             original: str,
                             daten: dict) -> tuple:
    """Liefert (enum_value, updated_daten).

    Semantics:
      - Wenn `original` schon Enum-Wert -> (original, daten unveraendert),
        idempotent.
      - Sonst: (mapped_enum, daten mit branche_kontext-Merge).
      - Wenn branche_kontext bereits belegt: APPENDED mit ' | ' Separator
        (kein Overwrite).
    """
    if original in VALID_ENUMS:
        return (original, daten)

    new_enum = _map_branche_to_enum(original)
    basis = daten.get('basis') or {}
    existing_raw = basis.get('branche_kontext', '')
    existing = existing_raw.strip() if isinstance(existing_raw, str) else ''
    if existing:
        basis['branche_kontext'] = f'{existing} | {original}'.strip()
    else:
        basis['branche_kontext'] = original.strip()
    daten['basis'] = basis
    return (new_enum, daten)


# ── DB-Orchestrator ────────────────────────────────────────────────────────

def _run(dry_run: bool = True) -> int:
    """Execute migration.

    Returns count of profiles migrated (or 'to-migrate' in dry-run).
    Returns -1 on Import-Error (script started from wrong cwd).
    """
    try:
        from database.db import SessionLocal
        from database.models import Profile
    except ImportError as e:
        print(f"[MIGRATE] Import failed (run from repo root): {e}",
              file=sys.stderr)
        return -1

    db = SessionLocal()
    count = 0
    try:
        profiles = db.query(Profile).all()
        print(f"[MIGRATE] scanning {len(profiles)} profiles ...")
        for p in profiles:
            original = (p.branche or '').strip()
            if not original:
                continue
            if original in VALID_ENUMS:
                continue  # Already migrated — skip
            try:
                daten = json.loads(p.daten) if p.daten else {}
            except Exception:
                daten = {}
            new_enum, new_daten = _migrate_profile_branche(p.id, original, daten)
            kontext_preview = (
                (new_daten.get('basis', {}) or {})
                .get('branche_kontext', '')[:40]
            )
            print(f"[MIGRATE] profile_id={p.id} "
                  f"'{original[:40]}' -> enum='{new_enum}', "
                  f"kontext_preserved='{kontext_preview}'")
            if not dry_run:
                p.branche = new_enum
                p.daten = json.dumps(new_daten, ensure_ascii=False)
            count += 1
        if not dry_run:
            db.commit()
            print(f"[MIGRATE] committed {count} profile updates")
        else:
            print(f"[MIGRATE] DRY-RUN — would migrate {count} profiles")
    finally:
        db.close()
    return count


def _main():
    parser = argparse.ArgumentParser(
        description='Phase 08 D-09 branche-Heuristik-Migration.'
    )
    parser.add_argument('--dry-run', action='store_true',
                        help='Preview without writing (recommended before --run)')
    parser.add_argument('--run', action='store_true',
                        help='Execute migration — writes to database!')
    args = parser.parse_args()
    if not args.dry_run and not args.run:
        parser.error('Specify --dry-run or --run')
    _run(dry_run=args.dry_run)


if __name__ == '__main__':
    _main()
