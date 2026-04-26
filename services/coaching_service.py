"""Coach-Modul: Post-Call Analyse (Sonnet) + Lernkarten Helpers."""
import json
import threading
from datetime import datetime, timezone
import config
from services.claude_service import claude_client

_analysis_lock = threading.Lock()

POSTCALL_PROMPT = """Du bist ein erfahrener Sales-Coach. Analysiere dieses Verkaufsgespraech und schlage exakt 3 Lernkarten vor.

Gespraechsdaten:
- Einwaende: {einwaende}
- Kaufsignale: {kaufsignale}
- Painpoints: {painpoints}
- Kaufbereitschaft: Start {kb_start}% -> Ende {kb_end}%
- Redeanteil Berater: {redeanteil_berater}% / Kunde: {redeanteil_kunde}%
- Dauer: {dauer_sek} Sekunden
- Skript-Abdeckung: {skript_abdeckung}%
- Gegenargument-Details: {ga_details}

Priorisierung (per D-03):
1. Fehler der den Abschluss direkt verhindert hat
2. Haeufigster Fehler im Call
3. Kleinste Verbesserung mit groesster Wirkung

WICHTIG: Jeder Vorschlag MUSS ein konkreter Satz sein, den der Vertriebler beim naechsten Call woertlich sagen kann. KEINE generischen Tipps wie "Vertiefen Sie Einwaende".

Beispiel guter Vorschlag:
"Wenn der Kunde sagt 'Das ist zu teuer' - antworte mit: 'Im Vergleich wozu meinen Sie das?' und schweig dann."

Antworte als JSON mit exakt diesem Format:
{{
  "vorschlaege": [
    {{
      "category": "einwand_preis",
      "original_suggestion": "Wenn der Kunde sagt...",
      "alternative_1": "Alternative Formulierung 1...",
      "alternative_2": "Alternative Formulierung 2...",
      "lernziel": "Einwaende vertiefen statt direkt kontern"
    }},
    ...
  ]
}}

Genau 3 Vorschlaege. Jeder mit 2 Alternativen (fuer "Neuer Vorschlag" per D-06, pre-generated to avoid extra Sonnet calls). Categories aus: einwand_preis, einwand_zeit, einwand_wettbewerb, einwand_bedarf, einwand_entscheider, zu_frueh_pitch, redeanteil, kaufsignal_verpasst, abschluss_timing, phasen_sprung."""


def generate_postcall_analysis(conv_id, user_id, einwaende, painpoints,
                                kb_start, kb_end, redeanteil_berater,
                                redeanteil_kunde, dauer_sek,
                                skript_abdeckung, ga_details,
                                kaufsignale=None, profile_data=None):
    """Generate max 3 learning card suggestions via Sonnet (D-01, D-02).

    T-04.11-05: Guard against duplicate analysis — check if suggestions
    already exist for this conv_id before calling Sonnet.
    """
    with _analysis_lock:
        # T-04.11-05: Duplicate guard — one analysis per conversation
        from database.db import get_session
        from database.models import LearningCard
        db_check = get_session()
        try:
            existing = db_check.query(LearningCard).filter_by(call_id=conv_id).count()
            if existing > 0:
                print(f"[Coach] Suggestions already exist for conv_id={conv_id}, skipping Sonnet call")
                return []
        finally:
            db_check.close()

        prompt_text = POSTCALL_PROMPT.format(
            einwaende=json.dumps(einwaende, ensure_ascii=False)[:2000],
            kaufsignale=json.dumps(kaufsignale or [], ensure_ascii=False)[:1000],
            painpoints=json.dumps(painpoints, ensure_ascii=False)[:1000],
            kb_start=kb_start, kb_end=kb_end,
            redeanteil_berater=redeanteil_berater,
            redeanteil_kunde=redeanteil_kunde,
            dauer_sek=dauer_sek,
            skript_abdeckung=skript_abdeckung,
            ga_details=json.dumps(ga_details, ensure_ascii=False)[:2000],
        )
        try:
            response = claude_client.messages.create(
                model=config.MODEL_POSTCALL_ANALYSIS,
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt_text}]
            )
            # Cost tracking (D-02: Sonnet)
            try:
                from services.cost_tracker import log_api_cost
                u = getattr(response, 'usage', None)
                if u:
                    log_api_cost('anthropic', 'sonnet-4-5', user_id=user_id,
                                 units=(getattr(u, 'input_tokens', 0) or 0)/1000.0,
                                 unit_type='per_1k_input_tokens',
                                 context_tag='postcall_coach')
                    log_api_cost('anthropic', 'sonnet-4-5', user_id=user_id,
                                 units=(getattr(u, 'output_tokens', 0) or 0)/1000.0,
                                 unit_type='per_1k_output_tokens',
                                 context_tag='postcall_coach')
            except Exception as _ce:
                print(f"[CostHook] postcall_coach skipped: {_ce}")

            text = response.content[0].text.strip()
            start = text.find('{')
            end = text.rfind('}') + 1
            if start < 0 or end <= start:
                print(f"[Coach] No JSON found in Sonnet response")
                return []
            result = json.loads(text[start:end])
            vorschlaege = result.get('vorschlaege', [])[:3]

            # Persist suggestions linked to conv_id
            db = get_session()
            try:
                for v in vorschlaege:
                    card = LearningCard(
                        user_id=user_id,
                        call_id=conv_id,
                        category=v.get('category', 'allgemein'),
                        original_suggestion=v.get('original_suggestion', ''),
                        final_text=v.get('original_suggestion', ''),
                        lernziel=v.get('lernziel', ''),
                        source='ki',
                        status='vorschlag',  # not yet 'aktiv' — user must confirm
                    )
                    db.add(card)
                db.commit()
            except Exception as _de:
                print(f"[Coach] DB persist failed: {_de}")
                db.rollback()
                return []  # Return empty so frontend knows analysis failed
            finally:
                db.close()

            return vorschlaege
        except Exception as e:
            print(f"[Coach] Sonnet analysis failed: {e}")
            return []


