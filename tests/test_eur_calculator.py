"""Phase 04.7.2 Wave 4 — EUR calculator §13b + USt-VA.

KRITISCH: Diese Tests validieren die steuerliche Korrektheit der USt-VA-Berechnung.
Sie muessen gruen sein bevor die erste produktive USt-VA auf Basis des Dashboards
abgegeben wird (siehe HT-04 count.tax Sign-Off).
"""
from datetime import date, datetime
from decimal import Decimal
import pytest

from services.eur_calculator import compute_eur, RC_13B_PROVIDERS
from database.models import RevenueLog, ApiCostLog, FixedCost


def _add_rev(db, inv_id, netto_cents, ust_cents, treatment, day=15, month=3, year=2026, country='DE'):
    db.add(RevenueLog(
        stripe_invoice_id=inv_id,
        paid_at=datetime(year, month, day),
        netto_cents=netto_cents, ust_cents=ust_cents,
        brutto_cents=netto_cents + ust_cents,
        currency='EUR', country=country, tax_treatment=treatment,
    ))


def _add_api(db, provider, cost_eur, day=15, month=3, year=2026):
    db.add(ApiCostLog(
        provider=provider, model='test', user_id=None,
        units=Decimal('1'), unit_type='per_1k_input_tokens',
        rate_applied=Decimal('1'), rate_currency='EUR',
        fx_rate_applied=Decimal('1'),
        cost_eur=Decimal(str(cost_eur)),
        created_at=datetime(year, month, day),
    ))


def _add_fc(db, name, amount, cycle='monthly', eur_line=57, vat=19.0):
    db.add(FixedCost(name=name, amount_eur=Decimal(str(amount)),
                     vat_rate=Decimal(str(vat)), cycle=cycle,
                     eur_line=eur_line, active=True))


# ── Phase 08.23.2.PGTEST Gruppe A — Baseline-Delta-Scoping (T-PGTEST-26) ──────────
# compute_eur() summiert FixedCost GLOBAL (eur_calculator.py:84
# `db.query(FixedCost).filter(FixedCost.active.is_(True))` — KEIN Zeitraum-Filter, da Fixkosten
# zeitraum-unabhaengig periodisiert werden). Auf der persistenten nerve_test traegt fixed_costs
# bereits die app-import-Baseline (_seed_founder_dashboard_defaults: 5 aktive Fixkosten auf
# eur_line 52/57/65). Eine absolute Assertion auf den FixedCost-getriebenen Output (Z52/Z57/Z65,
# inland_vst → zahllast, summe_ausgaben_netto) zoege diese Baseline-Rows mit rein → False-Red.
# FIX (baseline-delta, Plan 04 Task 2): die FixedCost-freie Baseline VOR dem test-eigenen Insert
# einmal messen, danach den DELTA gegen den Erwartungswert pruefen. Die RevenueLog/ApiCostLog-Tests
# bleiben unberuehrt — die sind paid_at/created_at-zeitraum-gefiltert (Baseline-leer in ihrem Fenster).
# db_session ist function-scoped + rollback-covered (D-03) → KEIN cleanup_rows noetig (rollback raeumt
# die test-eigenen FixedCost-Rows weg; Baseline-Rows werden NIE angefasst).
def _fc_baseline(db, start, end, home_days=0):
    """FixedCost-getriebene Felder der Baseline (ohne test-eigene FixedCosts) — als Subtrahend."""
    r = compute_eur(start, end, db, home_days=home_days)
    a = r['ausgaben']
    return {
        'z52': a['Z52_miete_edv']['total_netto'],
        'z57': a['Z57_uebrige']['total_netto'],
        'z65': a['Z65_homeoffice']['total_netto'],
        'summe_ausgaben': a['summe_ausgaben_netto'],
        'inland_vst': a['Z72_vorsteuer']['inland_vst'],
        'zahllast': r['ust_voranmeldung']['zahllast'],
    }


# ---------------------------------------------------------------------------

