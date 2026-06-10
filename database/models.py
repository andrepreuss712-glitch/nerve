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
    billing_vat_id       = Column(String(50), comment='USt-IdNr.')
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
    vorname             = Column(String(100), comment='Vorname')
    nachname            = Column(String(100), comment='Nachname')
    onboarding_done     = Column(Boolean, default=False, comment='Flag: Onboarding abgeschlossen')
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
    # H-18: Email-Confirmation-Flag (Microsoft-OAuth Email-Hijacking-Mitigation)
    # True = bestaetigt oder Email/Google-User. False = Microsoft Neu-User pending.
    # Default=True: bestehende User gelten automatisch als bestaetigt.
    email_confirmed       = Column(Boolean, default=True, nullable=True, comment='Email bestaetigt (Microsoft-OAuth Hijacking-Mitigation, H-18)')
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
    name          = Column(String(200), comment='Name')
    firma         = Column(String(200), comment='Firma')
    rolle         = Column(String(100), comment='Rolle/Position im Unternehmen')
    branche       = Column(String(100), comment='Branche')
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
    __tablename__ = 'ewb_ratings'
    __table_args__ = (
        UniqueConstraint('conversation_log_id', 'einwand_typ_key',
                         name='uq_ewb_rating_per_conv_ewb'),
        {'comment': 'Manuelle EWB-Quality-Ratings (3 binaere Kriterien) pro EWB einer Session, fuer Quality-Score. Status: lebt. Schreibt routes/admin_ewb.py:192; liest routes/admin_ewb.py:65/181.'},
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
    __table_args__ = ({'comment': 'Jeder API-Call mit eingefrorenem Wechselkurs und Rate (Founder Cost Dashboard, steuerlich korrekt). Status: lebt. Schreibt API-Call-Wrapper in services/; liest Founder-Cost-Dashboard.'},)
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
    latency_ms  = Column(Integer, nullable=True, comment='API-Latenz in ms')
    call_site   = Column(String(50), nullable=True, comment='Code-Aufrufstelle')


class ApiRate(Base):
    """Aktuelle API-Preise, editierbar, historisch ueber active-Flag."""
    __tablename__ = 'api_rates'
    __table_args__ = (
        UniqueConstraint('provider', 'model', 'unit_type', 'active', name='uix_api_rate_active'),
        {'comment': 'Aktuelle API-Preise pro Provider/Modell, editierbar, historisch via active-Flag. Status: lebt. Schreibt Admin-Rate-Pflege; liest Cost-Berechnung (api_cost_log) + Dashboard.'},
    )
    id = Column(Integer, primary_key=True)
    provider = Column(String(32), nullable=False, index=True, comment='API-Provider')
    model = Column(String(64), nullable=False, comment='Modell')
    unit_type = Column(String(32), nullable=False, comment='Einheiten-Typ')
    price_per_unit = Column(Numeric(12, 8), nullable=False, comment='Preis pro Einheit')
    currency = Column(String(3), nullable=False, default='USD', comment='Waehrung')
    active = Column(Boolean, default=True, nullable=False, comment='Aktiv-Flag: nur die aktuell gueltige Rate ist aktiv (Historie ueber active)')
    last_checked_at = Column(DateTime, default=utcnow, nullable=False, comment='Zeitpunkt letzter Preis-Pruefung')
    source_url = Column(String(512), nullable=True, comment='Quell-URL der Preisangabe')
    created_at = Column(DateTime, default=utcnow, nullable=False)


class PriceChangeLog(Base):
    """D-06: Manuell erkannte Preisaenderungen mit Impact-Berechnung."""
    __tablename__ = 'price_change_log'
    __table_args__ = ({'comment': 'Manuell erkannte API-Preisaenderungen mit Impact-Berechnung. Status: write-only [ZOMBIE]. Schreibt routes/admin_dashboard.py:434; kein Reader.'},)
    id = Column(Integer, primary_key=True)
    api_rate_id = Column(Integer, ForeignKey('api_rates.id'), nullable=False)
    changed_at = Column(DateTime, default=utcnow, nullable=False, index=True, comment='Zeitpunkt der Preisaenderung')
    old_rate = Column(Numeric(12, 8), nullable=False, comment='Alte Rate')
    new_rate = Column(Numeric(12, 8), nullable=False, comment='Neue Rate')
    currency = Column(String(3), nullable=False, default='USD', comment='Waehrung')
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
    currency = Column(String(3), nullable=False, default='EUR', comment='Waehrung')
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
        {'comment': 'Zentraler Call-Datensatz der neuen Architektur (UUID-PK, Outcome/Coaching/Transkript-Storage). Status: lebt (neue Architektur Phase 08.23.2.A+). Schreibt/liest services/+routes/ der neuen Call-Pipeline.'},
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
        CheckConstraint("event_type IN ('transcript_chunk', 'suggestion_shown', 'reaction', 'phase_change', 'audio_health', 'objection_detected', 'consent_optin')", name='ck_call_events_event_type'),
        Index('idx_call_events_call_time', 'call_id', 'event_ts_ms'),
        Index('idx_call_events_type', 'call_id', 'event_type'),
        Index('idx_call_events_payload_gin', 'payload', postgresql_using='gin'),
        {'comment': 'Append-only Event-Stream pro Call (Kind von calls) der neuen Architektur. Status: lebt (neue Architektur Phase 08.23.2.A+). Schreibt/liest Live-Call-Pipeline in services/.'},
    )


