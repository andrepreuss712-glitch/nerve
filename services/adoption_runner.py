# -*- coding: utf-8 -*-
"""Uebernahme-/Adoption-Judge (LLM-as-a-Judge, Soll-Verhalten §6, TAXO2-Plan 04/06).

EIN gebuendelter Sonnet-Tool-Use-Call am Call-Ende (async, Slow Lane — Latenz egal, Punkt 25):
  - Ganzes anonymisiertes Transkript (transcript_segments ts_ms ASC) UND
    Vorschlags-Liste (interaction_id + suggestion_text) an den LLM senden.
  - EINEN gebuendelten forced-Tool-Use-Sonnet-Call feuern (NICHT einen Call pro Moment —
    Soll-Verhalten §6 Schaerfung b: gebuendelt/gesampelt, nie pro Moment live).
  - LLM urteilt selbst je interaction_id (voll/teilweise/ignoriert + Beleg-Zitat) auf
    Basis des Gesamttranskripts — KEIN mechanisches Pairing, KEIN BLEU/ROUGE/Cosine/difflib.
  - Einstufung in die DEFERRED-Spalten von suggestion_reactions schreiben:
    adoption_value / reaction_class / following_utterance_ref (keine neue Tabelle).
  - Outcome (calls.outcome) physisch NICHT im Prompt (T-HT-04-03, grep-verifizierbar).
  - NERVE-Vorschlaege kennt NUR dieser Call (nicht der Verhaltens-Call Plan 03) — Bias-Schutz
    (Uebernahme getrennt vom Verhalten, Soll-Verhalten §6 Kern-Architektur-Entscheidung).

Bau-Regel 1 (NERVE TAXO-Geruest §5): KEIN LLM in der Live/Fast-Lane. Dieser Adoption-Judge
laeuft NUR async im Slow-Lane-Call-Ende-Schritt (_adoption_step in slow_lane.py) und NUR nach
transcript_resolved==True (Punkt 26 Fan-In-Gate, via _call_end_merge-Vorbedingung).

Transkript-Laden (Punkt 26): liest transcript_segments NUR nach transcript_resolved==True
(Merge-Gate in _call_end_merge). Anker: ts_ms-Reihenfolge (Sprech-Zeit, NICHT created_at
Batch-Schreibzeit — Lehre Punkt 26 CALLID/Audio-Race-Analogie).

D-RESIDENZ: claude_client = anthropic.Anthropic direkt (konsistent mit judge_runner.py;
Bedrock-Frankfurt-Migration = eigene Phase, nicht hier erfunden).

Phase: 08.23.2.TAXO2.HANDLING-TIMING Plan 04/06 (Gap-Closure: _build_adoption_pairs entfernt)
"""

import os

import httpx  # SOFORT-2 (D-03): httpx.Timeout je Aufruf — Abhaengigkeit von anthropic, kein neues Paket
import config
from database.models import SuggestionReaction, TranscriptSegment
from services.claude_service import claude_client

# ── Modell-Konstante (ENV-Override, Punkt 12) ────────────────────────────────────
# MODEL_ADOPTION: ENV-Override fuer den Uebernahme-Judge. Default: MODEL_POSTCALL_ANALYSIS (Sonnet).
MODEL_ADOPTION = os.getenv('MODEL_ADOPTION', config.MODEL_POSTCALL_ANALYSIS)

# ── Max-Tokens (Slow Lane, Latenz egal) ─────────────────────────────────────────
_ADOPTION_MAX_TOKENS = 2048

# ── Status-Konstanten ────────────────────────────────────────────────────────────
_STATUS_ADOPTION_DONE = 'adoption_done'
_STATUS_NO_SUGGESTIONS = 'no_suggestions'
_STATUS_ADOPTION_FAILED = 'adoption_failed'

# ── following_utterance_ref: max. Laenge des Beleg-Verweises (DSGVO — KEIN voller Text) ──────
_FOLLOWING_REF_MAX = 120

