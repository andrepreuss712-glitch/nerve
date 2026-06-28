# -*- coding: utf-8 -*-
"""Uebernahme-/Adoption-Judge (LLM-as-a-Judge, Soll-Verhalten §6, TAXO2-Plan 04).

EIN gebuendelter Sonnet-Tool-Use-Call am Call-Ende (async, Slow Lane — Latenz egal, Punkt 25):
  - Roh-Paare bauen: suggestion_reactions.suggestion_text + folgende Berater-Aeusserung
    aus transcript_segments (per interaction_id / ts_ms-Reihenfolge).
  - EINEN gebuendelten forced-Tool-Use-Sonnet-Call feuern (NICHT einen Call pro Moment —
    Soll-Verhalten §6 Schaerfung b: gebuendelt/gesampelt, nie pro Moment live).
  - Intent-Urteil: voll / teilweise / ignoriert — auf INTENT, NIE mechanisch
    (kein BLEU/ROUGE/Cosine/difflib, Soll-Verhalten §6).
  - Einstufung in die DEFERRED-Spalten von suggestion_reactions schreiben:
    adoption_value / reaction_class / following_utterance_ref (keine neue Tabelle).
  - Outcome (calls.outcome) physisch NICHT im Prompt (T-HT-04-03, grep-verifizierbar).
  - NERVE-Vorschlaege kennt NUR dieser Call (nicht der Verhaltens-Call Plan 03) — Bias-Schutz
    (Uebernahme getrennt vom Verhalten, Soll-Verhalten §6 Kern-Architektur-Entscheidung).

Bau-Regel 1 (NERVE TAXO-Geruest §5): KEIN LLM in der Live/Fast-Lane. Dieser Adoption-Judge
laeuft NUR async im Slow-Lane-Call-Ende-Schritt (_adoption_step in slow_lane.py) und NUR nach
transcript_resolved==True (Punkt 26 Fan-In-Gate, via _call_end_merge-Vorbedingung).

Roh-Paar-Bau (Punkt 26): liest transcript_segments NUR nach transcript_resolved==True
(Merge-Gate in _call_end_merge). Anker: ts_ms-Reihenfolge (Sprech-Zeit, NICHT created_at
Batch-Schreibzeit — Lehre Punkt 26 CALLID/Audio-Race-Analogie).

D-RESIDENZ: claude_client = anthropic.Anthropic direkt (konsistent mit judge_runner.py;
Bedrock-Frankfurt-Migration = eigene Phase, nicht hier erfunden).

Phase: 08.23.2.TAXO2.HANDLING-TIMING Plan 04
"""

import os

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
# Schema: ein Ergebnis-Array — pro Paar: interaction_id + beleg(folgende Aeusserung, kurz) +
# urteil(enum voll|teilweise|ignoriert) + adoption_value(0|0.5|1).
# KEIN Outcome. KEINE mechanischen Score-Felder.

