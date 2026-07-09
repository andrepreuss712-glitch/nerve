import os
import resend
from itsdangerous import URLSafeTimedSerializer

resend.api_key = os.environ.get('RESEND_API_KEY', '')
_eu_base = os.environ.get('RESEND_BASE_URL')  # optional override, e.g. 'https://api.resend.com'
if _eu_base:
    try:
        resend.base_url = _eu_base
    except Exception:
        pass

FROM_SYSTEM   = 'NERVE <noreply@getnerve.app>'
FROM_FEEDBACK = 'NERVE Feedback <feedback@getnerve.app>'


def _send(payload):
    if not resend.api_key:
        print('[EMAIL] RESEND_API_KEY missing — skip send')
        return False
    # Test-User-Guard (A-02): @nerve.local ist nicht-routbar (.local IANA-reserviert).
    # Domain-Check, kein DB-Lookup — alle @nerve.local-Empfaenger sind Test-Accounts.
    # WICHTIG (G-1): `to` zuerst zu einer Liste normalisieren. Resend akzeptiert sowohl
    # einen String als auch eine Liste. Ohne isinstance-Normalisierung wuerde
    # `any(... for r in recipients)` bei einem bare-String ueber EINZELZEICHEN iterieren
    # ('a','n','d',...), der endswith-Check waere immer False → Test-Mail wuerde
    # gesendet → A-02 ausgehebelt.
    recipients = payload.get('to', [])
    if isinstance(recipients, str):
        recipients = [recipients]
    if any(r.endswith('@nerve.local') for r in recipients):
        print(f'[EMAIL] test-user recipient {recipients!r}, skip')
        return False
    try:
        resend.Emails.send(payload)
        return True
    except Exception as e:
        print(f'[EMAIL] send failed: {e}')
        return False


def send_welcome(to_email, vorname=''):
    name = vorname or 'da'
    html = (
        f"<p>Hallo {name},</p>"
        "<p>willkommen bei NERVE. Du kannst direkt loslegen: "
        "<a href='https://app.getnerve.app/dashboard'>app.getnerve.app</a></p>"
        "<p>Wenn etwas hakt: einfach im Feedback-Button melden. Ich lese jedes Feedback selbst.</p>"
        "<p>— André, Founder NERVE</p>"
    )
    return _send({'from': FROM_SYSTEM, 'to': [to_email],
                  'subject': 'Willkommen bei NERVE', 'html': html})


def send_confirmation_email(to_email, confirmation_url, vorname=''):
    """H-18: Microsoft-OAuth Email-Hijacking-Mitigation.
    Sendet Bestaetigungs-Email an neue Microsoft-OAuth-User.
    confirmation_url: signierter Link zum Bestaetigen der Email (itsdangerous).
    """
    name = vorname or 'there'
    html = (
        f"<p>Hi {name},</p>"
        "<p>please confirm your email address for NERVE:</p>"
        f"<p><a href='{confirmation_url}'>Confirm email</a> (link valid for 24 hours)</p>"
        "<p>If you didn't sign up for NERVE, you can safely ignore this email.</p>"
        "<p>— André, Founder NERVE</p>"
    )
    return _send({'from': FROM_SYSTEM, 'to': [to_email],
                  'subject': 'Confirm your email for NERVE', 'html': html})


def send_feedback_in_planning(to_email, feedback_text, vorname=''):
    name = vorname or 'da'
    snippet = (feedback_text or '')[:300]
    html = (
        f"<p>Hallo {name},</p>"
        "<p>kurze Info: dein Feedback ist bei mir gelandet und ich habe es in die Planung übernommen.</p>"
        f"<blockquote style='border-left:3px solid #00D4AA;padding-left:12px;color:#444'>{snippet}</blockquote>"
        "<p>Ich melde mich nochmal sobald es live ist. Danke dass du NERVE besser machst.</p>"
        "<p>— André</p>"
    )
    return _send({'from': FROM_FEEDBACK, 'to': [to_email],
                  'subject': 'Dein Feedback ist in der Planung', 'html': html})


def send_password_reset(to_email, reset_url):
    html = (
        "<p>Du hast einen Passwort-Reset für NERVE angefordert.</p>"
        f"<p><a href='{reset_url}'>Neues Passwort setzen</a> (Link gültig 1 Stunde)</p>"
        "<p>Wenn du das nicht warst, ignoriere diese Email.</p>"
    )
    return _send({'from': FROM_SYSTEM, 'to': [to_email],
                  'subject': 'NERVE Passwort zurücksetzen', 'html': html})


def make_reset_token(secret, email):
    return URLSafeTimedSerializer(secret, salt='nerve-pwreset').dumps(email)


def parse_reset_token(secret, token, max_age=3600):
    return URLSafeTimedSerializer(secret, salt='nerve-pwreset').loads(token, max_age=max_age)
