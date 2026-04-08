"""Phase 04.7.2 — EUeR Calculator mit §13b Reverse-Charge.

KRITISCH: Fehler hier fuehren zu falschen USt-Voranmeldungen.
count.tax Sign-Off (HT-04) vor erstem produktiven USt-VA Export erforderlich.
"""
from __future__ import annotations
from datetime import date
from sqlalchemy import func

# US-Drittland-Provider die §13b Reverse-Charge ausloesen
RC_13B_PROVIDERS = {'anthropic', 'deepgram', 'elevenlabs'}

# EUeR-Zeilen-Mapping (Anlage EUeR 2026 per Briefing)
EUR_LINES = {
    'Z14': 'Umsatzerloese 19% USt (DE)',
    'Z16': 'Umsatzerloese Reverse Charge EU B2B',
    'Z17': 'Nicht steuerbare Drittland-Leistungen',
    'Z19': 'Vereinnahmte Umsatzsteuer',
    'Z26': 'Bezogene Fremdleistungen',
    'Z52': 'Miete/Leasing EDV',
    'Z57': 'Uebrige Betriebsausgaben',
    'Z65': 'Haeusliches Arbeitszimmer',
    'Z72': 'Gezahlte Vorsteuer',
    'Z75': 'Summe Betriebsausgaben',
    'Z77': 'Gewinn vor Steuern',
}

UST_KZ = ['KZ81', 'KZ21', 'KZ45', 'KZ84', 'KZ85', 'KZ66', 'KZ67']


def _cents_to_eur(c) -> float:
    return round((c or 0) / 100.0, 2)


def _sum_treatment(db, start, end, treatment):
    from database.models import RevenueLog
    rows = db.query(
        func.sum(RevenueLog.netto_cents),
        func.sum(RevenueLog.ust_cents),
        func.sum(RevenueLog.brutto_cents),
    ).filter(
        RevenueLog.paid_at >= start,
        RevenueLog.paid_at < end,
        RevenueLog.tax_treatment == treatment,
    ).one()
    return (_cents_to_eur(rows[0]), _cents_to_eur(rows[1]), _cents_to_eur(rows[2]))


def _sum_provider(db, start, end, provider: str) -> float:
    from database.models import ApiCostLog
    v = db.query(func.sum(ApiCostLog.cost_eur)).filter(
        ApiCostLog.created_at >= start,
        ApiCostLog.created_at < end,
        ApiCostLog.provider == provider,
    ).scalar()
    return float(v or 0)


