from datetime import datetime, timezone, date
from sqlalchemy import Column, Integer, BigInteger, SmallInteger, String, Boolean, DateTime, Text, ForeignKey, Float, Date, UniqueConstraint, Numeric, CheckConstraint, Index, text, JSON, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid
from database.db import Base

# JSONB on Postgres (performance, indexing), JSON on SQLite (test compatibility).
# Phase 08.23.2.A: SQLite-in-memory tests need to create the schema, but SQLite
# doesn't know JSONB. JSON.with_variant(JSONB, "postgresql") gives us JSONB
# on Postgres and JSON (TEXT) on SQLite — both render correctly per dialect.
JSON_TYPE = JSON().with_variant(JSONB(), "postgresql")
UUID_TYPE = String(36).with_variant(UUID(as_uuid=True), "postgresql")


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Organisation(Base):
    __tablename__ = 'organisations'
    id                   = Column(Integer, primary_key=True)
    name                 = Column(String(200), nullable=False)
    plan                 = Column(String(50), default='starter')  # starter/team/business/enterprise
    max_users            = Column(Integer, default=5)
    billing_email        = Column(String(200))
    aktiv                = Column(Boolean, default=True)
    erstellt_am          = Column(DateTime, default=utcnow)
    naechste_abrechnung  = Column(DateTime)
    trial_starts_at      = Column(DateTime, nullable=True)
    coach_id             = Column(Integer, ForeignKey('users.id'), nullable=True)
    dsgvo_modus          = Column(Boolean, default=True)
    # Block 3: Modulares Pricing
    plan_typ             = Column(String(50), default='bundle')   # training/live/bundle/coach
    training_free_calls  = Column(Integer, default=5)
    live_free_trainings  = Column(Integer, default=3)
    # Block 4: Self-Service / Billing
    billing_name         = Column(String(200))
    billing_street       = Column(String(200))
    billing_zip          = Column(String(20))
    billing_city         = Column(String(100))
    billing_country      = Column(String(100), default='Deutschland')
    billing_vat_id       = Column(String(50))
    cancelled_at         = Column(DateTime)
    cancel_reason        = Column(Text)
    cancel_feedback      = Column(Text)
    # Block 5: Early Access
    is_early_access      = Column(Boolean, default=False)
    early_access_discount = Column(Integer, default=50)
    # Block 6: Flat-Rate Pricing
    minuten_limit        = Column(Integer, default=1000)   # Fair-Use pro User/Monat
    training_voice_limit = Column(Integer, default=50)     # TTS-Trainings pro User/Monat
    plan_preis           = Column(Integer, default=49)     # Euro/Monat Flat-Rate
    # Fair-Use Tracking (org-level, resets monthly)
    live_minutes_used      = Column(Integer, default=0)    # Live-Minuten verbraucht diesen Monat
    training_sessions_used = Column(Integer, default=0)    # Trainings gestartet diesen Monat
    fair_use_reset_month   = Column(String(7))             # e.g. '2026-04'
    # Block 7: Stripe Integration
    stripe_customer_id     = Column(String(100))
    stripe_subscription_id = Column(String(100))
    stripe_price_id        = Column(String(100))
    subscription_status    = Column(String(50), default='inactive')


