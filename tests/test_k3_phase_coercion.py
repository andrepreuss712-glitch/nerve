"""Phase 08.23.2.TAXO1-03 — K3 Regression-Test (Cross-AI Finding #4).

Pure-logic Regression auf die int-Coercion in ki_logik.detect_phase. KEIN Source-Presence,
KEIN Live-Call, KEINE DB — nur echte Function-Call-Return-Assertions (Test-Qualitaets-Regel).

K3-Bug-Historie: `if raw_phase > current_phase:` (ki_logik) warf
`'>' not supported between 'int' and 'str'` wenn current_phase ein String ("1") war
(phase_classify lief still tot, 8x in 14 Tagen). Die Coercion `int(current_phase or 1)`
am Funktionseingang schuetzt davor. Dieser Test sichert die Coercion gegen Regression:
String-current_phase darf KEINEN TypeError werfen UND muss dasselbe Ergebnis wie int liefern.
"""
import pytest

# detect_phase importiert keine schweren Live-/DB-Dependencies; falls der Import (z.B. wegen
# eines fehlenden optionalen Pakets im Modulkopf) scheitert, sauber skippen statt False-Green.
try:
    from services.ki_logik import detect_phase
except Exception as _imp_err:  # pragma: no cover
    detect_phase = None
    _IMPORT_ERR = _imp_err
else:
    _IMPORT_ERR = None

pytestmark = pytest.mark.skipif(
    detect_phase is None,
    reason=f"ki_logik.detect_phase nicht importierbar: {_IMPORT_ERR}",
)


def test_detect_phase_accepts_string_current_phase():
    """K3: detect_phase mit String-current_phase ('2') wirft KEINEN TypeError.

    raw_phase=3 > current_phase erreicht die fruehere int-vs-str-Vergleichsstelle.
    Vor dem Fix: TypeError. Nach dem Fix: regulaeres (phase, confidence)-Tupel.
    """
    try:
        result = detect_phase(
            raw_phase=3,
            raw_confidence=0.9,
            current_phase="2",   # String — wie der K3-Bug ihn lieferte
            phase_change_count=0,
            cycles_since_change=5,
        )
    except TypeError as e:
        pytest.fail(f"K3-Regression: detect_phase wirft TypeError bei String-current_phase: {e}")
    # Ergebnis ist ein (phase, confidence)-Tupel
    assert isinstance(result, tuple) and len(result) == 2
    phase, conf = result
    assert isinstance(phase, int)


def test_detect_phase_int_str_parity():
    """K3: identische Argumente, current_phase einmal als str, einmal als int → gleiches Ergebnis.

    Beweist, dass die Coercion str und int aequivalent macht (kein Verhaltens-Drift).
    """
    common = dict(raw_phase=3, raw_confidence=0.9, phase_change_count=1, cycles_since_change=4)
    res_str = detect_phase(current_phase="3", **common)
    res_int = detect_phase(current_phase=3, **common)
    assert res_str == res_int

    # Auch ein vorwaerts-Advance-Fall (raw_phase > current_phase) muss paritaetisch sein.
    res_str_adv = detect_phase(raw_phase=4, raw_confidence=0.85, current_phase="2",
                               phase_change_count=0, cycles_since_change=5)
    res_int_adv = detect_phase(raw_phase=4, raw_confidence=0.85, current_phase=2,
                               phase_change_count=0, cycles_since_change=5)
    assert res_str_adv == res_int_adv


def test_detect_phase_none_current_phase_seeds_one():
    """K3 Edge (Task 1a): current_phase=None → kein Crash, Coercion-Seed 1.

    `int(current_phase or 1)` faengt None ab. raw_phase=1 == seed 1 → same-phase pass-through.
    """
    try:
        result = detect_phase(
            raw_phase=1,
            raw_confidence=0.5,
            current_phase=None,
            phase_change_count=0,
            cycles_since_change=0,
        )
    except (TypeError, ValueError) as e:
        pytest.fail(f"K3-Regression: detect_phase crasht bei current_phase=None: {e}")
    phase, conf = result
    # Seed 1: raw_phase=1 == current_phase(seed)=1 → bleibt 1 (Same-Phase-Pass-Through)
    assert phase == 1