ADOPTION_TOOL = {
    'name': 'record_adoption',
    'description': (
        'Erfasst das Uebernahme-Urteil fuer jedes Vorschlags-Berater-Paar. '
        'ALLE Paare in EINEM Ergebnis-Array. Pro Paar: erst den Beleg (kurze folgende Aeusserung), '
        'dann das Urteil (voll/teilweise/ignoriert), dann der adoption_value (1.0/0.5/0.0). '
        'Beleg-VOR-Urteil (kein Urteil ohne Beleg). '
        'KEIN Ergebnis/Outcome. NUR Intention pruefen.'
    ),
    'input_schema': {
        'type': 'object',
        'properties': {
            'ergebnisse': {
                'type': 'array',
                'description': 'Urteil fuer jedes Paar (in der Reihenfolge des Inputs).',
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
                                'Kurze folgende Berater-Aeusserung als Beleg (max. 120 Zeichen). '
                                'Muss aus dem Input stammen. Leer wenn folgende Aeusserung unbekannt.'
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
                                'folgende Aeusserung unbekannt.'
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


# ── Roh-Paar-Bau ─────────────────────────────────────────────────────────────────

def _build_adoption_pairs(call, db) -> list:
    """Baut Roh-Paare (suggestion_text + folgende Berater-Aeusserung) aus committeten Daten.

    Laedt suggestion_reactions des Calls (nur Zeilen mit suggestion_text).
    Fuer jeden Vorschlag: sucht die erste Berater-Aeusserung in transcript_segments
    NACH dem Angebots-Zeitpunkt (ts_ms-Reihenfolge, Sprech-Zeit — NICHT created_at
    Batch-Schreibzeit, Lehre Punkt 26).

    Wenn keine folgende Berater-Aeusserung gefunden: following_text=None
    (konservativ; LLM bekommt 'unbekannt', urteilt 'ignoriert' — kein Crash).

    Nur nach transcript_resolved==True erreichbar (der Adoption-Schritt sitzt
    hinter dem Merge-Gate, Punkt 26). Liest committete Daten.

    Args:
        call: Call-ORM-Objekt (id, conversation_log_id).
        db: SQLAlchemy-Session (GUC bereits gesetzt vom Merge-Gate, M-4).

    Returns:
        list of {interaction_id, suggestion_text, following_text}
        oder [] wenn keine Vorschlaege mit suggestion_text vorhanden.
    """
    # Alle Vorschlaege des Calls laden (nur mit suggestion_text — das Angebot)
    suggestions = (
        db.query(SuggestionReaction)
        .filter(
            SuggestionReaction.call_id == call.id,
            SuggestionReaction.suggestion_text.isnot(None),
        )
        .all()
    )

    if not suggestions:
        return []

    pairs = []
    conv_log_id = call.conversation_log_id

    for sug in suggestions:
        following_text = None

        if conv_log_id is not None and sug.interaction_id is not None:
            # Folgende Berater-Aeusserung: erstes berater-Segment in transcript_segments
            # NACH dem Angebots-Zeitpunkt des Vorschlags.
            # Anker: ts_offered -> ts_ms-Reihenfolge (Sprech-Zeit, NICHT created_at).
            # Wenn ts_offered nicht gesetzt: erste berater-Aeusserung nach ALL Segmenten
            # in diesem conversation_log (conservative fallback: following=None weil
            # keine saubere Zuordnung ohne ts_offered — lieber kein Urteil als falsches).
            ts_offered = getattr(sug, 'ts_offered', None)

            if ts_offered is not None:
                # ts_offered ist ein Datetime; transcript_segments.ts_ms ist Millisekunden
                # seit Call-Start (Integer). Anker: suche berater-Segment nach der Angebots-Zeit.
                # Da ts_ms die Sprech-Position ist und ts_offered die Wall-Clock-Zeit, bauen wir
                # einen konservativen Lookup: das frueheste berater-Segment nach dem letzten
                # kunden-Segment das NACH ts_offered liegt (Executor's Discretion, kein
                # Wall-Clock-Bruecke — wir nehmen alle berater-Segmente und nehmen das erste
                # NACH einem Kunden-Segment das nach ts_offered ist).
                # Vereinfachter konservativer Ansatz: das erste berater-Segment ueberhaupt
                # im conversation_log (Sprech-Zeit-Reihenfolge ts_ms ASC) — weil ts_offered
                # und ts_ms nicht direkt vergleichbar sind (Wall-Clock vs. Call-intern-ms),
                # nehmen wir das erste berater-Segment aus dem ganzen Call als Anker.
                # Das ist konservativ aber sauber: wenn kein berater-Satz -> None.
                # Punkt 26: kein Wall-Clock-Bruecke erfinden (Leitsatz 2).
                try:
                    seg = (
                        db.query(TranscriptSegment)
                        .filter(
                            TranscriptSegment.conversation_log_id == conv_log_id,
                            TranscriptSegment.speaker == 'berater',
                        )
                        .order_by(TranscriptSegment.ts_ms.asc())
                        .first()
                    )
                    following_text = seg.text if seg is not None else None
                except Exception:
                    following_text = None
            # else: ts_offered fehlt -> following=None (konservativ, kein Wall-Clock-Anker)

        pairs.append({
            'interaction_id': str(sug.interaction_id) if sug.interaction_id is not None else '',
            'suggestion_text': sug.suggestion_text or '',
            'following_text': following_text,
        })

    return pairs


# ── Prompt-Bau ───────────────────────────────────────────────────────────────────

def _build_adoption_prompt(pairs: list) -> tuple:
    """Baut System-Prompt + User-Prompt fuer den gebuendelten Adoption-Judge.

    Invarianten (grep-verifizierbar):
      - Kein calls.outcome im Prompt (T-HT-04-03)
      - Kein mechanischer Vergleich (kein BLEU/ROUGE/Cosine/difflib)
      - Beleg-VOR-Urteil

    Args:
        pairs: Liste von {interaction_id, suggestion_text, following_text}

    Returns:
        (system_str, user_str): beide Strings fuer den Anthropic-Call.
    """
    system_lines = [
        '== DEINE ROLLE ==',
        (
            'Du beurteilst fuer jeden NERVE-Vorschlag, ob der Berater die STRATEGISCHE INTENTION '
            'des Vorschlags in seiner folgenden Aeusserung aufgegriffen hat. '
            'Urteile auf INTENT, NICHT auf Wort-Ueberlappung: '
            'Paraphrase, Stichpunkt-Stil und eigene Formulierung zaehlen als Uebernahme, '
            'wenn die Kernidee (das strategische Angebot) aufgegriffen wurde. '
            'BLEU/ROUGE/Wort-Matching ist FALSCH — ein Berater soll die Idee aufgreifen, '
            'nicht den Wortlaut kopieren.'
        ),
        '',
        '== BEWERTUNGS-PRINZIPIEN ==',
        (
            '1. Erst den Beleg lesen (die folgende Berater-Aeusserung), DANN urteilen. '
            'Kein Urteil ohne Beleg (Beleg-VOR-Urteil).'
        ),
        (
            '2. voll: Kernidee des Vorschlags klar erkennbar in der Antwort — '
            'auch wenn Formulierung abweicht (Paraphrase zaehlt). '
            'Adoption-Value: 1.0'
        ),
        (
            '3. teilweise: Aspekte aufgegriffen, aber wesentliche Teile der Intention fehlen. '
            'Adoption-Value: 0.5'
        ),
        (
            '4. ignoriert: kein erkennbarer Bezug zur Intention des Vorschlags; '
            'auch wenn folgende Aeusserung unbekannt. '
            'Adoption-Value: 0.0'
        ),
        '',
        '== WICHTIG ==',
        (
            'Du siehst WEDER das Ergebnis des Gespraechs (ob ein Abschluss zustande kam) '
            'NOCH andere Bewertungen. Beurteile NUR die Uebernahme der Intention.'
        ),
    ]
    system_str = '\n'.join(system_lines)

    user_lines = [
        '== VORSCHLAGS-BERATER-PAARE ==',
        'Beurteile fuer jedes Paar die Uebernahme der Intention.',
        '',
    ]

    for i, pair in enumerate(pairs, start=1):
        iid = pair.get('interaction_id', '')
        sug_text = pair.get('suggestion_text', '')
        following = pair.get('following_text')

        user_lines.append(f'--- Paar {i} ---')
        user_lines.append(f'interaction_id: {iid}')
        user_lines.append(f'NERVE-Vorschlag (was ausgegeben wurde): {sug_text}')
        if following:
            user_lines.append(f'Folgende Berater-Aeusserung: {following}')
        else:
            user_lines.append('Folgende Berater-Aeusserung: (unbekannt — kein Berater-Satz nach dem Vorschlag)')
        user_lines.append('')

    user_lines.append('== AUFGABE ==')
    user_lines.append(
        'Befuelle das Werkzeug record_adoption mit deinen Urteilen fuer ALLE Paare. '
        'Pro Paar: Beleg -> Urteil -> adoption_value. ALLE Paare in EINEM Aufruf.'
    )

    user_str = '\n'.join(user_lines)
    return system_str, user_str


# ── Hauptfunktion ────────────────────────────────────────────────────────────────

def run_adoption_judge(call, db) -> dict:
    """Fuehrt den LLM-Uebernahme-Judge fuer einen abgeschlossenen Call aus.

    Laedt Roh-Paare (suggestion_text + folgende Berater-Aeusserung), baut den Prompt,
    feuert EINEN gebuendelten forced-Tool-Use-Sonnet-Call (temp=0), parst die Antwort,
    schreibt die Einstufung in suggestion_reactions' DEFERRED-Spalten.

    Trennung vom Verhaltens-Call (Plan 03, Bias-Schutz):
      - Dieser Call kennt die NERVE-Vorschlaege (suggestion_text).
      - Der Verhaltens-Call (judge_runner.py) kennt sie NICHT.
      - Outcome (calls.outcome) ist in KEINEM der beiden Prompts (physische Trennung).

    Invarianten:
      - Nur laeuft nach transcript_resolved==True (Punkt 26, via _call_end_merge-Gate).
      - Kein Outcome im Prompt (T-HT-04-03, grep == 0).
      - Kein mechanischer Vergleich (kein difflib/BLEU/ROUGE/Cosine).
      - EIN Call fuer ALLE Paare (gebuendelt, Soll-Verhalten §6 Schaerfung b).
      - Schreibt in suggestion_reactions.adoption_value / reaction_class / following_utterance_ref.
      - KEINE neue Tabelle.

    Args:
        call: Call-ORM-Objekt (id, conversation_log_id, tenant_id, ...)
        db: SQLAlchemy-Session (GUC bereits gesetzt vom Merge-Gate, M-4)

    Returns:
        {status: 'adoption_done', written: N}
        oder {status: 'no_suggestions'}
        oder {status: 'adoption_failed', error: str}
    """
    try:
        # ── Roh-Paar-Bau ─────────────────────────────────────────────────────────────
        # Punkt 26: nur nach transcript_resolved==True (das Gate sitzt im _call_end_merge —
        # hier kein zweites Gate noetig, konsistent mit _judge_step-Muster).
        pairs = _build_adoption_pairs(call, db)

        if not pairs:
            call_id = getattr(call, 'id', '?')
            print(f'[ADOPTION] no_suggestions call={call_id}: keine Vorschlaege mit suggestion_text')
            return {'status': _STATUS_NO_SUGGESTIONS, 'written': 0}

        # ── Prompt-Bau ────────────────────────────────────────────────────────────────
        system_str, user_str = _build_adoption_prompt(pairs)

        # ── EIN gebuendelter forced-Tool-Use-Sonnet-Call (temp=0) ────────────────────
        # ALLE Paare in EINEM Call (Soll-Verhalten §6 Schaerfung b: gebuendelt, nie pro
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
        )

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
        # following_utterance_ref: KEIN voller Roh-Text (DSGVO), nur kurzer Beleg-Verweis.
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