def test_empty_period(db_session):
    # Baseline-Delta: der EINNAHMEN-Pfad + §13b sind FixedCost-frei → absolute 0-Assertion bleibt.
    # FixedCost-getriebene Felder (summe_ausgaben, zahllast) tragen die persistente Baseline → Delta=0
    # statt absolut 0 (es wurden in DIESEM Test keine test-eigenen FixedCosts/Revenue/Api committet).
    base = _fc_baseline(db_session, date(2026, 3, 1), date(2026, 4, 1), home_days=0)
    r = compute_eur(date(2026, 3, 1), date(2026, 4, 1), db_session, home_days=0)
    assert r['einnahmen']['summe_einnahmen_netto'] == 0
    # FixedCost-Baseline-Delta == 0 (kein test-eigener Insert):
    assert r['ausgaben']['summe_ausgaben_netto'] == base['summe_ausgaben']
    assert r['ust_voranmeldung']['KZ84_rc_bemessung'] == 0
    assert r['ust_voranmeldung']['KZ85_rc_ust'] == 0
    # zahllast haengt an inland_vst (FixedCost) → Delta gegen die FixedCost-freie Baseline:
    assert r['ust_voranmeldung']['zahllast'] == base['zahllast']


def test_line_mapping_einnahmen_splits(db_session):
    _add_rev(db_session, 'in1', 10000, 1900, 'DE_19')
    _add_rev(db_session, 'in2',  5000,    0, 'EU_RC',    country='AT')
    _add_rev(db_session, 'in3',  3000,    0, 'DRITTLAND', country='CH')
    db_session.commit()
    r = compute_eur(date(2026, 3, 1), date(2026, 4, 1), db_session)
    assert r['einnahmen']['Z14_de_19']['netto'] == 100.0
    assert r['einnahmen']['Z14_de_19']['ust'] == 19.0
    assert r['einnahmen']['Z16_eu_rc']['netto'] == 50.0
    assert r['einnahmen']['Z17_drittland']['netto'] == 30.0
    assert r['einnahmen']['Z19_vereinnahmte_ust'] == 19.0
    assert r['einnahmen']['summe_einnahmen_netto'] == 180.0


def test_reverse_charge_13b(db_session):
    """KRITISCHER Test: §13b Reverse-Charge Korrektheit."""
    _add_api(db_session, 'anthropic',  50.00)
    _add_api(db_session, 'deepgram',   30.00)
    _add_api(db_session, 'elevenlabs', 20.00)
    db_session.commit()
    r = compute_eur(date(2026, 3, 1), date(2026, 4, 1), db_session)
    assert r['ausgaben']['Z26_fremdleistungen']['total_netto'] == 100.0
    kz84 = r['ust_voranmeldung']['KZ84_rc_bemessung']
    kz85 = r['ust_voranmeldung']['KZ85_rc_ust']
    kz67 = r['ust_voranmeldung']['KZ67_vst_rc']
    assert kz84 == 100.0
    assert kz85 == 19.0          # 100 * 0.19
    assert kz67 == kz85          # identisch per §13b


def test_ust_zahllast(db_session):
    # Baseline-Delta: zahllast haengt an inland_vst (globaler FixedCost-Pfad). Auf nerve_test
    # traegt die Baseline FixedCosts → absolute 18.24 zoege deren inland_vst mit rein. Die
    # FixedCost-freie Baseline-zahllast vor dem test-eigenen Insert messen, danach den DELTA pruefen.
    base = _fc_baseline(db_session, date(2026, 3, 1), date(2026, 4, 1))
    _add_rev(db_session, 'in_de', 10000, 1900, 'DE_19')
    _add_api(db_session, 'anthropic', 100.00)
    _add_fc(db_session, 'Hetzner', 4.00, cycle='monthly', eur_line=52, vat=19.0)
    db_session.commit()
    r = compute_eur(date(2026, 3, 1), date(2026, 4, 1), db_session)
    # Test-eigener Beitrag zur zahllast: (19 USt-DE + 19 §13b-RC) - (0.76 inland-VSt-Hetzner + 19 §13b-VSt)
    # = 18.24. Der inland_vst-Anteil der Baseline-FixedCosts kuerzt sich via Delta heraus.
    test_eigene_zahllast = r['ust_voranmeldung']['zahllast'] - base['zahllast']
    assert round(test_eigene_zahllast, 2) == 18.24


