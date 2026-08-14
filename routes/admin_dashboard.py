"""Phase 04.7.2 — Founder Cost Dashboard Blueprint.

Alle Routes gated mit @login_required + @superadmin_required.
6 Tabs: uebersicht, einnahmen, ausgaben, kunden, eur, export.
"""
from __future__ import annotations
import re
import calendar
from datetime import date, datetime, timedelta
from flask import Blueprint, render_template, request, jsonify, abort
from routes.auth import login_required
from services.auth_decorators import superadmin_required
from database.db import get_session

admin_dashboard_bp = Blueprint(
    'admin_dashboard', __name__,
    url_prefix='/admin/dashboard',
    template_folder='../templates/admin',
)

VALID_TABS = {'uebersicht', 'einnahmen', 'ausgaben', 'kunden', 'eur', 'export'}
PERIOD_RE = re.compile(r'^\d{4}-\d{2}$')

# METRIK-1 D-23 — Schwellen der Zitat-Pruefung (Vier-Saeulen-Punkt 3: Eingreifen in einer Zeile).
# KEIN Soll-0-Wert: Verwuerfe sind der GEWOLLTE Schutz. Auffaellig ist die MENGE und der ANTEIL.
BELEG_ALARM_VERWORFEN_HEUTE = 10   # ab so vielen verworfenen Beobachtungen am Tag: Alarm
# Der Beinahe-Treffer geht bewusst MIT in die Anteils-Schwelle ein: ein steigender
# Beinahe-Treffer-Anteil ist das FRUEHESTE Zeichen, dass Bewerter-Text und Pruef-Text
# auseinanderdriften — genau das, wogegen D-05 schuetzt. An "verworfen" allein sieht man das nicht.
BELEG_ALARM_ANTEIL = 0.30          # oder: (verworfen + near_miss) / geprueft ueber diesem Anteil
BELEG_ALARM_MIN_GEPRUEFT = 20      # ... aber erst ab dieser Stichprobe, sonst alarmieren 2 von 3


def _parse_period(period_str):
    """Parst 'YYYY-MM' in (start_date, end_date_exclusive).
    Fallback: aktueller Monat. Bei ungueltigem Format: abort(400)."""
    if period_str and not PERIOD_RE.match(period_str):
        abort(400, description="Invalid period format, expected YYYY-MM")
    if not period_str:
        today = date.today()
        period_str = f"{today.year}-{today.month:02d}"
    year, month = map(int, period_str.split('-'))
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)
    return start, end


# ── Phase 08.23.2.KOSTEN-1 ───────────────────────────────────────────────────────────
# Ab diesem Tag ist die Kosten-Erfassung vollstaendig: Live-STT (nova-3) wird gebucht, die
# Haiku-Preise stehen auf den echten 4.5-Werten, und die acht vorher ungehookten Call-Sites
# loggen. ALLES DAVOR ist unvollstaendig — vor allem fehlt die minuten-getriebene
# Hauptkostenposition, und Haiku war 4x zu niedrig bepreist. Die Marge aelterer Zeitraeume
# sieht deshalb BESSER aus als sie war.
# ★ D-02 (Finanzamt-Linie): alte api_cost_log-Zeilen werden NICHT rueckwirkend korrigiert.
#   Die Vergangenheit wird MARKIERT, nicht umgeschrieben. Kein Backfill, keine Schaetzung.
COST_DATA_COMPLETE_SINCE = date(2026, 7, 20)

from services.cost_tracker import LIVE_LLM_CONTEXT_TAGS, CACHE_CONTEXT_TAGS, STREAM_CONTEXT_TAGS

# ── Phase 08.23.2.MESSGERAETE-1 — Leser fuer die Live-KI-Messung ──────────────────────────
# ★ D-11: die Zuordnung "welcher context_tag ist Live-KI" kommt aus GENAU EINER Liste in
# services/cost_tracker.py. Hier wird sie NUR gelesen — keine zweite Liste, kein Duplikat.
# tests/test_live_latency_coverage.py::test_live_tag_liste_ist_synchron faellt rot, wenn die
# Liste von den Code-Funden abweicht.
#
# Perzentile werden in PYTHON gerechnet, nicht per percentile_cont in SQL. Grund (Punkt 27,
# einfachster tragfaehiger Weg): percentile_cont ist Postgres-Dialekt; die Tests laufen teils
# ohne Postgres, und eine Dialekt-Weiche im Leser waere mehr Mechanik als das Problem gross
# ist. Es werden nur ZWEI Integer-Spalten des gewaehlten Monats geladen (bei den heutigen
# Groessenordnungen — 152 Buchungen der teuersten Sorte in 21 Tagen — sind das dreistellige
# bis niedrig vierstellige Zahlen pro Monat).
_OHNE_HERKUNFT = '(ohne Herkunft)'


def _perzentil(werte_sortiert, q):
    """Nearest-Rank-Perzentil auf einer AUFSTEIGEND sortierten Liste. None bei leerer Liste.

    Bewusst Nearest-Rank (kein Interpolieren): das Ergebnis ist immer ein tatsaechlich
    gemessener Wert, keine Rechengroesse zwischen zwei Messungen. Bei zwei Dutzend Werten
    pro Sorte ist Interpolation ohnehin Scheingenauigkeit.
    """
    if not werte_sortiert:
        return None
    import math
    rang = max(1, math.ceil(q * len(werte_sortiert)))
    return int(werte_sortiert[rang - 1])


