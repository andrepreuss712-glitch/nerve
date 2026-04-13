"""
Phase 04.12: Gesamt-Integration Engine
Synchrone Verarbeitungs-Engine fuer Cross-Modul Muster-Erkennung.
Laeuft in api_beenden() (Post-Call) und training/end (Post-Training).
Kein Background-Worker, kein Scheduler (D-03).
"""
import json
from datetime import datetime, timedelta

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


# ── Engine Entry Points (werden in Plan 02 implementiert) ────────────────────

def run_postcall_engine(db_session, user_id, conv_id, einwaende, ewb_clicks, ga_details):
    """Synchrone Engine nach Live-Call. Silent failure guaranteed. (D-03, D-04)
    Wird in Plan 02 mit Logik gefuellt."""
    pass


def run_posttraining_engine(db_session, user_id, log_id, scoring, wendepunkt_saetze, modus):
    """Synchrone Engine nach Training-Session. Silent failure guaranteed. (D-03, D-04)
    Wird in Plan 02 mit Logik gefuellt."""
    pass
