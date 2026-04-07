import json
from flask import Blueprint, render_template, redirect, url_for, g, request, jsonify, make_response
from routes.auth import login_required
from database.db import get_session
from database.models import User, Profile

onboarding_bp = Blueprint('onboarding', __name__, url_prefix='/onboarding')

BRANCHE_TEMPLATES = {
    'SaaS': {
        'produkt': 'SaaS-Lösung',
        'einwaende': [
            {'typ': 'Kosten/Preis', 'einwand': 'Das ist zu teuer',
             'gegenargument': 'Was wäre es euch wert wenn ihr damit 10 Stunden pro Woche spart?'},
            {'typ': 'Zeit/Aufschub', 'einwand': 'Wir haben gerade andere Prioritäten',
             'gegenargument': 'Verstehe ich. Was steht gerade ganz oben auf eurer Liste?'},
            {'typ': 'Vergleich', 'einwand': 'Wir nutzen schon ein anderes Tool',
             'gegenargument': 'Wie zufrieden seid ihr damit auf einer Skala von 1-10?'},
            {'typ': 'Kein Bedarf', 'einwand': 'Das brauchen wir nicht',
             'gegenargument': 'Wie löst ihr das Thema aktuell?'},
        ],
        'phasen': [
            {'name': 'Einstieg & Rapport', 'beschreibung': 'Begrüßung, Anknüpfungspunkt finden'},
            {'name': 'Problem qualifizieren', 'beschreibung': 'Pain Points aufdecken'},
            {'name': 'Demo / Lösung', 'beschreibung': 'Produkt zeigen, Nutzen erklären'},
            {'name': 'Einwandbehandlung', 'beschreibung': 'Bedenken entkräften'},
            {'name': 'Closing', 'beschreibung': 'Nächsten Schritt vereinbaren'},
        ],
    },
    'Versicherung': {
        'produkt': 'Versicherungslösung',
        'einwaende': [
            {'typ': 'Kosten/Preis', 'einwand': 'Die Beiträge sind mir zu hoch',
             'gegenargument': 'Was wäre denn eine Summe die du monatlich investieren würdest?'},
            {'typ': 'Kein Bedarf', 'einwand': 'Ich bin schon abgesichert',
             'gegenargument': 'Wann hast du zuletzt geprüft ob dein Schutz noch zu deiner Lebenssituation passt?'},
            {'typ': 'Vertrauen', 'einwand': 'Versicherungen zahlen eh nie',
             'gegenargument': 'Was genau hat dich zu dieser Erfahrung gebracht?'},
        ],
        'phasen': [
            {'name': 'Begrüßung', 'beschreibung': 'Vertrauensaufbau'},
            {'name': 'Bedarfsanalyse', 'beschreibung': 'Lebenssituation erfragen'},
            {'name': 'Lückenanalyse', 'beschreibung': 'Absicherungslücken aufzeigen'},
            {'name': 'Lösungsvorschlag', 'beschreibung': 'Passende Produkte vorstellen'},
            {'name': 'Abschluss', 'beschreibung': 'Antrag vorbereiten'},
        ],
    },
    'Consulting': {
        'produkt': 'Beratungsleistung',
        'einwaende': [
            {'typ': 'Kosten/Preis', 'einwand': 'Das Honorar ist zu hoch',
             'gegenargument': 'Was wäre der ROI wenn wir euer Problem in 3 Monaten lösen?'},
            {'typ': 'Zeit/Aufschub', 'einwand': 'Wir starten nächstes Quartal',
             'gegenargument': 'Was passiert wenn ihr noch 3 Monate wartet?'},
            {'typ': 'Entscheidungsträger', 'einwand': 'Das muss der Vorstand entscheiden',
             'gegenargument': 'Was brauchst du damit du es dem Vorstand empfehlen kannst?'},
        ],
        'phasen': [
            {'name': 'Kennenlernen', 'beschreibung': 'Unternehmen und Herausforderung verstehen'},
            {'name': 'Problemverständnis', 'beschreibung': 'Tiefe Analyse der Situation'},
            {'name': 'Lösungsansatz', 'beschreibung': 'Methodik und Vorgehen erklären'},
            {'name': 'Investition', 'beschreibung': 'Honorar und Umfang besprechen'},
            {'name': 'Commitment', 'beschreibung': 'Nächste Schritte festlegen'},
        ],
    },
    'Recruiting': {
        'produkt': 'Recruiting-Dienstleistung',
        'einwaende': [
            {'typ': 'Kosten/Preis', 'einwand': 'Die Provision ist zu hoch',
             'gegenargument': 'Was kostet euch eine unbesetzte Stelle pro Monat?'},
            {'typ': 'Kein Bedarf', 'einwand': 'Wir machen das intern',
             'gegenargument': 'Wie viele offene Stellen habt ihr gerade und seit wann?'},
        ],
        'phasen': [
            {'name': 'Einstieg', 'beschreibung': 'Situation im Unternehmen verstehen'},
            {'name': 'Bedarf', 'beschreibung': 'Offene Stellen und Anforderungen'},
            {'name': 'Lösung', 'beschreibung': 'Recruiting-Ansatz vorstellen'},
            {'name': 'Konditionen', 'beschreibung': 'Provision und Garantie'},
            {'name': 'Auftrag', 'beschreibung': 'Zusammenarbeit starten'},
        ],
    },
    'Immobilien': {
        'produkt': 'Immobiliendienstleistung',
        'einwaende': [
            {'typ': 'Kosten/Preis', 'einwand': 'Die Maklerprovision ist zu hoch',
             'gegenargument': 'Wie viel Zeit und Aufwand steckt ihr gerade selbst in die Vermarktung?'},
            {'typ': 'Vertrauen', 'einwand': 'Makler bringen nichts',
             'gegenargument': 'Was müsste ein Makler tun damit sich die Provision für euch lohnt?'},
        ],
        'phasen': [
            {'name': 'Kennenlernen', 'beschreibung': 'Objekt und Eigentümer verstehen'},
            {'name': 'Bewertung', 'beschreibung': 'Marktwert und Strategie'},
            {'name': 'Leistung', 'beschreibung': 'Service und Marketing'},
            {'name': 'Konditionen', 'beschreibung': 'Provision und Vertrag'},
            {'name': 'Auftrag', 'beschreibung': 'Alleinauftrag sichern'},
        ],
    },
    'Agentur': {
        'produkt': 'Agenturleistung',
        'einwaende': [
            {'typ': 'Kosten/Preis', 'einwand': 'Das Monatsbudget ist zu hoch',
             'gegenargument': 'Welchen Umsatz müssten wir generieren damit sich die Investition lohnt?'},
            {'typ': 'Vergleich', 'einwand': 'Wir haben schon eine Agentur',
             'gegenargument': 'Was fehlt euch bei der aktuellen Zusammenarbeit?'},
        ],
        'phasen': [
            {'name': 'Briefing', 'beschreibung': 'Ziele und Herausforderungen'},
            {'name': 'Analyse', 'beschreibung': 'Ist-Stand und Potential'},
            {'name': 'Strategie', 'beschreibung': 'Lösungsansatz vorstellen'},
            {'name': 'Investment', 'beschreibung': 'Budget und Leistungsumfang'},
            {'name': 'Start', 'beschreibung': 'Kickoff planen'},
        ],
    },
    'Industrie': {
        'produkt': 'Industrielösung',
        'einwaende': [
            {'typ': 'Kosten/Preis', 'einwand': 'Das übersteigt unser Budget',
             'gegenargument': 'Was kostet euch das Problem das wir lösen pro Jahr?'},
            {'typ': 'Zeit/Aufschub', 'einwand': 'Wir haben kein Zeitfenster für eine Umstellung',
             'gegenargument': 'Wann wäre ein guter Zeitpunkt — und was passiert bis dahin?'},
        ],
        'phasen': [
            {'name': 'Kontaktaufnahme', 'beschreibung': 'Erste Verbindung herstellen'},
            {'name': 'Bedarfsanalyse', 'beschreibung': 'Prozesse und Probleme verstehen'},
            {'name': 'Lösungspräsentation', 'beschreibung': 'Produkt und Nutzen zeigen'},
            {'name': 'Angebot', 'beschreibung': 'Konditionen besprechen'},
            {'name': 'Abschluss', 'beschreibung': 'Auftrag sichern'},
        ],
    },
    'Sonstiges': {
        'produkt': 'Mein Produkt',
        'einwaende': [
            {'typ': 'Kosten/Preis', 'einwand': 'Das ist zu teuer',
             'gegenargument': 'Was wäre es dir wert wenn du damit dein Ziel erreichst?'},
            {'typ': 'Zeit/Aufschub', 'einwand': 'Jetzt ist kein guter Zeitpunkt',
             'gegenargument': 'Was muss passieren damit der Zeitpunkt besser wird?'},
        ],
        'phasen': [
            {'name': 'Einstieg', 'beschreibung': 'Vertrauen aufbauen'},
            {'name': 'Bedarfsanalyse', 'beschreibung': 'Problem verstehen'},
            {'name': 'Lösung', 'beschreibung': 'Angebot vorstellen'},
            {'name': 'Einwandbehandlung', 'beschreibung': 'Bedenken klären'},
            {'name': 'Abschluss', 'beschreibung': 'Nächsten Schritt vereinbaren'},
        ],
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
        user = db.query(User).get(g.user.id)
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
                        'einwaende': len(template.get('einwaende', [])),
                        'phasen': len(template.get('phasen', []))})
    finally:
        db.close()