def validate_user_text(user_text, lernziel):
    """D-06: KI prueft ob user-eingegebener Satz das Lernziel abdeckt (Haiku)."""
    try:
        response = claude_client.messages.create(
            model=config.MODEL_VALIDATE_USER_TEXT,
            max_tokens=200,
            messages=[{"role": "user", "content": f"""Lernziel: {lernziel}
User-Satz: {user_text}

Deckt der Satz das Lernziel ab? Antworte als JSON:
{{"covers_goal": true/false, "feedback": "Kurzes Feedback auf Deutsch"}}"""}]
        )
        text = response.content[0].text.strip()
        start = text.find('{'); end = text.rfind('}') + 1
        return json.loads(text[start:end])
    except Exception as e:
        print(f"[Coach] Validation failed: {e}")
        return {"covers_goal": False, "feedback": "Validierung fehlgeschlagen, bitte erneut versuchen."}


def get_active_cards(user_id):
    """Load user's active learning cards."""
    from database.db import get_session
    from database.models import LearningCard
    db = get_session()
    try:
        cards = db.query(LearningCard).filter_by(
            user_id=user_id, status='aktiv'
        ).order_by(LearningCard.created_at.desc()).all()
        return [{'id': c.id, 'category': c.category,
                 'final_text': c.final_text, 'lernziel': c.lernziel,
                 'applied_count': c.applied_count,
                 'created_at': c.created_at.isoformat() if c.created_at else None}
                for c in cards]
    finally:
        db.close()


