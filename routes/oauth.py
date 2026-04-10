"""OAuth 2.0 / OIDC Login für Google + Microsoft (Phase 04.6.1)."""
from flask import Blueprint, redirect, url_for, session, flash, request
from authlib.integrations.flask_client import OAuth
from sqlalchemy import func
from database.db import get_session
from database.models import User
from routes.auth import _login_user, _create_org_and_user
from services.audit import log_action
from config import (
    GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET,
    MICROSOFT_CLIENT_ID, MICROSOFT_CLIENT_SECRET,
)

oauth_bp = Blueprint('oauth', __name__)
oauth = OAuth()


def _is_known_oauth_tenant(provider, email_hint):
    """Liefert True wenn bereits ein User aus dieser Email-Domain via diesem Provider eingeloggt ist.

    Heuristik für D-06: Ist der Tenant Azure bereits 'bekannt' (= Service-Principal
    provisioniert), brauchen Folge-Logins kein prompt=consent mehr → Silent-SSO möglich.
    """
    if not email_hint or '@' not in email_hint:
        return False
    domain = email_hint.split('@', 1)[1].strip().lower()
    if not domain:
        return False
    db = get_session()
    try:
        existing = db.query(User).filter(
            User.oauth_provider == provider,
            func.lower(User.email).like(f'%@{domain}')
        ).first()
        return existing is not None
    finally:
        db.close()


def init_oauth(app):
    """Wird in app.py nach register_blueprint(oauth_bp) aufgerufen."""
    oauth.init_app(app)
    if GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET:
        oauth.register(
            name='google',
            client_id=GOOGLE_CLIENT_ID,
            client_secret=GOOGLE_CLIENT_SECRET,
            server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
            client_kwargs={'scope': 'openid email profile'},
        )
        print('[OAuth] Google client registered')
    else:
        print('[OAuth] Google credentials missing — /auth/google disabled')
    if MICROSOFT_CLIENT_ID and MICROSOFT_CLIENT_SECRET:
        oauth.register(
            name='microsoft',
            client_id=MICROSOFT_CLIENT_ID,
            client_secret=MICROSOFT_CLIENT_SECRET,
            # /organizations/ endpoint: nur Work/School-Accounts (Microsoft 365), keine personal accounts.
            # Multi-Tenant App im Shell-Tenant (AzureADMultipleOrgs). Matcht die B2B-Zielgruppe.
            server_metadata_url='https://login.microsoftonline.com/organizations/v2.0/.well-known/openid-configuration',
            client_kwargs={'scope': 'openid email profile'},
        )
        print('[OAuth] Microsoft client registered (organizations / Work-School only)')
    else:
        print('[OAuth] Microsoft credentials missing — /auth/microsoft disabled')


def _oauth_error_redirect(code, msg):
    flash(msg, 'error')
    return redirect(f'/?modal=login&oauth_error={code}')


def _oauth_login_or_create(*, provider, oauth_id, email, vorname, nachname, avatar_url):
    """Email-Match → existierenden User loggen + OAuth-Felder nachziehen.
    Sonst neuen Org+User anlegen. Redirect zu /onboarding bzw. /dashboard.
    """
    if not email:
        return _oauth_error_redirect('no_email', 'Provider hat keine E-Mail geliefert.')
    email = email.strip().lower()
    db = get_session()
    try:
        user = db.query(User).filter_by(email=email).first()
        if user:
            if not user.aktiv:
                return _oauth_error_redirect('inactive', 'Account ist deaktiviert.')
            # OAuth-Felder nachziehen (idempotent)
            updated = False
            if not user.oauth_provider:
                user.oauth_provider = provider
                updated = True
            if not user.oauth_id:
                user.oauth_id = oauth_id
                updated = True
            if not user.avatar_url and avatar_url:
                user.avatar_url = avatar_url
                updated = True
            if updated:
                db.flush()
            onboarding_done_flag = bool(getattr(user, 'onboarding_done', True))
            # Session-Fixation-Schutz: alte Session-Keys löschen, dann frisch setzen
            session.clear()
            _login_user(db, user)
            log_action(db, user.id, getattr(user, 'org_id', None), 'login',
                       target_type='user', target_id=user.id,
                       details={'method': provider}, request=request)
            db.commit()
            print(f'[OAuth] {provider} login: existing user id={user.id} onboarding_done={onboarding_done_flag}')
            # D-05: diagnostic — log redirect target for existing-user path
            # Onboarding redirect disabled — wird in einer späteren Phase neu gebaut
            print(f'[OAuth] redirect target: dashboard.index (existing user id={user.id})')
            return redirect(url_for('dashboard.index'))
        # Neuanlage
        firmenname_platzhalter = (vorname + ' ' + nachname).strip() or email.split('@')[0]
        firmenname_platzhalter = firmenname_platzhalter + ' (Workspace)'
        new_user = _create_org_and_user(
            db,
            email=email,
            vorname=vorname or '',
            nachname=nachname or '',
            firmenname=firmenname_platzhalter,  # Onboarding-Wizard fragt richtigen Namen ab
            teamgroesse='1-5',
            passwort_hash='',  # OAuth-Only Sentinel
            oauth_provider=provider,
            oauth_id=oauth_id,
            avatar_url=avatar_url,
        )
        session.clear()
        _login_user(db, new_user)
        log_action(db, new_user.id, getattr(new_user, 'org_id', None), 'login',
                   target_type='user', target_id=new_user.id,
                   details={'method': provider}, request=request)
        db.commit()
        try:
            from services.email_service import send_welcome
            send_welcome(new_user.email, getattr(new_user, 'vorname', '') or '')
        except Exception as e:
            print(f'[OAUTH] welcome mail failed: {e}')
        print(f'[OAuth] {provider} register: new user id={new_user.id}')
        # D-05: diagnostic — log redirect target for new-user path
        # Onboarding redirect disabled — wird in einer späteren Phase neu gebaut
        print(f'[OAuth] redirect target: dashboard.index (new user id={new_user.id})')
        return redirect(url_for('dashboard.index'))
    finally:
        db.close()


