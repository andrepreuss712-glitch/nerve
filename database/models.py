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
    __table_args__ = ({'comment': 'Mandant/Organisation = Abrechnungs- und Daten-Isolations-Einheit (Plan, Fair-Use, Stripe). Status: lebt (Kern-Identitaet). Schreibt/liest routes/auth.py, routes/billing/-Pfade und services/.'},)
    id                   = Column(Integer, primary_key=True)
    name                 = Column(String(200), nullable=False, comment='Organisations-Name')
    plan                 = Column(String(50), default='starter', comment='Plan: starter/team/business/enterprise')
    max_users            = Column(Integer, default=5, comment='Maximale Nutzerzahl im Plan')
    billing_email        = Column(String(200), comment='Rechnungs-Email')
    aktiv                = Column(Boolean, default=True)
    erstellt_am          = Column(DateTime, default=utcnow)
    naechste_abrechnung  = Column(DateTime, comment='Naechster Abrechnungstermin')
    trial_starts_at      = Column(DateTime, nullable=True, comment='Trial-Startzeitpunkt')
    coach_id             = Column(Integer, ForeignKey('users.id'), nullable=True)
    dsgvo_modus          = Column(Boolean, default=True, comment='DSGVO-Modus aktiv (kein woertliches Mitschneiden)')
    # Block 3: Modulares Pricing
    plan_typ             = Column(String(50), default='bundle', comment='Plan-Typ: training/live/bundle/coach')
    training_free_calls  = Column(Integer, default=5, comment='Freie Trainings-Calls')
    live_free_trainings  = Column(Integer, default=3, comment='Freie Live-Trainings')
    # Block 4: Self-Service / Billing
    billing_name         = Column(String(200), comment='Rechnungs-Name')
    billing_street       = Column(String(200), comment='Rechnungs-Strasse')
    billing_zip          = Column(String(20), comment='Rechnungs-PLZ')
    billing_city         = Column(String(100), comment='Rechnungs-Stadt')
    billing_country      = Column(String(100), default='Deutschland', comment='Rechnungs-Land')
    billing_vat_id       = Column(String(50), comment='USt-IdNr. (Umsatzsteuer-ID)')
    cancelled_at         = Column(DateTime, comment='Kuendigungszeitpunkt')
    cancel_reason        = Column(Text, comment='Kuendigungsgrund')
    cancel_feedback      = Column(Text, comment='Kuendigungs-Feedback')
    # Block 5: Early Access
    is_early_access      = Column(Boolean, default=False)
    early_access_discount = Column(Integer, default=50, comment='Early-Access-Rabatt in Prozent')
    # Block 6: Flat-Rate Pricing
    minuten_limit        = Column(Integer, default=1000, comment='Fair-Use Minuten-Limit pro User/Monat')   # Fair-Use pro User/Monat
    training_voice_limit = Column(Integer, default=50, comment='TTS-Trainings-Limit pro User/Monat')     # TTS-Trainings pro User/Monat
    plan_preis           = Column(Integer, default=49, comment='Flat-Rate-Preis in Euro/Monat')     # Euro/Monat Flat-Rate
    # Fair-Use Tracking (org-level, resets monthly)
    live_minutes_used      = Column(Integer, default=0, comment='Verbrauchte Live-Minuten diesen Monat')    # Live-Minuten verbraucht diesen Monat
    training_sessions_used = Column(Integer, default=0, comment='Gestartete Trainings diesen Monat')    # Trainings gestartet diesen Monat
    fair_use_reset_month   = Column(String(7), comment="Fair-Use-Reset-Monat, z.B. '2026-04'")             # e.g. '2026-04'
    # Block 7: Stripe Integration
    stripe_customer_id     = Column(String(100), comment='Stripe Customer-ID')
    stripe_subscription_id = Column(String(100), comment='Stripe Subscription-ID')
    stripe_price_id        = Column(String(100), comment='Stripe Price-ID')
    subscription_status    = Column(String(50), default='inactive', comment='Subscription-Status')


class User(Base):
    __tablename__ = 'users'
    __table_args__ = ({'comment': 'Nutzer-Konto innerhalb einer Organisation (Auth, Rolle, Onboarding, Usage, OAuth). Status: lebt (Kern-Identitaet). Schreibt/liest routes/auth.py, routes/onboarding/, services/ ueberall via g.user.'},)
    id                  = Column(Integer, primary_key=True)
    org_id              = Column(Integer, ForeignKey('organisations.id'), nullable=False)
    email               = Column(String(200), unique=True, nullable=False, comment='Login-Email (eindeutig)')
    passwort_hash       = Column(String(256), nullable=True, comment="Passwort-Hash; nullable fuer OAuth-User (OAuth setzt '' als Sentinel)")  # Phase 04.6.1: nullable für OAuth-User. SQLite Tabellen-NOT-NULL bleibt — OAuth-Flow setzt '' als Sentinel.
    rolle               = Column(String(50), default='member', comment='Rolle: owner/admin/member')  # owner/admin/member
    is_superadmin       = Column(Boolean, default=False, nullable=False)
    aktiv               = Column(Boolean, default=True)
    erstellt_am         = Column(DateTime, default=utcnow)
    active_profile_id   = Column(Integer, ForeignKey('profiles.id'), nullable=True)
    letzte_aktivitaet   = Column(DateTime, nullable=True, comment='Zeitpunkt der letzten User-Aktivitaet')
    trial_ends_at       = Column(DateTime, nullable=True, comment='Ablaufzeitpunkt der Trial-Phase')
    is_trial            = Column(Boolean, default=False)
    is_coach            = Column(Boolean, default=False)
    is_test_user        = Column(Boolean, default=False, nullable=False)
    # Block 1: Onboarding
    vorname             = Column(String(100), comment='Vorname des Users')
    nachname            = Column(String(100), comment='Nachname des Users')
    onboarding_done     = Column(Boolean, default=False, comment='[DEPRECATED ab AUTH-2 -- EINGEFROREN, nicht droppen] Abgeloest durch users.onboarding_state. Noch aktive LESER (kein neuer Schreiber): routes/auth.py (_login_user liest, _create_org_and_user setzt False), routes/oauth.py. Drop erst nach grep-Beleg 0 Leser (Zombie-Regel Punkt 23/29).')
    onboarding_state    = Column(Text, nullable=False, server_default='pending',
                                 comment='Onboarding-Fortschritt der Weiche post_login_destination (pending|done|skipped; CHECK ck_users_onboarding_state, erweiterbar um step_* ohne Weichen-Aenderung, D-09). Neue Wahrheitsquelle statt onboarding_done. Status: lebt (ab AUTH-2). Schreibt routes/onboarding.py (Erstprofil-Submit/Skip) + DB-Default pending bei Anlage; liest routes/auth.py + routes/oauth.py (post_login_destination).')
    skip_onboarding     = Column(Boolean, nullable=False, server_default=text('false'), default=False,
                                 comment='Founder/Support-Schalter: ueberspringt NUR das Onboarding (Stufe 1 der Weiche), NICHT das Billing (das laeuft ueber organisations.skip_billing, AUTH-3/4). Status: Foundation -- Setz-UI kommt AUTH-4, hier nur Spalte + Leser. Schreibt (spaeter) AUTH-4 Flask-Admin; liest routes/auth.py + routes/oauth.py (post_login_destination Stufe 1).')
    erfahrungslevel     = Column(String(50), comment='Erfahrungslevel: einsteiger/fortgeschritten/profi')   # einsteiger/fortgeschritten/profi
    schmerzpunkt        = Column(Text, comment='Onboarding: groesster Schmerzpunkt')
    persoenlich         = Column(Text, comment='Onboarding: persoenliche Angaben')
    # Block 2: Gamification
    streak_count        = Column(Integer, default=0, comment='Aktuelle Streak-Laenge')
    streak_last_date    = Column(Date, comment='Letztes Datum mit Aktivitaet (Streak)')
    total_points        = Column(Integer, default=0, comment='Gesamtpunkte (Gamification)')
    level               = Column(String(50), default='rookie', comment='Gamification-Level')
    # Block 3: Pricing / Nudges
    nudge_dismissed     = Column(Text, comment='JSON-Array: weggeklickte Nudges')         # JSON array
    live_calls_used     = Column(Integer, default=0, comment='Verbrauchte Live-Calls')
    trainings_used      = Column(Integer, default=0, comment='Verbrauchte Trainings')
    # Block 4: Notification prefs
    notif_training_reminder = Column(Boolean, default=True, comment='Notif-Praeferenz: Training-Reminder')
    notif_streak_warning    = Column(Boolean, default=True, comment='Notif-Praeferenz: Streak-Warnung')
    notif_achievements      = Column(Boolean, default=True, comment='Notif-Praeferenz: Achievements')
    notif_coach             = Column(Boolean, default=True, comment='Notif-Praeferenz: Coach-Hinweise')
    notif_nudges            = Column(Boolean, default=True, comment='Notif-Praeferenz: Nudges')
    # Block 4: Dashboard style
    dashboard_stil      = Column(Text, comment='Dashboard-Stil-Praeferenz (Legacy)')
    # Block 6: Changelog
    last_seen_changelog = Column(String(20), comment='Zuletzt gesehene Changelog-Version')
    # Block 8: Dashboard Layout Preference
    dashboard_style     = Column(String(20), default='vollstaendig', comment='Dashboard-Layout: vollstaendig/kompakt')
    # Block 7: Flat-Rate Usage Tracking
    minuten_used          = Column(Integer, default=0, comment='Verbrauchte Minuten diesen Monat')    # Diesen Monat verbrauchte Minuten
    trainings_voice_used  = Column(Integer, default=0, comment='TTS-Trainings diesen Monat')    # TTS-Trainings diesen Monat
    usage_reset_date      = Column(Date, comment='Datum des naechsten Usage-Resets')
    # Block 9: Language Preference
    preferred_language    = Column(String(10), default='de', comment='Bevorzugte UI-Sprache')
    # Block 10: Theme Preference
    preferred_theme       = Column(String(10), default='dark', comment='Bevorzugtes Theme: dark/light')
    # Block 11: Training Analytics
    weekly_goal           = Column(Integer, default=5, comment='Woechentliches Trainings-Ziel')
    # Block 7: Integration Engine
    pending_training_recommendation = Column(Text, nullable=True, comment='JSON: offene Trainings-Empfehlung der Integration-Engine')  # JSON: {"einwand_typ": "...", "scenario_name": "...", "created_at": "..."}
    # Block 12: Sales Performance Calculator
    avg_deal_wert         = Column(Integer, nullable=True, comment='Durchschnittlicher Deal-Wert in Euro (NULL = nicht gesetzt)')   # Euro, NULL = nicht gesetzt
    # Block 13: OAuth (Google + Microsoft) — Phase 04.6.1
    oauth_provider        = Column(String(50),  nullable=True, comment="OAuth-Provider: 'google' | 'microsoft' | None")  # 'google' | 'microsoft' | None
    oauth_id              = Column(String(200), nullable=True, comment='OAuth Provider-Sub-ID (eindeutig pro Provider)')  # Provider Sub-ID (eindeutig pro Provider)
    avatar_url            = Column(String(500), nullable=True, comment='Avatar-Bild-URL')
    # H-18/AUTH-EMAIL-VERIFY: Email-Confirmation-Flag. True = bestaetigt (Email/Google-User oder
    # nach Confirm-Klick). False = unbestaetigt (Form-Register, Microsoft-Neu-User) → fail-closed Gate.
    # Default=False (D-03b): neue Inserts unbestaetigt bis Confirm. Bestand-Rows unveraendert (kein
    # Backfill). Laeuft ZULETZT (Wave 3) — reiner No-Op, weil jeder Creator (Plan 03) schon explizit setzt.
    # nullable=True bleibt (kein NOT-NULL — Bestand-Rows nicht angefasst).
    email_confirmed       = Column(Boolean, default=False, nullable=True,
        comment='Email bestaetigt — das fail-closed login_required-Gate laesst nur True passieren '
                '(NULL/False gaten). Status: lebt. '
                'Schreibt routes/oauth.py (Microsoft=False, Google=True), '
                'routes/auth.py (api_register=False, confirm_email=True, invite=True), '
                'app.py + scripts/seed_test_user.py (seed=True), DB-Default False (Migration 0033); '
                'liest routes/auth.py login_required-Gate.')
    # Phase 04.7.1: Markt-Trennung (FT-Logging)
    market                = Column(String(10), nullable=False, default='dach', comment='Markt fuer FT-Logging-Trennung (z.B. dach)')
    language              = Column(String(10), nullable=False, default='de', comment='Sprache des Nutzers (z.B. de)')


class Profile(Base):
    __tablename__ = 'profiles'
    __table_args__ = ({'comment': 'Verkaeufer-Wissen/Methodik-Profil je Organisation (JSON-Methodik-Container daten). Status: lebt. Schreibt/liest routes/profiles.py; daten gelesen in live_session.set_active_profile.'},)
    id              = Column(Integer, primary_key=True)
    org_id          = Column(Integer, ForeignKey('organisations.id'), nullable=False)
    name            = Column(String(200), nullable=False, comment='Profil-Name')
    branche         = Column(String(200), comment='Branche des Profils')
    daten           = Column(Text, comment='JSON-Methodik-Container (einwaende/phasen/gegenargumente/ki/kaufsignale)')   # JSON
    erstellt_von    = Column(Integer, ForeignKey('users.id'), comment='Ersteller-User (FK users.id)')
    erstellt_am     = Column(DateTime, default=utcnow)
    aktualisiert_am = Column(DateTime, default=utcnow, onupdate=utcnow)
    consent_text    = Column(Text, nullable=True, comment='Editierbarer Consent-Vorlesetext (Phase 06)')  # Phase 06: editable consent Vorlesetext


class ProfileSkript(Base):
    __tablename__ = 'profile_skripte'
    __table_args__ = ({'comment': 'Skript-Bausteine je Profil (Gespraechsleitfaeden, ggf. personalisiert). Status: lebt. Schreibt/liest routes/profiles.py; PreCall-Personalisierung in services/.'},)
    id          = Column(Integer, primary_key=True)
    profile_id  = Column(Integer, ForeignKey('profiles.id'), nullable=False)
    name        = Column(String(200), nullable=False, comment='Skript-Name')
    inhalt      = Column(Text, comment='Skript-Inhalt')
    sortierung  = Column(Integer, default=0, comment='Sortier-Reihenfolge')
    created_at  = Column(DateTime, default=utcnow)
    parent_id             = Column(Integer, nullable=True, comment='Quell-Item-ID (ProfileSkript/ProfileOpener); D-04: kein FK-Constraint')              # D-04: kein FK-Constraint; zeigt auf Quell-Item (ProfileSkript oder ProfileOpener id)
    is_personalized       = Column(Boolean, default=False, nullable=False)
    briefing_source_firma = Column(String(200), nullable=True, comment='Firma aus PreCall-Briefing (Personalisierungs-Quelle)')