def _aggregiere_kosten_nach_tag(summen_rows, latenz_rows):
    """Teilt die Kosten in ZWEI Listen: (live_ki, uebrige_kosten).

    summen_rows: Iterable von (context_tag, anzahl_buchungen, summe_cost_eur) — ALLE Tags
    latenz_rows: Iterable von (context_tag, latency_ms, ttft_ms) — NUR Zeilen mit
                 latency_ms IS NOT NULL

    ★ D-07 (Doppelzaehlung): log_api_cost laeuft pro API-ANTWORT 2-4x (input, output, ggf.
    cache-read, cache-write). Die Dauer haengt deshalb NUR an der input-Token-Buchung
    (services/claude_service.py + services/qa_pipeline.py, MESSGERAETE-1 Plan 02). Dieser Leser
    filtert auf latency_ms IS NOT NULL und zaehlt damit jede API-Antwort GENAU EINMAL in
    Ø/p50/p95 — waehrend 'buchungen' bewusst weiterhin ALLE Zeilen zaehlt (das ist die
    Kosten-Sicht). Deshalb stehen 'buchungen' und 'antworten' als ZWEI Spalten nebeneinander;
    sie sind nicht dasselbe und duerfen nie zusammengefasst werden.

    ★ Punkt 12: Tabelle 2 bekommt bewusst KEINE Dauer-Felder. Ein neuer, unbekannter Tag faellt
    still dorthin — fuer Nicht-LLM-Kosten (stt, stripe_fee, training_*) ist das gewuenscht.
    Fuer einen neuen LIVE-Pfad waere es eine Luecke; die faengt der Waechter (Sync-Test), solange
    der Pfad in claude_service.py oder qa_pipeline.py steht. Steht er woanders: RESTLUECKE 3.

    ★ DSGVO/Mandanten: die Rueckgabe enthaelt ausschliesslich context_tag, Anzahlen, Kosten und
    Millisekunden. Kein user_id, kein org_id, kein session_id, kein Transkript. Eine nach
    context_tag gruppierte Aggregation ueber alle Mandanten ist damit personenbezugsfrei; eine
    Zeilen-Ansicht waere es nicht und wird deshalb NICHT gebaut.
    """
    roh = {}
    for tag, anzahl, summe in summen_rows:
        schluessel = tag or _OHNE_HERKUNFT
        e = roh.setdefault(schluessel, {'buchungen': 0, 'kosten_eur': 0.0, '_lat': [], '_ttft': []})
        e['buchungen'] += int(anzahl or 0)
        e['kosten_eur'] += float(summe or 0)
    for tag, lat, ttft in latenz_rows:
        schluessel = tag or _OHNE_HERKUNFT
        e = roh.setdefault(schluessel, {'buchungen': 0, 'kosten_eur': 0.0, '_lat': [], '_ttft': []})
        e['_lat'].append(int(lat))
        if ttft is not None:
            e['_ttft'].append(int(ttft))

    live_ki, uebrige_kosten = [], []
    for schluessel, e in roh.items():
        kosten = round(e['kosten_eur'], 4)
        if schluessel in LIVE_LLM_CONTEXT_TAGS:
            lat = sorted(e['_lat'])
            ttft = e['_ttft']
            live_ki.append({
                'context_tag': schluessel,
                'label': LIVE_LLM_CONTEXT_TAGS[schluessel],
                'nur_cache': schluessel in CACHE_CONTEXT_TAGS,
                # Die Dauer dieser Zeilen enthaelt zusaetzlich die Auslieferung an den Browser
                # (Begruendung an STREAM_CONTEXT_TAGS in services/cost_tracker.py). Die Anzeige
                # markiert sie sichtbar — ohne Markierung staenden hier zwei verschiedene
                # Groessen in derselben Spalte untereinander.
                'inkl_auslieferung': schluessel in STREAM_CONTEXT_TAGS,
                'buchungen': e['buchungen'],
                'kosten_eur': kosten,
                'antworten': len(lat),
                'latenz_avg_ms': int(sum(lat) / len(lat)) if lat else None,
                'latenz_p50_ms': _perzentil(lat, 0.5),
                'latenz_p95_ms': _perzentil(lat, 0.95),
                'ttft_avg_ms': int(sum(ttft) / len(ttft)) if ttft else None,
            })
        else:
            uebrige_kosten.append({
                'context_tag': schluessel,
                'label': schluessel,
                'buchungen': e['buchungen'],
                'kosten_eur': kosten,
            })
    live_ki.sort(key=lambda r: r['kosten_eur'], reverse=True)
    uebrige_kosten.sort(key=lambda r: r['kosten_eur'], reverse=True)
    return live_ki, uebrige_kosten


def _cost_skip_payload():
    """KOSTEN-1 W3 — Skip-Zaehler fuers Founder-Dashboard aufbereiten.

    Edge-Case 1 aus dem Plan: ein defekter Modellname in einer Schleife laesst die ANZAHL
    schnell wachsen. Die Anzahl verschiedener TRIPEL bleibt klein — trotzdem wird die Anzeige
    begrenzt, damit das Dashboard nie eine Endlosliste rendert.
    """
    try:
        from services.cost_tracker import get_skip_counts
        counts = get_skip_counts()
    except Exception:
        return {'total': 0, 'triples': []}
    top = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:10]
    return {
        'total': sum(counts.values()),
        'triples': [{'triple': k, 'count': v} for k, v in top],
    }


def _live_timeout_payload():
    """SOFORT-2 (D-04) — Zeitueberschreitungen der Live-LLM-Aufrufe. Soll-Wert: 0.

    Aufbau wortgleich zu _cost_skip_payload. Schluessel ist die aufrufende Funktion
    (analyse_loop / coaching_loop / classify_phase / infer_customer_state) — tenant-neutral,
    ohne Nutzerbezug (Punkt 28). Der Drei-in-Folge-Zaehler, der die PiP-Anzeige ausloest, liegt
    dagegen PER SID in _session_state und taucht hier bewusst NICHT auf.
    """
    try:
        from services.claude_service import get_live_timeout_counts
        counts = get_live_timeout_counts()
    except Exception:
        return {'total': 0, 'funktionen': []}
    top = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:10]
    return {
        'total': sum(counts.values()),
        'funktionen': [{'funktion': k, 'count': v} for k, v in top],
    }


def _beleg_check_payload():
    """METRIK-1 D-23 — Zaehler der Zitat-Pruefung fuers Founder-Dashboard aufbereiten.

    Aufbau wortgleich zu _cost_skip_payload. KEIN Soll-0-Wert: Verwuerfe sind der GEWOLLTE
    Schutz vor erfundenen Zitaten. Bewusste Grenze (wie dort): RAM DIESES Prozesses, seit
    Deploy. Der dauerhafte Wert je Anruf steht in rubric_score.payload_jsonb['beleg_check'].
    """
    leer = {'geprueft': 0, 'treffer': 0, 'near_miss': 0, 'verworfen': 0,
            'compliance_beleg_verworfen': 0}
    try:
        from services.beleg_check_counter import get_beleg_check_counts
        counts = get_beleg_check_counts()
    except Exception:
        return leer
    ergebnis = dict(leer)
    ergebnis.update({k: int(counts.get(k, 0) or 0) for k in leer})
    return ergebnis


_BELEG_FELDER = ('geprueft', 'treffer', 'near_miss', 'verworfen', 'compliance_beleg_verworfen')


