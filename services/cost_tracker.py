"""Phase 04.7.2 — API Cost Tracker.

Pattern: nicht-blockierend. Schreibt api_cost_log mit eingefrorenem Wechselkurs
und gefrorener ApiRate. Darf NIEMALS raisen — API-Calls duerfen nie wegen
Logging-Fehler crashen (Referenz: _write_ft_assistant_event aus Phase 04.7.1).

D-02: Wechselkurs + rate_applied werden beim Schreiben eingefroren.
Nachtraegliche Kursaenderungen veraendern keine bestehenden Buchungen.
"""
from __future__ import annotations
from decimal import Decimal


def _get_current_fx_rate(db, rate_currency: str) -> Decimal:
    """Liest den neuesten Kurs aus exchange_rates. Fallback 0.92 fuer USD_EUR."""
    if rate_currency == 'EUR':
        return Decimal('1.0')
    try:
        from database.models import ExchangeRate
        row = (db.query(ExchangeRate)
                 .filter_by(currency_pair=f'{rate_currency}_EUR')
                 .order_by(ExchangeRate.date.desc())
                 .first())
        if row and row.rate is not None:
            return Decimal(str(row.rate))
    except Exception:
        pass
    return Decimal('0.92')


def _resolve_user_id_from_live_session() -> int | None:
    """Liest user_id aus live_session.state fuer Background-Thread-Kontexte
    (analyse_loop, Deepgram-Close) wo kein Flask g.user verfuegbar ist."""
    try:
        import services.live_session as ls
        with ls.state_lock:
            return ls.state.get('user_id')
    except Exception:
        return None


def _resolve_org_id_from_live_session() -> int | None:
    try:
        import services.live_session as ls
        with ls.state_lock:
            return ls.state.get('org_id')
    except Exception:
        return None


def log_api_cost(
    provider: str,
    model: str,
    user_id: int | None,
    units: float,
    unit_type: str,
    *,
    org_id: int | None = None,
    session_id: str | None = None,
    context_tag: str | None = None,
) -> None:
    """Schreibt api_cost_log Eintrag. Darf NIEMALS raisen.

    Args:
        provider: 'anthropic' | 'deepgram' | 'elevenlabs' | 'stripe'
        model: z.B. 'haiku-4-5', 'nova-2', 'multilingual-v2'
        user_id: User-ID oder None (wird dann aus live_session.state gelesen)
        units: Anzahl Einheiten (tokens/1000, Minuten, chars/1000)
        unit_type: muss zu ApiRate.unit_type matchen
        org_id, session_id, context_tag: optional
    """
    try:
        import database.db as _db_mod
        from database.models import ApiCostLog, ApiRate

        if user_id is None:
            user_id = _resolve_user_id_from_live_session()
        if org_id is None:
            org_id = _resolve_org_id_from_live_session()

        db = _db_mod.SessionLocal()
        try:
            rate = (db.query(ApiRate)
                      .filter_by(provider=provider, model=model,
                                 unit_type=unit_type, active=True)
                      .first())
            if not rate:
                print(f"[CostTracker] no active ApiRate for "
                      f"{provider}/{model}/{unit_type} — skipping log")
                return

            rate_currency = rate.currency or 'USD'
            fx_rate = _get_current_fx_rate(db, rate_currency)
            units_d = Decimal(str(units))
            rate_d = Decimal(str(rate.price_per_unit))
            cost_eur = (units_d * rate_d * fx_rate).quantize(Decimal('0.000001'))

            db.add(ApiCostLog(
                provider=provider,
                model=model,
                user_id=user_id,
                org_id=org_id,
                units=units_d,
                unit_type=unit_type,
                rate_applied=rate_d,
                rate_currency=rate_currency,
                fx_rate_applied=fx_rate,
                cost_eur=cost_eur,
                session_id=session_id,
                context_tag=context_tag,
            ))
            db.commit()
        finally:
            try:
                db.close()
            except Exception:
                pass
    except Exception as e:
        print(f"[CostTracker] log_api_cost failed ({provider}/{model}): {e}")
