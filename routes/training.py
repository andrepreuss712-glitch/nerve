import json
import base64
import threading
from datetime import datetime, timedelta, date
from flask import (Blueprint, render_template, request, jsonify,
                   g, session as flask_session)
from routes.auth import login_required
from database.db import get_session
from database.models import Profile, TrainingScenario, PersonalityType, ConversationLog
from services.training_service import (
    build_customer_prompt, build_sekretaerin_prompt,
    build_sekretaerin_type_prompt,
    generate_response, generate_response_with_mood,
    generate_scoring, generate_help_suggestion,
    text_to_speech, _random_persona, SCHWIERIGKEITEN, SEKRETAERIN_TYPES, TRAINING_LANGUAGES,
    _generate_live_preview, build_personality_prompt,
)

training_bp = Blueprint('training', __name__)


def _ensure_dict(val, fallback=None):
    """Ensure val is a dict — handles double-encoded JSON, None, and other types."""
    if fallback is None:
        fallback = {}
    if val is None:
        return fallback
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
            if isinstance(parsed, str):
                parsed = json.loads(parsed)
            return parsed if isinstance(parsed, dict) else fallback
        except (json.JSONDecodeError, TypeError):
            return fallback
    return fallback

_sessions      = {}
_sessions_lock = threading.Lock()
_CODE_VERSION  = '45b02eb'  # git short hash for deploy verification


@training_bp.route('/training/ping')
def training_ping():
    return jsonify({'version': _CODE_VERSION, 'ensure_dict': hasattr(_ensure_dict, '__call__')})


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
                               sekretaerin_types=SEKRETAERIN_TYPES,
                               training_languages=TRAINING_LANGUAGES,
                               preferred_language=preferred_language)
    finally:
        db.close()