# ── Phase 08.5: FAQ-Feld pro Profil (D-13) ───────────────────────────────────

class ProfileFaq(Base):
    __tablename__ = 'profile_faqs'
    __table_args__ = ({'comment': 'FAQ-Eintraege je Profil (Frage-Muster -> Antwort, fuer Live-Antwort-Vorschlaege). Status: lebt. Schreibt/liest routes/profiles.py; gelesen im Live-Loop services/.'},)
    id           = Column(Integer, primary_key=True)
    profile_id   = Column(Integer, ForeignKey('profiles.id'), nullable=False)
    frage_muster = Column(Text, nullable=False, comment='Frage-Muster, gegen das gematcht wird')
    antwort      = Column(Text, nullable=False, comment='Hinterlegte Antwort')
    kategorie    = Column(String(100), nullable=True, comment='Kategorie: Technik/Preis/Referenzen/DSGVO/Produkt/Sonstiges')   # Technik/Preis/Referenzen/DSGVO/Produkt/Sonstiges
    created_at   = Column(DateTime, default=utcnow)
    used_count   = Column(Integer, default=0, nullable=False, comment='Verwendungs-Zaehler')
    mode         = Column(String(20), nullable=False, default='ki_generated', comment='Herkunft: ki_generated vs. manuell')


class ProfileOpener(Base):
    __tablename__ = 'profile_opener'
    __table_args__ = ({'comment': 'Gespraechs-Opener/Einstiegs-Bausteine je Profil (ggf. personalisiert). Status: lebt. Schreibt/liest routes/profiles.py; PreCall-Personalisierung in services/.'},)
    id          = Column(Integer, primary_key=True)
    profile_id  = Column(Integer, ForeignKey('profiles.id'), nullable=False)
    name        = Column(String(200), nullable=False, comment='Opener-Name')
    inhalt      = Column(Text, comment='Opener-Inhalt')
    sortierung  = Column(Integer, default=0, comment='Sortier-Reihenfolge')
    type        = Column(String(20), nullable=False, server_default='opener', comment='Typ des Bausteins (z.B. opener)')
    created_at  = Column(DateTime, default=utcnow)
    parent_id             = Column(Integer, ForeignKey('profile_opener.id'), nullable=True)
    is_personalized       = Column(Boolean, default=False, nullable=False)
    briefing_source_firma = Column(String(200), nullable=True, comment='Firma aus PreCall-Briefing (Personalisierungs-Quelle)')


class Session(Base):
    __tablename__ = 'sessions'
    __table_args__ = ({'comment': 'DB-Token-Session (DbSession) — Auth nutzt jedoch Flask-Session, nicht diese Tabelle. Status: write-only [ZOMBIE]. Schreibt routes/auth.py:134; KEIN Reader.'},)
    id          = Column(Integer, primary_key=True)
    user_id     = Column(Integer, ForeignKey('users.id'), nullable=False)
    token       = Column(String(256), unique=True, nullable=False, comment='Session-Token (eindeutig)')
    erstellt_am = Column(DateTime, default=utcnow)
    ablauf_am   = Column(DateTime, comment='Ablaufzeitpunkt der Session')


class Invitation(Base):
    __tablename__ = 'invitations'
    __table_args__ = ({'comment': 'Einladungs-Token fuer neue Team-Mitglieder einer Organisation. Status: lebt. Schreibt/liest routes/ (Org-/Team-Verwaltung) ueber Token.'},)
    id          = Column(Integer, primary_key=True)
    org_id      = Column(Integer, ForeignKey('organisations.id'), nullable=False)
    email       = Column(String(200), nullable=False, comment='Eingeladene Email-Adresse')
    token       = Column(String(256), unique=True, nullable=False, comment='Einladungs-Token (eindeutig)')
    erstellt_am = Column(DateTime, default=utcnow)
    verwendet   = Column(Boolean, default=False, comment='Flag: Einladung wurde bereits eingeloest')


class BillingEvent(Base):
    __tablename__ = 'billing_events'
    __table_args__ = ({'comment': 'Abrechnungs-Ereignisse pro Organisation (Stripe-Webhooks, Betraege). Status: lebt. Schreibt Billing-/Stripe-Webhook-Pfad; liest Abrechnungs-/Founder-Ansichten.'},)
    id           = Column(Integer, primary_key=True)
    org_id       = Column(Integer, ForeignKey('organisations.id'), nullable=False)
    typ          = Column(String(100), comment='Ereignis-Typ')
    betrag       = Column(Float, comment='Betrag in Euro')
    beschreibung = Column(Text, comment='Beschreibung des Ereignisses')
    timestamp    = Column(DateTime, default=utcnow, comment='Zeitpunkt des Ereignisses')
    stripe_event_id  = Column(String(200), unique=True, nullable=True, comment='Stripe-Event-ID (Idempotenz, eindeutig)')


class FeedbackEvent(Base):
    __tablename__ = 'feedback_events'
    __table_args__ = ({'comment': 'Stern-Feedback zu einer Session (Legacy-Feedback-Kanal). Status: write-only [ZOMBIE]. Schreibt routes/app_routes.py:1253; kein Reader.'},)
    id             = Column(Integer, primary_key=True)
    user_id        = Column(Integer, ForeignKey('users.id'), nullable=False)
    session_log_id = Column(String(200), comment='Referenzierte Session-Log-ID')
    stars          = Column(Integer, comment='Stern-Bewertung')
    comment        = Column(Text, comment='Freitext-Kommentar')
    created_at     = Column(DateTime, default=utcnow)


class CoachAssignment(Base):
    __tablename__ = 'coach_assignments'
    __table_args__ = ({'comment': 'Zuordnung Coach <-> Organisation (Coach-Plattform fuer Teams). Status: lebt. Schreibt/liest routes/coach.py.'},)
    id          = Column(Integer, primary_key=True)
    coach_id    = Column(Integer, ForeignKey('users.id'), nullable=False)
    org_id      = Column(Integer, ForeignKey('organisations.id'), nullable=False)
    erstellt_am = Column(DateTime, default=utcnow)
    aktiv       = Column(Boolean, default=True)


class TrainingScenario(Base):
    __tablename__ = 'training_scenarios'
    __table_args__ = ({'comment': 'Trainings-Szenario-Konfiguration je Organisation (Kunden-Situation/Verhalten/Einwaende fuer KI-Training). Status: lebt. Schreibt/liest routes/training.py; gelesen in services/training_service.py.'},)
    id                = Column(Integer, primary_key=True)
    org_id            = Column(Integer, ForeignKey('organisations.id'), nullable=False)
    name              = Column(String(200), nullable=False, comment='Szenario-Name')
    beschreibung      = Column(Text, comment='Szenario-Beschreibung')
    kunde_situation   = Column(Text, comment='Situation des simulierten Kunden')
    kunde_verhalten   = Column(Text, comment='Verhalten des simulierten Kunden')
    spezial_einwaende = Column(Text, comment='JSON-Array: spezielle Einwaende fuer dieses Szenario')   # JSON array of strings
    schwierigkeit     = Column(String(50), default='mittel', comment='Schwierigkeitsgrad: leicht/mittel/schwer')
    erstellt_von      = Column(Integer, ForeignKey('users.id'), comment='Ersteller-User (FK users.id)')
    erstellt_am       = Column(DateTime, default=utcnow)


class PersonalityType(Base):
    __tablename__ = 'personality_types'
    __table_args__ = ({'comment': 'Persoenlichkeitstyp-Konfiguration fuer Personality-driven Training (Standard + Custom). Status: lebt. Schreibt/liest routes/training.py; gelesen im Trainings-Loop services/.'},)
    id               = Column(Integer, primary_key=True)
    user_id          = Column(Integer, ForeignKey('users.id'), nullable=True)
    org_id           = Column(Integer, ForeignKey('organisations.id'), nullable=True)
    is_custom        = Column(Boolean, default=False, nullable=False)
    name             = Column(String(100), nullable=False, comment='Name des Persoenlichkeitstyps')
    icon             = Column(String(10), nullable=True, comment='Icon/Emoji des Typs')
    kurzbeschreibung = Column(String(300), nullable=True, comment='Kurzbeschreibung des Typs')
    attribute        = Column(Text, nullable=False, comment='JSON: Verhaltens-Attribute des Typs')  # JSON
    kommentar        = Column(Text, nullable=True, comment='Freitext-Kommentar')
    erstellt_am      = Column(DateTime, default=utcnow)


class ConversationLog(Base):
    __tablename__ = 'conversation_logs'
    __table_args__ = ({'comment': 'Persistenter Call-Datensatz mit aggregierter Post-Call-Analyse (Einwaende, Redeanteil, KB-Verlauf). RUECKGRAT des Call-Analyse-Clusters mit 6 Kindern. Status: lebt (TAXO-Umbau-Zone). Schreibt routes/app_routes.py (end_session); liest routes/dashboard.py, routes/learning.py.'},)
    id                       = Column(Integer, primary_key=True)
    user_id                  = Column(Integer, ForeignKey('users.id'), nullable=False)
    org_id                   = Column(Integer, ForeignKey('organisations.id'), nullable=False)
    profile_id               = Column(Integer, ForeignKey('profiles.id'), nullable=True)
    profile_name             = Column(String(200), comment='Profil-Name zum Zeitpunkt des Calls (Snapshot)')

    started_at               = Column(DateTime, nullable=False, comment='Call-Startzeitpunkt')
    ended_at                 = Column(DateTime, comment='Call-Endzeitpunkt')
    dauer_sekunden           = Column(Integer, comment='Call-Dauer in Sekunden')

    segmente_gesamt          = Column(Integer, default=0, comment='Anzahl Transkript-Segmente gesamt')
    einwaende_gesamt         = Column(Integer, default=0, comment='Anzahl erkannter Einwaende gesamt')
    einwaende_behandelt      = Column(Integer, default=0, comment='Anzahl erfolgreich behandelter Einwaende')
    einwaende_fehlgeschlagen = Column(Integer, default=0, comment='Anzahl fehlgeschlagener Einwand-Behandlungen')
    einwaende_ignoriert      = Column(Integer, default=0, comment='Anzahl ignorierter Einwaende')
    vorwaende_erkannt        = Column(Integer, default=0, comment='Anzahl als Vorwand erkannter Einwaende')

    kb_start                 = Column(Integer, default=30, comment='Kaufbereitschaft Start-Wert (0-100)')
    kb_end                   = Column(Integer, comment='Kaufbereitschaft End-Wert (0-100)')
    kb_min                   = Column(Integer, comment='Kaufbereitschaft Minimum waehrend Call')
    kb_max                   = Column(Integer, comment='Kaufbereitschaft Maximum waehrend Call')

    redeanteil_avg           = Column(Integer, comment='Durchschnittlicher Redeanteil Berater in Prozent')
    tempo_avg                = Column(Integer, comment='Durchschnittliches Sprechtempo')
    laengster_monolog        = Column(Float, comment='Laengster Monolog in Sekunden')

    hilfe_genutzt            = Column(Integer, default=0, comment='Anzahl genutzter Hilfe-/Coaching-Einblendungen')
    quick_actions            = Column(Integer, default=0, comment='Anzahl ausgeloester Quick-Actions')
    skript_abdeckung         = Column(Integer, comment='Skript-Abdeckung in Prozent')

    sterne                   = Column(Integer, comment='Manuelle Stern-Bewertung des Calls (1-5)')
    kommentar                = Column(Text, comment='Manueller Kommentar zum Call')

    gegenargument_details    = Column(Text, comment='JSON: Detail-Daten zu Gegenargumenten')
    painpoints_details       = Column(Text, comment='JSON: Detail-Daten zu erkannten Painpoints')
    phasen_details           = Column(Text, comment='JSON: Detail-Daten zu Gespraechsphasen')

    typ                      = Column(String(20), default='live', comment='Call-Typ: live oder training')
    session_mode             = Column(String(20), default='meeting', comment="Modus: 'cold_call' oder 'meeting'")
    created_at               = Column(DateTime, default=utcnow)
    result                   = Column(String(20), nullable=True, comment="Call-Ergebnis: 'gewonnen' | 'verloren' | NULL")
    # Phase 04.7.1: Markt-Trennung (FT-Logging)
    market                   = Column(String(10), nullable=False, default='dach', comment='Markt fuer FT-Logging-Trennung (z.B. dach)')
    language                 = Column(String(10), nullable=False, default='de', comment='Sprache des Calls (z.B. de)')
    # Phase 04.9: Personality-driven training
    personality_type_id      = Column(Integer, ForeignKey('personality_types.id'), nullable=True)
    stimmung_history         = Column(Text, nullable=True, comment='JSON-Liste: Stimmungs-Verlauf waehrend Call')
    # Phase 04.13: PreCall Intelligence
    precall_briefing         = Column(Text, nullable=True, comment='Generiertes Call-Briefing (D-03: nur Briefing-Text, keine Roh-Suchdaten)')
    # Phase 08.20.2: Structured Schicht-1 fields (JSON)
    precall_fields           = Column(Text, nullable=True, comment='JSON: strukturierte Schicht-1-Felder (D-03: keine Roh-Suchdaten)')
    # Phase 07.1: Kaufbereitschafts-Verlauf fuer Live-Session-Chart
    kb_verlauf               = Column(Text, nullable=True, comment='JSON-Liste: Kaufbereitschafts-Verlauf [{ts, wert 0-100}] fuer Chart')
    # Phase 08 D-14: PreCall-Anrede-Override (Du/Sie pro Session). Fallback: Profile.daten.ki.ansprache.
    anrede                   = Column(String(10), nullable=True, comment="PreCall-Anrede-Override (Du/Sie); Fallback: Profile.daten.ki.ansprache")