def get_or_generate_weekly_report(user_id):
    """D-12: On-demand weekly coach report with DB caching. Only generates if >= 1 call this week."""
    from datetime import date, timedelta
    from database.db import get_session
    from database.models import CoachingReport, ConversationLog

    today = date.today()
    week_start = today - timedelta(days=today.weekday())  # Monday
    week_end = week_start + timedelta(days=6)

    db = get_session()
    try:
        # Check cache
        existing = db.query(CoachingReport).filter_by(user_id=user_id).filter(
            CoachingReport.period_start == week_start
        ).first()
        if existing:
            return {
                'calls_count': existing.calls_count,
                'avg_readiness_score': existing.avg_readiness_score,
                'strongest_phase': existing.strongest_phase,
                'weakest_phase': existing.weakest_phase,
                'talk_ratio_user': existing.talk_ratio_user,
                'talk_ratio_customer': existing.talk_ratio_customer,
                'report_text': existing.report_text,
                'suggested_card': json.loads(existing.suggested_card_json) if existing.suggested_card_json else None,
                'period_start': week_start.isoformat(),
                'period_end': week_end.isoformat(),
            }

        # D-12/Pitfall 4: Only generate if user had >= 1 call this week
        from datetime import datetime as _dt
        week_start_dt = _dt.combine(week_start, _dt.min.time())
        week_end_dt = _dt.combine(week_end, _dt.max.time())
        calls = db.query(ConversationLog).filter(
            ConversationLog.user_id == user_id,
            ConversationLog.typ == 'live',
            ConversationLog.started_at >= week_start_dt,
            ConversationLog.started_at <= week_end_dt,
        ).all()

        # D-08: Training-Sessions dieser Woche einbeziehen
        training_sessions = db.query(ConversationLog).filter(
            ConversationLog.user_id == user_id,
            ConversationLog.typ == 'training',
            ConversationLog.started_at >= week_start_dt,
            ConversationLog.started_at <= week_end_dt,
        ).all()

        if not calls and not training_sessions:
            return None  # No calls or trainings this week

        # Aggregate data for report (D-13) — safe for 0 calls
        calls_count = len(calls)
        avg_kb = sum(c.kb_end or 30 for c in calls) / calls_count if calls_count else 0
        avg_talk = sum(c.redeanteil_avg or 50 for c in calls) / calls_count if calls_count else 50
        avg_talk_kunde = 100 - avg_talk

        # Phase analysis: find strongest/weakest from phasen_details
        phase_scores = {}
        for c in calls:
            if c.phasen_details:
                try:
                    phases = json.loads(c.phasen_details)
                    for ph in phases:
                        name = ph.get('name', '?')
                        if name not in phase_scores:
                            phase_scores[name] = []
                        phase_scores[name].append(ph.get('dauer_sek', 0))
                except Exception:
                    pass
        strongest = max(phase_scores, key=lambda k: sum(phase_scores[k])) if phase_scores else None
        weakest = min(phase_scores, key=lambda k: sum(phase_scores[k])) if phase_scores else None

        # D-08: Training-Aggregation fuer Cross-Modul Insight
        training_count = len(training_sessions)
        training_avg_score = (
            sum(t.kb_end or 0 for t in training_sessions) / training_count
            if training_count else 0
        )
        # Einwand-Typen aus Training extrahieren
        training_einwand_types = set()
        for t in training_sessions:
            if t.gegenargument_details:
                try:
                    for ga in json.loads(t.gegenargument_details):
                        et = ga.get('einwand_typ', '')
                        if et:
                            training_einwand_types.add(et)
                except Exception:
                    pass
        # Live-Call Einwand-Typen extrahieren
        call_einwand_types = set()
        for c in calls:
            if c.gegenargument_details:
                try:
                    for ga in json.loads(c.gegenargument_details):
                        et = ga.get('einwand_typ', '')
                        if et:
                            call_einwand_types.add(et)
                except Exception:
                    pass
        # Cross-Modul Insight: Einwaende die in beiden vorkommen
        cross_einwaende = training_einwand_types & call_einwand_types

        # Training-Kontext zum Prompt hinzufuegen
        training_context = ""
        if training_count > 0:
            training_context = f"""
Trainingsdaten:
- {training_count} Trainings-Sessions absolviert
- Durchschnittlicher Training-Score: {training_avg_score:.0f}%
- Trainierte Einwand-Typen: {', '.join(training_einwand_types) if training_einwand_types else 'keine'}
"""
            if cross_einwaende:
                training_context += f"- Cross-Modul: Einwaende die sowohl im Training als auch im echten Call vorkamen: {', '.join(cross_einwaende)}\n"

        # Generate report text via Sonnet (D-14)
        report_prompt = f"""Du bist ein Sales-Coach. Erstelle einen kurzen woechentlichen Coach-Report auf Deutsch.

Wochendaten:
- {calls_count} Calls gefuehrt
- Durchschnittlicher Kaufbereitschafts-Score: {avg_kb:.0f}%
- Redeanteil Berater: {avg_talk:.0f}% / Kunde: {avg_talk_kunde:.0f}%
- Staerkste Phase: {strongest or 'unbekannt'}
- Schwaechste Phase: {weakest or 'unbekannt'}
{training_context}
Schreibe:
1. Eine kurze Zusammenfassung (2-3 Saetze)
2. Ein erkanntes Muster (1-2 Saetze, narrativ, nicht als Liste)
3. Einen konkreten Lernkarten-Vorschlag (ein Satz den der Vertriebler sagen kann)

Antworte als JSON:
{{"report_text": "...", "muster": "...", "suggested_card": {{"category": "...", "text": "...", "lernziel": "..."}}}}"""

        try:
            response = claude_client.messages.create(
                model=config.MODEL_WEEKLY_SUMMARY,
                max_tokens=800,
                messages=[{"role": "user", "content": report_prompt}]
            )
            # Cost tracking
            try:
                from services.cost_tracker import log_api_cost
                u = getattr(response, 'usage', None)
                if u:
                    log_api_cost('anthropic', 'sonnet-4-5', user_id=user_id,
                                 units=(getattr(u, 'input_tokens', 0) or 0)/1000.0,
                                 unit_type='per_1k_input_tokens',
                                 context_tag='weekly_coach_report')
                    log_api_cost('anthropic', 'sonnet-4-5', user_id=user_id,
                                 units=(getattr(u, 'output_tokens', 0) or 0)/1000.0,
                                 unit_type='per_1k_output_tokens',
                                 context_tag='weekly_coach_report')
            except Exception as _ce:
                print(f"[CostHook] weekly_coach_report skipped: {_ce}")

            text = response.content[0].text.strip()
            start = text.find('{'); end = text.rfind('}') + 1
            report_data = json.loads(text[start:end])
            full_report = report_data.get('report_text', '') + '\n\nDein Muster:\n' + report_data.get('muster', '')
            suggested = report_data.get('suggested_card')
        except Exception as e:
            print(f"[Coach] Weekly report Sonnet failed: {e}")
            full_report = f"Diese Woche: {calls_count} Calls, Ø Score {avg_kb:.0f}%."
            suggested = None

        # Cache in DB (D-12)
        report = CoachingReport(
            user_id=user_id,
            period_start=week_start,
            period_end=week_end,
            calls_count=calls_count,
            avg_readiness_score=round(avg_kb, 1),
            strongest_phase=strongest,
            weakest_phase=weakest,
            talk_ratio_user=round(avg_talk, 1),
            talk_ratio_customer=round(avg_talk_kunde, 1),
            report_text=full_report,
            suggested_card_json=json.dumps(suggested, ensure_ascii=False) if suggested else None,
        )
        db.add(report)
        db.commit()

        return {
            'calls_count': calls_count,
            'avg_readiness_score': round(avg_kb, 1),
            'strongest_phase': strongest,
            'weakest_phase': weakest,
            'talk_ratio_user': round(avg_talk, 1),
            'talk_ratio_customer': round(avg_talk_kunde, 1),
            'report_text': full_report,
            'suggested_card': suggested,
            'period_start': week_start.isoformat(),
            'period_end': week_end.isoformat(),
        }
    except Exception as e:
        print(f"[Coach] Weekly report generation failed: {e}")
        return None
    finally:
        db.close()


