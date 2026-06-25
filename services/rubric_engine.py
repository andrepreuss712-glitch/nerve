# -*- coding: utf-8 -*-
"""TAXO2-Plan 02 — Die EINE rubrik-basierte Noten-Engine (BARS + Proration).

REINE, DETERMINISTISCHE FUNKTION (Bau-Regel 1): kein Sprachmodell-Aufruf, kein DB-Write
(kein Commit, keine Attribut-Mutation auf einem DB-Objekt), keine Live-Schleife. dict-in -> dict-out.
Die Verkabelung (DB lesen/schreiben, Slow-Lane, calls.coaching_score) ist Plan 04 — NICHT hier.

Sie nimmt:
  - events:        Liste intent_event-Dicts eines Calls (Tor-1-Konfidenz D-03, handling_score_numeric).
  - speech_stats:  {'redeanteil','tempo','monolog'} (get_speech_stats(sid), K1 per-SID).
  - call:          Call-Objekt/Dict mit call_mode, outcome, dauer_sekunden, origin (optional).
  - mode_config:   {dimension: {weight, enabled, partial_marker, indirekt_erkannt, confidence_gate}}
                   = der modus-spezifische Satz aus mode_weight_config (Plan 02 Task 1).
  - mode_key:      OPTIONAL expliziter Modus-Schluessel. Wenn None -> aus call abgeleitet (s.u.).

und liefert die volle Aufschluesselung (7 Dimensionen, je 3 BARS-Stufen) mit Proration.

N-4 NAMING-VERTRAG (KRITISCH gegen leeren Lookup): Der Modus-Lookup-Schluessel `mode_key` kommt
aus `call.call_mode` (die ECHTE Spalte, Werte {cold_call|meeting_consented}) bzw. ist 'training'
wenn origin='training'. Es gibt KEINE Spalte calls.session_mode — ein Read davon liefert None ->
leerer mode_config-Lookup -> alle Dimensionen config_off -> coaching_score IMMER NULL (stiller
Totalausfall). Diese Engine liest deshalb NIE call.session_mode; sie nimmt mode_key als Parameter
ODER leitet ihn aus call.call_mode/origin ab. Kommt der mode_config-Lookup leer zurueck (unbekannter
Modus / kein Gewichtssatz) -> es wird ein Status 'no_weight_set' gesetzt + die Aufschluesselung
traegt eine Spur (NICHT still 0/NULL ohne Trace).

D-01 Zwei-Stufen-Mode-Gate, D-02 modus-relative <50%-Schwelle, is_provisional. Siehe compute_rubric.

ERGEBNIS-BLIND (Soll-Verhalten §6, Andre-Entscheid 2026-06-25): Die Note misst NUR Verhalten.
Das Ergebnis (Ja/Nein, calls.outcome) zieht die Note NIE runter — ein Nein ist keine schlechte
Leistung (Outcome-Bias vermeiden). compute_rubric liest calls.outcome NICHT mehr fuer die Benotung
(die fruehere aborted_failure-Bestrafung ist entfernt). Der EINZIGE Schutz gegen Ueber-Bewertung
duenner Calls ist Daten-Substanz (genug messbares Gewicht, measured_weight_pct >= Schwelle) —
ERGEBNIS-BLIND. Verhaltens-Negativ-Signale (z.B. phasen_technik Festhaengen) BLEIBEN, die sind
verhaltens-basiert, nicht outcome-basiert.
"""

from services.rubric_dimensions import DIMENSIONS, DEFAULT_CONFIDENCE_GATE

# D-02 Schwelle: messbares Gewicht / modus-konfiguriertes Gewicht < THRESHOLD -> kein Gesamtscore.
# Das ist der EINZIGE Ueber-Bewertungs-Schutz (ergebnis-blind, Soll-Verhalten §6).
MEASURED_WEIGHT_THRESHOLD = 0.5


