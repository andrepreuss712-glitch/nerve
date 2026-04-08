import json
from database.models import AuditLog


def log_action(db, user_id, org_id, action, target_type=None, target_id=None, details=None, request=None):
    """Schreibt einen unveränderlichen Audit-Log-Eintrag.

    Fehler werden abgefangen — Audit darf den Request nicht killen.
    DSGVO: Kein Transkript, kein Audio, nur Aggregate und Metadaten.
    """
    try:
        entry = AuditLog(
            user_id=user_id,
            org_id=org_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=json.dumps(details, ensure_ascii=False) if details is not None else None,
            ip_address=(request.remote_addr if request else None),
            user_agent=((request.headers.get('User-Agent') or '')[:500] if request else None),
        )
        db.add(entry)
        db.commit()
    except Exception as e:
        # Audit darf den Request nicht killen
        print(f"[AUDIT] log_action failed: {e}")