@training_bp.route('/training/start', methods=['POST'])
@login_required
def training_start():
  try:
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

    data                = request.get_json(force=True)
    profile_id          = data.get('profile_id')
    schwierigkeit       = data.get('schwierigkeit', 'mittel')
    sprache             = data.get('sprache', 'de')
    scenario_id         = data.get('scenario_id')
    personality_type_id  = data.get('personality_type_id') or None
    generated_personality = data.get('generated_personality')
    modus               = data.get('modus', 'guided')
    anruf_typ           = data.get('anruf_typ', 'direkt')        # 'direkt' or 'sekretaerin'
    sekretaerin_typ     = data.get('sekretaerin_typ', 'blockerin')  # default blockerin
    einwand_typ         = data.get('einwand_typ')  # Optional: Quick-Training Einwand-Fokus

    # Support personality_type_id as int
    if personality_type_id is not None:
        try:
            personality_type_id = int(personality_type_id)
        except (TypeError, ValueError):
            personality_type_id = None

    if sprache not in TRAINING_LANGUAGES:
        sprache = 'de'

    lang_config = TRAINING_LANGUAGES[sprache]

    db = get_session()
    try:
        profile = db.query(Profile).filter_by(id=profile_id, org_id=g.org.id).first()
        if not profile:
            return jsonify({'error': 'Profil nicht gefunden'}), 404

        profile_data = _ensure_dict(profile.daten)

        # Load personality type if provided
        personality_data   = None
        personality_hidden = False
        startstimmung      = 0
        if personality_type_id:
            pt = db.query(PersonalityType).filter(
                PersonalityType.id == personality_type_id,
                (PersonalityType.is_custom == False) |
                (PersonalityType.user_id == g.user.id)
            ).first()
            if pt:
                personality_data = _ensure_dict(pt.attribute)
                personality_data['name'] = pt.name
                personality_data['icon'] = pt.icon
                personality_data['kurzbeschreibung'] = pt.kurzbeschreibung or ''
                startstimmung = personality_data.get('startstimmung', 0)
                # D-05: Hide personality in Experte mode with custom type
                if schwierigkeit == 'schwer' and pt.is_custom:
                    personality_hidden = True

        # Use generated (unsaved) personality if no personality_type_id was given
        if personality_type_id is None and generated_personality and isinstance(generated_personality, dict):
            personality_data = _ensure_dict(generated_personality.get('attribute'))
            personality_data['name']             = generated_personality.get('name', 'Generiert')
            personality_data['icon']             = generated_personality.get('icon', '\U0001F464')
            personality_data['kurzbeschreibung'] = generated_personality.get('kurzbeschreibung', '')
            personality_data['geschlecht']       = generated_personality.get('geschlecht', 'm')
            startstimmung = personality_data.get('startstimmung', 0)
            if schwierigkeit == 'schwer':
                personality_hidden = True

        # Load scenario data if provided
        scenario      = None
        szenario_data = None
        if scenario_id:
            scenario = db.query(TrainingScenario).filter(
                (TrainingScenario.id == scenario_id) &
                ((TrainingScenario.org_id == g.org.id) | (TrainingScenario.erstellt_von == None))
            ).first()
            if scenario:
                szenario_data = {
                    'name':            scenario.name,
                    'kunde_situation': scenario.kunde_situation,
                    'kunde_verhalten': scenario.kunde_verhalten,
                    'spezial_einwaende': scenario.spezial_einwaende,
                }

        persona         = _random_persona(sprache)
        diff            = SCHWIERIGKEITEN.get(schwierigkeit, SCHWIERIGKEITEN['mittel'])
        hat_sekretaerin = (anruf_typ == 'sekretaerin')

        # Berater-Name für Prompts
        berater_vorname  = getattr(g.user, 'vorname', '') or ''
        berater_nachname = getattr(g.user, 'nachname', '') or ''
        berater_name     = f"{berater_vorname} {berater_nachname}".strip() or 'der Berater'

        # Sync persona chef name with personality name if available
        if personality_data and personality_data.get('name') and not personality_hidden:
            _pname = personality_data['name'].split(',')[0].strip()
            parts = _pname.split()
            if len(parts) >= 2:
                persona['chef_vorname'] = parts[0]
                persona['chef_nachname'] = ' '.join(parts[1:])
            elif parts:
                persona['chef_vorname'] = parts[0]
                persona['chef_nachname'] = ''

        # Berater context injected into all prompts
        _berater_ctx = f"\n\nDER BERATER: Der Vertriebler der dich anruft heißt {berater_name}. Wenn er sich vorstellt, nutze seinen Namen im Gespräch."

        # Build system prompt: personality path or classic path
        if personality_data and not hat_sekretaerin:
            system_prompt   = build_personality_prompt(
                profile_data=profile_data,
                personality_data=personality_data,
                schwierigkeit=schwierigkeit,
                current_mood=startstimmung,
                sprache=sprache,
                szenario=szenario_data,
            ) + _berater_ctx
            customer_prompt = system_prompt  # keep in sync for sekretaerin fallback
            phase           = 'kunde'
        else:
            customer_prompt = build_customer_prompt(profile_data, schwierigkeit, persona, sprache) + _berater_ctx

            # Quick-Training: inject einwand_typ focus into customer prompt
            if einwand_typ:
                customer_prompt += f"\n\nWICHTIG: Fokussiere dich in diesem Training besonders auf den Einwand '{einwand_typ}'. Bringe diesen Einwand frueh und hartnaeckig vor."

            # Append scenario context to customer prompt (classic path)
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
                system_prompt = build_sekretaerin_type_prompt(persona, sekretaerin_typ, schwierigkeit, sprache)
                phase         = 'sekretaerin'
            else:
                system_prompt = customer_prompt
                phase         = 'kunde'

        # Use mood-aware response if personality prompt (contains JSON instruction)
        try:
            if personality_data and not hat_sekretaerin:
                mood_result = generate_response_with_mood([], system_prompt, startstimmung, schwierigkeit)
                erste_antwort = mood_result['text']
            else:
                erste_antwort = generate_response([], system_prompt)
        except Exception as _gen_err:
            import traceback
            traceback.print_exc()
            return jsonify({'error': f'KI-Antwort fehlgeschlagen: {type(_gen_err).__name__}: {str(_gen_err)[:200]}'}), 500

        # Voice selection: match gender to personality
        def _detect_female(pd, gp):
            """Check geschlecht field or detect from common German female first names."""
            for src in [gp, pd]:
                if isinstance(src, dict) and src.get('geschlecht') == 'w':
                    return True
            name = ''
            if isinstance(pd, dict):
                name = pd.get('name', '')
            if isinstance(gp, dict) and not name:
                name = gp.get('name', '')
            first = name.split()[0].rstrip(',') if name else ''
            female_names = {'anna','andrea','angelika','birgit','brigitte','carmen','caroline','charlotte',
                'christa','claudia','dagmar','diana','doris','elena','elke','eva','franziska',
                'gabriele','gabi','heike','ines','iris','jana','julia','jutta','karen','karin',
                'katja','katrin','kerstin','laura','lena','lisa','luisa','manuela','maria',
                'marina','marlene','martina','melanie','monika','nadine','nicole','nina',
                'petra','renate','ruth','sabine','sandra','sara','sarah','silke','simone',
                'sofia','sophie','stefanie','susanne','svenja','tanja','ulrike','ursula',
                'ute','vera','verena'}
            return first.lower() in female_names

        if hat_sekretaerin:
            voice_id = persona['voice_female']['id']
        elif _detect_female(personality_data, generated_personality):
            voice_id = persona['voice_female']['id']
        else:
            voice_id = persona['voice_male']['id']
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
                'profile_id':      profile.id,
                'profile_name':    profile.name,
                'profile_data':    profile_data,
                'persona':         persona,
                'sprache':         sprache,
                'phase':           phase,
                'modus':            modus,
                'voice_available':  voice_available,
                'voice_id':                voice_id,
                'berater_name':            berater_name,
                'sekretaerin_typ':         sekretaerin_typ if hat_sekretaerin else None,
                'sekretaerin_ueberwunden': False,
                'history': [{
                    'speaker': 'kunde',
                    'rolle':   'Sekretärin' if hat_sekretaerin else 'Kunde',
                    'text':    erste_antwort,
                    'ts':      datetime.now().strftime('%H:%M:%S'),
                }],
                'started_at':          datetime.now(),
                'einwand_typ':         einwand_typ,
                'personality_type_id': personality_type_id,
                'personality_data':    personality_data,
                'stimmung':            startstimmung,
                'stimmung_history':    [{'turn': 0, 'wert': startstimmung, 'grund': 'Start'}],
                'personality_hidden':  personality_hidden,
                'aufgelegt':           False,
                'scenario_id':         scenario_id,
                'szenario_data':       szenario_data,
            }

        # Build response — conditionally expose personality info (D-05 / T-04.9-07)
        # Use personality name for header if available
        if personality_data and personality_data.get('name') and not personality_hidden:
            # Extract name without age suffix (e.g. "Katrin Behrens, 48" -> "Katrin Behrens")
            _pname = personality_data['name'].split(',')[0].strip()
            display_name = _pname
            display_position = personality_data.get('kurzbeschreibung', persona['chef_position'])
        else:
            display_name = f"{persona['chef_vorname']} {persona['chef_nachname']}"
            display_position = persona['chef_position']

        resp = {
            'ok':             True,
            'session_id':     session_id,
            'kunde_text':     erste_antwort,
            'kunde_audio':    audio_b64,
            'phase':          phase,
            'persona': {
                'firma':         persona['firma'],
                'chef_name':     display_name,
                'chef_position': display_position,
                'sek_name':      persona['sek_name'] if hat_sekretaerin else None,
            },
            'hat_sekretaerin':    hat_sekretaerin,
            'sekretaerin_typ':    sekretaerin_typ if hat_sekretaerin else None,
            'voice_available':    voice_available,
            'voice_message':      voice_message,
            'ui':                 lang_config['ui'],
            'personality_hidden': personality_hidden,
        }
        if personality_data and not personality_hidden:
            resp['personality_name'] = personality_data.get('name', '')
            resp['personality_icon'] = personality_data.get('icon', '')
            resp['stimmung']         = startstimmung
        elif personality_hidden:
            resp['personality_name'] = 'Unbekannt'
            resp['personality_icon'] = '\u2753'  # question mark
            resp['stimmung']         = None  # hidden

        return resp
    finally:
        db.close()
  except Exception as _start_err:
    import traceback
    tb = traceback.format_exc()
    print(tb)
    # Extract last frame for debugging
    lines = [l for l in tb.strip().split('\n') if l.strip()]
    last_frame = ' | '.join(lines[-3:]) if len(lines) >= 3 else tb[-300:]
    return jsonify({'ok': False, 'error': f'{last_frame[:500]}'}), 500


