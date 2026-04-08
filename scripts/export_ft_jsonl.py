"""
Phase 04.7.1 JSONL-Export CLI-Stub.

Usage:
    python scripts/export_ft_jsonl.py --market dach --out data.jsonl
    python scripts/export_ft_jsonl.py --market dach --out data.jsonl --table objection

Exports ft_assistant_events or ft_objection_events as JSONL, one row per line.
Full anonymization + quality filter is a later phase (see CONTEXT.md deferred ideas).
"""
import argparse
import json
import sys


def main():
    parser = argparse.ArgumentParser(description="Export ft_*_events to JSONL")
    parser.add_argument("--market", default="dach", help="Filter by market (dach|us)")
    parser.add_argument("--out", required=True, help="Output JSONL file path")
    parser.add_argument("--table", default="assistant", choices=["assistant", "objection"])
    args = parser.parse_args()

    from database import db as dbmod
    from database.models import FtAssistantEvent, FtObjectionEvent

    Model = FtAssistantEvent if args.table == "assistant" else FtObjectionEvent

    db = dbmod.SessionLocal()
    count = 0
    try:
        rows = db.query(Model).filter_by(market=args.market).all()
        with open(args.out, "w", encoding="utf-8") as f:
            for r in rows:
                record = {c.name: getattr(r, c.name) for c in r.__table__.columns}
                for k, v in list(record.items()):
                    if hasattr(v, "isoformat"):
                        record[k] = v.isoformat()
                f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
                count += 1
    finally:
        db.close()

    print(f"[export] wrote {count} rows to {args.out} (market={args.market}, table={args.table})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