# ── ADOPTION_TOOL: erzwungenes JSON-Schema (Anthropic Tool-Use / forced tool_choice) ──────────
# Schema: ein Ergebnis-Array — pro Vorschlag: interaction_id + beleg(LLM-identifiziertes Zitat,
# kurz) + urteil(enum voll|teilweise|ignoriert) + adoption_value(0|0.5|1).
# KEIN Outcome. KEINE mechanischen Score-Felder.

ADOPTION_TOOL = {
    'name': 'record_adoption',
    'description': (
        'Erfasst das Uebernahme-Urteil fuer jeden NERVE-Vorschlag. '
        'ALLE Vorschlaege in EINEM Ergebnis-Array. Pro Vorschlag: erst den Beleg (woertliches '
        'Zitat aus dem Transkript), dann das Urteil (voll/teilweise/ignoriert), '
        'dann der adoption_value (1.0/0.5/0.0). '
        'Beleg-VOR-Urteil (kein Urteil ohne Beleg). '
        'KEIN Ergebnis/Outcome. NUR Intention pruefen.'
    ),
    'input_schema': {
        'type': 'object',
        'properties': {
            'ergebnisse': {
                'type': 'array',
                'description': 'Urteil fuer jeden Vorschlag (in der Reihenfolge des Inputs).',
                'items': {
                    'type': 'object',
                    'properties': {
                        'interaction_id': {
                            'type': 'string',
                            'description': 'Die interaction_id des Moments (unveraendert aus dem Input).',
                        },
                        'beleg': {
                            'type': 'string',
                            'description': (
                                'Woertliches Zitat aus dem Transkript als Beleg (max. 120 Zeichen). '
                                'Muss aus dem Transkript stammen. Leer wenn Berater danach gar nicht gesprochen hat.'
                            ),
                        },
                        'urteil': {
                            'type': 'string',
                            'enum': ['voll', 'teilweise', 'ignoriert'],
                            'description': (
                                'voll = Berater griff die strategische INTENTION des Vorschlags '
                                'auf (Paraphrase/Stichpunkt-Stil zaehlt — NUR Intent, nicht Wortlaut). '
                                'teilweise = Teilaspekte aufgegriffen. '
                                'ignoriert = kein erkennbarer Bezug zur Intention; auch wenn '
                                'Berater danach gar nicht gesprochen hat.'
                            ),
                        },
                        'adoption_value': {
                            'type': 'number',
                            'description': (
                                'Numerischer Wert: 1.0 (voll) / 0.5 (teilweise) / 0.0 (ignoriert).'
                            ),
                        },
                    },
                    'required': ['interaction_id', 'beleg', 'urteil', 'adoption_value'],
                },
            },
        },
        'required': ['ergebnisse'],
    },
}


# ── Prompt-Bau ───────────────────────────────────────────────────────────────────