def _hangup_reason(session):
    """Return human-readable hangup reason for popup (D-09)."""
    if session.get('phase') == 'sekretaerin' and not session.get('sekretaerin_ueberwunden'):
        return 'Sekretärin hat abgeblockt'
    return 'Kunde hat aufgelegt'


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

    with _sessions_lock:
        session['history'].append({
            'speaker': 'berater',
            'rolle':   'Berater',
            'text':    user_text,
            'ts':      datetime.now().strftime('%H:%M:%S'),
        })

    # Personality mode: use mood-tracking response; classic path otherwise
    aufgelegt    = False
    letzte_chance = False
    neue_stimmung = session.get('stimmung', 0)

    if session.get('personality_data') and session.get('schwierigkeit') != 'sekretaerin':
        current_mood = session.get('stimmung', 0)

        # Rebuild system prompt with current mood
        system_prompt = build_personality_prompt(
            profile_data=_ensure_dict(session.get('profile_data')),
            personality_data=_ensure_dict(session.get('personality_data')),
            schwierigkeit=session['schwierigkeit'],
            current_mood=current_mood,
            sprache=session.get('sprache', 'de'),
            szenario=session.get('szenario_data'),
        )

        mood_result   = generate_response_with_mood(
            conversation_history=session['history'],
            system_prompt=system_prompt,
            current_mood=current_mood,
            schwierigkeit=session['schwierigkeit'],
        )

        kunde_antwort = mood_result['text']
        neue_stimmung = mood_result['neue_stimmung']
        aufgelegt     = mood_result['aufgelegt']
        letzte_chance = mood_result['letzte_chance']

        # Update session mood state (WR-04: read turn count inside the lock)
        with _sessions_lock:
            _sessions[g.user.id]['stimmung'] = neue_stimmung
            _sessions[g.user.id]['stimmung_history'].append({
                'turn': len(_sessions[g.user.id]['history']),
                'wert': neue_stimmung,
                'grund': 'response',
            })
            if aufgelegt:
                _sessions[g.user.id]['aufgelegt'] = True
    else:
        kunde_antwort = generate_response(session['history'], session['system_prompt'])

    durchgestellt = False
    with _sessions_lock:
        if session['phase'] == 'sekretaerin' and '[DURCHGESTELLT]' in kunde_antwort:
            durchgestellt                      = True
            session['sekretaerin_ueberwunden'] = True
            session['phase']                   = 'kunde'
            session['system_prompt']           = session['customer_prompt']
            kunde_antwort                      = kunde_antwort.replace('[DURCHGESTELLT]', '').strip()
            # Switch voice: chef must have different voice than secretary
            sek_voice = persona['voice_female']['id']
            # Detect chef gender from personality data
            chef_is_female = _detect_female(
                _ensure_dict(session.get('personality_data')),
                None
            )
            if chef_is_female:
                # Female chef needs a DIFFERENT female voice than the secretary
                from services.training_service import VOICE_POOL_FEMALE
                alt_voices = [v['id'] for v in VOICE_POOL_FEMALE if v['id'] != sek_voice]
                session['voice_id'] = alt_voices[0] if alt_voices else persona['voice_male']['id']
            else:
                session['voice_id'] = persona['voice_male']['id']

        # Sekretaerin blocks — she hung up
        if session['phase'] == 'sekretaerin' and '[AUFGELEGT]' in kunde_antwort:
            session['aufgelegt'] = True
            aufgelegt = True
            kunde_antwort = kunde_antwort.replace('[AUFGELEGT]', '').strip()

        is_sek = (not durchgestellt and session['phase'] == 'sekretaerin')
        rolle  = 'Sekretärin' if is_sek else 'Kunde'

        session['history'].append({
            'speaker': 'kunde',
            'rolle':   rolle,
            'text':    kunde_antwort,
            'ts':      datetime.now().strftime('%H:%M:%S'),
        })

    voice_id  = persona['voice_female']['id'] if is_sek else session.get('voice_id', persona['voice_male']['id'])
    audio_b64 = None
    if session.get('voice_available', True):
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
        'aufgelegt':      aufgelegt,
        'letzte_chance':  letzte_chance,
        'schwierigkeit':  session['schwierigkeit'],
        'hangup_reason':  _hangup_reason(session) if aufgelegt else None,
        'sek_ueberwunden': session.get('sekretaerin_ueberwunden', False),
        'hat_sekretaerin': session.get('sekretaerin_typ') is not None,
    }

    # D-07: Only expose mood to Einsteiger (leicht)
    if session.get('personality_data'):
        if session['schwierigkeit'] == 'leicht':
            result['stimmung'] = neue_stimmung
        else:
            result['stimmung'] = None  # hidden from frontend

    if durchgestellt:
        chef_antwort   = generate_response([], session['system_prompt'])
        chef_audio_b64 = None
        if session.get('voice_available', True):
            chef_audio = text_to_speech(
                chef_antwort, session['voice_id'], lang_config['elevenlabs_model'])
            if chef_audio:
                chef_audio_b64 = base64.b64encode(chef_audio).decode('utf-8')

        with _sessions_lock:
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
        profile_data = _ensure_dict(session.get('profile_data'))
        berater_name = session.get('berater_name', 'der Berater')
        phase = session.get('phase', 'kunde')
        vorschlag = generate_help_suggestion(
            session['history'], profile_data, sprache,
            berater_name=berater_name, phase=phase)
        return jsonify({'ok': True, 'vorschlag': vorschlag})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'{type(e).__name__}: {str(e)[:200]}'}), 500


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
            conversation_history=session['history'],
            profile_data=session['profile_data'],
            schwierigkeit=session['schwierigkeit'],
            sekretaerin_ueberwunden=session.get('sekretaerin_ueberwunden', False),
            sprache=sprache,
            modus=modus,
            hilfe_count=hilfe_count,
            stimmung_history=session.get('stimmung_history'),
        )
    except Exception as e:
        print(f"[Training] Scoring-Fehler: {e}")
        scoring = {
            'gesamt_score': 0, 'kategorien': [],
            'staerken': [], 'verbesserungen': ['Scoring konnte nicht generiert werden'],
            'zusammenfassung': 'Fehler bei der Auswertung.',
            'wendepunkt_saetze': [],
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
        'stimmung_history':        session.get('stimmung_history', []),
    }

    # D-05: Reveal personality at end when it was hidden (Experte mode)
    if session.get('personality_hidden') and session.get('personality_data'):
        result['personality_revealed'] = {
            'name':             session['personality_data'].get('name', ''),
            'icon':             session['personality_data'].get('icon', ''),
            'kurzbeschreibung': session['personality_data'].get('kurzbeschreibung', ''),
        }

    # ── ConversationLog + Phrases + Streak ────────────────────────────────────
    wendepunkt_saetze = scoring.get('wendepunkt_saetze', [])
    ga_details = json.dumps([
        {'einwand_typ': ws['einwand_typ'], 'behandelt': True, 'gegenargument': ws['text']}
        for ws in wendepunkt_saetze
        if ws.get('einwand_typ') and ws.get('text')
    ])

    try:
        db_log = get_session()
        from database.models import ConversationLog as CLog, Phrase as PhraseModel
        log_entry = CLog(
            user_id              = g.user.id,
            org_id               = g.org.id,
            profile_id           = session.get('profile_id'),
            profile_name         = session['profile_name'],
            started_at           = session['started_at'],
            ended_at             = datetime.now(),
            dauer_sekunden       = int((datetime.now() - session['started_at']).total_seconds()),
            hilfe_genutzt        = hilfe_count,
            kb_end               = scoring.get('gesamt_score', 0),
            einwaende_gesamt     = len(wendepunkt_saetze),
            einwaende_behandelt  = len([ws for ws in wendepunkt_saetze if ws.get('text')]),
            gegenargument_details= ga_details,
            phasen_details       = json.dumps(scoring),
            typ                  = 'training',
            session_mode         = session.get('modus', 'guided'),
        )
        db_log.add(log_entry)
        db_log.flush()  # log_entry.id verfuegbar fuer Phrase FKs

        # Persist personality_type_id and stimmung_history to ConversationLog
        if session.get('personality_type_id'):
            log_entry.personality_type_id = session['personality_type_id']
        if session.get('stimmung_history'):
            log_entry.stimmung_history = json.dumps(session['stimmung_history'], ensure_ascii=False)

        for ws in wendepunkt_saetze:
            if ws.get('text') and ws.get('einwand_typ'):
                p = PhraseModel(
                    user_id        = g.user.id,
                    session_id     = log_entry.id,
                    text           = ws['text'],
                    objection_type = ws['einwand_typ'],
                )
                db_log.add(p)

        # Streak-Update
        from datetime import date as _date_type
        from database.models import User as _UStreak
        streak_user = db_log.get(_UStreak, g.user.id)
        if streak_user:
            today = _date_type.today()
            if streak_user.streak_last_date:
                days_diff = (today - streak_user.streak_last_date).days
                if days_diff == 1:
                    streak_user.streak_count = (streak_user.streak_count or 0) + 1
                elif days_diff > 1:
                    streak_user.streak_count = 1
                # days_diff == 0: already trained today, no change
            else:
                streak_user.streak_count = 1
            streak_user.streak_last_date = today

        db_log.commit()
    except Exception as ex:
        print(f"[Training] ConversationLog-Speicherung Fehler: {ex}")
    finally:
        try:
            db_log.close()
        except Exception:
            pass

    with _sessions_lock:
        _sessions.pop(g.user.id, None)

    # Award points for completing a training session
    try:
        db_pts = get_session()
        from database.models import User as UserModel
        try:
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
        finally:
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


