import os
from datetime import datetime
from flask import Blueprint, jsonify, request, g, session as flask_session
from routes.auth import login_required
import services.live_session as ls
from services.live_session import LOG_DIR, _build_log_content, reset_session
from database.db import get_session
from services.audit import log_action

app_routes_bp = Blueprint('app_routes', __name__)


class _CapExceeded(Exception):
    """Sentinel raised inside with _db.begin() to signal cap exceeded without error (WR-02)."""


OBJECTION_TRIGGER_PROMPT_BASE = """Du bist ein Echtzeit-Vertriebsassistent. Der Kunde hat gerade einen Einwand geäußert.
{profile_ctx}
Einwand-Typ: {einwand_typ}

Aktuelle Phase: {current_phase_name} (Phase {current_phase})
Aktuelle Kaufbereitschaft: {readiness_score}% ({readiness_bucket})
{inference_hint}
Letzter Gesprächskontext:
{ctx_text}

Liefere ein konkretes Gegenargument für den Einwand "{einwand_typ}", passend zur aktuellen Phase und Kaufbereitschaft. Max 2-3 Sätze. Kein Fettdruck, kein Markdown. Ende mit einer offenen Gegenfrage."""


@app_routes_bp.route('/live')
@login_required
def live():
    # Classic-View entfernt (Block F). Redirect auf Dashboard.
    from flask import redirect, url_for
    return redirect(url_for('dashboard.index'))


