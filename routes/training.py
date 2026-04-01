import json
import base64
import threading
from datetime import datetime
from flask import (Blueprint, render_template, request, jsonify,
                   g, session as flask_session)
from routes.auth import login_required
from database.db import get_session
from database.models import Profile, TrainingScenario
from services.training_service import (
    build_customer_prompt, build_sekretaerin_prompt,
    generate_response, generate_scoring, generate_help_suggestion,
    text_to_speech, _random_persona, SCHWIERIGKEITEN, TRAINING_LANGUAGES,
    _generate_live_preview,
)

training_bp = Blueprint('training', __name__)

_sessions      = {}
_sessions_lock = threading.Lock()


@training_bp.route('/training')
@login_required
def training_page():
    db = get_session()
    try:
        profiles = db.query(Profile).filter_by(org_id=g.org.id).order_by(Profile.name).all()
        preferred_language = getattr(g.user, 'preferred_language', 'de') or 'de'
        return render_template('training.html',
                               profiles=profiles,
                               schwierigkeiten=SCHWIERIGKEITEN,
                               training_languages=TRAINING_LANGUAGES,
                               preferred_language=preferred_language)
    finally:
        db.close()


@training_bp.route('/training/start', methods=['POST'])
@login_required
def training_start():
    # Monthly usage reset + voice-limit check (soft — degrades to text, no hard block)
    from datetime import date as _date
    from database.models import User as _UModel
    _db_vu = get_session()
    voice_available = True
    voice_message   = None
    try:
        _vu = _db_vu.get(_UModel, g.user.id)
        if _vu:
            today = _date.today()
            if not _vu.usage_reset_date or _vu.usage_reset_date.month != today.month or _vu.usage_reset_date.year != today.year:
                _vu.minuten_used = 0
                _vu.trainings_voice_used = 0
                _vu.usage_reset_date = today
                _db_vu.commit()
            voice_limit = g.org.training_voice_limit or 50
            voice_used  = _vu.trainings_voice_used or 0
            if voice_used >= voice_limit:
                voice_available = False
                voice_message   = ('Dein monatliches Kontingent für Trainings mit Stimme ist aufgebraucht. '
                                   'Das Training funktioniert weiter als Text-Chat.')
    except Exception as _ve:
        print(f'[Training] Voice-Check Fehler: {_ve}')
    finally:
        _db_vu.close()

    # Org-level fair-use: reset monthly and increment training_sessions_used
    try:
        from database.models import Organisation as _OrgModel
        from datetime import datetime as _dt
        _db_org = get_session()
        try:
            _org = _db_org.get(_OrgModel, g.org.id)
            if _org:
                today_month = _dt.now().strftime('%Y-%m')
                if _org.fair_use_reset_month != today_month:
                    _org.live_minutes_used = 0
                    _org.training_sessions_used = 0
                    _org.fair_use_reset_month = today_month
                _org.training_sessions_used = (_org.training_sessions_used or 0) + 1
                _db_org.commit()
                # Soft-warn at 80% of training limit (50 sessions)
                training_limit = _org.training_voice_limit or 50
                if _org.training_sessions_used >= int(training_limit * 0.8):
                    print(f'[FairUse] Org {_org.id} at {_org.training_sessions_used}/{training_limit} training sessions (80%+ warning)')
        finally:
            _db_org.close()
    except Exception as _te:
        print(f'[FairUse] Training org counter error: {_te}')

    data          = request.get_json(force=True)
    profile_id    = data.get('profile_id')
    schwierigkeit = data.get('schwierigkeit', 'mittel')
    sprache       = data.get('sprache', 'de')
    scenario_id   = data.get('scenario_id')
    modus         = data.get('modus', 'guided')

    if sprache not in TRAINING_LANGUAGES:
        sprache = 'de'

    lang_config = TRAINING_LANGUAGES[sprache]

    db = get_session()
    try:
        profile = db.query(Profile).filter_by(id=profile_id, org_id=g.org.id).first()
        if not profile:
            return jsonify({'error': 'Profil nicht gefunden'}), 404

        try:
            profile_data = json.loads(profile.daten) if profile.daten else {}
        except Exception:
            profile_data = {}

        scenario = None
        if scenario_id:
            scenario = db.query(TrainingScenario).filter_by(
                id=scenario_id, org_id=g.org.id).first()

        persona         = _random_persona(sprache)
        diff            = SCHWIERIGKEITEN.get(schwierigkeit, SCHWIERIGKEITEN['mittel'])
        hat_sekretaerin = diff.get('sekretaerin', False)

        customer_prompt = build_customer_prompt(profile_data, schwierigkeit, persona, sprache)

        # Append scenario context to customer prompt
        if scenario:
            sc_ctx = f"\n\nTRAININGS-SZENARIO: {scenario.name}"
            if scenario.beschreibung:
                sc_ctx += f"\nSituation: {scenario.beschreibung}"
            if scenario.kunde_situation:
                sc_ctx += f"\nDeine Situation: {scenario.kunde_situation}"
            if scenario.kunde_verhalten:
                sc_ctx += f"\nDein Verhalten: {scenario.kunde_verhalten}"
            if scenario.spezial_einwaende:
                try:
                    einw = json.loads(scenario.spezial_einwaende)
                    if einw:
                        sc_ctx += "\nSpezial-Einwände: " + ", ".join(f"'{e}'" for e in einw[:5])
                except Exception:
                    pass
            customer_prompt += sc_ctx

        if hat_sekretaerin:
            system_prompt = build_sekretaerin_prompt(persona, sprache)
            phase         = 'sekretaerin'
        else:
            system_prompt = customer_prompt
            phase         = 'kunde'

        erste_antwort = generate_response([], system_prompt)

        voice_id    = persona['voice_female']['id'] if hat_sekretaerin else persona['voice_male']['id']
        audio_b64   = None
        if voice_available:
            audio_bytes = text_to_speech(erste_antwort, voice_id, lang_config['elevenlabs_model'])
            if audio_bytes:
                audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')

        session_id = f"t_{g.user.id}_{int(datetime.now().timestamp())}"

        with _sessions_lock:
            _sessions[g.user.id] = {
                'session_id':      session_id,
                'system_prompt':   system_prompt,
                'customer_prompt': customer_prompt,
                'schwierigkeit':   schwierigkeit,
                'profile_name':    profile.name,
                'profile_data':    profile_data,
                'persona':         persona,
                'sprache':         sprache,
                'phase':           phase,
                'modus':            modus,
                'voice_available':  voice_available,
                'sekretaerin_ueberwunden': False,
                'history': [{
                    'speaker': 'kunde',
                    'rolle':   'Sekretärin' if hat_sekretaerin else 'Kunde',
                    'text':    erste_antwort,
                    'ts':      datetime.now().strftime('%H:%M:%S'),
                }],
                'started_at': datetime.now(),
            }

        return jsonify({
            'ok':             True,
            'session_id':     session_id,
            'kunde_text':     erste_antwort,
            'kunde_audio':    audio_b64,
            'phase':          phase,
            'persona': {
                'firma':         persona['firma'],
                'chef_name':     f"{persona['chef_vorname']} {persona['chef_nachname']}",
                'chef_position': persona['chef_position'],
                'sek_name':      persona['sek_name'] if hat_sekretaerin else None,
            },
            'hat_sekretaerin':  hat_sekretaerin,
            'voice_available':  voice_available,
            'voice_message':    voice_message,
            'ui':               lang_config['ui'],
        })
    finally:
        db.close()