# ── Personality API Endpoints ──────────────────────────────────────────────────

@training_bp.route('/api/training/personalities')
@login_required
def api_training_personalities():
    """List system + user's custom personality types."""
    db = get_session()
    try:
        types = db.query(PersonalityType).filter(
            (PersonalityType.is_custom == False) |
            ((PersonalityType.is_custom == True) & (PersonalityType.user_id == g.user.id))
        ).order_by(PersonalityType.is_custom, PersonalityType.id).all()

        result = []
        for t in types:
            attr = _ensure_dict(t.attribute)
            result.append({
                'id': t.id,
                'name': t.name,
                'icon': t.icon,
                'kurzbeschreibung': t.kurzbeschreibung,
                'is_custom': t.is_custom,
                'startstimmung': attr.get('startstimmung', 0),
                'kommentar': t.kommentar,
            })
        return jsonify(result)
    finally:
        db.close()


@training_bp.route('/api/training/personalities/generate', methods=['POST'])
@login_required
def api_training_personality_generate():
    """Generate a random personality via Claude Haiku (not saved until user confirms)."""
    from services.training_service import claude_client

    # Load profile context for industry-relevant personality
    branche_ctx = ""
    data = request.get_json(silent=True) or {}
    pid = data.get('profile_id')
    if pid:
        db = get_session()
        try:
            profile = db.query(Profile).filter_by(id=pid, org_id=g.user.org_id).first()
            if profile:
                prof_data = _ensure_dict(profile.daten)
                firma = prof_data.get('firma', '')
                produkt = prof_data.get('produkt', prof_data.get('dienstleistung', ''))
                branche = profile.branche or prof_data.get('branche', '')
                parts = []
                if branche:
                    parts.append(f"Branche des Verkäufers: {branche}")
                if firma:
                    parts.append(f"Firma des Verkäufers: {firma}")
                if produkt:
                    parts.append(f"Produkt/Dienstleistung: {produkt}")
                if parts:
                    branche_ctx = "\n\nKONTEXT DES VERKÄUFERS (der Kunde muss ein REALISTISCHER Ansprechpartner für diese Branche sein):\n" + "\n".join(parts)
        finally:
            db.close()

    import random as _rnd
    _gender = _rnd.choice(['männlich', 'weiblich'])
    _age = _rnd.randint(35, 62)

    prompt = f"""Erstelle eine PERSÖNLICHKEIT für ein B2B-Vertriebstraining.

WICHTIG: Du generierst einen MENSCHEN mit Charakter — KEIN Szenario, KEINE Firma, KEINE Branche, KEINE technischen Details.
Die Person soll NICHT einer dieser 6 Standard-Typen sein: Beschäftigter Chef, Skeptiker, Analytiker, Freundlicher Ja-Sager, Aggressiver, Entscheider.
{branche_ctx}

VORGABE FÜR DIESE GENERIERUNG:
- Geschlecht: {_gender}
- Alter: {_age} Jahre

REGELN:
- Generiere einen realistischen deutschen Vor- und Nachnamen passend zum Geschlecht
- Fokus auf CHARAKTER und VERHALTEN: Wie tickt diese Person? Was macht sie schwierig/interessant im Gespräch?
- KEINE Jobtitel, KEINE Firmennamen, KEINE Produktdetails, KEINE technischen Fragen — das gehört ins Szenario, nicht in den Kundentyp
- Kurzbeschreibung: 1 Satz der den Charakter beschreibt
- Sei KREATIV: Jede Person soll sich deutlich von den vorherigen unterscheiden

Antworte NUR als valides JSON:
{{
  "name": "Vorname Nachname, Alter",
  "geschlecht": "m" oder "w",
  "icon": "ein passendes Emoji",
  "kurzbeschreibung": "1 Satz Charakterbeschreibung — WIE die Person reagiert, nicht WAS sie beruflich macht",
  "briefing": "2-3 Sätze für den Vertriebler: Charakter, Eigenarten, worauf achten, was diese Person triggert",
  "attribute": {{
    "geduld": 1-5,
    "skeptik": 1-5,
    "zeitdruck": 1-5,
    "startstimmung": -3 bis +1,
    "auflege_trigger_hart": ["Verhaltens-Trigger 1", "Verhaltens-Trigger 2"],
    "auflege_trigger_weich": ["Verhaltens-Trigger"],
    "beispiel_reaktionen": ["Typische Reaktion 1", "Typische Reaktion 2"],
    "verhaltensregeln": "Fließtext: Wie verhält sich diese Person im Gespräch — Charakter, Tonfall, Muster",
    "position_profil": "Alter und allgemeine Rolle (z.B. 'Entscheider, 52 Jahre')",
    "vorgeschichte": "1-2 Sätze persönliche Vorgeschichte die das Verhalten erklärt"
  }}
}}"""

    try:
        response = claude_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1200,
            messages=[{"role": "user", "content": prompt}]
        )
        text = response.content[0].text.strip()
        start = text.find('{')
        end   = text.rfind('}') + 1
        if start == -1 or end <= start:
            print(f"[Training] No JSON in response: {text[:500]}")
            return jsonify({'error': 'KI-Antwort unvollständig. Bitte erneut versuchen.'}), 500
        parsed = json.loads(text[start:end])
        return jsonify(parsed)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'{type(e).__name__}: {str(e)[:200]}'}), 500