def _beleg_check_faelle(db, seit, grenze=20):
    """METRIK-1 D-23 — die JE ANRUF persistierten Werte aus rubric_score.payload_jsonb.

    Dies ist der echte Leser des dauerhaften Werts. Die Kachel aus Task 3
    (services/beleg_check_counter) misst eine ANDERE Groesse: summiert, pro Prozess, seit
    Deploy. Beide stehen bewusst nebeneinander.

    WARUM EINE MANDANTEN-SCHLEIFE UND KEINE EINZELNE ABFRAGE: rubric_score steht unter FORCE ROW
    LEVEL SECURITY. Ohne gesetzte Mandanten-GUC liefert die Tabelle als nerve_app STILL 0 Zeilen
    statt eines Fehlers — eine leere Liste waere von "keine Verwuerfe" nicht zu unterscheiden.
    Genau dieser Fehler hat im Projekt schon einmal zu einem falschen "kein Row"-Befund gefuehrt.

    WARUM DAS ROLLBACK VOR JEDEM MANDANTEN: die GUC ist TRANSAKTIONS-lokal und wird vom
    after_begin-Hook beim BEGINN einer Transaktion gesetzt (database/db.py:88-105). Wer sie
    mitten in einer laufenden Transaktion umsetzt, liest weiter mit der alten.

    ZEIT-ANKER (Punkt 26): gefiltert wird auf rubric_score.created_at, also auf den Zeitpunkt der
    PRUEFUNG — bewusst NICHT auf calls.started_at. Die Frage lautet "wie viel hat der Pruefer
    heute verworfen", nicht "wie viele Anrufe von heute". Hier IST die Schreib-Zeit der fachlich
    richtige Anker; der Unterschied ist benannt, nicht uebersehen.

    Returns:
        list[dict], je Fall: call_id, tenant_id, created_at, geprueft, treffer, near_miss,
        verworfen, compliance_beleg_verworfen. Sortiert nach created_at absteigend, auf
        `grenze` gekuerzt.
    """
    from database.db import set_current_tenant, clear_current_tenant
    from database.models import RubricScore, TenantOrg

    faelle = []
    try:
        tenant_ids = [row[0] for row in db.query(TenantOrg.id).all()]
        for tid in tenant_ids:
            # Die GUC greift erst beim NAECHSTEN Transaktions-Beginn — deshalb erst beenden.
            db.rollback()
            set_current_tenant(str(tid))
            rows = (db.query(RubricScore)
                      .filter(RubricScore.created_at >= seit,
                              RubricScore.origin == 'live')
                      .all())
            for r in rows:
                payload = getattr(r, 'payload_jsonb', None) or {}
                bc = payload.get('beleg_check') if isinstance(payload, dict) else None
                if not isinstance(bc, dict):
                    continue
                fall = {
                    'call_id': str(getattr(r, 'call_id', '') or ''),
                    'tenant_id': str(tid),
                    'created_at': getattr(r, 'created_at', None),
                }
                for feld in _BELEG_FELDER:
                    wert = bc.get(feld, 0)
                    fall[feld] = int(wert) if isinstance(wert, int) and not isinstance(wert, bool) else 0
                faelle.append(fall)
    except Exception as e:
        # DB-Regel: kein stiller except auf einer PG-Session OHNE rollback (sonst vergiftet der
        # verschluckte Fehler die Transaktion -> InFailedSqlTransaction in jeder Folge-Abfrage).
        db.rollback()
        print(f"[BelegCheckFaelle] uebersprungen: {type(e).__name__}: {e}")
        return []
    finally:
        db.rollback()
        clear_current_tenant()

    faelle.sort(key=lambda f: (f['created_at'] is not None, f['created_at']), reverse=True)
    return faelle[:grenze]


def _beleg_check_faelle_payload(db):
    """Tages-Summe + Schwellen-Alarm + die aufrufbaren Einzelfaelle (Bauform: _cost_skip_payload).

    Fehlertolerant, raist NIE: eine Diagnose-Sicht darf das Founder-Dashboard nicht kippen.
    """
    leer = {k: 0 for k in _BELEG_FELDER}
    try:
        faelle = _beleg_check_faelle(db, datetime.combine(date.today(), datetime.min.time()))
    except Exception:
        return {'heute': leer, 'alarm': False,
                'schwelle': BELEG_ALARM_VERWORFEN_HEUTE, 'faelle': []}

    heute = dict(leer)
    for fall in faelle:
        for feld in _BELEG_FELDER:
            heute[feld] += fall.get(feld, 0)

    # Zwei Wege in den Alarm: die schiere MENGE, oder der ANTEIL ab einer tragfaehigen Stichprobe.
    alarm = heute['verworfen'] >= BELEG_ALARM_VERWORFEN_HEUTE
    if not alarm and heute['geprueft'] >= BELEG_ALARM_MIN_GEPRUEFT:
        anteil = (heute['verworfen'] + heute['near_miss']) / float(heute['geprueft'])
        alarm = anteil > BELEG_ALARM_ANTEIL

    return {
        'heute': heute,
        'alarm': bool(alarm),
        'schwelle': BELEG_ALARM_VERWORFEN_HEUTE,
        'faelle': [{
            'call_id': f['call_id'],
            'zeit': f['created_at'].strftime('%H:%M') if f.get('created_at') else '—',
            **{k: f.get(k, 0) for k in _BELEG_FELDER},
        } for f in faelle],
    }


def _mrr_from_active_orgs(db):
    """MRR-Sum: Summe plan_preis aller active Organisationen.
    Fallback auf PLANS[plan]['preis'] wenn plan_preis nicht gesetzt."""
    from database.models import Organisation
    from config import PLANS
    orgs = db.query(Organisation).filter(
        Organisation.subscription_status == 'active'
    ).all()
    total = 0.0
    for o in orgs:
        price = getattr(o, 'plan_preis', None)
        if price:
            total += float(price)
        else:
            pk = getattr(o, 'plan', None) or 'starter'
            total += float(PLANS.get(pk, {}).get('preis', 0))
    return total


@admin_dashboard_bp.route('/')
@login_required
@superadmin_required
def index():
    tab = request.args.get('tab', 'uebersicht')
    if tab not in VALID_TABS:
        tab = 'uebersicht'
    period = request.args.get('period')
    _parse_period(period)  # validates, aborts 400 on bad format
    return render_template(
        'admin/dashboard.html',
        active_tab=tab,
        period=period or date.today().strftime('%Y-%m'),
    )


# ── Tab Uebersicht: KPI Endpoint ─────────────────────────────────────