class User(Base):
    __tablename__ = 'users'
    id                  = Column(Integer, primary_key=True)
    org_id              = Column(Integer, ForeignKey('organisations.id'), nullable=False)
    email               = Column(String(200), unique=True, nullable=False)
    passwort_hash       = Column(String(256), nullable=True)  # Phase 04.6.1: nullable für OAuth-User. SQLite Tabellen-NOT-NULL bleibt — OAuth-Flow setzt '' als Sentinel.
    rolle               = Column(String(50), default='member')  # owner/admin/member
    is_superadmin       = Column(Boolean, default=False, nullable=False)
    aktiv               = Column(Boolean, default=True)
    erstellt_am         = Column(DateTime, default=utcnow)
    active_profile_id   = Column(Integer, ForeignKey('profiles.id'), nullable=True)
    letzte_aktivitaet   = Column(DateTime, nullable=True)
    trial_ends_at       = Column(DateTime, nullable=True)
    is_trial            = Column(Boolean, default=False)
    is_coach            = Column(Boolean, default=False)
    is_test_user        = Column(Boolean, default=False, nullable=False)
    # Block 1: Onboarding
    vorname             = Column(String(100))
    nachname            = Column(String(100))
    onboarding_done     = Column(Boolean, default=False)
    erfahrungslevel     = Column(String(50))   # einsteiger/fortgeschritten/profi
    schmerzpunkt        = Column(Text)
    persoenlich         = Column(Text)
    # Block 2: Gamification
    streak_count        = Column(Integer, default=0)
    streak_last_date    = Column(Date)
    total_points        = Column(Integer, default=0)
    level               = Column(String(50), default='rookie')
    # Block 3: Pricing / Nudges
    nudge_dismissed     = Column(Text)         # JSON array
    live_calls_used     = Column(Integer, default=0)
    trainings_used      = Column(Integer, default=0)
    # Block 4: Notification prefs
    notif_training_reminder = Column(Boolean, default=True)
    notif_streak_warning    = Column(Boolean, default=True)
    notif_achievements      = Column(Boolean, default=True)
    notif_coach             = Column(Boolean, default=True)
    notif_nudges            = Column(Boolean, default=True)
    # Block 4: Dashboard style
    dashboard_stil      = Column(Text)
    # Block 6: Changelog
    last_seen_changelog = Column(String(20))
    # Block 8: Dashboard Layout Preference
    dashboard_style     = Column(String(20), default='vollstaendig')
    # Block 7: Flat-Rate Usage Tracking
    minuten_used          = Column(Integer, default=0)    # Diesen Monat verbrauchte Minuten
    trainings_voice_used  = Column(Integer, default=0)    # TTS-Trainings diesen Monat
    usage_reset_date      = Column(Date)
    # Block 9: Language Preference
    preferred_language    = Column(String(10), default='de')
    # Block 10: Theme Preference
    preferred_theme       = Column(String(10), default='dark')
    # Block 11: Training Analytics
    weekly_goal           = Column(Integer, default=5)
    # Block 7: Integration Engine
    pending_training_recommendation = Column(Text, nullable=True)  # JSON: {"einwand_typ": "...", "scenario_name": "...", "created_at": "..."}
    # Block 12: Sales Performance Calculator
    avg_deal_wert         = Column(Integer, nullable=True)   # Euro, NULL = nicht gesetzt
    # Block 13: OAuth (Google + Microsoft) — Phase 04.6.1
    oauth_provider        = Column(String(50),  nullable=True)  # 'google' | 'microsoft' | None
    oauth_id              = Column(String(200), nullable=True)  # Provider Sub-ID (eindeutig pro Provider)
    avatar_url            = Column(String(500), nullable=True)
    # H-18: Email-Confirmation-Flag (Microsoft-OAuth Email-Hijacking-Mitigation)
    # True = bestaetigt oder Email/Google-User. False = Microsoft Neu-User pending.
    # Default=True: bestehende User gelten automatisch als bestaetigt.
    email_confirmed       = Column(Boolean, default=True, nullable=True)
    # Phase 04.7.1: Markt-Trennung (FT-Logging)
    market                = Column(String(10), nullable=False, default='dach')
    language              = Column(String(10), nullable=False, default='de')


class Profile(Base):
    __tablename__ = 'profiles'
    id              = Column(Integer, primary_key=True)
    org_id          = Column(Integer, ForeignKey('organisations.id'), nullable=False)
    name            = Column(String(200), nullable=False)
    branche         = Column(String(200))
    daten           = Column(Text)   # JSON
    erstellt_von    = Column(Integer, ForeignKey('users.id'))
    erstellt_am     = Column(DateTime, default=utcnow)
    aktualisiert_am = Column(DateTime, default=utcnow, onupdate=utcnow)
    consent_text    = Column(Text, nullable=True)  # Phase 06: editable consent Vorlesetext


class ProfileSkript(Base):
    __tablename__ = 'profile_skripte'
    id          = Column(Integer, primary_key=True)
    profile_id  = Column(Integer, ForeignKey('profiles.id'), nullable=False)
    name        = Column(String(200), nullable=False)
    inhalt      = Column(Text)
    sortierung  = Column(Integer, default=0)
    created_at  = Column(DateTime, default=utcnow)
    parent_id             = Column(Integer, nullable=True)              # D-04: kein FK-Constraint; zeigt auf Quell-Item (ProfileSkript oder ProfileOpener id)
    is_personalized       = Column(Boolean, default=False, nullable=False)
    briefing_source_firma = Column(String(200), nullable=True)


# ── Phase 08.5: FAQ-Feld pro Profil (D-13) ───────────────────────────────────

class ProfileFaq(Base):
    __tablename__ = 'profile_faqs'
    id           = Column(Integer, primary_key=True)
    profile_id   = Column(Integer, ForeignKey('profiles.id'), nullable=False)
    frage_muster = Column(Text, nullable=False)
    antwort      = Column(Text, nullable=False)
    kategorie    = Column(String(100), nullable=True)   # Technik/Preis/Referenzen/DSGVO/Produkt/Sonstiges
    created_at   = Column(DateTime, default=utcnow)
    used_count   = Column(Integer, default=0, nullable=False)
    mode         = Column(String(20), nullable=False, default='ki_generated')