def _build_adoption_prompt(transcript_segments, suggestions) -> tuple:
    """Baut System-Prompt + User-Prompt fuer den gebuendelten Adoption-Judge.

    Empfaengt das GANZE anonymisierte Transkript (transcript_segments ts_ms ASC, alle
    speaker+text+ts_ms) und die Vorschlags-Liste (interaction_id + suggestion_text).
    Das LLM selbst urteilt je interaction_id auf Basis des Gesamt-Transkripts —
    KEIN mechanisches Pairing, KEIN Wall-Clock/ts_ms-Anker.

    Invarianten (grep-verifizierbar):
      - Kein calls.outcome im Prompt (T-HT-04-03)
      - Kein mechanischer Vergleich (kein BLEU/ROUGE/Cosine/difflib)
      - Beleg-VOR-Urteil
      - ts_offered wird NICHT in den Prompt eingebettet (Wall-Clock vs. ts_ms unvergleichbar)

    Args:
        transcript_segments: Liste von TranscriptSegment-Objekten (ts_ms ASC vorsortiert)
        suggestions: Liste von SuggestionReaction-Objekten (mit interaction_id + suggestion_text)

    Returns:
        (system_str, user_str): beide Strings fuer den Anthropic-Call.
    """
    system_lines = [
        '== DEINE ROLLE ==',
        (
            'Du beurteilst fuer jeden NERVE-Vorschlag im Transkript, ob der Berater die '
            'STRATEGISCHE INTENTION des Vorschlags aufgegriffen hat. Urteile auf INTENT, '
            'NICHT auf Wort-Ueberlappung: Paraphrase und eigene Formulierung zaehlen als '
            'Uebernahme, wenn die Kernidee aufgegriffen wurde.'
        ),
        '',
        '== BEWERTUNGS-PRINZIPIEN ==',
        (
            '1. Lese das GANZE Transkript der Reihe nach. Beurteile je Vorschlag was der '
            'Berater DANACH gesagt hat (nicht nur der naechste Satz — auch spaetere '
            'Saetze koennen die Intention aufgreifen).'
        ),
        '2. voll (1.0): Kernidee klar aufgegriffen — auch bei abweichender Formulierung.',
        '3. teilweise (0.5): Aspekte aufgegriffen, wesentliche Teile der Intention fehlen.',
        (
            '4. ignoriert (0.0): kein erkennbarer Bezug zur Intention; auch wenn der Berater '
            'nach dem Vorschlag schweigt oder das Gespraech abbricht.'
        ),
        (
            '5. Beleg-VOR-Urteil: erst das woertliche Zitat aus dem Transkript, dann das Urteil. '
            'Kein Urteil ohne Beleg (leeres beleg nur wenn Berater danach gar nicht gesprochen hat).'
        ),
        '',
        '== WICHTIG ==',
        (
            'Du siehst WEDER das Ergebnis des Gespraechs (kein Abschluss/Ablehnung-Info) '
            'NOCH andere Bewertungen. Beurteile NUR die Uebernahme der Intention.'
        ),
    ]
    system_str = '\n'.join(system_lines)

    user_lines = []

    # Sektion 1 — ganzes Transkript (chronologisch, ts_ms ASC)
    user_lines.append('== TRANSKRIPT (chronologisch, ts_ms ASC) ==')
    if transcript_segments:
        for i, seg in enumerate(transcript_segments, start=1):
            speaker = getattr(seg, 'speaker', 'unbekannt')
            ts_ms = getattr(seg, 'ts_ms', 0)
            text = getattr(seg, 'text', '')
            user_lines.append(f'[#{i} {speaker} {ts_ms}ms] {text}')
    else:
        user_lines.append('(Kein Transkript verfuegbar — kein Urteil moeglich)')
    user_lines.append('')

    # Sektion 2 — Vorschlags-Liste (interaction_id + suggestion_text)
    # ts_offered wird NICHT eingebettet: Wall-Clock vs. ts_ms unvergleichbar (Punkt 27)
    user_lines.append('== NERVE-VORSCHLAEGE (zu beurteilen) ==')
    for i, sug in enumerate(suggestions, start=1):
        iid = str(sug.interaction_id) if sug.interaction_id is not None else ''
        sug_text = sug.suggestion_text or ''
        user_lines.append(f'Vorschlag #{i}: interaction_id={iid} | Text: "{sug_text}"')
    user_lines.append('')

    # Sektion 3 — Aufgabe
    user_lines.append('== AUFGABE ==')
    user_lines.append(
        'Lies das Transkript von oben nach unten. Finde fuer jeden NERVE-Vorschlag, '
        'ob und wie der Berater die strategische Intention danach aufgegriffen hat. '
        'Befuelle das Werkzeug record_adoption mit einem Urteil pro Vorschlag. '
        'Alle Vorschlaege in EINEM Aufruf. Beleg -> Urteil -> adoption_value.'
    )

    user_str = '\n'.join(user_lines)
    return system_str, user_str


# ── Hauptfunktion ────────────────────────────────────────────────────────────────