@admin_dashboard_bp.route('/api/overview')
@login_required
@superadmin_required
def api_overview():
    from database.models import (
        RevenueLog, ApiCostLog, FixedCost, Organisation, User
    )
    from sqlalchemy import func

    period = request.args.get('period')
    start, end = _parse_period(period)

    db = get_session()
    try:
        # MRR aus aktiven Subscriptions (forward-looking)
        mrr_eur = _mrr_from_active_orgs(db)

        # Einnahmen in Periode (backward-looking, netto)
        revenue_q = (db.query(func.sum(RevenueLog.netto_cents))
                     .filter(RevenueLog.paid_at >= start,
                             RevenueLog.paid_at < end))
        revenue_eur = float((revenue_q.scalar() or 0) / 100.0)

        # API-Kosten in Periode
        api_costs_q = (db.query(func.sum(ApiCostLog.cost_eur))
                       .filter(ApiCostLog.created_at >= start,
                               ApiCostLog.created_at < end))
        api_costs_eur = float(api_costs_q.scalar() or 0)

        # Fixkosten (cycle='monthly', active)
        fc_monthly = (db.query(func.sum(FixedCost.amount_eur))
                      .filter(FixedCost.cycle == 'monthly',
                              FixedCost.active == True)  # noqa: E712
                      .scalar() or 0)
        total_costs = api_costs_eur + float(fc_monthly)

        # Aktive User (Org mit active-Subscription)
        active_users = (db.query(func.count(User.id))
                        .join(Organisation, Organisation.id == User.org_id)
                        .filter(Organisation.subscription_status == 'active')
                        .scalar() or 0)

        gewinn = revenue_eur - total_costs
        marge_pct = (gewinn / revenue_eur * 100.0) if revenue_eur > 0 else 0

        # 12-Monats-Serie rueckwaerts (ab 11 Monate vor start bis start inkl.)
        labels_12m = []
        mrr_12m = []
        costs_12m = []
        margin_12m = []

        cursor_year, cursor_month = start.year, start.month
        # 11 Monate zurueck
        for _ in range(11):
            cursor_month -= 1
            if cursor_month == 0:
                cursor_month = 12
                cursor_year -= 1

        for _ in range(12):
            m_start = date(cursor_year, cursor_month, 1)
            _last = calendar.monthrange(cursor_year, cursor_month)[1]
            m_end = date(cursor_year, cursor_month, _last) + timedelta(days=1)

            rev = float((db.query(func.sum(RevenueLog.netto_cents))
                         .filter(RevenueLog.paid_at >= m_start,
                                 RevenueLog.paid_at < m_end).scalar() or 0) / 100.0)
            api_c = float(db.query(func.sum(ApiCostLog.cost_eur))
                          .filter(ApiCostLog.created_at >= m_start,
                                  ApiCostLog.created_at < m_end).scalar() or 0)
            total_c = api_c + float(fc_monthly)
            labels_12m.append(f"{cursor_year}-{cursor_month:02d}")
            mrr_12m.append(round(rev, 2))
            costs_12m.append(round(total_c, 2))
            margin_12m.append(round((rev - total_c) / rev * 100, 1) if rev > 0 else 0)

            cursor_month += 1
            if cursor_month > 12:
                cursor_month = 1
                cursor_year += 1

        return jsonify({
            'period': start.strftime('%Y-%m'),
            'kpis': {
                'mrr': f"{mrr_eur:,.2f} EUR".replace(',', '.'),
                'costs_mo': f"{total_costs:,.2f} EUR".replace(',', '.'),
                'marge': f"{marge_pct:,.1f} %".replace(',', '.'),
                'active_users': str(int(active_users)),
                'gewinn_mo': f"{gewinn:,.2f} EUR".replace(',', '.'),
            },
            # KOSTEN-1 W3: Laufzeit-Skip-Zaehler. Soll-Wert 0. Steht hier etwas anderes,
            # verwirft cost_tracker gerade Kosten still — meist ein neuer Modell-String ohne
            # Rate. Das ist der einzige Waechter, der ENV-/config-basierte Modellnamen faengt.
            # Bewusste Grenze: der Zaehler lebt im RAM DIESES Prozesses (Gunicorn-Worker) —
            # nerve-rt und weitere Worker zaehlen eigene Staende. Deshalb das Label "pro Prozess".
            'cost_log_skips': _cost_skip_payload(),
            # SOFORT-2 (D-04): Zeitueberschreitungen der Live-LLM-Aufrufe. Soll-Wert 0.
            # Steht hier etwas anderes, hat ein Aufruf sein Limit gerissen — Stufe 1 hat die
            # Runde still uebersprungen, und ab drei in Folge hat der Berater es gesehen.
            # Bewusste Grenze (wie bei cost_log_skips): der Zaehler lebt im RAM DIESES
            # Prozesses (Gunicorn-Worker) — weitere Worker zaehlen eigene Staende. Deshalb das
            # Label "pro Prozess". Ein Neustart setzt ihn auf 0.
            'live_llm_timeouts': _live_timeout_payload(),
            # METRIK-1 D-23: verworfene Beleg-Zitate der Bewerter-Beobachtungen. KEIN Soll-0-Alarm
            # — Verwuerfe sind der GEWOLLTE Schutz vor erfundenen Zitaten. Auffaellig ist erst ein
            # hoher ANTEIL (verworfen / geprueft): dann halluziniert das Modell oder der
            # Pruef-Korpus stimmt nicht mehr mit dem Bewerter-Auftrag ueberein.
            # Bewusste Grenze (wie bei cost_log_skips): RAM DIESES Prozesses, seit Deploy.
            # Der dauerhafte Wert je Anruf steht in rubric_score.payload_jsonb['beleg_check'].
            'beleg_check': _beleg_check_payload(),
            # METRIK-1 D-23: der DAUERHAFTE Wert je Anruf (rubric_score.payload_jsonb), gelesen
            # ueber die Mandanten-Schleife. Andere Groesse als 'beleg_check' darueber: dort RAM,
            # summiert, pro Prozess — hier je Anruf, aus der Datenbank, mit aufrufbarem Einzelfall.
            'beleg_check_faelle': _beleg_check_faelle_payload(db),
            'mrr_costs_12m': {
                'labels': labels_12m,
                'mrr': mrr_12m,
                'costs': costs_12m,
            },
            'margin_12m': {
                'labels': labels_12m,
                'values': margin_12m,
            },
        })
    finally:
        db.close()


# ── Tab Einnahmen ────────────────────────────────────────────────────

@admin_dashboard_bp.route('/einnahmen')
@login_required
@superadmin_required
def einnahmen_page():
    from database.models import RevenueLog
    from sqlalchemy import func

    period = request.args.get('period')
    start, end = _parse_period(period)

    db = get_session()
    try:
        # Summary by tax_treatment
        rows = (db.query(RevenueLog.tax_treatment,
                         func.sum(RevenueLog.netto_cents),
                         func.sum(RevenueLog.ust_cents),
                         func.sum(RevenueLog.brutto_cents),
                         func.count(RevenueLog.id))
                .filter(RevenueLog.paid_at >= start,
                        RevenueLog.paid_at < end)
                .group_by(RevenueLog.tax_treatment).all())
        summary = [{
            'treatment': r[0],
            'netto': round((r[1] or 0) / 100.0, 2),
            'ust': round((r[2] or 0) / 100.0, 2),
            'brutto': round((r[3] or 0) / 100.0, 2),
            'count': r[4],
        } for r in rows]

        # By plan
        plan_rows = (db.query(RevenueLog.plan_key,
                              func.count(RevenueLog.id),
                              func.sum(RevenueLog.netto_cents))
                     .filter(RevenueLog.paid_at >= start,
                             RevenueLog.paid_at < end)
                     .group_by(RevenueLog.plan_key).all())
        by_plan = [{
            'plan': (r[0] or '—'),
            'count': r[1],
            'netto': round((r[2] or 0) / 100.0, 2),
        } for r in plan_rows]

        # By country + tax_treatment
        country_rows = (db.query(RevenueLog.country, RevenueLog.tax_treatment,
                                 func.count(RevenueLog.id),
                                 func.sum(RevenueLog.netto_cents))
                        .filter(RevenueLog.paid_at >= start,
                                RevenueLog.paid_at < end)
                        .group_by(RevenueLog.country,
                                  RevenueLog.tax_treatment).all())
        by_country = [{
            'country': r[0] or '?',
            'treatment': r[1],
            'count': r[2],
            'netto': round((r[3] or 0) / 100.0, 2),
        } for r in country_rows]

        # Transactions (paginated)
        try:
            page = max(1, int(request.args.get('page', 1)))
        except (TypeError, ValueError):
            page = 1
        per_page = 50
        txs = (db.query(RevenueLog)
               .filter(RevenueLog.paid_at >= start,
                       RevenueLog.paid_at < end)
               .order_by(RevenueLog.paid_at.desc())
               .offset((page - 1) * per_page).limit(per_page).all())
        transactions = [{
            'date': t.paid_at.strftime('%Y-%m-%d') if t.paid_at else '',
            'invoice_id': t.stripe_invoice_id,
            'country': t.country or '',
            'plan': t.plan_key or '',
            'netto': round((t.netto_cents or 0) / 100.0, 2),
            'ust': round((t.ust_cents or 0) / 100.0, 2),
            'brutto': round((t.brutto_cents or 0) / 100.0, 2),
            'treatment': t.tax_treatment,
        } for t in txs]

        return jsonify({
            'period': start.strftime('%Y-%m'),
            'summary': summary,
            'by_plan': by_plan,
            'by_country': by_country,
            'transactions': transactions,
            'page': page,
        })
    finally:
        db.close()


# ── Tab Ausgaben ─────────────────────────────────────────────────────