class Phrase(Base):
    __tablename__ = 'phrases'
    __table_args__ = ({'comment': 'Anonymisierte Einwand-Phrasen aus Calls als Trainings-/Muster-Korpus (DSGVO-Pipeline). Status: lebt. Schreibt services/-Anonymisierungs-Pipeline (Phase 08.23.2.B); liest Muster-/Klassifikator-Pfad.'},)
    id             = Column(Integer, primary_key=True)
    user_id        = Column(Integer, ForeignKey('users.id'), nullable=False)
    session_id     = Column(Integer, ForeignKey('conversation_logs.id'), nullable=True)
    text           = Column(Text, nullable=False, comment='Anonymisierter Phrasen-Text (Einwand)')
    objection_type = Column(String(100), nullable=False, comment='Einwand-Typ-Klassifikation')
    created_at     = Column(DateTime, default=utcnow)
    # Phase 08.23.2.B: DSGVO-Anonymisierungs-Pipeline quality_tier
    # 'A'=sauber, 'B'=Edge-Case-NER, 'C'=Art9-Treffer/Exception
    quality_tier   = Column(String(1), nullable=False, server_default='A', comment="Anonymisierungs-Qualitaet: 'A'=sauber, 'B'=Edge-Case-NER, 'C'=Art9/Exception")
    # Phase 08.23.2.C: Phasen-Klassifikator + Gatekeeper-Erkennung
    # Diskriminator fuer Gatekeeper-Phrases vs. cold_call/meeting-Phrases
    # CHECK-Constraint ck_phrases_mode in DB via Alembic 0003
    mode           = Column(String(20), nullable=False, server_default='cold_call', comment="Phasen-Diskriminator: gatekeeper vs. cold_call/meeting (CHECK ck_phrases_mode)")


# Block 5: Early Access Waitlist
class Waitlist(Base):
    __tablename__ = 'waitlist'
    __table_args__ = ({'comment': 'Early-Access-Warteliste mit Position und Referral-Tracking. Status: lebt. Schreibt Landing-/Waitlist-Pfad; liest Admin-/Invite-Ansicht.'},)
    id            = Column(Integer, primary_key=True)
    email         = Column(String(200), unique=True, nullable=False, comment='Email (eindeutig)')
    name          = Column(String(200), comment='Name des Interessenten')
    firma         = Column(String(200), comment='Firma des Interessenten')
    rolle         = Column(String(100), comment='Rolle/Position im Unternehmen')
    branche       = Column(String(100), comment='Branche des Interessenten')
    nachricht     = Column(Text, comment='Freitext-Nachricht')
    position      = Column(Integer, comment='Position in der Warteliste')
    status        = Column(String(50), default='waiting', comment='Status: waiting/invited/registered/declined')  # waiting/invited/registered/declined
    invited_at    = Column(DateTime, comment='Zeitpunkt der Einladung')
    registered_at = Column(DateTime, comment='Zeitpunkt der Registrierung')
    referral_code = Column(String(50), comment='Eigener Referral-Code')
    referred_by   = Column(String(50), comment='Referral-Code des Werbers')
    created_at    = Column(DateTime, default=utcnow)


# Block 6: Changelog
class Changelog(Base):
    __tablename__ = 'changelog'
    __table_args__ = ({'comment': 'Veroeffentlichte Produkt-Changelog-Eintraege fuer User-Anzeige. Status: lebt. Schreibt Admin-Pfad; liest Changelog-Anzeige (User.last_seen_changelog-Abgleich).'},)
    id              = Column(Integer, primary_key=True)
    version         = Column(String(20), nullable=False, comment='Versions-String des Eintrags')
    titel           = Column(String(300), nullable=False, comment='Titel des Eintrags')
    inhalt          = Column(Text, nullable=False, comment='Inhalt/Beschreibung')
    typ             = Column(String(50), default='update', comment='Typ: major/feature/improvement/bugfix/security')  # major/feature/improvement/bugfix/security
    bekannte_bugs   = Column(Text, comment='JSON-Array: bekannte Bugs')   # JSON array
    veroeffentlicht = Column(Boolean, default=True, comment='Sichtbarkeits-Flag: Changelog-Eintrag veroeffentlicht')
    created_at      = Column(DateTime, default=utcnow)


class AuditLog(Base):
    __tablename__ = 'audit_log'
    __table_args__ = ({'comment': 'Audit-Trail sicherheitsrelevanter Aktionen (Actor, Action, Target, IP). Status: lebt. Schreibt audit-loggende Pfade; liest Admin-/Compliance-Ansicht.'},)
    id          = Column(Integer, primary_key=True)
    user_id     = Column(Integer, ForeignKey('users.id'), nullable=True)
    org_id      = Column(Integer, ForeignKey('organisations.id'), nullable=True)
    action      = Column(String(100), nullable=False, comment='Durchgefuehrte Aktion')
    target_type = Column(String(100), nullable=True, comment='Typ des betroffenen Objekts')
    target_id   = Column(Integer, nullable=True, comment='ID des betroffenen Objekts')
    details     = Column(Text, nullable=True, comment='JSON/Freitext: Aktions-Details')
    ip_address  = Column(String(64), nullable=True, comment='IP-Adresse des Actors')
    user_agent  = Column(String(500), nullable=True, comment='User-Agent des Actors')
    created_at  = Column(DateTime, default=utcnow, nullable=False)


class ObjectionEvent(Base):
    __tablename__ = 'objection_events'
    __table_args__ = ({'comment': 'Einzel-Einwand-Ereignis pro Call mit Erfolgs-Status (Kind von conversation_logs). Status: lebt. Schreibt routes/app_routes.py:384; liest routes/app_routes.py:471/1389, routes/dashboard.py:736.'},)
    id                  = Column(Integer, primary_key=True)
    user_id             = Column(Integer, ForeignKey('users.id'), nullable=False)
    org_id              = Column(Integer, ForeignKey('organisations.id'), nullable=True)
    conversation_log_id = Column(Integer, ForeignKey('conversation_logs.id'), nullable=False)
    einwand_typ         = Column(String(100), nullable=False, comment='Einwand-Typ-Klassifikation')
    # Phase 08 D-01: 3-state (TRUE=Erfolg, FALSE=Kein Erfolg, NULL=Uebersprungen/Unbekannt)
    success             = Column(Boolean, default=None, nullable=True, comment='3-State: TRUE=Erfolg, FALSE=kein Erfolg, NULL=uebersprungen/unbekannt')
    created_at          = Column(DateTime, default=utcnow, nullable=False)
    # Phase 08.X: Persistierter Claude-Response-Text für Rating-Page
    antwort_text        = Column(Text, nullable=True, comment='Persistierter Claude-Antwort-Text (fuer Rating-Page)')
    einwand_text        = Column(Text, nullable=True, comment='Original-Einwand-Text des Kunden')


class EwbRating(Base):
    """Phase 08 D-30/D-35: Manuelle EWB-Quality-Ratings von Andre (solo pre-launch).

    3 binaere Sub-Kriterien pro EWB: klingt_wie_mensch, keine_halluzination, trifft_einwand.
    Quality-Score-Formel (D-27): (klingt + 2*halluzi + trifft) / 4 * 100.
    Eindeutig pro (conversation_log_id, einwand_typ_key) -- 1 Rating pro EWB in einer Session.
    """
    # TAXO1-Welle 5 (§0.1 Zombie-Rename): hart zu zombie_ewb_ratings umbenannt
    # (0 Zeilen, NICHT gedroppt — Rueckhol-Sicherung). Gehoert thematisch zur
    # Noten-Engine TAXO2 und schlaeft bis dahin. admin_ewb.py umgestellt (Migration 0017).
    __tablename__ = 'zombie_ewb_ratings'
    __table_args__ = (
        UniqueConstraint('conversation_log_id', 'einwand_typ_key',
                         name='uq_ewb_rating_per_conv_ewb'),
        {'comment': 'Manuelle EWB-Qualitaets-Bewertungen (3 binaere Kriterien) pro EWB einer Session, fuer Quality-Score. Status: [ZOMBIE] — gehoert zur Noten-Engine TAXO2, schlaeft. Schreibt+liest routes/admin_ewb.py (umgestellt, TAXO1-Welle 5).'},
    )
    id                  = Column(Integer, primary_key=True)
    conversation_log_id = Column(Integer, ForeignKey('conversation_logs.id'), nullable=False)
    einwand_typ_key     = Column(String(100), nullable=False, comment='Einwand-Typ-Key (matched gegen ObjectionEvent.einwand_typ)')
    klingt_wie_mensch   = Column(Boolean, nullable=False, comment='Sub-Kriterium: klingt wie Mensch')
    keine_halluzination = Column(Boolean, nullable=False, comment='Sub-Kriterium: keine Halluzination (doppelt gewichtet)')
    trifft_einwand      = Column(Boolean, nullable=False, comment='Sub-Kriterium: trifft den Einwand')
    rater_id            = Column(Integer, ForeignKey('users.id'), nullable=False)
    rated_at            = Column(DateTime, default=utcnow, nullable=False, comment='Zeitpunkt der Bewertung')

    @property
    def quality_score(self) -> float:
        """D-27 Formel: (klingt + 2*halluzi + trifft) / 4 * 100 -> Skala 0-100."""
        return ((int(bool(self.klingt_wie_mensch))
                 + 2 * int(bool(self.keine_halluzination))
                 + int(bool(self.trifft_einwand))) / 4.0) * 100


class Feedback(Base):
    __tablename__ = 'feedback'
    __table_args__ = ({'comment': 'In-App-Nutzer-Feedback (Bug/Idee/Lob/Frage) mit Screenshot und Status-Workflow. Status: lebt. Schreibt Feedback-Widget-Pfad; liest Admin-/Founder-Feedback-Ansicht.'},)
    id                = Column(Integer, primary_key=True)
    user_id           = Column(Integer, ForeignKey('users.id'), nullable=False)
    org_id            = Column(Integer, ForeignKey('organisations.id'), nullable=True)
    typ               = Column(String(50), nullable=False, comment="Feedback-Typ: 'bug'|'idea'|'praise'|'question'")   # 'bug' | 'idea' | 'praise' | 'question'
    text              = Column(Text, nullable=False, comment='Feedback-Text')
    screenshot_path   = Column(String(300), nullable=True, comment="Relativer Screenshot-Pfad: 'feedback/{uuid}.png'")   # relativ: 'feedback/{uuid}.png'
    context_url       = Column(String(500), nullable=True, comment='URL, auf der das Feedback gegeben wurde')
    status            = Column(String(30), default='new', nullable=False, comment='Status: new|seen|in_planning|done|wont_fix')  # new|seen|in_planning|done|wont_fix
    kategorie         = Column(String(50), nullable=True, comment='Kategorie des Feedbacks')
    rating            = Column(Integer, nullable=True, comment='Quick-Rating 1-5')       # 1-5 für Quick-Rating
    created_at        = Column(DateTime, default=utcnow, nullable=False)
    updated_at        = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    notification_sent = Column(Boolean, default=False, nullable=False, comment='Flag: Benachrichtigung ueber dieses Feedback wurde versendet')


class PlanningFeedbackLink(Base):
    __tablename__ = 'planning_feedback_link'
    __table_args__ = ({'comment': 'Verknuepfung Feedback <-> Planungs-Eintrag (Backlog-Tracking). Status: lebt. Schreibt/liest Admin-/Founder-Feedback-Planungs-Ansicht.'},)
    id               = Column(Integer, primary_key=True)
    feedback_id      = Column(Integer, ForeignKey('feedback.id'), nullable=False)
    planning_title   = Column(String(200), nullable=False, comment='Titel des Planungs-Eintrags')
    planning_status  = Column(String(40), default='backlog', nullable=False, comment='Planungs-Status: backlog|active|done')  # backlog|active|done
    created_at       = Column(DateTime, default=utcnow, nullable=False)


class PromptVersion(Base):
    __tablename__ = 'prompt_versions'
    __table_args__ = (
        UniqueConstraint('version', 'module', name='uq_prompt_version_module'),
        {'comment': 'Versionierte LLM-Prompts pro Modul mit A/B-Default-Fallback. Status: lebt. Schreibt Prompt-Admin-Pfad; liest get_active_prompt_version() in services/.'},
    )
    id          = Column(Integer, primary_key=True)
    version     = Column(String(50), nullable=False, comment='Prompt-Versions-String')
    module      = Column(String(50), nullable=False, comment='Modul, zu dem der Prompt gehoert')
    prompt_text = Column(Text, nullable=False, comment='Prompt-Text')
    changelog   = Column(Text, comment='Changelog zur Prompt-Version')
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
    __table_args__ = ({'comment': 'Jeder API-Call mit eingefrorenem Wechselkurs und Rate (Founder Cost Dashboard, steuerlich korrekt). Status: lebt. Schreibt ausschliesslich services/cost_tracker.py log_api_cost (gerufen aus services/claude_service.py sieben Live-Pfaden, coaching_service.py, precall_service.py, qa_pipeline.py, deepgram_service.py, training_service.py, crm_service.py, judge_runner.py, adoption_runner.py, outcome_service.py, routes/dashboard.py, routes/payments.py, routes/training.py, nerve_rt/services/session_manager.py, nerve_rt/services/llm/claude_adapter.py); liest routes/admin_dashboard.py (Founder-Dashboard: Tab Ausgaben inkl. Live-KI-Auswertung je context_tag, CSV-Export) + services/eur_calculator.py (EUER). latency_ms/ttft_ms tragen die Dauer NUR an der input-Token-Buchung (D-07).'},)
    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=utcnow, nullable=False, index=True)
    provider = Column(String(32), nullable=False, index=True, comment='API-Provider (z.B. anthropic/deepgram)')
    model = Column(String(64), nullable=False, comment='Verwendetes Modell')
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    org_id = Column(Integer, ForeignKey('organisations.id'), nullable=True, index=True)
    units = Column(Numeric(14, 4), nullable=False, comment='Verbrauchte Einheiten')
    unit_type = Column(String(32), nullable=False, comment='Einheiten-Typ (z.B. tokens/minutes)')
    rate_applied = Column(Numeric(12, 8), nullable=False, comment='Angewandte (eingefrorene) Rate')
    rate_currency = Column(String(3), nullable=False, default='USD', comment='Waehrung der Rate')
    fx_rate_applied = Column(Numeric(10, 6), nullable=False, comment='Eingefrorener Wechselkurs (D-02)')
    cost_eur = Column(Numeric(12, 6), nullable=False, comment='Berechnete Kosten in Euro')
    session_id = Column(String(64), nullable=True, index=True, comment='Zugehoerige Session-ID')
    context_tag = Column(String(32), nullable=True, comment='Kontext-Tag des Calls')
    latency_ms  = Column(Integer, nullable=True, comment='Dauer des KI-Aufrufs in ms bis zum LETZTEN Token. ACHTUNG, zwei Bedeutungen: bei den beiden Stream-Pfaden (pip_variante, pip_autovar) INKLUSIVE der Auslieferung an den Browser, weil der per-Token-Versand (sio.emit, async_mode=threading) im Messfenster liegt; bei den sechs blockierenden Pfaden reine API-Dauer. Bewusst so gelassen (Punkt 25: kein Umbau eines funktionierenden Live-Pfads); die Ansicht markiert die Stream-Zeilen sichtbar. Nur an der input-Token-Buchung gesetzt (D-07: eine API-Antwort zaehlt genau einmal), Cache-/Output-Buchungen bleiben NULL. NICHT identisch mit latency_e/latency_c aus live_session (die enthalten Puffer-Wartezeit + QA-Dispatch).')
    ttft_ms     = Column(Integer, nullable=True, comment='Zeit bis zum ERSTEN Token in ms, im selben Messrahmen wie latency_ms — also inklusive der Auslieferung dieses ersten Tokens an den Browser. Nur Streaming-Pfade (pip_autovar, pip_variante), nur an der input-Token-Buchung; bei blockierenden Aufrufen immer NULL. Getrennte Spalte, weil latency_ms bis zum letzten Token misst — beide Bedeutungen in EINE Spalte zu kippen waere der Name-luegt-Fehler (D-03).')
    call_site   = Column(String(50), nullable=True, comment='Code-Aufrufstelle')


