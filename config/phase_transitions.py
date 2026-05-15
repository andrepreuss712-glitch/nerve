"""Hysterese-Konfig fuer Phasen-Klassifikator (Phase 08.23.2.C, D-03).

Werte sind initiale Schaetzungen -- Stufe-1-Kalibrierung ueber
scripts/calibrate_phase_durations.py vor erstem Live-Test.
Stufe-2-Kalibrierung monatlich gegen call_events.event_type='phase_change'
(siehe CLAUDE.md Punkt 3c).
"""

# Mindest-Verweildauer pro Phase in SEKUNDEN.
# Wechsel akzeptiert nur wenn: (1) >=2 aufeinanderfolgende Classifier-Hinweise
# UND (2) elapsed_in_current_phase >= MIN_PHASE_DURATIONS[mode][phase_name]
# UND (3) Uebergang in ALLOWED_TRANSITIONS[mode] erlaubt.
MIN_PHASE_DURATIONS = {
    'cold_call': {
        'opener': 5,       # Begruessungs-Phase ist sehr kurz
        'permission': 8,   # Erlaubnis-Frage typisch 5-10s
        'reason': 12,      # Grund des Anrufs braucht Substanz
        'pitch': 20,       # Pitch braucht Zeit zum Aufbau
        'discovery': 30,   # Bedarfsanalyse: laengste Phase
        'closing': 15,     # Abschluss + Termin-Vereinbarung
    },
    'gatekeeper': {
        'greeting': 3,     # "Guten Tag, Mueller-AG"
        'identify': 5,     # "Wen darf ich melden"
        'bypass': 10,      # Mr.-Miyagi-Phase, braucht 2-3 Saetze
        'handoff': 5,      # Uebergabe oder Ablehnung
    },
    'meeting': {
        'intro': 10,       # Vorstellung beider Seiten
        'agenda': 15,      # Agenda-Klaerung
        'discovery': 45,   # Meeting-Bedarfsanalyse laenger als Cold-Call
        'pitch': 30,       # Praesentation
        'objection': 20,   # Einwand-Block
        'closing': 20,     # Termin / Naechste Schritte
    },
}

# Erlaubte Vorwaerts- + Rueckwaerts-Uebergaenge pro Modus.
# Format: {mode: {from_phase: [to_phase_1, to_phase_2, ...]}}
ALLOWED_TRANSITIONS = {
    'cold_call': {
        'opener': ['permission'],
        'permission': ['reason'],
        'reason': ['pitch'],
        'pitch': ['discovery', 'closing'],          # closing direkt erlaubt (Express-Pitch)
        'discovery': ['pitch', 'closing'],           # Einwand-Recovery rueckwaerts erlaubt
        'closing': ['discovery', 'pitch'],           # Einwand-Recovery rueckwaerts erlaubt
    },
    'gatekeeper': {
        'greeting': ['identify'],
        'identify': ['bypass'],
        'bypass': ['identify', 'handoff'],           # rueck zu identify wenn neuer Name faellt
        'handoff': ['bypass'],                       # rueck zu bypass wenn Uebergabe-Versuch scheitert
    },
    'meeting': {
        'intro': ['agenda'],
        'agenda': ['discovery'],
        'discovery': ['pitch', 'objection'],
        'pitch': ['discovery', 'objection'],
        'objection': ['discovery', 'pitch', 'closing'],
        'closing': ['objection'],                    # rueck zu objection wenn neuer Einwand kommt
    },
}

# Explizit verbotene Uebergaenge (Sanity-Check / dokumentiert auch wenn nicht in ALLOWED).
# Hauptzweck: Klarstellung dass kein Sprung zurueck zu Begruessungs-Phasen erlaubt ist.
FORBIDDEN_TRANSITIONS = {
    'cold_call': {
        'permission': ['opener'],
        'reason': ['opener', 'permission'],
        'pitch': ['opener', 'permission'],
        'discovery': ['opener', 'permission'],
        'closing': ['opener', 'permission', 'reason'],
    },
    'gatekeeper': {
        'identify': ['greeting'],
        'bypass': ['greeting'],
        'handoff': ['greeting', 'identify'],
    },
    'meeting': {
        'agenda': ['intro'],
        'discovery': ['intro', 'agenda'],
        'pitch': ['intro', 'agenda'],
        'objection': ['intro', 'agenda'],
        'closing': ['intro', 'agenda', 'discovery'],
    },
}

# Modus-Wechsel-Regel (D-03):
# gatekeeper -> cold_call: immer erlaubt wenn classify_contact() == 'target'
#   -> Hysterese-Reset: aktive Phase wird zu 'opener' (cold_call), Timer neu.
# cold_call -> gatekeeper: NUR via manueller Strg+G-Toggle (kein Auto).
MODE_TRANSITION_AUTO = {
    # Auto-allowed: (from_mode, to_mode) Tupel
    ('gatekeeper', 'cold_call'): True,
    ('gatekeeper', 'meeting'): False,
    ('cold_call', 'gatekeeper'): False,    # nur manuell
    ('cold_call', 'meeting'): False,        # call_mode-bound, kein mid-call swap
    ('meeting', 'cold_call'): False,
    ('meeting', 'gatekeeper'): False,       # nur manuell
}

# Anzahl aufeinanderfolgender Classifier-Hinweise bevor Wechsel akzeptiert wird (D-03 Bedingung 1).
HYSTERESIS_REQUIRED_HINTS = 2
