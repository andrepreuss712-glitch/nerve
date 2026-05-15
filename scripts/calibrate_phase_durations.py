"""Stufe-1-Kalibrierung fuer Hysterese-Mindest-Zeiten (Phase 08.23.2.C, D-03).

Berechnet empfohlene MIN_PHASE_DURATIONS aus dem Trainings-Korpus
tests/fixtures/phase_classifier_corpus.json.

Heuristik: Phasen-Dauer ~ len(transcript_window) * 4 Sekunden.
Begruendung: Pro Berater-Satz ~4s (Pause + Kundenreaktion + naechster Satz).
Empfohlener Min-Wert: max(3, round(avg * 0.6)) -- 60% des Avg, mindestens 3s.

Aufruf: python scripts/calibrate_phase_durations.py
Exit-Code: 0 (Diagnose, kein Gate).
Schreibt KEINE Datei -- nur Vorschlaege auf stdout. Andre bestaetigt manuell.
"""

import json
import os
import sys
from collections import defaultdict

# Heuristik-Konstante: Sekunden pro Berater-Satz im transcript_window
SECS_PER_SENTENCE = 4


def _load_corpus(path):
    """Laedt Korpus-JSON. Gibt leere Liste zurueck wenn Datei fehlt."""
    try:
        with open(path, encoding='utf-8') as fh:
            return json.load(fh)
    except FileNotFoundError:
        return None
    except json.JSONDecodeError as exc:
        print(f'[CALIBRATE] FEHLER: Korpus-JSON ungueltig: {exc}')
        return []


def _estimate_duration_s(entry):
    """Schaetzt Phasen-Dauer in Sekunden aus Transkript-Fenster-Laenge."""
    window = entry.get('transcript_window', [])
    return len(window) * SECS_PER_SENTENCE


def _phase_name_for_entry(entry, mode):
    """Gibt Phasen-Name als String zurueck.

    Schema speichert expected_phase als Integer (1-6).
    Mapping zu Name via modus-spezifischer Liste.
    """
    phase_idx = entry.get('expected_phase', 1)
    phase_maps = {
        'cold_call': {1: 'opener', 2: 'permission', 3: 'reason',
                      4: 'pitch', 5: 'discovery', 6: 'closing'},
        'gatekeeper': {1: 'greeting', 2: 'identify', 3: 'bypass', 4: 'handoff'},
        'meeting': {1: 'intro', 2: 'agenda', 3: 'discovery',
                    4: 'pitch', 5: 'objection', 6: 'closing'},
    }
    return phase_maps.get(mode, {}).get(phase_idx, f'phase_{phase_idx}')


def _percentile(sorted_vals, pct):
    """P50/P95 aus sortierter Liste (lineare Interpolation)."""
    if not sorted_vals:
        return 0
    n = len(sorted_vals)
    idx = (pct / 100) * (n - 1)
    lo = int(idx)
    hi = min(lo + 1, n - 1)
    frac = idx - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


def calibrate(corpus_path, current_config=None):
    """Hauptfunktion: Berechnet und gibt Kalibrierungs-Vorschlaege aus."""
    corpus = _load_corpus(corpus_path)
    if corpus is None:
        print('[CALIBRATE] Korpus fehlt, calibration uebersprungen')
        print(f'[CALIBRATE] Erwartet: {corpus_path}')
        return

    if not corpus:
        print('[CALIBRATE] Korpus leer oder ungueltig -- kein Output.')
        return

    # Durationen aggregieren: {mode: {phase_name: [dauer_s, ...]}}
    durations = defaultdict(lambda: defaultdict(list))
    for entry in corpus:
        mode = entry.get('mode', 'cold_call')
        phase_name = _phase_name_for_entry(entry, mode)
        dur_s = _estimate_duration_s(entry)
        durations[mode][phase_name].append(dur_s)

    # Vergleichs-Konfig laden
    if current_config is None:
        try:
            from config.phase_transitions import MIN_PHASE_DURATIONS
            current_config = MIN_PHASE_DURATIONS
        except ImportError:
            current_config = {}

    # Tabelle ausgeben
    print('[CALIBRATE] ============================================================')
    print('[CALIBRATE] Stufe-1-Kalibrierung gegen phase_classifier_corpus.json')
    print(f'[CALIBRATE] Heuristik: {SECS_PER_SENTENCE}s pro Satz, recommended = max(3, round(avg * 0.6))')
    print('[CALIBRATE] ============================================================')

    for mode in sorted(durations.keys()):
        print(f'[CALIBRATE] {mode}')
        mode_config = current_config.get(mode, {})
        for phase_name in sorted(durations[mode].keys()):
            vals = sorted(durations[mode][phase_name])
            avg = sum(vals) / len(vals)
            p50 = _percentile(vals, 50)
            p95 = _percentile(vals, 95)
            recommended = max(3, round(avg * 0.6))
            current = mode_config.get(phase_name, '?')
            delta = (recommended - current) if isinstance(current, int) else '?'
            delta_str = f'{delta:+d}' if isinstance(delta, int) else delta
            print(
                f'  {phase_name:<12} current={current!s:<4} '
                f'corpus_avg={avg:<6.1f} p50={p50:<5.1f} p95={p95:<6.1f} '
                f'recommended={recommended:<4} delta={delta_str}'
            )
        print()

    print('[CALIBRATE] Hinweis: Keine Datei wurde geschrieben.')
    print('[CALIBRATE] Andre bestaetigt Vorschlaege manuell und editiert config/phase_transitions.py.')


def main():
    # Pfad relativ zum Projekt-Root (Aufruf via python scripts/calibrate_phase_durations.py)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    corpus_path = os.path.join(project_root, 'tests', 'fixtures', 'phase_classifier_corpus.json')

    # Sicherstellen dass config/ importierbar ist (Projekt-Root im Pfad)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    calibrate(corpus_path)


if __name__ == '__main__':
    main()
