"""Phase 04.7.2 — API Cost Tracker.

Pattern: nicht-blockierend. Schreibt api_cost_log mit eingefrorenem Wechselkurs
und gefrorener ApiRate. Darf NIEMALS raisen — API-Calls duerfen nie wegen
Logging-Fehler crashen (Referenz: _write_ft_assistant_event aus Phase 04.7.1).

D-02: Wechselkurs + rate_applied werden beim Schreiben eingefroren.
Nachtraegliche Kursaenderungen veraendern keine bestehenden Buchungen.
"""
from __future__ import annotations
from decimal import Decimal


def normalize_model_name(model: str | None) -> str:
    """Phase 08.23.2.KOSTEN-1 R2 — EINE Namens-Normalisierung fuer die Kosten-Hooks.

    Konsolidierung, KEIN neues System: dieses Idiom stand als Einzeiler verstreut in
    coaching_service.py:92/:326, precall_service.py und qa_pipeline.py:

        _cost_model = 'sonnet-4-5' if 'sonnet' in config.MODEL_X else 'haiku-4-5'

    Verhalten ist bewusst WORTGLEICH uebernommen (keine stille Semantik-Aenderung): alles mit
    'sonnet' im Namen wird auf den Kurznamen 'sonnet-4-5' abgebildet, alles andere auf
    'haiku-4-5'. Beide Kurznamen haben aktive Raten (KOSTEN-1 R1, app._API_RATE_SOLL).

    ★ Die BESTANDS-Sites werden hier NICHT umgeschrieben (Fable-Gegencheck 2026-07-20,
      Abweichung 3): ein Sweep-Refactor waere Beifang im Fix-Block. Nur die NEUEN Hooks
      nutzen diese Funktion; die alten Einzeiler bleiben, wo sie sind.

    ⚠ Grenze, bewusst so: die Funktion RAET nicht nach Versionen. Ein kuenftiges 'opus'- oder
    'haiku-5'-Modell landete stumm auf 'haiku-4-5' und damit auf einem falschen Preis. Der
    Laufzeit-Skip-Zaehler aus W3 (Plan 04) faengt das nicht — er sieht nur FEHLENDE Raten, nicht
    falsch zugeordnete. Wer ein neues Modell einfuehrt, pflegt hier UND in _API_RATE_SOLL nach.
    """
    return 'sonnet-4-5' if 'sonnet' in (model or '') else 'haiku-4-5'


def resolve_org_id_from_user(db, user_id: int | None) -> int | None:
    """Phase 08.23.2.KOSTEN-1 R2 — org_id ueber den User aufloesen (Nachlauf-Kontext).

    Die Post-Call-Runner (Judge, Adoption) bekommen ein `call`-Objekt. `calls` traegt
    `user_id` (Integer, NOT NULL) und `tenant_id` (UUID) — aber KEINE `org_id`, waehrend
    `api_cost_log.org_id` ein Integer-FK auf `organisations.id` ist (Punkt 21: die Namen
    sehen verwandt aus, die Schichten sind es nicht). Ohne diese Aufloesung blieben die
    teuersten Zeilen (zwei Sonnet-Laeufe pro Call) org-los und faenden im
    Kunden-Deckungsbeitrag (`compute_org_profitability`) nicht statt.

    Laeuft auf der Session des Aufrufers (Nachlauf, kein Live-Pfad, Punkt 25 unkritisch).
    Fehlschlag ist nie fatal: None -> die Zeile wird trotzdem geschrieben, nur ohne Org.
    """
    if not user_id:
        return None
    try:
        from database.models import User
        return db.query(User.org_id).filter(User.id == user_id).scalar()
    except Exception as e:
        print(f"[CostTracker] org_id-Aufloesung fuer user={user_id} fehlgeschlagen: {e}")
        return None


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


def _resolve_user_id_from_live_session(sid: str | None = None) -> int | None:
    """Liest user_id GEZIELT aus der per-SID-Session `sid` (Background-Thread-Kontext:
    analyse_loop, Deepgram-Close — kein Flask g.user verfuegbar).

    Phase 08.23.2.TAXO1-03 (B-B Interlock — Option 2): der frühere
    `for _st in _session_state.values(): return`-First-Session-Scan ist GELOESCHT.
    Er lieferte bei mehreren parallelen Calls die ERSTE BELIEBIGE Session →
    Call B's Kosten landeten unter Call A's user_id (Cross-Tenant-Kosten-Leak).
    Jetzt: ohne sid -> None (KEIN Raten; besser NULL als Fehlzuordnung;
    Multi-Tenancy-Integritaet > Vollstaendigkeit). Mit sid -> gezielte Lesung."""
    if not sid:
        return None
    try:
        import services.live_session as ls
        with ls._session_state_lock:
            _st = ls._session_state.get(sid)
            return _st.get('user_id') if _st else None
    except Exception:
        return None


def _resolve_org_id_from_live_session(sid: str | None = None) -> int | None:
    """Liest org_id GEZIELT aus der per-SID-Session `sid`.

    Phase 08.23.2.TAXO1-03 (B-B Interlock — Option 2): values()-First-Session-Scan
    GELOESCHT (siehe _resolve_user_id_from_live_session). Ohne sid -> None."""
    if not sid:
        return None
    try:
        import services.live_session as ls
        with ls._session_state_lock:
            _st = ls._session_state.get(sid)
            return _st.get('org_id') if _st else None
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
    latency_ms: int | None = None,    # NEU: Phase 08.13
    call_site: str | None = None,     # NEU: Phase 08.13
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

        # Phase 08.23.2.TAXO1-03 (B-B): session_id an die Resolver durchreichen, damit
        # selbst ein Aufrufer der NUR session_id (nicht user_id/org_id) mitgibt die
        # KORREKTE Session trifft statt einer geratenen. Ohne session_id -> Resolver None.
        if user_id is None:
            user_id = _resolve_user_id_from_live_session(session_id)
        if org_id is None:
            org_id = _resolve_org_id_from_live_session(session_id)

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
                latency_ms=latency_ms,    # NEU: Phase 08.13
                call_site=call_site,      # NEU: Phase 08.13
            ))
            db.commit()
        finally:
            try:
                db.close()
            except Exception:
                pass
    except Exception as e:
        print(f"[CostTracker] log_api_cost failed ({provider}/{model}): {e}")
