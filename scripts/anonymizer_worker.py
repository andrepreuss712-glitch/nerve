"""
anonymizer_worker.py — DSGVO Cross-Wall Anonymizer Cron (Phase 08.23.2.G-MEET Wave 3, D-15/D-16)

Standalone cron worker. The ONLY component that connects as DB-role `nerve_anon_worker` (D-16 —
the single role that sees BOTH walls: it reads cleartext crm material and writes anonymized
training material). It is out-of-process: if it is not scheduled, NOTHING in the app breaks
(Wave 3 is independently deployable, D-02).

VARIANTE A state-tracking (RESEARCH §4): the worker SELECTs `crm.account_memory` rows WHERE
`anonymized_at IS NULL`, anonymizes the associated call transcript material, writes it to
`training.transcript_archive`, and stamps `crm.account_memory.anonymized_at = now()`. A second run
selects nothing (idempotent — the stamp took).

⚠ W-6 SCOPE BOUNDARY (explicit, NOT a silent reduction): this worker writes
`training.transcript_archive` (the existing 0008 raw anonymized-segment sink) and stamps
`anonymized_at`. It does NOT write `training.preference_pairs`. The prompt/chosen/rejected
DPO-triple mapping is owned by Phase 08.23.2.E (the DPO consumer) and is not yet specified;
emitting triples now would produce structurally-valid-but-empty pairs (a silent D-15 reduction).
preference_pairs exists (migration 0013) with this role's INSERT grant already provisioned, so
Phase E can populate it without a new migration.

is_test_user FILTER (CLAUDE.md Pre-Launch Sandbox mandate): calls whose owning user has
is_test_user=true are SKIPPED — no test data poisons the training foundation.

RLS RESOLUTION (PINNED — see migration 0013, NOT resolved empirically here):
  nerve_anon_worker reads + stamps crm under FORCE ROW LEVEL SECURITY as a NON-OWNER without
  BYPASSRLS (rolbypassrls=f, PROVEN) and sets NO `app.tenant_id`. The crm `tenant_isolation`
  policy (migration 0012, nullif fail-closed form) is PERMISSIVE with NO TO/FOR clause, so it
  applies to this worker too; with no app.tenant_id its predicate is NULL -> FALSE -> it would
  SELECT 0 rows AND its anonymized_at-stamp UPDATE would be blocked. This is RESOLVED in migration
  0013 by two role-targeted PERMISSIVE policies on crm.account_memory: `anon_worker_read`
  (FOR SELECT TO nerve_anon_worker USING true) and `anon_worker_stamp` (FOR UPDATE TO
  nerve_anon_worker USING/CHECK true). PERMISSIVE policies combine with OR, so this worker's row
  set becomes all rows CROSS-TENANT (D-16, by design — the sole role seeing both walls). The worker
  therefore deliberately sets NO app.tenant_id and relies on these policies. nerve_app is NOT in
  the policies' TO list, so app reads stay tenant-scoped (no leak). The column-level
  GRANT UPDATE (anonymized_at) (0013) still confines this worker's write to the single anonymized_at
  column even though anon_worker_stamp's WITH CHECK is `true` — it cannot mutate cleartext.

NO raw crm ids cross the wall (D-17): `source_call_hash` is a one-way SHA-256 hash of the call id,
never the raw id, and there is no crm<->training foreign key.

Run:  python scripts/anonymizer_worker.py [--dry-run]
Env:  ANON_WORKER_DATABASE_URL  (postgresql DSN connecting as nerve_anon_worker — NOT the app's
      nerve_app engine; see .env.example). This worker MUST NOT reuse database/db.py's engine.
"""
import os
import sys
import hashlib
from datetime import datetime, timezone

from dotenv import load_dotenv
from sqlalchemy import create_engine, text, bindparam

# Pure functions (lazy NLP load happens only on the first real anonymize() call).
from services.anonymization import anonymize, should_persist

load_dotenv()

ANON_WORKER_DATABASE_URL = os.environ.get('ANON_WORKER_DATABASE_URL', '')
DRY_RUN = '--dry-run' in sys.argv


def _hash_call_id(call_id) -> str:
    """One-way SHA-256 of the call id. NEVER store the raw crm/call id in training (D-17)."""
    return hashlib.sha256(str(call_id).encode('utf-8')).hexdigest()


def _source_calls_for(conn, account_id, contact_id):
    """Resolve the source calls linked to an account_memory row via the calls.account_id /
    calls.contact_id soft links, joined to users for the is_test_user flag.

    Returns rows of (call_id, conversation_log_id, is_test_user).
    """
    return conn.execute(
        text(
            """
            SELECT c.id, c.conversation_log_id, u.is_test_user
            FROM calls c
            JOIN users u ON u.id = c.user_id
            WHERE (:acc IS NOT NULL AND c.account_id = :acc)
               OR (:con IS NOT NULL AND c.contact_id = :con)
            """
        ),
        {'acc': account_id, 'con': contact_id},
    ).fetchall()


