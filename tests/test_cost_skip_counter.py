"""Phase 08.23.2.KOSTEN-1 Welle 3 — W3 Laufzeit-Skip-Zaehler (ERST-ROT).

WOFUER — Geminis staerkster Fund im Cross-Check: die beiden grep-Waechter W1/W2 greifen nur auf
String-Literale bzw. Aufruf-Muster. Unsere Modellnamen entstehen aber zur Laufzeit aus ENV-Variablen
(`config.MODEL_*` = `os.getenv`, `config.py:74-97`) und aus Modul-Locals (`MODEL_JUDGE`,
`MODEL_ADOPTION`). **Die sieht ein Datei-Sweep grundsaetzlich nicht.**

Der Laufzeit-Zaehler ist der robuste Fang: er zaehlt JEDEN stillen Skip in dem Moment, in dem er
passiert — egal wie der Modellname entstanden ist. W1/W2 fangen zur Deploy-Zeit, W3 zur Laufzeit.
Zusammen dicht. ★ Gelockte Andre-Entscheidung: W3 ist PFLICHT-Kernwaechter, nicht optional.

BEWUSSTE GRENZEN:
- Der Zaehler lebt im **Prozess-Speicher** und startet bei jedem Neustart bei 0 ("Skips seit
  Deploy") — das ist Absicht, keine Luecke. Wer Historie will, braucht eine eigene Tabelle: NICHT
  in dieser Phase.
- Jeder Prozess (nerve, nerve-rt, Worker) zaehlt fuer sich. Bewusste Grenze — es wird KEINE
  gemeinsame Zaehl-Infrastruktur gebaut (das waere das neue System, das der Bauplan verbietet).
- Er zaehlt **Konfigurations-Defekte**, niemals Nutzer-Daten (keine user_id, keine session_id).
"""
from __future__ import annotations

import pytest


def test_skip_increments_counter_with_offending_triple(db_session):
    """Ein Log auf ein Modell OHNE Rate muss den Zaehler erhoehen — mitsamt dem Tripel.

    Nur eine Gesamtsumme wuerde zeigen DASS etwas faellt, aber nicht WAS — und damit den Alarm
    im Founder-Dashboard wertlos machen.
    """
    from services import cost_tracker

    cost_tracker.reset_skip_counts()
    assert cost_tracker.get_skip_counts() == {}

    cost_tracker.log_api_cost(
        'anthropic', 'modell-das-es-nicht-gibt', None,
        units=1.0, unit_type='per_1k_input_tokens',
    )

    counts = cost_tracker.get_skip_counts()
    assert counts, "Der stille Skip wurde NICHT gezaehlt — genau das Loch, das W3 schliessen soll."
    key = 'anthropic/modell-das-es-nicht-gibt/per_1k_input_tokens'
    assert key in counts, f"Zaehler nennt das verletzende Tripel nicht: {counts}"
    assert counts[key] == 1

    # Zweiter Skip auf dasselbe Tripel zaehlt hoch, legt keinen zweiten Eintrag an.
    cost_tracker.log_api_cost(
        'anthropic', 'modell-das-es-nicht-gibt', None,
        units=1.0, unit_type='per_1k_input_tokens',
    )
    assert cost_tracker.get_skip_counts()[key] == 2


def test_successful_log_does_not_increment_counter(db_session):
    """Ein erfolgreicher Log darf den Alarm NICHT ausloesen — sonst ist er Rauschen.

    Soll-Zustand im Dashboard ist 0. Ein Zaehler, der bei Normalbetrieb hochlaeuft, wuerde genau
    die Aufmerksamkeit verbrennen, die den echten Defekt sichtbar machen soll.
    """
    from database.models import ApiRate
    from services import cost_tracker

    from database.models import ApiCostLog
    from tests.conftest import cleanup_rows

    rate = (db_session.query(ApiRate)
            .filter_by(active=True)
            .first())
    if rate is None:
        pytest.skip("keine aktive ApiRate in nerve_test — nichts zu buchen")

    cost_tracker.reset_skip_counts()
    cost_tracker.log_api_cost(
        rate.provider, rate.model, None,
        units=0.001, unit_type=rate.unit_type,
        context_tag='w3-selftest',
    )
    try:
        assert cost_tracker.get_skip_counts() == {}, (
            "Ein erfolgreicher Log hat den Skip-Zaehler erhoeht — der Alarm waere sofort unbrauchbar."
        )
    finally:
        # PGTEST-Cleanup-Regel: dieser Test committet eine echte api_cost_log-Zeile
        # (log_api_cost bringt seine EIGENE SessionLocal mit — der Rollback der Test-Session
        # raeumt sie deshalb NICHT weg). Ohne dieses Teardown waechst die Baseline mit jedem
        # Gate-Lauf und der Baseline-Waechter schlaegt zu Recht an.
        ids = [r.id for r in db_session.query(ApiCostLog)
               .filter(ApiCostLog.context_tag == 'w3-selftest').all()]
        if ids:
            cleanup_rows(db_session, {ApiCostLog: ids})


def test_counter_holds_no_user_data(db_session):
    """Punkt 28: der Zaehler ist prozess-global und darf deshalb NIE pro-Nutzer-Daten tragen."""
    from services import cost_tracker

    cost_tracker.reset_skip_counts()
    cost_tracker.log_api_cost(
        'anthropic', 'modell-das-es-nicht-gibt', 4711,
        units=1.0, unit_type='per_1k_input_tokens',
        org_id=42, session_id='geheime-sid',
    )
    blob = repr(cost_tracker.get_skip_counts())
    for leaked in ('4711', '42', 'geheime-sid'):
        assert leaked not in blob, (
            f"Der prozess-globale Skip-Zaehler traegt Nutzer-/Session-Daten ({leaked}) — "
            "Punkt-28-Verstoss (Cross-Tenant-Risiko im geteilten Zustand)."
        )