# EÜR-Kategorie-Mapping (Stammdaten, hart-codiert)
EUR_CATEGORY_BY_PROVIDER = {
    'anthropic':  {'label': 'Anthropic Claude API',  'cat': 'Bezogene Fremdleistungen', 'eur_line': 26, 'skr03': '3100', 'vat_rc': True},
    'deepgram':   {'label': 'Deepgram Nova-2 STT',   'cat': 'Bezogene Fremdleistungen', 'eur_line': 26, 'skr03': '3100', 'vat_rc': True},
    'elevenlabs': {'label': 'ElevenLabs TTS',        'cat': 'Bezogene Fremdleistungen', 'eur_line': 26, 'skr03': '3100', 'vat_rc': True},
    'stripe':     {'label': 'Stripe Gebühren',       'cat': 'Nebenkosten Geldverkehr',  'eur_line': 57, 'skr03': '4970', 'vat_rc': False},
}


@admin_dashboard_bp.route('/ausgaben')
@login_required
@superadmin_required
def ausgaben_page():
    from database.models import ApiCostLog, ApiRate, FixedCost
    from sqlalchemy import func
    period = request.args.get('period')
    start, end = _parse_period(period)
    db = get_session()
    try:
        by_provider_rows = (db.query(ApiCostLog.provider,
                                     func.sum(ApiCostLog.cost_eur))
                              .filter(ApiCostLog.created_at >= start,
                                      ApiCostLog.created_at < end)
                              .group_by(ApiCostLog.provider).all())
        by_provider = []
        api_total = 0.0
        for row in by_provider_rows:
            cat_info = EUR_CATEGORY_BY_PROVIDER.get(
                row[0],
                {'label': row[0], 'cat': 'Übrige', 'eur_line': 57, 'skr03': '', 'vat_rc': False},
            )
            val = float(row[1] or 0)
            api_total += val
            by_provider.append({**cat_info, 'provider': row[0], 'netto': round(val, 2)})

        fc_all = db.query(FixedCost).filter(FixedCost.active == True).all()  # noqa: E712
        fixed_costs_rows = []
        for fc in fc_all:
            amount = float(fc.amount_eur)
            if fc.cycle == 'monthly':
                period_cost = amount
            elif fc.cycle == 'yearly':
                period_cost = amount / 12.0
            elif fc.cycle == 'per_day':
                try:
                    home_days = int(request.args.get(f'days_{fc.id}', 0))
                except (TypeError, ValueError):
                    home_days = 0
                period_cost = amount * home_days
            else:
                period_cost = 0.0
            fixed_costs_rows.append({
                'id': fc.id, 'name': fc.name, 'amount_eur': amount,
                'cycle': fc.cycle, 'skr03': fc.skr03, 'eur_line': fc.eur_line,
                'period_cost': round(period_cost, 2),
            })
        fc_total = sum(r['period_cost'] for r in fixed_costs_rows)

        # 30-Tage-Serie (rückwärts ab end)
        daily = []
        cursor = end - timedelta(days=30)
        while cursor < end:
            next_day = cursor + timedelta(days=1)
            v = float(db.query(func.sum(ApiCostLog.cost_eur))
                        .filter(ApiCostLog.created_at >= cursor,
                                ApiCostLog.created_at < next_day).scalar() or 0)
            daily.append({'date': cursor.strftime('%Y-%m-%d'), 'cost': round(v, 2)})
            cursor = next_day

        rates = db.query(ApiRate).filter(ApiRate.active == True).all()  # noqa: E712
        now = datetime.utcnow()
        rates_out = []
        for r in rates:
            stale_days = (now - r.last_checked_at).days if r.last_checked_at else 999
            rates_out.append({
                'id': r.id, 'provider': r.provider, 'model': r.model,
                'unit_type': r.unit_type,
                'price': float(r.price_per_unit),
                'currency': r.currency,
                'last_checked': r.last_checked_at.strftime('%Y-%m-%d') if r.last_checked_at else '—',
                'stale_days': stale_days,
                'stale': stale_days > 30,
            })

        # ── MESSGERAETE-1 (D-04 + Punkt 12): zwei Tabellen aus EINER Abfrage-Paarung ──────
        # Zwei Abfragen statt einer: die Kosten-Summe braucht ALLE Zeilen, die Dauer-Statistik
        # nur die mit gesetztem latency_ms (D-07). Eine gemeinsame Abfrage wuerde entweder
        # Kosten unterschlagen oder Dauern doppelt zaehlen. Der Split Live-KI/Uebrige passiert
        # in Python gegen LIVE_LLM_CONTEXT_TAGS — kein context_tag-Filter im SQL, damit ein
        # unbekannter Tag sichtbar bleibt statt lautlos zu verschwinden.
        ktag_summen = (db.query(ApiCostLog.context_tag,
                                func.count(ApiCostLog.id),
                                func.sum(ApiCostLog.cost_eur))
                         .filter(ApiCostLog.created_at >= start,
                                 ApiCostLog.created_at < end)
                         .group_by(ApiCostLog.context_tag).all())
        ktag_latenzen = (db.query(ApiCostLog.context_tag,
                                  ApiCostLog.latency_ms,
                                  ApiCostLog.ttft_ms)
                           .filter(ApiCostLog.created_at >= start,
                                   ApiCostLog.created_at < end,
                                   ApiCostLog.latency_ms.isnot(None)).all())
        live_ki, uebrige_kosten = _aggregiere_kosten_nach_tag(ktag_summen, ktag_latenzen)

        return jsonify({
            'period': start.strftime('%Y-%m'),
            'by_provider': by_provider,
            'api_total': round(api_total, 2),
            'fixed_costs': fixed_costs_rows,
            'fixed_total': round(fc_total, 2),
            'grand_total': round(api_total + fc_total, 2),
            'daily_30': daily,
            'api_rates': rates_out,
            'live_ki': live_ki,
            'uebrige_kosten': uebrige_kosten,
        })
    finally:
        db.close()