def test_line_mapping_ausgaben_fixedcost(db_session):
    # Baseline-Delta: Z52/Z57/Z65 summieren GLOBAL alle aktiven FixedCosts der jeweiligen eur_line.
    # Auf nerve_test traegt die Baseline schon Hetzner(52)/Domain+Kontist+count.tax(57)/Homeoffice(65)
    # → absolute Assertions zoegen sie mit rein. Baseline pro Linie messen, danach den DELTA der
    # test-eigenen Rows pruefen.
    base = _fc_baseline(db_session, date(2026, 3, 1), date(2026, 4, 1), home_days=14)
    _add_fc(db_session, 'Hetzner',  4.00,  cycle='monthly', eur_line=52, vat=19.0)
    _add_fc(db_session, 'Domain',   1.25,  cycle='monthly', eur_line=57, vat=19.0)
    _add_fc(db_session, 'HomeOffice', 6.00, cycle='per_day', eur_line=65, vat=0.0)
    db_session.commit()
    r = compute_eur(date(2026, 3, 1), date(2026, 4, 1), db_session, home_days=14)
    assert round(r['ausgaben']['Z52_miete_edv']['total_netto'] - base['z52'], 2) == 4.0
    assert round(r['ausgaben']['Z57_uebrige']['total_netto'] - base['z57'], 2) == 1.25
    assert round(r['ausgaben']['Z65_homeoffice']['total_netto'] - base['z65'], 2) == 84.0  # 14 * 6


def test_period_filter_excludes_out_of_range(db_session):
    _add_api(db_session, 'anthropic', 999.99, month=1)
    _add_api(db_session, 'anthropic',  10.00, month=3)
    db_session.commit()
    r = compute_eur(date(2026, 3, 1), date(2026, 4, 1), db_session)
    assert r['ausgaben']['Z26_fremdleistungen']['total_netto'] == 10.0


def test_period_year_aggregation(db_session):
    for m in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12):
        _add_api(db_session, 'anthropic', 5.0, month=m)
    db_session.commit()
    r = compute_eur(date(2026, 1, 1), date(2027, 1, 1), db_session)
    assert r['ausgaben']['Z26_fremdleistungen']['total_netto'] == 60.0


def test_stripe_not_in_rc13b(db_session):
    # Phase 08.23.2.PGTEST.GREEN Muster C: echtes nerve_test traegt gesaete FixedCosts -> Z57_uebrige
    # enthaelt mehr als nur den Test-stripe-Betrag (absolutes ==5.0 drift-anfaellig). Delta: Baseline
    # messen, Test-Rows addieren, Differenz pruefen (float-sicher). Verifiziert weiterhin: stripe -> Z57
    # (nicht RC-13b/Z26), anthropic -> Z26 + KZ84.
    start, end = date(2026, 3, 1), date(2026, 4, 1)
    base = compute_eur(start, end, db_session)
    base_z26 = base['ausgaben']['Z26_fremdleistungen']['total_netto']
    base_z57 = base['ausgaben']['Z57_uebrige']['total_netto']
    base_kz84 = base['ust_voranmeldung']['KZ84_rc_bemessung']

    _add_api(db_session, 'anthropic', 50.0)
    _add_api(db_session, 'stripe',     5.0)
    db_session.commit()
    r = compute_eur(start, end, db_session)
    assert abs((r['ausgaben']['Z26_fremdleistungen']['total_netto'] - base_z26) - 50.0) < 1e-6
    assert abs((r['ausgaben']['Z57_uebrige']['total_netto'] - base_z57) - 5.0) < 1e-6
    assert abs((r['ust_voranmeldung']['KZ84_rc_bemessung'] - base_kz84) - 50.0) < 1e-6


def test_rc_13b_providers_constant():
    assert 'anthropic' in RC_13B_PROVIDERS
    assert 'deepgram' in RC_13B_PROVIDERS
    assert 'elevenlabs' in RC_13B_PROVIDERS
    assert 'stripe' not in RC_13B_PROVIDERS
