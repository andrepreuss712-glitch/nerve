"""Mechanismus-Selbsttest des Baseline-Cleanup-Waechters (Phase 08.23.2.PGTEST, Extension 2).

Beweist den Vergleichs-Kern `_diff_baseline` (current-{pk:xmin} vs baseline-{pk:xmin}) runtime — KEINE
Source-Presence (kein inspect.getsource/grep). Drei Pflicht-Faelle:
  (a) Leak (extra-PK, committed+nicht-aufgeraeumt) -> Waechter feuert.
  (b) #7 UPDATE-Mutation (gleiche PK, geaendertes xmin, z.B. User(id=1).is_superadmin=True) -> Waechter
      feuert. Ein reiner PK-Set-Vergleich (frozenset(pks)) wuerde DAS UEBERSEHEN.
  (c) sauberer Zustand (identisch) -> Waechter bleibt gruen (leeres Drift-Dict).
Plus: missing-PK (Baseline-Row geloescht) -> Waechter feuert.

Der Vergleichs-Kern ist DSN-frei -> dieser Test laeuft auch lokal ohne nerve_test (kein SKIP noetig).
"""
from tests.conftest import _diff_baseline


def test_guard_catches_leaked_row():
    """(a) Ein Test committet eine NEUE Row (extra-PK) und raeumt nicht auf -> Drift erkannt."""
    baseline = {"users": {1: "100"}}
    current = {"users": {1: "100", 2: "101"}}  # 2 ist neu (leaked)
    drift = _diff_baseline(current, baseline)
    assert "users" in drift
    assert drift["users"]["leaked"] == {2}
    assert drift["users"]["missing"] == set()
    assert drift["users"]["mutated"] == set()


def test_guard_catches_mutated_baseline_row_via_xmin():
    """(b) #7: committetes UPDATE einer Baseline-Row bei UNVERAENDERTER PK (xmin aendert sich) -> Drift.

    Beweist, dass der {pk:xmin}-Vergleich die Mutation faengt, die ein reiner PK-Set-Vergleich uebersaehe:
    das PK-Set ist hier IDENTISCH ({1}), nur das xmin-Change-Token unterscheidet sich."""
    baseline = {"users": {1: "100"}}            # User(id=1) xmin=100
    current = {"users": {1: "999"}}             # User(id=1).is_superadmin=True committet -> xmin=999
    drift = _diff_baseline(current, baseline)
    assert "users" in drift
    assert drift["users"]["mutated"] == {1}
    assert drift["users"]["leaked"] == set()
    assert drift["users"]["missing"] == set()


def test_guard_catches_missing_baseline_row():
    """Ein Test hat eine Baseline-Row geloescht (missing-PK) -> Drift erkannt."""
    baseline = {"users": {1: "100", 2: "101"}}
    current = {"users": {1: "100"}}             # 2 fehlt
    drift = _diff_baseline(current, baseline)
    assert "users" in drift
    assert drift["users"]["missing"] == {2}


def test_guard_passes_clean_state():
    """(c) Identischer Zustand -> kein Drift, Waechter bleibt gruen."""
    baseline = {"users": {1: "100"}, "organisations": {1: "50"}}
    current = {"users": {1: "100"}, "organisations": {1: "50"}}
    drift = _diff_baseline(current, baseline)
    assert drift == {}


def test_pk_set_only_would_miss_mutation():
    """Kontroll-Beweis: ein reiner PK-Set-Vergleich wuerde die xmin-Mutation aus (b) UEBERSEHEN — der
    {pk:xmin}-Vergleich faengt sie. Belegt warum #7 (per-Row-Change-Token) noetig ist."""
    baseline = {"users": {1: "100"}}
    current = {"users": {1: "999"}}
    # PK-Set-only: identisch -> blind.
    assert set(baseline["users"]) == set(current["users"])
    # {pk:xmin}: faengt es.
    assert _diff_baseline(current, baseline)["users"]["mutated"] == {1}