@training_bp.route('/api/training/personalities/save', methods=['POST'])
@login_required
def api_training_personality_save():
    """Save a generated personality as custom type for the user."""
    data = request.get_json()
    if not data or not data.get('name') or not data.get('attribute'):
        return jsonify({'error': 'Name und Attribute erforderlich'}), 400

    db = get_session()
    try:
        pt = PersonalityType(
            user_id=g.user.id,
            org_id=g.org.id,
            is_custom=True,
            name=data['name'][:100],
            icon=data.get('icon', '\U0001F464')[:10],
            kurzbeschreibung=data.get('kurzbeschreibung', '')[:300],
            attribute=json.dumps(data['attribute'], ensure_ascii=False),
            kommentar=data.get('kommentar', '')
        )
        db.add(pt)
        db.commit()
        return jsonify({'id': pt.id, 'name': pt.name})
    except Exception as e:
        db.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'{type(e).__name__}: {str(e)[:200]}'}), 500
    finally:
        db.close()


# ── Szenario-Routen ────────────────────────────────────────────────────────────

@training_bp.route('/training/scenarios', methods=['GET'])
@login_required
def training_scenarios_list():
    db = get_session()
    try:
        scenarios = db.query(TrainingScenario).filter(
            (TrainingScenario.org_id == g.org.id) | (TrainingScenario.erstellt_von == None)
        ).order_by(TrainingScenario.name).all()
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


