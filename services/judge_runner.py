# -*- coding: utf-8 -*-
"""LLM-Verhaltens-Judge (LLM-as-a-Judge, Soll-Verhalten §6, TAXO2-Plan 03).

EIN Sonnet-Tool-Use-Call am Call-Ende (async, Slow Lane — Latenz egal, Punkt 25):
  - Liest das ganze getaggte Transkript (ts_ms ASC) + Marker + Profil/Briefing.
  - Rubrik (BARS) an Anfang UND Ende des Prompts (Lost-in-the-Middle, Report-Ergaenzung 2).
  - Outcome (calls.outcome) physisch NICHT im Prompt (T-HT-03-01, grep-verifizierbar).
  - NERVE-Vorschlaege (suggestion_reactions) physisch NICHT im Prompt (T-HT-03-02, Bias-Schutz).
  - Erzwungenes JSON-Schema via Anthropic Tool-Use (forced tool_choice).
  - Beleg-VOR-Note: Schema-Reihenfolge beleg_zitat -> beobachtung -> auspraegung.
  - Compliance-Hard-Gate (Cross-AI-Finding 2): separates binaeres Feld compliance_violation +
    compliance_beleg_zitat im Schema (NICHT in einer Dimension, nicht aufmittelbar).
  - Parse -> observations_jsonb {dim:[{beobachtung,beleg_zitat}]} + ratings_jsonb {dim: auspraegung}
    + observations_jsonb['_compliance'] = {verletzt:bool, beleg_zitat:str}.
  - KEIN DB-Write in dieser Funktion — UPSERT im GUC-geklammerten Slow-Lane-Schritt (Task 2).

Bau-Regel 1 (NERVE TAXO-Geruest §5): KEIN LLM in der Live/Fast-Lane. Dieser Judge laeuft
NUR async im Slow-Lane-Call-Ende-Schritt und NUR nach transcript_resolved==True (Punkt 26).

D-RESIDENZ (offene Entscheidung, checkpoint Plan 05): der Judge nutzt den BESTEHENDEN
claude_client (anthropic.Anthropic direkt, wie alle anderen Post-Call-Calls — kein neuer
Bedrock-Client erfunden; Bedrock-Frankfurt-Migration aller Calls ist eine eigene Phase).
Das Transkript ist bereits anonymisiert (DSGVO §1).

Phase: 08.23.2.TAXO2.HANDLING-TIMING Plan 03
"""

import os

import httpx  # SOFORT-2 (D-03): httpx.Timeout je Aufruf — Abhaengigkeit von anthropic, kein neues Paket
import config
from database.models import TranscriptSegment
from services.claude_service import claude_client
from services.judge_dimensions import DIMENSIONS, DIMENSIONS_VERSION, dimensions_for_prompt
from services.prompt_pipeline import build_profile_context

# ── Modell-Konstante (ENV-Override, Punkt 12) ────────────────────────────────────
# MODEL_JUDGE: ENV-Override fuer den Verhaltens-Judge. Default: MODEL_POSTCALL_ANALYSIS (Sonnet).
MODEL_JUDGE = os.getenv('MODEL_JUDGE', config.MODEL_POSTCALL_ANALYSIS)

# ── Max-Tokens (Slow Lane, Latenz egal) ─────────────────────────────────────────
_JUDGE_MAX_TOKENS = 4096

# ── Status-Konstanten ────────────────────────────────────────────────────────────
_STATUS_JUDGED = 'judged'
_STATUS_JUDGE_FAILED = 'judge_failed'
_STATUS_TRANSCRIPT_NOT_RESOLVED = 'transcript_not_resolved'

# ── JUDGE_TOOL: erzwungenes JSON-Schema (Anthropic Tool-Use / forced tool_choice) ──────
# Beleg-VOR-Note: Schema-Reihenfolge beleg_zitat -> beobachtung -> auspraegung.
# Pro Dimension: Array von Beobachtungs-Objekten (ein Call kann mehrere Beobachtungen pro Dim haben).
# Compliance-Hard-Gate (Cross-AI-Finding 2): SEPARATE Top-Level-Felder — NICHT innerhalb einer Dim.