def _get(obj, key, default=None):
    """Liest aus Dict ODER Objekt-Attribut (call kann beides sein). Rein, kein DB-Zugriff."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _resolve_mode_key(call, mode_key):
    """N-4: expliziter mode_key gewinnt; sonst aus call.call_mode bzw. origin='training' ableiten.

    Liest NIEMALS call.session_mode (Spalte existiert nicht -> None -> leerer Lookup, Totalausfall).
    """
    if mode_key:
        return mode_key
    origin = _get(call, 'origin', None)
    if origin == 'training':
        return 'training'
    # QUELLE DER WAHRHEIT = call.call_mode (live). KEIN getattr(call, 'session_mode').
    return _get(call, 'call_mode', None)


def compute_rubric(events, speech_stats, call, mode_config, mode_key=None):
    """Berechnet die rubric-Aufschluesselung (reine Funktion).

    Returns dict:
      {
        coaching_score: float|None,        # None wenn <50% Gewicht messbar (D-02) oder Sonderfall
        dimensions: [ {dim, label, score, weight, available, sample_size, beleg_ref, marker[]} ],
        is_provisional: bool,              # D-08: ueber Schwelle, aber Dimensionen weggeprorated
        measured_weight_pct: float,        # messbares / modus-konfiguriertes Gewicht
        unmeasured_dimensions: [ {dim, reason} ],   # reason: config_off|na (ergebnis-blind, kein not_reached)
        status: str,                       # scored|insufficient_data|no_weight_set
        mode_key: str|None,
      }
    """
    resolved_mode = _resolve_mode_key(call, mode_key)
    mode_config = mode_config or {}

    # N-4 Spur: leerer Lookup -> NICHT still 0/NULL. Status + Trace setzen.
    if not mode_config:
        return {
            'coaching_score': None,
            'dimensions': [],
            'is_provisional': False,
            'measured_weight_pct': 0.0,
            'unmeasured_dimensions': [
                {'dim': d, 'reason': 'config_off'} for d in DIMENSIONS.keys()
            ],
            'status': 'no_weight_set',
            'mode_key': resolved_mode,
        }

    dimensions_out = []
    unmeasured = []
    config_on_weight = 0.0   # Summe Gewicht aller config-an Dimensionen des Modus (D-02-Nenner)
    measured_weight = 0.0    # Summe Gewicht der messbaren Dimensionen (D-02-Zaehler)

    for dim_key, dim_def in DIMENSIONS.items():
        cfg = mode_config.get(dim_key) or {}
        weight = cfg.get('weight', 0.0) or 0.0
        enabled = cfg.get('enabled', False)

        # ── Stufe (a): config-an? (D-01) — sonst raus mit Grund 'config_off' ──────────────
        if not enabled or weight <= 0:
            unmeasured.append({'dim': dim_key, 'reason': 'config_off'})
            continue

        config_on_weight += weight

        # ── Stufe (b): per-Call-Verfuegbarkeit (Proration, D-01) ─────────────────────────
        measurable = dim_def['is_measurable'](events, speech_stats, call, cfg)
        if not measurable:
            # ERGEBNIS-BLIND (Soll-Verhalten §6): eine nicht-messbare config-an-Dimension faellt
            # NEUTRAL raus (reason='na') — NIE ein outcome-getriebener Straf-Grund ('not_reached').
            # Das Ergebnis (calls.outcome) darf die Note nicht runterziehen.
            unmeasured.append({'dim': dim_key, 'reason': 'na'})
            # NIE als 0 werten — available=false faellt aus der Proration raus.
            continue

        # Messbar -> Score (1-3) + Gewicht zaehlt.
        score = dim_def['score'](events, speech_stats, call)
        measured_weight += weight

        # sample_size: Ereignis-Dims = Anzahl konfidenter Events (D-03 Daten-Rider).
        sample_size = _sample_size_for(dim_key, events, cfg)
        marker = []
        if cfg.get('partial_marker'):
            marker.append(cfg['partial_marker'])
        if cfg.get('indirekt_erkannt'):
            marker.append('(indirekt erkannt)')  # D-04

        dimensions_out.append({
            'dim': dim_key,
            'label': dim_def.get('label', dim_key),
            'score': score,
            'weight': weight,
            'available': True,
            'sample_size': sample_size,
            'beleg_ref': _beleg_ref_for(dim_key, events),
            'marker': marker,
        })

    # ── D-02 modus-relative <50%-Schwelle (gegen Modus-Maximum, NICHT gegen volle 7) ──────
    measured_weight_pct = (measured_weight / config_on_weight) if config_on_weight > 0 else 0.0

    if measured_weight_pct < MEASURED_WEIGHT_THRESHOLD:
        # Zu wenig messbares Gewicht -> KEIN erfundener Gesamtscore (D-02).
        return {
            'coaching_score': None,
            'dimensions': dimensions_out,
            'is_provisional': False,
            'measured_weight_pct': measured_weight_pct,
            'unmeasured_dimensions': unmeasured,
            'status': 'insufficient_data',
            'mode_key': resolved_mode,
        }

    # ── Proration: Restgewichte der messbaren Dims auf 100% renormalisieren -> Gesamtscore ─
    coaching_score = _prorated_score(dimensions_out, measured_weight)

    # is_provisional: ueber der Schwelle, aber config-an Dimensionen weggeprorated (na/no_data).
    # config_off zaehlt NICHT (Modus hatte die Dimension nie). Ergebnis-blind, kein not_reached.
    prorated_drop = any(u['reason'] in ('na', 'no_data') for u in unmeasured)
    is_provisional = prorated_drop

    return {
        'coaching_score': coaching_score,
        'dimensions': dimensions_out,
        'is_provisional': is_provisional,
        'measured_weight_pct': measured_weight_pct,
        'unmeasured_dimensions': unmeasured,
        'status': 'scored',
        'mode_key': resolved_mode,
    }


def _prorated_score(dimensions_out, measured_weight):
    """Renormalisiert die Gewichte der messbaren Dims auf 100% und mappt 1-3 -> 0-100.

    Stufe 1->33.3, 2->66.7, 3->100. Gewichteter Schnitt ueber die messbaren Dimensionen.
    """
    if not dimensions_out or measured_weight <= 0:
        return None
    total = 0.0
    for d in dimensions_out:
        norm_weight = d['weight'] / measured_weight
        stufe_pct = (d['score'] / 3.0) * 100.0
        total += norm_weight * stufe_pct
    return round(total, 1)


def _sample_size_for(dim_key, events, cfg):
    """Ereignis-Dims: Anzahl konfidenter Events (Tor-1 D-03). Sonst 1 (vorhandenes Signal)."""
    intent_map = {
        'vorwand_behandlung': 'vorwand',
        'aufschub_behandlung': 'aufschub',
        'kaufsignal_nutzung': 'kaufsignal',
    }
    intent_type = intent_map.get(dim_key)
    if not intent_type:
        return 1
    gate = cfg.get('confidence_gate') or DEFAULT_CONFIDENCE_GATE
    n = 0
    for ev in (events or []):
        it = ev.get('intent_type') if isinstance(ev, dict) else getattr(ev, 'intent_type', None)
        if it != intent_type:
            continue
        conf = ev.get('confidence') if isinstance(ev, dict) else getattr(ev, 'confidence', None)
        # Skeptisch (Gemini-Flag): Events OHNE Vertrauens-Wert (conf=None) NICHT als sicher zaehlen.
        if conf is not None and conf >= gate:
            n += 1
    return n


def _beleg_ref_for(dim_key, events):
    """Beleg-Referenz = Verweis auf intent_event (event_id), KEIN freier LLM-Text (Req 5)."""
    intent_map = {
        'vorwand_behandlung': 'vorwand',
        'aufschub_behandlung': 'aufschub',
        'kaufsignal_nutzung': 'kaufsignal',
    }
    intent_type = intent_map.get(dim_key)
    if not intent_type:
        return None
    for ev in (events or []):
        it = ev.get('intent_type') if isinstance(ev, dict) else getattr(ev, 'intent_type', None)
        if it == intent_type:
            eid = ev.get('event_id') if isinstance(ev, dict) else getattr(ev, 'event_id', None)
            if eid is not None:
                return {'intent_event_id': eid}
    return None
