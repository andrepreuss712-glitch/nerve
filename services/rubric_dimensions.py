# -*- coding: utf-8 -*-
"""TAXO2-Plan 02 — Die 7 Bewertungs-Dimensionen + 3 BARS-Stufen je Dimension + Messbarkeits-Regeln.

Single Source der Dimensions-Daten fuer die Noten-Engine (services/rubric_engine.py). Abgeleitet
aus dem verriegelten Bauplan `Nerve-Vault/04 Entscheidungen/NERVE TAXO-Geruest (verriegelt).md`
§4 (Scoring: EINE Rubrik, 7 Dimensionen, BARS = Behaviorally Anchored Rating Scales, je 3 Stufen)
und den WIE-Entscheidungen D-05 (Messbarkeit) aus
`.planning/phases/08.23.2.TAXO2-bewerten-eine-noten-engine/08.23.2.TAXO2-CONTEXT.md`.

REINE DATEN/LOGIK — KEIN LLM (Bau-Regel 1), KEIN DB-Zugriff, KEINE Live-Schleife. dict-in -> Wert-out.

Dimensions-Keys sind ASCII (CLAUDE.md UTF-8-Regel: Code-Identifier ohne Umlaute):
  vorwand_behandlung, kaufsignal_nutzung, aufschub_behandlung, phasen_technik,
  fragen_qualitaet, gespraechsfuehrung, outcome_progression
Die BARS-Stufen-Texte sind user-facing -> echte Umlaute (ae/oe/ue/ss NICHT).

Mess-Inputs (existieren, RESEARCH §E):
  - events: Liste von intent_event-Dicts. Pro Event relevante Keys:
      intent_type (str), confidence (float), handling_score_numeric (int 1-3 | None),
      phase (int 1-6 | None), payload_jsonb (dict mit speaker_role, was_correct,
      dimension_available, outcome.resolution, text), text (Berater-Aeusserung optional).
  - speech_stats: {'redeanteil': int %, 'tempo': int, 'monolog': float sec}
      (services/live_session.get_speech_stats(sid), K1 per-SID).
  - call: Objekt/Dict mit call_mode, outcome, dauer_sekunden (Call-Dauer in s).
  - mode_cfg: Dict pro Dimension {weight, enabled, partial_marker, indirekt_erkannt,
      confidence_gate} aus mode_weight_config (Plan 02 Task 1).

D-05-Mess-Regeln je Dimension siehe is_measurable-Funktion + DIMENSIONS-Eintrag.
"""

# ── Konfigurierbare Schwellen (Punkt 12, post-launch tunbar — D-05 Plan-Flag) ───────────────
DEFAULT_CONFIDENCE_GATE = 0.70   # D-03 Tor-1-Default, falls mode_cfg.confidence_gate NULL
MIN_PHASE_CALL_SECONDS = 60      # D-05: Phasen-Technik messbar ab plausibler Mindest-Dauer
VERY_SHORT_PHASE_SECONDS = 3     # D-05: "sehr kurze Phasen" harter Schwellenwert (Negativ-Signal)

# D-05 Sprechdisziplin-Baselines (cold_call Gespraechsfuehrung) — initiale Ziel-Werte aus Andres
# Vertriebs-Wissen, post-launch kalibrieren (D-05 Plan-Flag: Messbarkeit != Benotbarkeit).
SPRECHDISZIPLIN_BASELINE = {
    'max_gute_monolog_sek': 25.0,    # ueber dieser Monolog-Laenge = Stufe 1 (zu viel Monolog)
    'ziel_redeanteil_pct': 45,       # Ziel-Berater-Redeanteil (Spanne um diesen Wert)
    'redeanteil_toleranz': 15,       # +- Toleranz um den Ziel-Redeanteil
}

# D-05 Meeting-Gespraechsfuehrung (Talk-Share Zwei-Sprecher) — Ziel-Balance.
TALKSHARE_BASELINE = {
    'ziel_redeanteil_pct': 45,
    'redeanteil_toleranz': 20,
}

