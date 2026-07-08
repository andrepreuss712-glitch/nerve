import json
from database.models import AuditLog


def log_action(db, user_id, org_id, action, target_type=None, target_id=None, details=None, request=None, strict=False):
    """Schreibt einen unveränderlichen Audit-Log-Eintrag.

    Fehler werden abgefangen — Audit darf den Request nicht killen.
    DSGVO: Kein Transkript, kein Audio, nur Aggregate und Metadaten.

    strict=False (Default, Bestands-Verhalten): Fehler werden geschluckt (nur geloggt) — kein Caller bricht.
    strict=True (Phase 08.23.2.AUTH-LOGS-TENANT, Founder-Log-Pfad): der Fehler wird RE-RAISED, damit der
    Aufrufer FAIL-CLOSED abbrechen kann (kein Audit -> kein Download). Metadaten-only bleibt unverändert.
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
        # Audit darf den Request nicht killen (Default). Ausnahme: strict=True re-raist (fail-closed Founder-Pfad).
        print(f"[AUDIT] log_action failed: {e}")
        if strict:
            raise