class ProfileOpener(Base):
    __tablename__ = 'profile_opener'
    id          = Column(Integer, primary_key=True)
    profile_id  = Column(Integer, ForeignKey('profiles.id'), nullable=False)
    name        = Column(String(200), nullable=False)
    inhalt      = Column(Text)
    sortierung  = Column(Integer, default=0)
    type        = Column(String(20), nullable=False, server_default='opener')
    created_at  = Column(DateTime, default=utcnow)
    parent_id             = Column(Integer, ForeignKey('profile_opener.id'), nullable=True)
    is_personalized       = Column(Boolean, default=False, nullable=False)
    briefing_source_firma = Column(String(200), nullable=True)


class Session(Base):
    __tablename__ = 'sessions'
    id          = Column(Integer, primary_key=True)
    user_id     = Column(Integer, ForeignKey('users.id'), nullable=False)
    token       = Column(String(256), unique=True, nullable=False)
    erstellt_am = Column(DateTime, default=utcnow)
    ablauf_am   = Column(DateTime)


class Invitation(Base):
    __tablename__ = 'invitations'
    id          = Column(Integer, primary_key=True)
    org_id      = Column(Integer, ForeignKey('organisations.id'), nullable=False)
    email       = Column(String(200), nullable=False)
    token       = Column(String(256), unique=True, nullable=False)
    erstellt_am = Column(DateTime, default=utcnow)
    verwendet   = Column(Boolean, default=False)


class BillingEvent(Base):
    __tablename__ = 'billing_events'
    id           = Column(Integer, primary_key=True)
    org_id       = Column(Integer, ForeignKey('organisations.id'), nullable=False)
    typ          = Column(String(100))
    betrag       = Column(Float)
    beschreibung = Column(Text)
    timestamp    = Column(DateTime, default=utcnow)
    stripe_event_id  = Column(String(200), unique=True, nullable=True)


class FeedbackEvent(Base):
    __tablename__ = 'feedback_events'
    id             = Column(Integer, primary_key=True)
    user_id        = Column(Integer, ForeignKey('users.id'), nullable=False)
    session_log_id = Column(String(200))
    stars          = Column(Integer)
    comment        = Column(Text)
    created_at     = Column(DateTime, default=utcnow)


class CoachAssignment(Base):
    __tablename__ = 'coach_assignments'
    id          = Column(Integer, primary_key=True)
    coach_id    = Column(Integer, ForeignKey('users.id'), nullable=False)
    org_id      = Column(Integer, ForeignKey('organisations.id'), nullable=False)
    erstellt_am = Column(DateTime, default=utcnow)
    aktiv       = Column(Boolean, default=True)


class TrainingScenario(Base):
    __tablename__ = 'training_scenarios'
    id                = Column(Integer, primary_key=True)
    org_id            = Column(Integer, ForeignKey('organisations.id'), nullable=False)
    name              = Column(String(200), nullable=False)
    beschreibung      = Column(Text)
    kunde_situation   = Column(Text)
    kunde_verhalten   = Column(Text)
    spezial_einwaende = Column(Text)   # JSON array of strings
    schwierigkeit     = Column(String(50), default='mittel')
    erstellt_von      = Column(Integer, ForeignKey('users.id'))
    erstellt_am       = Column(DateTime, default=utcnow)


class PersonalityType(Base):
    __tablename__ = 'personality_types'
    id               = Column(Integer, primary_key=True)
    user_id          = Column(Integer, ForeignKey('users.id'), nullable=True)
    org_id           = Column(Integer, ForeignKey('organisations.id'), nullable=True)
    is_custom        = Column(Boolean, default=False, nullable=False)
    name             = Column(String(100), nullable=False)
    icon             = Column(String(10), nullable=True)
    kurzbeschreibung = Column(String(300), nullable=True)
    attribute        = Column(Text, nullable=False)  # JSON
    kommentar        = Column(Text, nullable=True)
    erstellt_am      = Column(DateTime, default=utcnow)


