"""Phase 08 Plan 01 Task 2 — Migration blocks in app.py _migrate().

Tests the 5 migration blocks (A-E):
- Block A: Pre-Migration DB-Backup
- Block B: ObjectionEvent.success Nullable (Table-Rebuild)
- Block C: Alt-Daten-Reset POLISH-38.1 (D-02, destruktiv) + audit_log marker
- Block D: conversation_logs.anrede Column
- Block E: prompt_versions.is_default Column + Backfill

We verify migration-marker presence via grep in app.py source (stable, env-agnostic).
DB-PRAGMA tests require a live DB migration run — covered by source-level checks here
since the TDD gate is about the migration code itself, not a live DB run.
"""
import pytest
import os
import re

APP_PY = os.path.join(os.path.dirname(__file__), '..', 'app.py')


def _read_app():
    with open(APP_PY, 'r', encoding='utf-8') as f:
        return f.read()


def test_block_a_backup_present():
    src = _read_app()
    assert 'nerve.db.bak_pre_v08_01' in src, (
        "Block A missing: Pre-Migration DB-Backup (database/nerve.db.bak_pre_v08_01)"
    )
    assert 'shutil.copy' in src or 'shutil' in src, (
        "Block A must use shutil.copy to create backup"
    )


def test_block_b_table_rebuild_present():
    src = _read_app()
    assert 'Phase 08 D-01' in src, (
        "Block B missing: Phase 08 D-01 marker for objection_events.success rebuild"
    )
    assert 'CREATE TABLE objection_events_new' in src, (
        "Block B missing: Table-Rebuild SQL (CREATE TABLE objection_events_new)"
    )
    assert 'INSERT INTO objection_events_new SELECT' in src, (
        "Block B missing: INSERT SELECT for data migration"
    )
    assert 'ALTER TABLE objection_events_new RENAME TO objection_events' in src, (
        "Block B missing: RENAME step for Table-Rebuild"
    )


def test_block_c_reset_and_audit_marker_present():
    src = _read_app()
    assert 'Phase 08 D-02' in src, (
        "Block C missing: Phase 08 D-02 marker for POLISH-38.1 reset"
    )
    assert 'migration_v08_01_reset_success_polish38_1' in src, (
        "Block C missing: audit_log marker action string"
    )
    assert '2026-04-22 00:00:00' in src, (
        "Block C missing: hardcoded cutoff timestamp '2026-04-22 00:00:00'"
    )
    assert 'UPDATE objection_events SET success = NULL' in src, (
        "Block C missing: UPDATE objection_events SET success = NULL"
    )


def test_block_d_anrede_column_present():
    src = _read_app()
    assert 'Phase 08 D-14' in src, (
        "Block D missing: Phase 08 D-14 marker for conversation_logs.anrede"
    )
    # ADD COLUMN anrede VARCHAR(10) — via template pattern
    assert "'anrede'" in src and 'VARCHAR(10)' in src, (
        "Block D missing: anrede VARCHAR(10) column definition"
    )


def test_block_e_is_default_column_and_backfill():
    src = _read_app()
    assert 'Phase 08 D-26' in src, (
        "Block E missing: Phase 08 D-26 marker for prompt_versions.is_default"
    )
    assert 'ALTER TABLE prompt_versions ADD COLUMN is_default' in src, (
        "Block E missing: ALTER TABLE ADD COLUMN is_default"
    )
    assert 'UPDATE prompt_versions SET is_default = 1 WHERE is_active = 1' in src, (
        "Block E missing: backfill UPDATE is_default=1 WHERE is_active=1"
    )


def test_blocks_ordered_a_b_c_d_e():
    """Critical: Block A (Backup) MUST come before Block B (Rebuild) and C (Reset)."""
    src = _read_app()
    idx_a = src.find('nerve.db.bak_pre_v08_01')
    idx_b = src.find('Phase 08 D-01')
    idx_c = src.find('Phase 08 D-02')
    idx_d = src.find('Phase 08 D-14')
    idx_e = src.find('Phase 08 D-26')
    assert idx_a > 0 and idx_b > 0 and idx_c > 0 and idx_d > 0 and idx_e > 0, (
        f"One or more block markers missing. Positions: A={idx_a}, B={idx_b}, C={idx_c}, D={idx_d}, E={idx_e}"
    )
    assert idx_a < idx_b, f"Block A (Backup @{idx_a}) MUST precede Block B (Rebuild @{idx_b})"
    assert idx_b < idx_c, f"Block B (Rebuild @{idx_b}) MUST precede Block C (Reset @{idx_c})"
    assert idx_c < idx_d, f"Block C (Reset @{idx_c}) MUST precede Block D (anrede @{idx_d})"
    assert idx_d < idx_e, f"Block D (anrede @{idx_d}) MUST precede Block E (is_default @{idx_e})"
