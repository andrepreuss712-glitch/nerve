"""
Phase 04.12: Gesamt-Integration Engine
Synchrone Verarbeitungs-Engine fuer Cross-Modul Muster-Erkennung.
Laeuft in api_beenden() (Post-Call) und training/end (Post-Training).
Kein Background-Worker, kein Scheduler (D-03).
"""
import json
from datetime import datetime, timedelta
from collections import Counter

# D-01: Alle 12 Event-Typen — Whitelist fuer Input-Validierung (T-04.12 Security)
VALID_EVENT_TYPES = frozenset([
    'hint_used',
    'hint_ignored',
    'button_pressed',
    'learning_card_accepted',
    'learning_card_rejected',
    'learning_card_custom',
    'learning_card_applied',
    'training_completed',
    'training_hangup',
    'call_rated',
    'score_milestone',
    'training_recommended',   # interner Typ fuer Engine-Empfehlungen
])

VALID_SOURCE_MODULES = frozenset(['assistant', 'training', 'coach', 'rating'])

# ── Schwellenwerte ──────────────────────────────────────────────────────────────
_LOOKBACK_DAYS = 30
_EWB_THRESHOLD = 3          # D-11: >3x gleicher Einwand-Typ => Empfehlung
_CALL_WEAKNESS_MIN = 2      # D-06: 2+ verschiedene Calls mit gleichem schwaechsten Typ
_TRAINING_FAILURE_MIN = 3   # D-05: 3x Training-Scheitern am selben Einwand-Typ
_SCORE_MILESTONE = 80       # Score >= 80 => score_milestone Event
_TRAINING_SUCCESS_THRESHOLD = 50  # gesamt_score >= 50 => success


def log_learning_event(db_session, user_id, event_type, source_module,
                       source_id=None, metadata=None):
    """Schreibt einen learning_event. db_session wird vom Caller verwaltet.

    KEIN db_session.commit() hier — Caller committet (Pattern aus ObjectionEvent bulk-insert).
    Whitelist-Check auf event_type und source_module (Security: T-04.12 Input Validation).
    """
    if event_type not in VALID_EVENT_TYPES:
        print(f"[Engine] Ungueltiger event_type: {event_type}")
        return
    if source_module not in VALID_SOURCE_MODULES:
        print(f"[Engine] Ungueltiges source_module: {source_module}")
        return

    from database.models import LearningEvent
    ev = LearningEvent(
        user_id=user_id,
        event_type=event_type,
        source_module=source_module,
        source_id=source_id,
        event_metadata=json.dumps(metadata or {}, ensure_ascii=False) if metadata else None,
    )
    db_session.add(ev)


# ── Hilfsfunktionen ─────────────────────────────────────────────────────────────

def _persist_training_recommendation(db_session, user_id, einwand_typ):
    """Setzt User.pending_training_recommendation als JSON mit passendem Szenario."""
    try:
        from database.models import User as UserModel, TrainingScenario
        user = db_session.get(UserModel, user_id)
        if not user:
            return

        # Passendes Szenario suchen (Name oder spezial_einwaende enthaelt den Typ)
        scenario = (db_session.query(TrainingScenario)
                    .filter(TrainingScenario.name.ilike(f'%{einwand_typ}%'))
                    .first())
        if not scenario:
            scenario = (db_session.query(TrainingScenario)
                        .filter(TrainingScenario.spezial_einwaende.ilike(f'%{einwand_typ}%'))
                        .first())

        rec = {
            'einwand_typ': einwand_typ,
            'scenario_name': scenario.name if scenario else 'Freies Training',
            'scenario_id': scenario.id if scenario else None,
            'created_at': datetime.now().isoformat(),
        }
        user.pending_training_recommendation = json.dumps(rec, ensure_ascii=False)
        log_learning_event(db_session, user_id, 'training_recommended', 'coach', None, rec)
        db_session.commit()
        print(f"[Engine] Training-Empfehlung gesetzt: user={user_id}, typ={einwand_typ}")
    except Exception as ex:
        print(f"[Engine] _persist_training_recommendation Fehler: {ex}")