class ConversationLog(Base):
    __tablename__ = 'conversation_logs'
    id                       = Column(Integer, primary_key=True)
    user_id                  = Column(Integer, ForeignKey('users.id'), nullable=False)
    org_id                   = Column(Integer, ForeignKey('organisations.id'), nullable=False)
    profile_id               = Column(Integer, ForeignKey('profiles.id'), nullable=True)
    profile_name             = Column(String(200))

    started_at               = Column(DateTime, nullable=False)
    ended_at                 = Column(DateTime)
    dauer_sekunden           = Column(Integer)

    segmente_gesamt          = Column(Integer, default=0)
    einwaende_gesamt         = Column(Integer, default=0)
    einwaende_behandelt      = Column(Integer, default=0)
    einwaende_fehlgeschlagen = Column(Integer, default=0)
    einwaende_ignoriert      = Column(Integer, default=0)
    vorwaende_erkannt        = Column(Integer, default=0)

    kb_start                 = Column(Integer, default=30)
    kb_end                   = Column(Integer)
    kb_min                   = Column(Integer)
    kb_max                   = Column(Integer)

    redeanteil_avg           = Column(Integer)
    tempo_avg                = Column(Integer)
    laengster_monolog        = Column(Float)

    hilfe_genutzt            = Column(Integer, default=0)
    quick_actions            = Column(Integer, default=0)
    skript_abdeckung         = Column(Integer)

    sterne                   = Column(Integer)
    kommentar                = Column(Text)

    gegenargument_details    = Column(Text)   # JSON
    painpoints_details       = Column(Text)   # JSON
    phasen_details           = Column(Text)   # JSON

    typ                      = Column(String(20), default='live')
    session_mode             = Column(String(20), default='meeting')  # 'cold_call' or 'meeting'
    created_at               = Column(DateTime, default=utcnow)
    result                   = Column(String(20), nullable=True)  # 'gewonnen' | 'verloren' | NULL
    # Phase 04.7.1: Markt-Trennung (FT-Logging)
    market                   = Column(String(10), nullable=False, default='dach')
    language                 = Column(String(10), nullable=False, default='de')
    # Phase 04.9: Personality-driven training
    personality_type_id      = Column(Integer, ForeignKey('personality_types.id'), nullable=True)
    stimmung_history         = Column(Text, nullable=True)  # JSON list
    # Phase 04.13: PreCall Intelligence
    precall_briefing         = Column(Text, nullable=True)     # generated call briefing (per D-03: only briefing text, no raw search data)
    # Phase 08.20.2: Structured Schicht-1 fields (JSON)
    precall_fields           = Column(Text, nullable=True)     # JSON-serialized Schicht-1 fields dict (per D-03: no raw search data)
    # Phase 07.1: Kaufbereitschafts-Verlauf fuer Live-Session-Chart
    kb_verlauf               = Column(Text, nullable=True)     # JSON list [{ts: "HH:MM:SS", wert: 0-100}]
    # Phase 08 D-14: PreCall-Anrede-Override (Du/Sie pro Session). Fallback: Profile.daten.ki.ansprache.
    anrede                   = Column(String(10), nullable=True)


class Phrase(Base):
    __tablename__ = 'phrases'
    id             = Column(Integer, primary_key=True)
    user_id        = Column(Integer, ForeignKey('users.id'), nullable=False)
    session_id     = Column(Integer, ForeignKey('conversation_logs.id'), nullable=True)
    text           = Column(Text, nullable=False)
    objection_type = Column(String(100), nullable=False)
    created_at     = Column(DateTime, default=utcnow)
    # Phase 08.23.2.B: DSGVO-Anonymisierungs-Pipeline quality_tier
    # 'A'=sauber, 'B'=Edge-Case-NER, 'C'=Art9-Treffer/Exception
    quality_tier   = Column(String(1), nullable=False, server_default='A')
    # Phase 08.23.2.C: Phasen-Klassifikator + Gatekeeper-Erkennung
    # Diskriminator fuer Gatekeeper-Phrases vs. cold_call/meeting-Phrases
    # CHECK-Constraint ck_phrases_mode in DB via Alembic 0003
    mode           = Column(String(20), nullable=False, server_default='cold_call')


# Block 5: Early Access Waitlist
class Waitlist(Base):
    __tablename__ = 'waitlist'
    id            = Column(Integer, primary_key=True)
    email         = Column(String(200), unique=True, nullable=False)
    name          = Column(String(200))
    firma         = Column(String(200))
    rolle         = Column(String(100))
    branche       = Column(String(100))
    nachricht     = Column(Text)
    position      = Column(Integer)
    status        = Column(String(50), default='waiting')  # waiting/invited/registered/declined
    invited_at    = Column(DateTime)
    registered_at = Column(DateTime)
    referral_code = Column(String(50))
    referred_by   = Column(String(50))
    created_at    = Column(DateTime, default=utcnow)


# Block 6: Changelog
class Changelog(Base):
    __tablename__ = 'changelog'
    id              = Column(Integer, primary_key=True)
    version         = Column(String(20), nullable=False)
    titel           = Column(String(300), nullable=False)
    inhalt          = Column(Text, nullable=False)
    typ             = Column(String(50), default='update')  # major/feature/improvement/bugfix/security
    bekannte_bugs   = Column(Text)   # JSON array
    veroeffentlicht = Column(Boolean, default=True)
    created_at      = Column(DateTime, default=utcnow)


