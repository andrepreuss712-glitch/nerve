"""Phase 08.23.2.MESSGERAETE-1 Plan 03 — Tests fuer den Leser der Live-KI-Messung.

Prueft die Rechnung und den Split, nicht die Abfrage — ob die SQLAlchemy-Filter die richtigen
Zeilen liefern, beweist erst die Abnahme an echten Prod-Daten (D-06, Plan 04).

Deterministisch, ohne DB und ohne App-Kontext: `_perzentil` und `_aggregiere_kosten_nach_tag`
sind reine Funktionen und bekommen ihre Zeilen als einfache Tupel-Listen gereicht — genau in
der Form, in der `db.query(...).all()` sie liefern wuerde.

Bewusst OHNE die Marker "live" und "perf": das Deploy-Tor faehrt mit `-m "not live and not perf"`
und waere fuer diese Datei sonst blind.
"""
from routes.admin_dashboard import (
    _perzentil,
    _aggregiere_kosten_nach_tag,
    _OHNE_HERKUNFT,
)

# Dauer-Schluessel, die es NUR in Tabelle 1 geben darf (Punkt 12).
_DAUER_FELDER = ('antworten', 'latenz_avg_ms', 'latenz_p50_ms', 'latenz_p95_ms', 'ttft_avg_ms')


def _nach_tag(liste):
    """Kleiner Helfer: Liste von Zeilen-Dicts nach context_tag greifbar machen."""
    return {r['context_tag']: r for r in liste}


# ── _perzentil ────────────────────────────────────────────────────────────────────────

def test_perzentil_p50():
    assert _perzentil([10, 20, 30, 40], 0.5) == 20


def test_perzentil_p95():
    assert _perzentil([10, 20, 30, 40], 0.95) == 40


def test_perzentil_leer_ist_none():
    # Kein ZeroDivisionError, kein Absturz: eine Sorte ohne jede Messung ist der Normalfall
    # (Cache-Tags, dormante Pfade) und darf die ganze Ansicht nicht kippen.
    assert _perzentil([], 0.5) is None


def test_perzentil_einzelwert():
    assert _perzentil([42], 0.95) == 42


# ── _aggregiere_kosten_nach_tag ───────────────────────────────────────────────────────

def test_eine_antwort_zaehlt_einmal():
    """D-07: vier Buchungen EINER API-Antwort, aber nur die input-Zeile traegt latency_ms."""
    summen = [('live_haiku_merged', 4, 0.0041)]          # input + output + cache-read + cache-write
    latenzen = [('live_haiku_merged', 850, None)]        # nur die input-Buchung
    live_ki, uebrige = _aggregiere_kosten_nach_tag(summen, latenzen)
    zeile = _nach_tag(live_ki)['live_haiku_merged']
    assert zeile['buchungen'] == 4
    assert zeile['antworten'] == 1
    assert zeile['latenz_avg_ms'] == 850
    assert zeile['latenz_p50_ms'] == 850
    assert zeile['latenz_p95_ms'] == 850
    assert uebrige == []


def test_sorte_ohne_dauer_verschwindet_nicht():
    """Eine Live-Sorte nur mit Cache-/Output-Zeilen bleibt sichtbar — mit Strichen statt Zahlen."""
    summen = [('coaching_haiku', 3, 0.0019)]
    live_ki, _ = _aggregiere_kosten_nach_tag(summen, [])
    zeile = _nach_tag(live_ki)['coaching_haiku']
    assert zeile['buchungen'] == 3
    assert zeile['antworten'] == 0
    assert zeile['latenz_avg_ms'] is None
    assert zeile['latenz_p50_ms'] is None
    assert zeile['latenz_p95_ms'] is None
    assert zeile['ttft_avg_ms'] is None


def test_unbekannter_tag_faellt_in_tabelle_zwei():
    """Punkt 12: was nicht in LIVE_LLM_CONTEXT_TAGS steht, landet still in Tabelle 2 — ohne Dauer."""
    summen = [('stt', 120, 1.8400), ('stripe_fee', 7, 0.9100)]
    live_ki, uebrige = _aggregiere_kosten_nach_tag(summen, [])
    assert live_ki == []
    tags = _nach_tag(uebrige)
    assert set(tags) == {'stt', 'stripe_fee'}
    for zeile in uebrige:
        for feld in _DAUER_FELDER:
            assert feld not in zeile


def test_cache_tags_sind_tabelle_eins_mit_flag():
    """Die Cache-Tags gehoeren zur Live-KI-Tabelle, haben aber nie eine eigene API-Antwort."""
    summen = [('analyse', 20, 0.0300), ('ewb', 12, 0.0100)]
    live_ki, uebrige = _aggregiere_kosten_nach_tag(summen, [])
    assert uebrige == []
    tags = _nach_tag(live_ki)
    assert set(tags) == {'analyse', 'ewb'}
    for zeile in live_ki:
        assert zeile['nur_cache'] is True
        assert zeile['antworten'] == 0


def test_ohne_context_tag_bekommt_label():
    """context_tag NULL bekommt ein Label statt zu verschwinden; beide Listen sortieren absteigend."""
    summen = [
        (None, 2, 0.0500),
        ('stt', 9, 1.2000),
        ('coaching_haiku', 3, 0.0019),
        ('live_haiku_merged', 4, 0.0041),
    ]
    live_ki, uebrige = _aggregiere_kosten_nach_tag(summen, [])
    tags = _nach_tag(uebrige)
    assert _OHNE_HERKUNFT in tags
    assert tags[_OHNE_HERKUNFT]['label'] == _OHNE_HERKUNFT
    assert [r['kosten_eur'] for r in uebrige] == sorted(
        (r['kosten_eur'] for r in uebrige), reverse=True)
    assert [r['kosten_eur'] for r in live_ki] == sorted(
        (r['kosten_eur'] for r in live_ki), reverse=True)