class ApiRate(Base):
    """Aktuelle API-Preise, editierbar, historisch ueber active-Flag."""
    __tablename__ = 'api_rates'
    __table_args__ = (
        # F-3 (KOSTEN-1): UNIQUE ueber (provider, model, unit_type, ACTIVE) laesst pro Tripel
        # genau EINE inaktive Zeile zu -> das Muster "alte deaktivieren + neue einfuegen" traegt
        # genau EINE Preis-Korrektur. Die zweite kollidiert. Bewusst nicht in KOSTEN-1 geloest,
        # Backlog: APIRATE-HISTORY-UNIQUE. Betrifft auch routes/admin_dashboard.py:393-442.
        UniqueConstraint('provider', 'model', 'unit_type', 'active', name='uix_api_rate_active'),
        {'comment': 'Aktuelle API-Preise pro Provider/Modell, editierbar, historisch via active-Flag. Preispflege ist MANUELL (gepflegte Liste + Admin-UI), keine Sync-Engine. Status: lebt. Schreibt app.py _seed_api_rates (Startup-Seed, Liste _API_RATE_SOLL) + routes/admin_dashboard.py:411-438 (Admin-Preiswechsel); liest services/cost_tracker.py:105-108 (Rate pro geloggtem Call; fehlt sie, wird der Call STILL verworfen) + routes/admin_dashboard.py (Founder-Dashboard).'},
    )
    id = Column(Integer, primary_key=True)
    provider = Column(String(32), nullable=False, index=True, comment='API-Provider')
    model = Column(String(64), nullable=False, comment='API-Modellname (z.B. claude-haiku)')
    unit_type = Column(String(32), nullable=False, comment='Einheiten-Typ')
    price_per_unit = Column(Numeric(12, 8), nullable=False, comment='Preis pro Einheit')
    currency = Column(String(3), nullable=False, default='USD', comment='Waehrung des Preises (z.B. USD)')
    active = Column(Boolean, default=True, nullable=False, comment='Aktiv-Flag: nur die aktuell gueltige Rate ist aktiv (Historie ueber active)')
    last_checked_at = Column(DateTime, default=utcnow, nullable=False, comment='Zeitpunkt letzter Preis-Pruefung')
    source_url = Column(String(512), nullable=True, comment='Quell-URL der Preisangabe')
    created_at = Column(DateTime, default=utcnow, nullable=False)


class PriceChangeLog(Base):
    """D-06: Manuell erkannte Preisaenderungen mit Impact-Berechnung."""
    __tablename__ = 'price_change_log'
    __table_args__ = ({'comment': 'Erkannte API-Preisaenderungen mit Impact-Berechnung (Historie-Spur zu api_rates). Status: write-only [ZOMBIE] — kein Reader. Schreibt routes/admin_dashboard.py:434 (Admin-Preiswechsel) + app.py _seed_api_rates (Startup-Seed, wenn die Soll-Liste einen Preis korrigiert).'},)
    id = Column(Integer, primary_key=True)
    api_rate_id = Column(Integer, ForeignKey('api_rates.id'), nullable=False)
    changed_at = Column(DateTime, default=utcnow, nullable=False, index=True, comment='Zeitpunkt der Preisaenderung')
    old_rate = Column(Numeric(12, 8), nullable=False, comment='Alte Rate vor der Aenderung')
    new_rate = Column(Numeric(12, 8), nullable=False, comment='Neue Rate nach der Aenderung')
    currency = Column(String(3), nullable=False, default='USD', comment='Waehrung der Rate (z.B. USD)')
    impact_eur_per_month = Column(Numeric(12, 2), nullable=True, comment='Geschaetzter Impact in Euro/Monat')
    note = Column(Text, nullable=True, comment='Notiz zur Preisaenderung')


class FixedCost(Base):
    """D-10: Fixe Betriebskosten (Hetzner, Domain, Kontist, count.tax, Homeoffice)."""
    __tablename__ = 'fixed_costs'
    __table_args__ = ({'comment': 'Fixe Betriebskosten (Hetzner, Domain, Kontist etc.) mit USt und SKR03-Konto. Status: lebt. Schreibt Admin-Fixkosten-Pflege; liest Founder-Cost-Dashboard.'},)
    id = Column(Integer, primary_key=True)
    name = Column(String(128), nullable=False, comment='Bezeichnung der Fixkosten-Position')
    amount_eur = Column(Numeric(12, 2), nullable=False, comment='Betrag in Euro')
    vat_rate = Column(Numeric(4, 2), nullable=False, default=19.00, comment='USt-Satz in Prozent')
    cycle = Column(String(16), nullable=False, comment="Abrechnungs-Zyklus: 'monthly'|'yearly'|'per_day'")  # 'monthly' | 'yearly' | 'per_day'
    skr03 = Column(String(8), nullable=True, comment='SKR03-Kontonummer')
    eur_line = Column(Integer, nullable=True, comment='EUER-Zeilennummer')
    active = Column(Boolean, default=True, nullable=False, comment='Aktiv-Flag: Fixkosten-Posten aktuell gueltig')
    created_at = Column(DateTime, default=utcnow, nullable=False)


class RevenueLog(Base):
    """D-03: Jede Stripe-Zahlung aus invoice.payment_succeeded mit USt-Split + Land."""
    __tablename__ = 'revenue_log'
    __table_args__ = ({'comment': 'Jede Stripe-Zahlung (invoice.payment_succeeded) mit USt-Split und Land. Status: lebt. Schreibt Stripe-Webhook-Handler; liest Founder-Revenue-Dashboard.'},)
    id = Column(Integer, primary_key=True)
    stripe_invoice_id = Column(String(128), nullable=False, unique=True, index=True, comment='Stripe-Invoice-ID (eindeutig, Idempotenz)')
    stripe_customer_id = Column(String(128), nullable=True, index=True, comment='Stripe-Customer-ID')
    org_id = Column(Integer, ForeignKey('organisations.id'), nullable=True, index=True)
    paid_at = Column(DateTime, nullable=False, index=True, comment='Zahlungszeitpunkt')
    netto_cents = Column(Integer, nullable=False, default=0, comment='Netto-Betrag in Cent')
    ust_cents = Column(Integer, nullable=False, default=0, comment='USt-Betrag in Cent')
    brutto_cents = Column(Integer, nullable=False, default=0, comment='Brutto-Betrag in Cent')
    currency = Column(String(3), nullable=False, default='EUR', comment='Waehrung der Zahlung (z.B. EUR)')
    country = Column(String(2), nullable=True, index=True, comment='Laenderkennung (ISO-2)')
    tax_treatment = Column(String(16), nullable=False, comment="Steuer-Behandlung: 'DE_19'|'EU_RC'|'DRITTLAND'")  # 'DE_19' | 'EU_RC' | 'DRITTLAND'
    plan_key = Column(String(32), nullable=True, comment='Plan-Schluessel der Zahlung')
    raw_json = Column(Text, nullable=True, comment='Roh-JSON des Stripe-Events')
    created_at = Column(DateTime, default=utcnow, nullable=False)


class ExchangeRate(Base):
    """D-05: Taeglicher EZB-Kurs (Frankfurter API)."""
    __tablename__ = 'exchange_rates'
    __table_args__ = (
        UniqueConstraint('date', 'currency_pair', name='uix_exchange_rate_date_pair'),
        {'comment': 'Taeglicher EZB-Wechselkurs (Frankfurter-API) zum Einfrieren in api_cost_log. Status: lebt. Schreibt FX-Sync-Job; liest Cost-Berechnung in services/.'},
    )
    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False, index=True, comment='Kurs-Datum')
    currency_pair = Column(String(7), nullable=False, comment="Waehrungspaar, z.B. 'USD_EUR'")  # 'USD_EUR'
    rate = Column(Numeric(10, 6), nullable=False, comment='Wechselkurs')
    source = Column(String(16), nullable=False, default='frankfurter', comment='Kurs-Quelle')
    created_at = Column(DateTime, default=utcnow, nullable=False)


# ── Phase 04.11: Coach-Modul (Persoenliches Lernsystem) ──────────────────────

class LearningCard(Base):
    __tablename__ = 'learning_cards'
    __table_args__ = ({'comment': 'Persoenliche Lernkarten (Coach-Modul): KI-/User-Formulierungen mit Lernziel und Status. Status: lebt. Schreibt services/coaching_service.py; liest routes/learning.py:429+, services/coaching_service.py:65/170.'},)
    id                  = Column(Integer, primary_key=True)
    user_id             = Column(Integer, ForeignKey('users.id'), nullable=False)
    call_id             = Column(Integer, ForeignKey('conversation_logs.id'), nullable=True)
    category            = Column(String(100), nullable=False, comment='Kategorie der Lernkarte')
    original_suggestion = Column(Text, nullable=False, comment='Urspruenglicher KI-Vorschlag')
    final_text          = Column(Text, nullable=False, comment='Finaler (ggf. editierter) Karten-Text')
    lernziel            = Column(Text, nullable=True, comment='Lernziel der Karte')
    source              = Column(String(20), default='ki', comment="Quelle: 'ki' | 'user'")
    status              = Column(String(20), default='vorschlag', comment="Status: 'vorschlag' | 'aktiv' | 'gelernt' | 'archiviert'")
    applied_count       = Column(Integer, default=0, comment='Wie oft angewendet')
    regenerate_count    = Column(Integer, default=0, comment='Wie oft neu generiert')
    created_at          = Column(DateTime, default=utcnow)
    learned_at          = Column(DateTime, nullable=True, comment='Zeitpunkt als gelernt markiert')


class CoachingReport(Base):
    __tablename__ = 'coaching_reports'
    __table_args__ = ({'comment': 'Woechentlicher Coaching-Report je User (Read-Through-Cache). Status: lebt (Read-Through-Wochen-Cache, D-03 — NICHT write-only). Schreibt services/coaching_service.py:351; liest services/coaching_service.py:195 + Dashboard.'},)
    id                  = Column(Integer, primary_key=True)
    user_id             = Column(Integer, ForeignKey('users.id'), nullable=False)
    period_start        = Column(Date, nullable=False, comment='Wochen-Start des Report-Zeitraums')
    period_end          = Column(Date, nullable=False, comment='Wochen-Ende des Report-Zeitraums')
    calls_count         = Column(Integer, default=0, comment='Anzahl Calls im Zeitraum')
    avg_readiness_score = Column(Float, nullable=True, comment='Durchschnittlicher Readiness-Score im Zeitraum')
    strongest_phase     = Column(String(100), nullable=True, comment='Staerkste Gespraechsphase')
    weakest_phase       = Column(String(100), nullable=True, comment='Schwaechste Gespraechsphase')
    talk_ratio_user     = Column(Float, nullable=True, comment='Redeanteil Berater')
    talk_ratio_customer = Column(Float, nullable=True, comment='Redeanteil Kunde')
    report_text         = Column(Text, nullable=True, comment='Generierter Coaching-Report-Text (Dashboard-Anzeige)')
    suggested_card_json = Column(Text, nullable=True, comment='JSON: vorgeschlagene Lernkarte aus dem Report')
    created_at          = Column(DateTime, default=utcnow)


# ── Phase 04.12: Gesamt-Integration — Learning Events ────────────────────────

class LearningEvent(Base):
    __tablename__ = 'learning_events'
    __table_args__ = ({'comment': 'Cross-Modul-Lernereignisse fuer Muster-Erkennung der Integration-Engine. Status: lebt. Schreibt services/integration_engine.py:54+ (log_learning_event); liest services/integration_engine.py:163+188 (raw-SQL Muster-Erkennung).'},)
    id            = Column(Integer, primary_key=True)
    user_id       = Column(Integer, ForeignKey('users.id'), nullable=False)
    event_type    = Column(String(50), nullable=False, comment='Art des Lernereignisses')
    source_module = Column(String(20), nullable=False, comment='Ursprungs-Modul des Ereignisses')
    source_id     = Column(Integer, nullable=True, comment='ID des Quell-Objekts im Ursprungs-Modul')
    event_metadata = Column('metadata', Text, nullable=True, comment='JSON: ereignisspezifische Metadaten')
    created_at    = Column(DateTime, default=utcnow)


# ── Phase 04.14: CRM Customer Success ────────────────────────────────────────