@admin_dashboard_bp.route('/beleg-check/<call_id>')
@login_required
@superadmin_required
def beleg_check_fall(call_id):
    """METRIK-1 D-23 Auflage 3 — ein einzelner Fall der Zitat-Pruefung, wirklich nachpruefbar.

    Ohne diese Seite ist der Satz aus Plan 01 Task 4 ("wird von einem NERVE-Mitarbeiter
    geprueft") ein Versprechen ohne Deckung.

    RLS-Weg: calls traegt KEINE RLS und liefert tenant_id + conversation_log_id zum Anruf.
    Damit wird die Mandanten-GUC fuer GENAU diesen Fall gesetzt und rubric_score gelesen.
    Danach rollback + clear_current_tenant im finally.

    DSGVO: sichtbar ist ausschliesslich der BEREITS GESCHWAERZTE Transkript-Text (die
    Anonymisierung laeuft vor dem Persistieren). Zugriff nur superadmin. Die noch offene Folge
    — "Mitarbeiter pruefen Gespraeche" steht nicht in der Datenschutzerklaerung — ist in
    Plan 01 Task 4, Abschnitt C2 benannt (Ort: Anwalts-Liste).
    """
    from database.db import set_current_tenant, clear_current_tenant
    from database.models import Call, RubricScore, TranscriptSegment

    db = get_session()
    try:
        call = db.query(Call).filter(Call.id == call_id).first()
        if call is None:
            abort(404)
        tenant_id = getattr(call, 'tenant_id', None)
        conv_id = getattr(call, 'conversation_log_id', None)

        # transcript_segments traegt KEINE RLS -> vor dem GUC-Wechsel lesbar.
        segmente = []
        if conv_id is not None:
            segmente = (db.query(TranscriptSegment)
                          .filter(TranscriptSegment.conversation_log_id == conv_id)
                          .order_by(TranscriptSegment.ts_ms.asc(), TranscriptSegment.id.asc())
                          .all())

        zeile = None
        if tenant_id is not None:
            db.rollback()  # die GUC greift erst beim naechsten Transaktions-Beginn
            set_current_tenant(str(tenant_id))
            zeile = (db.query(RubricScore)
                       .filter(RubricScore.call_id == call.id,
                               RubricScore.origin == 'live')
                       .first())

        payload = (getattr(zeile, 'payload_jsonb', None) or {}) if zeile is not None else {}
        rohwerte = payload.get('beleg_check') if isinstance(payload, dict) else None
        werte = {k: 0 for k in _BELEG_FELDER}
        if isinstance(rohwerte, dict):
            for feld in _BELEG_FELDER:
                wert = rohwerte.get(feld, 0)
                werte[feld] = int(wert) if isinstance(wert, int) and not isinstance(wert, bool) else 0

        observations = (getattr(zeile, 'observations_jsonb', None) or {}) if zeile is not None else {}
        compliance = observations.get('_compliance') if isinstance(observations, dict) else None
        if not isinstance(compliance, dict):
            compliance = {'verletzt': False, 'beleg_zitat': ''}

        return render_template(
            'admin/beleg_check_fall.html',
            call_id=str(call.id),
            zeitpunkt=getattr(zeile, 'created_at', None) if zeile is not None else None,
            werte=werte,
            compliance=compliance,
            observations=observations if isinstance(observations, dict) else {},
            segmente=segmente,
        )
    finally:
        db.rollback()
        clear_current_tenant()
        db.close()


@admin_dashboard_bp.route('/api_rates/<int:rate_id>/mark_checked', methods=['POST'])
@login_required
@superadmin_required
def api_rate_mark_checked(rate_id):
    from database.models import ApiRate
    db = get_session()
    try:
        rate = db.query(ApiRate).get(rate_id)
        if not rate:
            abort(404)
        rate.last_checked_at = datetime.utcnow()
        db.commit()
        return jsonify({'ok': True, 'last_checked': rate.last_checked_at.isoformat()})
    finally:
        db.close()


@admin_dashboard_bp.route('/api_rates/<int:rate_id>/new_price', methods=['POST'])
@login_required
@superadmin_required
def api_rate_new_price(rate_id):
    """Deaktiviert alten Preis, legt neuen aktiven Preis an, schreibt PriceChangeLog."""
    from database.models import ApiRate, ApiCostLog, PriceChangeLog
    from sqlalchemy import func
    from decimal import Decimal, InvalidOperation
    db = get_session()
    try:
        old = db.query(ApiRate).get(rate_id)
        if not old:
            abort(404)
        try:
            new_price = Decimal(request.form.get('new_price', '').replace(',', '.'))
        except (InvalidOperation, AttributeError):
            abort(400, description="new_price invalid")
        note = (request.form.get('note', '') or '')[:500]
        old.active = False
        db.flush()
        new = ApiRate(
            provider=old.provider, model=old.model, unit_type=old.unit_type,
            price_per_unit=new_price, currency=old.currency, active=True,
            last_checked_at=datetime.utcnow(),
            source_url=old.source_url,
        )
        db.add(new)
        db.flush()
        since = datetime.utcnow() - timedelta(days=30)
        avg_units = float(db.query(func.sum(ApiCostLog.units))
                            .filter(ApiCostLog.provider == old.provider,
                                    ApiCostLog.model == old.model,
                                    ApiCostLog.unit_type == old.unit_type,
                                    ApiCostLog.created_at >= since).scalar() or 0)
        delta = float(new_price) - float(old.price_per_unit)
        try:
            from services.exchange_rates import get_current_rate
            fx = float(get_current_rate('USD_EUR')) if old.currency == 'USD' else 1.0
        except Exception:
            fx = 0.92 if old.currency == 'USD' else 1.0
        impact = round(avg_units * delta * fx, 2)
        db.add(PriceChangeLog(
            api_rate_id=new.id, old_rate=old.price_per_unit,
            new_rate=new_price, currency=old.currency,
            impact_eur_per_month=Decimal(str(impact)), note=note,
        ))
        db.commit()
        return jsonify({'ok': True, 'impact_eur_per_month': impact})
    finally:
        db.close()


@admin_dashboard_bp.route('/fixed_costs', methods=['POST'])
@login_required
@superadmin_required
def fixed_cost_create():
    from database.models import FixedCost
    from decimal import Decimal, InvalidOperation
    db = get_session()
    try:
        name = (request.form.get('name', '') or '').strip()[:128]
        cycle = request.form.get('cycle', 'monthly')
        if cycle not in ('monthly', 'yearly', 'per_day'):
            abort(400, description="invalid cycle")
        try:
            amount = Decimal(request.form.get('amount_eur', '0').replace(',', '.'))
            vat = Decimal(request.form.get('vat_rate', '19').replace(',', '.'))
        except (InvalidOperation, AttributeError):
            abort(400, description="amount/vat invalid")
        if not name or float(amount) < 0:
            abort(400, description="name and non-negative amount required")
        try:
            eur_line = int(request.form.get('eur_line') or 57)
        except (TypeError, ValueError):
            eur_line = 57
        fc = FixedCost(
            name=name, amount_eur=amount, vat_rate=vat,
            cycle=cycle,
            skr03=(request.form.get('skr03', '') or '')[:8] or None,
            eur_line=eur_line,
            active=True,
        )
        db.add(fc)
        db.commit()
        return jsonify({'ok': True, 'id': fc.id})
    finally:
        db.close()


@admin_dashboard_bp.route('/fixed_costs/<int:fc_id>', methods=['POST'])
@login_required
@superadmin_required
def fixed_cost_update(fc_id):
    from database.models import FixedCost
    from decimal import Decimal, InvalidOperation
    db = get_session()
    try:
        fc = db.query(FixedCost).get(fc_id)
        if not fc:
            abort(404)
        action = request.form.get('_action', 'update')
        if action == 'delete':
            db.delete(fc)
            db.commit()
            return jsonify({'ok': True, 'deleted': True})
        if action == 'toggle':
            fc.active = not bool(fc.active)
            db.commit()
            return jsonify({'ok': True, 'active': fc.active})
        # update
        name = request.form.get('name')
        if name is not None:
            fc.name = name[:128]
        skr = request.form.get('skr03')
        if skr is not None:
            fc.skr03 = skr[:8] or None
        try:
            if 'amount_eur' in request.form:
                fc.amount_eur = Decimal(request.form['amount_eur'].replace(',', '.'))
            if 'vat_rate' in request.form:
                fc.vat_rate = Decimal(request.form['vat_rate'].replace(',', '.'))
        except (InvalidOperation, AttributeError):
            abort(400, description="amount/vat invalid")
        if 'cycle' in request.form:
            c = request.form['cycle']
            if c in ('monthly', 'yearly', 'per_day'):
                fc.cycle = c
        if 'eur_line' in request.form:
            try:
                fc.eur_line = int(request.form['eur_line'])
            except (TypeError, ValueError):
                pass
        db.commit()
        return jsonify({'ok': True})
    finally:
        db.close()