def compute_eur(start: date, end: date, db, home_days: int = 0) -> dict:
    """Berechnet EUeR fuer Zeitraum [start, end)."""
    from database.models import FixedCost

    # --- A. Einnahmen ---
    de_netto, de_ust, de_brutto = _sum_treatment(db, start, end, 'DE_19')
    eu_netto, _eu_ust, eu_brutto = _sum_treatment(db, start, end, 'EU_RC')
    dl_netto, _dl_ust, dl_brutto = _sum_treatment(db, start, end, 'DRITTLAND')

    # --- B. Ausgaben: Fremdleistungen Z26 ---
    anthropic_netto = round(_sum_provider(db, start, end, 'anthropic'), 2)
    deepgram_netto  = round(_sum_provider(db, start, end, 'deepgram'), 2)
    eleven_netto    = round(_sum_provider(db, start, end, 'elevenlabs'), 2)
    stripe_netto    = round(_sum_provider(db, start, end, 'stripe'), 2)

    z26_total = round(anthropic_netto + deepgram_netto + eleven_netto, 2)
    z26_items = [
        {'provider': 'anthropic',  'netto': anthropic_netto},
        {'provider': 'deepgram',   'netto': deepgram_netto},
        {'provider': 'elevenlabs', 'netto': eleven_netto},
    ]

    # --- C. FixedCost nach eur_line ---
    fc_by_line = {52: [], 57: [], 65: []}
    inland_vst = 0.0
    for fc in db.query(FixedCost).filter(FixedCost.active.is_(True)).all():
        amt = float(fc.amount_eur)
        if fc.cycle == 'monthly':
            period_cost = amt
        elif fc.cycle == 'yearly':
            period_cost = amt / 12.0
        elif fc.cycle == 'per_day':
            period_cost = amt * home_days
        else:
            period_cost = 0
        line = fc.eur_line or 57
        if line not in fc_by_line:
            fc_by_line[line] = []
        fc_by_line[line].append({
            'name': fc.name, 'netto': round(period_cost, 2),
            'skr03': fc.skr03, 'vat_rate': float(fc.vat_rate or 0),
        })
        inland_vst += period_cost * float(fc.vat_rate or 0) / 100.0

    # Stripe-Gebuehren -> Z57 Nebenkosten Geldverkehr (NICHT §13b)
    if stripe_netto > 0:
        fc_by_line.setdefault(57, []).append({
            'name': 'Stripe Gebuehren', 'netto': stripe_netto,
            'skr03': '4970', 'vat_rate': 19.0,
        })
        inland_vst += stripe_netto * 0.19

    z52_total = round(sum(i['netto'] for i in fc_by_line.get(52, [])), 2)
    z57_total = round(sum(i['netto'] for i in fc_by_line.get(57, [])), 2)
    z65_total = round(sum(i['netto'] for i in fc_by_line.get(65, [])), 2)

    summe_ausgaben_netto = round(z26_total + z52_total + z57_total + z65_total, 2)

    # --- D. §13b Reverse Charge ---
    kz84_basis = round(anthropic_netto + deepgram_netto + eleven_netto, 2)
    kz85_ust = round(kz84_basis * 0.19, 2)
    kz67_vst = kz85_ust  # identisch per §13b — harter Invariant

    inland_vst_r = round(inland_vst, 2)
    z72_vst_total = round(inland_vst_r + kz67_vst, 2)

    # --- E. Gesamt ---
    summe_einnahmen_netto = round(de_netto + eu_netto + dl_netto, 2)
    z77_gewinn = round(summe_einnahmen_netto - summe_ausgaben_netto, 2)

    ust_zahllast = round((de_ust + kz85_ust) - (inland_vst_r + kz67_vst), 2)
    gewinn_nach_ust = round(z77_gewinn - ust_zahllast, 2)

    return {
        'period': {
            'start': start.isoformat(),
            'end':   end.isoformat(),
        },
        'einnahmen': {
            'Z14_de_19':       {'netto': de_netto, 'ust': de_ust, 'brutto': de_brutto},
            'Z16_eu_rc':       {'netto': eu_netto, 'ust': 0, 'brutto': eu_brutto},
            'Z17_drittland':   {'netto': dl_netto, 'ust': 0, 'brutto': dl_brutto},
            'Z19_vereinnahmte_ust': de_ust,
            'summe_einnahmen_netto': summe_einnahmen_netto,
        },
        'ausgaben': {
            'Z26_fremdleistungen': {'total_netto': z26_total, 'items': z26_items},
            'Z52_miete_edv':       {'total_netto': z52_total, 'items': fc_by_line.get(52, [])},
            'Z57_uebrige':         {'total_netto': z57_total, 'items': fc_by_line.get(57, [])},
            'Z65_homeoffice':      {'total_netto': z65_total, 'items': fc_by_line.get(65, [])},
            'summe_ausgaben_netto': summe_ausgaben_netto,
            'Z72_vorsteuer': {
                'inland_vst': inland_vst_r,
                'rc_13b_vst': kz67_vst,
                'total':      z72_vst_total,
            },
            'Z75_summe_ausgaben': summe_ausgaben_netto,
        },
        'ergebnis': {
            'Z77_gewinn_vor_steuern': z77_gewinn,
            'ust_zahllast': ust_zahllast,
            'gewinn_nach_ust': gewinn_nach_ust,
        },
        'ust_voranmeldung': {
            'KZ81_steuerpfl_19': {'basis': de_netto, 'ust': de_ust},
            'KZ21_igL':         eu_netto,
            'KZ45_drittland':   dl_netto,
            'KZ84_rc_bemessung': kz84_basis,
            'KZ85_rc_ust':      kz85_ust,
            'KZ66_vst_inland':  inland_vst_r,
            'KZ67_vst_rc':      kz67_vst,
            'zahllast':         ust_zahllast,
        },
    }
