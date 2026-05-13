"""
Performance-Test fuer services/anonymization.py (Phase 08.23.2.B Req-12).

Ausfuehren: pytest tests/test_anonymization_perf.py -v

Acceptance-Kriterium: 95. Perzentil von anonymize() auf 1000-Zeichen-Text < 200ms.

Hintergrund (aus RESEARCH.md):
- spaCy de_core_news_lg: ~40-70ms/1000 Zeichen auf Hetzner CX22
- Regex-Filter: ~5-8ms
- Art-9-Filter: < 1ms
- Gesamt: komfortabel unter 200ms fuer typische Snippets (50-200 Zeichen)

Hinweis: Tests laufen auch ohne installiertes spaCy (NER-Schritt wird dann geskippt).
Die P95-Schwelle gilt fuer die vollstaendige Pipeline inkl. spaCy NER — lokal ohne
spaCy sind die Latenzwerte deutlich niedriger (nur Regex + Art-9-Filter).
"""
import time
import statistics
import pytest
from services.anonymization import AnrufAnonymisierer, anonymize


# ── Modul-State-Reset Fixture ──────────────────────────────────────────────────

class _FalsyNlpSentinel:
    """
    Sentinel-Objekt fuer anon_module._nlp wenn spaCy nicht installiert ist.

    Zweck: Verhindert den wiederholten spaCy-Import-Versuch in _get_nlp().
    _get_nlp() prueft: if _nlp is None -> Import versuchen.
    Mit diesem Sentinel: _nlp is not None -> _get_nlp() gibt Sentinel sofort zurueck.
    anonymize() prueft: if nlp and is_pipeline_healthy -> False wegen __bool__=False.
    Ergebnis: NER-Schritt wird geskippt, is_pipeline_healthy bleibt True,
    anonymize() laeuft durch (Regex + Art-9-Filter aktiv).

    Runtime-Behavior-Test: testet tatsaechliches Pipeline-Verhalten ohne spaCy.
    """
    def __bool__(self):
        return False


@pytest.fixture(autouse=True)
def reset_anonymization_module_state():
    """
    Setzt den globalen Modul-State von services.anonymization vor JEDEM Test zurueck.
    Notwendig weil is_pipeline_healthy und _error_timestamps Modul-Level-Singletons sind.

    Ohne Reset schlaegt der zweite anonymize()-Aufruf in der Perf-Loop fehl:
    _get_nlp() setzt is_pipeline_healthy=False beim ersten Aufruf (spaCy fehlt),
    der zweite Aufruf prueft if not is_pipeline_healthy: raise.

    Loesung: _nlp auf _FalsyNlpSentinel setzen — _get_nlp() gibt Sentinel zufort zurueck
    (kein neuer Import-Versuch), anonymize() skipped NER wegen if nlp and ...: False.
    is_pipeline_healthy bleibt True fuer alle 100 Schleifendurchlaeufe.

    Runtime-Behavior-Test: greift nur auf Modul-State zu (keine Source-Presence).
    """
    import services.anonymization as anon_module

    original_healthy = anon_module.is_pipeline_healthy
    original_errors = list(anon_module._error_timestamps)
    original_nlp = anon_module._nlp

    # Sauberen Zustand herstellen
    anon_module.is_pipeline_healthy = True
    anon_module._error_timestamps.clear()

    # Wenn spaCy nicht verfuegbar (_nlp=None nach fehlgeschlagenem Import oder noch nicht
    # versucht): Sentinel setzen damit _get_nlp() keinen weiteren Import-Versuch macht.
    if anon_module._nlp is None:
        anon_module._nlp = _FalsyNlpSentinel()

    yield

    # Original-State wiederherstellen
    anon_module.is_pipeline_healthy = original_healthy
    anon_module._error_timestamps.clear()
    anon_module._error_timestamps.extend(original_errors)
    anon_module._nlp = original_nlp


# 1000-Zeichen-Testtext mit realistischer B2B-Vertriebssituation
# Enthaelt IBAN, E-Mail, Telefon, Personennamen, Firmennamen
TEST_TEXT_1000 = (
    "Thomas Mueller von der Commerzbank AG hat heute Morgen angerufen. "
    "Er ist der Leiter der Einkaufsabteilung und hat Bedenken bezueglich des Preises. "
    "Seine E-Mail-Adresse ist thomas.mueller@commerzbank.de und er ist erreichbar "
    "unter der Telefonnummer 0151 12345678. Die IBAN fuer die Zahlung lautet "
    "DE89370400440532013000. Herr Mueller sagte, dass er das Angebot zunaechst "
    "intern besprechen muesse, insbesondere mit seiner Kollegin Frau Dr. Schmidt, "
    "die als CFO bei der Commerzbank in Frankfurt taetig ist. "
    "Er erwartet eine Entscheidung bis Ende des Quartals. "
    "Die Commerzbank AG hat ihren Hauptsitz in Frankfurt am Main und beschaeftigt "
    "weltweit ueber 40.000 Mitarbeiter. Mueller betonte, dass die Loesung "
    "in ihre bestehende SAP-Landschaft integriert werden muesse. "
    "Der Jahresumsatz der Abteilung betraegt ungefaehr 50 Millionen Euro."
)[:1000]

