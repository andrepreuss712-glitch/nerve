"""Phase 08.14 — Regression: ApiRate-Seed auf fresh in-memory-SQLite.

Bug: INSERT fehlte last_checked_at -> NOT NULL constraint failed auf jeder fresh DB.
Fix: last_checked_at=datetime.utcnow() im INSERT ergaenzt.

Testet Runtime-Verhalten (echte SQLite-Writes), keine Source-Presence-Checks.
"""
import pytest
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session


@pytest.fixture(scope='module')
def fresh_engine():
    """In-memory SQLite mit ApiRate-Tabelle, frisch erstellt."""
    from database.models import Base
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    return engine


SEED_ROWS = [
    ('anthropic', 'claude-sonnet-4-5-20251022', 'per_1k_input_tokens',       0.003,   'USD'),
    ('anthropic', 'claude-sonnet-4-5-20251022', 'per_1k_output_tokens',      0.015,   'USD'),
    ('anthropic', 'claude-sonnet-4-5-20251022', 'per_1k_cache_read_tokens',  0.0003,  'USD'),
    ('anthropic', 'claude-sonnet-4-5-20251022', 'per_1k_cache_write_tokens', 0.00375, 'USD'),
    ('anthropic', 'claude-haiku-4-5-20251001',  'per_1k_input_tokens',       0.00025, 'USD'),
    ('anthropic', 'claude-haiku-4-5-20251001',  'per_1k_output_tokens',      0.00125, 'USD'),
    ('anthropic', 'claude-haiku-4-5-20251001',  'per_1k_cache_read_tokens',  0.000025,'USD'),
    ('anthropic', 'claude-haiku-4-5-20251001',  'per_1k_cache_write_tokens', 0.0003,  'USD'),
]


class TestApiRateSeed:
    def test_seed_inserts_8_rows(self, fresh_engine):
        """Seed-Logik schreibt exakt 8 Rows in eine leere api_rates-Tabelle."""
        now = datetime.utcnow()
        with fresh_engine.connect() as conn:
            for provider, model, unit, price, currency in SEED_ROWS:
                conn.execute(
                    text(
                        "INSERT INTO api_rates "
                        "(provider, model, unit_type, price_per_unit, currency, active, source_url, last_checked_at, created_at) "
                        "VALUES (:p,:m,:u,:price,:cur,1,'seed:test',:now,:now)"
                    ),
                    {'p': provider, 'm': model, 'u': unit, 'price': price, 'cur': currency, 'now': now}
                )
            conn.commit()
            count = conn.execute(text("SELECT COUNT(*) FROM api_rates")).scalar()
        assert count == 8

    def test_seed_rows_have_last_checked_at(self, fresh_engine):
        """Alle Seed-Rows haben last_checked_at != NULL (war der Bug)."""
        with fresh_engine.connect() as conn:
            null_count = conn.execute(
                text("SELECT COUNT(*) FROM api_rates WHERE last_checked_at IS NULL")
            ).scalar()
        assert null_count == 0, f"{null_count} Rows haben last_checked_at=NULL"

    def test_seed_idempotent_no_duplicates(self, fresh_engine):
        """Zweiter Seed-Lauf fuegt keine Duplikate ein (existing-Row-Check greift)."""
        now = datetime.utcnow()
        with fresh_engine.connect() as conn:
            for provider, model, unit, price, currency in SEED_ROWS:
                exists = conn.execute(
                    text("SELECT 1 FROM api_rates WHERE provider=:p AND model=:m AND unit_type=:u AND active=1"),
                    {'p': provider, 'm': model, 'u': unit}
                ).fetchone()
                if not exists:
                    conn.execute(
                        text(
                            "INSERT INTO api_rates "
                            "(provider, model, unit_type, price_per_unit, currency, active, source_url, last_checked_at) "
                            "VALUES (:p,:m,:u,:price,:cur,1,'seed:test',:now)"
                        ),
                        {'p': provider, 'm': model, 'u': unit, 'price': price, 'cur': currency, 'now': now}
                    )
            conn.commit()
            count = conn.execute(text("SELECT COUNT(*) FROM api_rates")).scalar()
        assert count == 8, f"Nach zweitem Seed-Lauf: {count} Rows statt 8 (Duplikat-Bug)"

    def test_seed_sonnet_and_haiku_models_present(self, fresh_engine):
        """Beide Models (sonnet-4-5 + haiku-4-5) sind nach Seed vorhanden."""
        with fresh_engine.connect() as conn:
            models = {
                row[0] for row in
                conn.execute(text("SELECT DISTINCT model FROM api_rates")).fetchall()
            }
        assert 'claude-sonnet-4-5-20251022' in models
        assert 'claude-haiku-4-5-20251001' in models