def _maybe_clear_training_recommendation(db_session, user_id, wendepunkt_saetze):
    """Loescht pending_training_recommendation wenn trainierter Einwand-Typ passt (D-12)."""
    try:
        from database.models import User as UserModel
        user = db_session.get(UserModel, user_id)
        if not user or not user.pending_training_recommendation:
            return

        rec = json.loads(user.pending_training_recommendation)
        rec_typ = rec.get('einwand_typ', '').lower()
        if not rec_typ:
            return

        for ws in (wendepunkt_saetze or []):
            ws_typ = (ws.get('einwand_typ') or '').lower()
            if ws_typ and ws_typ == rec_typ:
                user.pending_training_recommendation = None
                db_session.commit()
                print(f"[Engine] Training-Empfehlung geloescht: user={user_id}, typ={rec_typ}")
                return
    except Exception as ex:
        print(f"[Engine] _maybe_clear_training_recommendation Fehler: {ex}")


# ── Engine Entry Points ─────────────────────────────────────────────────────────

def run_postcall_engine(db_session, user_id, conv_id, einwaende, ewb_clicks, ga_details):
    """Synchrone Engine nach Live-Call. Silent failure guaranteed. (D-03, D-04)

    1. Event-Logging: hint_used + button_pressed
    2. Muster-Erkennung EWB >3x (D-11)
    3. Muster-Erkennung Call-Schwaeche (D-06)
    # D-10: call_rated Event wird in routes/app_routes.py bei Bewertungs-Speicherung geloggt
    """
    try:
        from database.models import LearningEvent
        cutoff = datetime.now() - timedelta(days=_LOOKBACK_DAYS)

        # ── 1. Event-Logging (D-01, D-03) ───────────────────────────────────────
        for e in (einwaende or []):
            log_learning_event(db_session, user_id, 'hint_used', 'assistant', conv_id, {
                'einwand_typ': e.get('typ', 'unknown'),
                'intensitaet': e.get('intensitaet', '?'),
            })

        for click in (ewb_clicks or []):
            log_learning_event(db_session, user_id, 'button_pressed', 'assistant', conv_id, {
                'einwand_typ': click.get('einwand_typ', 'unknown'),
                'success': click.get('success', False),
            })

        db_session.commit()

        # ── 2. Muster-Erkennung EWB >3x (D-11) ─────────────────────────────────
        try:
            from sqlalchemy import text
            rows = db_session.execute(text(
                "SELECT json_extract(metadata, '$.einwand_typ') as einwand_typ, COUNT(*) as cnt "
                "FROM learning_events "
                "WHERE user_id = :uid AND event_type = 'button_pressed' "
                "AND created_at >= :cutoff "
                "GROUP BY einwand_typ HAVING cnt > :threshold"
            ), {'uid': user_id, 'cutoff': cutoff, 'threshold': _EWB_THRESHOLD}).fetchall()

            for row in rows:
                top_typ = row[0]
                if top_typ:
                    _persist_training_recommendation(db_session, user_id, top_typ)
                    break  # Eine Empfehlung pro Engine-Lauf reicht
        except Exception as ex:
            print(f"[Engine] EWB-Muster-Check Fehler: {ex}")

        # ── 3. Muster-Erkennung Call-Schwaeche (D-06) ────────────────────────────
        try:
            if einwaende:
                # Haeufigster Einwand-Typ in dieser Session = schwächster
                typ_counts = Counter(e.get('typ', 'unknown') for e in einwaende)
                schwach_typ = typ_counts.most_common(1)[0][0]

                from sqlalchemy import text
                result = db_session.execute(text(
                    "SELECT COUNT(DISTINCT source_id) as call_count "
                    "FROM learning_events "
                    "WHERE user_id = :uid AND event_type = 'hint_used' "
                    "AND json_extract(metadata, '$.einwand_typ') = :typ "
                    "AND created_at >= :cutoff "
                    "AND source_id IS NOT NULL"
                ), {'uid': user_id, 'typ': schwach_typ, 'cutoff': cutoff}).fetchone()

                if result and result[0] >= _CALL_WEAKNESS_MIN:
                    _persist_training_recommendation(db_session, user_id, schwach_typ)
        except Exception as ex:
            print(f"[Engine] Call-Schwaeche-Check Fehler: {ex}")

        print(f"[Engine] Post-Call Engine fertig: user={user_id}, conv={conv_id}")

    except Exception as ex:
        print(f"[Engine] run_postcall_engine Fehler: {ex}")