# ── Tab Kunden: Profitabilität (Org + User-Drilldown) ────────────────

def classify_margin(margin_pct: float) -> str:
    if margin_pct > 70:
        return 'healthy'
    if margin_pct >= 50:
        return 'warn'
    return 'critical'


def compute_org_profitability(db, org_id: int, start, end) -> dict:
    from database.models import RevenueLog, ApiCostLog
    from sqlalchemy import func
    revenue_cents = db.query(func.sum(RevenueLog.netto_cents)).filter(
        RevenueLog.org_id == org_id,
        RevenueLog.paid_at >= start, RevenueLog.paid_at < end).scalar() or 0
    revenue = float(revenue_cents) / 100.0
    api_cost = float(db.query(func.sum(ApiCostLog.cost_eur)).filter(
        ApiCostLog.org_id == org_id,
        ApiCostLog.created_at >= start, ApiCostLog.created_at < end).scalar() or 0)
    margin_pct = ((revenue - api_cost) / revenue * 100.0) if revenue > 0 else 0.0
    return {
        'revenue_eur': round(revenue, 2),
        'api_cost_eur': round(api_cost, 2),
        'margin_pct': round(margin_pct, 1),
        'status': classify_margin(margin_pct),
    }


@admin_dashboard_bp.route('/kunden')
@login_required
@superadmin_required
def kunden_page():
    from database.models import Organisation, User
    from sqlalchemy import func
    period = request.args.get('period')
    start, end = _parse_period(period)
    db = get_session()
    try:
        orgs = db.query(Organisation).filter(
            Organisation.subscription_status == 'active').all()
        out = []
        for org in orgs:
            prof = compute_org_profitability(db, org.id, start, end)
            user_count = db.query(func.count(User.id)).filter(User.org_id == org.id).scalar() or 0
            out.append({
                'org_id': org.id,
                'name': org.name,
                'plan': getattr(org, 'plan', '') or '',
                'user_count': int(user_count),
                **prof,
            })
        out.sort(key=lambda r: r['margin_pct'])
        summary = {
            'healthy':  sum(1 for r in out if r['status'] == 'healthy'),
            'warn':     sum(1 for r in out if r['status'] == 'warn'),
            'critical': sum(1 for r in out if r['status'] == 'critical'),
        }
        return jsonify({
            'period': start.strftime('%Y-%m'),
            'orgs': out,
            'summary': summary,
            # KOSTEN-1 R5: Historie-Marker. Bedingung ist START < Stichtag, NICHT end — ein
            # Zeitraum, der ueber den Stichtag HINWEG laeuft, ist teilweise unvollstaendig und
            # muss den Hinweis genauso zeigen. Mit `end <` waere genau der Uebergangs-Monat
            # stillschweigend als vollstaendig durchgegangen.
            'cost_data_incomplete': start < COST_DATA_COMPLETE_SINCE,
            'cost_data_complete_since': COST_DATA_COMPLETE_SINCE.strftime('%d.%m.%Y'),
        })
    finally:
        db.close()


@admin_dashboard_bp.route('/kunden/<int:org_id>/users')
@login_required
@superadmin_required
def kunden_drilldown(org_id):
    from database.models import User, ApiCostLog
    from sqlalchemy import func
    period = request.args.get('period')
    start, end = _parse_period(period)
    db = get_session()
    try:
        users = db.query(User).filter(User.org_id == org_id).all()
        result = []
        for u in users:
            by_provider_rows = db.query(
                ApiCostLog.provider, func.sum(ApiCostLog.cost_eur)
            ).filter(
                ApiCostLog.user_id == u.id,
                ApiCostLog.created_at >= start, ApiCostLog.created_at < end,
            ).group_by(ApiCostLog.provider).all()
            breakdown = {p: round(float(c or 0), 2) for p, c in by_provider_rows}
            total = sum(breakdown.values())
            weekly = []
            cur = end - timedelta(days=28)
            while cur < end:
                nxt = cur + timedelta(days=7)
                v = float(db.query(func.sum(ApiCostLog.cost_eur)).filter(
                    ApiCostLog.user_id == u.id,
                    ApiCostLog.created_at >= cur,
                    ApiCostLog.created_at < nxt).scalar() or 0)
                weekly.append({'week_start': cur.strftime('%Y-%m-%d'), 'cost': round(v, 2)})
                cur = nxt
            result.append({
                'user_id': u.id, 'email': u.email,
                'total_cost_eur': round(total, 2),
                'by_provider': breakdown,
                'weekly_trend': weekly,
            })
        result.sort(key=lambda r: r['total_cost_eur'], reverse=True)
        return jsonify({'org_id': org_id, 'users': result})
    finally:
        db.close()


# ── Tab EÜR ───────────────────────────────────────────────────────

@admin_dashboard_bp.route('/eur')
@login_required
@superadmin_required
def eur_data():
    period = request.args.get('period')
    start, end = _parse_period(period)
    try:
        home_days = int(request.args.get('home_days', 0))
    except (TypeError, ValueError):
        home_days = 0
    from services.eur_calculator import compute_eur
    db = get_session()
    try:
        data = compute_eur(start, end, db, home_days=home_days)
        return jsonify(data)
    finally:
        db.close()


# ── Tab Export: PDF + CSV Downloads ─────────────────────────────────

@admin_dashboard_bp.route('/export/eur.html')
@login_required
@superadmin_required
def export_eur_html_preview():
    """HTML-Preview des EÜR-Reports. Funktioniert IMMER (auch ohne WeasyPrint).
    Dev-Fallback wenn WeasyPrint nicht installiert ist."""
    period = request.args.get('period')
    start, end = _parse_period(period)
    try:
        home_days = int(request.args.get('home_days', 0))
    except (TypeError, ValueError):
        home_days = 0
    from services.eur_calculator import compute_eur
    db = get_session()
    try:
        data = compute_eur(start, end, db, home_days=home_days)
    finally:
        db.close()
    return render_template('admin/eur_pdf.html', data=data)


@admin_dashboard_bp.route('/export/eur.pdf')
@login_required
@superadmin_required
def export_eur_pdf():
    """EÜR als PDF via WeasyPrint. 501 wenn WeasyPrint nicht installiert (Dev-Maschine)."""
    try:
        from weasyprint import HTML
    except ImportError:
        return ("WeasyPrint nicht installiert. Verwende /export/eur.html für Preview.", 501)
    period = request.args.get('period')
    start, end = _parse_period(period)
    try:
        home_days = int(request.args.get('home_days', 0))
    except (TypeError, ValueError):
        home_days = 0
    from services.eur_calculator import compute_eur
    db = get_session()
    try:
        data = compute_eur(start, end, db, home_days=home_days)
    finally:
        db.close()
    html = render_template('admin/eur_pdf.html', data=data)
    pdf_bytes = HTML(string=html).write_pdf()
    from flask import Response
    return Response(pdf_bytes, mimetype='application/pdf', headers={
        'Content-Disposition': f'attachment; filename=eur_{period or "current"}.pdf'
    })


# ── CSV Exports ──────────────────────────────────────────────────────

