#!/usr/bin/env python3
"""
POLISH-38 Migration: Reconcile ConversationLog counters with ObjectionEvent table.

Per POLISH-29 User-Definition ("EWB-Button gedrueckt = Einwand behandelt") muss
ConversationLog.einwaende_gesamt der Anzahl der ObjectionEvent-Rows fuer diese
Session entsprechen, und einwaende_behandelt der Anzahl der ObjectionEvents mit
success=True.

Bis Commit cf38589 war einwaende_gesamt=len(einwaende_liste) (AI-detected, nicht
User-Klicks). Sessions vor cf38589 haben deshalb Mismatches zwischen Counter und
tatsaechlichen ObjectionEvents. Dieses Script korrigiert sie.

Idempotent: nur Write wenn Counter != aggregierte Werte.

Usage:
    python scripts/migrate_polish_38_counters.py --dry-run                # Dry-Run (zeigt nur was geaendert wuerde)
    python scripts/migrate_polish_38_counters.py --confirm-production     # Produktions-Run (scharf)

LB-02 (2026-04-21): --dry-run via argparse (zuvor '--dry' in sys.argv
-> operator folgt Doc, schreibt in Prod). Zusaetzlich verpflichtender
--confirm-production Safeguard fuer scharfe Laeufe ohne Dry-Run.
"""
import sys
import os

# Bootstrap project path so `from database.*` imports work when called from repo root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import func, case
from database.db import get_session
from database.models import ConversationLog, ObjectionEvent


def main(dry_run: bool = False) -> int:
    db = get_session()
    try:
        # Aggregiere ObjectionEvents pro conversation_log_id
        agg_q = (
            db.query(
                ObjectionEvent.conversation_log_id.label('cid'),
                func.count(ObjectionEvent.id).label('total'),
                func.sum(case((ObjectionEvent.success == True, 1), else_=0)).label('ok'),
            )
            .group_by(ObjectionEvent.conversation_log_id)
        )
        agg_map = {row.cid: (int(row.total or 0), int(row.ok or 0)) for row in agg_q.all()}

        if not agg_map:
            print("[migrate] Keine ObjectionEvent-Rows in der DB - nichts zu tun.")
            return 0

        print(f"[migrate] {len(agg_map)} ConversationLog-IDs haben ObjectionEvents - pruefe Counter...")

        updated = 0
        skipped = 0
        for cid, (total, ok) in agg_map.items():
            conv = db.get(ConversationLog, cid)
            if conv is None:
                print(f"[migrate] WARN: ObjectionEvents verweisen auf conv.id={cid}, aber ConversationLog-Row fehlt (orphan) - skip")
                continue
            cur_total = conv.einwaende_gesamt or 0
            cur_ok = conv.einwaende_behandelt or 0
            if cur_total == total and cur_ok == ok:
                skipped += 1
                continue
            print(f"[migrate] conv.id={cid}: einwaende_gesamt {cur_total}->{total}, einwaende_behandelt {cur_ok}->{ok}")
            if not dry_run:
                conv.einwaende_gesamt = total
                conv.einwaende_behandelt = ok
            updated += 1

        if dry_run:
            print(f"[migrate] DRY-RUN: {updated} Rows wuerden geaendert, {skipped} sind bereits konsistent.")
        else:
            db.commit()
            print(f"[migrate] OK: {updated} Rows korrigiert, {skipped} bereits konsistent.")
        return 0
    finally:
        db.close()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(
        description="Reconcile ConversationLog counters from ObjectionEvent (POLISH-38)."
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help="Zeigt intendierte Aenderungen, schreibt NICHT in die DB.",
    )
    parser.add_argument(
        '--confirm-production',
        action='store_true',
        help="Pflicht fuer Produktions-Lauf (ohne --dry-run). Schuetzt vor versehentlichem Schreiben.",
    )
    args = parser.parse_args()

    if not args.dry_run and not args.confirm_production:
        print("[migrate] FEHLER: Produktions-Lauf braucht --confirm-production flag.")
        print("[migrate] Tipp: Erst mit --dry-run pruefen, dann mit --confirm-production scharf laufen lassen.")
        sys.exit(2)

    sys.exit(main(dry_run=args.dry_run))