def run_posttraining_engine(db_session, user_id, log_id, scoring, wendepunkt_saetze, modus):
    """Synchrone Engine nach Training-Session. Silent failure guaranteed. (D-03, D-04)

    1. Event-Logging: training_completed + score_milestone
    2. Schwaeche-Muster-Erkennung (D-05)
    3. Empfehlung loeschen wenn Training absolviert (D-12)
    """
    try:
        from database.models import LearningEvent

        # ── 1. Event-Logging (D-01, D-03) ───────────────────────────────────────
        gesamt_score = scoring.get('gesamt_score', 0) if scoring else 0
        success = gesamt_score >= _TRAINING_SUCCESS_THRESHOLD

        # Haupt-Einwand-Typ extrahieren (erster wendepunkt_satz mit einwand_typ)
        einwand_typ = 'unknown'
        for ws in (wendepunkt_saetze or []):
            if ws.get('einwand_typ'):
                einwand_typ = ws['einwand_typ']
                break

        log_learning_event(db_session, user_id, 'training_completed', 'training', log_id, {
            'einwand_typ': einwand_typ,
            'score': gesamt_score,
            'schwierigkeit': modus or 'unknown',
            'success': success,
            'dauer_sek': scoring.get('dauer_sek', 0) if scoring else 0,
        })

        # Score-Milestone pruefen
        if gesamt_score >= _SCORE_MILESTONE:
            log_learning_event(db_session, user_id, 'score_milestone', 'training', log_id, {
                'milestone': _SCORE_MILESTONE,
                'context': 'training',
            })

        db_session.commit()

        # ── 2. Schwaeche-Muster-Erkennung (D-05) ────────────────────────────────
        needs_learning_card = False
        try:
            if einwand_typ != 'unknown':
                cutoff = datetime.now() - timedelta(days=_LOOKBACK_DAYS)
                from sqlalchemy import text

                result = db_session.execute(text(
                    "SELECT COUNT(*) as fail_count "
                    "FROM learning_events "
                    "WHERE user_id = :uid AND event_type = 'training_completed' "
                    "AND json_extract(metadata, '$.einwand_typ') = :typ "
                    "AND json_extract(metadata, '$.success') = 'false' "
                    "AND created_at >= :cutoff"
                ), {'uid': user_id, 'typ': einwand_typ, 'cutoff': cutoff}).fetchone()

                if result and result[0] >= _TRAINING_FAILURE_MIN:
                    _persist_training_recommendation(db_session, user_id, einwand_typ)
                    needs_learning_card = True  # Flag fuer Plan 03 (Lernkarten-Generierung)
                    print(f"[Engine] Training-Schwaeche erkannt: user={user_id}, typ={einwand_typ}, failures={result[0]}")
        except Exception as ex:
            print(f"[Engine] Training-Schwaeche-Check Fehler: {ex}")

        # ── 3. Empfehlung loeschen wenn Training absolviert (D-12) ───────────────
        if success:
            _maybe_clear_training_recommendation(db_session, user_id, wendepunkt_saetze)

        print(f"[Engine] Post-Training Engine fertig: user={user_id}, log={log_id}, score={gesamt_score}")

    except Exception as ex:
        print(f"[Engine] run_posttraining_engine Fehler: {ex}")
