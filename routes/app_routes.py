import os
from datetime import datetime
from flask import Blueprint, render_template, jsonify, request, Response, g, session as flask_session
from routes.auth import login_required
import services.live_session as ls
from services.live_session import LOG_DIR, _build_log_content, reset_session
from database.db import get_session
from services.audit import log_action

app_routes_bp = Blueprint('app_routes', __name__)

_letzte_gemeldete_version = 0

API_FRAGE_PROMPT_BASE = """Du bist ein Echtzeit-Vertriebsassistent. Der Berater hat live eine Frage gestellt.
{profile_ctx}
Letzter Gesprächskontext:
{ctx_text}

Frage des Beraters: {frage}

Antworte direkt, konkret, max 2-3 Sätze. Kein Fettdruck, kein Markdown. Immer mit einer offenen Gegenfrage enden."""

OBJECTION_TRIGGER_PROMPT_BASE = """Du bist ein Echtzeit-Vertriebsassistent. Der Kunde hat gerade einen Einwand geäußert.
{profile_ctx}
Einwand-Typ: {einwand_typ}

Letzter Gesprächskontext:
{ctx_text}

Liefere ein konkretes Gegenargument für den Einwand "{einwand_typ}". Max 2-3 Sätze. Kein Fettdruck, kein Markdown. Ende mit einer offenen Gegenfrage."""


@app_routes_bp.route('/live')
@login_required
def live():
    # Fair-Use soft-limit check (never hard-block)
    from datetime import date as _date, datetime as _dt
    from flask import flash
    from database.models import Organisation as _OrgModel
    db_fu = get_session()
    try:
        from database.models import User as _UModel
        _fu_user = db_fu.get(_UModel, g.user.id)
        if _fu_user:
            today = _date.today()
            # Monthly reset (user-level)
            if not _fu_user.usage_reset_date or _fu_user.usage_reset_date.month != today.month or _fu_user.usage_reset_date.year != today.year:
                _fu_user.minuten_used = 0
                _fu_user.trainings_voice_used = 0
                _fu_user.usage_reset_date = today
                db_fu.commit()
            limit = g.org.minuten_limit or 1000
            used  = _fu_user.minuten_used or 0
            if used >= limit:
                flash(f'Du hast dein monatliches Kontingent von {limit} Minuten erreicht. Kontaktiere uns für ein Upgrade.', 'warning')
            elif used >= int(limit * 0.9):
                flash(f'Fair-Use: {used} von {limit} Minuten verbraucht ({round(used/limit*100)}%). Fast aufgebraucht.', 'info')
        # Org-level fair-use monthly reset
        _org = db_fu.get(_OrgModel, g.org.id)
        if _org:
            today_month = _dt.now().strftime('%Y-%m')
            if _org.fair_use_reset_month != today_month:
                _org.live_minutes_used = 0
                _org.training_sessions_used = 0
                _org.fair_use_reset_month = today_month
                db_fu.commit()
            # Soft-warn at 80% of limit (1000 min limit)
            org_limit = _org.minuten_limit or 1000
            org_used  = _org.live_minutes_used or 0
            if org_used >= int(org_limit * 0.8):
                print(f'[FairUse] Org {_org.id} at {org_used}/{org_limit} live minutes (80%+ warning)')
    except Exception as _e:
        print(f'[FairUse] {_e}')
    finally:
        db_fu.close()
    db = get_session()
    try:
        from database.models import Profile
        active_profile = None
        apid = flask_session.get('active_profile_id')
        if not apid:
            u = db.get(type(g.user), g.user.id)
            if u and u.active_profile_id:
                apid = u.active_profile_id
                flask_session['active_profile_id'] = apid
        if apid:
            active_profile = db.query(Profile).filter_by(id=apid, org_id=g.org.id).first()
        profiles = db.query(Profile).filter_by(org_id=g.org.id).order_by(Profile.name).all()
        # Phasen aus aktivem Profil extrahieren
        active_phasen = []
        if active_profile and active_profile.daten:
            try:
                import json as _json
                pd = _json.loads(active_profile.daten)
                active_phasen = pd.get('phasen', [])
            except Exception:
                pass
        import json as _json2
        try:
            ad = _json2.loads(active_profile.daten) if active_profile and active_profile.daten else {}
        except Exception:
            ad = {}
        # active_profile_daten: parsed JSON of active profile for Opener section (D-19)
        import json as _json3
        active_profile_daten = {}
        if active_profile and active_profile.daten:
            try:
                active_profile_daten = _json3.loads(active_profile.daten) if isinstance(active_profile.daten, str) else active_profile.daten
            except Exception:
                active_profile_daten = {}
        ls.set_active_profile(active_profile.name if active_profile else '', ad)
        return render_template('app.html', user=g.user, org=g.org,
                               active_profile=active_profile, profiles=profiles,
                               active_phasen=active_phasen,
                               active_profile_daten=active_profile_daten)
    finally:
        db.close()