@training_bp.route('/training/respond', methods=['POST'])
@login_required
def training_respond():
    data      = request.get_json(force=True)
    user_text = data.get('text', '').strip()

    if not user_text:
        return jsonify({'error': 'Kein Text'}), 400

    with _sessions_lock:
        session = _sessions.get(g.user.id)

    if not session:
        return jsonify({'error': 'Keine aktive Session'}), 400

    sprache     = session.get('sprache', 'de')
    lang_config = TRAINING_LANGUAGES.get(sprache, TRAINING_LANGUAGES['de'])
    persona     = session['persona']

    session['history'].append({
        'speaker': 'berater',
        'rolle':   'Berater',
        'text':    user_text,
        'ts':      datetime.now().strftime('%H:%M:%S'),
    })

    kunde_antwort = generate_response(session['history'], session['system_prompt'])

    durchgestellt = False
    if session['phase'] == 'sekretaerin' and '[DURCHGESTELLT]' in kunde_antwort:
        durchgestellt                      = True
        session['sekretaerin_ueberwunden'] = True
        session['phase']                   = 'kunde'
        session['system_prompt']           = session['customer_prompt']
        kunde_antwort                      = kunde_antwort.replace('[DURCHGESTELLT]', '').strip()

    is_sek = (not durchgestellt and session['phase'] == 'sekretaerin')
    rolle  = 'Sekretärin' if is_sek else 'Kunde'

    session['history'].append({
        'speaker': 'kunde',
        'rolle':   rolle,
        'text':    kunde_antwort,
        'ts':      datetime.now().strftime('%H:%M:%S'),
    })

    voice_id    = persona['voice_female']['id'] if is_sek else persona['voice_male']['id']
    audio_b64   = None
    audio_bytes = text_to_speech(kunde_antwort, voice_id, lang_config['elevenlabs_model'])
    if audio_bytes:
        audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')

    result = {
        'ok':            True,
        'kunde_text':    kunde_antwort,
        'kunde_audio':   audio_b64,
        'phase':         session['phase'],
        'durchgestellt': durchgestellt,
        'turn_count':    len([h for h in session['history'] if h['speaker'] == 'berater']),
    }

    if durchgestellt:
        chef_antwort   = generate_response([], session['system_prompt'])
        chef_audio_b64 = None
        chef_audio     = text_to_speech(
            chef_antwort, persona['voice_male']['id'], lang_config['elevenlabs_model'])
        if chef_audio:
            chef_audio_b64 = base64.b64encode(chef_audio).decode('utf-8')

        session['history'].append({
            'speaker': 'kunde',
            'rolle':   'Kunde',
            'text':    chef_antwort,
            'ts':      datetime.now().strftime('%H:%M:%S'),
        })

        result['chef_text']  = chef_antwort
        result['chef_audio'] = chef_audio_b64

    return jsonify(result)


