"""
GLiNER Smoke-Test: Latenz + Return-Format-Verifikation
======================================================
Standalone-Diagnoseskript fuer Open Question 1 (Phase 08.23.2.C):
  - Gibt GLiNER predict_entities() Character-Offsets zurueck (start/end)?
  - Wie ist die Latenz auf CX32 (Min/Avg/P95 ueber 100 Runs)?
  - Wie lange dauert das Modell-Laden?

Aufruf: python scripts/gliner_smoke.py

Exit-Code immer 0 (Diagnose-Skript, kein Test-Gate).
"""

import time
import statistics


def main():
    print("[GLiNER-Smoke] Lade Modell urchade/gliner_multi-v2.1 ...")
    t_load_start = time.perf_counter()

    try:
        from gliner import GLiNER
        model = GLiNER.from_pretrained('urchade/gliner_multi-v2.1')
    except Exception as e:
        print(f"[GLiNER-Smoke] FEHLER beim Laden: {type(e).__name__}: {e}")
        print("[GLiNER-Smoke] Abbruch — GLiNER nicht installiert oder Modell nicht verfuegbar.")
        return

    t_load_end = time.perf_counter()
    load_secs = t_load_end - t_load_start
    print(f"[GLiNER-Smoke] Modell geladen in {load_secs:.2f}s")

    # Test-Text (generisch, keine reale PII — T-08.23.2.C-03 accept)
    test_text = "Hallo Herr Mueller, ich rufe wegen Siemens AG an."
    labels = ['person', 'organisation', 'location']
    n_runs = 100

    print(f"\n[GLiNER-Smoke] Starte {n_runs} Inferenzen auf: '{test_text}'")
    print(f"[GLiNER-Smoke] Labels: {labels}")

    # Erster Run — Return-Format-Dump fuer Open Question 1
    entities_first = model.predict_entities(test_text, labels, threshold=0.5)
    print("\n[GLiNER-Smoke] Return-Format-Dump (erster Run):")
    print(f"  repr: {repr(entities_first)}")
    if entities_first:
        first_entity = entities_first[0]
        print(f"  Keys im ersten Entity-Dict: {list(first_entity.keys())}")
        print(f"  Hat 'start'-Key: {'start' in first_entity}")
        print(f"  Hat 'end'-Key: {'end' in first_entity}")
        print(f"  Hat 'score'-Key: {'score' in first_entity}")
    else:
        print("  Keine Entities erkannt im ersten Run.")

    # Latenz-Messung ueber n_runs
    latencies_ms = []
    for i in range(n_runs):
        t_start = time.perf_counter()
        _ = model.predict_entities(test_text, labels, threshold=0.5)
        t_end = time.perf_counter()
        latencies_ms.append((t_end - t_start) * 1000.0)

    latencies_sorted = sorted(latencies_ms)
    p95_idx = int(len(latencies_sorted) * 0.95)
    p95_ms = latencies_sorted[p95_idx]
    avg_ms = statistics.mean(latencies_ms)
    min_ms = min(latencies_ms)

    print(f"\n[GLiNER-Smoke] Latenz-Ergebnis ueber {n_runs} Runs:")
    print(f"  Min:  {min_ms:.1f}ms")
    print(f"  Avg:  {avg_ms:.1f}ms")
    print(f"  P95:  {p95_ms:.1f}ms")

    # Latenz-Gate-Hinweis (Pitfall 1 aus RESEARCH.md)
    if p95_ms > 200:
        print(f"\n[GLiNER-Smoke] WARNUNG: P95 {p95_ms:.1f}ms > 200ms (Req-1 Latenz-Gate)")
        print("  -> Erwage: nur 'person'-Label statt 3 Labels fuer Gatekeeper-Erkennung")
    elif p95_ms > 150:
        print(f"\n[GLiNER-Smoke] INFO: P95 {p95_ms:.1f}ms nahe Limit (Req-1: <200ms P95)")
    else:
        print(f"\n[GLiNER-Smoke] OK: P95 {p95_ms:.1f}ms < 150ms — Latenz-Budget eingehalten")

    print("\n[GLiNER-Smoke] Fertig.")


if __name__ == '__main__':
    main()