def process_unstamped(conn, dry_run=False, anonymize_fn=None, should_persist_fn=None,
                      limit_ids=None):
    """Core Variante-A loop. Operates on the given SQLAlchemy Connection; the CALLER commits.

    For each crm.account_memory row with anonymized_at IS NULL (selected CROSS-TENANT via the
    0013 anon_worker_read policy), resolve its source calls, drop is_test_user calls, anonymize the
    remaining calls' transcript segments into training.transcript_archive, and stamp anonymized_at.

    A per-row SAVEPOINT isolates failures: one bad record logs [ANON] and is skipped without
    aborting the batch (CLAUDE.md error-swallow for non-critical paths).

    `anonymize_fn`/`should_persist_fn` are injectable for testing (so the logic group never loads
    the heavy NLP pipeline). `limit_ids` is a TEST-ONLY scoping seam: when set, the worker restricts
    its scan to those account_memory ids so the real-PG RLS test touches ONLY its own seeded rows
    (zero blast radius on Production). Production runs pass limit_ids=None (full scan).

    Returns a stats dict.
    """
    anonymize_fn = anonymize_fn or anonymize
    should_persist_fn = should_persist_fn or should_persist

    stats = {
        'candidates': 0, 'archived_segments': 0, 'stamped': 0,
        'skipped_test_user': 0, 'errors': 0,
    }
    stamp_ts = datetime.now(timezone.utc)

    base_sql = "SELECT id, account_id, contact_id FROM crm.account_memory WHERE anonymized_at IS NULL"
    if limit_ids:
        stmt = text(base_sql + " AND id IN :ids").bindparams(bindparam('ids', expanding=True))
        rows = conn.execute(stmt, {'ids': list(limit_ids)}).fetchall()
    else:
        rows = conn.execute(text(base_sql)).fetchall()
    stats['candidates'] = len(rows)
    print(f"[ANON] {stats['candidates']} unstamped account_memory row(s) (cross-tenant)"
          f"{' [DRY-RUN]' if dry_run else ''}")

    for row in rows:
        mem_id, account_id, contact_id = row[0], row[1], row[2]
        try:
            with conn.begin_nested():  # SAVEPOINT — per-record isolation
                calls = _source_calls_for(conn, account_id, contact_id)
                for call_id, conv_log_id, is_test in calls:
                    if is_test:
                        stats['skipped_test_user'] += 1
                        continue  # no test-user data into the training foundation (CLAUDE.md)
                    if conv_log_id is None:
                        continue
                    src_hash = _hash_call_id(call_id)  # one-way hash, never the raw id (D-17)
                    segs = conn.execute(
                        text(
                            "SELECT ts_ms, speaker, text FROM transcript_segments "
                            "WHERE conversation_log_id = :clid ORDER BY ts_ms, id"
                        ),
                        {'clid': conv_log_id},
                    ).fetchall()
                    seg_index = 0
                    for ts_ms, speaker, seg_text in segs:
                        anon_text, _tier = anonymize_fn(seg_text, None)
                        if not should_persist_fn(anon_text):
                            continue  # drop [ART9_REDACTED] / [ANON_FEHLER]
                        if not dry_run:
                            conn.execute(
                                text(
                                    "INSERT INTO training.transcript_archive "
                                    "(source_call_hash, segment_index, speaker, text, ts_offset_ms, schema_version) "
                                    "VALUES (:h, :idx, :sp, :tx, :off, 1)"
                                ),
                                {'h': src_hash, 'idx': seg_index, 'sp': speaker,
                                 'tx': anon_text, 'off': ts_ms},
                            )
                        seg_index += 1
                        stats['archived_segments'] += 1
                # Variante A stamp — relies on the 0013 column-level UPDATE grant + anon_worker_stamp
                # policy to pass FORCE RLS. Python-side timestamp (portable; no SQL now()).
                if not dry_run:
                    conn.execute(
                        text("UPDATE crm.account_memory SET anonymized_at = :ts WHERE id = :id"),
                        {'ts': stamp_ts, 'id': mem_id},
                    )
                    stats['stamped'] += 1
        except Exception as e:  # per-record isolation — never abort the whole run
            stats['errors'] += 1
            print(f"[ANON] Fehler bei account_memory {mem_id}: {type(e).__name__}: {e}")
            continue

    print(f"[ANON] fertig: {stats['archived_segments']} Segment(e) archiviert, "
          f"{stats['stamped']} Row(s) gestempelt, {stats['skipped_test_user']} Test-User-Call(s) "
          f"uebersprungen, {stats['errors']} Fehler.")
    return stats


def main() -> None:
    if not ANON_WORKER_DATABASE_URL.startswith('postgresql'):
        print("[ANON] FEHLER: ANON_WORKER_DATABASE_URL muss eine postgresql:// DSN sein "
              "(Rolle nerve_anon_worker — NICHT die nerve_app-Engine). Siehe .env.example.")
        sys.exit(1)

    engine = create_engine(ANON_WORKER_DATABASE_URL)
    try:
        with engine.connect() as conn:
            stats = process_unstamped(conn, dry_run=DRY_RUN)
            if not DRY_RUN:
                conn.commit()
    finally:
        engine.dispose()

    if DRY_RUN:
        print("[ANON] --dry-run: keine Schreibvorgaenge ausgefuehrt.")


if __name__ == '__main__':
    main()
