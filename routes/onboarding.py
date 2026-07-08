import json
from flask import (Blueprint, redirect, url_for, render_template,
                   request, flash, g, session as flask_session)
from database.db import get_session
from database.models import Profile, User
from routes.auth import login_required

onboarding_bp = Blueprint('onboarding', __name__, url_prefix='/onboarding')

BRANCHE_TEMPLATES = {
    'SaaS': {
        'basis': {
            'produktbeschreibung': 'SaaS-Lösung',
            'einwaende_detail': [
                {'einwand': 'Das ist zu teuer', 'varianten': [], 'gegenargument': 'Was wäre es euch wert wenn ihr damit 10 Stunden pro Woche spart?',
                 'technik': '', 'intensitaet': 3, 'kurzlabel': 'Preis', 'kategorie': 'Kosten/Preis', 'einwand_typ': 'unbekannt'},
                {'einwand': 'Wir haben gerade andere Prioritäten', 'varianten': [], 'gegenargument': 'Verstehe ich. Was steht gerade ganz oben auf eurer Liste?',
                 'technik': '', 'intensitaet': 3, 'kurzlabel': 'Prioritäten', 'kategorie': 'Zeit/Aufschub', 'einwand_typ': 'unbekannt'},
                {'einwand': 'Wir nutzen schon ein anderes Tool', 'varianten': [], 'gegenargument': 'Wie zufrieden seid ihr damit auf einer Skala von 1-10?',
                 'technik': '', 'intensitaet': 3, 'kurzlabel': 'Vergleich', 'kategorie': 'Vergleich', 'einwand_typ': 'unbekannt'},
                {'einwand': 'Das brauchen wir nicht', 'varianten': [], 'gegenargument': 'Wie löst ihr das Thema aktuell?',
                 'technik': '', 'intensitaet': 3, 'kurzlabel': 'Kein Bedarf', 'kategorie': 'Kein Bedarf', 'einwand_typ': 'unbekannt'},
            ],
            'phasen': [
                {'name': 'Einstieg & Rapport', 'beschreibung': 'Begrüßung, Anknüpfungspunkt finden'},
                {'name': 'Problem qualifizieren', 'beschreibung': 'Pain Points aufdecken'},
                {'name': 'Demo / Lösung', 'beschreibung': 'Produkt zeigen, Nutzen erklären'},
                {'name': 'Einwandbehandlung', 'beschreibung': 'Bedenken entkräften'},
                {'name': 'Closing', 'beschreibung': 'Nächsten Schritt vereinbaren'},
            ],
        },
    },
    'Versicherung': {
        'basis': {
            'produktbeschreibung': 'Versicherungslösung',
            'einwaende_detail': [
                {'einwand': 'Die Beiträge sind mir zu hoch', 'varianten': [], 'gegenargument': 'Was wäre denn eine Summe die du monatlich investieren würdest?',
                 'technik': '', 'intensitaet': 3, 'kurzlabel': 'Beiträge', 'kategorie': 'Kosten/Preis', 'einwand_typ': 'unbekannt'},
                {'einwand': 'Ich bin schon abgesichert', 'varianten': [], 'gegenargument': 'Wann hast du zuletzt geprüft ob dein Schutz noch zu deiner Lebenssituation passt?',
                 'technik': '', 'intensitaet': 3, 'kurzlabel': 'Abgesichert', 'kategorie': 'Kein Bedarf', 'einwand_typ': 'unbekannt'},
                {'einwand': 'Versicherungen zahlen eh nie', 'varianten': [], 'gegenargument': 'Was genau hat dich zu dieser Erfahrung gebracht?',
                 'technik': '', 'intensitaet': 3, 'kurzlabel': 'Vertrauen', 'kategorie': 'Vertrauen', 'einwand_typ': 'unbekannt'},
            ],
            'phasen': [
                {'name': 'Begrüßung', 'beschreibung': 'Vertrauensaufbau'},
                {'name': 'Bedarfsanalyse', 'beschreibung': 'Lebenssituation erfragen'},
                {'name': 'Lückenanalyse', 'beschreibung': 'Absicherungslücken aufzeigen'},
                {'name': 'Lösungsvorschlag', 'beschreibung': 'Passende Produkte vorstellen'},
                {'name': 'Abschluss', 'beschreibung': 'Antrag vorbereiten'},
            ],
        },
    },
    'Consulting': {
        'basis': {
            'produktbeschreibung': 'Beratungsleistung',
            'einwaende_detail': [
                {'einwand': 'Das Honorar ist zu hoch', 'varianten': [], 'gegenargument': 'Was wäre der ROI wenn wir euer Problem in 3 Monaten lösen?',
                 'technik': '', 'intensitaet': 3, 'kurzlabel': 'Honorar', 'kategorie': 'Kosten/Preis', 'einwand_typ': 'unbekannt'},
                {'einwand': 'Wir starten nächstes Quartal', 'varianten': [], 'gegenargument': 'Was passiert wenn ihr noch 3 Monate wartet?',
                 'technik': '', 'intensitaet': 3, 'kurzlabel': 'Aufschub', 'kategorie': 'Zeit/Aufschub', 'einwand_typ': 'unbekannt'},
                {'einwand': 'Das muss der Vorstand entscheiden', 'varianten': [], 'gegenargument': 'Was brauchst du damit du es dem Vorstand empfehlen kannst?',
                 'technik': '', 'intensitaet': 3, 'kurzlabel': 'Vorstand', 'kategorie': 'Entscheidungsträger', 'einwand_typ': 'unbekannt'},
            ],
            'phasen': [
                {'name': 'Kennenlernen', 'beschreibung': 'Unternehmen und Herausforderung verstehen'},
                {'name': 'Problemverständnis', 'beschreibung': 'Tiefe Analyse der Situation'},
                {'name': 'Lösungsansatz', 'beschreibung': 'Methodik und Vorgehen erklären'},
                {'name': 'Investition', 'beschreibung': 'Honorar und Umfang besprechen'},
                {'name': 'Commitment', 'beschreibung': 'Nächste Schritte festlegen'},
            ],
        },
    },
    'Recruiting': {
        'basis': {
            'produktbeschreibung': 'Recruiting-Dienstleistung',
            'einwaende_detail': [
                {'einwand': 'Die Provision ist zu hoch', 'varianten': [], 'gegenargument': 'Was kostet euch eine unbesetzte Stelle pro Monat?',
                 'technik': '', 'intensitaet': 3, 'kurzlabel': 'Provision', 'kategorie': 'Kosten/Preis', 'einwand_typ': 'unbekannt'},
                {'einwand': 'Wir machen das intern', 'varianten': [], 'gegenargument': 'Wie viele offene Stellen habt ihr gerade und seit wann?',
                 'technik': '', 'intensitaet': 3, 'kurzlabel': 'Intern', 'kategorie': 'Kein Bedarf', 'einwand_typ': 'unbekannt'},
            ],
            'phasen': [
                {'name': 'Einstieg', 'beschreibung': 'Situation im Unternehmen verstehen'},
                {'name': 'Bedarf', 'beschreibung': 'Offene Stellen und Anforderungen'},
                {'name': 'Lösung', 'beschreibung': 'Recruiting-Ansatz vorstellen'},
                {'name': 'Konditionen', 'beschreibung': 'Provision und Garantie'},
                {'name': 'Auftrag', 'beschreibung': 'Zusammenarbeit starten'},
            ],
        },
    },
    'Immobilien': {
        'basis': {
            'produktbeschreibung': 'Immobiliendienstleistung',
            'einwaende_detail': [
                {'einwand': 'Die Maklerprovision ist zu hoch', 'varianten': [], 'gegenargument': 'Wie viel Zeit und Aufwand steckt ihr gerade selbst in die Vermarktung?',
                 'technik': '', 'intensitaet': 3, 'kurzlabel': 'Provision', 'kategorie': 'Kosten/Preis', 'einwand_typ': 'unbekannt'},
                {'einwand': 'Makler bringen nichts', 'varianten': [], 'gegenargument': 'Was müsste ein Makler tun damit sich die Provision für euch lohnt?',
                 'technik': '', 'intensitaet': 3, 'kurzlabel': 'Vertrauen', 'kategorie': 'Vertrauen', 'einwand_typ': 'unbekannt'},
            ],
            'phasen': [
                {'name': 'Kennenlernen', 'beschreibung': 'Objekt und Eigentümer verstehen'},
                {'name': 'Bewertung', 'beschreibung': 'Marktwert und Strategie'},
                {'name': 'Leistung', 'beschreibung': 'Service und Marketing'},
                {'name': 'Konditionen', 'beschreibung': 'Provision und Vertrag'},
                {'name': 'Auftrag', 'beschreibung': 'Alleinauftrag sichern'},
            ],
        },
    },
    'Agentur': {
        'basis': {
            'produktbeschreibung': 'Agenturleistung',
            'einwaende_detail': [
                {'einwand': 'Das Monatsbudget ist zu hoch', 'varianten': [], 'gegenargument': 'Welchen Umsatz müssten wir generieren damit sich die Investition lohnt?',
                 'technik': '', 'intensitaet': 3, 'kurzlabel': 'Budget', 'kategorie': 'Kosten/Preis', 'einwand_typ': 'unbekannt'},
                {'einwand': 'Wir haben schon eine Agentur', 'varianten': [], 'gegenargument': 'Was fehlt euch bei der aktuellen Zusammenarbeit?',
                 'technik': '', 'intensitaet': 3, 'kurzlabel': 'Agentur', 'kategorie': 'Vergleich', 'einwand_typ': 'unbekannt'},
            ],
            'phasen': [
                {'name': 'Briefing', 'beschreibung': 'Ziele und Herausforderungen'},
                {'name': 'Analyse', 'beschreibung': 'Ist-Stand und Potential'},
                {'name': 'Strategie', 'beschreibung': 'Lösungsansatz vorstellen'},
                {'name': 'Investment', 'beschreibung': 'Budget und Leistungsumfang'},
                {'name': 'Start', 'beschreibung': 'Kickoff planen'},
            ],
        },
    },
    'Industrie': {
        'basis': {
            'produktbeschreibung': 'Industrielösung',
            'einwaende_detail': [
                {'einwand': 'Das übersteigt unser Budget', 'varianten': [], 'gegenargument': 'Was kostet euch das Problem das wir lösen pro Jahr?',
                 'technik': '', 'intensitaet': 3, 'kurzlabel': 'Budget', 'kategorie': 'Kosten/Preis', 'einwand_typ': 'unbekannt'},
                {'einwand': 'Wir haben kein Zeitfenster für eine Umstellung', 'varianten': [], 'gegenargument': 'Wann wäre ein guter Zeitpunkt — und was passiert bis dahin?',
                 'technik': '', 'intensitaet': 3, 'kurzlabel': 'Zeitfenster', 'kategorie': 'Zeit/Aufschub', 'einwand_typ': 'unbekannt'},
            ],
            'phasen': [
                {'name': 'Kontaktaufnahme', 'beschreibung': 'Erste Verbindung herstellen'},
                {'name': 'Bedarfsanalyse', 'beschreibung': 'Prozesse und Probleme verstehen'},
                {'name': 'Lösungspräsentation', 'beschreibung': 'Produkt und Nutzen zeigen'},
                {'name': 'Angebot', 'beschreibung': 'Konditionen besprechen'},
                {'name': 'Abschluss', 'beschreibung': 'Auftrag sichern'},
            ],
        },
    },
    'Sonstiges': {
        'basis': {
            'produktbeschreibung': 'Mein Produkt',
            'einwaende_detail': [
                {'einwand': 'Das ist zu teuer', 'varianten': [], 'gegenargument': 'Was wäre es dir wert wenn du damit dein Ziel erreichst?',
                 'technik': '', 'intensitaet': 3, 'kurzlabel': 'Preis', 'kategorie': 'Kosten/Preis', 'einwand_typ': 'unbekannt'},
                {'einwand': 'Jetzt ist kein guter Zeitpunkt', 'varianten': [], 'gegenargument': 'Was muss passieren damit der Zeitpunkt besser wird?',
                 'technik': '', 'intensitaet': 3, 'kurzlabel': 'Zeitpunkt', 'kategorie': 'Zeit/Aufschub', 'einwand_typ': 'unbekannt'},
            ],
            'phasen': [
                {'name': 'Einstieg', 'beschreibung': 'Vertrauen aufbauen'},
                {'name': 'Bedarfsanalyse', 'beschreibung': 'Problem verstehen'},
                {'name': 'Lösung', 'beschreibung': 'Angebot vorstellen'},
                {'name': 'Einwandbehandlung', 'beschreibung': 'Bedenken klären'},
                {'name': 'Abschluss', 'beschreibung': 'Nächsten Schritt vereinbaren'},
            ],
        },
    },
}


