import json
from flask import Blueprint, render_template, redirect, url_for, g, request, jsonify, make_response
from routes.auth import login_required
from database.db import get_session
from database.models import User, Profile

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


@onboarding_bp.route('/')
@login_required
def wizard():
    # D-05: diagnostic — log every wizard hit with onboarding state
    print(f'[Onboarding] wizard hit: user_id={g.user.id} email={g.user.email} onboarding_done={g.user.onboarding_done}')
    if g.user.onboarding_done:
        print(f'[Onboarding] wizard hit: redirecting to dashboard (onboarding_done=True)')
        return redirect(url_for('dashboard.index'))
    db = get_session()
    try:
        profiles = db.query(Profile).filter_by(org_id=g.org.id).all()
        # D-05: Cache-Control no-store — verhindert dass Browser/Proxy eine alte
        # Onboarding-Antwort cached und beim zweiten OAuth-Login fälschlich zurückspielt.
        resp = make_response(render_template('onboarding.html', profiles=profiles))
        resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        resp.headers['Pragma'] = 'no-cache'
        return resp
    finally:
        db.close()


@onboarding_bp.route('/complete', methods=['POST'])
@login_required
def complete():
    data = request.get_json(force=True)
    db = get_session()
    try:
        user = db.get(User, g.user.id)
        user.onboarding_done = True
        user.erfahrungslevel = data.get('erfahrungslevel', '')
        user.schmerzpunkt = data.get('schmerzpunkt', '')
        user.persoenlich = data.get('persoenlich', '')
        user.dashboard_stil = data.get('dashboard_stil', '')
        user.dashboard_style = data.get('dashboard_style', 'vollstaendig')
        if data.get('vorname'):
            user.vorname = data.get('vorname')
        db.commit()
        return jsonify({'ok': True})
    finally:
        db.close()


@onboarding_bp.route('/create_profile', methods=['POST'])
@login_required
def create_profile_from_template():
    data = request.get_json(force=True)
    branche = data.get('branche', 'SaaS')
    template = BRANCHE_TEMPLATES.get(branche, BRANCHE_TEMPLATES['Sonstiges'])
    _basis = template.get('basis', {})
    if not _basis:
        # Defensive: template structure broken — log and use empty basis
        print(f"[Onboarding] create_profile_from_template: no basis in template for branche={branche}")
    db = get_session()
    try:
        profil = Profile(
            org_id=g.org.id,
            name=f"Mein {branche}-Profil",
            branche=branche,
            daten=json.dumps(template, ensure_ascii=False),
            erstellt_von=g.user.id,
        )
        db.add(profil)
        db.commit()
        return jsonify({'ok': True, 'id': profil.id, 'name': profil.name,
                        'einwaende': len(template.get('einwaende_detail', [])),
                        'phasen': len(template.get('phasen', []))})
    finally:
        db.close()