def _build_dim_observation_schema() -> dict:
    """Baut das Schema-Properties-Dict fuer alle 4 Dimensionen + Compliance-Felder."""
    props = {}
    for dim in DIMENSIONS:
        key = dim['key']
        props[key] = {
            'type': 'array',
            'description': (
                f"Beobachtungen fuer Dimension '{dim['name']}'. "
                f"Definition: {dim['definition']} "
                "Pro Beobachtung: erst das woertliche Beleg-Zitat aus dem Transkript, "
                "dann die Beobachtung, dann die grobe Auspraegung."
            ),
            'items': {
                'type': 'object',
                'properties': {
                    'beleg_zitat': {
                        'type': 'string',
                        'description': (
                            'WOERTLICHES Zitat direkt aus dem Transkript (exakter Wortlaut). '
                            'MUSS im Transkript vorkommen — kein Paraphrasieren, kein Erfinden.'
                        ),
                    },
                    'beobachtung': {
                        'type': 'string',
                        'description': 'Beobachtung/Interpretation des Verhaltens (nach dem Zitat, 1-2 Saetze).',
                    },
                    'auspraegung': {
                        'type': 'string',
                        'enum': ['schwach', 'ok', 'stark'],
                        'description': 'Grobe interne Auspraegung (schwach/ok/stark) — nie an den Nutzer.',
                    },
                },
                'required': ['beleg_zitat', 'beobachtung', 'auspraegung'],
            },
        }

    # Cross-AI-Finding 2: Compliance-Hard-Gate als SEPARATE Top-Level-Felder (NICHT in einer Dim)
    props['compliance_violation'] = {
        'type': 'boolean',
        'description': (
            'HARD-GATE (L3-Safety): true NUR wenn der Kunde MEHRFACH klar Nein sagte UND der Berater '
            'trotzdem weiter drang — das ist nicht Verkauf, sondern Belaestigung. '
            'Bei einem normalen abgelehnten Abschluss (Kunde sagt einmal Nein, Berater akzeptiert): false. '
            'Dieses Feld ist KEIN Dimensions-Urteil — es kann keine gute Dimension aufwiegen.'
        ),
    }
    props['compliance_beleg_zitat'] = {
        'type': 'string',
        'description': (
            'Woertliches Zitat der Verletzung (MUSS im Transkript stehen). '
            'Leer wenn compliance_violation=false.'
        ),
    }

    return props


JUDGE_TOOL = {
    'name': 'record_observations',
    'description': (
        'Erfasst Beobachtungen + woertliche Beleg-Zitate je Dimension sowie das Compliance-Hard-Gate. '
        'ALLE Dimensionen MUESSEN befuellt werden. Beleg-VOR-Note: erst Zitat, dann Beobachtung, dann Auspraegung.'
    ),
    'input_schema': {
        'type': 'object',
        'properties': _build_dim_observation_schema(),
        'required': [d['key'] for d in DIMENSIONS] + ['compliance_violation', 'compliance_beleg_zitat'],
    },
}


# ── Prompt-Bau ──────────────────────────────────────────────────────────────────

def _assemble_markers(events, call) -> str:
    """Kompakte Marker-Liste aus intent_event-Zeilen + audio_health (wer/was/wann, Phase, Aussetzer).
    Kein Outcome, keine Vorschlaege.

    Returns:
        str: formatierter Marker-Block fuer den User-Prompt.
    """
    lines = []

    # NERVE-Erkennungen aus intent_event
    if events:
        lines.append('## NERVE-Erkennungen (Einwand-/Signal-Marker)')
        for ev in events:
            ts = getattr(ev, 'timestamp', None) or getattr(ev, 'ts_ms', None) or '?'
            intent_type = getattr(ev, 'intent_type', '?')
            trigger = getattr(ev, 'triggering_text', None) or ''
            phase = getattr(ev, 'call_phase', None) or ''
            phase_info = f', Phase: {phase}' if phase else ''
            trigger_info = f' — Ausloeser: "{trigger}"' if trigger else ''
            lines.append(f'  [{ts}] Erkannt: {intent_type}{trigger_info}{phase_info}')
    else:
        lines.append('## NERVE-Erkennungen (Einwand-/Signal-Marker)')
        lines.append('  (keine Marker-Events fuer diesen Call)')

    # Audio-Gesundheit / Aussetzer
    audio_score = getattr(call, 'audio_health_score', None)
    lines.append('')
    lines.append('## Audio-Qualitaet')
    if audio_score is not None:
        quality = 'gut' if audio_score >= 0.7 else ('mittel' if audio_score >= 0.4 else 'schlecht')
        lines.append(f'  Audio-Health-Score: {audio_score:.2f} ({quality})')
    else:
        lines.append('  Audio-Health-Score: nicht ermittelt')

    return '\n'.join(lines)