@app_routes_bp.route('/api/ergebnis')
@login_required
def api_ergebnis():
    global _letzte_gemeldete_version
    with ls.state_lock:
        payload = {
            'version':          ls.state['version'],
            'aktiv':            ls.state['aktiv'],
            'ergebnis':         ls.state['ergebnis'],
            'line_id':          ls.state['line_id'],
            'kaufbereitschaft': ls.state.get('kaufbereitschaft', 30),
            'ewb_top2':         ls.state.get('ewb_top2'),  # AI-ranked top 2 EWBs, or None
        }
    payload['speech_stats'] = ls.get_speech_stats()
    if payload['version'] > _letzte_gemeldete_version:
        _letzte_gemeldete_version = payload['version']
        print(f"[API] Neues Ergebnis v{payload['version']} (line {payload['line_id']}) an Browser")
    return jsonify(payload)


@app_routes_bp.route('/api/analyse_line', methods=['POST'])
@login_required
def api_analyse_line():
    from services.claude_service import analysiere_mit_claude
    data    = request.get_json(force=True)
    text    = data.get('text', '').strip()
    line_id = data.get('line_id', '')
    if not text:
        return jsonify({'error': 'no text'}), 400
    with ls.buffer_lock:
        kontext = " ".join(ls.analysiert_bisher[-20:])
    try:
        print(f"[Claude-1] Manuelle Analyse (line {line_id}): {text[:80]}…")
        ergebnis = analysiere_mit_claude(text, kontext)
        ts = datetime.now().strftime('%H:%M:%S')
        with ls.log_lock:
            ls.conversation_log.append({
                'ts': ts, 'type': 'analyse',
                'speaker': 1, 'text': text, 'data': ergebnis,
            })
        return jsonify({'ergebnis': ergebnis, 'line_id': line_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app_routes_bp.route('/api/log_correction', methods=['POST'])
@login_required
def api_log_correction():
    data = request.get_json(force=True)
    typ  = data.get('type', '')
    ts   = datetime.now().strftime('%H:%M:%S')
    with ls.log_lock:
        ls.conversation_log.append({
            'ts':          ts,
            'type':        typ,
            'von':         data.get('von', ''),
            'nach':        data.get('nach', ''),
            'einwand_typ': data.get('einwand_typ', ''),
            'line_id':     data.get('line_id', ''),
        })
    return jsonify({'ok': True})


@app_routes_bp.route('/api/pause', methods=['POST'])
@login_required
def api_pause():
    with ls.pause_lock:
        ls.is_paused = not ls.is_paused
        paused = ls.is_paused
    print(f"[API] Analyse {'pausiert' if paused else 'aktiv'}")
    return jsonify({'paused': paused})


@app_routes_bp.route('/api/swap_roles', methods=['POST'])
@login_required
def api_swap_roles():
    with ls.roles_lock:
        ls.roles_swapped = not ls.roles_swapped
        swapped = ls.roles_swapped
    print(f"[API] Rollen getauscht: {'Sp0=Kunde/Sp1=Berater' if swapped else 'Sp0=Berater/Sp1=Kunde'}")
    return jsonify({'swapped': swapped})


@app_routes_bp.route('/api/status')
@login_required
def api_status():
    with ls.pause_lock:
        return jsonify({'paused': ls.is_paused})


@app_routes_bp.route('/api/log')
@login_required
def api_log():
    profile_name = ''
    apid = flask_session.get('active_profile_id')
    if apid:
        db2 = get_session()
        try:
            from database.models import Profile as ProfileModel
            p = db2.get(ProfileModel, apid)
            if p:
                profile_name = p.name
        finally:
            db2.close()
    content = _build_log_content(user_email=g.user.email, profile_name=profile_name)
    return Response(
        content,
        mimetype='text/plain; charset=utf-8',
        headers={'Content-Disposition': 'attachment; filename=nerve_log.txt'}
    )


@app_routes_bp.route('/api/beenden', methods=['POST'])
@login_required
def api_beenden():
    req_data = request.get_json(silent=True) or {}
    session_mode = req_data.get('session_mode', 'meeting')
    profile_name = ''
    apid = flask_session.get('active_profile_id')
    if apid:
        db2 = get_session()
        try:
            from database.models import Profile as ProfileModel
            p = db2.get(ProfileModel, apid)
            if p:
                profile_name = p.name
        finally:
            db2.close()

    # Post-Call-Daten vor Reset sammeln
    with ls.log_lock:
        log_entries = list(ls.conversation_log)
    with ls.painpoints_lock:
        pp_snapshot = list(ls.painpoints)
    with ls.kb_lock:
        kb_verlauf  = list(ls.kaufbereitschaft_verlauf)
        kb_end      = ls.kaufbereitschaft
    with ls.speech_lock:
        bw = ls.berater_words
        kw = ls.kunde_words
        _st = ls.session_start_time
    import time as _time
    dauer_sek = int(_time.monotonic() - _st) if _st else 0

    einwaende_liste = []
    kaufsignale_liste = []
    for e in log_entries:
        if e['type'] == 'analyse' and e.get('data', {}).get('einwand'):
            d = e['data']
            einwaende_liste.append({
                'typ': d.get('typ', '?'), 'intensitaet': d.get('intensitaet', '?'),
                'zitat': d.get('einwand_zitat', ''), 'ts': e.get('ts', ''),
            })
        if e['type'] == 'tipp' and e.get('kategorie') == 'signal':
            kaufsignale_liste.append({'text': e.get('text', ''), 'ts': e.get('ts', '')})

    # Skript-Abdeckung berechnen
    _, pdata = ls.get_active_profile()
    phasen_list = pdata.get('phasen', []) if pdata else []
    with ls.covered_phases_lock:
        cp_snapshot = set(ls.covered_phases)
    with ls.phase_lock:
        cp_snapshot.add(ls.aktive_phase_idx)
    if phasen_list:
        phasen_abdeckung = [
            {'name': ph.get('name', '?'), 'abgedeckt': i in cp_snapshot}
            for i, ph in enumerate(phasen_list)
        ]
        abgedeckt_count = sum(1 for x in phasen_abdeckung if x['abgedeckt'])
        gesamt_prozent  = round(abgedeckt_count / len(phasen_list) * 100)
    else:
        phasen_abdeckung = []
        gesamt_prozent   = 0

    postcall = {
        'einwaende': einwaende_liste,
        'kaufsignale': kaufsignale_liste,
        'painpoints': [{'text': p['text'], 'ts': p['ts']} for p in pp_snapshot],
        'berater_words': bw, 'kunde_words': kw,
        'kb_start': kb_verlauf[0]['wert'] if kb_verlauf else 30,
        'kb_end': kb_end,
        'kb_verlauf': kb_verlauf,
        'skript_abdeckung': {'gesamt_prozent': gesamt_prozent, 'phasen': phasen_abdeckung},
        'dauer_sek': dauer_sek,
    }

    # CRM-Export generieren
    try:
        from services.crm_service import generate_crm_export
        dsgvo_modus = getattr(g.org, 'dsgvo_modus', True)
        crm_data = generate_crm_export(
            log_entries, pp_snapshot, einwaende_liste,
            kb_end, profile_name, dsgvo_modus=dsgvo_modus
        )
        postcall['crm_notiz']       = crm_data.get('crm_notiz', '')
        postcall['followup_email']  = crm_data.get('followup_email', '')
        postcall['naechste_schritte'] = crm_data.get('naechste_schritte', [])
    except Exception as e:
        print(f"[CRM] Fehler beim Generieren des CRM-Exports: {e}")
        postcall['crm_notiz']       = ''
        postcall['followup_email']  = ''
        postcall['naechste_schritte'] = []

    # Sammle Tracking-Daten vor dem Reset
    with ls.gegenargument_log_lock:
        ga_details = list(ls.gegenargument_log)
        # Letzten Eintrag abschließen
        if ga_details and ga_details[-1]['kb_nachher'] is None:
            ga_details[-1]['kb_nachher'] = kb_end
            ga_details[-1]['kb_delta']   = kb_end - ga_details[-1]['kb_vorher']
            ga_details[-1]['erfolgreich'] = ga_details[-1]['kb_delta'] > 0
    with ls.phasen_log_lock:
        ph_details = list(ls.phasen_log)
    with ls.hilfe_log_lock:
        hilfe_count = len(ls.hilfe_log)
    with ls.quick_action_log_lock:
        qa_count = len(ls.quick_action_log)

    content  = _build_log_content(user_email=g.user.email, profile_name=profile_name)
    filename = f"nerve_log_U{g.user.id}_{datetime.now().strftime('%Y-%m-%dT%H-%M-%S')}.txt"
    filepath = os.path.join(LOG_DIR, filename)
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"[Beenden] Log gespeichert: {filepath}")
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

    # ── In DB speichern ───────────────────────────────────────────────────────
    import json as _json
    from database.models import ConversationLog
    stats = ls.get_speech_stats()
    kb_min_val = min((v['wert'] for v in kb_verlauf), default=30)
    kb_max_val = max((v['wert'] for v in kb_verlauf), default=30)
    kb_start_val = kb_verlauf[0]['wert'] if kb_verlauf else 30
    skript_pct = postcall.get('skript_abdeckung', {}).get('gesamt_prozent', 0)
    started = datetime.now()  # approximation — real start tracked via session_start_time
    db_conv = get_session()
    try:
        conv = ConversationLog(
            user_id=g.user.id,
            org_id=g.org.id,
            profile_id=flask_session.get('active_profile_id'),
            profile_name=profile_name,
            started_at=started,
            ended_at=datetime.now(),
            dauer_sekunden=int(postcall.get('dauer_sek', 0)),
            segmente_gesamt=len([e for e in log_entries if e['type'] == 'transcript']),
            einwaende_gesamt=len(einwaende_liste),
            einwaende_behandelt=len([x for x in ga_details if x.get('erfolgreich') is True]),
            einwaende_fehlgeschlagen=len([x for x in ga_details if x.get('erfolgreich') is False]),
            einwaende_ignoriert=len([x for x in ga_details if x.get('gewaehlte_option') is None]),
            vorwaende_erkannt=len([x for x in ga_details if x.get('ist_vorwand') is True]),
            kb_start=kb_start_val,
            kb_end=kb_end,
            kb_min=kb_min_val,
            kb_max=kb_max_val,
            redeanteil_avg=stats.get('redeanteil', 0),
            tempo_avg=stats.get('tempo', 0),
            laengster_monolog=stats.get('monolog', 0),
            hilfe_genutzt=hilfe_count,
            quick_actions=qa_count,
            skript_abdeckung=skript_pct,
            gegenargument_details=_json.dumps(ga_details, ensure_ascii=False),
            painpoints_details=_json.dumps([{'text': p['text'], 'ts': p['ts']} for p in pp_snapshot], ensure_ascii=False),
            phasen_details=_json.dumps(ph_details, ensure_ascii=False),
            typ='live',
            session_mode=session_mode,
        )
        db_conv.add(conv)
        db_conv.commit()
        print(f"[DB] Gespräch gespeichert: conv.id={conv.id}")

        # ── ObjectionEvents: granulare EWB-Klicks persistieren (Plan 03) ──────────
        from database.models import ObjectionEvent
        with ls.state_lock:
            ewb_clicks = list(ls.state.get('ewb_clicks', []))
        for click in ewb_clicks:
            db_conv.add(ObjectionEvent(
                user_id=g.user.id,
                org_id=g.org.id,
                conversation_log_id=conv.id,
                einwand_typ=click['einwand_typ'],
                success=click['success'],
            ))
        if ewb_clicks:
            db_conv.commit()

        # ── Audit: session_start + session_end (DSGVO: nur Aggregate, kein Transkript) ─
        log_action(db_conv, g.user.id, g.org.id, 'session_start',
                   target_type='conversation_log', target_id=conv.id,
                   details={'mode': session_mode}, request=request)
        log_action(db_conv, g.user.id, g.org.id, 'session_end',
                   target_type='conversation_log', target_id=conv.id,
                   details={
                       'mode': conv.session_mode,
                       'dauer_sekunden': conv.dauer_sekunden,
                       'einwaende_total': conv.einwaende_gesamt,
                       'einwaende_ok':    conv.einwaende_behandelt,
                   },
                   request=request)

        # Award points for completing a live call
        try:
            from database.models import User as UserModel
            live_user = db_conv.get(UserModel, g.user.id)
            if live_user:
                einwaende_ok = len([x for x in ga_details if x.get('erfolgreich') is True])
                live_user.total_points = (live_user.total_points or 0) + 20 + (einwaende_ok * 5)
                live_user.live_calls_used = (live_user.live_calls_used or 0) + 1
                # Track minutes used (Fair-Use)
                dauer_sek = int(postcall.get('dauer_sek', 0))
                if dauer_sek <= 0 and kb_verlauf:
                    pass  # dauer_sek may be 0 if not tracked; keep existing
                minuten = max(1, round(dauer_sek / 60)) if dauer_sek > 0 else 1
                live_user.minuten_used = (live_user.minuten_used or 0) + minuten
                # Org-level live minutes tracking
                try:
                    from database.models import Organisation as _OrgModel2
                    from datetime import datetime as _dt2
                    _org2 = db_conv.get(_OrgModel2, g.org.id)
                    if _org2:
                        today_month2 = _dt2.now().strftime('%Y-%m')
                        if _org2.fair_use_reset_month != today_month2:
                            _org2.live_minutes_used = 0
                            _org2.training_sessions_used = 0
                            _org2.fair_use_reset_month = today_month2
                        _org2.live_minutes_used = (_org2.live_minutes_used or 0) + minuten
                except Exception as _oe:
                    print(f'[FairUse] Org minutes update error: {_oe}')
                _LEVELS = [('rookie',0),('starter',200),('professional',1000),('expert',3000),('master',7000),('legend',15000)]
                for lname, threshold in reversed(_LEVELS):
                    if live_user.total_points >= threshold:
                        live_user.level = lname
                        break
                db_conv.commit()
        except Exception as ex:
            print(f"[Points] Fehler beim Punktevergabe: {ex}")
    except Exception as e:
        print(f"[DB] Fehler beim Speichern des Gesprächs: {e}")
    finally:
        db_conv.close()

    # Postcall-Snapshot speichern (bleibt nach reset erhalten)
    with ls.last_postcall_lock:
        ls.last_postcall = {'filename': filename, **postcall}

    reset_session()
    print("[Beenden] State zurückgesetzt.")
    return jsonify({'ok': True, 'filename': filename, 'postcall': postcall})


@app_routes_bp.route('/api/keepalive', methods=['POST'])
@login_required
def api_keepalive():
    return jsonify({'ok': True})


@app_routes_bp.route('/api/set_profile', methods=['POST'])
@login_required
def api_set_profile():
    from database.models import Profile as ProfileModel, User as UserModel
    pid = request.get_json(force=True).get('profile_id')
    db = get_session()
    try:
        p = db.query(ProfileModel).filter_by(id=pid, org_id=g.org.id).first()
        if not p:
            return jsonify({'error': 'not found'}), 404
        flask_session['active_profile_id'] = p.id
        import json as _json
        try:
            daten = _json.loads(p.daten) if p.daten else {}
        except Exception:
            daten = {}
        ls.set_active_profile(p.name, daten)
        u = db.get(UserModel, g.user.id)
        if u:
            u.active_profile_id = p.id
            db.commit()
        return jsonify({'ok': True, 'name': p.name, 'phasen': daten.get('phasen', [])})
    finally:
        db.close()


@app_routes_bp.route('/api/set_phase', methods=['POST'])
@login_required
def api_set_phase():
    data = request.get_json(force=True)
    idx  = data.get('phase_index', 0)
    phase_name = data.get('phase_name', str(idx))
    ts = datetime.now().strftime('%H:%M:%S')
    with ls.phasen_log_lock:
        alte_phase = ls.phasen_log[-1].get('nach_phase', '') if ls.phasen_log else ''
        with ls.buffer_lock:
            seg_count = len(ls.analysiert_bisher)
        ls.phasen_log.append({
            'ts':            ts,
            'von_phase':     alte_phase,
            'nach_phase':    phase_name,
            'segment_count': seg_count,
        })
    with ls.phase_lock:
        ls.aktive_phase_idx = int(idx)
    with ls.covered_phases_lock:
        ls.covered_phases.add(int(idx))
    return jsonify({'ok': True, 'phase_index': ls.aktive_phase_idx})


@app_routes_bp.route('/api/log_gegenargument_wahl', methods=['POST'])
@login_required
def log_gegenargument_wahl():
    data = request.get_json(force=True)
    with ls.gegenargument_log_lock:
        for entry in reversed(ls.gegenargument_log):
            if entry['gewaehlte_option'] is None:
                entry['gewaehlte_option'] = data.get('gewaehlte_option')
                entry['kb_vorher'] = data.get('kb_aktuell', entry['kb_vorher'])
                break
    return jsonify({'ok': True})


@app_routes_bp.route('/api/frage', methods=['POST'])
@login_required
def api_frage():
    import anthropic as _ant
    from config import ANTHROPIC_API_KEY
    data    = request.get_json(force=True)
    frage   = data.get('frage', '').strip()
    context = data.get('context', [])  # letzte 3 Segmente
    if not frage:
        return jsonify({'error': 'no question'}), 400
    ctx_text = '\n'.join(f"[{s.get('speaker','?')}] {s.get('text','')}" for s in context[-3:])
    pname, pdata = ls.get_active_profile()
    profile_ctx = ''
    if pdata:
        profile_ctx = f'\nProdukt: {pdata.get("produkt","")}\n'
        if pdata.get('einwaende'):
            profile_ctx += 'Bekannte Einwände: ' + ', '.join(e.get('typ','') for e in pdata['einwaende']) + '\n'
        ki = pdata.get('ki', {})
        if ki.get('zusatz'):
            profile_ctx += f'KI-Anweisung: {ki["zusatz"]}\n'
    prompt = API_FRAGE_PROMPT_BASE.format(
        profile_ctx=profile_ctx,
        ctx_text=ctx_text if ctx_text else '(kein Kontext)',
        frage=frage,
    )
    try:
        client   = _ant.Anthropic(api_key=ANTHROPIC_API_KEY)
        msg      = client.messages.create(
            model='claude-haiku-4-5-20251001', max_tokens=200,
            messages=[{'role': 'user', 'content': prompt}]
        )
        antwort = msg.content[0].text.strip()
        # Quick-Action loggen
        with ls.quick_action_log_lock:
            ls.quick_action_log.append({
                'ts':     datetime.now().strftime('%H:%M:%S'),
                'typ':    data.get('typ', 'frage'),
                'frage':  frage,
                'antwort': antwort,
            })
        return jsonify({'ok': True, 'antwort': antwort})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app_routes_bp.route('/api/ewb_trigger', methods=['POST'])
@login_required
def api_ewb_trigger():
    import anthropic as _ant
    from config import ANTHROPIC_API_KEY
    data = request.get_json(force=True)
    einwand_typ = data.get('einwand_typ', '').strip()
    if not einwand_typ:
        return jsonify({'error': 'no einwand_typ'}), 400

    # Last 3 transcript segments as context
    with ls.log_lock:
        recent = [e for e in ls.conversation_log if e['type'] == 'transcript'][-3:]
    ctx_text = '\n'.join(f"[{e.get('speaker','?')}] {e.get('text','')}" for e in recent)

    # Profile context
    pname, pdata = ls.get_active_profile()
    profile_ctx = ''
    if pdata:
        profile_ctx = f'\nProdukt: {pdata.get("produkt","")}\n'
        # Check for matching Gegenargument in profile
        matching_ga = ''
        for ew in pdata.get('einwaende', []):
            if ew.get('typ', '').lower() == einwand_typ.lower():
                matching_ga = ew.get('gegenargument', '')
                break
        if matching_ga:
            profile_ctx += f'Vorbereitetes Gegenargument: {matching_ga}\n'
        ki = pdata.get('ki', {})
        if ki.get('zusatz'):
            profile_ctx += f'KI-Anweisung: {ki["zusatz"]}\n'

    prompt = OBJECTION_TRIGGER_PROMPT_BASE.format(
        profile_ctx=profile_ctx,
        einwand_typ=einwand_typ,
        ctx_text=ctx_text if ctx_text else '(kein Kontext)',
    )

    try:
        client = _ant.Anthropic(api_key=ANTHROPIC_API_KEY)
        msg = client.messages.create(
            model='claude-haiku-4-5-20251001', max_tokens=200,
            messages=[{'role': 'user', 'content': prompt}]
        )
        antwort = msg.content[0].text.strip()
        # Log as quick action with typ='ewb' (per D-18)
        with ls.quick_action_log_lock:
            ls.quick_action_log.append({
                'ts': datetime.now().strftime('%H:%M:%S'),
                'typ': 'ewb',
                'frage': einwand_typ,
                'antwort': antwort,
            })
        # Granulares EWB-Klick-Tracking fuer objection_events (Plan 03)
        from services.live_session import record_ewb_click
        record_ewb_click(einwand_typ=einwand_typ, success=False)
        return jsonify({'ok': True, 'antwort': antwort, 'einwand_typ': einwand_typ})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app_routes_bp.route('/api/feedback', methods=['POST'])
@login_required
def api_feedback():
    from database.models import FeedbackEvent, ConversationLog
    data           = request.get_json(force=True)
    stars          = data.get('stars')
    comment        = data.get('comment', '')
    session_log_id = data.get('session_log_id', '')
    if not stars or not (1 <= int(stars) <= 5):
        return jsonify({'error': 'invalid stars'}), 400
    db = get_session()
    try:
        fb = FeedbackEvent(
            user_id=g.user.id, session_log_id=session_log_id,
            stars=int(stars), comment=comment,
        )
        db.add(fb)
        # Auch neuestes ConversationLog mit Sterne aktualisieren
        latest = (db.query(ConversationLog)
                  .filter_by(user_id=g.user.id)
                  .order_by(ConversationLog.created_at.desc())
                  .first())
        if latest and latest.sterne is None:
            latest.sterne    = int(stars)
            latest.kommentar = comment
        db.commit()
        return jsonify({'ok': True})
    finally:
        db.close()


@app_routes_bp.route('/api/postcall_insights', methods=['POST'])
@login_required
def api_postcall_insights():
    import anthropic as _ant
    from config import ANTHROPIC_API_KEY
    data      = request.get_json(force=True)
    einwaende = data.get('einwaende', [])
    painpoints = data.get('painpoints', [])
    kb_start  = data.get('kb_start', 30)
    kb_end    = data.get('kb_end', 30)
    prompt = f"""Du bist ein Vertriebsanalyse-Assistent. Analysiere dieses abgeschlossene Verkaufsgespräch und gib genau 3 prägnante Erkenntnisse (Bullets) zurück.

Erkannte Einwände ({len(einwaende)}): {', '.join(e.get('typ','?') for e in einwaende) or 'keine'}
Painpoints: {', '.join(p.get('text','') for p in painpoints) or 'keine'}
Kaufbereitschaft: {kb_start}% → {kb_end}%

Antworte als JSON-Array mit exakt 3 Strings:
["Erkenntnis 1", "Erkenntnis 2", "Erkenntnis 3"]
Max 15 Wörter pro Bullet. Kein Markdown."""
    try:
        client = _ant.Anthropic(api_key=ANTHROPIC_API_KEY)
        msg    = client.messages.create(
            model='claude-haiku-4-5-20251001', max_tokens=300,
            messages=[{'role': 'user', 'content': prompt}]
        )
        import json as _json
        text = msg.content[0].text.strip()
        start = text.find('[')
        end   = text.rfind(']') + 1
        bullets = _json.loads(text[start:end])
        return jsonify({'ok': True, 'bullets': bullets[:3]})
    except Exception as e:
        return jsonify({'ok': True, 'bullets': ['Keine Insights verfügbar.', '', '']})
