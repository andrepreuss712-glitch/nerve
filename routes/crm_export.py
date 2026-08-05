"""Phase 08.23.2.G-MEET Wave 2 — CRM CSV export (accounts/contacts).

Tenant-scoped via RLS: reads go through nerve_app, and the request's transaction-local
app.tenant_id GUC (set on Session after_begin, Task 3) scopes crm.accounts / crm.contacts to the
current tenant automatically -- no explicit org/tenant filter needed (and none would be trusted
over RLS). UTF-8 BOM + ';' delimiter for DE Excel (copied verbatim from admin_dashboard._csv_response).

Route slugs are ASCII; CSV CONTENT keeps Umlaute (user-facing data). Both routes @login_required.
"""
import traceback
from datetime import datetime
from flask import Blueprint, g, request, jsonify
from sqlalchemy import text
from routes.auth import login_required
from database.db import get_session
from database.models import Account, Contact, Meeting, UserPreference

crm_export_bp = Blueprint('crm_export', __name__, url_prefix='/crm')


def _csv_response(rows: list, headers: list, filename: str):
    """Hilfs-Helper fuer CSV-Download mit UTF-8-BOM (Excel-kompatibel).
    Verbatim aus routes/admin_dashboard.py:712-725 (DE-Excel ';'-Delimiter)."""
    import csv
    from io import StringIO
    from flask import Response
    buf = StringIO()
    writer = csv.writer(buf, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    data = '\ufeff' + buf.getvalue()  # UTF-8 BOM for Excel
    return Response(data, mimetype='text/csv; charset=utf-8', headers={
        'Content-Disposition': f'attachment; filename={filename}'
    })


@crm_export_bp.route('/export/accounts.csv')
@login_required
def export_accounts_csv():
    db = get_session()
    try:
        # RLS scopes to the current tenant via the transaction-local app.tenant_id GUC.
        rows = db.query(Account).order_by(Account.created_at).all()
        csv_rows = [[
            str(a.id),
            a.name or '',
            a.domain or '',
            a.created_at.strftime('%Y-%m-%d') if a.created_at else '',
        ] for a in rows]
        return _csv_response(
            csv_rows,
            ['ID', 'Name', 'Domain', 'Erstellt'],
            'accounts.csv',
        )
    finally:
        db.close()


@crm_export_bp.route('/export/contacts.csv')
@login_required
def export_contacts_csv():
    db = get_session()
    try:
        rows = db.query(Contact).order_by(Contact.created_at).all()
        csv_rows = [[
            str(c.id),
            str(c.account_id) if c.account_id else '',
            c.name or '',
            c.email or '',
            c.phone or '',
            c.created_at.strftime('%Y-%m-%d') if c.created_at else '',
        ] for c in rows]
        return _csv_response(
            csv_rows,
            ['ID', 'Account-ID', 'Name', 'E-Mail', 'Telefon', 'Erstellt'],
            'contacts.csv',
        )
    finally:
        db.close()


# ── Meeting-Modal-Increment (08.23.2.G-MEET Plan 04) — Write-Route /crm/meetings + Preferences ──
# RLS scopes every crm query to the request's tenant via the transaction-local app.tenant_id GUC
# (db.py after_begin). The route stamps tenant_id = g.tenant_id (== the GUC) so WITH CHECK passes.

def _resolve_account(db, tenant_id, firma):
    """Resolve-or-create a tenant-scoped crm.accounts row by name; blank -> None.

    MM-05: find-then-create is not atomic. On a double-submit two requests race past the
    SELECT and both INSERT -> the DB UNIQUE(tenant_id, name) (uq_accounts_tenant_name, 0014)
    rejects the loser. We INSERT ... ON CONFLICT DO NOTHING and re-select so both the winner
    and the racing creator end up with the same single row (no IntegrityError to the client).
    """
    firma = (firma or '').strip()
    if not firma:
        return None
    acc = db.query(Account).filter(Account.name == firma).first()   # RLS scopes to tenant
    if acc:
        return acc.id
    db.execute(
        text("INSERT INTO crm.accounts (id, tenant_id, name) "
             "VALUES (gen_random_uuid(), :tid, :name) "
             "ON CONFLICT (tenant_id, name) DO NOTHING"),
        {"tid": tenant_id, "name": firma},
    )
    db.flush()
    acc = db.query(Account).filter(Account.name == firma).first()
    return acc.id if acc else None


def _resolve_contact(db, tenant_id, account_id, name):
    """Resolve-or-create a tenant-scoped crm.contacts row by name; blank -> None.

    Contact-Uniqueness ist in diesem Increment NICHT als DB-Constraint nachgeruestet (Plan 04
    MM-05-Entscheidung, deferred): account_id ist nullable (blank-Firma-Fall) -> partielle
    Uniqueness verkompliziert. find-then-create reicht hier (Doppel-Submit-Risiko adressiert
    primaer accounts als Pflicht-Resolve-Ziel)."""
    name = (name or '').strip()
    if not name:
        return None
    con = db.query(Contact).filter(Contact.name == name).first()   # RLS scopes to tenant
    if con is None:
        con = Contact(tenant_id=tenant_id, account_id=account_id, name=name)  # tenant_id stamped -> WITH CHECK ok
        db.add(con)
        db.flush()
    return con.id


@crm_export_bp.route('/meetings', methods=['POST'])
@login_required
def save_meeting():
    tenant_id = g.tenant_id
    if not tenant_id:
        return jsonify(ok=False, error='Kein Mandant'), 403
    data = request.get_json(silent=True) or {}
    firma   = (data.get('firma') or '').strip()
    # André-Direktive 2026-06-02: Firma ist PFLICHTFELD — kein Orphan-Termin (account_id NULL).
    # Firma ist der Schluessel, der den Termin spaeter dem richtigen Briefing zuordnet (Phase MODES).
    # Ansprechpartner/Datum/Thema bleiben optional. Fail-closed VOR jedem DB-Write.
    if not firma:
        return jsonify(ok=False, error='Firma ist Pflicht'), 400
    person  = (data.get('ansprechpartner') or '').strip()
    notes   = (data.get('notes') or '').strip() or None
    call_id = data.get('call_id') or None
    # SOFORT-2 R-7: Besitzpruefung der geposteten call_id — fail-closed VOR jedem DB-Write,
    # genau wie die Firma-Pflicht drei Zeilen darueber.
    # Vorher wurde die call_id ungeprueft als Meeting.call_id gespeichert: Konto A konnte einen
    # FREMDEN Anruf an seinen EIGENEN Termin haengen. Die RLS auf crm.* schuetzt die ZEILE
    # mandantenweise — NICHT die Fremdreferenz darin. Heute liest niemand die Spalte; genau
    # deshalb wird hier geprueft statt vertagt: ein nur-einfuegender Haken ohne Pruefung
    # sammelt stillen Muell, der spaeter nicht mehr von echten Daten unterscheidbar ist.
    # BESITZ-KRITERIUM (benannte Festlegung, Plan 09): eigener Anruf ODER gleicher Mandant.
    # Beide Vergleichswerte sind serverseitig (g.user.id / g.tenant_id) — der Client setzt keinen.
    # ⚠ public.calls traegt KEINE RLS (relrowsecurity = f, Production 2026-08-05) — nur deshalb
    # darf ein leeres Ergebnis hier als "gehoert dir nicht" gelesen werden. Auf einer
    # FORCE-RLS-Tabelle waere derselbe Rueckschluss ein Falsch-403.
    if call_id:
        import services.live_session as ls
        if not ls.call_belongs_to(call_id, g.user.id, tenant_id):
            return jsonify(ok=False, error='Unbekannter Anruf'), 403
    sched_raw = data.get('scheduled_at')
    scheduled_at = None
    if sched_raw:
        # MM-01 (Andre-Decision Option a): Frontend sendet offset-tragende ISO-8601
        # (z.B. "2026-06-03T10:00:00+02:00"). datetime.fromisoformat erzeugt ein tz-AWARE
        # datetime -> Insert in timestamptz speichert den korrekten Instant (10:00+02:00 == 08:00Z).
        # Eine offset-LOSE (naive) Eingabe wird ABGELEHNT, damit Postgres NICHT still die Session-TZ
        # unterstellt (sonst stiller TZ-Drift). Py 3.8: fromisoformat akzeptiert "+02:00"-Offsets;
        # "Z"-Suffix erst ab 3.11 -> Frontend sendet numerischen Offset, kein "Z".
        try:
            parsed = datetime.fromisoformat(sched_raw)
        except (ValueError, TypeError):
            return jsonify(ok=False, error='Datum ungueltig'), 400
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return jsonify(ok=False, error='Datum braucht Zeitzone'), 400
        scheduled_at = parsed
    db = get_session()
    try:
        account_id = _resolve_account(db, tenant_id, firma)
        contact_id = _resolve_contact(db, tenant_id, account_id, person)
        m = Meeting(tenant_id=tenant_id, account_id=account_id, contact_id=contact_id,
                    call_id=call_id, scheduled_at=scheduled_at, notes=notes)
        db.add(m)
        db.commit()
        return jsonify(ok=True, firma=firma, thema=notes or '',
                       scheduled_at=scheduled_at.isoformat() if scheduled_at else None)
    except Exception as e:
        db.rollback()
        # MM-04 (CLAUDE.md Punkt 15 / learning.py:184-185-Pattern): Diagnose loggen VOR sanitized
        # Antwort. User-Response bleibt ohne Traceback.
        traceback.print_exc()
        print(f"[CRM-Meeting] save_meeting Fehler: {e}")
        return jsonify(ok=False, error='Konnte nicht gespeichert werden'), 500
    finally:
        db.close()


@crm_export_bp.route('/preferences', methods=['GET'])
@login_required
def get_meeting_pref():
    db = get_session()
    try:
        # MM-07: per-User-Authz via Session-Identitaet g.user.id (kein Client-Wert). RLS scopt
        # zusaetzlich auf Tenant -> Nutzer liest nur die EIGENE Zeile.
        pref = db.query(UserPreference).filter(UserPreference.user_id == g.user.id).first()
        return jsonify(auto_save_meeting=bool(pref.auto_save_meeting) if pref else False)
    except Exception as e:
        traceback.print_exc()
        print(f"[CRM-Meeting] get_meeting_pref Fehler: {e}")
        return jsonify(auto_save_meeting=False), 500
    finally:
        db.close()


@crm_export_bp.route('/preferences', methods=['POST'])
@login_required
def set_meeting_pref():
    tenant_id = g.tenant_id
    if not tenant_id:
        return jsonify(ok=False, error='Kein Mandant'), 403
    val = bool((request.get_json(silent=True) or {}).get('auto_save_meeting'))
    db = get_session()
    try:
        # MM-07: g.user.id serverseitig, kein Client-user_id.
        pref = db.query(UserPreference).filter(UserPreference.user_id == g.user.id).first()
        if pref is None:
            pref = UserPreference(tenant_id=tenant_id, user_id=g.user.id, auto_save_meeting=val)
            db.add(pref)
        else:
            pref.auto_save_meeting = val
        db.commit()
        return jsonify(ok=True, auto_save_meeting=val)
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        print(f"[CRM-Meeting] set_meeting_pref Fehler: {e}")
        return jsonify(ok=False, error='Speichern fehlgeschlagen'), 500
    finally:
        db.close()