# D-05 Fragen-Qualitaet: W-Fragewoerter (NICHT '?' — STT-Satzzeichen unzuverlaessig).
# Erkennung ueber Wortstamm-Praefix (deckt wer/wen/wem, welche/welcher/welches, etc. ab).
FRAGEWOERTER = (
    'wer', 'wen', 'wem', 'was', 'wann', 'wo', 'warum', 'wieso', 'weshalb',
    'wie', 'welch', 'wozu', 'wofuer', 'wofür', 'womit', 'wodurch', 'inwiefern', 'inwieweit',
)

# Ereignis-basierte Dimensionen: Dimension-Key -> intent_type (D-03, Tor 1).
_EVENT_DIM_TO_INTENT = {
    'vorwand_behandlung': 'vorwand',
    'aufschub_behandlung': 'aufschub',
    'kaufsignal_nutzung': 'kaufsignal',
}


# ── Hilfen (rein) ───────────────────────────────────────────────────────────────────────────
def _get(obj, key, default=None):
    """Liest aus Dict ODER Objekt-Attribut (call kann beides sein) — rein, kein DB-Zugriff."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _event_field(event, key, default=None):
    """Event-Feld: erst Top-Level, dann payload_jsonb. Rein."""
    if event is None:
        return default
    val = _get(event, key, None)
    if val is not None:
        return val
    payload = _get(event, 'payload_jsonb', None) or {}
    if isinstance(payload, dict):
        return payload.get(key, default)
    return default


def _confidence_gate(mode_cfg):
    """Tor-1-Schwelle aus mode_cfg.confidence_gate (D-03) bzw. Default 0.70."""
    if mode_cfg:
        gate = mode_cfg.get('confidence_gate')
        if gate is not None:
            return gate
    return DEFAULT_CONFIDENCE_GATE


def _is_berater(event):
    """True wenn das Event eine Berater-Aeusserung ist (payload speaker_role)."""
    role = _event_field(event, 'speaker_role', None)
    return role in ('berater', 'advisor', 'agent')


def _confident_events_of_type(events, intent_type, gate):
    """Tor-1 (D-03): Events dieses intent_type mit confidence >= gate."""
    out = []
    for ev in (events or []):
        if _event_field(ev, 'intent_type', None) != intent_type:
            continue
        conf = _event_field(ev, 'confidence', None)
        if conf is None or conf >= gate:
            # confidence None = ui_asserted/intern -> als sicher behandeln (TAXO1: ui_asserted=1.0)
            out.append(ev)
    return out


def _count_berater_fragen(events):
    """Zaehlt Berater-Fragen ueber FRAGEWOERTER (D-05, NICHT ueber '?')."""
    n = 0
    for ev in (events or []):
        if not _is_berater(ev):
            continue
        text = (_event_field(ev, 'text', '') or '')
        low = text.lower()
        if any(w in low.split() or low.startswith(w) or (' ' + w) in low for w in FRAGEWOERTER):
            n += 1
    return n


# ── Messbarkeits-Funktionen (D-05) — rein, geben bool ─────────────────────────────────────
def _measurable_event_dim(intent_type):
    """Factory: Ereignis-Dim messbar ab >=1 Ereignis mit confidence >= gate (D-03, NICHT >=2)."""
    def _fn(events, speech_stats, call, mode_cfg):
        gate = _confidence_gate(mode_cfg)
        return len(_confident_events_of_type(events, intent_type, gate)) >= 1
    return _fn


def _measurable_fragen_qualitaet(events, speech_stats, call, mode_cfg):
    # D-05: messbar wenn >=1 Berater-Frage ueber FRAGEWOERTER (NICHT '?').
    return _count_berater_fragen(events) >= 1


def _measurable_phasen_technik(events, speech_stats, call, mode_cfg):
    # D-05: messbar wenn Call-Dauer >= plausible Mindestlaenge.
    dauer = _get(call, 'dauer_sekunden', None)
    if dauer is None:
        return False
    return dauer >= MIN_PHASE_CALL_SECONDS


def _measurable_gespraechsfuehrung(events, speech_stats, call, mode_cfg):
    # D-05 MODUS-ABHAENGIG: meeting -> Talk-Share (Zwei-Sprecher); cold_call -> Berater-Speech-Stats
    # (Monolog/Tempo/Pausen, K1, Einzelsprecher; partial_marker='sprechdisziplin').
    mode_key = _get(call, 'call_mode', None)
    stats = speech_stats or {}
    if mode_key == 'meeting_consented':
        # Talk-Share braucht beide Sprecher -> redeanteil zwischen 1 und 99 (nicht 0/100 = Einzelsprecher).
        rede = stats.get('redeanteil', 0)
        return 0 < rede < 100
    # cold_call (+ training): Berater-Speech-Stats reichen (Monolog/Tempo), Einzelsprecher OK.
    return (stats.get('monolog', 0) or 0) > 0 or (stats.get('tempo', 0) or 0) > 0


def _measurable_outcome_progression(events, speech_stats, call, mode_cfg):
    # D-05: messbar wenn calls.outcome klassifiziert (nicht NULL/'unknown').
    outcome = _get(call, 'outcome', None)
    return outcome is not None and outcome != 'unknown'


# ── Score-Funktionen (D-05) — rein, geben int 1-3 fuer eine MESSBARE Dimension ──────────────
def _score_event_dim(intent_type):
    """Ereignis-Dim: aggregierter handling_score_numeric (Mittel, gerundet) der konfidenten Events."""
    def _fn(events, speech_stats, call):
        gate = DEFAULT_CONFIDENCE_GATE  # Aggregation nutzt denselben Tor-1-Default
        evs = _confident_events_of_type(events, intent_type, gate)
        scores = [s for s in (_event_field(e, 'handling_score_numeric', None) for e in evs)
                  if s is not None]
        if not scores:
            # Ereignis valide, aber Behandlung unsicher (Abstention D-07) -> niedrigste Stufe NICHT
            # erzwingen; Engine behandelt fehlende handling_scores. Default neutrale Stufe 2.
            return 2
        avg = sum(scores) / len(scores)
        return max(1, min(3, round(avg)))
    return _fn


def _score_fragen_qualitaet(events, speech_stats, call):
    # Wortzahl als EIN Qualitaets-Input (D-05): mehr durchdachte Berater-Fragen -> hoehere Stufe.
    n = _count_berater_fragen(events)
    if n >= 3:
        return 3
    if n == 2:
        return 2
    return 1


def _score_phasen_technik(events, speech_stats, call):
    # D-05: Progression ODER explizites Steckenbleiben (Festhaengen = messbares NEGATIV).
    dauer = _get(call, 'dauer_sekunden', 0) or 0
    if dauer < VERY_SHORT_PHASE_SECONDS:
        return 1  # sehr kurze Phase = Steckenbleiben (Negativ-Signal)
    phases = [p for p in (_event_field(e, 'phase', None) for e in (events or [])) if p is not None]
    if not phases:
        return 1  # keine erkennbare Phasen-Progression = Festhaengen
    progression = max(phases) - min(phases)
    if progression >= 3:
        return 3
    if progression >= 1:
        return 2
    return 1  # in einer Phase steckengeblieben


def _score_gespraechsfuehrung(events, speech_stats, call):
    # cold_call: Sprechdisziplin (Monolog/Tempo gegen Baselines); meeting: Talk-Share-Balance.
    stats = speech_stats or {}
    mode_key = _get(call, 'call_mode', None)
    if mode_key == 'meeting_consented':
        rede = stats.get('redeanteil', 50) or 50
        diff = abs(rede - TALKSHARE_BASELINE['ziel_redeanteil_pct'])
        tol = TALKSHARE_BASELINE['redeanteil_toleranz']
        if diff <= tol:
            return 3
        if diff <= tol * 2:
            return 2
        return 1
    # cold_call / training: Sprechdisziplin = Monolog-Laenge.
    monolog = stats.get('monolog', 0.0) or 0.0
    max_gut = SPRECHDISZIPLIN_BASELINE['max_gute_monolog_sek']
    if monolog <= max_gut:
        return 3
    if monolog <= max_gut * 2:
        return 2
    return 1


def _score_outcome_progression(events, speech_stats, call):
    # Outcome-Klasse -> Stufe. Positive Outcomes hoeher; Abbruch/no_interest niedrig (konsistent D-08).
    outcome = _get(call, 'outcome', None)
    positiv = ('meeting_booked', 'contract_signed')
    teilweise = ('callback', 'send_info')
    if outcome in positiv:
        return 3
    if outcome in teilweise:
        return 2
    return 1  # no_interest/wrong_person/gatekeeper_blocked/unknown


# ── DIMENSIONS — Single Source der 7 Dimensionen + 3 BARS-Stufen je Dimension ───────────────
# Pro Dimension: bars = {1,2,3} user-facing deutsche Texte (Geruest §4); is_measurable + score
# = reine Funktionen (D-05).
DIMENSIONS = {
    'vorwand_behandlung': {
        'label': 'Vorwand-Behandlung',
        'bars': {
            1: 'Vorwand sofort weggebuegelt oder mit einem Gegenargument gekontert.',
            2: 'Vorwand teilweise angenommen, aber nicht sauber isoliert.',
            3: 'Vorwand gelabelt und mit einer Frage isoliert (verstanden, dann geoeffnet).',
        },
        'is_measurable': _measurable_event_dim('vorwand'),
        'score': _score_event_dim('vorwand'),
    },
    'kaufsignal_nutzung': {
        'label': 'Kaufsignal-Nutzung',
        'bars': {
            1: 'Kaufsignal ueberhoert oder ueberredet, kein Aufgreifen.',
            2: 'Kaufsignal erkannt, aber nicht konsequent zum Abschluss gefuehrt.',
            3: 'Kaufsignal aufgegriffen und gezielt zum naechsten Schritt genutzt.',
        },
        'is_measurable': _measurable_event_dim('kaufsignal'),
        'score': _score_event_dim('kaufsignal'),
    },
    'aufschub_behandlung': {
        'label': 'Aufschub-Behandlung',
        'bars': {
            1: 'Aufschub akzeptiert ohne Nachhaken (vertagt sich selbst).',
            2: 'Aufschub angesprochen, aber kein konkreter naechster Schritt vereinbart.',
            3: 'Aufschub hinterfragt und in einen verbindlichen naechsten Schritt ueberfuehrt.',
        },
        'is_measurable': _measurable_event_dim('aufschub'),
        'score': _score_event_dim('aufschub'),
    },
    'phasen_technik': {
        'label': 'Phasen-Technik-Passung',
        'bars': {
            1: 'In einer Phase steckengeblieben oder Gespraech sehr frueh abgebrochen.',
            2: 'Einzelne Phasen-Uebergaenge, aber kein klarer roter Faden.',
            3: 'Saubere Progression durch die Gespraechsphasen.',
        },
        'is_measurable': _measurable_phasen_technik,
        'score': _score_phasen_technik,
    },
    'fragen_qualitaet': {
        'label': 'Fragen-Qualitaet',
        'bars': {
            1: 'Kaum offene Fragen, ueberwiegend Aussagen/geschlossene Fragen.',
            2: 'Einige offene Fragen, aber wenig Tiefe.',
            3: 'Mehrere durchdachte offene Fragen, die das Gespraech vertiefen.',
        },
        'is_measurable': _measurable_fragen_qualitaet,
        'score': _score_fragen_qualitaet,
    },
    'gespraechsfuehrung': {
        'label': 'Gespraechsfuehrung',
        'bars': {
            1: 'Sehr langer Monolog oder stark unausgewogener Redeanteil.',
            2: 'Redeanteil/Tempo teils unausgewogen, aber im Rahmen.',
            3: 'Ausgewogener Redeanteil und angemessenes Tempo (gute Gespraechsbalance).',
        },
        'is_measurable': _measurable_gespraechsfuehrung,
        'score': _score_gespraechsfuehrung,
    },
    'outcome_progression': {
        'label': 'Outcome-Progression',
        'bars': {
            1: 'Kein Fortschritt (kein Interesse / abgebrochen).',
            2: 'Teil-Fortschritt (Rueckruf vereinbart, Infos angefragt).',
            3: 'Klarer Fortschritt (Termin gebucht, Abschluss).',
        },
        'is_measurable': _measurable_outcome_progression,
        'score': _score_outcome_progression,
    },
}