@app_routes_bp.route('/api/beenden', methods=['POST'])
@login_required
def api_beenden():
    req_data = request.get_json(silent=True) or {}
    session_mode = req_data.get('session_mode', 'meeting')
    # POLISH-40: Accept string, dict-with-.text (Frontend sends whole briefing
    # object from pip-launcher.js), or fall back to live_session.state which is
    # populated at start_live_session via deepgram_service.
    precall_briefing = req_data.get('precall_briefing', None)
    if isinstance(precall_briefing, dict):
        precall_briefing = precall_briefing.get('text') or None
    if not isinstance(precall_briefing, str) or not precall_briefing.strip():
        # Fall back to runtime state (set in services/deepgram_service.py)
        try:
            with ls.state_lock:
                state_pb = ls.state.get('precall_briefing')
            if isinstance(state_pb, str) and state_pb.strip():
                precall_briefing = state_pb
            else:
                precall_briefing = None
        except Exception:
            precall_briefing = None
    if isinstance(precall_briefing, str) and len(precall_briefing) > 2000:
        precall_briefing = precall_briefing[:2000]
    # Phase 08.20.2: Schicht-1 structured fields (T-08.20.2-06: isinstance check before dumps)
    precall_fields_raw = req_data.get('precall_fields', None)
    precall_fields_json = None
    if isinstance(precall_fields_raw, dict):
        import json as _json_pf
        try:
            precall_fields_json = _json_pf.dumps(precall_fields_raw, ensure_ascii=False)
        except Exception:
            precall_fields_json = None
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

    # Skript-Abdeckung berechnen — D-05: DB ist Single Source of Truth, kein ls.get_active_profile()
    try:
        from database.db import SessionLocal as _sl
        from database.models import Profile as _Prof
        import json as _json
        _pid = flask_session.get('active_profile_id') or getattr(g.user, 'active_profile_id', None)
        if _pid:
            _db = _sl()
            try:
                _p = _db.query(_Prof).filter_by(id=_pid).first()
                pdata = _json.loads(_p.daten) if _p and _p.daten else {}
            finally:
                _db.close()
        else:
            pdata = {}
    except Exception:
        pdata = {}
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
    # 06.1-r2: Log-Write ist nice-to-have — darf Call-Beendigung nicht blockieren.
    # Perm-Fehler oder voller Disk wird geloggt, postcall laeuft trotzdem durch.
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"[Beenden] Log gespeichert: {filepath}")
    except Exception as e:
        print(f"[Beenden] WARN: Log-Write fehlgeschlagen ({e}) — postcall laeuft trotzdem durch")

    # Redeanteil fuer postcall + async analysis
    _stats = ls.get_speech_stats()
    redeanteil_berater = _stats.get('redeanteil', 50)
    redeanteil_kunde = 100 - redeanteil_berater

    # ── In DB speichern ───────────────────────────────────────────────────────
    import json as _json
    from database.models import ConversationLog
    # POLISH-38: einwaende_gesamt = len(ewb_clicks) (User-Definition POLISH-29:
    # "EWB-Button gedrueckt = behandelt"). Read here so it's available before
    # ConversationLog-Insert (moved up from line ~435).
    with ls.state_lock:
        ewb_clicks = list(ls.state.get('ewb_clicks', []))
    saved_conv_id = None
    stats = _stats
    kb_min_val = min((v['wert'] for v in kb_verlauf), default=30)
    kb_max_val = max((v['wert'] for v in kb_verlauf), default=30)
    kb_start_val = kb_verlauf[0]['wert'] if kb_verlauf else 30
    skript_pct = postcall.get('skript_abdeckung', {}).get('gesamt_prozent', 0)
    started = datetime.now()  # approximation — real start tracked via session_start_time
    # Phase 08 D-14: session_anrede aus ls.state lesen (gesetzt in deepgram_service.py
    # handle_start_live_session bei whitelist-Werten 'Du'|'Sie'). None wenn nicht gesetzt
    # → ConversationLog.anrede bleibt NULL → build_profile_context nutzt Profile-Default.
    try:
        with ls.state_lock:
            _session_anrede = ls.state.get('session_anrede')
    except Exception:
        _session_anrede = None
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
            einwaende_gesamt=len(ewb_clicks),  # POLISH-38: count EWB-clicks, not AI-detected (POLISH-29 user definition)
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
            precall_briefing=precall_briefing,
            precall_fields=precall_fields_json,     # Phase 08.20.2: Schicht-1 JSON
            kb_verlauf=_json.dumps(kb_verlauf, ensure_ascii=False),   # Phase 07.1
            anrede=_session_anrede,  # Phase 08 D-14: Du/Sie oder None
        )
        db_conv.add(conv)
        db_conv.commit()
        saved_conv_id = conv.id
        print(f"[DB] Gespräch gespeichert: conv.id={conv.id}")

        # ── ObjectionEvents: granulare EWB-Klicks persistieren (Plan 03) ──────────
        # POLISH-38: ewb_clicks bereits weiter oben gelesen (vor ConversationLog-Insert).
        from database.models import ObjectionEvent
        for click in ewb_clicks:
            db_conv.add(ObjectionEvent(
                user_id=g.user.id,
                org_id=g.org.id,
                conversation_log_id=conv.id,
                einwand_typ=click['einwand_typ'],
                success=click['success'],
                antwort_text=click.get('antwort_text'),
                einwand_text=click.get('einwand_text'),
            ))
        if ewb_clicks:
            db_conv.commit()

        # POLISH-38 (Haupt-Fix): Re-aggregate counters from ObjectionEvent (authoritative source).
        # cf38589 set einwaende_gesamt=len(ewb_clicks) initially - defensive fallback.
        # Here we overwrite with the DB-truth: einwaende_behandelt becomes SUM(success)
        # from the just-committed ObjectionEvent rows (POLISH-29: "EWB-Button gedrueckt
        # = behandelt", success-Flag aus POLISH-38.1 spiegelt erfolgreichen Haiku-Spawn).
        # Defence-in-depth: works even if ewb_clicks list had stale state.
        try:
            from sqlalchemy import func as _sqlfunc, case as _sqlcase
            _agg = (
                db_conv.query(
                    _sqlfunc.count(ObjectionEvent.id),
                    _sqlfunc.sum(_sqlcase((ObjectionEvent.success == True, 1), else_=0)),
                )
                .filter(ObjectionEvent.conversation_log_id == conv.id)
                .one()
            )
            _total = int(_agg[0] or 0)
            _ok = int(_agg[1] or 0)
            if _total > 0 and (conv.einwaende_gesamt != _total or conv.einwaende_behandelt != _ok):
                conv.einwaende_gesamt = _total
                conv.einwaende_behandelt = _ok
                db_conv.commit()
                print(f"[POLISH-38] counters reconciled conv.id={conv.id} gesamt={_total} behandelt={_ok}")
        except Exception as _reconcile_err:
            print(f"[POLISH-38] counter reconcile fehlgeschlagen (conv.id={conv.id}): {_reconcile_err}")

        # POLISH-54: Merge ObjectionEvent-Rows in postcall['einwaende'] so dass Cold-Call
        # (kein Analyse-Loop seit Phase 06.3) nicht "-" in der Postcall-Kachel zeigt.
        # Analog zu POLISH-38-Reconcile oben: DB ist Single Source of Truth.
        # Additiv: existierende einwaende_liste (aus log_entries, Meeting-Analyse-Loop)
        # bleibt erhalten, ObjectionEvent-Rows werden gemergt mit Dedup (typ+ts-Bucket).
        # CRM (oben) und run_postcall_engine (unten) lesen die LOKALE einwaende_liste-
        # Variable - nicht postcall['einwaende'] - und sind daher regression-sicher.
        try:
            _oe_rows = (
                db_conv.query(ObjectionEvent)
                .filter(ObjectionEvent.conversation_log_id == conv.id)
                .order_by(ObjectionEvent.created_at.asc())
                .all()
            )
            if _oe_rows:
                from datetime import datetime as _dt_polish54
                def _ts_bucket(iso_str):
                    if not iso_str:
                        return None
                    try:
                        s = iso_str.replace('Z', '+00:00') if iso_str.endswith('Z') else iso_str
                        dt = _dt_polish54.fromisoformat(s)
                        return int(dt.timestamp() // 5) * 5
                    except Exception:
                        return None
                _seen = set()
                for _ex in (postcall.get('einwaende') or []):
                    _typ_ex = (_ex.get('typ') or '').lower()
                    if _typ_ex:
                        _seen.add((_typ_ex, _ts_bucket(_ex.get('ts') or '')))
                _new_entries = []
                _merged_from_oe = 0
                for _oe in _oe_rows:
                    _typ = (_oe.einwand_typ or '').strip()
                    if not _typ:
                        continue
                    _iso = _oe.created_at.isoformat() if _oe.created_at else ''
                    _key = (_typ.lower(), _ts_bucket(_iso))
                    if _key in _seen:
                        continue
                    _seen.add(_key)
                    _new_entries.append({
                        'typ': _typ,
                        'zitat': '',
                        'intensitaet': 'mittel',
                        'ts': _iso,
                    })
                    _merged_from_oe += 1
                if _new_entries:
                    postcall['einwaende'] = list(postcall.get('einwaende') or []) + _new_entries
                    print(f"[POLISH-54] einwaende merged from ObjectionEvent conv.id={conv.id} added={_merged_from_oe} total={len(postcall['einwaende'])}")
        except Exception as _polish54_err:
            print(f"[POLISH-54] merge ObjectionEvent->postcall.einwaende fehlgeschlagen (conv.id={conv.id}): {_polish54_err}")

        # FT logging: update ft_call_sessions with aggregates (Phase 04.7.1)
        try:
            from database.models import FtCallSession
            with ls.state_lock:
                ft_session_id = ls.state.get('ft_session_id')
                buttons_pressed = len(ls.state.get('ewb_clicks') or [])
            readiness_end = getattr(ls, 'kaufbereitschaft', None)
            if ft_session_id:
                ft_row = db_conv.query(FtCallSession).filter_by(id=ft_session_id).first()
                if ft_row:
                    ft_row.duration_seconds = int(postcall.get('dauer_sek', 0))
                    ft_row.hints_shown = len([e for e in log_entries if e.get('type') == 'tipp'])
                    ft_row.hints_used = hilfe_count
                    ft_row.buttons_pressed = buttons_pressed
                    ft_row.readiness_score_end = readiness_end
                    ft_row.readiness_score_start = kb_start_val
                    ft_row.conversation_log_id = conv.id if 'conv' in locals() and conv else None
                    ft_row.outcome = (req_data.get('outcome') or 'unknown')
                    db_conv.commit()
                with ls.state_lock:
                    ls.state['ft_session_id'] = None
        except Exception as _e:
            print(f"[FT] ft_call_sessions update failed: {_e}")

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

        # ── Phase 04.12: Integration Engine — Post-Call Events + Muster (D-03) ──
        try:
            from services.integration_engine import run_postcall_engine
            run_postcall_engine(
                db_session=db_conv,
                user_id=g.user.id,
                conv_id=saved_conv_id,
                einwaende=einwaende_liste,
                ewb_clicks=ewb_clicks,
                ga_details=ga_details,
            )
        except Exception as _ie:
            print(f"[Engine] Post-Call Engine Fehler: {_ie}")
    except Exception as e:
        print(f"[DB] Fehler beim Speichern des Gesprächs: {e}")
    finally:
        db_conv.close()

    # Postcall-Snapshot speichern (bleibt nach reset erhalten)
    with ls.last_postcall_lock:
        ls.last_postcall = {'filename': filename, **postcall}

    # Add additional fields for async postcall analysis
    postcall['redeanteil_berater'] = redeanteil_berater
    postcall['redeanteil_kunde'] = redeanteil_kunde
    postcall['ga_details'] = ga_details

    # D-12: Trainings-Empfehlung fuer PostCall-Overlay
    try:
        db_rec = get_session()
        try:
            from database.models import User as _URec
            _u_rec = db_rec.get(_URec, g.user.id)
            if _u_rec and _u_rec.pending_training_recommendation:
                import json as _jrec
                postcall['training_recommendation'] = _jrec.loads(_u_rec.pending_training_recommendation)
        finally:
            db_rec.close()
    except Exception:
        pass

    reset_session()
    print("[Beenden] State zurückgesetzt.")
    return jsonify({'ok': True, 'filename': filename, 'postcall': postcall, 'conv_id': saved_conv_id})


@app_routes_bp.route('/api/keepalive', methods=['POST'])
@login_required
def api_keepalive():
    return jsonify({'ok': True})


def _calc_call_score(conv):
    """Server-seitige Spiegelung der client-seitigen _calcScore()-Formel in pip-launcher.js.
    Gewichtung: kb_end 40%, behandeltRate 30%, redeScore 20%, skript 10%."""
    kb = conv.kb_end if conv.kb_end is not None else 30
    einw_total = conv.einwaende_gesamt or 0
    einw_ok = conv.einwaende_behandelt or 0
    behandelt_rate = (einw_ok / einw_total) if einw_total > 0 else 0.5
    redeanteil = conv.redeanteil_avg if conv.redeanteil_avg is not None else 50
    rede_score = max(0, 100 - abs(redeanteil - 40) * 2)
    skript = conv.skript_abdeckung or 0
    return min(100, max(0, round(kb * 0.4 + behandelt_rate * 100 * 0.3 + rede_score * 0.2 + skript * 0.1)))


# ========================================================================
# Phase 07.1: POLISH-24 Practice Recommendations Helper
# ========================================================================

def _cross_context_objections_live(db, user_id, einwand_typ):
    """Live-Session -> wie oft/gut im Training mit diesem Einwand?
    Returns: {sessions: int, avg_score: float|None, focus_match: str}
    Filter: typ='training', letzte 14 Tage, einwand_typ match.
    Score basiert auf kb_end (Training), NICHT sterne (SC-1 — Training setzt sterne NICHT).
    Root-Entity: OE explizit via select_from() (W-01 — query mit Aggregaten + JOIN).
    """
    from datetime import datetime, timedelta
    from sqlalchemy import func
    from database.models import ConversationLog as CL, ObjectionEvent as OE
    try:
        cutoff = datetime.utcnow() - timedelta(days=14)
        row = (db.query(
                    func.count(func.distinct(CL.id)).label('n'),
                    func.avg(CL.kb_end).label('avg_score'),
                )
                .select_from(OE)                              # W-01: Root explizit
                .join(CL, CL.id == OE.conversation_log_id)
                .filter(CL.user_id == user_id)
                .filter(CL.typ == 'training')
                .filter(CL.created_at >= cutoff)
                .filter(OE.einwand_typ == einwand_typ)
                .first())
        n = int(row.n or 0) if row else 0
        avg_score = float(row.avg_score) if (row and row.avg_score is not None) else None
        return {'sessions': n, 'avg_score': avg_score, 'focus_match': einwand_typ}
    except Exception as exc:
        print(f"[07.1] cross_context_objections_live failed: {exc}")
        return None


def _cross_context_objections_training(db, user_id, einwand_typ):
    """Training-Session -> wie oft/erfolgreich im Live-Call mit diesem Einwand?
    Returns: {sessions: int, n_success: int, focus_match: str}
    Filter: typ='live', letzte 14 Tage.
    Root-Entity: OE explizit via select_from() (W-01).
    """
    from datetime import datetime, timedelta
    from sqlalchemy import func, case
    from database.models import ConversationLog as CL, ObjectionEvent as OE
    try:
        cutoff = datetime.utcnow() - timedelta(days=14)
        # Rule 1 fix: ObjectionEvent-Column heisst `success`, nicht `erfolgreich`
        rows = (db.query(OE.success)
                .select_from(OE)                              # W-01: Root explizit
                .join(CL, CL.id == OE.conversation_log_id)
                .filter(CL.user_id == user_id)
                .filter(CL.typ == 'live')
                .filter(CL.created_at >= cutoff)
                .filter(OE.einwand_typ == einwand_typ)
                .all())
        n = len(rows)
        n_success = sum(1 for r in rows if r.success)
        return {'sessions': n, 'n_success': n_success, 'focus_match': einwand_typ}
    except Exception as exc:
        print(f"[07.1] cross_context_objections_training failed: {exc}")
        return None


def _derive_practice_recommendations(db, conv, events):
    """POLISH-24 R3 — typ+mode-aware practice recommendations.
    Returns: List[Dict] mit max 3 Eintraegen, sortiert nach Prioritaet.

    Keys pro Eintrag:
      icon: 'target' | 'alert-circle' | 'trending-down'
      observation: str (14px/600 konkrete Zahl + Beobachtung)
      explanation: str (14px/400 ein Satz)
      training_focus: str (ASCII-Slug)
      training_url: str (heute immer '/training')
      cross_context: dict | None (nur bei objection-Recommendations)
    """
    recs = []
    typ = getattr(conv, 'typ', 'live') or 'live'

    # UAT-R2 G: sync with template Fix B — kb_verlauf is source of truth when present
    # Der Helper liest hier den effektiven kb_end analog zur Fallback-Logik in
    # routes/dashboard.py (session_detail) und im Template. Ohne diesen Shim sähe der
    # User im Chart/Score z.B. 30, aber in der Recommendation-Card "Kaufbereitschaft
    # Ende: 20/100" (alter DB-Wert).
    kb_end_effective = conv.kb_end
    try:
        import json as _json_kb
        if conv.kb_verlauf:
            _verl = _json_kb.loads(conv.kb_verlauf)
            if isinstance(_verl, list) and _verl:
                _last = _verl[-1]
                if isinstance(_last, dict) and 'wert' in _last:
                    kb_end_effective = _last.get('wert')
    except Exception:
        kb_end_effective = conv.kb_end
    if kb_end_effective is None:
        kb_end_effective = 0

    # ── Training-spezifische Regeln ────────────────────────────────
    if typ == 'training':
        # Regel 1: kb_end < 50 -> generic weakness
        if kb_end_effective < 50:
            recs.append({
                'icon': 'alert-circle',
                'observation': f'Gesamt-Score unter 50 ({kb_end_effective}/100)',
                'explanation': 'Allgemeine Schwäche erkannt. Wiederhole ein ähnliches Szenario.',
                'training_focus': 'training:generic_weakness',
                'training_url': '/training',
                'cross_context': None,
            })

        # Regel 2: Kunde hat aufgelegt (stimmung[-1] == -5)
        try:
            import json as _json_local
            hist = _json_local.loads(conv.stimmung_history or '[]')
            if hist and hist[-1].get('wert') == -5:
                pt_id = getattr(conv, 'personality_type_id', None)
                focus = f'training:personality_{pt_id}' if pt_id else 'training:mood_management'
                recs.append({
                    'icon': 'target',
                    'observation': 'Kunde hat aufgelegt (Stimmung -5)',
                    'explanation': 'Wiederhole mit dem gleichen Persönlichkeitstyp und fang Stimmungs-Drop früher ab.',
                    'training_focus': focus,
                    'training_url': '/training',
                    'cross_context': None,
                })
        except Exception:
            pass

        # Regel 3: Einwaende mit niedriger Behandlungs-Rate (Training -> Live cross)
        # Rule 1 fix: ObjectionEvent-Column heisst `success`, nicht `erfolgreich`
        for ev in (events or [])[:3]:
            if not getattr(ev, 'success', True):
                recs.append({
                    'icon': 'alert-circle',
                    'observation': f'Einwand "{ev.einwand_typ}" nicht erfolgreich behandelt',
                    'explanation': 'Im echten Call ist dieser Einwand häufig — übe die Antwort.',
                    'training_focus': f'objections:{ev.einwand_typ}',
                    'training_url': '/training',
                    'cross_context': _cross_context_objections_training(db, conv.user_id, ev.einwand_typ),
                })

        # Regel 4: Stimmungs-Verschlechterung (Drop >= 3 Punkte ueber Verlauf)
        try:
            import json as _json_local
            hist = _json_local.loads(conv.stimmung_history or '[]')
            if len(hist) >= 2:
                max_wert = max((h.get('wert', 0) for h in hist), default=0)
                min_wert = min((h.get('wert', 0) for h in hist), default=0)
                if (max_wert - min_wert) >= 3 and len(recs) < 3:
                    recs.append({
                        'icon': 'trending-down',
                        'observation': f'Stimmung fiel um {max_wert - min_wert} Punkte',
                        'explanation': 'Die Kundin wurde deutlich negativer. Übe Stimmungs-Management.',
                        'training_focus': 'training:mood_management',
                        'training_url': '/training',
                        'cross_context': None,
                    })
        except Exception:
            pass

    # ── Live-Regeln (cold_call + meeting) ──────────────────────────
    else:
        # Regel 1: Nicht behandelte Einwaende
        # Rule 1 fix: ObjectionEvent-Column heisst `success`, nicht `erfolgreich`
        not_handled = [ev for ev in (events or []) if not getattr(ev, 'success', True)]
        for ev in not_handled[:3]:
            recs.append({
                'icon': 'target',
                'observation': f'Einwand "{ev.einwand_typ}" nicht behandelt',
                'explanation': 'Im Training kannst du die Antwort mit weniger Druck festigen.',
                'training_focus': f'objections:{ev.einwand_typ}',
                'training_url': '/training',
                'cross_context': _cross_context_objections_live(db, conv.user_id, ev.einwand_typ),
            })

        # Regel 2: kb_end < 40 -> drop
        # UAT-R2 G: nutzt kb_end_effective (= kb_verlauf[-1] falls vorhanden)
        if kb_end_effective < 40 and len(recs) < 3:
            recs.append({
                'icon': 'trending-down',
                'observation': f'Kaufbereitschaft Ende: {kb_end_effective}/100',
                'explanation': 'Der Kunde ist am Ende ungewöhnlich skeptisch. Übe Qualifizierungs-Fragen, um früh Vertrauen aufzubauen.',
                'training_focus': 'kb:drop',
                'training_url': '/training',
                'cross_context': None,
            })

        # Regel 3: Redeanteil zu hoch / zu niedrig (Optimum ~40%)
        # Fix D (07.1 UAT-R1): OBS-02 — Cold Call has no speaker diarization,
        # berater_words bleibt 0 -> redeanteil_avg=0.0 triggert faelschlich 'rede aktiver'.
        # Redeanteil-Regel nur fuer Sessions mit echter Speaker-Trennung (meeting, training).
        rede = conv.redeanteil_avg
        _mode = getattr(conv, 'session_mode', None)
        _has_diarization = (_mode != 'cold_call')
        if rede is not None and _has_diarization and len(recs) < 3:
            if rede > 65:
                recs.append({
                    'icon': 'alert-circle',
                    'observation': f'Du redest {int(rede)}% — zu viel',
                    'explanation': 'Gute Berater reden ca. 40%. Übe aktives Zuhören und offene Fragen.',
                    'training_focus': 'redeanteil:too_high',
                    'training_url': '/training',
                    'cross_context': None,
                })
            elif rede < 25:
                recs.append({
                    'icon': 'alert-circle',
                    'observation': f'Du redest nur {int(rede)}% — zu wenig',
                    'explanation': 'Führe das Gespräch aktiver. Stelle gezielte Fragen und setze Impulse.',
                    'training_focus': 'redeanteil:too_low',
                    'training_url': '/training',
                    'cross_context': None,
                })

        # Regel 4: Skript-Abdeckung < 40%
        if (conv.skript_abdeckung or 0) < 40 and len(recs) < 3:
            recs.append({
                'icon': 'alert-circle',
                'observation': f'Skript nur zu {int(conv.skript_abdeckung or 0)}% abgedeckt',
                'explanation': 'Die wichtigen Bausteine deines Skripts sind nicht gefallen. Übe den Opener.',
                'training_focus': 'skript:opener',
                'training_url': '/training',
                'cross_context': None,
            })

    # UAT-R2 B1: Dedupe by explanation — same generic Live-Rule 1 text wurde bis zu
    # 3x ausgegeben, wenn 3 Einwaende unbehandelt waren. Wir behalten den ersten
    # Eintrag pro explanation-String (Order-preserving), damit Sektion 14
    # keine sichtbaren Doubletten mehr zeigt. observation bleibt einwand-spezifisch
    # im ersten Eintrag erhalten.
    _seen = set()
    _deduped = []
    for r in recs:
        _key = r.get('explanation')
        if _key in _seen:
            continue
        _seen.add(_key)
        _deduped.append(r)
    return _deduped[:3]


@app_routes_bp.route('/api/postcall/trend')
@login_required
def api_postcall_trend():
    """POLISH-22: Durchschnitts-Score der letzten N Calls desselben Users als Trend-Baseline
    fuer den PiP-Quick-Scoring-Screen ('+5% vs Schnitt letzte 5').

    Query-Param: n (optional, default 5, max 20)
    Response: {'ok': True, 'avg_score': <0-100 | null>, 'sample_size': <int>, 'n_requested': <int>}
    """
    from database.models import ConversationLog
    try:
        n = int(request.args.get('n', 5))
    except (TypeError, ValueError):
        n = 5
    n = max(1, min(20, n))

    db = get_session()
    try:
        recent = (
            db.query(ConversationLog)
              .filter(ConversationLog.user_id == g.user.id)
              .filter(ConversationLog.typ == 'live')
              .order_by(ConversationLog.created_at.desc())
              .limit(n)
              .all()
        )
        if not recent:
            return jsonify({'ok': True, 'avg_score': None, 'sample_size': 0, 'n_requested': n})
        scores = [_calc_call_score(c) for c in recent]
        avg = round(sum(scores) / len(scores))
        return jsonify({'ok': True, 'avg_score': avg, 'sample_size': len(scores), 'n_requested': n})
    finally:
        db.close()


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
        import json as _json
        try:
            daten = _json.loads(p.daten) if p.daten else {}
        except Exception:
            daten = {}
        # D-05: DB ist Single Source of Truth — kein ls.set_active_profile() mehr
        u = db.get(UserModel, g.user.id)
        if u:
            u.active_profile_id = p.id
            db.commit()
        # load_learning_cards(sid, user_id) requires a WebSocket SID — not available in
        # this HTTP route. handle_start_live_session already calls load_learning_cards
        # with the correct SID at session start. Removing this call is safe (Option B).
        flask_session['active_profile_id'] = p.id  # convenience only — not authoritative (D-05)
        return jsonify({'ok': True, 'name': p.name, 'phasen': daten.get('phasen', [])})
    finally:
        db.close()


@app_routes_bp.route('/api/launcher/init')
@login_required
def api_launcher_init():
    """Return profiles + settings for pip-launcher.js (called from any page)."""
    db = get_session()
    try:
        from database.models import Profile, User as _UModel
        profiles_raw = db.query(Profile).filter_by(org_id=g.org.id).order_by(Profile.name).all()
        profiles = [{'id': p.id, 'name': p.name} for p in profiles_raw]
        u = db.get(_UModel, g.user.id)
        active_profile_id = u.active_profile_id if u else None
        # Get active profile data for EWB buttons + opener
        active_profile_daten = {}
        if active_profile_id:
            ap = db.query(Profile).filter_by(id=active_profile_id, org_id=g.org.id).first()
            if ap and ap.daten:
                import json
                try:
                    active_profile_daten = json.loads(ap.daten) if isinstance(ap.daten, str) else ap.daten
                except Exception:
                    active_profile_daten = {}
        from services.precall_service import ist_verfuegbar
        precall_verfuegbar = ist_verfuegbar()
        # Skripte + Opener des aktiven Profils laden
        from database.models import ProfileSkript, ProfileOpener
        skripte = []
        opener_items = []
        if active_profile_id:
            skripte = [{'id': s.id, 'name': s.name, 'inhalt': s.inhalt or ''}
                       for s in db.query(ProfileSkript).filter_by(profile_id=active_profile_id)
                       .order_by(ProfileSkript.sortierung, ProfileSkript.id).all()]
            opener_items = [
                {
                    'id': o.id,
                    'name': o.name,
                    'inhalt': o.inhalt or '',
                    'is_personalized': bool(o.is_personalized),
                    'briefing_source_firma': o.briefing_source_firma or '',
                }
                for o in db.query(ProfileOpener).filter_by(profile_id=active_profile_id)
                .order_by(ProfileOpener.sortierung, ProfileOpener.id).all()
            ]
        return jsonify({
            'profiles': profiles,
            'active_profile_id': active_profile_id,
            'precall_verfuegbar': precall_verfuegbar,
            'profile_daten': active_profile_daten,
            'skripte': skripte,
            'opener': opener_items
        })
    finally:
        db.close()


@app_routes_bp.route('/api/launcher/profile/<int:pid>')
@login_required
def api_launcher_profile(pid):
    """Return profile daten for pip-launcher when profile changes."""
    db = get_session()
    try:
        from database.models import Profile
        p = db.query(Profile).filter_by(id=pid, org_id=g.org.id).first()
        if not p:
            return jsonify({'error': 'Profil nicht gefunden'}), 404
        import json
        daten = {}
        if p.daten:
            try:
                daten = json.loads(p.daten) if isinstance(p.daten, str) else p.daten
            except Exception:
                pass
        from database.models import ProfileSkript, ProfileOpener
        skripte = [{'id': s.id, 'name': s.name, 'inhalt': s.inhalt or ''}
                   for s in db.query(ProfileSkript).filter_by(profile_id=pid)
                   .order_by(ProfileSkript.sortierung, ProfileSkript.id).all()]
        opener_items = [
            {
                'id': o.id,
                'name': o.name,
                'inhalt': o.inhalt or '',
                'is_personalized': bool(o.is_personalized),
                'briefing_source_firma': o.briefing_source_firma or '',
            }
            for o in db.query(ProfileOpener).filter_by(profile_id=pid)
            .order_by(ProfileOpener.sortierung, ProfileOpener.id).all()
        ]
        return jsonify({'id': p.id, 'name': p.name, 'daten': daten, 'skripte': skripte, 'opener': opener_items})
    finally:
        db.close()


@app_routes_bp.route('/api/session-rating', methods=['POST'])
@login_required
def api_session_rating():
    # HIGH-3 pre-check: no FE caller found for /api/feedback at Phase 08.19.5 execution
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

        # D-10: Rating-Diskrepanz als learning_event loggen
        try:
            from services.integration_engine import log_learning_event
            if latest:
                ki_score = latest.kb_end or 0
                user_rating_pct = (int(stars) or 0) * 20  # 1-5 Sterne -> 0-100 Skala
                discrepancy = user_rating_pct - ki_score
                log_learning_event(db, g.user.id, 'call_rated', 'rating', latest.id, {
                    'conv_id': latest.id, 'user_rating': int(stars),
                    'ki_score': ki_score, 'discrepancy': discrepancy,
                })
                db.commit()
        except Exception as _re:
            print(f"[Engine] Rating-Event Fehler: {_re}")

        return jsonify({'ok': True})
    finally:
        db.close()


@app_routes_bp.route('/api/precall/research', methods=['POST'])
@login_required
def api_precall_research():
    from services.precall_service import recherche_firma
    data = request.get_json(force=True)
    firmenname = (data.get('firmenname') or '').strip()
    if not firmenname or len(firmenname) < 3 or len(firmenname) > 200:
        return jsonify({'error': 'Firmenname ist Pflicht (3-200 Zeichen)'}), 400

    ansprechpartner = (data.get('ansprechpartner') or '').strip() or None
    branche = (data.get('branche') or '').strip() or None

    # Aktives Profil laden fuer kontextreicheres Briefing
    profil_daten = None
    apid = flask_session.get('active_profile_id')
    if apid:
        from database.db import get_session as get_db_session
        from database.models import Profile as ProfileModel
        import json as _json
        db_pf = get_db_session()
        try:
            pf = db_pf.get(ProfileModel, apid)
            if pf and pf.daten:
                try:
                    profil_daten = _json.loads(pf.daten) if isinstance(pf.daten, str) else pf.daten
                except Exception:
                    profil_daten = None
        finally:
            db_pf.close()

    sid = (data.get('sid') or '').strip() or None
    user_id = g.user.id if g.user else None
    profile_id = flask_session.get('active_profile_id')

    briefing, error = recherche_firma(
        firmenname, ansprechpartner, branche,
        profil_daten=profil_daten,
        user_id=user_id,
        profile_id=profile_id,
        sid=sid,
    )
    if error:
        # Distinguish client-caused validation errors from upstream failures
        if 'Pflicht' in error or 'Zeichen' in error or 'konfiguriert' in error:
            return jsonify({'error': error}), 400
        return jsonify({'error': error}), 502
    return jsonify({'briefing': briefing})


# ── Phase 08 D-04: POLISH-55 3-State EWB-Rating-API ────────────────────────
@app_routes_bp.route('/api/ewb/<int:event_id>/rate', methods=['POST'])
@login_required
def api_ewb_rate(event_id):
    """3-State-Rating: success in {True, False, None}. Ownership via ConversationLog.user_id.

    Phase 08 D-04: Kein Submit-Button — jeder Click speichert sofort.
    D-05 konsumiert dies: WHERE success IS NOT NULL fuer A/B-Auswertung.

    Phase 08 W-1: Strict type-check via isinstance(value, bool).
    Python-Equality akzeptiert sonst integer 1 als True und integer 0 als False
    (1 in (True, False, None) == True). isinstance(value, bool) schliesst
    numeric 1/0 explizit aus — kritisch fuer Daten-Integritaet.
    """
    from database.models import ObjectionEvent, ConversationLog
    _MISSING = object()
    data = request.get_json(silent=True) or {}
    value = data.get('success', _MISSING)
    if value is _MISSING:
        return jsonify({'error': 'missing_success_key',
                        'expected': [True, False, None]}), 400
    if not (isinstance(value, bool) or value is None):
        return jsonify({'error': 'invalid_success_value',
                        'expected': [True, False, None]}), 400
    db = get_session()
    try:
        ev = db.query(ObjectionEvent).filter_by(id=event_id).first()
        if not ev:
            return jsonify({'error': 'not_found'}), 404
        # Ownership check — event muss zu einem ConversationLog von g.user.id gehoeren
        conv = db.query(ConversationLog).filter_by(
            id=ev.conversation_log_id, user_id=g.user.id
        ).first()
        if not conv:
            return jsonify({'error': 'forbidden'}), 403
        ev.success = value
        db.commit()
        print(f"[POLISH-55] event_id={event_id} success={value} by user_id={g.user.id}")
        return jsonify({'ok': True, 'success': value})
    finally:
        db.close()


# ── Phase 08.20.3: KI-Skript-Personalisierung ─────────────────────────────

@app_routes_bp.route('/api/precall/personalize', methods=['POST'])
@login_required
def api_personalize_skript():
    """Endpoint 1: KI-Call only — returns personalized_text. No DB write.

    Cap-check is NOT done here (SPEC L4: cap check must happen AFTER KI call,
    i.e., in the /save endpoint only after user approves the result).

    Briefing data is passed from the frontend via request JSON body (key 'briefing'),
    sourced from state.precallBriefing in pip-launcher.js. This avoids reliance on
    Flask session key availability from Phase 08.20.2.
    """
    from services.precall_service import generate_personalized_skript
    from database.db import get_session as get_db_session

    data = request.get_json(force=True) or {}
    briefing_dict = data.get('briefing') or {}
    call_mode = (data.get('call_mode') or '').strip()  # 'meeting' | 'cold_call' | '' (backwards-compat)

    # ── call_mode-Routing ──
    # Primär: call_mode steuert den Pfad
    # Fallback (backwards-compat): call_mode leer → skript_id-Präsenz → meeting; sonst cold_call
    skript_id = None
    opener_id = None

    if call_mode == 'meeting':
        try:
            skript_id = int(data.get('skript_id'))
            if skript_id <= 0: raise ValueError
        except (TypeError, ValueError):
            return jsonify({'error': 'skript_id muss eine positive Ganzzahl sein'}), 400
    elif call_mode == 'cold_call':
        try:
            opener_id = int(data.get('opener_id'))
            if opener_id <= 0: raise ValueError
        except (TypeError, ValueError):
            return jsonify({'error': 'opener_id muss eine positive Ganzzahl sein'}), 400
    else:
        # Kein call_mode — Fallback: skript_id hat Vorrang, dann opener_id
        if data.get('skript_id') is not None:
            try:
                skript_id = int(data.get('skript_id'))
                if skript_id <= 0: raise ValueError
            except (TypeError, ValueError):
                return jsonify({'error': 'skript_id muss eine positive Ganzzahl sein'}), 400
        elif data.get('opener_id') is not None:
            try:
                opener_id = int(data.get('opener_id'))
                if opener_id <= 0: raise ValueError
            except (TypeError, ValueError):
                return jsonify({'error': 'opener_id muss eine positive Ganzzahl sein'}), 400
        else:
            return jsonify({'error': 'skript_id oder opener_id erforderlich'}), 400

    user_id = g.user.id if g.user else None
    profile_id = flask_session.get('active_profile_id')
    if not profile_id:
        return jsonify({'error': 'Kein aktives Profil'}), 400

    _db = get_db_session()
    try:
        # Org-Isolation-Check via Profile
        from database.models import Profile
        profile = _db.query(Profile).filter_by(id=profile_id).first()
        if not profile or profile.org_id != g.org.id:
            return jsonify({'error': 'Profil nicht gefunden oder kein Zugriff'}), 403

        profil_daten = {}
        if profile.daten:
            try:
                import json as _json
                profil_daten = _json.loads(profile.daten) if isinstance(profile.daten, str) else (profile.daten or {})
            except Exception:
                profil_daten = {}

        # ── Modus-abhängiges Item-Loading ──
        if skript_id:
            from database.models import ProfileSkript
            item = _db.query(ProfileSkript).filter_by(
                id=skript_id, profile_id=profile_id
            ).first()
            if not item:
                return jsonify({'error': 'Skript nicht gefunden'}), 400
        else:
            from database.models import ProfileOpener
            item = _db.query(ProfileOpener).filter_by(
                id=opener_id, profile_id=profile_id
            ).first()
            if not item:
                return jsonify({'error': 'Opener nicht gefunden'}), 400

        opener_inhalt = item.inhalt or ''  # Parameter-Name bleibt (generate_personalized_skript Signatur)
    finally:
        _db.close()

    personalized_text, error = generate_personalized_skript(
        briefing_dict=briefing_dict,
        opener_inhalt=opener_inhalt,   # Wert: skript.inhalt (meeting) ODER opener.inhalt (cold_call)
        profil_daten=profil_daten,
        user_id=user_id,
    )
    if error:
        return jsonify({'error': error}), 502

    return jsonify({'personalized_text': personalized_text})


@app_routes_bp.route('/api/precall/personalize/save', methods=['POST'])
@login_required
def api_personalize_skript_save():
    """Endpoint 2: DB write with Cap-Check. Atomic delete+insert transaction (Finding B).

    Returns {'item_id': int, 'ok': True} on success.
    Returns {'cap_exceeded': True, 'items': [...]} when cap is hit (no delete_ids given).
    Accepts optional 'delete_ids' list to free cap slots before saving.

    IMPORTANT (Finding B): All deletes + the INSERT are wrapped in a single
    `with _db.begin():` transaction. If INSERT fails after DELETE, ALL changes
    are rolled back. No partial state, no data loss.

    IMPORTANT (Finding A): briefing_source_firma is stored on the new ProfileOpener,
    sourced from request body 'firmenname'. This enables the Step-5 optgroup grouping
    in pip-launcher.js (Plan 01).
    """
    from database.db import get_session as get_db_session
    from database.models import ProfileOpener, Profile
    from config import PERSONALIZED_SCRIPTS_CAP
    import datetime

    data = request.get_json(force=True) or {}
    personalized_text = (data.get('personalized_text') or '').strip()
    delete_ids = data.get('delete_ids') or []
    # firmenname from request body (sent by _savePersonalizedAndStartCall in Plan 1)
    firmenname = (data.get('firmenname') or '').strip()[:50]

    # WR-03: validate opener_id as positive integer before any DB query
    try:
        opener_id = int(data.get('opener_id'))
        if opener_id <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({'error': 'opener_id muss eine positive Ganzzahl sein'}), 400
    if not personalized_text:
        return jsonify({'error': 'personalized_text ist Pflicht'}), 400

    user_id = g.user.id if g.user else None
    profile_id = flask_session.get('active_profile_id')
    if not profile_id:
        return jsonify({'error': 'Kein aktives Profil'}), 400

    cap = max(1, int(PERSONALIZED_SCRIPTS_CAP))  # guard: cap >= 1 (T-08203-03-04)

    _db = get_db_session()
    try:
        # Org-isolation check: verify active profile belongs to current org (CR-01)
        _prof_check = _db.query(Profile).filter_by(id=profile_id, org_id=g.org.id).first()
        if not _prof_check:
            return jsonify({'error': 'Zugriff verweigert'}), 403

        # Verify original opener belongs to this profile
        original = _db.query(ProfileOpener).filter_by(
            id=opener_id, profile_id=profile_id
        ).first()
        if not original:
            return jsonify({'error': 'Opener nicht gefunden'}), 400

        # ── Cap-Check + Delete + Insert (WR-02) ──────────────────────────
        # with_for_update() acquires row-level lock on Postgres; no-op on SQLite.
        # Prevents race: two concurrent requests both read count < cap and both insert.
        # NOTE: No 'with _db.begin()' wrapper here — SQLAlchemy already started an
        # implicit transaction at the first query above (lines ~1155/1160). Calling
        # _db.begin() again raises InvalidRequestError. We use explicit commit/rollback.
        today_str = datetime.datetime.utcnow().strftime('%Y-%m-%d')
        firma_display = firmenname or (original.name or 'Lead')[:50]
        new_name = f"{firma_display} — {original.name} (personalisiert, {today_str})"

        cap_exceeded_response = None  # set if cap is hit
        new_item_id = None
        try:
            # Cap-Check
            if not delete_ids:
                personalized_count = _db.query(ProfileOpener).filter_by(
                    profile_id=profile_id, is_personalized=True
                ).with_for_update().count()

                if personalized_count >= cap:
                    # Cap exceeded — collect items list for sub-modal (SPEC Req 9)
                    items_query = _db.query(ProfileOpener).filter_by(
                        profile_id=profile_id, is_personalized=True
                    ).order_by(ProfileOpener.created_at.asc()).all()

                    now = datetime.datetime.utcnow()
                    items_list = []
                    for item in items_query:
                        weeks_old = 0
                        if item.created_at:
                            delta = now - item.created_at
                            weeks_old = int(delta.days / 7)
                        items_list.append({
                            'id': item.id,
                            'name': item.name or '',
                            'created_at': str(item.created_at) if item.created_at else '',
                            'firmenname': (item.name or '')[:20],
                            'weeks_old': weeks_old,
                        })
                    cap_exceeded_response = items_list
                    # Exit without insert
                    raise _CapExceeded()

            # Delete-Phase (Cap-Befreiung) — only items belonging to this profile
            for item_id in delete_ids:
                item = _db.query(ProfileOpener).filter_by(
                    id=item_id,
                    profile_id=profile_id,
                    is_personalized=True  # Schutz: nur personalisierte koennen via Cap-Modal geloescht werden
                ).first()
                if not item:
                    raise ValueError(f"Item {item_id} not found or not personalized")

                # DSGVO-Audit-Log (SPEC Req 10) — before delete so we have the data
                firmenname_hint = (item.name or '')[:20]
                print(
                    f"[DSGVO-Audit] User-Aktion: personalisiertes Skript gelöscht zur Cap-Befreiung "
                    f"(item_id={item.id}, firmenname={firmenname_hint}, erstellt={item.created_at})"
                )
                _db.delete(item)

            # Insert-Phase (neues personalisiertes Skript — SPEC Req 8)
            new_opener = ProfileOpener(
                profile_id=profile_id,
                name=new_name,
                inhalt=personalized_text,
                sortierung=0,
                type=original.type,
                parent_id=opener_id,               # parent_id links to original (SPEC Req 8, 11)
                is_personalized=True,              # marks as personalized (SPEC Req 8)
                briefing_source_firma=firmenname,  # Finding A: enables optgroup grouping in Plan 01
            )
            _db.add(new_opener)
            _db.flush()   # trigger ID generation without committing yet
            new_item_id = new_opener.id
            _db.commit()  # explicit commit (Bug A fix: no with _db.begin() wrapper)

        except _CapExceeded:
            pass  # cap_exceeded_response already set; no error, just skip insert
        except Exception as e:
            _db.rollback()
            raise

    finally:
        _db.close()

    if cap_exceeded_response is not None:
        return jsonify({'cap_exceeded': True, 'items': cap_exceeded_response})

    return jsonify({'item_id': new_item_id, 'ok': True})