def get_longterm_data(user_id, weeks=12):
    """D-15/D-16: Aggregate ConversationLog data over past N weeks for Chart.js."""
    from datetime import date, timedelta
    from database.db import get_session
    from database.models import ConversationLog

    today = date.today()
    start_date = today - timedelta(weeks=weeks)

    db = get_session()
    try:
        from datetime import datetime as _dt
        start_dt = _dt.combine(start_date, _dt.min.time())
        calls = db.query(ConversationLog).filter(
            ConversationLog.user_id == user_id,
            ConversationLog.typ == 'live',
            ConversationLog.started_at >= start_dt,
        ).order_by(ConversationLog.started_at).all()

        # Group by ISO week
        weekly = {}
        for c in calls:
            if not c.started_at:
                continue
            iso = c.started_at.isocalendar()
            week_key = f"{iso[0]}-W{iso[1]:02d}"
            if week_key not in weekly:
                weekly[week_key] = {'kb_scores': [], 'talk_ratios': [], 'einwaende_total': 0, 'einwaende_ok': 0, 'calls': 0}
            w = weekly[week_key]
            w['calls'] += 1
            w['kb_scores'].append(c.kb_end or 30)
            w['talk_ratios'].append(c.redeanteil_avg or 50)
            w['einwaende_total'] += c.einwaende_gesamt or 0
            w['einwaende_ok'] += c.einwaende_behandelt or 0

        # Build chart data arrays
        labels = sorted(weekly.keys())
        kb_data = [round(sum(weekly[k]['kb_scores'])/len(weekly[k]['kb_scores']), 1) if weekly[k]['kb_scores'] else 0 for k in labels]
        talk_data = [round(sum(weekly[k]['talk_ratios'])/len(weekly[k]['talk_ratios']), 1) if weekly[k]['talk_ratios'] else 50 for k in labels]
        ewb_rate = [round(weekly[k]['einwaende_ok']/weekly[k]['einwaende_total']*100, 1) if weekly[k]['einwaende_total'] > 0 else 0 for k in labels]
        calls_per_week = [weekly[k]['calls'] for k in labels]

        return {
            'labels': labels,
            'kaufbereitschaft': kb_data,
            'redeanteil': talk_data,
            'einwand_erfolgsrate': ewb_rate,
            'calls_per_week': calls_per_week,
        }
    finally:
        db.close()
