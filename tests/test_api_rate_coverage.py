"""Phase 08.23.2.KOSTEN-1 Welle 1 — W1 Rate-Coverage-Waechter (real-PG, ERST-ROT).

WOFUER: `cost_tracker.log_api_cost` verwirft **still**, wenn fuer das geloggte Tripel
(provider, model, unit_type) keine aktive `ApiRate` existiert (`cost_tracker.py:109-112`).
Genau so ist die Live-Spracherkennung seit Ende April unsichtbar geworden: der Hook loggt
`nova-3`, die Preis-Tabelle kannte nur `nova-2`.

WAS DIESER WAECHTER TUT: er sammelt jedes Tripel, das im Repo tatsaechlich geloggt wird, und
verlangt dafuer eine aktive `ApiRate` in der (geseedeten) Datenbank. Fehlt eine -> ROT, mit der
vollstaendigen Liste der fehlenden Tripel.

BEWUSSTE GRENZEN (Fable/Gemini, verbindlich — NICHT "verbessern"):
- **Literal-/Listen-Granularitaet, KEIN AST-Parsing.** Funktions-genaues Matching waere der
  Stolperdraht-Verstoss aus dem Bauplan. Zwei Quellen: (1) String-Literale aus dem Repo,
  (2) die explizite, kommentierte Liste NICHT-literaler Modellnamen unten.
- **Der Blindfleck ist bekannt und beabsichtigt:** Modellnamen, die zur Laufzeit aus ENV/Config
  entstehen, kann ein Literal-Sweep grundsaetzlich nicht vollstaendig sehen. Die Liste unten deckt
  die heute bekannten Faelle ab; alles darueber hinaus faengt **W3** (Laufzeit-Skip-Zaehler,
  `tests/test_cost_skip_counter.py` + Founder-Alarm) im Moment des Auftretens.
  W1/W2 fangen zur Deploy-Zeit, W3 zur Laufzeit. Zusammen dicht.
- **real-PG-only.** Ohne `TEST_DATABASE_URL` wird geSKIPPT statt gruen gemeldet — ein blind-gruener
  Check ist gefaehrlicher als gar keiner (PGTEST-Lehre).

Dieser Test ist ERST-ROT gebaut: gegen den Stand vor R1 meldet er mindestens
`deepgram/nova-3/per_minute` und `anthropic/claude-sonnet-4-5/*` als rate-los.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCAN_DIRS = ('services', 'routes', 'nerve_rt')

# Ein log_api_cost-Aufruf beginnt mit zwei String-Literalen (provider, model); der unit_type
# folgt als Keyword irgendwo in denselben paar Zeilen. Bewusst simpel gehalten (kein AST).
_CALL_RE = re.compile(r"log_api_cost\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]")
_UNIT_RE = re.compile(r"unit_type\s*=\s*['\"]([^'\"]+)['\"]")
_CALL_WINDOW = 400  # Zeichen nach dem Call-Anfang, in denen unit_type stehen muss


def _known_non_literal_triples() -> set[tuple[str, str, str]]:
    """Die EXPLIZITE, kommentierte Liste der Sites, deren Modellname KEIN String-Literal ist.

    Jede Zeile ist eine bewusste Pflege-Entscheidung. Waechst diese Liste unkontrolliert, ist das
    das Signal, dass die Modellnamen-Aufloesung selbst aufgeraeumt gehoert — NICHT dass hier ein
    AST-Parser hinsoll.
    """
    import config

    def _norm(model: str) -> str:
        """Spiegelt das BESTEHENDE _cost_model-Idiom (coaching_service.py:92) wortgleich.

        Bewusst hier lokal statt Import aus cost_tracker: dieser Waechter muss gegen den
        UNGEFIXTEN Stand rot werden koennen — ein Import auf noch nicht gebauten Code waere
        ein ImportError (rot aus dem FALSCHEN Grund) statt eines echten Befunds.
        Plan 02 baut `normalize_model_name()` mit exakt diesem Verhalten; weicht es ab,
        faellt genau das hier auf.
        """
        return 'sonnet-4-5' if 'sonnet' in (model or '') else 'haiku-4-5'

    token_units = (
        'per_1k_input_tokens',
        'per_1k_output_tokens',
        'per_1k_cache_read_tokens',
        'per_1k_cache_write_tokens',
    )

    triples: set[tuple[str, str, str]] = set()

    def _add_tokens(model: str) -> None:
        for unit in token_units:
            triples.add(('anthropic', model, unit))

    # claude_service.py:626/693-707 — _model_autovar = config.MODEL_PIP_AUTOVAR.
    # Genau dieser Name (heute 'claude-sonnet-4-5', OHNE Datum) wird roh geloggt.
    # Fund F-1 der Phase: dafuer existierte auf Prod GAR KEINE Rate -> zweites stilles Loch.
    _add_tokens(config.MODEL_PIP_AUTOVAR)

    # judge_runner.py:38 / adoption_runner.py:39 — MODEL_JUDGE / MODEL_ADOPTION defaulten auf
    # config.MODEL_POSTCALL_ANALYSIS. Beide Hooks loggen normalisiert.
    _add_tokens(_norm(os.getenv('MODEL_JUDGE', config.MODEL_POSTCALL_ANALYSIS)))
    _add_tokens(_norm(os.getenv('MODEL_ADOPTION', config.MODEL_POSTCALL_ANALYSIS)))

    # outcome_service.py:28-31 / routes/training.py:962 / coaching_service.py:148 —
    # config-getriebene Haiku-Pfade, ueber die Normalisierung geloggt.
    _add_tokens(_norm(config.MODEL_TRAINING_PREVIEW))
    _add_tokens(_norm(config.MODEL_VALIDATE_USER_TEXT))
    _add_tokens(_norm(config.MODEL_ANALYSE))

    # coaching_service.py:92 / precall_service.py / qa_pipeline.py — das bestehende
    # _cost_model-Idiom loest auf genau diese beiden Kurznamen auf.
    _add_tokens('sonnet-4-5')
    _add_tokens('haiku-4-5')

    return triples


def _literal_triples() -> set[tuple[str, str, str]]:
    """Alle (provider, model, unit_type) aus String-Literalen im Produktiv-Code."""
    found: set[tuple[str, str, str]] = set()
    for rel in SCAN_DIRS:
        base = REPO_ROOT / rel
        if not base.is_dir():
            continue
        for path in base.rglob('*.py'):
            try:
                src = path.read_text(encoding='utf-8')
            except OSError:  # pragma: no cover - defensiv
                continue
            for match in _CALL_RE.finditer(src):
                provider, model = match.group(1), match.group(2)
                window = src[match.start():match.start() + _CALL_WINDOW]
                unit = _UNIT_RE.search(window)
                if unit:
                    found.add((provider, model, unit.group(1)))
    return found


def test_every_logged_triple_has_an_active_rate(db_session):
    """Fuer JEDES geloggte (provider, model, unit_type) muss eine aktive ApiRate existieren."""
    from database.models import ApiRate

    expected = _literal_triples() | _known_non_literal_triples()
    assert expected, (
        "Der Waechter hat GAR KEINE log_api_cost-Tripel gefunden — das ist selbst ein Defekt "
        "(Scan kaputt oder Verzeichnisse verschoben), kein Erfolg."
    )

    active = {
        (r.provider, r.model, r.unit_type)
        for r in db_session.query(ApiRate).filter_by(active=True).all()
    }

    missing = sorted(expected - active)
    assert not missing, (
        "Kosten werden STILL verworfen — fuer diese geloggten Tripel gibt es keine aktive ApiRate "
        "(cost_tracker.py:109-112 skippt sie):\n  "
        + "\n  ".join(f"{p}/{m}/{u}" for p, m, u in missing)
        + "\n\nFix: Rate in die Seed-Liste in app.py aufnehmen (KOSTEN-1 R1) — keine Rate-Sync-Engine."
    )


def test_nova3_rate_exists(db_session):
    """Regressions-Nagel auf das konkrete Leck dieser Phase.

    Die Live-Spracherkennung loggt 'nova-3' (deepgram_service.py:497). Fehlte diese eine Rate,
    war die minuten-getriebene HAUPT-Kostenposition unsichtbar. Eigener Test, damit der Befund
    beim Lesen des Reports sofort ins Auge springt statt in einer Sammelliste unterzugehen.
    """
    from database.models import ApiRate

    row = (db_session.query(ApiRate)
           .filter_by(provider='deepgram', model='nova-3',
                      unit_type='per_minute', active=True)
           .first())
    assert row is not None, (
        "deepgram/nova-3/per_minute hat KEINE aktive Rate — die Live-STT-Kosten werden still "
        "verworfen (das Leck, das KOSTEN-1 schliesst)."
    )
    assert float(row.price_per_unit) > 0, "nova-3-Rate existiert, ist aber 0 — das loggt 0-Kosten."
