"""TAXO2-Plan 03, Task 1 — Anker-Marker-Regeln fuer die Einwand-Behandlungs-Note (handling_score 1-3).

Quelle: NERVE TAXO-Geruest (verriegelt) §4 (handling_score 1-3, Label/Frage vs Gegenargument,
grosszuegige Abstention) + 08.23.2.TAXO2-CONTEXT D-07 (grosszuegige Abstention).

Bewertet die NAECHSTE Berater-Aussage nach einem erkannten Einwand auf Anker-Verhalten:
  Stufe 3 (GUT):     Label/Spiegeln/Isolieren — der Berater erkennt den Einwand an, spiegelt
                     ihn, stellt eine Rueckfrage oder isoliert ihn, BEVOR er argumentiert.
  Stufe 2 (MITTEL):  teils Anerkennung, teils sofortiges Gegenargument.
  Stufe 1 (SCHLECHT): sofortiges Wegargumentieren ohne Anerkennung ("aber/doch/trotzdem"
                     als Eroeffnung + direkter Pitch).
  Abstention (None): zu kurz / generisch / unklar — KEINE Note (D-07: grosszuegig). Eine
                     FALSCHE Note zerstoert Trust; eine FEHLENDE Note ist verschmerzbar.

D-07-Grosszuegigkeits-Richtung: im Zweifel KEINE Note. Default ist Abstention.

v1 ist rein regel-/marker-basiert. KEIN LLM-Urteil (Bau-Regel 1, Zirkelschluss-Schutz;
ein spaeteres LLM-Urteil laeuft NUR async in der Slow Lane, nie im Live-Loop). Daher KEIN
anthropic/claude-Import in diesem Modul.

Die Poison-Pill-Behandlung (Exception -> handling_status='failed') liegt NICHT hier, sondern
im Aufrufer services/slow_lane.py:_persist_event_ref (try/except, F-05). grade_handling bleibt
eine reine Funktion: int|None, keine Seiteneffekte, kein DB-Zugriff.
"""

from __future__ import annotations

import re


# ── Marker-Listen (Konstanten, ASCII-Keys; deutsche Marker-Strings mit Umlauten OK) ──

# Label/Spiegeln/Isolieren — die Anker-Technik (GUT, Stufe 3). Der Berater nimmt den
# Einwand zuerst auf, statt ihn sofort wegzuargumentieren.
LABEL_MARKERS = (
    "verstehe ich richtig",
    "wenn ich sie richtig verstehe",
    "wenn ich richtig verstehe",
    "habe ich sie richtig verstanden",
    "das hoere ich oft",
    "das hoere ich haeufig",
    "kann ich gut nachvollziehen",
    "kann ich nachvollziehen",
    "verstehe ich",
    "das verstehe ich",
    "danke fuer die offenheit",
    "danke fuer ihre offenheit",
    "abgesehen davon",
    "mal angenommen",
    "angenommen",
    "es klingt so als",
    "es klingt als",
    "sie meinen also",
    "sie sagen also",
    "das bedeutet fuer sie",
    "was genau meinen sie",
    "wie meinen sie das",
    "was steckt dahinter",
    "darf ich fragen",
)

# Sofortiges Gegenargument / Wegargumentieren als EROEFFNUNG (SCHLECHT, Stufe 1).
# Nur als Satz-Eroeffnung gewertet (nicht irgendwo mittendrin) — daher separat geprueft.
COUNTER_OPENERS = (
    "aber",
    "doch",
    "trotzdem",
    "nein",
    "das stimmt nicht",
    "das ist falsch",
    "im gegenteil",
)

# Wortzahl-Schwelle: kuerzer -> "zu kurz/generisch" -> Abstention (D-07).
MIN_WORDS = 4


def _normalize(text: str) -> str:
    """Kleinschreibung + kollabierte Whitespaces. Reine Hilfsfunktion (kein Seiteneffekt)."""
    return re.sub(r"\s+", " ", text.strip().lower())


def _starts_with_counter(norm: str) -> bool:
    """True, wenn die Aussage mit einem sofortigen Gegenargument eroeffnet."""
    for opener in COUNTER_OPENERS:
        # Wort-Grenze: "aber" ja, aber nicht "abermals". Eroeffnung des Satzes.
        if re.match(r"^" + re.escape(opener) + r"\b", norm):
            return True
    return False


def _has_label_marker(norm: str) -> bool:
    """True, wenn ein Label-/Spiegel-/Isolier-Marker vorkommt."""
    return any(marker in norm for marker in LABEL_MARKERS)


def grade_handling(objection_event, next_advisor_utterance, triggering_text=None):
    """Benotet die Einwand-Behandlung 1-3 ODER abstainiert (None). Reine Funktion.

    Args:
        objection_event:        die intent_event-Zeile (Einwand), Kontext — nur lesend genutzt.
        next_advisor_utterance: die naechste Berater-Aussage nach dem Einwand (str|None).
        triggering_text:        FOLD B P1 (optional, additiv) — der anonymisierte Ausloeser-
                                Wortlaut des Einwands (intent_event.payload_jsonb['triggering_text'],
                                Welle 7). Sauberer Ausloeser-Bezug statt Rekonstruktion aus dem
                                Transkript-Fenster: erlaubt zu pruefen, ob der Berater den
                                bekannten Einwand AUFNIMMT (Spiegeln) statt nur generisch zu
                                reden. Default None -> Verhalten rein auf next_advisor_utterance.

    Returns:
        3 (GUT/Label), 2 (MITTEL/teils), 1 (SCHLECHT/sofort dagegen) ODER None (Abstention).
    """
    # ── Abstention bei fehlender/zu kurzer Aussage (D-07, grosszuegig) ──────────────
    if not next_advisor_utterance or not str(next_advisor_utterance).strip():
        return None
    norm = _normalize(str(next_advisor_utterance))
    if len(norm.split()) < MIN_WORDS:
        return None  # zu kurz/generisch -> keine verlaessliche Note

    has_label = _has_label_marker(norm)
    starts_counter = _starts_with_counter(norm)

    # FOLD B P1: spiegelt der Berater den bekannten Ausloeser-Wortlaut? Verstaerkt das
    # Label-Signal (sauberer Bezug statt Transkript-Rekonstruktion). Additiv, None-safe.
    mirrors_trigger = False
    if triggering_text and str(triggering_text).strip():
        trig = _normalize(str(triggering_text))
        # signifikante Stichwoerter (>3 Zeichen) des Einwands, die der Berater aufgreift
        trig_words = {w for w in trig.split() if len(w) > 3}
        utt_words = set(norm.split())
        mirrors_trigger = len(trig_words & utt_words) >= 2

    # ── Klassifikation ───────────────────────────────────────────────────────────
    if has_label and not starts_counter:
        return 3                       # Anker zuerst, kein sofortiges Dagegen -> GUT
    if (has_label or mirrors_trigger) and starts_counter:
        return 2                       # teils Anerkennung, teils Gegenargument -> MITTEL
    if starts_counter and not has_label:
        return 1                       # sofortiges Wegargumentieren -> SCHLECHT
    if mirrors_trigger and not starts_counter:
        return 3                       # greift den Einwand auf, kein Dagegen -> GUT

    # Weder klarer Anker noch klares Dagegen erkennbar -> grosszuegige Abstention.
    return None