# ── Analytics API Endpoints ────────────────────────────────────────────────────

@training_bp.route('/api/training/stats')
@login_required
def api_training_stats():
    db = get_session()
    try:
        from database.models import User as _U, ConversationLog as _CL
        user = db.get(_U, g.user.id)
        heute = datetime.now()
        woche_start = (heute - timedelta(days=heute.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        monat_start = heute.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        basis = db.query(_CL).filter(_CL.user_id == g.user.id, _CL.typ == 'training')
        sessions_gesamt = basis.count()
        sessions_diese_woche = basis.filter(_CL.created_at >= woche_start).count()
        sessions_diesen_monat = basis.filter(_CL.created_at >= monat_start).count()

        alle_logs = basis.order_by(_CL.created_at.desc()).all()
        avg_dauer = 0
        if alle_logs:
            dauern = [l.dauer_sekunden for l in alle_logs if l.dauer_sekunden]
            avg_dauer = int(sum(dauern) / len(dauern)) if dauern else 0

        # Heatmap: Erfolgsquote pro Einwand-Typ
        EINWAND_TYPEN = ['Keine Zeit', 'Zu teuer', 'Kein Interesse',
                         'Haben schon', 'Muss ueberlegen',
                         'Schicken Sie Unterlagen', 'Kein Bedarf']
        einwand_stats = {et: {'gesamt': 0, 'behandelt': 0} for et in EINWAND_TYPEN}
        for log in alle_logs:
            if not log.gegenargument_details:
                continue
            try:
                for ga in json.loads(log.gegenargument_details):
                    et = ga.get('einwand_typ', '')
                    if et in einwand_stats:
                        einwand_stats[et]['gesamt'] += 1
                        if ga.get('behandelt'):
                            einwand_stats[et]['behandelt'] += 1
            except Exception:
                pass

        # Trend: letzte 10 Sessions gesamt_score
        letzte_scores = [l.kb_end or 0 for l in reversed(alle_logs[:10])]

        return jsonify({
            'ok': True,
            'sessions': {
                'diese_woche': sessions_diese_woche,
                'diesen_monat': sessions_diesen_monat,
                'gesamt': sessions_gesamt,
            },
            'avg_dauer_sekunden': avg_dauer,
            'streak': user.streak_count or 0,
            'streak_date': user.streak_last_date.isoformat() if user.streak_last_date else None,
            'wochenziel': user.weekly_goal or 5,
            'heatmap': einwand_stats,
            'trend_scores': letzte_scores,
        })
    finally:
        db.close()


@training_bp.route('/api/training/recommendation')
@login_required
def api_training_recommendation():
    db = get_session()
    try:
        from database.models import User as _U, ConversationLog as _CL
        user = db.get(_U, g.user.id)
        alle_logs = db.query(_CL).filter(
            _CL.user_id == g.user.id, _CL.typ == 'training'
        ).order_by(_CL.created_at.desc()).limit(50).all()

        if not alle_logs:
            return jsonify({'ok': True, 'typ': 'empty',
                'text': 'Starte dein erstes Training um personalisierte Empfehlungen zu erhalten.',
                'quick_url': '/training'})

        # Heatmap berechnen
        einwand_stats = {}
        for log in alle_logs:
            if not log.gegenargument_details:
                continue
            try:
                for ga in json.loads(log.gegenargument_details):
                    et = ga.get('einwand_typ', '')
                    if not et:
                        continue
                    if et not in einwand_stats:
                        einwand_stats[et] = {'gesamt': 0, 'behandelt': 0}
                    einwand_stats[et]['gesamt'] += 1
                    if ga.get('behandelt'):
                        einwand_stats[et]['behandelt'] += 1
            except Exception:
                pass

        # Regel 1: Schlechtester Einwand-Typ (< 40% + >= 3 Versuche)
        schlechtester = None
        schlechteste_quote = 1.0
        for et, stats in einwand_stats.items():
            if stats['gesamt'] >= 3:
                quote = stats['behandelt'] / stats['gesamt']
                if quote < schlechteste_quote:
                    schlechteste_quote = quote
                    schlechtester = et

        if schlechtester and schlechteste_quote < 0.40:
            verluste = einwand_stats[schlechtester]['gesamt'] - einwand_stats[schlechtester]['behandelt']
            return jsonify({'ok': True, 'typ': 'schwaeche', 'einwand_typ': schlechtester,
                'text': f'Du hast "{schlechtester}" {verluste}x verloren \u2014 ueb das jetzt.',
                'quick_url': f'/training?quick=1&einwand_typ={schlechtester}'})

        # Regel 2: Streak-Break (> 3 Tage)
        if user.streak_last_date:
            tage_seit = (date.today() - user.streak_last_date).days
            if tage_seit > 3:
                return jsonify({'ok': True, 'typ': 'streak_break',
                    'text': f'Seit {tage_seit} Tagen nicht trainiert \u2014 10 Minuten reichen.',
                    'quick_url': '/training'})

        # Regel 3: Positiver Trend (letzte 5 Sessions vs. vorherige 5)
        if len(alle_logs) >= 10:
            letzte_5 = [l.kb_end or 0 for l in alle_logs[:5]]
            vorherige_5 = [l.kb_end or 0 for l in alle_logs[5:10]]
            avg_neu = sum(letzte_5) / 5
            avg_alt = sum(vorherige_5) / 5
            if avg_alt > 0 and ((avg_neu - avg_alt) / avg_alt) > 0.15:
                return jsonify({'ok': True, 'typ': 'trend',
                    'text': f'Dein Score ist von {int(avg_alt)} auf {int(avg_neu)} gestiegen \u2014 weiter so!',
                    'quick_url': '/training'})

        # Fallback
        fallback_einwand = schlechtester or 'Zu teuer'
        return jsonify({'ok': True, 'typ': 'fallback',
            'text': f'Trainiere heute den haertesten Einwand: {fallback_einwand}',
            'quick_url': f'/training?quick=1&einwand_typ={fallback_einwand}'})
    finally:
        db.close()


@training_bp.route('/api/training/last-session')
@login_required
def api_training_last_session():
    db = get_session()
    try:
        from database.models import ConversationLog as _CL
        log = db.query(_CL).filter(
            _CL.user_id == g.user.id, _CL.typ == 'training'
        ).order_by(_CL.created_at.desc()).first()

        if not log:
            return jsonify({'ok': True, 'session': None})

        haupt_einwand = None
        top_verbesserung = None

        # Haupt-Einwand aus gegenargument_details
        if log.gegenargument_details:
            try:
                ga_list = json.loads(log.gegenargument_details)
                if ga_list:
                    haupt_einwand = ga_list[0].get('einwand_typ', '')
            except Exception:
                pass

        # Top-Feedback aus phasen_details (= full scoring dict from Plan 01)
        if log.phasen_details:
            try:
                scoring = json.loads(log.phasen_details)
                verbesserungen = scoring.get('verbesserungen', [])
                if verbesserungen:
                    top_verbesserung = verbesserungen[0]
            except Exception:
                pass

        return jsonify({
            'ok': True,
            'session': {
                'id': log.id,
                'profile_name': log.profile_name,
                'dauer_sekunden': log.dauer_sekunden,
                'gesamt_score': log.kb_end,
                'haupt_einwand': haupt_einwand,
                'top_verbesserung': top_verbesserung,
                'datum': log.created_at.strftime('%d.%m.%Y') if log.created_at else None,
                'dashboard_link': f'/dashboard#session-{log.id}',
            }
        })
    finally:
        db.close()


@training_bp.route('/api/training/phrases')
@login_required
def api_training_phrases():
    db = get_session()
    try:
        from database.models import Phrase as _P
        page = request.args.get('page', 1, type=int)
        per_page = 20
        objection_type = request.args.get('objection_type', '').strip()

        query = db.query(_P).filter(_P.user_id == g.user.id)
        if objection_type:
            query = query.filter(_P.objection_type == objection_type)

        total = query.count()
        phrases = query.order_by(_P.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()

        return jsonify({
            'ok': True,
            'phrases': [{
                'id': p.id,
                'text': p.text,
                'objection_type': p.objection_type,
                'created_at': p.created_at.strftime('%d.%m.%Y') if p.created_at else None,
            } for p in phrases],
            'total': total,
            'page': page,
            'pages': (total + per_page - 1) // per_page,
        })
    finally:
        db.close()


@training_bp.route('/api/training/goal', methods=['POST'])
@login_required
def api_training_goal():
    data = request.get_json(force=True) or {}
    goal = data.get('goal')

    # Input validation: Integer, 1-30 range (ASVS V5)
    try:
        goal = int(goal)
    except (TypeError, ValueError):
        return jsonify({'error': 'goal muss eine Zahl sein'}), 400
    if goal < 1 or goal > 30:
        return jsonify({'error': 'goal muss zwischen 1 und 30 liegen'}), 400

    db = get_session()
    try:
        from database.models import User as _U
        user = db.get(_U, g.user.id)
        if user:
            user.weekly_goal = goal
            db.commit()
        return jsonify({'ok': True, 'weekly_goal': goal})
    finally:
        db.close()