class CrmNote(Base):
    # PUBLIC-Schema-Tabelle trotz "Crm"-Klassenname (kein {schema:crm}) — Customer-Success-Notiz pro User.
    __tablename__ = 'crm_notes'
    __table_args__ = ({'comment': 'Customer-Success-Notiz pro User (public-Schema, NICHT crm-Schema trotz Klassenname). Status: lebt. Schreibt/liest routes/admin_views.py:209, services/customer_success_service.py:48.'},)
    id         = Column(Integer, primary_key=True)
    user_id    = Column(Integer, ForeignKey('users.id'), nullable=False, unique=True)
    notiz      = Column(Text, nullable=True, comment='Freitext-Notiz zum User (Customer Success)')
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
    call_mode = Column(Text, nullable=False, comment="Call-Modus: 'cold_call' | 'meeting_consented' (CHECK ck_calls_call_mode)")
    call_type = Column(Text, nullable=True, comment='Optionale Call-Typ-Klassifikation')
    started_at = Column(DateTime(timezone=True), nullable=True, comment='Call-Startzeitpunkt (tz-aware)')
    ended_at = Column(DateTime(timezone=True), nullable=True, comment='Call-Endzeitpunkt (tz-aware)')
    transcript_storage = Column(Text, nullable=True, comment="Transkript-Speichermodus: 'none'|'ephemeral'|'consented_full' (DSGVO, CHECK)")
    transcript_expires_at = Column(DateTime(timezone=True), nullable=True, comment='Ablaufzeitpunkt fuer ephemeres Transkript (DSGVO)')
    call_summary = Column(Text, nullable=True, comment='Post-Call-Zusammenfassung')
    outcome = Column(Text, nullable=True, comment='Call-Ergebnis (CHECK ck_calls_outcome, z.B. meeting_booked/no_interest)')
    audio_health_score = Column(Float, nullable=True, comment='Audio-Qualitaets-Score des Calls')
    # --- Phase 08.23.2.TAXO2-04 Gap-Fix — Fan-In-Join-Flag gegen die Audio-Race (Migration 0027) ---
    audio_health_resolved = Column(
        Boolean, nullable=False, server_default=text('false'),
        comment="Fan-In-Join-Flag (TAXO2-04 Audio-Race-Fix): TRUE sobald der async Audio-Zustand "
                "endgueltig festgeschrieben ist (Score gesetzt ODER bewiesen kein Buffer). Der "
                "Call-Ende-Merge wartet darauf, BEVOR er ein NULL-audio_health_score als "
                "poor_audio_health wertet — verhindert die Race, in der der Merge VOR dem "
                "Audio-Thread liest. Schreibt routes/app_routes.py (api_beenden / _audio_health_bg); "
                "liest services/slow_lane.py (Merge-Gate).",
    )
    # --- Phase 08.23.2.TAXO2 LLM-Bewerter — Fan-In-Anstoss-Signal fuer den Verhaltens-Call (Migration 0028) ---
    transcript_resolved = Column(
        Boolean, nullable=False, server_default=text('false'),
        comment="Fan-In-Anstoss-Signal fuer den LLM-Verhaltens-Bewerter (Beobachtung statt Note): TRUE sobald "
                "das Transkript am Call-Ende festgeschrieben ist (Segmente geschrieben ODER bewiesen leer = "
                "resolved-als-absent). Der Judge-Anstoss (slow_lane Call-Ende-Schritt) wartet darauf, BEVOR er "
                "das Transkript an Sonnet gibt — verhindert die Race, in der gegen ein noch nicht geschriebenes "
                "Transkript bewertet wird (Punkt 26, analog audio_health_resolved). Status: lebt (TAXO2 LLM-Bewerter). "
                "Schreibt routes/app_routes.py (api_beenden); liest services/slow_lane.py (Judge-Anstoss-Gate + Merge-Gate).",
    )
    coaching_score = Column(Float, nullable=True, comment='Gesamt-Coaching-Score des Calls')
    # --- Phase 08.23.2.D.UX — Score-Breakdown (REQ-D.UX-11, Migration 0007) ---
    score_breakdown = Column(JSON_TYPE, nullable=True, comment='JSON: Aufschluesselung des Coaching-Scores')
    score_schema_version = Column(SmallInteger, nullable=False, server_default='1', comment='Schema-Version des score_breakdown')
    # --- Phase 08.23.2.D — Outcome-Erfassung (REQ-D-1) ---
    conversation_log_id = Column(Integer, ForeignKey('conversation_logs.id'), nullable=True)
    outcome_confidence = Column(Float, nullable=True, comment='KI-Konfidenz der Outcome-Klassifikation (0-1)')
    outcome_note = Column(Text, nullable=True, comment='Notiz zum Outcome')
    outcome_source = Column(Text, nullable=True, comment="Outcome-Quelle: 'ai_auto'|'ai_auto_unsicher'|'user_corrected' (CHECK)")
    # --- Phase 08.23.2.D.UX — followup_intent (REQ-D.UX-9/10, Migration 0006) ---
    followup_intent = Column(Text, nullable=False, server_default='none', comment="Follow-up-Absicht: 'none'|'callback'|'meeting'|'send_info'|'retry_internal' (CHECK)")
    meddpicc_extracted = Column(JSON_TYPE, nullable=True, comment='JSON: aus Call extrahierte MEDDPICC-Felder')
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
        {'comment': 'Zentraler Call-Datensatz der neuen Architektur (UUID-PK, Outcome/Coaching/Transkript-Storage). Status: lebt (neue Architektur Phase 08.23.2.A+). Schreibt/liest services/+routes/ der neuen Call-Pipeline; audio_health_resolved geschrieben routes/app_routes.py (api_beenden/_audio_health_bg), gelesen services/slow_lane.py (Call-Ende-Merge-Gate, TAXO2-04 Audio-Race-Fix); transcript_resolved geschrieben routes/app_routes.py (api_beenden), gelesen services/slow_lane.py (LLM-Judge-Anstoss-Gate + Merge-Gate).'},
    )


class CallEvent(Base):
    __tablename__ = 'call_events'
    id = Column(BigInteger, primary_key=True, autoincrement=True)  # BIGSERIAL on Postgres
    call_id = Column(UUID_TYPE, ForeignKey('calls.id', ondelete='CASCADE'), nullable=False)
    # FK-Verknüpfung wird in Phase 08.23.2.F nachgereicht (tenant_orgs existiert dort)
    tenant_id = Column(UUID_TYPE, nullable=True)
    event_type = Column(Text, nullable=False, comment="Event-Typ (CHECK ck_call_events_event_type, z.B. transcript_chunk/objection_detected)")
    event_ts_ms = Column(BigInteger, nullable=False, comment='Event-Zeitstempel in Unix-ms (BIGINT, 2038-sicher)')  # BIGINT required: Unix ms timestamps exceed 2^31 after 2038 (C-4 fix)
    payload = Column(JSON_TYPE, nullable=False, comment='JSON: event-spezifische Nutzdaten (GIN-indiziert)')
    created_at = Column(DateTime, default=utcnow)
    __table_args__ = (
        # Phase 08.23.2.COUNTERPART: Werte-Liste gleichgezogen mit Migration 0035
        # (counterpart_initial/counterpart_switch; die alten mode_*-Namen sind raus,
        # inkl. der 113 Bestandszeilen). Nebenbei repariert: die Deklaration hinkte
        # seit Migration 0004 hinterher (7 statt 9 Werte) — der R3-Waechter
        # tests/test_call_events_check_constraint_parity.py faengt so eine Drift ab jetzt.
        # Reine Deklaration: wirkt auf create_all (SQLite-Testpfade) + die Metadata,
        # NICHT auf Postgres — dort regiert die Migration.
        CheckConstraint(
            "event_type IN ('transcript_chunk', 'suggestion_shown', 'reaction', "
            "'phase_change', 'audio_health', 'objection_detected', 'consent_optin', "
            "'counterpart_switch', 'counterpart_initial')",
            name='ck_call_events_event_type'),
        Index('idx_call_events_call_time', 'call_id', 'event_ts_ms'),
        Index('idx_call_events_type', 'call_id', 'event_type'),
        Index('idx_call_events_payload_gin', 'payload', postgresql_using='gin'),
        {'comment': 'Append-only Event-Stream pro Call (Kind von calls) der neuen Architektur. Status: lebt (neue Architektur Phase 08.23.2.A+). Schreibt/liest Live-Call-Pipeline in services/.'},
    )


class IntentEvent(Base):
    # TAXO1-Welle 1 — DIE zentrale Ereignis-Tabelle (Single Source of Truth) fuer
    # erkannte Kunden-Intents pro Call. Verriegelter gemeinsamer Vertrag mit TAXO2/TAXO3
    # (Geruest §3). Vollstaendiges Schema ab Tag 1; handling_score_numeric bleibt NULL
    # (Scoring = TAXO2). KEIN Live-Writer in dieser Welle (matcher/analyse_loop = Welle 4).
    __tablename__ = 'intent_event'
    event_id               = Column(BigInteger, primary_key=True, autoincrement=True)  # BIGSERIAL, trivial (L-04)
    session_id             = Column(String(128), index=True, nullable=False, comment="SocketIO-sid des Live-Calls. Korreliert mit live_session._session_state[sid]. Per-Call-Filter.")
    call_id                = Column(UUID_TYPE, ForeignKey('calls.id', ondelete='CASCADE'), index=True, nullable=False, comment="Bezug zum Call-Record. HARTER FK ON DELETE CASCADE (INTERLOCK I-2 / DD-01-Konvention wie CallEvent models.py:738) — geloeschter Call raeumt Einwand + abstain_log (TAXO2-Wortlaut) DSGVO-sauber mit. A2-'lose FK' revidiert (F-08). NOT NULL ab CALLID Deploy 2 (CI-3, Migration 0025): jeder Event traegt seinen Call (call_id-Naht Plan 01 + Race-Close Plan 02); alte NULL-Testzeilen geloescht.")
    mode                   = Column(String(32), index=True, nullable=False, comment="Modus-Dimension (cold_call/meeting/...). First-Class, nicht aus Intent ableitbar. Quelle: ModeStrategy-Registry (Welle 7).")
    timestamp              = Column(DateTime(timezone=True), index=True, nullable=False, default=utcnow, comment="Erzeugungs-Zeitpunkt des Events (Zeit-Achse/Latenz-Auswertung).")
    intent_type            = Column(String(64), index=True, nullable=False, comment="Taxonomie-Wert (Geruest §1): Kern+Gemini-Werte ∪ custom_objection_*. Quelle services/intent_taxonomy.py. Geschrieben Fast+Medium Lane (Welle 4).")
    phase                  = Column(SmallInteger, index=True, nullable=True, comment="Gespraechs-Phase 1-6 als INT (getrennt vom Intent). NICHT String (K3-Falle). Quelle detect_phase (Welle 4).")
    handling_score_numeric = Column(SmallInteger, index=True, nullable=True, comment="REQ 2: Behandlungs-Note 1-3. Existiert ab Tag 1, bleibt NULL in TAXO1. Befuellung = TAXO2 (Slow Lane). KEIN Scoring-Code in TAXO1.")
    handling_status        = Column(String(16), index=True, nullable=False, server_default='pending', comment="INTERLOCK I-1: Verarbeitungs-Status der Slow-Lane-Benotung (pending|scored|abstained|failed|not_gradable). TAXO2-Wurzel-Fix gegen dreifach-ueberladene NULL. Arbeitsliste = WHERE handling_status='pending'; abstained/failed/not_gradable = abgeschlossen. not_gradable = F2-Stilllegung (PERSID Req 8): per-Ereignis-Benoter tot, drainet auf 0 deadlock-frei. Schreibt services/slow_lane.py (_persist_event_ref); liest services/slow_lane.py (_pending_events, Merge-Gate).")
    confidence             = Column(Float, nullable=True, comment="Konfidenz der Klassifikation (ui_asserted=1.0). Steuert spaeter Cue-Aufdringlichkeit + Score-Beitrag.")
    reaction_latency_ms    = Column(Integer, nullable=True, comment="Stress-Metrik: Reaktionszeit des Beraters in ms. Existiert ab Tag 1, befuellt spaeter (TAXO2).")
    interaction_id         = Column(UUID_TYPE, index=True, nullable=True, comment="Korrelations-ID pro Kundenmoment — klammert alle Emits (Fast/Medium/Button) + Cue + Reaktion + Abstain eines Moments zusammen; FK-Ziel für spätere suggestion_reactions (Phase H). call_id zu grob, event_id zu fein.")
    payload_jsonb          = Column(JSON_TYPE, nullable=False, default=dict, server_default='{}', comment="Hybrid-Rest: source, inference_basis, taxonomy_version(Pflicht non-null), abstained, speaker_role, speaker_id, is_simulation, origin_type, source_context, outcome, resolved_at_event_id, superseded_by, inference_config_id, was_correct, cue_fired, dimension_available, cue_visible, ui_state_hash. Provenance+Kontext-Felder; Pflichtfelder ab Tag 1, viele NULL in TAXO1.")
    __table_args__ = (
        {'comment': "Zentrale Ereignis-Tabelle (Single Source of Truth) fuer erkannte Kunden-Intents pro Call. Fast+Medium Lane emittieren; Slow Lane reichert IN-PLACE an (handling_score_numeric/handling_status, TAXO2). Hybrid: indizierte Kern-Spalten + payload_jsonb. Status: lebt (TAXO1). Schreibt services/einwand_keyword_matcher.py (Keyword-Fast-Lane), services/claude_service.py (Medium+QA-Lane), services/deepgram_service.py (EWB-Knopf-Emit), services/slow_lane.py (In-Place-Benotung); liest TAXO2/TAXO3-Auswertung."},
    )