@training_bp.route('/training/help', methods=['POST'])
@login_required
def training_help():
    with _sessions_lock:
        session = _sessions.get(g.user.id)
    if not session:
        return jsonify({'error': 'Keine aktive Session'}), 400

    try:
        sprache  = session.get('sprache', 'de')
        vorschlag = generate_help_suggestion(
            session['history'], session['profile_data'], sprache)
        return jsonify({'ok': True, 'vorschlag': vorschlag})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@training_bp.route('/training/end', methods=['POST'])
@login_required
def training_end():
    req_data   = request.get_json(force=True) or {}
    hilfe_count = int(req_data.get('hilfe_count', 0))

    with _sessions_lock:
        session = _sessions.get(g.user.id)
    if not session:
        return jsonify({'error': 'Keine aktive Session'}), 400

    sprache = session.get('sprache', 'de')
    modus   = session.get('modus', 'guided')

    try:
        scoring = generate_scoring(
            session['history'],
            session['profile_data'],
            session['schwierigkeit'],
            session.get('sekretaerin_ueberwunden', False),
            sprache,
            modus,
            hilfe_count,
        )
    except Exception as e:
        print(f"[Training] Scoring-Fehler: {e}")
        scoring = {
            'gesamt_score': 0, 'kategorien': [],
            'staerken': [], 'verbesserungen': ['Scoring konnte nicht generiert werden'],
            'zusammenfassung': 'Fehler bei der Auswertung.'
        }

    # Modus-based points calculation
    base_points = 10 + scoring.get('gesamt_score', 0)
    if modus == 'free':
        points = int(base_points * 1.5)
    else:
        penalty = min(hilfe_count * 5, 30)
        points  = max(base_points - penalty, base_points // 2)

    # Generate live preview (Haiku, fast + cheap)
    live_preview = None
    try:
        live_preview = _generate_live_preview(session['history'], session['profile_data'])
    except Exception as e:
        print(f"[Training] Live-Preview Fehler: {e}")

    result = {
        'ok':                      True,
        'scoring':                 scoring,
        'turns':                   len([h for h in session['history'] if h['speaker'] == 'berater']),
        'dauer_min':               round((datetime.now() - session['started_at']).total_seconds() / 60, 1),
        'schwierigkeit':           session['schwierigkeit'],
        'profile_name':            session['profile_name'],
        'sekretaerin_ueberwunden': session.get('sekretaerin_ueberwunden', False),
        'modus':                   modus,
        'hilfe_count':             hilfe_count,
        'punkte_verdient':         points,
        'live_preview':            live_preview,
    }

    with _sessions_lock:
        _sessions.pop(g.user.id, None)

    # Award points for completing a training session
    try:
        db_pts = get_session()
        from database.models import User as UserModel
        train_user = db_pts.get(UserModel, g.user.id)
        if train_user:
            train_user.total_points   = (train_user.total_points or 0) + points
            train_user.trainings_used = (train_user.trainings_used or 0) + 1
            if session.get('voice_available', True):
                train_user.trainings_voice_used = (train_user.trainings_voice_used or 0) + 1
            _LEVELS = [('rookie',0),('starter',200),('professional',1000),('expert',3000),('master',7000),('legend',15000)]
            for lname, threshold in reversed(_LEVELS):
                if train_user.total_points >= threshold:
                    train_user.level = lname
                    break
            db_pts.commit()
        db_pts.close()
    except Exception as ex:
        print(f"[Points] Training-Punkte Fehler: {ex}")

    return jsonify(result)


@training_bp.route('/training/transcribe', methods=['POST'])
@login_required
def training_transcribe():
    from deepgram import DeepgramClient, PrerecordedOptions
    from config import DEEPGRAM_API_KEY

    if 'audio' not in request.files:
        return jsonify({'error': 'Keine Audio-Datei'}), 400

    audio_data = request.files['audio'].read()
    if len(audio_data) < 1000:
        return jsonify({'error': 'Audio zu kurz'}), 400

    language    = request.form.get('language', 'de')
    lang_config = TRAINING_LANGUAGES.get(language, TRAINING_LANGUAGES['de'])

    try:
        client  = DeepgramClient(DEEPGRAM_API_KEY)
        source  = {'buffer': audio_data, 'mimetype': 'audio/webm'}
        options = PrerecordedOptions(
            model='nova-2', language=lang_config['deepgram_code'],
            smart_format=True, punctuate=True,
        )
        response   = client.listen.rest.v("1").transcribe_file(source, options)
        transcript = response.results.channels[0].alternatives[0].transcript
        return jsonify({'ok': True, 'text': transcript})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── Szenario-Routen ────────────────────────────────────────────────────────────

@training_bp.route('/training/scenarios', methods=['GET'])
@login_required
def training_scenarios_list():
    db = get_session()
    try:
        scenarios = (db.query(TrainingScenario)
                     .filter_by(org_id=g.org.id)
                     .order_by(TrainingScenario.erstellt_am.desc())
                     .all())
        return jsonify({'ok': True, 'scenarios': [{
            'id':            s.id,
            'name':          s.name,
            'beschreibung':  s.beschreibung or '',
            'schwierigkeit': s.schwierigkeit or 'mittel',
            'is_system':     s.erstellt_von is None,
        } for s in scenarios]})
    finally:
        db.close()


@training_bp.route('/training/scenarios', methods=['POST'])
@login_required
def training_scenarios_create():
    data = request.get_json(force=True)
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Name fehlt'}), 400

    db = get_session()
    try:
        s = TrainingScenario(
            org_id=g.org.id,
            name=name,
            beschreibung=data.get('beschreibung', ''),
            kunde_situation=data.get('kunde_situation', ''),
            kunde_verhalten=data.get('kunde_verhalten', ''),
            spezial_einwaende=json.dumps(data.get('spezial_einwaende', [])),
            schwierigkeit=data.get('schwierigkeit', 'mittel'),
            erstellt_von=g.user.id,
            erstellt_am=datetime.now(),
        )
        db.add(s)
        db.commit()
        return jsonify({'ok': True, 'id': s.id})
    finally:
        db.close()


@training_bp.route('/training/scenarios/<int:sid>', methods=['DELETE'])
@login_required
def training_scenarios_delete(sid):
    db = get_session()
    try:
        s = db.query(TrainingScenario).filter_by(id=sid, org_id=g.org.id).first()
        if not s:
            return jsonify({'error': 'Nicht gefunden'}), 404
        if s.erstellt_von is None:
            return jsonify({'error': 'System-Szenarien können nicht gelöscht werden.'}), 403
        db.delete(s)
        db.commit()
        return jsonify({'ok': True})
    finally:
        db.close()