class TranscriptSegment(Base):
    __tablename__ = 'transcript_segments'
    id                  = Column(BigInteger, primary_key=True, autoincrement=True)  # BIGSERIAL
    conversation_log_id = Column(Integer, ForeignKey('conversation_logs.id', ondelete='CASCADE'), nullable=False)
    ts_ms               = Column(Integer, nullable=False, comment='ms ab Call-Start, fuer Reihenfolge')        # ms ab Call-Start, fuer Reihenfolge
    speaker             = Column(Text, nullable=False, comment="Sprecher: 'berater'|'kunde'|'system' (CHECK)")           # 'berater'|'kunde'|'system'
    text                = Column(Text, nullable=False, comment='Anonymisierter Segment-Text (Pipeline B)')           # anonymisierter Text (Pipeline B)
    # WICHTIG: das Spalten-Attribut `text` ueberdeckt im Klassen-Koerper die importierte
    # sqlalchemy-Funktion `text` -> server_default=text('now()') wuerde das Column-Objekt
    # aufrufen (TypeError). Daher func.now() (Modul-Ebene, nicht ueberdeckt). DDL-Aequivalent
    # zur Migration 0010 `DEFAULT now()` (CLAUDE.md Punkt 21 ORM/DDL-Konsistenz).
    created_at          = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        CheckConstraint("speaker IN ('berater', 'kunde', 'system')", name='ck_transcript_segments_speaker'),
        Index('idx_transcript_segments_conv_ts', 'conversation_log_id', 'ts_ms'),
        {'comment': 'Anonymisierte Transkript-Segmente pro Call (Kind von conversation_logs, Pipeline B). Status: lebt (neue Architektur Phase 08.23.2.A+). Schreibt Anonymisierungs-Pipeline; liest Analyse-/Anzeige-Pfad.'},
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
    call_id        = Column(UUID_TYPE, nullable=True, comment='Soft-Link zu public.calls.id, KEIN FK (D-08)')   # soft link zu public.calls.id, KEIN FK (D-08)
    scheduled_at   = Column(DateTime(timezone=True), nullable=True, comment='Geplanter Meeting-Zeitpunkt')
    notes          = Column(Text, nullable=True, comment='Meeting-Notizen')
    schema_version = Column(SmallInteger, nullable=False, server_default='1', comment='Schema-Version des Meeting-Datensatzes')
    created_at     = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        Index('idx_meetings_tenant', 'tenant_id'),
        Index('idx_meetings_account_id', 'account_id'),
        Index('idx_meetings_contact_id', 'contact_id'),
        {'schema': 'crm', 'comment': 'Termin-/Meeting-Datensaetze je Tenant (PiP-Termin-Form, G-MEET). Status: lebt (crm, RLS-isoliert). Schreibt/liest services/crm_service.py + routes/app_routes.py.'},
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
