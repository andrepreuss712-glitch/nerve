"""
Korpus-Gate: Pre-Execute-Gate fuer Phasen-Klassifikator-Tests (Phase 08.23.2.C)
================================================================================
Prueft ob beide Test-Korpora existieren, schema-valide sind und die Mindest-Anzahl
von Eintraegen erfuellen. Muss gruenn sein BEVOR Execute-Phase der Tests (Wave 5) startet.

Aufruf: python scripts/verify_corpus_gate.py

Exit-Code 0  = alle Checks gruen (ALLE CHECKS GRUEN)
Exit-Code 1  = mindestens ein Check fehlgeschlagen (BLOCKIERT)

Entscheidung D-04 (CONTEXT.md): Korpora werden von Andre async via claude.ai erstellt.
Schemas: tests/fixtures/phase_classifier_corpus.schema.json
         tests/fixtures/gatekeeper_classifier_corpus.schema.json
"""

import json
import os
import sys

# ── Pfade ────────────────────────────────────────────────────────────────────
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PHASE_CORPUS_PATH = os.path.join(_BASE_DIR, 'tests', 'fixtures', 'phase_classifier_corpus.json')
GATEKEEPER_CORPUS_PATH = os.path.join(_BASE_DIR, 'tests', 'fixtures', 'gatekeeper_classifier_corpus.json')

# ── Mindest-Anzahlen (Req-12, Req-13) ────────────────────────────────────────
MIN_PHASE_ENTRIES = 20
MIN_GATEKEEPER_ENTRIES = 10

# ── Gueltiger Wertebereich ────────────────────────────────────────────────────
VALID_MODES = {'cold_call', 'meeting', 'gatekeeper'}
VALID_PHASES = set(range(1, 7))  # 1..6
VALID_CATEGORIES = {'target', 'gatekeeper', 'unknown'}


def _check(condition, ok_msg, err_msg, errors):
    """Druckt Status und sammelt Fehler."""
    if condition:
        print(f"[CORPUS-GATE] OK: {ok_msg}")
    else:
        print(f"[CORPUS-GATE] FEHLER: {err_msg}")
        errors.append(err_msg)


def _validate_phase_entry(entry, idx):
    """Prueft einen einzelnen Phasen-Korpus-Eintrag. Gibt Liste von Fehlern zurueck."""
    errs = []
    if not isinstance(entry, dict):
        errs.append(f"Eintrag {idx}: kein Dict")
        return errs
    # transcript_window: List[str], minItems=1
    tw = entry.get('transcript_window')
    if not isinstance(tw, list) or len(tw) < 1:
        errs.append(f"Eintrag {idx}: transcript_window fehlt oder leer")
    elif not all(isinstance(s, str) for s in tw):
        errs.append(f"Eintrag {idx}: transcript_window-Elemente muessen Strings sein")
    # mode: enum
    mode = entry.get('mode')
    if mode not in VALID_MODES:
        errs.append(f"Eintrag {idx}: mode='{mode}' ungueltig (erlaubt: {VALID_MODES})")
    # expected_phase: int 1..6
    ep = entry.get('expected_phase')
    if not isinstance(ep, int) or ep not in VALID_PHASES:
        errs.append(f"Eintrag {idx}: expected_phase='{ep}' ungueltig (erlaubt: 1-6)")
    return errs


def _validate_gatekeeper_entry(entry, idx):
    """Prueft einen einzelnen Gatekeeper-Korpus-Eintrag. Gibt Liste von Fehlern zurueck."""
    errs = []
    if not isinstance(entry, dict):
        errs.append(f"Eintrag {idx}: kein Dict")
        return errs
    # transcript_window: List[str], minItems=1
    tw = entry.get('transcript_window')
    if not isinstance(tw, list) or len(tw) < 1:
        errs.append(f"Eintrag {idx}: transcript_window fehlt oder leer")
    elif not all(isinstance(s, str) for s in tw):
        errs.append(f"Eintrag {idx}: transcript_window-Elemente muessen Strings sein")
    # briefing_ceo_name: str
    ceo = entry.get('briefing_ceo_name')
    if not isinstance(ceo, str) or not ceo:
        errs.append(f"Eintrag {idx}: briefing_ceo_name fehlt oder leer")
    # expected_category: enum
    cat = entry.get('expected_category')
    if cat not in VALID_CATEGORIES:
        errs.append(f"Eintrag {idx}: expected_category='{cat}' ungueltig (erlaubt: {VALID_CATEGORIES})")
    return errs


