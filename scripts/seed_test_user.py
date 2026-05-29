#!/usr/bin/env python3
"""seed_test_user.py — Idempotentes Test-User-Seed (Phase 08.23.2.D.UX.0)
Legt andre-test@nerve.local mit is_test_user=True an.
Ausfuehren (einmalig auf Production via SSH, nach Migration 0008):
    cd /opt/nerve/app && source venv/bin/activate && \
    TEST_USER_PASSWORD='<aus-secrets>' python scripts/seed_test_user.py
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import get_session
from database.models import User, Organisation
from werkzeug.security import generate_password_hash

EMAIL = 'andre-test@nerve.local'
PASSWORD = os.environ.get('TEST_USER_PASSWORD', '')

if not PASSWORD:
    print('[SEED] FEHLER: TEST_USER_PASSWORD Env-Variable nicht gesetzt')
    sys.exit(1)

db = get_session()
try:
    existing = db.query(User).filter_by(email=EMAIL).first()
    if existing:
        print(f'[SEED] Test-User {EMAIL} existiert bereits (id={existing.id}) — skip')
        sys.exit(0)
    org = db.query(Organisation).first()
    if not org:
        print('[SEED] FEHLER: Keine Organisation in DB — Seed nicht moeglich')
        sys.exit(1)
    user = User(
        email=EMAIL,
        passwort_hash=generate_password_hash(PASSWORD),
        org_id=org.id,
        rolle='member',
        is_test_user=True,
        is_superadmin=False,
        aktiv=True,
        market='dach',
        language='de',
    )
    db.add(user)
    db.commit()
    print(f'[SEED] Test-User {EMAIL} angelegt (id={user.id}, is_test_user=True)')
finally:
    db.close()