class AbstainLog(Base):
    # TAXO2-Plan 03, Task 2 — Goodhart-/Bias-Schutz-Log (D-07 Rider 3): jede handling_score-
    # Abstention der Slow Lane wird mit der nachfolgenden Berater-Aussage + interaction_id
    # geloggt. Goldstaub fuer Post-Call-LLM-Nachbewertung (Flywheel/Active-Learning).
    #
    # SCHEMA-ABWEICHUNG vom PLAN (dokumentiert): der Plan spezifizierte event_id als
    # UUID -> intent_event.id ON DELETE CASCADE. Der REALE TAXO1-Vertrag (models.py:763 /
    # Migration 0016) hat KEIN id-UUID — der PK von intent_event ist event_id BIGSERIAL.
    # Darum: event_id = BigInteger -> ForeignKey('intent_event.event_id', ondelete='CASCADE').
    # Die F-08-DSGVO-Cascade-Kette calls->intent_event->abstain_log bleibt durchgehend
    # (intent_event.call_id ist harter FK CASCADE, models.py:765 / I-2).
    #
    # F-08 DSGVO: next_advisor_sentence speichert gesprochenen Wortlaut (Berater-EIGENE Stimme).
    # Harter FK ON DELETE CASCADE (DD-01-Konvention wie CallEvent models.py:741) sorgt dafuer,
    # dass beim Call-Loeschen (calls -> intent_event CASCADE -> abstain_log CASCADE) KEINE
    # verwaiste Wortlaut-Zeile bleibt. Kunden-PII faellt nicht an (Berater-Satz); falls doch
    # moeglich, anonymisiert der Aufrufer via services/anonymization.py vor dem Insert.
    __tablename__ = 'abstain_log'
    id                    = Column(UUID_TYPE, primary_key=True, default=uuid.uuid4)
    event_id              = Column(BigInteger, ForeignKey('intent_event.event_id', ondelete='CASCADE'), index=True, nullable=False, comment="HARTER FK -> intent_event.event_id ON DELETE CASCADE (F-08/DD-01). Schliesst die DSGVO-Loesch-Kette calls->intent_event->abstain_log: geloeschter Call raeumt die Wortlaut-Zeile mit. event_id = BigInteger (intent_event-PK ist BIGSERIAL, KEIN UUID — Plan-Abweichung dokumentiert).")
    interaction_id        = Column(UUID_TYPE, index=True, nullable=True, comment="Moment-Klammer (Korrelation zu intent_event.interaction_id, TAXO1). Bindet die Abstention an den Kundenmoment fuer die Post-Call-Nachbewertung. KEIN FK (interaction_id ist kein PK).")
    next_advisor_sentence = Column(Text, nullable=True, comment="Die nachfolgende Berater-Aussage zum abgewinkten Einwand (D-07 Rider 3, Goodhart-Beleg). Berater-EIGENE Stimme; bei moeglichem Kunden-PII anonymisiert (services/anonymization.py). DSGVO: Cascade-clean via event_id-FK.")
    intent_type           = Column(String(64), nullable=True, comment="Einwand-Typ-Kontext der Abstention (Korrelation/Auswertung welche Intents oft abgewinkt werden).")
    tenant_id             = Column(UUID_TYPE, index=True, nullable=False, comment="Mandanten-Abschottung (FORCE RLS tenant_isolation, NOT NULL; abgeleitet aus calls.tenant_id via Daemon-GUC Plan 03). Per-Tenant-Wall der Nachbewertung.")
    created_at            = Column(DateTime, default=utcnow)
    __table_args__ = (
        {'comment': "Goodhart-/Bias-Schutz-Log (D-07 Rider 3): jede handling_score-Abstention mit nachfolgendem Berater-Satz + interaction_id. Harter FK event_id ON DELETE CASCADE (F-08, DSGVO-clean). Goldstaub fuer Post-Call-LLM-Nachbewertung (Flywheel). Status: lebt (neu, TAXO2). Schreibt services/slow_lane.py; liest Active-Learning (Post-Launch)."},
    )


class SuggestionReaction(Base):
    # TAXO2-Plan 08 (FOLD A) — Roh-Erfassung JEDES NERVE-Vorschlags pro Call
    # (Auto-Variante Slot B + Manueller Knopf + Keyword-Slot A). insert-only,
    # Call-Ende-Flush (KEIN Live-Write, Punkt 25). suggestion_text = die am ERFASSEN
    # anonymisierte Storage-Version (Plan 09, lebender Per-SID-Cache; NIE cache=None).
    # ANGEBOT-Haelfte befuellt (FOLD A); Reaktions-Haelfte (adoption_value/...) wird
    # ab TAXO2 vom LLM-Uebernahme-Call befuellt (services/adoption_runner.py). interaction_id
    # korreliert zu intent_event.interaction_id (Tuermoeffner-Naht models.py:774 /
    # 0016:76) — KEIN harter FK (interaction_id ist kein PK).
    __tablename__ = 'suggestion_reactions'
    # ── Roh-Angebot-Spalten (JETZT befuellt) ──────────────────────────────────
    id                     = Column(UUID_TYPE, primary_key=True, default=uuid.uuid4)
    call_id                = Column(UUID_TYPE, ForeignKey('calls.id', ondelete='CASCADE'), index=True, nullable=True, comment="Bezug zum Call. HARTER FK ON DELETE CASCADE (F-08/DD-01) — geloeschter Call raeumt das Angebot (suggestion_text=potenzieller Wortlaut) DSGVO-sauber mit. nullable: Edge ohne ermittelbare call_id.")
    conversation_log_id    = Column(Integer, index=True, nullable=True, comment="Bezug zur Session. Korrelations-/Gruppier-Schluessel des Flushs.")
    interaction_id         = Column(UUID_TYPE, index=True, nullable=True, comment="Moment-Klammer (Korrelation zu intent_event.interaction_id, TAXO1). Vom Capture-Pfad IMMER gesetzt (get_or_open_moment, FOLD A-2/B1); nullable nur als Defense. KEIN FK (kein PK). Naht fuer spaeteres Uebernahme-Scoring.")
    org_id                 = Column(Integer, index=True, nullable=True, comment="Mandant (per-Berater-/Org-Filter, RLS-Ergaenzung).")
    user_id                = Column(Integer, index=True, nullable=True, comment="Berater (per-Berater-Auswertung, DEFERRED).")
    slot                   = Column(String(8), nullable=True, comment="Liefer-Kanal: A=Profil-Stichwort-instant (Keyword/Fast-Lane) | B=KI-gestreamt (Auto-Variante/Knopf-Antwort).")
    source                 = Column(String(24), index=True, nullable=True, comment="Ausloeser des Angebots: auto_variante | manual_button | keyword. Fuer A/B-Test der Antwort-Engine + systematisch-ignoriert-Analyse (TAXO3).")
    model                  = Column(String(48), nullable=True, comment="Antwort-Modell (z.B. haiku/sonnet) — A/B-Test + Selbst-Verbesserung.")
    suggestion_text        = Column(Text, nullable=True, comment="Was NERVE ausgab — ANONYMISIERTE Storage-Version (Plan 09, am Erfassen mit lebendem Per-SID-Cache; NIE cache=None). DSGVO: Cascade-clean via call_id-FK.")
    einwand_typ            = Column(String(64), nullable=True, comment="Einwand-Typ-Kontext des Angebots (Korrelation).")
    ts_offered             = Column(DateTime, nullable=True, comment="Zeitpunkt des Angebots (Live-Latenz-Diagnose: ignoriert-weil-zu-spaet vs weil-schlecht).")
    tenant_id              = Column(UUID_TYPE, index=True, nullable=False, comment="Mandanten-Abschottung (FORCE RLS tenant_isolation, NOT NULL; abgeleitet aus calls.tenant_id). Request-Flush fail-closed bei fehlendem Tenant.")
    payload_jsonb          = Column(JSON_TYPE, nullable=False, default=dict, server_default='{}', comment="Reserve fuer kuenftige Felder (confidence, einwand_typ-Detail) ohne Migration. FOLD A.")
    created_at             = Column(DateTime, default=utcnow)
    # ── Reaktions-Spalten (nullable; ab TAXO2 vom LLM-Uebernahme-Call befuellt) ──
    adoption_value         = Column(Float, nullable=True, comment="Uebernahme-Grad 0-1 (voll/teilweise/ignoriert). Befuellt ab TAXO2 LLM-Uebernahme-Call. Schreibt services/adoption_runner.py (gebuendelter Sonnet-Call am Call-Ende); gelesen: Uebernahme-Auswertung post-Launch.")
    following_utterance_ref = Column(String(128), nullable=True, comment="Verweis/Hash auf die folgende Berater-Aeusserung (Uebernahme-Beleg). Befuellt ab TAXO2 LLM-Uebernahme-Call (services/adoption_runner.py); gelesen: Auswertung post-Launch.")
    reaction_class         = Column(String(24), nullable=True, comment="Klassifikation der Reaktion (voll|teilweise|ignoriert). Befuellt ab TAXO2 LLM-Uebernahme-Call (services/adoption_runner.py); gelesen: Auswertung post-Launch.")
    __table_args__ = (
        Index('ix_suggestion_reactions_call_id', 'call_id'),
        Index('ix_suggestion_reactions_interaction_id', 'interaction_id'),
        Index('ix_suggestion_reactions_source', 'source'),
        Index('ix_suggestion_reactions_conversation_log_id', 'conversation_log_id'),
        Index('ix_suggestion_reactions_org_id', 'org_id'),
        Index('ix_suggestion_reactions_user_id', 'user_id'),
        Index('ix_suggestion_reactions_tenant_id', 'tenant_id'),
        {'comment': "Roh-Erfassung jedes NERVE-Vorschlags pro Call (Auto-Variante Slot B + Manueller Knopf + Keyword), insert-only + anonymisiert, Call-Ende-Flush (KEIN Live-Write). ANGEBOT-Haelfte befuellt (FOLD A); Reaktions-Haelfte (adoption_value/reaction_class/following_utterance_ref) ab TAXO2 vom LLM-Uebernahme-Call befuellt. call_id harter FK CASCADE (F-08). Status: lebt (neu, TAXO2 FOLD A). Schreibt services/suggestion_capture.py (Flush) + services/live_session.py (RAM) + services/adoption_runner.py (Reaktions-Haelfte adoption_value/reaction_class/following_utterance_ref, gebuendelter LLM-Uebernahme-Call am Call-Ende); liest Uebernahme-Auswertung (post-Launch)."},
    )


# ── Phase 08.23.2.METRIK-1 — Schild-Texte, zeichengleich zu alembic 0040 (Punkt 23) ──
_SCHILD_RUBRIC_STATUS = 'Bewertungs-Status. Werte judged, scored, pending, judge_failed, transcript_not_resolved, not_gradable. NULL bedeutet noch nicht gelaufen. Bei not_gradable steht der Grund in payload_jsonb unter dem Schluessel reason. Ab METRIK-1 gibt es zwei lebende Gruende - poor_audio_health (Audio-Tor, unveraendert) und too_little_speech (Sprech-Substanz-Tor, weniger als zwanzig gesprochene Berater-Woerter; die Zahl der Redeabschnitte ist reiner Messwert und KEINE Bedingung). Welcher Weg genommen wurde, steht daneben im Schluessel tor_zweig. Der Alt-Grund too_few_high_confidence_events wird seit METRIK-1 NICHT mehr geschrieben, steht aber weiter auf Alt-Zeilen in der Datenbank - der Anzeige-Zweig dafuer bleibt deshalb erhalten. Schreibt services/slow_lane.py; liest routes/dashboard.py und templates/session_detail.html.'
_SCHILD_RUBRIC_OBSERVATIONS = 'Beobachtungen und WOERTLICHE Beleg-Zitate je fester Dimension (LLM-Verhaltens-Bewerter, Beobachtung statt Note). Form dim_key auf Liste von beobachtung und beleg_zitat. SICHTBAR fuer den Nutzer (als KI-Einschaetzung gelabelt). Drei reservierte Unterstrich-Schluessel stehen daneben und sind KEINE Dimensionen. _compliance traegt das Sicherheits-Hard-Gate mit verletzt und beleg_zitat. _kopfzeile traegt ab METRIK-1 den besten Moment mit beobachtung und beleg_zitat, geliefert vom Modell im SELBEN Aufruf (kein zweiter LLM-Aufruf). _fokus traegt die eine Sache fuers naechste Mal mit focus_key, count, satz und beleg; sie wird vom CODE berechnet (services/fokus_katalog.py), nie vom Modell, und focus_key NULL bedeutet ehrlich kein Kriterium verletzt - auf deutschem Bestand ist das der Normalfall, weil der Katalog englisch ist. JEDES Beleg-Zitat in dieser Spalte ist vor dem Speichern gegen das Transkript geprueft (services/slow_lane.py, Drei-Wege-Behandlung); ein erfundenes Zitat loescht die ganze Beobachtung, ein Beinahe-Treffer bleibt und wird gezaehlt. Status lebt. Schreibt services/judge_runner.py und services/slow_lane.py; liest routes/dashboard.py und templates/session_detail.html.'
_SCHILD_RUBRIC_PAYLOAD = 'Reserve, Training-only-Felder (was_correct, scenario_id, ground_truth_score) und ab METRIK-1 zwei feste Bereiche. Bei not_gradable die Begruendung samt Messwerten - reason, schema, berater_woerter, redeabschnitte, sprechzeit_ms, high_conf_events, tor_zweig. redeabschnitte ist dort ein reiner Diagnose-Wert und keine Bedingung. tor_zweig nennt den genommenen Weg - genug_woerter, zu_wenig_woerter, keine_berater_zeile oder wortzahl_unbekannt_durchgelassen; der letzte laesst bewusst DURCH und erscheint deshalb nur an judged-Zeilen. Eine Zahl NULL heisst dort UNBEKANNT, nie null Woerter; sie ist die Grundlage der Tor-Nachjustierung nach rund hundert echten Anrufen. Bei judged der Zaehler der Zitat-Pruefung unter dem Schluessel beleg_check mit geprueft, treffer, near_miss, verworfen und compliance_beleg_verworfen. Dieser Zaehler ist ein ABSOLUTWERT des Laufs - der Upsert ersetzt payload_jsonb vollstaendig (ON CONFLICT DO UPDATE), ein Wiederholungslauf desselben Anrufs zaehlt daher per Bauart nicht doppelt. Schreibt services/slow_lane.py; liest routes/dashboard.py, templates/session_detail.html und services/beleg_check_counter.py (Prozess-Zaehler der Founder-Sicht).'