def _csv_response(rows: list, headers: list, filename: str):
    """Hilfs-Helper für CSV-Download mit UTF-8-BOM (Excel-kompatibel)."""
    import csv
    from io import StringIO
    from flask import Response
    buf = StringIO()
    writer = csv.writer(buf, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    data = '\ufeff' + buf.getvalue()  # BOM for Excel
    return Response(data, mimetype='text/csv; charset=utf-8', headers={
        'Content-Disposition': f'attachment; filename={filename}'
    })


@admin_dashboard_bp.route('/export/einnahmen.csv')
@login_required
@superadmin_required
def export_einnahmen_csv():
    from database.models import RevenueLog
    period = request.args.get('period')
    start, end = _parse_period(period)
    db = get_session()
    try:
        rows = (db.query(RevenueLog)
                  .filter(RevenueLog.paid_at >= start, RevenueLog.paid_at < end)
                  .order_by(RevenueLog.paid_at).all())
        csv_rows = [[
            r.paid_at.strftime('%Y-%m-%d') if r.paid_at else '',
            r.stripe_invoice_id or '',
            r.country or '',
            r.plan_key or '',
            f"{(r.netto_cents or 0)/100:.2f}".replace('.', ','),
            f"{(r.ust_cents or 0)/100:.2f}".replace('.', ','),
            f"{(r.brutto_cents or 0)/100:.2f}".replace('.', ','),
            r.tax_treatment or '',
        ] for r in rows]
        return _csv_response(csv_rows,
            ['Datum','Rechnung','Land','Plan','Netto EUR','USt EUR','Brutto EUR','Behandlung'],
            f'einnahmen_{period or "current"}.csv')
    finally:
        db.close()


@admin_dashboard_bp.route('/export/ausgaben.csv')
@login_required
@superadmin_required
def export_ausgaben_csv():
    from database.models import ApiCostLog, FixedCost
    period = request.args.get('period')
    start, end = _parse_period(period)
    try:
        home_days = int(request.args.get('home_days', 0))
    except (TypeError, ValueError):
        home_days = 0
    db = get_session()
    try:
        csv_rows = []
        api_rows = (db.query(ApiCostLog)
                      .filter(ApiCostLog.created_at >= start, ApiCostLog.created_at < end)
                      .order_by(ApiCostLog.created_at).all())
        for a in api_rows:
            category = EUR_CATEGORY_BY_PROVIDER.get(a.provider, {})
            csv_rows.append([
                a.created_at.strftime('%Y-%m-%d') if a.created_at else '',
                a.provider,
                category.get('label', a.provider),
                f"{float(a.cost_eur or 0):.6f}".replace('.', ','),
                str(category.get('eur_line', '')),
                category.get('skr03', ''),
                getattr(a, 'context_tag', '') or '',
            ])
        for fc in db.query(FixedCost).filter(FixedCost.active == True).all():  # noqa: E712
            amt = float(fc.amount_eur)
            if fc.cycle == 'monthly':
                period_cost = amt
            elif fc.cycle == 'yearly':
                period_cost = amt / 12.0
            elif fc.cycle == 'per_day':
                period_cost = amt * home_days
            else:
                period_cost = 0
            if period_cost > 0:
                csv_rows.append([
                    start.strftime('%Y-%m-%d'),
                    'fixed_cost',
                    fc.name,
                    f"{period_cost:.2f}".replace('.', ','),
                    str(fc.eur_line or ''),
                    fc.skr03 or '',
                    fc.cycle,
                ])
        return _csv_response(csv_rows,
            ['Datum','Quelle','Bezeichnung','Netto EUR','EÜR-Zeile','SKR03','Kontext'],
            f'ausgaben_{period or "current"}.csv')
    finally:
        db.close()


@admin_dashboard_bp.route('/export/ustva.csv')
@login_required
@superadmin_required
def export_ustva_csv():
    from services.eur_calculator import compute_eur
    period = request.args.get('period')
    start, end = _parse_period(period)
    try:
        home_days = int(request.args.get('home_days', 0))
    except (TypeError, ValueError):
        home_days = 0
    db = get_session()
    try:
        data = compute_eur(start, end, db, home_days=home_days)
    finally:
        db.close()
    u = data['ust_voranmeldung']
    rows = [
        ['KZ 81', 'Steuerpflichtige Umsätze 19% (Basis)', f"{u['KZ81_steuerpfl_19']['basis']:.2f}".replace('.', ',')],
        ['KZ 81', 'Darauf entfallende USt',              f"{u['KZ81_steuerpfl_19']['ust']:.2f}".replace('.', ',')],
        ['KZ 21', 'Steuerfreie igL (EU B2B RC)',         f"{u['KZ21_igL']:.2f}".replace('.', ',')],
        ['KZ 45', 'Nicht steuerbare Drittland',          f"{u['KZ45_drittland']:.2f}".replace('.', ',')],
        ['KZ 84', 'Bemessungsgrundlage §13b RC',         f"{u['KZ84_rc_bemessung']:.2f}".replace('.', ',')],
        ['KZ 85', 'USt §13b RC',                         f"{u['KZ85_rc_ust']:.2f}".replace('.', ',')],
        ['KZ 66', 'Vorsteuer Inland',                    f"{u['KZ66_vst_inland']:.2f}".replace('.', ',')],
        ['KZ 67', 'Vorsteuer §13b RC',                   f"{u['KZ67_vst_rc']:.2f}".replace('.', ',')],
        ['—',     'USt-Zahllast',                         f"{u['zahllast']:.2f}".replace('.', ',')],
    ]
    return _csv_response(rows, ['KZ','Bezeichnung','Betrag EUR'],
                         f'ustva_{period or "current"}.csv')


@admin_dashboard_bp.route('/export/datev_stub.csv')
@login_required
@superadmin_required
def export_datev_stub():
    """D-07: STUB. NICHT DATEV-format-konform. Volle Implementierung wartet auf count.tax."""
    from database.models import RevenueLog, ApiCostLog
    period = request.args.get('period')
    start, end = _parse_period(period)
    db = get_session()
    try:
        csv_rows = []
        for r in db.query(RevenueLog).filter(
                RevenueLog.paid_at >= start, RevenueLog.paid_at < end).all():
            betrag = f"{(r.brutto_cents or 0)/100:.2f}".replace('.', ',')
            konto = '8400' if r.tax_treatment == 'DE_19' else '8338'
            csv_rows.append([
                r.paid_at.strftime('%d.%m.%Y') if r.paid_at else '',
                konto, '1200', betrag,
                f"NERVE Abo {r.plan_key or ''} {r.country or ''} #{r.stripe_invoice_id or ''}"[:200],
            ])
        for a in db.query(ApiCostLog).filter(
                ApiCostLog.created_at >= start, ApiCostLog.created_at < end).all():
            category = EUR_CATEGORY_BY_PROVIDER.get(a.provider, {})
            konto_haben = category.get('skr03', '3100')
            betrag = f"{float(a.cost_eur or 0):.2f}".replace('.', ',')
            csv_rows.append([
                a.created_at.strftime('%d.%m.%Y') if a.created_at else '',
                konto_haben, '1200', betrag,
                f"{a.provider} {getattr(a, 'model', '') or ''} {getattr(a, 'context_tag', '') or ''}"[:200],
            ])
        return _csv_response(csv_rows,
            ['Datum','Konto','Gegenkonto','Betrag','Buchungstext'],
            f'datev_stub_{period or "current"}.csv')
    finally:
        db.close()