def main():
    errors = []

    # ── Check 1: Existenz Phasen-Korpus ──────────────────────────────────────
    phase_exists = os.path.isfile(PHASE_CORPUS_PATH)
    _check(
        phase_exists,
        f"phase_classifier_corpus.json existiert ({PHASE_CORPUS_PATH})",
        f"phase_classifier_corpus.json fehlt: {PHASE_CORPUS_PATH}",
        errors,
    )

    # ── Check 2: Existenz Gatekeeper-Korpus ──────────────────────────────────
    gk_exists = os.path.isfile(GATEKEEPER_CORPUS_PATH)
    _check(
        gk_exists,
        f"gatekeeper_classifier_corpus.json existiert ({GATEKEEPER_CORPUS_PATH})",
        f"gatekeeper_classifier_corpus.json fehlt: {GATEKEEPER_CORPUS_PATH}",
        errors,
    )

    # ── Phasen-Korpus validieren ──────────────────────────────────────────────
    phase_data = None
    if phase_exists:
        try:
            with open(PHASE_CORPUS_PATH, encoding='utf-8') as f:
                phase_data = json.load(f)
            _check(True, "phase_classifier_corpus.json ist valides JSON", "", errors)
        except json.JSONDecodeError as e:
            _check(False, "", f"phase_classifier_corpus.json JSON-Parse-Fehler: {e}", errors)

    if phase_data is not None:
        # Mindest-Anzahl
        _check(
            isinstance(phase_data, list) and len(phase_data) >= MIN_PHASE_ENTRIES,
            f"phase_classifier_corpus.json hat {len(phase_data) if isinstance(phase_data, list) else 0} >= {MIN_PHASE_ENTRIES} Eintraege",
            f"phase_classifier_corpus.json hat zu wenige Eintraege (braucht >={MIN_PHASE_ENTRIES}, hat {len(phase_data) if isinstance(phase_data, list) else 'N/A'})",
            errors,
        )
        # Schema-Validation pro Eintrag
        if isinstance(phase_data, list):
            entry_errors = []
            for idx, entry in enumerate(phase_data):
                entry_errors.extend(_validate_phase_entry(entry, idx))
            _check(
                len(entry_errors) == 0,
                f"phase_classifier_corpus.json Schema-Validation: alle {len(phase_data)} Eintraege OK",
                f"phase_classifier_corpus.json Schema-Fehler in {len(entry_errors)} Feldern: {entry_errors[:3]}{'...' if len(entry_errors) > 3 else ''}",
                errors,
            )

    # ── Gatekeeper-Korpus validieren ─────────────────────────────────────────
    gk_data = None
    if gk_exists:
        try:
            with open(GATEKEEPER_CORPUS_PATH, encoding='utf-8') as f:
                gk_data = json.load(f)
            _check(True, "gatekeeper_classifier_corpus.json ist valides JSON", "", errors)
        except json.JSONDecodeError as e:
            _check(False, "", f"gatekeeper_classifier_corpus.json JSON-Parse-Fehler: {e}", errors)

    if gk_data is not None:
        # Mindest-Anzahl
        _check(
            isinstance(gk_data, list) and len(gk_data) >= MIN_GATEKEEPER_ENTRIES,
            f"gatekeeper_classifier_corpus.json hat {len(gk_data) if isinstance(gk_data, list) else 0} >= {MIN_GATEKEEPER_ENTRIES} Eintraege",
            f"gatekeeper_classifier_corpus.json hat zu wenige Eintraege (braucht >={MIN_GATEKEEPER_ENTRIES}, hat {len(gk_data) if isinstance(gk_data, list) else 'N/A'})",
            errors,
        )
        # Schema-Validation pro Eintrag
        if isinstance(gk_data, list):
            entry_errors = []
            for idx, entry in enumerate(gk_data):
                entry_errors.extend(_validate_gatekeeper_entry(entry, idx))
            _check(
                len(entry_errors) == 0,
                f"gatekeeper_classifier_corpus.json Schema-Validation: alle {len(gk_data)} Eintraege OK",
                f"gatekeeper_classifier_corpus.json Schema-Fehler in {len(entry_errors)} Feldern: {entry_errors[:3]}{'...' if len(entry_errors) > 3 else ''}",
                errors,
            )

    # ── Summary ──────────────────────────────────────────────────────────────
    print()
    if not errors:
        print("[CORPUS-GATE] ALLE CHECKS GRUEN — Execute-Phase kann starten")
        sys.exit(0)
    else:
        print(f"[CORPUS-GATE] BLOCKIERT: {len(errors)} Fehler — Execute-Phase nicht erlaubt")
        print("[CORPUS-GATE] Korpora von Andre via claude.ai erstellen und committen (D-04)")
        sys.exit(1)


if __name__ == '__main__':
    main()