# ── Google ────────────────────────────────────────────────────────────────
@oauth_bp.route('/auth/google')
def google_login():
    if not (GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET):
        return _oauth_error_redirect('not_configured', 'Google-Login nicht konfiguriert.')
    redirect_uri = url_for('oauth.google_callback', _external=True)
    # D-06: login_hint durchreichen falls Frontend ihn liefert. Kein prompt=consent
    # nötig für Google (kein Service-Principal-Konzept wie bei Azure).
    # TODO: Frontend kann ?login_hint=<email> mitsenden wenn User Email kennt.
    login_hint = request.args.get('login_hint', '').strip()
    extra = {}
    if login_hint:
        extra['login_hint'] = login_hint
    return oauth.google.authorize_redirect(redirect_uri, **extra)


@oauth_bp.route('/auth/google/callback')
def google_callback():
    try:
        token = oauth.google.authorize_access_token()
    except Exception as e:
        print(f'[OAuth] Google callback failed: {type(e).__name__}')
        return _oauth_error_redirect('google_failed', 'Google-Login abgebrochen oder fehlgeschlagen.')
    userinfo = token.get('userinfo') or {}
    if not userinfo.get('email_verified', False):
        return _oauth_error_redirect('unverified', 'Google-Email ist nicht verifiziert.')
    return _oauth_login_or_create(
        provider='google',
        oauth_id=str(userinfo.get('sub', '')),
        email=userinfo.get('email', ''),
        vorname=userinfo.get('given_name', ''),
        nachname=userinfo.get('family_name', ''),
        avatar_url=userinfo.get('picture'),
    )


# ── Microsoft ─────────────────────────────────────────────────────────────
@oauth_bp.route('/auth/microsoft')
def microsoft_login():
    if not (MICROSOFT_CLIENT_ID and MICROSOFT_CLIENT_SECRET):
        return _oauth_error_redirect('not_configured', 'Microsoft-Login nicht konfiguriert.')
    redirect_uri = url_for('oauth.microsoft_callback', _external=True)
    # D-06: prompt=consent nur beim ersten Login eines Tenants senden.
    # Hintergrund: prompt=consent zwingt Azure dazu, den Service-Principal im Ziel-Tenant
    # beim ersten Login neu zu provisionieren. Umgeht einen bekannten AADSTS900971-Bug
    # bei Multi-Tenant Apps aus Shell-Home-Tenants. Sobald jedoch ein User aus dieser
    # Email-Domain bereits via Microsoft eingeloggt ist, ist der Service-Principal im
    # Ziel-Tenant bereits provisioniert → Silent-SSO möglich, kein consent nötig.
    # TODO: Frontend kann ?login_hint=<email> mitsenden wenn User Email kennt.
    login_hint = request.args.get('login_hint', '').strip()
    extra = {}
    if login_hint:
        extra['login_hint'] = login_hint
        if not _is_known_oauth_tenant('microsoft', login_hint):
            extra['prompt'] = 'consent'
    else:
        # Kein Hint → konservativ consent senden (alter Default, Tenant-Provisioning sicher).
        extra['prompt'] = 'consent'
    return oauth.microsoft.authorize_redirect(redirect_uri, **extra)


@oauth_bp.route('/auth/microsoft/callback')
def microsoft_callback():
    try:
        token = oauth.microsoft.authorize_access_token()
    except Exception as e:
        print(f'[OAuth] Microsoft callback failed: {type(e).__name__}')
        return _oauth_error_redirect('microsoft_failed', 'Microsoft-Login abgebrochen oder fehlgeschlagen.')
    userinfo = token.get('userinfo') or {}
    # Defense-in-Depth: persönliche MS-Konten (outlook.com, hotmail.com, live.com) ablehnen.
    # Der /organizations/ endpoint sollte sie bereits blocken, aber falls Azure-Config
    # später versehentlich auf 'common' oder 'AzureADandPersonalMicrosoftAccount' umgestellt
    # wird, fängt dieser Check es trotzdem ab. Personal-Account tenant GUID ist konstant.
    MS_PERSONAL_TENANT = '9188040d-6c67-4c5b-b112-36a304b66dad'
    if userinfo.get('tid') == MS_PERSONAL_TENANT:
        return _oauth_error_redirect(
            'personal_account',
            'NERVE benötigt ein Microsoft 365 Business-Konto. Private Microsoft-Konten (Hotmail, Outlook, Live) werden nicht unterstützt. Bitte verwende deinen Firmen-Account oder melde dich mit Google an.'
        )
    # Microsoft: KEIN email_verified-Check (siehe RESEARCH.md)
    email = userinfo.get('email') or userinfo.get('preferred_username') or ''
    name  = userinfo.get('name') or ''
    # Microsoft liefert nur "name" als ganzen String — pragmatisch splitten
    parts = name.split(' ', 1)
    vorname  = parts[0] if parts else ''
    nachname = parts[1] if len(parts) > 1 else ''
    return _oauth_login_or_create(
        provider='microsoft',
        oauth_id=str(userinfo.get('sub', '') or userinfo.get('oid', '')),
        email=email,
        vorname=vorname,
        nachname=nachname,
        avatar_url=None,  # Microsoft Graph /me/photo wäre ein zweiter Call — out of scope
    )