class RubricScore(Base):
    # TAXO2-Plan 01 — DIE Single Source der Benotung (BARS + Proration), Live + Training
    # (SPEC Req 1). Hybrid: indizierte Kern-Spalten + payload_jsonb-Reserve. KEIN Schreiber
    # in dieser Welle — die Engine (Plan 02/04) ist der einzige Schreiber. call_id harter FK
    # ON DELETE CASCADE (F-08/DD-01-Konvention wie CallEvent models.py:741). Partieller
    # Unique-Index ux_rubric_score_live_call_id (call_id WHERE origin='live') macht Plan-04
    # ON CONFLICT valide (F-03); Training-Zeilen (origin='training') bleiben frei.
    # FORCE ROW LEVEL SECURITY (D-11) — greift auch fuer Owner nerve_app; die M-4-Daemon-GUC-
    # Falle (Schreiber ohne Request-Context) ist hier nur dokumentiert/getestet, Fix = Plan 04.
    __tablename__ = 'rubric_score'
    id                    = Column(UUID_TYPE, primary_key=True, default=uuid.uuid4)
    call_id               = Column(UUID_TYPE, ForeignKey('calls.id', ondelete='CASCADE'), index=True, nullable=True, comment="Bezug zum Call. HARTER FK ON DELETE CASCADE (F-08/DD-01-Konvention wie CallEvent models.py:741) — geloeschter Call raeumt die Note DSGVO-sauber mit. nullable: Training-Zeilen ohne call_id.")
    conversation_log_id   = Column(Integer, index=True, nullable=True, comment="Bezug zur Session/conversation_logs. Live=aus Call, Training=aus Trainings-Session.")
    session_mode          = Column(String(32), index=True, nullable=False, comment="Modus der Bewertung: cold_call|meeting_consented|training (N-4, EXAKT calls.call_mode-Werte + training, kein 'meeting'-Kurzform). Bestimmt den Gewichtssatz (D-01/D-04).")
    origin                = Column(String(16), index=True, nullable=False, comment="Herkunft der Note: live|training. SPEC Req 1 — eine Tabelle fuer beide Welten. Steuert den partiellen Unique-Index (F-03).")
    coaching_score        = Column(Float, nullable=True, comment="Gesamt-Kopf-Zahl (0-100). NULL wenn <50% Gewicht messbar (Proration, D-02) oder not_gradable (D-09). Spiegel von calls.coaching_score (Plan 04). [ALT-Marker-Engine, write-stop ab LLM-Bewerter TAXO2 — nicht mehr befuellt; Cutover services/slow_lane.py Plan 03; nicht geloescht (Foundation-Register/Punkt 20)].")
    is_provisional        = Column(Boolean, nullable=False, default=False, comment="Vorlaeufig-Marker (D-08): Score ueber der 50%-Schwelle aber mit weggeprorateten Dimensionen. Anzeige 999.2. [ALT-Marker-Engine, write-stop ab LLM-Bewerter TAXO2 — nicht mehr befuellt; Cutover services/slow_lane.py Plan 03; nicht geloescht (Foundation-Register/Punkt 20)].")
    measured_weight_pct   = Column(Float, nullable=True, comment="Anteil messbaren Gewichts am modus-konfigurierten Maximum (D-02/D-08). <0.5 -> coaching_score NULL. [ALT-Marker-Engine, write-stop ab LLM-Bewerter TAXO2 — nicht mehr befuellt; Cutover services/slow_lane.py Plan 03; nicht geloescht (Foundation-Register/Punkt 20)].")
    unmeasured_dimensions = Column(JSON_TYPE, nullable=True, comment="Liste der nicht gewerteten Dimensionen + Grund (n/a vs vergeigt, D-08). Goldstaub fuer 999.2-Erklaerung + ML. [ALT-Marker-Engine, write-stop ab LLM-Bewerter TAXO2 — nicht mehr befuellt; Cutover services/slow_lane.py Plan 03; nicht geloescht (Foundation-Register/Punkt 20)].")
    dimensions            = Column(JSON_TYPE, nullable=True, comment="Volle Aufschluesselung pro Dimension (D-05/Req 5): je Dim {score, weight, available, sample_size, beleg_ref, marker[]}. Beleg-Referenz = Transkript-/intent_event-Verweis, KEIN freier LLM-Text. [ALT-Marker-Engine, write-stop ab LLM-Bewerter TAXO2 — nicht mehr befuellt; Cutover services/slow_lane.py Plan 03; nicht geloescht (Foundation-Register/Punkt 20)].")
    status                = Column(String(24), nullable=True, comment=_SCHILD_RUBRIC_STATUS)
    tenant_id             = Column(UUID_TYPE, index=True, nullable=False, comment="Mandanten-Abschottung (D-11 FORCE RLS, NOT NULL). Abgeleitet aus calls.tenant_id via Daemon-GUC (Plan 04 erbt Plan-03-A1-Klammer).")
    payload_jsonb         = Column(JSON_TYPE, nullable=False, default=dict, server_default='{}', comment=_SCHILD_RUBRIC_PAYLOAD)
    score_schema_version  = Column(SmallInteger, nullable=False, default=1, comment="Format-Version der Aufschluesselung fuer spaetere Bumps.")
    # ── TAXO2 LLM-Bewerter — Beobachtung statt Note (Plan 02, Migration 0029) ─────────────────
    observations_jsonb    = Column(JSON_TYPE, nullable=False, default=dict, server_default='{}',
                                   comment=_SCHILD_RUBRIC_OBSERVATIONS)
    ratings_jsonb         = Column(JSON_TYPE, nullable=False, default=dict, server_default='{}',
                                   comment="INTERNE grobe Auspraegung schwach/ok/stark je Dimension (Lern-Signal, Soll-Verhalten §6). NIE an den Nutzer ausgegeben. Form {dim_key:schwach|ok|stark}. Status: lebt (TAXO2 LLM-Bewerter, intern). Schreibt services/judge_runner.py; liest spaeter Korrelation/Lernen (post-Launch).")
    created_at            = Column(DateTime, default=utcnow)
    __table_args__ = (
        # F-03 partieller Unique-Index: Plan 04 ON CONFLICT (call_id) WHERE origin='live'
        # braucht genau diesen Index (index=True allein reicht NICHT). Partiell -> Training-Zeilen
        # (origin='training', call_id NULL/mehrfach) kollidieren NICHT. `text` = Modul-Import
        # (models.py:2), NICHT vom Spalten-Attribut ueberdeckt (vgl. TranscriptSegment-Hinweis).
        Index('ux_rubric_score_live_call_id', 'call_id', unique=True, postgresql_where=text("origin = 'live'")),
        {'comment': "Beobachtungen + Beleg-Zitate + interne Auspraegung (LLM-Bewerter, Soll-Verhalten §6), nicht mehr maschinelle Note. Eine Zeile pro bewerteter Call/Session. Hybrid: indizierte Kern-Spalten + observations_jsonb/ratings_jsonb + payload_jsonb. call_id harter FK CASCADE (F-08/DD-01). Partieller Unique-Index (call_id, origin=live) fuer idempotenten Upsert (F-03). FORCE ROW LEVEL SECURITY (D-11). Status: lebt (TAXO2 LLM-Bewerter). Schreibt services/judge_runner.py (Plan 03); liest routes/dashboard.py (Preview Plan 05)."},
    )


class ModeWeightConfig(Base):
    # TAXO2-Plan 02 — Modus-Gewichtssatz fuer die Noten-Engine (D-01/D-04, laufzeit-tunbar
    # Punkt 12). Pro (session_mode, dimension) genau eine Zeile: config-Gewicht + config-an/aus-
    # Flag + Tor-1-Konfidenzschwelle (D-03) + Kaltakquise-Marker (partial_marker/indirekt_erkannt,
    # D-04). Globale Config-Tabelle (KEINE per-Call-Daten, KEIN tenant_id, KEINE RLS noetig) ->
    # Owner nerve_app. session_mode traegt EXAKT calls.call_mode-Werte {cold_call,
    # meeting_consented} + 'training' (N-4, KEIN 'meeting'-Kurzform). Liest services/rubric_engine.py
    # (Plan 04 laedt den Satz beim compute); schreibt Migration-Seed/Admin. KEIN Schreiber in der
    # App. UNIQUE(session_mode, dimension).
    __tablename__ = 'mode_weight_config'
    id               = Column(Integer, primary_key=True, autoincrement=True)
    session_mode     = Column(String(32), nullable=False, comment="Modus: cold_call|meeting_consented|training (N-4, EXAKT calls.call_mode-Werte + training, KEIN 'meeting'-Kurzform). Lookup-Schluessel der Engine (aus calls.call_mode/origin='training').")
    dimension        = Column(String(48), nullable=False, comment="Dimensions-Key (ASCII): vorwand_behandlung/kaufsignal_nutzung/aufschub_behandlung/phasen_technik/fragen_qualitaet/gespraechsfuehrung/abschluss_fuehrung. Korreliert mit services/rubric_dimensions.py DIMENSIONS.")
    weight           = Column(Float, nullable=False, comment="Config-Gewicht der Dimension im Modus (D-01/D-04). 0 = config-AUS = Dimension gilt im Modus nicht (Ausschluss-Grund config_off, getrennt von Proration-Drop).")
    enabled          = Column(Boolean, nullable=False, server_default=text('true'), default=True, comment="config-an-Flag (D-01). enabled=false ODER weight<=0 -> Dimension config_off (faellt VOR der Messbarkeit raus, eigener Ausschluss-Grund).")
    partial_marker   = Column(String(48), nullable=True, comment="Teil-Messbarkeits-Marker (D-04), z.B. 'sprechdisziplin' fuer Kaltakquise-Gespraechsfuehrung (nur Monolog/Tempo messbar, Talk-Share aus). NULL = voll messbar.")
    indirekt_erkannt = Column(Boolean, nullable=False, server_default=text('false'), default=False, comment="(indirekt erkannt)-Marker (D-04): Kaltakquise-Vorwand/Aufschub/Kaufsignal werden indirekt erkannt -> 999.2 zeigt geringere statistische Belastbarkeit. NICHT killen, Unsicherheit transparent machen.")
    confidence_gate  = Column(Float, nullable=True, comment="Tor-1-Konfidenzschwelle (D-03) fuer Ereignis-Messbarkeit. NULL -> Engine-Default 0.70. Niedrig-Konfidenz-Ereignisse zaehlen nicht fuer >=1/messbar (garbage-in-Schutz).")
    updated_at       = Column(DateTime, default=utcnow, onupdate=utcnow)
    __table_args__ = (
        UniqueConstraint('session_mode', 'dimension', name='uq_mode_weight_config_mode_dim'),
        {'comment': "Modus-Gewichtssatz fuer die Noten-Engine (D-01/D-04, laufzeit-tunbar Punkt 12). Pro Modus+Dimension: Gewicht, config-an/aus, Tor-1-Konfidenzschwelle. Globale Config (kein tenant_id, keine RLS). Status: lebt (neu, TAXO2). Liest services/rubric_engine.py; schreibt Admin/Seed (Migration)."},
    )


# ── Phase 08.23.2.ZEITSTEMPEL-1 — Schild-Texte, zeichengleich zu alembic 0039 (Punkt 23) ──
_SCHILD_START_MS = 'Beginn des Abschnitts in ms auf der DEEPGRAM-AUDIO-Achse (Startzeit des ersten Wortobjekts). NICHT dieselbe Achse wie ts_ms (Wall-Clock, auf ganze Sekunden gerundet) - nie gegeneinander rechnen. NULL = unbekannt (Zeile ohne Deepgram-Wortzeiten, z.B. EWB-Knopf-Zeile, oder Anruf vor ZEITSTEMPEL-1). Verworfen wurde die dritte Variante (ts_ms einfach genau machen): dann stuenden Alt-Anrufe sekundengenau und Neu-Anrufe millisekundengenau in DERSELBEN Spalte, ein Vergleich ueber die Zeit ergaebe still Unsinn. UNVERIFIED: ueberlappende Deepgram-Endergebnisse sind nicht ausgeschlossen (endpointing=900 plus smart_format); ein Leser muss end_ms minus start_ms kleiner 0 und negative Luecken abfangen. Eine negative Luecke zum Vorgaenger ist zugleich das gewollte Naht-Signal - es gibt bewusst KEINEN Naht-Marker und keinen Versatz.'
_SCHILD_END_MS = 'Ende des Abschnitts in ms auf der DEEPGRAM-AUDIO-Achse (Endzeit des letzten Wortobjekts). end_ms minus start_ms ist die Sprech-Dauer des Abschnitts - Grundlage fuer Redeanteil, Sprechtempo, Redeblock-Laenge und Pausenlaenge (gerechnet in METRIK-1, nicht hier). NULL = unbekannt, nie 0.'
_SCHILD_WORD_COUNT = 'Anzahl gesprochener Woerter aus den ROHEN Deepgram-Wortobjekten, gezaehlt VOR der Anonymisierung. Nicht aus dem anonymisierten Text zaehlen: der Platzhalter [PERSON_A] steht fuer zwei gesprochene Woerter. NULL = unbekannt; 0 hiesse hat nichts gesagt und wuerde jeden Mittelwert verfaelschen. Bekannte Kante: ein Endergebnis mit Text, aber ohne Wortobjekte (nur Satzzeichen) liefert NULL, obwohl gesprochen wurde.'
_SCHILD_TABELLE = 'Anonymisierte Transkript-Segmente pro Call (Kind von conversation_logs, Pipeline B). Status: lebt (neue Architektur Phase 08.23.2.A+). ZWEI Zeitachsen, nie mischen: ts_ms = Wall-Clock ab Call-Start auf ganze Sekunden gerundet, nur fuer die Reihenfolge; start_ms/end_ms = Deepgram-Audio-Zeit in ms, nur fuer Messgroessen. Naht-Luecken (neue Verbindung, zurueckgehaltenes Audio) erkennt ein Leser an der Divergenz beider Uhren bzw. an einer negativen Differenz - es gibt bewusst KEINEN Naht-Marker und keinen Versatz. GEPRUEFT UND OFFEN: im Cold-Call-Modus sind Redeanteil und Redeblock-Laenge strukturell NICHT berechenbar (diarize=is_meeting in services/deepgram_service.py:490, log_sp hart 0 in services/deepgram_service.py:113-118) - jedes Segment landet als berater, der Redeanteil ist dort IMMER exakt 100 Prozent, eine Konstante die wie eine Messung aussieht. Sprechtempo und Pausenlaenge bleiben im Cold-Call gueltig; im Meeting-Modus kommen alle vier heraus. Abschnitte mit Art-9-Treffer oder Anonymisierungs-Fehler werden seit ZEITSTEMPEL-1 MIT echten Zeiten und dem neutralen Platzhalter-Text [nicht gespeichert] geschrieben (Weg C) - vorher entstand gar keine Zeile und ihre Sprech-Zeit fehlte still in jeder Summe. Gebuendelt am Call-Ende geschrieben - alle created_at einer Gruppe sind identisch, created_at ist KEIN Zeit-Anker (Punkt 26). Schreibt routes/app_routes.py api_beenden (Quelle: RAM-Log aus services/deepgram_service.py on_message und EWB-Knopf); liest services/adoption_runner.py, services/judge_runner.py, services/slow_lane.py (ankert auf created_at), routes/learning.py, routes/settings.py.'