# ── D-13: EXPLIZITES Branche-Enum-Mapping (BRANCHE_TEMPLATES-Key → profiles.VALID_BRANCHE) ──
# KEIN stiller _normalize_branche()-Fallback. Recruiting + Agentur haben KEINEN eigenen
# Whitelist-Wert → bewusst dokumentiert auf 'sonstiges' (nicht still geschluckt).
# VALID_BRANCHE aus routes/profiles.py: {'saas_b2b','maschinenbau','versicherung',
# 'finanzprodukte','immobilien','coaching','beratung','sonstiges',''}
BRANCHE_ENUM_MAP = {
    'SaaS':         'saas_b2b',
    'Versicherung': 'versicherung',
    'Consulting':   'beratung',
    'Immobilien':   'immobilien',
    'Industrie':    'maschinenbau',
    'Sonstiges':    'sonstiges',
    'Recruiting':   'sonstiges',   # dokumentiert: kein eigener Whitelist-Wert
    'Agentur':      'sonstiges',   # dokumentiert: kein eigener Whitelist-Wert
}


@onboarding_bp.route('/', methods=['GET', 'POST'])
@login_required
def wizard():
    """Erstprofil-Minimum-Seite (D-11/D-15).

    GET: rendert Branchen-Wahl (1 von 8) + Produktfeld (vorbefüllt aus BRANCHE_TEMPLATES).
    POST Submit: ★ Finding 3 — Rollen-Gate ZUERST (owner/admin only), dann Profil anlegen +
                 aktiv setzen + onboarding_state='done' im SELBEN Commit (D-14).
    POST Skip:   Eigene Route /onboarding/skip (offen für alle Rollen, D-12).
    """
    if request.method == 'POST':
        # ── ★ Finding 3: Rollen-Gate (wie profiles.py:63) — ZUERST, vor jeder Profil-Anlage ──
        if g.user.rolle not in ('owner', 'admin'):
            flash('Keine Berechtigung.', 'error')
            return redirect(url_for('dashboard.index'))

        branche_key = request.form.get('branche_key', 'Sonstiges').strip()
        # Validierung: nur bekannte Keys akzeptieren (T-AUTH2-05 Whitelist)
        if branche_key not in BRANCHE_ENUM_MAP:
            branche_key = 'Sonstiges'

        produkt = request.form.get('produkt', '').strip()

        # D-13: EXPLIZITES Mapping — kein _normalize_branche()-Fallback
        branche_enum = BRANCHE_ENUM_MAP.get(branche_key, 'sonstiges')

        # Profil-Daten aus Template seeden (D-11: Durchklicken ohne Ändern erlaubt)
        template_basis = BRANCHE_TEMPLATES[branche_key]['basis']
        daten = {'basis': dict(template_basis)}
        daten['basis']['produktbeschreibung'] = (
            produkt or template_basis['produktbeschreibung']
        )

        # D-11: Profilname automatisch
        name = f"{branche_key} — Startprofil"

        db = get_session()
        try:
            # Profil anlegen (Muster profiles.py:74-83)
            p = Profile(
                org_id=g.org.id,
                name=name,
                branche=branche_enum,
                daten=json.dumps(daten, ensure_ascii=False),
                erstellt_von=g.user.id,
            )
            db.add(p)
            db.flush()  # p.id vergeben, noch kein Commit

            # ── D-14: Aktiv-Setzen + State-Flip im SELBEN Commit (kein Training-404-Trap) ──
            # (Muster profiles.py:194-198)
            u = db.get(User, g.user.id)
            if u is not None:
                u.active_profile_id = p.id
                u.onboarding_state = 'done'
            db.commit()
            flask_session['active_profile_id'] = p.id  # convenience only
        finally:
            db.close()

        return redirect(url_for('dashboard.index'))

    # GET: Branchen-Wahl + vorbefülltes Produktfeld anzeigen
    default_branche = 'Sonstiges'
    default_produkt = BRANCHE_TEMPLATES[default_branche]['basis']['produktbeschreibung']
    # Vorbefüllung aller Branchen als JSON für client-seitigen Tausch (optional)
    branchen_produkte = {
        k: v['basis']['produktbeschreibung'] for k, v in BRANCHE_TEMPLATES.items()
    }
    return render_template(
        'onboarding_erstprofil.html',
        branchen=list(BRANCHE_TEMPLATES.keys()),
        default_branche=default_branche,
        default_produkt=default_produkt,
        branchen_produkte=branchen_produkte,
    )


@onboarding_bp.route('/skip', methods=['POST'])
@login_required
def skip():
    """Skip-Handler — KEIN Rollen-Gate (Finding 3: Skip offen für alle Rollen).
    Setzt onboarding_state='skipped' + Flash-Banner (D-12).
    Plan 05 stellt die Banner-Sichtbarkeit im Dashboard sicher.
    """
    db = get_session()
    try:
        u = db.get(User, g.user.id)
        if u is not None:
            u.onboarding_state = 'skipped'
            db.commit()
    finally:
        db.close()
    flash('Noch kein Profil — lege eins an, sonst ist Training nicht nutzbar.', 'warning')
    return redirect(url_for('dashboard.index'))