def run_adoption_judge(call, db) -> dict:
    """Fuehrt den LLM-Uebernahme-Judge fuer einen abgeschlossenen Call aus.

    Laedt das GANZE anonymisierte Transkript (transcript_segments ts_ms ASC) und die
    Vorschlags-Liste (interaction_id + suggestion_text), baut den Prompt, feuert EINEN
    gebuendelten forced-Tool-Use-Sonnet-Call (temp=0), parst die Antwort und schreibt
    die Einstufung in suggestion_reactions' DEFERRED-Spalten.

    Das LLM selbst urteilt je interaction_id auf Basis des Gesamttranskripts —
    KEIN mechanisches Pairing (Punkt 27: einfachster tragfaehiger Weg).

    Trennung vom Verhaltens-Call (Plan 03, Bias-Schutz):
      - Dieser Call kennt die NERVE-Vorschlaege (suggestion_text).
      - Der Verhaltens-Call (judge_runner.py) kennt sie NICHT.
      - Outcome (calls.outcome) ist in KEINEM der beiden Prompts (physische Trennung).

    Invarianten:
      - Nur laeuft nach transcript_resolved==True (Punkt 26, via _call_end_merge-Gate).
      - Kein Outcome im Prompt (T-HT-04-03, grep == 0).
      - Kein mechanischer Vergleich (kein difflib/BLEU/ROUGE/Cosine).
      - EIN Call fuer ALLE Vorschlaege (gebuendelt, Soll-Verhalten §6 Schaerfung b).
      - Schreibt in suggestion_reactions.adoption_value / reaction_class / following_utterance_ref.
      - KEINE neue Tabelle.
      - following_utterance_ref: LLM-identifiziertes woertliches Zitat aus dem Gesamttranskript
        (max. 120 Zeichen, DSGVO).

    Args:
        call: Call-ORM-Objekt (id, conversation_log_id, tenant_id, ...)
        db: SQLAlchemy-Session (GUC bereits gesetzt vom Merge-Gate, M-4)

    Returns:
        {status: 'adoption_done', written: N}
        oder {status: 'no_suggestions'}
        oder {status: 'adoption_failed', error: str}
    """
    try:
        # ── Vorschlaege laden (suggestion_text gesetzt, FOLD A) ───────────────────────
        # Punkt 26: nur nach transcript_resolved==True (das Gate sitzt im _call_end_merge —
        # hier kein zweites Gate noetig, konsistent mit _judge_step-Muster).
        suggestions = (
            db.query(SuggestionReaction)
            .filter(
                SuggestionReaction.call_id == call.id,
                SuggestionReaction.suggestion_text.isnot(None),
            )
            .all()
        )

        if not suggestions:
            call_id = getattr(call, 'id', '?')
            print(f'[ADOPTION] no_suggestions call={call_id}: keine Vorschlaege mit suggestion_text')
            return {'status': _STATUS_NO_SUGGESTIONS, 'written': 0}

        # ── Ganzes Transkript laden (ts_ms ASC — Sprech-Zeit, NICHT created_at) ──────
        # Punkt 26: nur nach transcript_resolved==True (Gate im _call_end_merge).
        # Anker: ts_ms (Sprech-Zeit), NICHT created_at (Batch-Schreibzeit wertlos).
        segments = (
            db.query(TranscriptSegment)
            .filter(
                TranscriptSegment.conversation_log_id == call.conversation_log_id,
            )
            .order_by(TranscriptSegment.ts_ms.asc())
            .all()
        ) if call.conversation_log_id else []

        # ── Prompt-Bau ────────────────────────────────────────────────────────────────
        system_str, user_str = _build_adoption_prompt(segments, suggestions)

        # ── EIN gebuendelter forced-Tool-Use-Sonnet-Call (temp=0) ────────────────────
        # ALLE Vorschlaege in EINEM Call (Soll-Verhalten §6 Schaerfung b: gebuendelt, nie pro
        # Moment live). KEIN Outcome. KEIN mechanischer Vergleich.
        # D-RESIDENZ: claude_client = anthropic.Anthropic direkt (Plan 05-Checkpoint).
        response = claude_client.messages.create(
            model=MODEL_ADOPTION,
            max_tokens=_ADOPTION_MAX_TOKENS,
            temperature=0,
            system=system_str,
            messages=[{'role': 'user', 'content': user_str}],
            tools=[ADOPTION_TOOL],
            tool_choice={'type': 'tool', 'name': 'record_adoption'},
            # SOFORT-2 (D-03/R-10): blockierender Aufruf im EINZIGEN slow_lane-Consumer-Faden.
            # Ohne Zeitlimit blockiert ein Haenger hier die Nachbearbeitung ALLER Mandanten
            # (SDK-Vorgabe read=600 s). => LIVE_LLM_TIMEOUT_S, derselbe Mechanismus wie live.
            timeout=httpx.Timeout(config.LIVE_LLM_TIMEOUT_S, connect=config.LLM_CONNECT_TIMEOUT_S),
        )

        # ── KOSTEN-1 R2.2 Cost-Hook (Muster: claude_service.py:542-568) ──────────────
        # POSITION wie im Judge-Runner: direkt nach dem Call, VOR dem Parsen — unten
        # folgt ein `raise ValueError` (fehlender Tool-Use-Block) im except-Mantel.
        # Der zweite Sonnet-Lauf pro Call; zusammen mit dem Judge die groesste bisher
        # unsichtbare Position nach der Live-STT.
        try:
            from services.cost_tracker import log_api_cost, normalize_model_name, resolve_org_id_from_user
            _u = getattr(response, 'usage', None)
            if _u is not None:
                _m = normalize_model_name(MODEL_ADOPTION)
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
                                     context_tag='adoption', call_site='run_adoption_judge')
        except Exception as _e:
            print(f"[CostHook] adoption skipped: {_e}")
        # ─────────────────────────────────────────────────────────────────────────────

        # ── Parse: Tool-Use-Block extrahieren ─────────────────────────────────────────
        tool_input = None
        for block in response.content:
            if (getattr(block, 'type', None) == 'tool_use'
                    and getattr(block, 'name', None) == 'record_adoption'):
                tool_input = block.input
                break

        if tool_input is None:
            raise ValueError('Adoption-Antwort enthaelt keinen record_adoption-Tool-Use-Block')

        ergebnisse = tool_input.get('ergebnisse') or []

        # ── Write: Einstufung in suggestion_reactions (DEFERRED-Spalten) ─────────────
        # Under Tenant-GUC (der Schritt laeuft in der M-4-GUC-Klammer von _call_end_merge).
        # IN-PLACE-UPDATE der existing Zeilen (per interaction_id).
        # following_utterance_ref: LLM-identifiziertes woertliches Zitat (DSGVO, max. 120 Zeichen).
        written = 0
        for res in ergebnisse:
            iid = res.get('interaction_id')
            urteil = res.get('urteil')
            adv = res.get('adoption_value')
            beleg = (res.get('beleg') or '')[:_FOLLOWING_REF_MAX]

            if not iid:
                continue

            # Suche die Zeile per interaction_id (unter M-4-GUC -> FORCE RLS)
            row = (
                db.query(SuggestionReaction)
                .filter(
                    SuggestionReaction.interaction_id == iid,
                    SuggestionReaction.call_id == call.id,
                )
                .first()
            )

            if row is None:
                continue

            # Schreibe die DEFERRED-Spalten (jetzt befuellt, ab TAXO2 Plan 04)
            row.adoption_value = float(adv) if adv is not None else None
            row.reaction_class = urteil if urteil in ('voll', 'teilweise', 'ignoriert') else None
            row.following_utterance_ref = beleg if beleg else None
            written += 1

        call_id = getattr(call, 'id', '?')
        print(f'[ADOPTION] adoption_done call={call_id}: written={written}')
        return {'status': _STATUS_ADOPTION_DONE, 'written': written}

    except Exception as exc:
        # Fehler-Mantel: kein Crash des Consumers, status=adoption_failed.
        # Idempotenter Re-Run ist sauber (DEFERRED-Spalten sind nullable).
        call_id = getattr(call, 'id', '?')
        print(f'[ADOPTION] adoption_failed call={call_id}: {type(exc).__name__}: {exc}')
        return {'status': _STATUS_ADOPTION_FAILED, 'error': str(exc)}