class TranscriptSegment(Base):
    __tablename__ = 'transcript_segments'
    id                  = Column(BigInteger, primary_key=True, autoincrement=True)  # BIGSERIAL
    conversation_log_id = Column(Integer, ForeignKey('conversation_logs.id', ondelete='CASCADE'), nullable=False)
    ts_ms               = Column(Integer, nullable=False, comment='ms ab Call-Start, fuer Reihenfolge')        # ms ab Call-Start, fuer Reihenfolge
    speaker             = Column(Text, nullable=False, comment="Sprecher: 'berater'|'kunde'|'system' (CHECK)")           # 'berater'|'kunde'|'system'
    text                = Column(Text, nullable=False, comment='Anonymisierter Segment-Text (Pipeline B)')           # anonymisierter Text (Pipeline B)
    start_ms            = Column(Integer, nullable=True, comment=_SCHILD_START_MS)
    end_ms              = Column(Integer, nullable=True, comment=_SCHILD_END_MS)
    word_count          = Column(Integer, nullable=True, comment=_SCHILD_WORD_COUNT)
    # WICHTIG: das Spalten-Attribut `text` ueberdeckt im Klassen-Koerper die importierte
    # sqlalchemy-Funktion `text` -> server_default=text('now()') wuerde das Column-Objekt
    # aufrufen (TypeError). Daher func.now() (Modul-Ebene, nicht ueberdeckt). DDL-Aequivalent
    # zur Migration 0010 `DEFAULT now()` (CLAUDE.md Punkt 21 ORM/DDL-Konsistenz).
    created_at          = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        CheckConstraint("speaker IN ('berater', 'kunde', 'system')", name='ck_transcript_segments_speaker'),
        Index('idx_transcript_segments_conv_ts', 'conversation_log_id', 'ts_ms'),
        {'comment': _SCHILD_TABELLE},
    )


class TenantOrg(Base):
    # Phase 08.23.2.G-MEET Wave 1 — UUID tenancy root (parallel register beside Integer org_id,
    # bridged by legacy_org_id). public schema (tenancy infra, NOT crm) -> no schema= table_arg.
    # ORM/DDL-konsistent zu Migration 0011 (CLAUDE.md Punkt 21 — ORM ist die Test-Schema-Quelle).
    __tablename__ = 'tenant_orgs'
    __table_args__ = ({'comment': 'UUID-Tenancy-Root parallel zur Integer-org_id (Bruecke via legacy_org_id), public-Schema. Status: Reserve/Foundation (FK-Aktivierung Phase 08.23.2.F). Schreibt/liest noch nicht aktiv — Foundation fuer UUID-Tenancy.'},)
    id            = Column(UUID_TYPE, primary_key=True, default=uuid.uuid4)
    legacy_org_id = Column(Integer, ForeignKey('organisations.id'), nullable=False, unique=True, comment='Bruecke zur Integer-organisations.id (Tenancy-Migration)')
    name          = Column(Text, nullable=False, comment='Tenant-/Organisations-Name')
    # func.now() (Modul-Ebene) wie TranscriptSegment — DDL-Aequivalent zu 0011 `DEFAULT now()`.
    created_at    = Column(DateTime(timezone=True), server_default=func.now())


# --- Phase 08.23.2.G-MEET Wave 2 — crm-Schema-Modelle (DDL-parity zu Migration 0012) ---
# Alle EXPLIZIT schema-qualifiziert via __table_args__ {'schema': 'crm'} — bewiesen noetig:
# nerve_app rolconfig ist EMPTY (kein role search_path), die ORM MUSS schema-qualifizieren.
# Das {'schema': 'crm'}-Dict MUSS das LETZTE Element des __table_args__-Tuples sein.
# Diese Modelle sind die SQLite-in-memory-Test-Schema-Quelle (CLAUDE.md Punkt 21) — sie muessen
# 0012's DDL Spalte-fuer-Spalte (und Index-fuer-Index) spiegeln.

class Account(Base):
    __tablename__ = 'accounts'
    id         = Column(UUID_TYPE, primary_key=True, default=uuid.uuid4)
    tenant_id  = Column(UUID_TYPE, nullable=False)   # NOT NULL auf neuen Tabellen (D-07); FK DB-seitig zu tenant_orgs
    name       = Column(Text, nullable=False, comment='Account-/Firmen-Name')
    domain     = Column(Text, nullable=True, comment='Firmen-Domain')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        # MM-05 (Cross-AI): atomare Doppel-Submit-Sicherung — DDL-parity zu Migration 0014.
        UniqueConstraint('tenant_id', 'name', name='uq_accounts_tenant_name'),
        Index('idx_accounts_tenant', 'tenant_id'),
        {'schema': 'crm', 'comment': 'Account-Stammdaten je Tenant. Status: lebt (crm, RLS-isoliert). Schreibt/liest services/crm_service.py + routes/crm_export.py.'},   # MUSS letztes Element sein; explizite Schema-Qualifizierung (kein search_path-Verlass)
    )


class Contact(Base):
    __tablename__ = 'contacts'
    id         = Column(UUID_TYPE, primary_key=True, default=uuid.uuid4)
    tenant_id  = Column(UUID_TYPE, nullable=False)
    account_id = Column(UUID_TYPE, nullable=True)
    name       = Column(Text, nullable=False, comment='Kontakt-Name')
    email      = Column(Text, nullable=True, comment='Kontakt-Email')
    phone      = Column(Text, nullable=True, comment='Kontakt-Telefon')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        Index('idx_contacts_tenant', 'tenant_id'),
        Index('idx_contacts_account_id', 'account_id'),
        {'schema': 'crm', 'comment': 'Ansprechpartner je Account/Tenant. Status: lebt (crm, RLS-isoliert). Schreibt/liest services/crm_service.py + routes/crm_export.py.'},
    )


class AccountMemory(Base):
    __tablename__ = 'account_memory'
    id                = Column(UUID_TYPE, primary_key=True, default=uuid.uuid4)
    tenant_id         = Column(UUID_TYPE, nullable=False)
    account_id        = Column(UUID_TYPE, nullable=True)
    contact_id        = Column(UUID_TYPE, nullable=True)
    schema_version    = Column(SmallInteger, nullable=False, server_default='1', comment='Schema-Version des MEDDPICC-Memory-Datensatzes (D-19)')  # D-19
    # MEDDPICC 8 ASCII keys leben INSIDE der meddpicc JSONB:
    # metrics, economic_buyer, decision_criteria, decision_process, paper_process,
    # pain, champion, competition.
    meddpicc          = Column(JSON_TYPE, nullable=False, server_default='{}', comment='MEDDPICC-JSONB (8 ASCII-Keys: metrics/economic_buyer/decision_criteria/decision_process/paper_process/pain/champion/competition)')
    context_hooks     = Column(JSON_TYPE, nullable=False, server_default='[]', comment='JSON-Array: Kontext-Hooks fuer PreCall-Briefing')
    last_call_summary = Column(Text, nullable=True, comment='Zusammenfassung des letzten Calls')
    anonymized_at     = Column(DateTime(timezone=True), nullable=True, comment='Anonymisierungs-Zeitpunkt (Variante A state-tracking, Wave 3)')   # Variante A state-tracking (Wave 3)
    updated_at        = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        CheckConstraint("account_id IS NOT NULL OR contact_id IS NOT NULL", name='ck_account_memory_acc_or_con'),
        Index('idx_account_memory_tenant', 'tenant_id'),
        Index('idx_account_memory_account_id', 'account_id'),
        Index('idx_account_memory_contact_id', 'contact_id'),
        Index('idx_account_memory_meddpicc_gin', 'meddpicc', postgresql_using='gin'),
        {'schema': 'crm', 'comment': 'MEDDPICC-Gedaechtnis je Account (PreCall-Briefing-Quelle). Status: lebt (Foundation, crm; D-02 — NICHT toter Import). Schreibt G-MEET-Pipeline; liest services/precall_service.py:175.'},
    )


class Meeting(Base):
    __tablename__ = 'meetings'
    id             = Column(UUID_TYPE, primary_key=True, default=uuid.uuid4)
    tenant_id      = Column(UUID_TYPE, nullable=False)
    account_id     = Column(UUID_TYPE, nullable=True)
    contact_id     = Column(UUID_TYPE, nullable=True)
    call_id        = Column(UUID_TYPE, nullable=True, comment='Soft-Link zu public.calls.id, KEIN FK (D-08). Wird beim Speichern gegen den Besitzer geprueft (services/live_session.py::call_belongs_to, eigener Anruf ODER gleicher Mandant) — vorher wurde der geposteten Wert ungeprueft uebernommen. Status: wird befuellt, hat KEINEN Leser.')   # soft link zu public.calls.id, KEIN FK (D-08)
    scheduled_at   = Column(DateTime(timezone=True), nullable=True, comment='Geplanter Meeting-Zeitpunkt')
    notes          = Column(Text, nullable=True, comment='Meeting-Notizen')
    schema_version = Column(SmallInteger, nullable=False, server_default='1', comment='Schema-Version des Meeting-Datensatzes')
    created_at     = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        Index('idx_meetings_tenant', 'tenant_id'),
        Index('idx_meetings_account_id', 'account_id'),
        Index('idx_meetings_contact_id', 'contact_id'),
        {'schema': 'crm', 'comment': 'Termin-/Meeting-Datensaetze je Tenant (PiP-Termin-Form, G-MEET). Status: lebt (crm, RLS-isoliert, tenant_isolation FORCE). Schreibt routes/crm_export.py::save_meeting (POST /crm/meetings, seit 08.23.2.SOFORT-2 mit Besitzpruefung der call_id) + services/crm_service.py + routes/app_routes.py; liest bislang KEIN Produktionspfad.'},
    )


# --- Meeting-Modal-Increment (08.23.2.G-MEET Plan 04) — crm.user_preferences (DDL-parity zu Migration 0014) ---
# auto_save_meeting DEFAULT false = DSGVO Opt-in off-by-default (Art. 25 Abs. 2), serverseitig gehonort.
# user_id ist SOFT-LINK zu public.users.id (Integer, KEIN Mauer-FK, D-08-Analogie); serverseitig aus
# g.user.id gesetzt, nie aus Client-Wert (MM-07). Schema-qualifiziert via {'schema': 'crm'} (LETZTES Element).

class UserPreference(Base):
    __tablename__ = 'user_preferences'
    id                = Column(UUID_TYPE, primary_key=True, default=uuid.uuid4)
    tenant_id         = Column(UUID_TYPE, nullable=False)
    user_id           = Column(Integer, nullable=False)          # soft link zu public.users.id, KEIN FK (D-08); serverseitig aus g.user.id (MM-07)
    auto_save_meeting = Column(Boolean, nullable=False, server_default=text('false'), comment='DSGVO Opt-in (Art. 25 Abs. 2), default OFF, serverseitig gehonort')  # DSGVO default OFF
    schema_version    = Column(SmallInteger, nullable=False, server_default='1', comment='Schema-Version des User-Preference-Datensatzes')
    created_at        = Column(DateTime(timezone=True), server_default=func.now())
    updated_at        = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        UniqueConstraint('tenant_id', 'user_id', name='uq_user_preferences_tenant_user'),
        Index('idx_user_preferences_tenant', 'tenant_id'),
        {'schema': 'crm', 'comment': 'Nutzer-Praeferenzen je Tenant (z.B. auto_save_meeting DSGVO-Opt-in). Status: lebt (crm, RLS-isoliert). Schreibt/liest services/crm_service.py + routes/app_routes.py (g.user.id, MM-07).'},
    )


# --- Phase 08.23.2.G-MEET Wave 3 — training-Schema DPO-Foundation (DDL-parity zu Migration 0013) ---
# preference_pairs wird HIER als ORM/DDL-Quelle definiert, aber von Phase 08.23.2.E BEFUELLT
# (W-6-Grenze: das crm-Row -> DPO-Triple-Mapping gehoert Phase E, ist noch nicht spezifiziert).
# Schema-qualifiziert via {'schema': 'training'} (LETZTES __table_args__-Element) — KEIN search_path-Verlass.
# EXPLIZIT KEIN ForeignKey auf irgendeine crm.*-Tabelle (D-17, DSGVO-Mauer) — source_call_hash ist
# ein Einweg-Hash, kein call_id-FK. UUID-PK -> keine Sequence.

class PreferencePair(Base):
    __tablename__ = 'preference_pairs'
    pair_id            = Column(UUID_TYPE, primary_key=True, default=uuid.uuid4)
    prompt             = Column(JSON_TYPE, nullable=False, comment='JSON: DPO-Prompt (Kontext/Einwand)')
    chosen             = Column(JSON_TYPE, nullable=False, comment='JSON: bevorzugte (chosen) Antwort im DPO-Triple')
    rejected           = Column(JSON_TYPE, nullable=False, comment='JSON: abgelehnte (rejected) Antwort im DPO-Triple')
    batch_id           = Column(UUID_TYPE, nullable=False, comment='Batch-Gruppierung der Generierung')
    anonymizer_version = Column(Text, nullable=False, comment='Version der Anonymisierungs-Pipeline')
    source_call_hash   = Column(Text, nullable=True, comment='Einweg-Hash der Quell-Call (D-17, kein call_id-FK ueber die DSGVO-Mauer)')   # Hash, NICHT call_id (D-17, kein FK ueber die Mauer)
    labeller           = Column(Text, nullable=True, comment='Labeller-Kennung')
    rating_chosen      = Column(SmallInteger, nullable=True, comment='Rating der chosen-Antwort')
    rating_rejected    = Column(SmallInteger, nullable=True, comment='Rating der rejected-Antwort')
    rationale          = Column(Text, nullable=True, comment='Begruendung der Praeferenz')
    split              = Column(Text, nullable=True, comment="Datensatz-Split: 'train'|'val'|'test' (CHECK ck_preference_pairs_split)")
    schema_version     = Column(SmallInteger, nullable=False, server_default='1', comment='Schema-Version des Preference-Pair-Datensatzes (D-19)')  # D-19
    created_at         = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        CheckConstraint("split IN ('train', 'val', 'test') OR split IS NULL", name='ck_preference_pairs_split'),
        Index('idx_preference_pairs_batch', 'batch_id'),
        {'schema': 'training', 'comment': 'DPO-Praeferenz-Triples (DPO-Foundation). Status: Reserve/Foundation (0 aktive Befueller; Phase 08.23.2.E befuellt). Schreibt noch nicht aktiv; liest spaeterer DPO-Trainings-Job.'},   # MUSS letztes Element sein; explizite Schema-Qualifizierung
    )
