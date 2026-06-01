"""Phase 08.23.2.G-MEET Wave 2 — CRM CSV export (accounts/contacts).

Tenant-scoped via RLS: reads go through nerve_app, and the request's transaction-local
app.tenant_id GUC (set on Session after_begin, Task 3) scopes crm.accounts / crm.contacts to the
current tenant automatically -- no explicit org/tenant filter needed (and none would be trusted
over RLS). UTF-8 BOM + ';' delimiter for DE Excel (copied verbatim from admin_dashboard._csv_response).

Route slugs are ASCII; CSV CONTENT keeps Umlaute (user-facing data). Both routes @login_required.
"""
from flask import Blueprint
from routes.auth import login_required
from database.db import get_session
from database.models import Account, Contact

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
