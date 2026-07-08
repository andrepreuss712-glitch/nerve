# ── Phase 08.23.2.AUTH-2 Plan 04: Onboarding-Weiche ──────────────────────────
# Exportiert: post_login_destination(user)
# Importierbar von routes/auth.py UND routes/oauth.py ohne Zirkelimport
# (dieses Modul importiert NICHT routes/auth).
#
# D-03: Nummerierte Stufenliste (nicht verschachteltes if).
# D-09: Finding 2 — liest state NOT IN ('done','skipped'), nicht == 'pending'.
# D-04: skip_onboarding (Stufe 1) != skip_billing (AUTH-3, Stufe 2). Trennung verbatim.

from flask import url_for
from database.db import get_session
from database.models import Profile, User

# ── Finding 2 / D-09: alles AUSSER done/skipped = Onboarding offen ──────────
# Ein späterer Voll-Wizard kann step_*-Zwischenzustände per CHECK-Erweiterung ergänzen,
# ohne diese Weiche anzufassen (Türöffner-Design). Fail-safe-Default 'done' (None/unbekannt
# → nicht umleiten).
_DONE_STATES = ('done', 'skipped')


def post_login_destination(user):
    """Nummerierte Stufenliste (D-03). Gibt eine Redirect-URL (str) zurück ODER None
    ('nichts tun' — Aufrufer behält sein Standard-Ziel, z.B. Coach-Weiche).

    Aufgerufen nach erfolgreichem Login/OAuth mit dem frischen g.user-Objekt.
    url_for() ist zur Aufruf-Zeit im Flask-Request-Context gültig.

    Latenz (Punkt 25): 1 zusätzlicher COUNT-Query nur im NOT-done/skipped+owner/admin-Zweig
    (reiner Login-Pfad, nicht Live-Loop) — vernachlässigbar.
    """

    # ── Stufe 1 — skip_onboarding → nichts tun (Onboarding übersprungen) ─────
    # skip_onboarding überspringt NUR das Onboarding, NICHT die Kasse (D-04).
    if getattr(user, 'skip_onboarding', False):
        return None

    # ── Stufe 2 — [LEER — AUTH-3-SLOT] ───────────────────────────────────────
    # AUTH-3 baut hier seinen Billing-Gate ein, VOR der Onboarding-Stufe.
    # VERTRAG (D-03/D-04, WORTGLEICH — AUTH-3 nicht raten lassen):
    #   „kein Abo = Owner UND nicht skip_billing UND Status nicht in (active, past_due)
    #    → Preisseite; past_due → Portal."
    # ★ ANDRE-TRENNUNG (D-04): skip_onboarding überspringt NUR das Onboarding, NICHT die
    #   Kasse. Das Geld läuft über ein EIGENES organisations.skip_billing pro Firma
    #   (AUTH-3/4). Diese zwei Schranken NIEMALS vermischen: Stufe 1 (skip_onboarding, oben)
    #   und der Billing-Gate hier (skip_billing) sind getrennte Spalten mit getrennter Semantik.
    # (In AUTH-2 bewusst LEER — kein Billing verdrahtet.)

    # ── Stufe 3 — Onboarding (D-09 Türöffner: NOT IN done/skipped, Finding 2) ──
    # fail-safe-Default 'done' (unbekannt/None → nicht umleiten).
    state = getattr(user, 'onboarding_state', 'done') or 'done'
    rolle = getattr(user, 'rolle', None)

    if state not in _DONE_STATES and rolle in ('owner', 'admin'):
        db = get_session()
        try:
            profile_count = db.query(Profile).filter_by(org_id=user.org_id).count()
            if profile_count == 0:
                return url_for('onboarding.wizard')  # Erstprofil-Seite '/onboarding/'
            # Selbstheilung: Profile existieren schon → offener State war stale → auf done, kein Redirect
            u = db.get(User, user.id)
            if u is not None:
                u.onboarding_state = 'done'
                db.commit()
            return None
        finally:
            db.close()
    # Member NIE umgeleitet (fällt durch); NOT-done/skipped+member → None.

    # ── Stufe 4 — nichts tun (Standard-Ziel; done/skipped/member landen hier) ─
    return None