def _build_judge_prompt(call, events, profile_briefing: str, segments) -> tuple:
    """Baut System-Prompt + User-Prompt fuer den Verhaltens-Judge.

    Invarianten (grep-verifizierbar):
      - Kein calls.outcome im Prompt (T-HT-03-01)
      - Keine suggestion_reactions im Prompt (T-HT-03-02, Bias-Schutz)
      - Rubrik (BARS) an Anfang UND Ende (Lost-in-the-Middle, Report-Ergaenzung 2)
      - Compliance-Hard-Gate-Instruktion klar abgesetzt (Cross-AI-Finding 2)

    Args:
        call: Call-ORM-Objekt (call_mode, conversation_log_id, audio_health_score — KEIN outcome)
        events: Liste von IntentEvent-Objekten (Marker; kein Outcome, kein Vorschlag)
        profile_briefing: build_profile_context-Output (Profil + Briefing als Massstab)
        segments: Liste von TranscriptSegment-Objekten (ts_ms ASC sortiert)

    Returns:
        (system_str, user_str): beide Strings fuer den Anthropic-Call.
    """
    dims_block = dimensions_for_prompt()  # BARS als Klartext (Plan 02)

    # ── System-Prompt ─────────────────────────────────────────────────────────────
    # Rubrik an ANFANG (Lost-in-the-Middle #1)
    system_lines = [
        '== BEWERTUNGS-RUBRIK (Anfang — merken fuer das ganze Transkript) ==',
        dims_block,
        '',
        '== DEINE ROLLE ==',
        (
            'Du beobachtest und belegst Verhalten in einem Verkaufsgespraech. '
            'Du VERRECHNEST NICHT. KEINE Note, KEINE Zahl, KEINE Gesamtbewertung. '
            'Pro Dimension: erst das WOERTLICHE Beleg-Zitat direkt aus dem Transkript, '
            'dann die Beobachtung, dann die grobe Auspraegung schwach/ok/stark. '
            'Beleg-VOR-Note — eine Note ohne Beleg ist wertlos und wird abgelehnt.'
        ),
        '',
        '== BEWERTUNGS-PRINZIPIEN ==',
        (
            '1. Bewerte NUR das beobachtbare Verhalten. Ein ablehnender Kunde ist KEINE schlechte Leistung. '
            'Decentering: das Ergebnis (ob der Deal zustande kam) ist IRRELEVANT fuer die Bewertung — '
            'du weisst es nicht und es gehoert nicht in dein Urteil.'
        ),
        (
            '2. Laengen-Neutralitaet (Verbosity-Bias): nicht der laengere oder fluessigere Sprecher ist besser. '
            'Beobachte Inhalt und Verhalten, nicht Redefluss.'
        ),
        (
            '3. Kaltakquise-Redeanteil-Norm: ~55% Berater / ~45% Kunde (Gong Cold-Call-Norm). '
            'NICHT 43:57 (das waere eine Discovery-Session).'
        ),
        (
            '4. Hard-Cap Gespraechsfuehrung: wenn der Kunde MEHRFACH klar ablehnt und der Berater '
            'trotzdem weiterdraengt, ist das KEINE schlechte Gespraechsfuehrung mehr — '
            'das ist Belaestigung (Hard-Cap). Das deckelt Gespraechsfuehrung auf hoechstens schwach.'
        ),
        '',
        '== COMPLIANCE-HARD-GATE (L3-Safety — SEPARAT von den Dimensionen) ==',
        (
            'Pruefe SEPARAT und unabhaengig von den Dimensionen eine harte Compliance-Grenze: '
            'Hat der Kunde MEHRFACH klar Nein gesagt und der Berater drueckt trotzdem weiter '
            '(nicht Verkauf, sondern Belaestigung)? '
            'Wenn ja: setze compliance_violation = true und liefere das woertliche Beleg-Zitat '
            '(compliance_beleg_zitat). '
            'Das ist ein HARD-GATE, KEINE Dimension. Es kann NICHT von einer guten Dimension aufgewogen werden. '
            'Bei einem normalen abgelehnten Abschluss (Kunde sagt einmal Nein, Berater akzeptiert): false.'
        ),
        '',
        '== RUBRIK (Ende — nochmals zur Erinnerung) ==',
        dims_block,  # Rubrik am ENDE (Lost-in-the-Middle #2)
    ]
    system_str = '\n'.join(system_lines)

    # ── User-Prompt ──────────────────────────────────────────────────────────────
    # (1) Profil + Pre-Call-Briefing (legitimer Referenz-Massstab)
    user_lines = [
        '== BERATER-PROFIL + PRE-CALL-BRIEFING (Referenz-Massstab) ==',
        profile_briefing,
        '',
    ]

    # (2) Getaggtes Transkript in Sprech-Reihenfolge (ts_ms ASC)
    user_lines.append('== TRANSKRIPT (chronologisch, ts_ms ASC) ==')
    if segments:
        for i, seg in enumerate(segments, start=1):
            speaker = getattr(seg, 'speaker', 'unbekannt')
            ts_ms = getattr(seg, 'ts_ms', 0)
            text = getattr(seg, 'text', '')
            user_lines.append(f'[#{i} {speaker} {ts_ms}ms] {text}')
    else:
        user_lines.append('(Keine Transkript-Segmente verfuegbar)')
    user_lines.append('')

    # (3) NERVE-Erkennungen / Aussetzer als kompakte Marker-Liste
    # STRIKT NICHT enthalten: calls.outcome, suggestion_reactions (physische Trennung)
    user_lines.append(_assemble_markers(events, call))
    user_lines.append('')

    # (4) Aufgabe
    user_lines.append('== AUFGABE ==')
    user_lines.append(
        'Lies das Transkript der Reihe nach. '
        'Befuelle das Werkzeug record_observations mit deinen Beobachtungen. '
        'Pro Dimension: woertliches Beleg-Zitat (EXAKT aus dem Transkript) -> Beobachtung -> Auspraegung. '
        'Pruefe SEPARAT das Compliance-Hard-Gate (compliance_violation). '
        'KEINE Gesamtnote. KEINE Zahl. NUR Beobachtungen mit Belegen.'
    )

    user_str = '\n'.join(user_lines)
    return system_str, user_str