class AuditLog(Base):
    __tablename__ = 'audit_log'
    id          = Column(Integer, primary_key=True)
    user_id     = Column(Integer, ForeignKey('users.id'), nullable=True)
    org_id      = Column(Integer, ForeignKey('organisations.id'), nullable=True)
    action      = Column(String(100), nullable=False)
    target_type = Column(String(100), nullable=True)
    target_id   = Column(Integer, nullable=True)
    details     = Column(Text, nullable=True)
    ip_address  = Column(String(64), nullable=True)
    user_agent  = Column(String(500), nullable=True)
    created_at  = Column(DateTime, default=utcnow, nullable=False)


class ObjectionEvent(Base):
    __tablename__ = 'objection_events'
    id                  = Column(Integer, primary_key=True)
    user_id             = Column(Integer, ForeignKey('users.id'), nullable=False)
    org_id              = Column(Integer, ForeignKey('organisations.id'), nullable=True)
    conversation_log_id = Column(Integer, ForeignKey('conversation_logs.id'), nullable=False)
    einwand_typ         = Column(String(100), nullable=False)
    # Phase 08 D-01: 3-state (TRUE=Erfolg, FALSE=Kein Erfolg, NULL=Uebersprungen/Unbekannt)
    success             = Column(Boolean, default=None, nullable=True)
    created_at          = Column(DateTime, default=utcnow, nullable=False)
    # Phase 08.X: Persistierter Claude-Response-Text für Rating-Page
    antwort_text        = Column(Text, nullable=True)
    einwand_text        = Column(Text, nullable=True)


class EwbRating(Base):
    """Phase 08 D-30/D-35: Manuelle EWB-Quality-Ratings von Andre (solo pre-launch).

    3 binaere Sub-Kriterien pro EWB: klingt_wie_mensch, keine_halluzination, trifft_einwand.
    Quality-Score-Formel (D-27): (klingt + 2*halluzi + trifft) / 4 * 100.
    Eindeutig pro (conversation_log_id, einwand_typ_key) -- 1 Rating pro EWB in einer Session.
    """
    __tablename__ = 'ewb_ratings'
    __table_args__ = (
        UniqueConstraint('conversation_log_id', 'einwand_typ_key',
                         name='uq_ewb_rating_per_conv_ewb'),
    )
    id                  = Column(Integer, primary_key=True)
    conversation_log_id = Column(Integer, ForeignKey('conversation_logs.id'), nullable=False)
    einwand_typ_key     = Column(String(100), nullable=False)  # matched gegen ObjectionEvent.einwand_typ
    klingt_wie_mensch   = Column(Boolean, nullable=False)
    keine_halluzination = Column(Boolean, nullable=False)
    trifft_einwand      = Column(Boolean, nullable=False)
    rater_id            = Column(Integer, ForeignKey('users.id'), nullable=False)
    rated_at            = Column(DateTime, default=utcnow, nullable=False)

    @property
    def quality_score(self) -> float:
        """D-27 Formel: (klingt + 2*halluzi + trifft) / 4 * 100 -> Skala 0-100."""
        return ((int(bool(self.klingt_wie_mensch))
                 + 2 * int(bool(self.keine_halluzination))
                 + int(bool(self.trifft_einwand))) / 4.0) * 100


class Feedback(Base):
    __tablename__ = 'feedback'
    id                = Column(Integer, primary_key=True)
    user_id           = Column(Integer, ForeignKey('users.id'), nullable=False)
    org_id            = Column(Integer, ForeignKey('organisations.id'), nullable=True)
    typ               = Column(String(50), nullable=False)   # 'bug' | 'idea' | 'praise' | 'question'
    text              = Column(Text, nullable=False)
    screenshot_path   = Column(String(300), nullable=True)   # relativ: 'feedback/{uuid}.png'
    context_url       = Column(String(500), nullable=True)
    status            = Column(String(30), default='new', nullable=False)  # new|seen|in_planning|done|wont_fix
    kategorie         = Column(String(50), nullable=True)
    rating            = Column(Integer, nullable=True)       # 1-5 für Quick-Rating
    created_at        = Column(DateTime, default=utcnow, nullable=False)
    updated_at        = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    notification_sent = Column(Boolean, default=False, nullable=False)


class PlanningFeedbackLink(Base):
    __tablename__ = 'planning_feedback_link'
    id               = Column(Integer, primary_key=True)
    feedback_id      = Column(Integer, ForeignKey('feedback.id'), nullable=False)
    planning_title   = Column(String(200), nullable=False)
    planning_status  = Column(String(40), default='backlog', nullable=False)  # backlog|active|done
    created_at       = Column(DateTime, default=utcnow, nullable=False)


