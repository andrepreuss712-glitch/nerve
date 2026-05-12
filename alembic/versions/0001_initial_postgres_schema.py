"""initial_postgres_schema

Revision ID: 0001
Revises:
Create Date: 2026-05-12

NOTE: This file was created MANUALLY because Postgres 16 is not yet installed
on this machine. Once Postgres is available, this file should be verified
(and optionally regenerated via `alembic revision --autogenerate` against an
empty `nerve_test` DB) to confirm the schema matches models.py exactly.

The manual creation was necessary per the plan fallback instructions:
  - Plan 08.23.2.A-06, Task 1: Postgres NOT available → create manually
  - Must be verified/regenerated once Postgres is available
  - All 35 tables captured (33 legacy + calls + call_events)
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── organisations ─────────────────────────────────────────────────────────
    op.create_table(
        'organisations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('plan', sa.String(length=50), nullable=True),
        sa.Column('max_users', sa.Integer(), nullable=True),
        sa.Column('billing_email', sa.String(length=200), nullable=True),
        sa.Column('aktiv', sa.Boolean(), nullable=True),
        sa.Column('erstellt_am', sa.DateTime(), nullable=True),
        sa.Column('naechste_abrechnung', sa.DateTime(), nullable=True),
        sa.Column('trial_starts_at', sa.DateTime(), nullable=True),
        sa.Column('coach_id', sa.Integer(), nullable=True),
        sa.Column('dsgvo_modus', sa.Boolean(), nullable=True),
        sa.Column('plan_typ', sa.String(length=50), nullable=True),
        sa.Column('training_free_calls', sa.Integer(), nullable=True),
        sa.Column('live_free_trainings', sa.Integer(), nullable=True),
        sa.Column('billing_name', sa.String(length=200), nullable=True),
        sa.Column('billing_street', sa.String(length=200), nullable=True),
        sa.Column('billing_zip', sa.String(length=20), nullable=True),
        sa.Column('billing_city', sa.String(length=100), nullable=True),
        sa.Column('billing_country', sa.String(length=100), nullable=True),
        sa.Column('billing_vat_id', sa.String(length=50), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(), nullable=True),
        sa.Column('cancel_reason', sa.Text(), nullable=True),
        sa.Column('cancel_feedback', sa.Text(), nullable=True),
        sa.Column('is_early_access', sa.Boolean(), nullable=True),
        sa.Column('early_access_discount', sa.Integer(), nullable=True),
        sa.Column('minuten_limit', sa.Integer(), nullable=True),
        sa.Column('training_voice_limit', sa.Integer(), nullable=True),
        sa.Column('plan_preis', sa.Integer(), nullable=True),
        sa.Column('live_minutes_used', sa.Integer(), nullable=True),
        sa.Column('training_sessions_used', sa.Integer(), nullable=True),
        sa.Column('fair_use_reset_month', sa.String(length=7), nullable=True),
        sa.Column('stripe_customer_id', sa.String(length=100), nullable=True),
        sa.Column('stripe_subscription_id', sa.String(length=100), nullable=True),
        sa.Column('stripe_price_id', sa.String(length=100), nullable=True),
        sa.Column('subscription_status', sa.String(length=50), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── users ─────────────────────────────────────────────────────────────────
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=200), nullable=False),
        sa.Column('passwort_hash', sa.String(length=256), nullable=True),
        sa.Column('rolle', sa.String(length=50), nullable=True),
        sa.Column('is_superadmin', sa.Boolean(), nullable=False),
        sa.Column('aktiv', sa.Boolean(), nullable=True),
        sa.Column('erstellt_am', sa.DateTime(), nullable=True),
        sa.Column('active_profile_id', sa.Integer(), nullable=True),
        sa.Column('letzte_aktivitaet', sa.DateTime(), nullable=True),
        sa.Column('trial_ends_at', sa.DateTime(), nullable=True),
        sa.Column('is_trial', sa.Boolean(), nullable=True),
        sa.Column('is_coach', sa.Boolean(), nullable=True),
        sa.Column('vorname', sa.String(length=100), nullable=True),
        sa.Column('nachname', sa.String(length=100), nullable=True),
        sa.Column('onboarding_done', sa.Boolean(), nullable=True),
        sa.Column('erfahrungslevel', sa.String(length=50), nullable=True),
        sa.Column('schmerzpunkt', sa.Text(), nullable=True),
        sa.Column('persoenlich', sa.Text(), nullable=True),
        sa.Column('streak_count', sa.Integer(), nullable=True),
        sa.Column('streak_last_date', sa.Date(), nullable=True),
        sa.Column('total_points', sa.Integer(), nullable=True),
        sa.Column('level', sa.String(length=50), nullable=True),
        sa.Column('nudge_dismissed', sa.Text(), nullable=True),
        sa.Column('live_calls_used', sa.Integer(), nullable=True),
        sa.Column('trainings_used', sa.Integer(), nullable=True),
        sa.Column('notif_training_reminder', sa.Boolean(), nullable=True),
        sa.Column('notif_streak_warning', sa.Boolean(), nullable=True),
        sa.Column('notif_achievements', sa.Boolean(), nullable=True),
        sa.Column('notif_coach', sa.Boolean(), nullable=True),
        sa.Column('notif_nudges', sa.Boolean(), nullable=True),
        sa.Column('dashboard_stil', sa.Text(), nullable=True),
        sa.Column('last_seen_changelog', sa.String(length=20), nullable=True),
        sa.Column('dashboard_style', sa.String(length=20), nullable=True),
        sa.Column('minuten_used', sa.Integer(), nullable=True),
        sa.Column('trainings_voice_used', sa.Integer(), nullable=True),
        sa.Column('usage_reset_date', sa.Date(), nullable=True),
        sa.Column('preferred_language', sa.String(length=10), nullable=True),
        sa.Column('preferred_theme', sa.String(length=10), nullable=True),
        sa.Column('weekly_goal', sa.Integer(), nullable=True),
        sa.Column('pending_training_recommendation', sa.Text(), nullable=True),
        sa.Column('avg_deal_wert', sa.Integer(), nullable=True),
        sa.Column('oauth_provider', sa.String(length=50), nullable=True),
        sa.Column('oauth_id', sa.String(length=200), nullable=True),
        sa.Column('avatar_url', sa.String(length=500), nullable=True),
        sa.Column('email_confirmed', sa.Boolean(), nullable=True),
        sa.Column('market', sa.String(length=10), nullable=False),
        sa.Column('language', sa.String(length=10), nullable=False),
        sa.ForeignKeyConstraint(['active_profile_id'], ['profiles.id']),
        sa.ForeignKeyConstraint(['org_id'], ['organisations.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
    )

    # ── profiles ──────────────────────────────────────────────────────────────
    op.create_table(
        'profiles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('branche', sa.String(length=200), nullable=True),
        sa.Column('daten', sa.Text(), nullable=True),
        sa.Column('erstellt_von', sa.Integer(), nullable=True),
        sa.Column('erstellt_am', sa.DateTime(), nullable=True),
        sa.Column('aktualisiert_am', sa.DateTime(), nullable=True),
        sa.Column('consent_text', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['erstellt_von'], ['users.id']),
        sa.ForeignKeyConstraint(['org_id'], ['organisations.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── profile_skripte ───────────────────────────────────────────────────────
    op.create_table(
        'profile_skripte',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('profile_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('inhalt', sa.Text(), nullable=True),
        sa.Column('sortierung', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('parent_id', sa.Integer(), nullable=True),
        sa.Column('is_personalized', sa.Boolean(), nullable=False),
        sa.Column('briefing_source_firma', sa.String(length=200), nullable=True),
        sa.ForeignKeyConstraint(['profile_id'], ['profiles.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── profile_faqs ──────────────────────────────────────────────────────────
    op.create_table(
        'profile_faqs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('profile_id', sa.Integer(), nullable=False),
        sa.Column('frage_muster', sa.Text(), nullable=False),
        sa.Column('antwort', sa.Text(), nullable=False),
        sa.Column('kategorie', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('used_count', sa.Integer(), nullable=False),
        sa.Column('mode', sa.String(length=20), nullable=False),
        sa.ForeignKeyConstraint(['profile_id'], ['profiles.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── profile_opener ────────────────────────────────────────────────────────
    op.create_table(
        'profile_opener',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('profile_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('inhalt', sa.Text(), nullable=True),
        sa.Column('sortierung', sa.Integer(), nullable=True),
        sa.Column('type', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('parent_id', sa.Integer(), nullable=True),
        sa.Column('is_personalized', sa.Boolean(), nullable=False),
        sa.Column('briefing_source_firma', sa.String(length=200), nullable=True),
        sa.ForeignKeyConstraint(['parent_id'], ['profile_opener.id']),
        sa.ForeignKeyConstraint(['profile_id'], ['profiles.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── sessions ──────────────────────────────────────────────────────────────
    op.create_table(
        'sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('token', sa.String(length=256), nullable=False),
        sa.Column('erstellt_am', sa.DateTime(), nullable=True),
        sa.Column('ablauf_am', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token'),
    )

    # ── invitations ───────────────────────────────────────────────────────────
    op.create_table(
        'invitations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=200), nullable=False),
        sa.Column('token', sa.String(length=256), nullable=False),
        sa.Column('erstellt_am', sa.DateTime(), nullable=True),
        sa.Column('verwendet', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['org_id'], ['organisations.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token'),
    )

    # ── billing_events ────────────────────────────────────────────────────────
    op.create_table(
        'billing_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column('typ', sa.String(length=100), nullable=True),
        sa.Column('betrag', sa.Float(), nullable=True),
        sa.Column('beschreibung', sa.Text(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=True),
        sa.Column('stripe_event_id', sa.String(length=200), nullable=True),
        sa.ForeignKeyConstraint(['org_id'], ['organisations.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('stripe_event_id'),
    )

    # ── feedback_events ───────────────────────────────────────────────────────
    op.create_table(
        'feedback_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('session_log_id', sa.String(length=200), nullable=True),
        sa.Column('stars', sa.Integer(), nullable=True),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── coach_assignments ─────────────────────────────────────────────────────
    op.create_table(
        'coach_assignments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('coach_id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column('erstellt_am', sa.DateTime(), nullable=True),
        sa.Column('aktiv', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['coach_id'], ['users.id']),
        sa.ForeignKeyConstraint(['org_id'], ['organisations.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── training_scenarios ────────────────────────────────────────────────────
    op.create_table(
        'training_scenarios',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('beschreibung', sa.Text(), nullable=True),
        sa.Column('kunde_situation', sa.Text(), nullable=True),
        sa.Column('kunde_verhalten', sa.Text(), nullable=True),
        sa.Column('spezial_einwaende', sa.Text(), nullable=True),
        sa.Column('schwierigkeit', sa.String(length=50), nullable=True),
        sa.Column('erstellt_von', sa.Integer(), nullable=True),
        sa.Column('erstellt_am', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['erstellt_von'], ['users.id']),
        sa.ForeignKeyConstraint(['org_id'], ['organisations.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── personality_types ─────────────────────────────────────────────────────
    op.create_table(
        'personality_types',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('org_id', sa.Integer(), nullable=True),
        sa.Column('is_custom', sa.Boolean(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('icon', sa.String(length=10), nullable=True),
        sa.Column('kurzbeschreibung', sa.String(length=300), nullable=True),
        sa.Column('attribute', sa.Text(), nullable=False),
        sa.Column('kommentar', sa.Text(), nullable=True),
        sa.Column('erstellt_am', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['org_id'], ['organisations.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── conversation_logs ─────────────────────────────────────────────────────
    op.create_table(
        'conversation_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column('profile_id', sa.Integer(), nullable=True),
        sa.Column('profile_name', sa.String(length=200), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('ended_at', sa.DateTime(), nullable=True),
        sa.Column('dauer_sekunden', sa.Integer(), nullable=True),
        sa.Column('segmente_gesamt', sa.Integer(), nullable=True),
        sa.Column('einwaende_gesamt', sa.Integer(), nullable=True),
        sa.Column('einwaende_behandelt', sa.Integer(), nullable=True),
        sa.Column('einwaende_fehlgeschlagen', sa.Integer(), nullable=True),
        sa.Column('einwaende_ignoriert', sa.Integer(), nullable=True),
        sa.Column('vorwaende_erkannt', sa.Integer(), nullable=True),
        sa.Column('kb_start', sa.Integer(), nullable=True),
        sa.Column('kb_end', sa.Integer(), nullable=True),
        sa.Column('kb_min', sa.Integer(), nullable=True),
        sa.Column('kb_max', sa.Integer(), nullable=True),
        sa.Column('redeanteil_avg', sa.Integer(), nullable=True),
        sa.Column('tempo_avg', sa.Integer(), nullable=True),
        sa.Column('laengster_monolog', sa.Float(), nullable=True),
        sa.Column('hilfe_genutzt', sa.Integer(), nullable=True),
        sa.Column('quick_actions', sa.Integer(), nullable=True),
        sa.Column('skript_abdeckung', sa.Integer(), nullable=True),
        sa.Column('sterne', sa.Integer(), nullable=True),
        sa.Column('kommentar', sa.Text(), nullable=True),
        sa.Column('gegenargument_details', sa.Text(), nullable=True),
        sa.Column('painpoints_details', sa.Text(), nullable=True),
        sa.Column('phasen_details', sa.Text(), nullable=True),
        sa.Column('typ', sa.String(length=20), nullable=True),
        sa.Column('session_mode', sa.String(length=20), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('result', sa.String(length=20), nullable=True),
        sa.Column('market', sa.String(length=10), nullable=False),
        sa.Column('language', sa.String(length=10), nullable=False),
        sa.Column('personality_type_id', sa.Integer(), nullable=True),
        sa.Column('stimmung_history', sa.Text(), nullable=True),
        sa.Column('precall_briefing', sa.Text(), nullable=True),
        sa.Column('precall_fields', sa.Text(), nullable=True),
        sa.Column('kb_verlauf', sa.Text(), nullable=True),
        sa.Column('anrede', sa.String(length=10), nullable=True),
        sa.ForeignKeyConstraint(['org_id'], ['organisations.id']),
        sa.ForeignKeyConstraint(['personality_type_id'], ['personality_types.id']),
        sa.ForeignKeyConstraint(['profile_id'], ['profiles.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── phrases ───────────────────────────────────────────────────────────────
    op.create_table(
        'phrases',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=True),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('objection_type', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['conversation_logs.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── waitlist ──────────────────────────────────────────────────────────────
    op.create_table(
        'waitlist',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=200), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=True),
        sa.Column('firma', sa.String(length=200), nullable=True),
        sa.Column('rolle', sa.String(length=100), nullable=True),
        sa.Column('branche', sa.String(length=100), nullable=True),
        sa.Column('nachricht', sa.Text(), nullable=True),
        sa.Column('position', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.Column('invited_at', sa.DateTime(), nullable=True),
        sa.Column('registered_at', sa.DateTime(), nullable=True),
        sa.Column('referral_code', sa.String(length=50), nullable=True),
        sa.Column('referred_by', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
    )

    # ── changelog ─────────────────────────────────────────────────────────────
    op.create_table(
        'changelog',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('version', sa.String(length=20), nullable=False),
        sa.Column('titel', sa.String(length=300), nullable=False),
        sa.Column('inhalt', sa.Text(), nullable=False),
        sa.Column('typ', sa.String(length=50), nullable=True),
        sa.Column('bekannte_bugs', sa.Text(), nullable=True),
        sa.Column('veroeffentlicht', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── audit_log ─────────────────────────────────────────────────────────────
    op.create_table(
        'audit_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('org_id', sa.Integer(), nullable=True),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('target_type', sa.String(length=100), nullable=True),
        sa.Column('target_id', sa.Integer(), nullable=True),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('ip_address', sa.String(length=64), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organisations.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── objection_events ──────────────────────────────────────────────────────
    op.create_table(
        'objection_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=True),
        sa.Column('conversation_log_id', sa.Integer(), nullable=False),
        sa.Column('einwand_typ', sa.String(length=100), nullable=False),
        sa.Column('success', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('antwort_text', sa.Text(), nullable=True),
        sa.Column('einwand_text', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['conversation_log_id'], ['conversation_logs.id']),
        sa.ForeignKeyConstraint(['org_id'], ['organisations.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── ewb_ratings ───────────────────────────────────────────────────────────
    op.create_table(
        'ewb_ratings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('conversation_log_id', sa.Integer(), nullable=False),
        sa.Column('einwand_typ_key', sa.String(length=100), nullable=False),
        sa.Column('klingt_wie_mensch', sa.Boolean(), nullable=False),
        sa.Column('keine_halluzination', sa.Boolean(), nullable=False),
        sa.Column('trifft_einwand', sa.Boolean(), nullable=False),
        sa.Column('rater_id', sa.Integer(), nullable=False),
        sa.Column('rated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['conversation_log_id'], ['conversation_logs.id']),
        sa.ForeignKeyConstraint(['rater_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('conversation_log_id', 'einwand_typ_key',
                            name='uq_ewb_rating_per_conv_ewb'),
    )

    # ── feedback ──────────────────────────────────────────────────────────────
    op.create_table(
        'feedback',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=True),
        sa.Column('typ', sa.String(length=50), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('screenshot_path', sa.String(length=300), nullable=True),
        sa.Column('context_url', sa.String(length=500), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('kategorie', sa.String(length=50), nullable=True),
        sa.Column('rating', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('notification_sent', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organisations.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── planning_feedback_link ────────────────────────────────────────────────
    op.create_table(
        'planning_feedback_link',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('feedback_id', sa.Integer(), nullable=False),
        sa.Column('planning_title', sa.String(length=200), nullable=False),
        sa.Column('planning_status', sa.String(length=40), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['feedback_id'], ['feedback.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── prompt_versions ───────────────────────────────────────────────────────
    op.create_table(
        'prompt_versions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('version', sa.String(length=50), nullable=False),
        sa.Column('module', sa.String(length=50), nullable=False),
        sa.Column('prompt_text', sa.Text(), nullable=False),
        sa.Column('changelog', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('is_default', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('version', 'module', name='uq_prompt_version_module'),
    )

    # ── api_cost_log ──────────────────────────────────────────────────────────
    op.create_table(
        'api_cost_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, index=True),
        sa.Column('provider', sa.String(length=32), nullable=False, index=True),
        sa.Column('model', sa.String(length=64), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True, index=True),
        sa.Column('org_id', sa.Integer(), nullable=True, index=True),
        sa.Column('units', sa.Numeric(14, 4), nullable=False),
        sa.Column('unit_type', sa.String(length=32), nullable=False),
        sa.Column('rate_applied', sa.Numeric(12, 8), nullable=False),
        sa.Column('rate_currency', sa.String(length=3), nullable=False),
        sa.Column('fx_rate_applied', sa.Numeric(10, 6), nullable=False),
        sa.Column('cost_eur', sa.Numeric(12, 6), nullable=False),
        sa.Column('session_id', sa.String(length=64), nullable=True, index=True),
        sa.Column('context_tag', sa.String(length=32), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('call_site', sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(['org_id'], ['organisations.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── api_rates ─────────────────────────────────────────────────────────────
    op.create_table(
        'api_rates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('provider', sa.String(length=32), nullable=False, index=True),
        sa.Column('model', sa.String(length=64), nullable=False),
        sa.Column('unit_type', sa.String(length=32), nullable=False),
        sa.Column('price_per_unit', sa.Numeric(12, 8), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('last_checked_at', sa.DateTime(), nullable=False),
        sa.Column('source_url', sa.String(length=512), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('provider', 'model', 'unit_type', 'active',
                            name='uix_api_rate_active'),
    )

    # ── price_change_log ──────────────────────────────────────────────────────
    op.create_table(
        'price_change_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('api_rate_id', sa.Integer(), nullable=False),
        sa.Column('changed_at', sa.DateTime(), nullable=False, index=True),
        sa.Column('old_rate', sa.Numeric(12, 8), nullable=False),
        sa.Column('new_rate', sa.Numeric(12, 8), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False),
        sa.Column('impact_eur_per_month', sa.Numeric(12, 2), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['api_rate_id'], ['api_rates.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── fixed_costs ───────────────────────────────────────────────────────────
    op.create_table(
        'fixed_costs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('amount_eur', sa.Numeric(12, 2), nullable=False),
        sa.Column('vat_rate', sa.Numeric(4, 2), nullable=False),
        sa.Column('cycle', sa.String(length=16), nullable=False),
        sa.Column('skr03', sa.String(length=8), nullable=True),
        sa.Column('eur_line', sa.Integer(), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── revenue_log ───────────────────────────────────────────────────────────
    op.create_table(
        'revenue_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('stripe_invoice_id', sa.String(length=128), nullable=False),
        sa.Column('stripe_customer_id', sa.String(length=128), nullable=True),
        sa.Column('org_id', sa.Integer(), nullable=True),
        sa.Column('paid_at', sa.DateTime(), nullable=False),
        sa.Column('netto_cents', sa.Integer(), nullable=False),
        sa.Column('ust_cents', sa.Integer(), nullable=False),
        sa.Column('brutto_cents', sa.Integer(), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False),
        sa.Column('country', sa.String(length=2), nullable=True),
        sa.Column('tax_treatment', sa.String(length=16), nullable=False),
        sa.Column('plan_key', sa.String(length=32), nullable=True),
        sa.Column('raw_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organisations.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('stripe_invoice_id'),
    )

    # ── exchange_rates ────────────────────────────────────────────────────────
    op.create_table(
        'exchange_rates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('currency_pair', sa.String(length=7), nullable=False),
        sa.Column('rate', sa.Numeric(10, 6), nullable=False),
        sa.Column('source', sa.String(length=16), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('date', 'currency_pair', name='uix_exchange_rate_date_pair'),
    )

    # ── learning_cards ────────────────────────────────────────────────────────
    op.create_table(
        'learning_cards',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('call_id', sa.Integer(), nullable=True),
        sa.Column('category', sa.String(length=100), nullable=False),
        sa.Column('original_suggestion', sa.Text(), nullable=False),
        sa.Column('final_text', sa.Text(), nullable=False),
        sa.Column('lernziel', sa.Text(), nullable=True),
        sa.Column('source', sa.String(length=20), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('applied_count', sa.Integer(), nullable=True),
        sa.Column('regenerate_count', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('learned_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['call_id'], ['conversation_logs.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── coaching_reports ──────────────────────────────────────────────────────
    op.create_table(
        'coaching_reports',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('period_start', sa.Date(), nullable=False),
        sa.Column('period_end', sa.Date(), nullable=False),
        sa.Column('calls_count', sa.Integer(), nullable=True),
        sa.Column('avg_readiness_score', sa.Float(), nullable=True),
        sa.Column('strongest_phase', sa.String(length=100), nullable=True),
        sa.Column('weakest_phase', sa.String(length=100), nullable=True),
        sa.Column('talk_ratio_user', sa.Float(), nullable=True),
        sa.Column('talk_ratio_customer', sa.Float(), nullable=True),
        sa.Column('report_text', sa.Text(), nullable=True),
        sa.Column('suggested_card_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── learning_events ───────────────────────────────────────────────────────
    op.create_table(
        'learning_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('source_module', sa.String(length=20), nullable=False),
        sa.Column('source_id', sa.Integer(), nullable=True),
        sa.Column('metadata', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── crm_notes ─────────────────────────────────────────────────────────────
    op.create_table(
        'crm_notes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('notiz', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id'),
    )

    # ── calls ─────────────────────────────────────────────────────────────────
    op.create_table(
        'calls',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('account_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('contact_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('call_mode', sa.Text(), nullable=False),
        sa.Column('call_type', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('transcript_storage', sa.Text(), nullable=True),
        sa.Column('transcript_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('call_summary', sa.Text(), nullable=True),
        sa.Column('outcome', sa.Text(), nullable=True),
        sa.Column('audio_health_score', sa.Float(), nullable=True),
        sa.Column('coaching_score', sa.Float(), nullable=True),
        sa.Column('meddpicc_extracted', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # calls indexes
    op.create_index('idx_calls_account_time', 'calls', ['account_id', 'started_at'])
    op.create_index('idx_calls_user_time', 'calls', ['user_id', 'started_at'])
    op.create_index(
        'idx_calls_mode_outcome', 'calls', ['call_mode', 'outcome'],
        postgresql_where=sa.text('outcome IS NOT NULL'),
    )

    # calls CHECK constraints (autogenerate typically misses dialect-specific constraints)
    op.execute("ALTER TABLE calls ADD CONSTRAINT ck_calls_call_mode CHECK (call_mode IN ('cold_call', 'meeting_consented'))")
    op.execute("ALTER TABLE calls ADD CONSTRAINT ck_calls_transcript_storage CHECK (transcript_storage IN ('none', 'ephemeral', 'consented_full'))")
    op.execute("ALTER TABLE calls ADD CONSTRAINT ck_calls_outcome CHECK (outcome IN ('meeting_booked', 'callback', 'no_interest', 'wrong_person', 'contract_signed', 'unknown') OR outcome IS NULL)")

    # ── call_events ───────────────────────────────────────────────────────────
    op.create_table(
        'call_events',
        sa.Column('id', sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column('call_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('event_type', sa.Text(), nullable=False),
        sa.Column('event_ts_ms', sa.BigInteger(), nullable=False),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['call_id'], ['calls.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    # call_events indexes
    op.create_index('idx_call_events_call_time', 'call_events', ['call_id', 'event_ts_ms'])
    op.create_index('idx_call_events_type', 'call_events', ['call_id', 'event_type'])
    op.create_index(
        'idx_call_events_payload_gin', 'call_events', ['payload'],
        postgresql_using='gin',
    )

    # call_events CHECK constraint
    op.execute("ALTER TABLE call_events ADD CONSTRAINT ck_call_events_event_type CHECK (event_type IN ('transcript_chunk', 'suggestion_shown', 'reaction', 'phase_change', 'audio_health', 'objection_detected', 'consent_optin'))")


def downgrade() -> None:
    # Drop in reverse dependency order
    op.execute("ALTER TABLE call_events DROP CONSTRAINT IF EXISTS ck_call_events_event_type")
    op.drop_index('idx_call_events_payload_gin', table_name='call_events')
    op.drop_index('idx_call_events_type', table_name='call_events')
    op.drop_index('idx_call_events_call_time', table_name='call_events')
    op.drop_table('call_events')

    op.execute("ALTER TABLE calls DROP CONSTRAINT IF EXISTS ck_calls_outcome")
    op.execute("ALTER TABLE calls DROP CONSTRAINT IF EXISTS ck_calls_transcript_storage")
    op.execute("ALTER TABLE calls DROP CONSTRAINT IF EXISTS ck_calls_call_mode")
    op.drop_index('idx_calls_mode_outcome', table_name='calls')
    op.drop_index('idx_calls_user_time', table_name='calls')
    op.drop_index('idx_calls_account_time', table_name='calls')
    op.drop_table('calls')

    op.drop_table('crm_notes')
    op.drop_table('learning_events')
    op.drop_table('coaching_reports')
    op.drop_table('learning_cards')
    op.drop_table('exchange_rates')
    op.drop_table('revenue_log')
    op.drop_table('fixed_costs')
    op.drop_table('price_change_log')
    op.drop_table('api_rates')
    op.drop_table('api_cost_log')
    op.drop_table('prompt_versions')
    op.drop_table('planning_feedback_link')
    op.drop_table('feedback')
    op.drop_table('ewb_ratings')
    op.drop_table('objection_events')
    op.drop_table('audit_log')
    op.drop_table('changelog')
    op.drop_table('waitlist')
    op.drop_table('phrases')
    op.drop_table('conversation_logs')
    op.drop_table('personality_types')
    op.drop_table('training_scenarios')
    op.drop_table('coach_assignments')
    op.drop_table('feedback_events')
    op.drop_table('billing_events')
    op.drop_table('invitations')
    op.drop_table('sessions')
    op.drop_table('profile_opener')
    op.drop_table('profile_faqs')
    op.drop_table('profile_skripte')
    op.drop_table('profiles')
    op.drop_table('users')
    op.drop_table('organisations')