# ── Parser ───────────────────────────────────────────────────────────────────────

def _parse_judge_output(tool_input: dict) -> tuple:
    """Parst den Tool-Use-Output des Judge in observations_jsonb + ratings_jsonb.

    observations_jsonb: {dim_key: [{beobachtung, beleg_zitat}], '_compliance': {verletzt, beleg_zitat}}
      - auspraegung ist NICHT in observations (nur intern in ratings)
      - '_compliance' (Underscore-Praefix) ist der reservierte Compliance-Hard-Gate-Schluessel

    ratings_jsonb: {dim_key: 'schwach'|'ok'|'stark'}
      - '_compliance' ist NICHT in ratings (Hard-Gate, kein Mittelwert-Beitrag)

    Args:
        tool_input: das 'input'-Dict aus dem tool_use-Block der Anthropic-Antwort.

    Returns:
        (observations_jsonb, ratings_jsonb): beide dicts.
    """
    observations = {}
    ratings = {}

    dim_keys = {d['key'] for d in DIMENSIONS}

    for dim in DIMENSIONS:
        key = dim['key']
        raw_list = tool_input.get(key) or []

        obs_list = []
        for item in raw_list:
            # Beleg-VOR-Note: beleg_zitat + beobachtung in observations (auspraegung NICHT)
            obs_list.append({
                'beobachtung': item.get('beobachtung', ''),
                'beleg_zitat': item.get('beleg_zitat', ''),
            })
            # Auspraegung landet nur in ratings (intern, nie an Nutzer)
            auspraegung = item.get('auspraegung', 'ok')
            if auspraegung in ('schwach', 'ok', 'stark'):
                # Letzter Wert gewinnt (i.d.R. eine Beobachtung pro Dim)
                ratings[key] = auspraegung

        observations[key] = obs_list

    # Compliance-Hard-Gate (Cross-AI-Finding 2): in observations['_compliance'], NICHT in ratings
    compliance_violation = bool(tool_input.get('compliance_violation', False))
    compliance_beleg = tool_input.get('compliance_beleg_zitat', '') or ''
    observations['_compliance'] = {
        'verletzt': compliance_violation,
        'beleg_zitat': compliance_beleg,
    }
    # '_compliance' wird NICHT in ratings geschrieben (kein Mittelwert-Beitrag — Hard-Gate-Semantik)

    return observations, ratings