class PromptVersion(Base):
    __tablename__ = 'prompt_versions'
    __table_args__ = (
        UniqueConstraint('version', 'module', name='uq_prompt_version_module'),
    )
    id          = Column(Integer, primary_key=True)
    version     = Column(String(50), nullable=False)
    module      = Column(String(50), nullable=False)
    prompt_text = Column(Text, nullable=False)
    changelog   = Column(Text)
    is_active   = Column(Boolean, default=False, nullable=False)
    # Phase 08 D-26: A/B-Default-Fallback (wenn get_active_prompt_version() single-lookup macht).
    # Bei 2+ aktiven Varianten pro module: exakt 1 Row hat is_default=True.
    is_default  = Column(Boolean, default=False, nullable=False)
    created_at  = Column(DateTime, default=utcnow)


# ── Phase 04.7.2: Founder Cost Dashboard Models ──────────────────────────

class ApiCostLog(Base):
    """Jeder einzelne API-Call mit eingefrorenem Wechselkurs und gefrorener Rate.
    D-02: Wechselkurs wird beim Schreiben eingefroren (steuerlich korrekt).
    """
    __tablename__ = 'api_cost_log'
    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=utcnow, nullable=False, index=True)
    provider = Column(String(32), nullable=False, index=True)
    model = Column(String(64), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    org_id = Column(Integer, ForeignKey('organisations.id'), nullable=True, index=True)
    units = Column(Numeric(14, 4), nullable=False)
    unit_type = Column(String(32), nullable=False)
    rate_applied = Column(Numeric(12, 8), nullable=False)
    rate_currency = Column(String(3), nullable=False, default='USD')
    fx_rate_applied = Column(Numeric(10, 6), nullable=False)
    cost_eur = Column(Numeric(12, 6), nullable=False)
    session_id = Column(String(64), nullable=True, index=True)
    context_tag = Column(String(32), nullable=True)
    latency_ms  = Column(Integer, nullable=True)
    call_site   = Column(String(50), nullable=True)


class ApiRate(Base):
    """Aktuelle API-Preise, editierbar, historisch ueber active-Flag."""
    __tablename__ = 'api_rates'
    __table_args__ = (
        UniqueConstraint('provider', 'model', 'unit_type', 'active', name='uix_api_rate_active'),
    )
    id = Column(Integer, primary_key=True)
    provider = Column(String(32), nullable=False, index=True)
    model = Column(String(64), nullable=False)
    unit_type = Column(String(32), nullable=False)
    price_per_unit = Column(Numeric(12, 8), nullable=False)
    currency = Column(String(3), nullable=False, default='USD')
    active = Column(Boolean, default=True, nullable=False)
    last_checked_at = Column(DateTime, default=utcnow, nullable=False)
    source_url = Column(String(512), nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class PriceChangeLog(Base):
    """D-06: Manuell erkannte Preisaenderungen mit Impact-Berechnung."""
    __tablename__ = 'price_change_log'
    id = Column(Integer, primary_key=True)
    api_rate_id = Column(Integer, ForeignKey('api_rates.id'), nullable=False)
    changed_at = Column(DateTime, default=utcnow, nullable=False, index=True)
    old_rate = Column(Numeric(12, 8), nullable=False)
    new_rate = Column(Numeric(12, 8), nullable=False)
    currency = Column(String(3), nullable=False, default='USD')
    impact_eur_per_month = Column(Numeric(12, 2), nullable=True)
    note = Column(Text, nullable=True)


class FixedCost(Base):
    """D-10: Fixe Betriebskosten (Hetzner, Domain, Kontist, count.tax, Homeoffice)."""
    __tablename__ = 'fixed_costs'
    id = Column(Integer, primary_key=True)
    name = Column(String(128), nullable=False)
    amount_eur = Column(Numeric(12, 2), nullable=False)
    vat_rate = Column(Numeric(4, 2), nullable=False, default=19.00)
    cycle = Column(String(16), nullable=False)  # 'monthly' | 'yearly' | 'per_day'
    skr03 = Column(String(8), nullable=True)
    eur_line = Column(Integer, nullable=True)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class RevenueLog(Base):
    """D-03: Jede Stripe-Zahlung aus invoice.payment_succeeded mit USt-Split + Land."""
    __tablename__ = 'revenue_log'
    id = Column(Integer, primary_key=True)
    stripe_invoice_id = Column(String(128), nullable=False, unique=True, index=True)
    stripe_customer_id = Column(String(128), nullable=True, index=True)
    org_id = Column(Integer, ForeignKey('organisations.id'), nullable=True, index=True)
    paid_at = Column(DateTime, nullable=False, index=True)
    netto_cents = Column(Integer, nullable=False, default=0)
    ust_cents = Column(Integer, nullable=False, default=0)
    brutto_cents = Column(Integer, nullable=False, default=0)
    currency = Column(String(3), nullable=False, default='EUR')
    country = Column(String(2), nullable=True, index=True)
    tax_treatment = Column(String(16), nullable=False)  # 'DE_19' | 'EU_RC' | 'DRITTLAND'
    plan_key = Column(String(32), nullable=True)
    raw_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class ExchangeRate(Base):
    """D-05: Taeglicher EZB-Kurs (Frankfurter API)."""
    __tablename__ = 'exchange_rates'
    __table_args__ = (
        UniqueConstraint('date', 'currency_pair', name='uix_exchange_rate_date_pair'),
    )
    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False, index=True)
    currency_pair = Column(String(7), nullable=False)  # 'USD_EUR'
    rate = Column(Numeric(10, 6), nullable=False)
    source = Column(String(16), nullable=False, default='frankfurter')
    created_at = Column(DateTime, default=utcnow, nullable=False)


# ── Phase 04.11: Coach-Modul (Persoenliches Lernsystem) ──────────────────────

class LearningCard(Base):
    __tablename__ = 'learning_cards'
    id                  = Column(Integer, primary_key=True)
    user_id             = Column(Integer, ForeignKey('users.id'), nullable=False)
    call_id             = Column(Integer, ForeignKey('conversation_logs.id'), nullable=True)
    category            = Column(String(100), nullable=False)
    original_suggestion = Column(Text, nullable=False)
    final_text          = Column(Text, nullable=False)
    lernziel            = Column(Text, nullable=True)
    source              = Column(String(20), default='ki')       # 'ki' | 'user'
    status              = Column(String(20), default='vorschlag') # 'vorschlag' | 'aktiv' | 'gelernt' | 'archiviert'
    applied_count       = Column(Integer, default=0)
    regenerate_count    = Column(Integer, default=0)
    created_at          = Column(DateTime, default=utcnow)
    learned_at          = Column(DateTime, nullable=True)


class CoachingReport(Base):
    __tablename__ = 'coaching_reports'
    id                  = Column(Integer, primary_key=True)
    user_id             = Column(Integer, ForeignKey('users.id'), nullable=False)
    period_start        = Column(Date, nullable=False)
    period_end          = Column(Date, nullable=False)
    calls_count         = Column(Integer, default=0)
    avg_readiness_score = Column(Float, nullable=True)
    strongest_phase     = Column(String(100), nullable=True)
    weakest_phase       = Column(String(100), nullable=True)
    talk_ratio_user     = Column(Float, nullable=True)
    talk_ratio_customer = Column(Float, nullable=True)
    report_text         = Column(Text, nullable=True)
    suggested_card_json = Column(Text, nullable=True)
    created_at          = Column(DateTime, default=utcnow)


# ── Phase 04.12: Gesamt-Integration — Learning Events ────────────────────────

class LearningEvent(Base):
    __tablename__ = 'learning_events'
    id            = Column(Integer, primary_key=True)
    user_id       = Column(Integer, ForeignKey('users.id'), nullable=False)
    event_type    = Column(String(50), nullable=False)
    source_module = Column(String(20), nullable=False)
    source_id     = Column(Integer, nullable=True)
    event_metadata = Column('metadata', Text, nullable=True)
    created_at    = Column(DateTime, default=utcnow)


# ── Phase 04.14: CRM Customer Success ────────────────────────────────────────

class CrmNote(Base):
    __tablename__ = 'crm_notes'
    id         = Column(Integer, primary_key=True)
    user_id    = Column(Integer, ForeignKey('users.id'), nullable=False, unique=True)
    notiz      = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    created_at = Column(DateTime, default=utcnow)


def init_db(engine_instance):
    """Create all tables."""
    Base.metadata.create_all(engine_instance)


# --- Neue Architektur-Tabellen (Phase 08.23.2.A+) ---

class Call(Base):
    __tablename__ = 'calls'
    id = Column(UUID_TYPE, primary_key=True, default=uuid.uuid4)
    # FK-Verknüpfung wird in Phase 08.23.2.F nachgereicht (tenant_orgs existiert dort)
    tenant_id = Column(UUID_TYPE, nullable=True)
    # FK-Verknüpfung wird in Phase 08.23.2.G nachgereicht (accounts existiert dort)
    account_id = Column(UUID_TYPE, nullable=True)
    # FK-Verknüpfung wird in Phase 08.23.2.G nachgereicht (contacts existiert dort)
    contact_id = Column(UUID_TYPE, nullable=True)
    # user_id bleibt Integer-kompatibel mit users.id bis UUID-Migration in 08.23.2.F
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    call_mode = Column(Text, nullable=False)
    call_type = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    transcript_storage = Column(Text, nullable=True)
    transcript_expires_at = Column(DateTime(timezone=True), nullable=True)
    call_summary = Column(Text, nullable=True)
    outcome = Column(Text, nullable=True)
    audio_health_score = Column(Float, nullable=True)
    coaching_score = Column(Float, nullable=True)
    # --- Phase 08.23.2.D.UX — Score-Breakdown (REQ-D.UX-11, Migration 0007) ---
    score_breakdown = Column(JSON_TYPE, nullable=True)
    score_schema_version = Column(SmallInteger, nullable=False, server_default='1')
    # --- Phase 08.23.2.D — Outcome-Erfassung (REQ-D-1) ---
    conversation_log_id = Column(Integer, ForeignKey('conversation_logs.id'), nullable=True)
    outcome_confidence = Column(Float, nullable=True)
    outcome_note = Column(Text, nullable=True)
    outcome_source = Column(Text, nullable=True)
    # --- Phase 08.23.2.D.UX — followup_intent (REQ-D.UX-9/10, Migration 0006) ---
    followup_intent = Column(Text, nullable=False, server_default='none')
    meddpicc_extracted = Column(JSON_TYPE, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    __table_args__ = (
        CheckConstraint("call_mode IN ('cold_call', 'meeting_consented')", name='ck_calls_call_mode'),
        CheckConstraint("transcript_storage IN ('none', 'ephemeral', 'consented_full')", name='ck_calls_transcript_storage'),
        CheckConstraint(
            "outcome IN ('meeting_booked', 'callback', 'send_info', 'wrong_person', "
            "'gatekeeper_blocked', 'no_interest', 'contract_signed', 'unknown') OR outcome IS NULL",
            name='ck_calls_outcome',
        ),
        CheckConstraint(
            "outcome_source IN ('ai_auto', 'ai_auto_unsicher', 'user_corrected') OR outcome_source IS NULL",
            name='ck_calls_outcome_source',
        ),
        CheckConstraint(
            "followup_intent IN ('none', 'callback', 'meeting', 'send_info', 'retry_internal')",
            name='ck_calls_followup_intent',
        ),
        Index('idx_calls_account_time', 'account_id', 'started_at'),
        Index('idx_calls_user_time', 'user_id', 'started_at'),
        Index('idx_calls_mode_outcome', 'call_mode', 'outcome', postgresql_where=text('outcome IS NOT NULL')),
    )


class CallEvent(Base):
    __tablename__ = 'call_events'
    id = Column(BigInteger, primary_key=True, autoincrement=True)  # BIGSERIAL on Postgres
    call_id = Column(UUID_TYPE, ForeignKey('calls.id', ondelete='CASCADE'), nullable=False)
    # FK-Verknüpfung wird in Phase 08.23.2.F nachgereicht (tenant_orgs existiert dort)
    tenant_id = Column(UUID_TYPE, nullable=True)
    event_type = Column(Text, nullable=False)
    event_ts_ms = Column(BigInteger, nullable=False)  # BIGINT required: Unix ms timestamps exceed 2^31 after 2038 (C-4 fix)
    payload = Column(JSON_TYPE, nullable=False)
    created_at = Column(DateTime, default=utcnow)
    __table_args__ = (
        CheckConstraint("event_type IN ('transcript_chunk', 'suggestion_shown', 'reaction', 'phase_change', 'audio_health', 'objection_detected', 'consent_optin')", name='ck_call_events_event_type'),
        Index('idx_call_events_call_time', 'call_id', 'event_ts_ms'),
        Index('idx_call_events_type', 'call_id', 'event_type'),
        Index('idx_call_events_payload_gin', 'payload', postgresql_using='gin'),
    )


class TranscriptSegment(Base):
    __tablename__ = 'transcript_segments'
    id                  = Column(BigInteger, primary_key=True, autoincrement=True)  # BIGSERIAL
    conversation_log_id = Column(Integer, ForeignKey('conversation_logs.id', ondelete='CASCADE'), nullable=False)
    ts_ms               = Column(Integer, nullable=False)        # ms ab Call-Start, fuer Reihenfolge
    speaker             = Column(Text, nullable=False)           # 'berater'|'kunde'|'system'
    text                = Column(Text, nullable=False)           # anonymisierter Text (Pipeline B)
    # WICHTIG: das Spalten-Attribut `text` ueberdeckt im Klassen-Koerper die importierte
    # sqlalchemy-Funktion `text` -> server_default=text('now()') wuerde das Column-Objekt
    # aufrufen (TypeError). Daher func.now() (Modul-Ebene, nicht ueberdeckt). DDL-Aequivalent
    # zur Migration 0010 `DEFAULT now()` (CLAUDE.md Punkt 21 ORM/DDL-Konsistenz).
    created_at          = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        CheckConstraint("speaker IN ('berater', 'kunde', 'system')", name='ck_transcript_segments_speaker'),
        Index('idx_transcript_segments_conv_ts', 'conversation_log_id', 'ts_ms'),
    )
