"""Regressions-Waechter: Erstprofil-Anlage traegt schema_version (AUTH2-ERSTPROFIL-SCHEMA-FIX).

VALID Runtime-Verhalten (HTTP-POST gegen die echte Onboarding-Route + DB-Read gegen nerve_test,
KEIN Source-Presence): ein Owner legt via /onboarding/ ein Erstprofil an → das persistierte
Profil traegt `daten['schema_version'] == LATEST_SCHEMA_VERSION` (aktuell 4), NICHT versions-los.

★ Fängt die Klasse (Test-Netz-Regel): Gegen den VOR-Fix-Stand (routes/onboarding.py ohne
`_migrate_profile_data`, vor Commit ce57dea) speicherte der Submit-Handler die Template-`daten`
direkt via `Profile(daten=json.dumps(daten))` OHNE schema_version → dieser Waechter ist ROT
(`daten.get('schema_version')` == None != 4). Nach dem migrate-on-save-Fix → v4 → GRUEN. Damit
verhindert er die Rueckkehr des versions-losen Profils, das die Startup-Batch-Migration vergiftet
([Schema]/ProfileOpener InFailedSqlTransaction bei jedem Neustart).

Rows via cleanup_rows im POST-yield-Teardown (public.*), uuid-suffixed Email gegen UNIQUE.
"""

import json
import uuid

import pytest
from sqlalchemy import text
from werkzeug.security import generate_password_hash

from tests.conftest import cleanup_rows
from database.models import User, Organisation, Profile
from services.profile_schema import LATEST_SCHEMA_VERSION


@pytest.fixture
def cleanup_tracker(client):
    """yield ein {Model/'schema.table': [ids]}-Dict; POST-yield reverse-FK-clean via cleanup_rows."""
    ids = {Profile: [], User: [], Organisation: [], 'public.tenant_orgs': []}
    yield ids
    cleanup_rows(client._test_session, ids)


def test_erstprofil_submit_sets_schema_version(client, cleanup_tracker):
    """Owner-Submit auf /onboarding/ → angelegtes Profil traegt schema_version == LATEST_SCHEMA_VERSION."""
    db = client._test_session

    # Owner + Org direkt per ORM anlegen (kein Register-Pfad). email_confirmed defaultet via
    # conftest before_insert-Listener auf True → passiert das fail-closed login_required-Gate.
    org = Organisation(name='ErstprofilSchema TestOrg', plan='starter')
    db.add(org)
    db.flush()
    owner = User(
        org_id=org.id,
        email=f'erstprofil-{uuid.uuid4().hex[:8]}@nerve.local',
        passwort_hash=generate_password_hash('secret12345'),
        rolle='owner',
        aktiv=True,
    )
    db.add(owner)
    db.commit()
    cleanup_tracker[Organisation].append(org.id)
    cleanup_tracker[User].append(owner.id)
    to_row = db.execute(
        text("SELECT id FROM tenant_orgs WHERE legacy_org_id = :oid"),
        {"oid": org.id},
    ).first()
    if to_row is not None:
        cleanup_tracker['public.tenant_orgs'].append(to_row[0])

    # Owner-Session etablieren (CSRF im Test aus).
    with client.session_transaction() as sess:
        sess['user_id'] = owner.id
        sess['org_id'] = org.id

    # Erstprofil-Submit über die echte Onboarding-Seite.
    resp = client.post('/onboarding/', data={
        'branche_key': 'SaaS',
        'produkt': 'Test-Produkt fuer Vertrieb',
    }, follow_redirects=False)
    assert resp.status_code in (301, 302, 303, 307, 308), (
        f"Owner-Erstprofil-Submit erwartet Redirect, war {resp.status_code}: "
        f"{resp.get_data(as_text=True)[:300]}"
    )

    # Das angelegte Profil aus nerve_test lesen (Submit committet in eigener get_session).
    db.expire_all()
    p = db.query(Profile).filter_by(org_id=org.id).order_by(Profile.id.desc()).first()
    assert p is not None, "Kein Profil nach Owner-Submit angelegt"
    cleanup_tracker[Profile].append(p.id)

    daten = json.loads(p.daten) if p.daten else {}
    assert daten.get('schema_version') == LATEST_SCHEMA_VERSION, (
        f"Erstprofil traegt schema_version={daten.get('schema_version')!r}, "
        f"erwartet {LATEST_SCHEMA_VERSION} (migrate-on-save fehlt? AUTH2-ERSTPROFIL-SCHEMA-FIX)"
    )