# ── Hauptfunktion ────────────────────────────────────────────────────────────────

def run_behavior_judge(call, events, db) -> dict:
    """Fuehrt den LLM-Verhaltens-Judge fuer einen abgeschlossenen Call aus.

    Laedt Profil+Briefing + Transkript-Segmente, baut den Prompt, feuert EINEN
    forced-Tool-Use-Sonnet-Call (temp=0), parst die Antwort.

    KEIN DB-Write hier — der UPSERT passiert im GUC-geklammerten Slow-Lane-Schritt (Task 2),
    der diese Funktion aufruft und das Ergebnis-Dict unter der M-4-GUC persistiert.

    Invarianten:
      - Nur laeuft wenn transcript_resolved==True (Punkt 26, Plan-01-Fan-In-Gate).
      - Kein Outcome im Prompt (T-HT-03-01).
      - Keine Vorschlaege im Prompt (T-HT-03-02).
      - EIN Call, temperature=0 (Punkt 27: einfachster tragfaehiger Weg).

    Args:
        call: Call-ORM-Objekt (call_mode, conversation_log_id, user_id, transcript_resolved, ...)
        events: Liste von IntentEvent-Objekten (Marker, aus der Slow-Lane-ctx)
        db: SQLAlchemy-Session (GUC bereits gesetzt vom Merge-Gate, M-4)

    Returns:
        dict mit {observations_jsonb, ratings_jsonb, dimensions_version, status}
        oder {status: 'transcript_not_resolved'} (Gate nicht erfuellt)
        oder {status: 'judge_failed', error: str} (LLM-/Parse-Fehler)
    """
    # ── Punkt 26 / Plan-01-Fan-In-Gate: Judge nur nach transcript_resolved==True ──────────────
    # api_beenden setzt transcript_resolved IMMER (resolved-als-absent): kein Hang.
    if not getattr(call, 'transcript_resolved', False):
        print(f'[JUDGE] skip call={getattr(call, "id", "?")}: transcript_resolved=False (Punkt 26)')
        return {'status': _STATUS_TRANSCRIPT_NOT_RESOLVED}

    try:
        # ── Profil + Pre-Call-Briefing (legitimer Referenz-Massstab) ──────────────────────────
        mode = getattr(call, 'call_mode', 'cold_call') or 'cold_call'
        sid = getattr(call, 'conversation_log_id', None)
        user_id = getattr(call, 'user_id', None) or 0
        profile_briefing = build_profile_context(user_id, mode, sid)

        # ── Transkript-Segmente laden (ts_ms ASC, dann id ASC fuer Ties) ─────────────────────
        segments = (
            db.query(TranscriptSegment)
            .filter(TranscriptSegment.conversation_log_id == sid)
            .order_by(TranscriptSegment.ts_ms.asc(), TranscriptSegment.id.asc())
            .all()
        )

        # ── Prompt-Bau ───────────────────────────────────────────────────────────────────────
        system_str, user_str = _build_judge_prompt(call, events, profile_briefing, segments)

        # ── EIN forced-Tool-Use-Sonnet-Call (temp=0, Bewertung — keine Kreativitaet) ──────────
        # D-RESIDENZ: claude_client = anthropic.Anthropic direkt (konsistent mit allen anderen
        # Post-Call-Calls; Bedrock-Frankfurt-Migration = checkpoint Plan 05, nicht hier erfunden).
        response = claude_client.messages.create(
            model=MODEL_JUDGE,
            max_tokens=_JUDGE_MAX_TOKENS,
            temperature=0,
            system=system_str,
            messages=[{'role': 'user', 'content': user_str}],
            tools=[JUDGE_TOOL],
            tool_choice={'type': 'tool', 'name': 'record_observations'},
            # SOFORT-2 (D-03/R-10): blockierender Aufruf im EINZIGEN slow_lane-Consumer-Faden.
            # Ohne Zeitlimit blockiert ein Haenger hier die Nachbearbeitung ALLER Mandanten
            # (SDK-Vorgabe read=600 s).
            # ⚠ BATCH_LLM_TIMEOUT_S, NICHT LIVE_LLM_TIMEOUT_S (Andre-Entscheidung 2026-08-06,
            # Fund E-10): dieser Pfad laeuft NICHT im Live-Gespraech. Die Post-Call-Auswertung
            # dauert insgesamt 15,2 s — 12 s haetten sie gekappt und dem Berater die
            # Coaching-Note genommen. Begruendung der 45 s: config.py, Abschnitt F-7.
            timeout=httpx.Timeout(config.BATCH_LLM_TIMEOUT_S, connect=config.LLM_CONNECT_TIMEOUT_S),
        )

        # ── KOSTEN-1 R2.1 Cost-Hook (Muster: claude_service.py:542-568) ─────────────────────
        # POSITION: unmittelbar nach dem Call, VOR dem Parsen. Weiter unten steht ein
        # `raise ValueError` (fehlender Tool-Use-Block) und darunter der except-Mantel — saesse
        # der Hook dahinter, waere ein bezahlter Sonnet-Lauf bei jeder Parse-Panne unsichtbar.
        # (Anker-Lehre: Interim-Position-Bug 08.19.5.6.4.2 — Code hinter zwei returns war tot.)
        # ATTRIBUTION: Nachlauf-Kontext, kein Flask `g`. user_id kommt aus dem Call-Objekt
        # (calls.user_id, NOT NULL); org_id hat der Call nicht -> ueber den User aufgeloest.
        try:
            from services.cost_tracker import log_api_cost, normalize_model_name, resolve_org_id_from_user
            _u = getattr(response, 'usage', None)
            if _u is not None:
                _m = normalize_model_name(MODEL_JUDGE)
                _uid = getattr(call, 'user_id', None)
                _oid = resolve_org_id_from_user(db, _uid)
                for _units, _unit_type in (
                    ((getattr(_u, 'input_tokens', 0) or 0) / 1000.0, 'per_1k_input_tokens'),
                    ((getattr(_u, 'output_tokens', 0) or 0) / 1000.0, 'per_1k_output_tokens'),
                    ((getattr(_u, 'cache_read_input_tokens', 0) or 0) / 1000.0, 'per_1k_cache_read_tokens'),
                    ((getattr(_u, 'cache_creation_input_tokens', 0) or 0) / 1000.0, 'per_1k_cache_write_tokens'),
                ):
                    if _units > 0:
                        log_api_cost('anthropic', _m, user_id=_uid, org_id=_oid,
                                     units=_units, unit_type=_unit_type,
                                     context_tag='judge', call_site='run_behavior_judge')
        except Exception as _e:
            print(f"[CostHook] judge skipped: {_e}")
        # ───────────────────────────────────────────────────────────────────────────────────

        # ── Parse: Tool-Use-Block extrahieren ───────────────────────────────────────────────
        tool_input = None
        for block in response.content:
            if getattr(block, 'type', None) == 'tool_use' and getattr(block, 'name', None) == 'record_observations':
                tool_input = block.input
                break

        if tool_input is None:
            raise ValueError('Judge-Antwort enthaelt keinen record_observations-Tool-Use-Block')

        observations_jsonb, ratings_jsonb = _parse_judge_output(tool_input)

        return {
            'observations_jsonb': observations_jsonb,
            'ratings_jsonb': ratings_jsonb,
            'dimensions_version': DIMENSIONS_VERSION,
            'status': _STATUS_JUDGED,
        }

    except Exception as exc:
        # Fehler-Mantel (T-HT-03-05): kein Crash des Consumers, status=judge_failed.
        # Der Merge-Gate-UPSERT schreibt dann status=judge_failed in rubric_score.
        call_id = getattr(call, 'id', '?')
        print(f'[JUDGE] judge_failed call={call_id}: {type(exc).__name__}: {exc}')
        return {'status': _STATUS_JUDGE_FAILED, 'error': str(exc)}