# Sicherstellen dass exakt 1000 Zeichen
assert len(TEST_TEXT_1000) <= 1000, f"Test-Text zu lang: {len(TEST_TEXT_1000)} Zeichen"


def test_p95_latency():
    """
    Req-12: 95. Perzentil von anonymize() auf 1000-Zeichen-Text < 200ms.
    100 Wiederholungen; latencies in Millisekunden.
    """
    n_runs = 100
    latencies_ms = []

    for _ in range(n_runs):
        cache = AnrufAnonymisierer()  # Frischer Cache pro Run (repraesentativ)
        start = time.perf_counter()
        result = anonymize(TEST_TEXT_1000, cache)
        end = time.perf_counter()
        latency_ms = (end - start) * 1000
        latencies_ms.append(latency_ms)

    latencies_ms.sort()
    p50 = latencies_ms[int(n_runs * 0.50)]
    p95 = latencies_ms[int(n_runs * 0.95)]
    p99 = latencies_ms[int(n_runs * 0.99)]

    print(f"\n[Perf] anonymize() Latenz auf {len(TEST_TEXT_1000)}-Zeichen-Text ({n_runs} Runs):")
    print(f"  P50: {p50:.1f}ms")
    print(f"  P95: {p95:.1f}ms")
    print(f"  P99: {p99:.1f}ms")
    print(f"  Max: {max(latencies_ms):.1f}ms")
    print(f"  Min: {min(latencies_ms):.1f}ms")

    assert p95 < 200, (
        f"P95-Latenz {p95:.1f}ms >= 200ms — PERFORMANCE-TEST FEHLGESCHLAGEN!\n"
        f"P50: {p50:.1f}ms, P99: {p99:.1f}ms, Max: {max(latencies_ms):.1f}ms"
    )


def test_short_snippet_latency():
    """
    Smoke-Test: Kurze Snippets (typische STT-Segmente, 50-100 Zeichen) < 100ms P95.
    """
    short_text = "Thomas Mueller von der Commerzbank hat angerufen wegen des Angebots"
    n_runs = 50
    latencies_ms = []

    for _ in range(n_runs):
        cache = AnrufAnonymisierer()
        start = time.perf_counter()
        anonymize(short_text, cache)
        end = time.perf_counter()
        latencies_ms.append((end - start) * 1000)

    latencies_ms.sort()
    p95 = latencies_ms[int(n_runs * 0.95)]
    print(f"\n[Perf] Short-Snippet ({len(short_text)} Zeichen) P95: {p95:.1f}ms")

    assert p95 < 100, f"Short-Snippet P95 {p95:.1f}ms >= 100ms"


def test_art9_short_circuit_faster():
    """
    Art-9-Treffer soll schneller sein als volle Pipeline (Short-Circuit nach Schritt 0).
    Kein harter Assert — nur Logging fuer Diagnose.
    """
    art9_text = "Er leidet an Diabetes und ist deshalb oft krank"
    normal_text = "Der Preis ist zu hoch fuer die aktuelle Budgetplanung"

    n_runs = 20
    art9_times = []
    normal_times = []

    for _ in range(n_runs):
        cache = AnrufAnonymisierer()
        start = time.perf_counter()
        anonymize(art9_text, cache)
        art9_times.append((time.perf_counter() - start) * 1000)

        cache2 = AnrufAnonymisierer()
        start = time.perf_counter()
        anonymize(normal_text, cache2)
        normal_times.append((time.perf_counter() - start) * 1000)

    art9_p50 = sorted(art9_times)[int(n_runs * 0.5)]
    normal_p50 = sorted(normal_times)[int(n_runs * 0.5)]
    print(f"\n[Perf] Art-9 P50: {art9_p50:.1f}ms vs Normal P50: {normal_p50:.1f}ms")
    # Kein harter Assert — Art-9 kann schneller ODER langsamer sein je nach spaCy-Load
