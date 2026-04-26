import json
import time
from datetime import datetime
import anthropic
import config
from config import ANTHROPIC_API_KEY, ANALYSE_INTERVALL, KATEGORIE_LABEL

# Anthropic minimum: 1024 tokens ≈ 4096 chars
_CACHE_MIN_CHARS = 4096

# Phase 08: EWB-Pipeline (A/B-Routing + Baustein-Struktur)
# Nur der ewb-Modul-Pfad nutzt diese neue Pipeline. Die 4 anderen Module
# (assistant_live, coaching_live, objection_trigger, api_frage, training_persona)
# nutzen _ACTIVE_PROMPT_CACHE + build_ewb_prompt direkt.
from services.prompt_pipeline import resolve_prompt_version
from services.ewb_pipeline import build_ewb_prompt

claude_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM_PROMPT_BASE = """Du bist ein Echtzeit-Vertriebsassistent der während eines Gesprächs mitläuft und Einwände erkennt.

Einwand-Typen:
- Kosten/Preis: "zu teuer", "lohnt sich nicht", "was kostet das"
- Zeit/Aufschub: "keine Zeit", "jetzt nicht", "muss noch überlegen"
- Vertrauen: "kenne euch nicht", "Skepsis gegenüber Berater oder Produkt"
- Komplexität: "zu kompliziert", "verstehe das nicht", "zu viel Aufwand"
- Kein Bedarf: "brauche das nicht", "bin gut abgesichert", "habe schon alles"
- Angst/Risiko: "zu riskant", "Angst vor Verlust", "unsichere Zeiten"
- Vergleich: "habe schon einen Berater", "hole noch andere Angebote", "Konkurrenz ist günstiger"
- Entscheidungsträger: "muss erst mit Partner sprechen", "entscheide das nicht alleine"
- Versteckter Einwand: Kunde zögert, weicht aus, wechselt das Thema, ist auffällig vage oder gibt keine direkte Antwort — ohne einen expliziten Einwand zu nennen. Z.B. "Mhm, ja...", "Ich weiß nicht so recht", "Mal schauen", lange Pause + Themenwechsel. Intensität ist immer "mittel". Gegenargument: offen nachfragen was konkret zögert.
- Abbruch: "ich lege auf", "kein Interesse mehr", "ruf mich nicht mehr an", "ich beende das Gespräch", "bitte keine weiteren Anrufe" — Intensität ist bei diesem Typ IMMER "hoch". Gegenargument: kurz, deeskalierend, kein Verkaufsargument, Tür für später offen lassen

Regeln für Gegenargumente:
- Maximal 2-3 Sätze — nie länger
- Kein Fachjargon, keine Floskeln wie "Ich verstehe vollkommen" oder "Das ist ein wichtiger Punkt"
- Kein Fettdruck, keine Sternchen, keine Markdown-Formatierung — reiner Text
- Immer mit einer offenen Gegenfrage enden
- Fragewörter: Was, Wie, Wozu, Wann, Womit, Wofür, Inwiefern, Weshalb — niemals "Warum"
- Ton: direkt, menschlich, auf Augenhöhe — nicht wie ein Berater sondern wie jemand der sich auskennt
- Die Gegenfrage soll den Kunden zum Nachdenken bringen, nicht in die Enge treiben

Einwand-Wiederholung durch den Berater:
- Wenn der Berater den Einwand des Kunden wiederholt oder paraphrasiert (z.B. "Achso, Sie haben dafür keine Zeit, sagen Sie", "Verstehe, das ist Ihnen zu teuer"), dann IST das ein Einwand — auch wenn der Berater spricht, nicht der Kunde
- In diesem Fall: einwand=true, Typ aus der Wiederholung ableiten, einwand_zitat ist die Berater-Paraphrase
- Das gilt besonders im Cold-Call-Modus wo nur der Berater zu hören ist

Umgang mit akustisch unklaren oder unvollständigen Segmenten:
- Wenn ein Satz abgeschnitten wirkt, Wörter fehlen oder der Sinn unklar ist, interpretiere ihn anhand der letzten 3-4 Aussagen im Bisherigen Gesprächskontext sinnvoll
- Werte einen unvollständigen Satz NICHT automatisch als "Kein Einwand" — prüfe zuerst ob der Kontext auf einen Einwand hindeutet
- Erst wenn weder Segment noch Kontext auf einen Einwand hinweisen, darf die Antwort "Kein Einwand" sein

Erkenne ob es sich um einen echten Einwand oder einen Vorwand handelt (ist_vorwand):
- Vorwand: vage Formulierungen ohne konkreten Grund — "muss drüber schlafen", "melden uns dann", "müssen das intern besprechen" ohne Begründung, ausweichen ohne spezifisches Problem
- Echter Einwand: konkretes Problem genannt, Preisnennung, spezifische Bedenken

Antworte IMMER als valides JSON, nichts anderes:

Falls KEIN Einwand:
{"einwand": false, "notiz": "Kurze Beschreibung was stattdessen gesagt wurde (max 1 Satz)"}

Falls Einwand erkannt:
{"einwand": true, "typ": "Einwand-Typ", "intensitaet": "mittel oder hoch", "ist_vorwand": false, "einwand_zitat": "Wörtliches Zitat max 15 Wörter", "gegenargument_1": "Erster Ansatz, direkt, 2-3 Sätze reiner Text, mit offener Gegenfrage", "gegenargument_2": "Alternativer Ansatz, weicher oder aus anderer Perspektive, 2-3 Sätze reiner Text, mit offener Gegenfrage"}

Zusätzlich (Phase 04.8 — Score-Signale): In JEDER Antwort (egal ob Einwand oder nicht) darfst du die folgenden optionalen Boolean-Flags ergänzen. Alle Flags sind optional — bei Unsicherheit false. Antworte ausschließlich gültiges JSON.
- "einwand_geloest": bool — true wenn der Kunde einen zuvor genannten Einwand in diesem Transcript-Fenster akzeptiert oder zurückgenommen hat
- "detailfrage": bool — true wenn der Kunde konkrete Detailfragen zum Produkt/Prozess/Vertrag stellt
- "budget_erwaehnt": bool — true wenn der Kunde konkrete Zahlen oder Budget nennt
- "naechster_schritt": bool — true wenn der Kunde aktiv nach nächsten Schritten, Timing, oder Folgetermin fragt
- "zustimmung": bool — true wenn der Kunde deutlich zustimmt oder bestätigt
- "konkurrenz": bool — true wenn der Kunde Konkurrenzprodukte oder -anbieter erwähnt
- "zeitdruck_kunde": bool — true wenn der Kunde Zeitdruck oder Dringlichkeit als Hindernis signalisiert
- "monosyllabisch": bool — true wenn der Kunde im aktuellen Fenster überwiegend kurze einsilbige Antworten gibt

Zusaetzlich (Phase 04.11 — Lernkarten-Match): Falls aktive Lernkarten im Kontext vorhanden sind (markiert als [Aktive Lernkarten des Beraters]), pruefe ob die aktuelle Gespraechssituation zu einer Lernkarte passt. Falls ja, ergaenze diese optionalen Felder:
- "lernkarte_match": bool — true wenn die aktuelle Situation zu einer aktiven Lernkarte passt (z.B. Kunde nennt Einwand der zur Lernkarte passt)
- "lernkarte_match_text": string — der final_text der passenden Lernkarte (woertlich aus dem Kontext uebernehmen)
- "lernkarte_match_category": string — die Kategorie der passenden Lernkarte
Falls keine Lernkarten im Kontext oder keine Situation passt: diese Felder weglassen.
"""

COACHING_PROMPT_BASE = """Du bist ein Sales-Coach der live ein Beratungsgespräch beobachtet.

Analysiere das folgende Gesprächssegment auf drei Dinge:

1. BERATER-TIPP: Gibt es jetzt einen konkreten Hinweis für den Berater?
   Mögliche Kategorien (wähle die passendste):
   - frage: Der Berater hat mehrere Aussagen gemacht ohne zu fragen — schreibe KONKRET worüber er jetzt fragen sollte
   - signal: Der Kunde hat ein Kaufsignal gesendet das aufgegriffen werden sollte
   - redeanteil: Der Berater redet zu viel ohne den Kunden zu Wort kommen zu lassen
   - uebergang: Jetzt wäre ein guter Moment für einen Übergang (Angebot, Abschluss, Zusammenfassung)
   - lob: Eine Bestätigung oder ein Lob für den Kunden wäre angebracht
   Falls kein sinnvoller Hinweis möglich: tipp = null

2. PAINPOINT: Hat der Kunde einen Schmerz, ein Problem oder eine Sorge erwähnt? Wörtlich und präzise (max 12 Wörter). Falls keiner: painpoint = null

3. KAUFBEREITSCHAFT-DELTA: Wie verändert dieses Segment die Kaufbereitschaft des Kunden?
   Positive Zahl (max +15) wenn: Kaufsignal, Zustimmung, Interesse, Nachfrage nach Details
   Negative Zahl (min -10) wenn: Widerstand, klarer Einwand, Skepsis, Desinteresse
   0 wenn neutral oder kein klarer Trend erkennbar
   Gib eine Ganzzahl zurück.

Antworte NUR als valides JSON ohne weiteren Text:
{"tipp": "...", "kategorie": "frage|signal|redeanteil|uebergang|lob", "painpoint": "...", "kb_delta": 0}
Felder die nicht zutreffen als null setzen (außer kb_delta, das ist immer eine Zahl)."""


_ACTIVE_PROMPT_CACHE: dict = {}


def get_active_prompt_version(module: str) -> str:
    if module in _ACTIVE_PROMPT_CACHE:
        return _ACTIVE_PROMPT_CACHE[module]
    try:
        from database.db import SessionLocal
        from database.models import PromptVersion
        db = SessionLocal()
        try:
            pv = db.query(PromptVersion).filter_by(module=module, is_active=True).first()
            version = pv.version if pv else 'unknown'
        finally:
            db.close()
    except Exception:
        version = 'unknown'
    _ACTIVE_PROMPT_CACHE[module] = version
    return version


def _write_ft_assistant_event(
    module: str,
    hint_type: str,
    hint_text: str,
    model_used: str,
    context: dict | None = None,
) -> None:
    """
    Write one row to ft_assistant_events. Called from background threads
    (analyse_loop, coaching_loop). MUST NOT raise — swallows all errors.

    Cold-Call DSGVO enforcement: transcript_segment and speaker are
    hard-set to None when ls.state['mode'] == 'cold_call' (or when mode
    is missing/unknown — default to cold_call for safety), regardless
    of what the caller passed in.
    """
    context = context or {}
    try:
        import services.live_session as ls
        from database.db import SessionLocal
        from database.models import FtAssistantEvent

        with ls.state_lock:
            ft_session_id = ls.state.get('ft_session_id')
            mode          = ls.state.get('mode') or 'cold_call'
            user_id       = ls.state.get('user_id')
            market        = ls.state.get('market') or 'dach'
            language      = ls.state.get('language') or 'de'
            readiness     = ls.state.get('kaufbereitschaft')

        if ft_session_id is None or user_id is None:
            # Phase not yet started or anonymous — skip write (no error)
            return

        # D-03/D-04/D-05: Cold-Call hard NULL enforcement (DSGVO)
        if mode == 'cold_call':
            transcript_segment = None
            speaker = None
        else:
            transcript_segment = context.get('transcript_segment')
            speaker = context.get('speaker')

        def _jdump(v):
            if v is None:
                return None
            try:
                return json.dumps(v, ensure_ascii=False)
            except Exception:
                return None

        db = SessionLocal()
        try:
            row = FtAssistantEvent(
                ft_session_id=ft_session_id,
                user_id=user_id,
                market=market,
                language=language,
                timestamp_ms=int(time.time() * 1000),
                conversation_phase=context.get('conversation_phase') or 'unknown',
                speaker=speaker,
                transcript_segment=transcript_segment,
                context_window=_jdump(context.get('context_window')),
                customer_data=_jdump(context.get('customer_data')),
                profile_data=_jdump(context.get('profile_data')),
                readiness_score=readiness,
                active_learning_cards=None,  # Phase 4.11
                hint_type=hint_type or 'hint',
                hint_text=hint_text or '',
                hint_category=context.get('hint_category'),
                model_used=model_used or 'unknown',
                prompt_version=get_active_prompt_version(module),
            )
            db.add(row)
            db.commit()
        finally:
            db.close()
    except Exception as e:
        # NEVER raise — analyse_loop/coaching_loop must not crash on FT logging
        print(f"[FT] assistant_event write failed (module={module}): {e}")


def _build_coaching_prompt() -> str:
    import services.live_session as ls
    _, pdata = ls.get_active_profile()
    if not pdata:
        return COACHING_PROMPT_BASE
    basis       = pdata.get('basis', {})
    zielgruppe  = pdata.get('zielgruppe', {})
    schmerzen   = pdata.get('schmerzen', {})
    kaufsignale = pdata.get('kaufsignale', [])
    uebergaenge = pdata.get('uebergaenge', [])
    wettbew     = pdata.get('wettbewerber', [])
    phasen      = pdata.get('phasen', [])
    ki          = pdata.get('ki', {})
    lines = [COACHING_PROMPT_BASE, '\n--- AKTIVES VERKAUFSPROFIL ---']
    if basis.get('produktbeschreibung'):
        lines.append(f'Produkt: {basis["produktbeschreibung"]}')
    if basis.get('unternehmen'):
        lines.append(f'Unternehmen: {basis["unternehmen"]}')
    zg_parts = []
    if zielgruppe.get('vorwissen'): zg_parts.append(f'Vorwissen: {zielgruppe["vorwissen"]}')
    if zielgruppe.get('entscheidungsverhalten'): zg_parts.append(f'Entscheidungstyp: {", ".join(zielgruppe["entscheidungsverhalten"])}')
    if zg_parts:
        lines.append(f'Zielgruppe: {" | ".join(zg_parts)}')
    if kaufsignale:
        lines.append('\nProfilspezifische Kaufsignale:')
        for k in kaufsignale:
            reaktion = k.get('beschreibung') or k.get('reaktion', '')
            if k.get('signal'):
                lines.append(f'- Signal: "{k["signal"]}" → Reaktion: {reaktion}')
    schmerzpunkte = schmerzen.get('schmerzpunkte', [])
    if schmerzpunkte:
        lines.append('\nHauptschmerzpunkte des Kunden:')
        for s in schmerzpunkte:
            if isinstance(s, dict) and s.get('situation'):
                kern = s.get('kern', '')
                lines.append(f'- {s["situation"]}' + (f': {kern}' if kern else ''))
    if wettbew:
        lines.append('\nWettbewerber (achte auf Erwähnungen):')
        for w in wettbew:
            if w.get('name'):
                lines.append(f'- {w["name"]}: {w.get("schwaeche","")}')
    if uebergaenge:
        lines.append('\nGesprächsübergänge (erkenne wann der Zeitpunkt kommt):')
        for u in uebergaenge:
            if u.get('von') or u.get('nach'):
                lines.append(f'- {u.get("von","")} → {u.get("nach","")}: "{u.get("bruecke","")}"')
    if phasen:
        with ls.phase_lock:
            idx = ls.aktive_phase_idx
        if 0 <= idx < len(phasen):
            ph = phasen[idx]
            lines.append(f'\nAktuelle Gesprächsphase: {ph.get("name","")} — {ph.get("ziel","") or ph.get("beschreibung","")}')
    if ki.get('ansprache'):
        lines.append(f'Kundenansprache: {ki["ansprache"]}')
    if ki.get('zusatz'):
        lines.append(f'Zusatz-Anweisung: {ki["zusatz"]}')
    return '\n'.join(lines)


def _parse_json(raw: str) -> dict:
    if not raw:
        return {}
    start = raw.find('{')
    end   = raw.rfind('}') + 1
    if start == -1 or end == 0 or start >= end:
        return {}
    try:
        return json.loads(raw[start:end])
    except json.JSONDecodeError:
        return {}


# ── Phase-Classifier (Phase 04.8 P02, D-01) ──────────────────────────────────
# rank_ewb / EWB-Ranking Haiku call REMOVED per Phase 04.8 D-08 + user override.
# Phase-based button table from briefing (ki_logik.PHASE_BUTTONS) replaces it.

_PHASE_NAMES = {
    1: 'Opener',
    2: 'Qualifizierung',
    3: 'Bedarfsanalyse',
    4: 'Pitch',
    5: 'Einwandbehandlung',
    6: 'Abschluss',
}

PHASE_CLASSIFIER_PROMPT = """Du klassifizierst die aktuelle Phase eines B2B-Verkaufsgesprächs.

Die 6 Phasen (exakt in dieser Reihenfolge):
1 = Opener — Begrüßung, Aufmerksamkeit gewinnen, Gesprächserlaubnis (0-3 Min)
2 = Qualifizierung — Entscheider? Budget? Bedarf? (3-10 Min)
3 = Bedarfsanalyse — Kunde artikuliert seinen Schmerz (10-20 Min)
4 = Pitch — Lösungspräsentation, USPs auf Schmerz mappen (20-30 Min)
5 = Einwandbehandlung — Einwand kam, wird adressiert (variabel)
6 = Abschluss — Verbindliche Entscheidung herbeiführen (variabel)

Aktueller Kontext:
- Bisherige Phase: {current_phase}
- Gesprächsdauer bisher: {elapsed_s} Sekunden
- Modus: {mode}

Letzte Gesprächsaussagen (chronologisch):
{transcript_window}

Bestimme die AKTUELLE Phase basierend auf den letzten Aussagen.
Eine Phase kann bestehen bleiben. Phase 5 kann aus jeder späteren Phase zurück-aktiviert werden wenn ein Einwand kommt.

Antworte NUR als JSON:
{{"phase": <1-6>, "confidence": <0.0-1.0>, "grund": "<max 10 Wörter>"}}"""


def classify_phase(transcript_window, current_phase, elapsed_s, mode):
    """Haiku call. Returns {'phase': int 1-6, 'confidence': float, 'grund': str}
    or None on parse failure / empty input."""
    if not transcript_window:
        return None
    formatted = "\n".join(f"- {t}" for t in transcript_window[-10:])
    prompt = PHASE_CLASSIFIER_PROMPT.format(
        current_phase=current_phase,
        elapsed_s=int(elapsed_s or 0),
        mode=mode or 'meeting',
        transcript_window=formatted,
    )
    try:
        resp = claude_client.messages.create(
            model=config.MODEL_PHASE_CLASSIFY,
            max_tokens=60,
            messages=[{'role': 'user', 'content': prompt}],
        )
        # ── Phase 04.7.2 Cost-Hook ─────────────────────────────────────────
        try:
            from services.cost_tracker import log_api_cost
            u = getattr(resp, 'usage', None)
            if u is not None:
                in_tok = getattr(u, 'input_tokens', 0) or 0
                out_tok = getattr(u, 'output_tokens', 0) or 0
                log_api_cost('anthropic', 'haiku-4-5', user_id=None,
                             units=in_tok/1000.0, unit_type='per_1k_input_tokens',
                             context_tag='phase_classify')
                log_api_cost('anthropic', 'haiku-4-5', user_id=None,
                             units=out_tok/1000.0, unit_type='per_1k_output_tokens',
                             context_tag='phase_classify')
        except Exception as _e:
            print(f"[CostHook] claude phase_classify skipped: {_e}")
        # ────────────────────────────────────────────────────────────────────
        text = resp.content[0].text.strip()
        # strip markdown fences if present
        if text.startswith('```'):
            text = text.strip('`')
            if '\n' in text:
                text = text.split('\n', 1)[1]
            if text.endswith('```'):
                text = text[:-3]
            text = text.strip()
        # tolerate a leading "json" language hint
        if text.startswith('json'):
            text = text[4:].strip()
        data = json.loads(text)
        phase = int(data.get('phase', current_phase))
        conf = float(data.get('confidence', 0.0))
        if 1 <= phase <= 6 and 0.0 <= conf <= 1.0:
            return {
                'phase': phase,
                'confidence': conf,
                'grund': data.get('grund', ''),
            }
    except Exception as e:
        print(f"[phase_classify] parse error: {e}")
    return None


COLDCALL_INFER_PROMPT = """Du bist Vertriebs-Assistent im Cold-Call-Modus. Du hörst NUR den Vertriebler — der Kunde ist nicht zu hören. Leite aus den letzten Aussagen des Vertrieblers den wahrscheinlichsten Kunden-State ab.

Aktuelle Phase: {phase}
Letzte Aussagen des Vertrieblers (chronologisch):
{seller_transcript}

Inferenzregeln (Beispiele):
- Vertriebler wiederholt/umformuliert Frage → Kunde schweigt/zögert → recommended_next: "konkreter nachhaken"
- Vertriebler sagt "verstehe", "klar", "das kann ich nachvollziehen" → Kunde hat Einwand geäußert → likely_customer_action: "einwand"
- Vertriebler wird leiser/kürzer → Kunde übernimmt Gespräch → recommended_next: "zuhören, nicht unterbrechen"
- Vertriebler nennt Preis und schweigt → Kunde prüft/rechnet → recommended_next: "Stille halten"
- Vertriebler sagt "wann passt es Ihnen" → Kunde bei Terminfindung → likely_customer_action: "terminbereit"

Antworte NUR als JSON:
{{"likely_customer_action": "<max 8 Wörter>", "confidence": <0.0-1.0>, "recommended_next": "<max 10 Wörter>"}}"""


def infer_customer_state(seller_transcript, phase):
    """Haiku call for D-05 cold-call customer-state inference.
    Returns dict or None on empty input / parse failure."""
    if not seller_transcript:
        return None
    formatted = "\n".join(f"- {t}" for t in seller_transcript[-6:])
    prompt = COLDCALL_INFER_PROMPT.format(phase=phase, seller_transcript=formatted)
    try:
        resp = claude_client.messages.create(
            model=config.MODEL_COLDCALL_INFER,
            max_tokens=120,
            messages=[{'role': 'user', 'content': prompt}],
        )
        # ── Phase 04.7.2 Cost-Hook ─────────────────────────────────────────
        try:
            from services.cost_tracker import log_api_cost
            u = getattr(resp, 'usage', None)
            if u is not None:
                in_tok = getattr(u, 'input_tokens', 0) or 0
                out_tok = getattr(u, 'output_tokens', 0) or 0
                log_api_cost('anthropic', 'haiku-4-5', user_id=None,
                             units=in_tok/1000.0, unit_type='per_1k_input_tokens',
                             context_tag='coldcall_infer')
                log_api_cost('anthropic', 'haiku-4-5', user_id=None,
                             units=out_tok/1000.0, unit_type='per_1k_output_tokens',
                             context_tag='coldcall_infer')
        except Exception as _e:
            print(f"[CostHook] claude coldcall_infer skipped: {_e}")
        # ────────────────────────────────────────────────────────────────────
        text = resp.content[0].text.strip()
        if text.startswith('```'):
            text = text.strip('`')
            if '\n' in text:
                text = text.split('\n', 1)[1]
            if text.endswith('```'):
                text = text[:-3]
            text = text.strip()
        if text.startswith('json'):
            text = text[4:].strip()
        data = json.loads(text)
        if not isinstance(data.get('likely_customer_action'), str):
            return None
        conf = float(data.get('confidence', 0.0))
        if not 0.0 <= conf <= 1.0:
            return None
        return {
            'likely_customer_action': data['likely_customer_action'][:200],
            'confidence': conf,
            'recommended_next': str(data.get('recommended_next', ''))[:200],
            'ts': datetime.utcnow().isoformat(),
        }
    except Exception as e:
        print(f"[coldcall_infer] error: {e}")
        return None


def analysiere_mit_claude(neuer_text: str, kontext: str) -> dict:
    user_msg = f"""Bisheriger Gesprächskontext (zur Orientierung, letzte Aussagen):
{kontext if kontext else "(Kein vorheriger Kontext)"}

Neues Gesprächssegment (analysiere NUR dieses auf Einwände):
{neuer_text}"""
    # ── Phase 08 EWB-Pipeline Integration ──────────────────────────────────────
    # Routing ueber resolve_prompt_version (A/B-Router mit ENV-Override)
    # + build_ewb_prompt (Baustein-Struktur).
    # user_id aus ls.state (W-6): deepgram_service.handle_start_live_session
    # setzt ls.state['user_id'] bei Call-Start. Fallback auf 0 wenn leer —
    # resolve_prompt_version wechselt dann auf variants[0] (deterministisch
    # v1-legacy als sicherer Default).
    import services.live_session as ls
    # CR-01: reads under state_lock — deepgram_service writes session_anrede/user_id under same lock
    if hasattr(ls, 'state') and hasattr(ls, 'state_lock'):
        with ls.state_lock:
            _user_id = ls.state.get('user_id') or 0
            _anrede = ls.state.get('session_anrede') or 'Sie'
    else:
        _user_id = 0
        _anrede = 'Sie'
    if not _user_id:
        print("[Phase08] WARN: ls.state['user_id'] leer — faellt auf variants[0] zurueck (v1-legacy als Default)")
    _ewb_version = resolve_prompt_version('ewb', _user_id)
    _system_prompt = build_ewb_prompt(
        profile_data=None,
        anrede=_anrede,
        version=_ewb_version,
        user_id=_user_id,
    )
    # ── Phase 08.13: Prompt-Caching Analyse-Loop (CACHE_ANALYSE=False default) ──
    if config.CACHE_ANALYSE and len(_system_prompt) >= _CACHE_MIN_CHARS:
        _system = [{"type": "text", "text": _system_prompt, "cache_control": {"type": "ephemeral"}}]
    else:
        _system = _system_prompt  # String, kein Cache
    if config.CACHE_ANALYSE:
        print(f"[Cache-Check] analyse system_prompt: {len(_system_prompt)} chars, "
              f"threshold {_CACHE_MIN_CHARS}, cache={'on' if len(_system_prompt) >= _CACHE_MIN_CHARS else 'off'}")
    # ──────────────────────────────────────────────────────────────────────────
    msg = claude_client.messages.create(
        model=config.MODEL_ANALYSE,
        max_tokens=400,
        system=_system,
        messages=[{"role": "user", "content": user_msg}]
    )
    # ── Phase 04.7.2 Cost-Hook ─────────────────────────────────────────
    try:
        from services.cost_tracker import log_api_cost
        u = getattr(msg, 'usage', None)
        if u is not None:
            in_tok = getattr(u, 'input_tokens', 0) or 0
            out_tok = getattr(u, 'output_tokens', 0) or 0
            log_api_cost('anthropic', 'haiku-4-5', user_id=None,
                         units=in_tok/1000.0, unit_type='per_1k_input_tokens',
                         context_tag='live_haiku')
            log_api_cost('anthropic', 'haiku-4-5', user_id=None,
                         units=out_tok/1000.0, unit_type='per_1k_output_tokens',
                         context_tag='live_haiku')
        # Cache-Token-Logging (B1 Review-Finding)
        _cache_hits = getattr(getattr(msg, 'usage', None), 'cache_read_input_tokens', 0) or 0
        _cache_writes = getattr(getattr(msg, 'usage', None), 'cache_creation_input_tokens', 0) or 0
        if _cache_hits > 0:
            log_api_cost('anthropic', 'haiku-4-5', user_id=None,
                         units=_cache_hits/1000.0, unit_type='per_1k_cache_read_tokens',
                         context_tag='analyse', call_site='analyse')
        if _cache_writes > 0:
            log_api_cost('anthropic', 'haiku-4-5', user_id=None,
                         units=_cache_writes/1000.0, unit_type='per_1k_cache_write_tokens',
                         context_tag='analyse', call_site='analyse')
    except Exception as _e:
        print(f"[CostHook] claude live_haiku skipped: {_e}")
    # ────────────────────────────────────────────────────────────────────
    return _parse_json(msg.content[0].text.strip())


def streame_auto_variante(neuer_text: str, einwaende: list, kontext: str, sid: str, slot: int = 1, trigger: str = "analyse_loop") -> dict:
    # ── Shared-Lock Design ────────────────────────────────────────────────────
    # Der Anti-Overlap-Guard fuer Slot 1 laeuft ueber ls.state['slot1_variant_busy_until']
    # (geschuetzt durch ls.state_lock). BEIDE automatischen Caller nutzen DENSELBEN Key:
    #   - Keyword-Pipe (deepgram_service.py): trigger="keyword"
    #   - analyse_loop (claude_service.py):   trigger="analyse_loop"
    # Wer zuerst feuert, setzt busy_until = now + 6s. Der andere trifft busy und skippt.
    # UNABHAENGIG davon: streame_manual_ewb_variante (Button-Klick-Pfad) nutzt diesen Lock
    # NICHT — er ist by design unabhaengig, damit Berater-Button nie geblockt wird.
    # ──────────────────────────────────────────────────────────────────────────
    """BUG-10 r3: Parallele Auto-Variante — startet SOFORT ohne auf Typ-Detection zu warten.
    Haiku bekommt den rohen Kunden-Satz + Profil-Einwaende-Liste als Kontext und baut
    eine knappe Gegenargument-Variante fuer Slot 1 (Slot 0 = analysiere_mit_claude).
    """
    from extensions import socketio as sio

    # Profil-Einwaende als kompakte Referenz fuer Haiku aufbereiten
    _profile_lines = []
    for _e in (einwaende or [])[:10]:
        if isinstance(_e, dict):
            _lbl = (_e.get('kurzlabel') or _e.get('kategorie') or _e.get('typ') or _e.get('einwand') or '').strip()
            _ga = (_e.get('gegenargument_1') or _e.get('gegenargument') or '').strip()
            if _lbl and _ga:
                _profile_lines.append(f"- {_lbl}: {_ga[:160]}")
    _profile_block = "\n".join(_profile_lines) if _profile_lines else "(keine hinterlegten Einwaende)"

    user_msg = f"""Kunde hat gerade gesagt:
"{neuer_text}"

Bisheriger Gespraechsverlauf:
{kontext if kontext else "(Call gerade gestartet)"}

Hinterlegte Einwand-Gegenargumente (als Orientierung, nicht woertlich kopieren):
{_profile_block}

Falls der Kunde einen Einwand geaeussert hat: Baue eine KURZE (2-3 Saetze) kontextbezogene
Gegenargument-Variante — greif konkret das Gesagte auf, authentisch und direkt.

Falls kein Einwand: Formuliere eine knappe gespraechsfuehrende Reaktion / naechste Frage
(1-2 Saetze) die den Rapport-Aufbau weitertraegt.

Antworte NUR mit dem Text. Kein JSON, keine Labels, keine Meta-Kommentare.
"""

    # ── Phase 08.13: Prompt-Caching EWB AutoVar (CACHE_EWB=True default) ─────────
    _ewb_autovar_system = "Du bist ein erfahrener Sales-Coach im DACH-B2B. Antworte knapp, praktisch, menschlich — keine Fuellwoerter."
    if config.CACHE_EWB and len(_ewb_autovar_system) >= _CACHE_MIN_CHARS:
        _system_autovar = [{"type": "text", "text": _ewb_autovar_system, "cache_control": {"type": "ephemeral"}}]
    else:
        _system_autovar = _ewb_autovar_system
    if config.CACHE_EWB:
        print(f"[Cache-Check] ewb system_prompt: {len(_ewb_autovar_system)} chars, "
              f"threshold {_CACHE_MIN_CHARS}, cache={'on' if len(_ewb_autovar_system) >= _CACHE_MIN_CHARS else 'off'}")
    # ──────────────────────────────────────────────────────────────────────────
    print(f"[PiP-AutoVar] ENTRY trigger={trigger} sid={sid} slot={slot} text={neuer_text[:60]!r}")
    sio.emit('pip_stream_start', {'slot': slot, 'raw_text': True}, room=sid)
    full_text = ''
    try:
        with claude_client.messages.stream(
            model=config.MODEL_PIP_AUTOVAR,
            max_tokens=200,
            system=_system_autovar,
            messages=[{'role': 'user', 'content': user_msg}]
        ) as stream:
            for token in stream.text_stream:
                full_text += token
                sio.emit('pip_token', {'slot': slot, 'token': token, 'raw_text': True}, room=sid)
        cleaned = full_text.strip()
        result = {'einwand': True, 'typ': 'AUTO', 'gegenargument_1': cleaned}
        sio.emit('pip_token_done', {'slot': slot, 'result': result, 'raw_text': True}, room=sid)
        print(f"[PiP-AutoVar] DONE sid={sid} slot={slot} chars={len(cleaned)}")
        try:
            from services.cost_tracker import log_api_cost
            final_msg = stream.get_final_message()
            u = getattr(final_msg, 'usage', None)
            if u is not None:
                in_tok = getattr(u, 'input_tokens', 0) or 0
                out_tok = getattr(u, 'output_tokens', 0) or 0
                log_api_cost('anthropic', 'haiku-4-5', user_id=None,
                             units=in_tok/1000.0, unit_type='per_1k_input_tokens',
                             context_tag='pip_autovar')
                log_api_cost('anthropic', 'haiku-4-5', user_id=None,
                             units=out_tok/1000.0, unit_type='per_1k_output_tokens',
                             context_tag='pip_autovar')
            # Cache-Token-Logging (B1 Review-Finding)
            _cache_hits = getattr(getattr(final_msg, 'usage', None), 'cache_read_input_tokens', 0) or 0
            _cache_writes = getattr(getattr(final_msg, 'usage', None), 'cache_creation_input_tokens', 0) or 0
            if _cache_hits > 0:
                log_api_cost('anthropic', 'haiku-4-5', user_id=None,
                             units=_cache_hits/1000.0, unit_type='per_1k_cache_read_tokens',
                             context_tag='ewb', call_site='ewb')
            if _cache_writes > 0:
                log_api_cost('anthropic', 'haiku-4-5', user_id=None,
                             units=_cache_writes/1000.0, unit_type='per_1k_cache_write_tokens',
                             context_tag='ewb', call_site='ewb')
        except Exception as _e:
            print(f"[CostHook] pip_autovar skipped: {_e}")
        return result
    except Exception as e:
        print(f"[PiP-AutoVar] Fehler sid={sid} slot={slot}: {e}")
        err_msg = str(e).lower()
        if '529' in err_msg or 'overloaded' in err_msg:
            friendly = 'KI aktuell ausgelastet — Standard-Antwort oben nutzen.'
        else:
            friendly = 'Variante nicht verfuegbar.'
        sio.emit('pip_stream_error', {'slot': slot, 'error': friendly}, room=sid)
        return {}


def streame_manual_ewb_variante(typ: str, profile_einwand: dict, kontext: str, sid: str, slot: int = 1) -> dict:
    """06.1-r2 r4: Manual-EWB Slot-1 Variante.
    Berater hat EWB-Button 'typ' geklickt. Slot 0 zeigt bereits das Profil-Gegenargument
    instant (client-side). Hier streamen wir eine KONTEXTBEZOGENE Variante in Slot 1:
    Haiku bekommt Profil-Standard + Gespraechsverlauf, baut eine knappe Adaption.
    Emits pip_stream_start (mit raw_text:true), pip_token (plain text), pip_token_done.

    UNABHAENGIG von streame_auto_variante: dieser Pfad prueft/setzt
    ls.state['slot1_variant_busy_until'] NICHT — Button-Klick soll nie durch den
    automatischen Anti-Overlap-Guard geblockt werden. By design unabhaengig.
    """
    from extensions import socketio as sio
    standard_ga = ''
    if isinstance(profile_einwand, dict):
        standard_ga = (profile_einwand.get('gegenargument_1')
                       or profile_einwand.get('gegenargument')
                       or profile_einwand.get('text')
                       or '')

    user_msg = f"""Der Berater hat im PiP-Live-Fenster den Einwand-Button "{typ}" geklickt.

Standard-Gegenargument aus Profil:
{standard_ga or "(keines hinterlegt)"}

Bisheriger Gespraechsverlauf (letzte Aussagen):
{kontext if kontext else "(kein Kontext — Call ist gerade gestartet)"}

Baue eine KURZE, kontextbezogene Variante des Gegenarguments:
- 2-3 Saetze maximal
- Greif konkret den Gespraechsverlauf auf (falls Kontext vorhanden)
- Authentischer Ton, wie der Berater wirklich sprechen wuerde
- Kein Jargon, direkt und glaubwuerdig

Antworte NUR mit dem Gegenargument-Text. Kein JSON, keine Labels, keine Meta-Kommentare.
"""

    # ── Phase 08.13: Prompt-Caching EWB Manual (CACHE_EWB=True default) ──────────
    _ewb_manual_system = "Du bist ein erfahrener Sales-Coach im DACH-B2B. Antworte knapp, praktisch, menschlich — keine Fuellwoerter, keine Meta-Kommentare."
    if config.CACHE_EWB and len(_ewb_manual_system) >= _CACHE_MIN_CHARS:
        _system_manual = [{"type": "text", "text": _ewb_manual_system, "cache_control": {"type": "ephemeral"}}]
    else:
        _system_manual = _ewb_manual_system
    if config.CACHE_EWB:
        print(f"[Cache-Check] ewb system_prompt: {len(_ewb_manual_system)} chars, "
              f"threshold {_CACHE_MIN_CHARS}, cache={'on' if len(_ewb_manual_system) >= _CACHE_MIN_CHARS else 'off'}")
    # ──────────────────────────────────────────────────────────────────────────
    print(f"[PiP-Variante] ENTRY sid={sid} slot={slot} typ={typ!r}")
    sio.emit('pip_stream_start', {'slot': slot, 'raw_text': True}, room=sid)
    full_text = ''
    # 06.1-r2 r6: Retry bei 529 overloaded_error — Anthropic hat stossweise Spitzen,
    # ein kurzer Backoff rettet i.d.R. den zweiten Versuch. Max 2 Retries, dann graceful fallback.
    import time as _time
    attempts = 0
    last_err = None
    stream_ctx = None
    while attempts < 3:
        attempts += 1
        try:
            with claude_client.messages.stream(
                model=config.MODEL_PIP_VARIANTE,
                max_tokens=250,
                system=_system_manual,
                messages=[{'role': 'user', 'content': user_msg}]
            ) as stream:
                stream_ctx = stream
                for token in stream.text_stream:
                    full_text += token
                    sio.emit('pip_token', {'slot': slot, 'token': token, 'raw_text': True}, room=sid)
            break  # Erfolg — raus aus Retry-Loop
        except Exception as e:
            last_err = e
            msg = str(e).lower()
            is_overloaded = '529' in msg or 'overloaded' in msg
            if is_overloaded and attempts < 3:
                backoff = 0.8 * attempts  # 0.8s, 1.6s
                print(f"[PiP-Variante] 529 overloaded — retry {attempts}/3 in {backoff:.1f}s (sid={sid})")
                full_text = ''  # Reset Akkumulator fuer neuen Versuch
                _time.sleep(backoff)
                continue
            # Kein Overload ODER letzter Versuch: raise in den outer except
            raise
    try:
        cleaned = full_text.strip()
        result = {'einwand': True, 'typ': typ, 'gegenargument_1': cleaned}
        sio.emit('pip_token_done', {'slot': slot, 'result': result, 'raw_text': True}, room=sid)
        print(f"[PiP-Variante] DONE sid={sid} slot={slot} chars={len(cleaned)} (attempts={attempts})")
        # Cost-Hook
        try:
            from services.cost_tracker import log_api_cost
            final_msg = stream.get_final_message()
            u = getattr(final_msg, 'usage', None)
            if u is not None:
                in_tok = getattr(u, 'input_tokens', 0) or 0
                out_tok = getattr(u, 'output_tokens', 0) or 0
                log_api_cost('anthropic', 'haiku-4-5', user_id=None,
                             units=in_tok/1000.0, unit_type='per_1k_input_tokens',
                             context_tag='pip_variante')
                log_api_cost('anthropic', 'haiku-4-5', user_id=None,
                             units=out_tok/1000.0, unit_type='per_1k_output_tokens',
                             context_tag='pip_variante')
            # Cache-Token-Logging (B1 Review-Finding)
            _cache_hits = getattr(getattr(final_msg, 'usage', None), 'cache_read_input_tokens', 0) or 0
            _cache_writes = getattr(getattr(final_msg, 'usage', None), 'cache_creation_input_tokens', 0) or 0
            if _cache_hits > 0:
                log_api_cost('anthropic', 'haiku-4-5', user_id=None,
                             units=_cache_hits/1000.0, unit_type='per_1k_cache_read_tokens',
                             context_tag='ewb', call_site='ewb')
            if _cache_writes > 0:
                log_api_cost('anthropic', 'haiku-4-5', user_id=None,
                             units=_cache_writes/1000.0, unit_type='per_1k_cache_write_tokens',
                             context_tag='ewb', call_site='ewb')
        except Exception as _e:
            print(f"[CostHook] pip_variante skipped: {_e}")
        return result
    except Exception as e:
        # 06.1-r2 r6: Freundliche User-Message statt roher Exception.
        # Slot 0 hat bereits das Profil-Gegenargument — Slot 1 sagt dem User nur
        # dass die Variante gerade nicht geht, nicht mehr.
        err_msg = str(e).lower()
        if '529' in err_msg or 'overloaded' in err_msg:
            friendly = 'KI aktuell ausgelastet — nimm die Standard-Antwort oben.'
        elif 'rate' in err_msg or '429' in err_msg:
            friendly = 'Zu viele Anfragen — gleich nochmal versuchen.'
        else:
            friendly = 'Variante nicht verfuegbar — Standard oben nutzen.'
        print(f"[PiP-Variante] Fehler sid={sid} slot={slot} (attempts={attempts}): {e}")
        sio.emit('pip_stream_error', {'slot': slot, 'error': friendly}, room=sid)
        return {}


def analysiere_coaching(segmente: list, kontext: str) -> dict:
    gespraech = "\n".join(f"[{s['speaker']}] {s['text']}" for s in segmente)
    user_msg  = f"""Bisheriger Gesprächskontext:
{kontext if kontext else "(Kein vorheriger Kontext)"}

Aktuelles Gesprächssegment:
{gespraech}"""
    # Phase 04.8 P07: migrated Sonnet→Haiku per Haiku-only-live constraint
    msg = claude_client.messages.create(
        model=config.MODEL_COACHING,
        max_tokens=200,
        system=_build_coaching_prompt(),
        messages=[{"role": "user", "content": user_msg}]
    )
    # ── Phase 04.7.2 Cost-Hook (04.8 P07: Haiku) ────────────────────────
    try:
        from services.cost_tracker import log_api_cost
        u = getattr(msg, 'usage', None)
        if u is not None:
            in_tok = getattr(u, 'input_tokens', 0) or 0
            out_tok = getattr(u, 'output_tokens', 0) or 0
            log_api_cost('anthropic', 'haiku-4-5', user_id=None,
                         units=in_tok/1000.0, unit_type='per_1k_input_tokens',
                         context_tag='coaching_haiku')
            log_api_cost('anthropic', 'haiku-4-5', user_id=None,
                         units=out_tok/1000.0, unit_type='per_1k_output_tokens',
                         context_tag='coaching_haiku')
    except Exception as _e:
        print(f"[CostHook] claude coaching_haiku skipped: {_e}")
    # ────────────────────────────────────────────────────────────────────
    return _parse_json(msg.content[0].text.strip())


def analyse_loop():
    """Call 1 — Einwand-Analyse (Haiku, schnell)."""
    import services.live_session as ls
    from extensions import socketio as sio
    while True:
        ls.analyse_trigger.wait(timeout=ANALYSE_INTERVALL)
        ls.analyse_trigger.clear()
        with ls.pause_lock:
            if ls.is_paused:
                continue
        with ls.buffer_lock:
            if not ls.transcript_buffer:
                continue
            neuer_text = " ".join(e['text'] for e in ls.transcript_buffer)
            line_id    = ls.transcript_buffer[-1]['line_id']
            t_start    = ls.transcript_buffer[0].get('t_start', time.monotonic())
            kontext    = " ".join(ls.analysiert_bisher[-20:])
            ls.analysiert_bisher.extend(e['text'] for e in ls.transcript_buffer)
            ls.transcript_buffer.clear()
        # D-09: Inject active learning cards into kontext
        with ls.state_lock:
            _lk_cards = ls.state.get('active_learning_cards', [])
        if _lk_cards:
            _lk_ctx = "\n\n[Aktive Lernkarten des Beraters - bei passender Situation mit lernkarte_match=true markieren]:\n"
            for _c in _lk_cards[:5]:
                _lk_ctx += f"- [{_c['category']}] {_c['final_text'][:80]}\n"
            kontext = kontext + _lk_ctx
        print(f"[Claude-1] Analysiere (line {line_id}): {neuer_text[:80]}…")
        with ls.state_lock:
            ls.state['aktiv'] = True
        try:
            # Phase 06.3: analyse_loop no longer renders into PiP slots.
            # Keyword-Matcher (06.2) is sole primary for Slot 0 + Slot 1.
            # Non-streaming call preserves ergebnis for FT-events, Kaufbereitschaft,
            # Phase-Classifier, Cold-Call-Inference, Active-Hint-Orchestration.
            ergebnis = analysiere_mit_claude(neuer_text, kontext)
            # ── Phase 08.5: Universal Response Loop ──────────────────────────
            # Classifies utterance via qa_pipeline when kw_fired_for_line != line_id
            # (D-02 guard). Emits qa_slot1 or qa_soft_hint to active session.
            _qa_pipeline_dispatch(neuer_text, line_id, kontext, ls, sio)
            latency_e = round(time.monotonic() - t_start, 2)
            print(f"[Claude-1] Ergebnis (Latenz {latency_e}s): {ergebnis}")
            ts = datetime.now().strftime('%H:%M:%S')
            # Kaufbereitschaft deterministisch anpassen
            with ls.kb_lock:
                kb_vor_einwand = ls.kaufbereitschaft
            if ergebnis.get('einwand'):
                delta = -5 if ergebnis.get('intensitaet') == 'hoch' else -3
                ls.update_kaufbereitschaft(delta)
            with ls.log_lock:
                ls.conversation_log.append({
                    'ts': ts, 'type': 'analyse',
                    'speaker': None, 'text': neuer_text, 'data': ergebnis,
                    'latency': latency_e,
                })
            with ls.kb_lock:
                kb_aktuell = ls.kaufbereitschaft
            # Gegenargument-Tracking
            if ergebnis.get('einwand'):
                with ls.gegenargument_log_lock:
                    # Vorherigen Eintrag mit kb_nachher aktualisieren
                    if ls.gegenargument_log:
                        last = ls.gegenargument_log[-1]
                        if last['kb_nachher'] is None:
                            last['kb_nachher'] = kb_vor_einwand
                            last['kb_delta']   = kb_vor_einwand - last['kb_vorher']
                            last['erfolgreich'] = last['kb_delta'] > 0
                    # Neuen Eintrag anlegen
                    ls.gegenargument_log.append({
                        'ts':               ts,
                        'einwand_typ':      ergebnis.get('typ', ''),
                        'einwand_zitat':    ergebnis.get('einwand_zitat', ''),
                        'ist_vorwand':      ergebnis.get('ist_vorwand', False),
                        'gegenargument_1':  ergebnis.get('gegenargument_1', ''),
                        'gegenargument_2':  ergebnis.get('gegenargument_2', ''),
                        'gewaehlte_option': None,
                        'kb_vorher':        kb_aktuell,
                        'kb_nachher':       None,
                        'kb_delta':         None,
                        'erfolgreich':      None,
                    })
            with ls.state_lock:
                ls.state['ergebnis']        = ergebnis
                ls.state['line_id']         = line_id
                ls.state['aktiv']           = False
                ls.state['version']        += 1
                ls.state['kaufbereitschaft'] = kb_aktuell
            # ── FT logging hook (Phase 04.7.1) ────────────────────────────────
            try:
                if ergebnis.get('einwand'):
                    _hint_text = (ergebnis.get('gegenargument_1') or '').strip()
                    _hint_type = ergebnis.get('typ') or 'einwand'
                else:
                    _hint_text = ergebnis.get('notiz') or ''
                    _hint_type = 'kein_einwand'
                _write_ft_assistant_event(
                    module='assistant_live',
                    hint_type=_hint_type,
                    hint_text=_hint_text,
                    model_used=config.MODEL_ANALYSE,
                    context={
                        'transcript_segment': neuer_text,
                        'speaker': 'rep',
                        'conversation_phase': None,
                        'hint_category': ergebnis.get('typ'),
                    },
                )
            except Exception as _e:
                print(f"[FT] assistant_live hook skipped: {_e}")
            # ── Phase 04.8: phase classifier (every 5th cycle) ────────────────
            _phase_cycle_counter = getattr(analyse_loop, '_phase_cycle_counter', 0) + 1
            analyse_loop._phase_cycle_counter = _phase_cycle_counter
            if _phase_cycle_counter % 5 == 0:
                try:
                    from services.ki_logik import detect_phase
                    with ls.buffer_lock:
                        transcript_window = list(ls.analysiert_bisher[-10:])
                    with ls.state_lock:
                        cur_phase = ls.state.get('current_phase', 1) or 1
                        phase_change_count = ls.state.get('phase_change_count', 0) or 0
                        last_change_cycle = ls.state.get('_phase_cycle_at_last_change', 0) or 0
                        mode = ls.state.get('mode', 'meeting')
                    elapsed_s = (time.time() - ls.session_start_ts) if hasattr(ls, 'session_start_ts') else 0
                    raw = classify_phase(transcript_window, cur_phase, elapsed_s, mode)
                    if raw:
                        cycles_since_change = _phase_cycle_counter - last_change_cycle
                        new_phase, new_conf = detect_phase(
                            raw_phase=raw['phase'],
                            raw_confidence=raw['confidence'],
                            current_phase=cur_phase,
                            phase_change_count=phase_change_count,
                            cycles_since_change=cycles_since_change,
                        )
                        with ls.state_lock:
                            phase_did_change = (new_phase != cur_phase)
                            if phase_did_change:
                                ls.state['current_phase'] = new_phase
                                ls.state['current_phase_name'] = _PHASE_NAMES.get(new_phase, '')
                                ls.state['phase_changed_at'] = datetime.utcnow().isoformat()
                                ls.state['phase_change_count'] = phase_change_count + 1
                                ls.state['_phase_cycle_at_last_change'] = _phase_cycle_counter
                                print(f"[phase_classify] {cur_phase}→{new_phase} ({_PHASE_NAMES.get(new_phase,'')}) conf={new_conf:.2f} grund={raw.get('grund','')}")
                            ls.state['phase_confidence'] = new_conf
                        # POLISH-39 + POLISH-42: propagate AI phase-change to phasen_log (for
                        # ConversationLog.phasen_details) and covered_phases (for skript_abdeckung).
                        # Done outside state_lock to avoid nested-lock stalls.
                        if phase_did_change:
                            try:
                                old_phase_name = _PHASE_NAMES.get(cur_phase, str(cur_phase))
                                new_phase_name = _PHASE_NAMES.get(new_phase, str(new_phase))
                                ts = datetime.now().strftime('%H:%M:%S')
                                with ls.buffer_lock:
                                    seg_count = len(ls.analysiert_bisher)
                                with ls.phasen_log_lock:
                                    ls.phasen_log.append({
                                        'ts':            ts,
                                        'name':          new_phase_name,  # Template uses ph.name
                                        'typ':           new_phase_name.lower(),
                                        'von_phase':     old_phase_name,
                                        'nach_phase':    new_phase_name,
                                        'segment_count': seg_count,
                                        'source':        'ai_classifier',
                                        'confidence':    round(float(new_conf), 2),
                                    })
                                # POLISH-42: map AI-phase (1-6) -> profile-phase index (0-based),
                                # capped to profile's actual phase count so skript_abdeckung
                                # can't overflow when profile has <6 phases.
                                try:
                                    _pid, _pdata = ls.get_active_profile()
                                    _ph_list = _pdata.get('phasen', []) if _pdata else []
                                    if _ph_list:
                                        _idx = max(0, min(int(new_phase) - 1, len(_ph_list) - 1))
                                        with ls.covered_phases_lock:
                                            ls.covered_phases.add(_idx)
                                except Exception as _ce:
                                    print(f"[phase_classify] covered_phases propagate error: {_ce}")
                            except Exception as _pe:
                                print(f"[phase_classify] phasen_log propagate error: {_pe}")
                    # ── Phase 04.8 P03: Cold-call inference (coldcall mode only) ──
                    try:
                        from services.ki_logik import infer_cold_call_context
                        with ls.state_lock:
                            cc_mode = ls.state.get('mode', 'meeting')
                            cc_phase = ls.state.get('current_phase', 1) or 1
                        if cc_mode == 'cold_call':
                            with ls.buffer_lock:
                                seller_window = list(ls.analysiert_bisher[-6:])
                            inference = infer_cold_call_context(
                                seller_window, cc_phase, cc_mode,
                                haiku_caller=infer_customer_state,
                            )
                            with ls.state_lock:
                                ls.state['cold_call_inference'] = inference
                    except Exception as e:
                        print(f"[coldcall_infer] loop error: {e}")
                except Exception as e:
                    print(f"[phase_classify] loop error: {e}")
            # ── Phase 04.8 P04: Readiness score + active hint orchestration ──
            try:
                from services.ki_logik import (
                    compute_readiness_score,
                    select_active_hint,
                    dynamic_ewb_buttons,
                )
                with ls.state_lock:
                    factors = dict(ls.state.get('score_factors_seen') or {})
                    cur_phase_p4 = ls.state.get('current_phase', 1) or 1
                    cold_inf = ls.state.get('cold_call_inference')
                # Tally factors from latest ergebnis (non-destructive — increments only)
                if ergebnis:
                    if ergebnis.get('kaufsignal'):
                        factors['kaufsignal'] = factors.get('kaufsignal', 0) + 1
                    if ergebnis.get('einwand') and ergebnis.get('einwand_geloest'):
                        factors['einwand_geloest'] = factors.get('einwand_geloest', 0) + 1
                    elif ergebnis.get('einwand'):
                        factors['einwand_offen'] = factors.get('einwand_offen', 0) + 1
                    for _k in ('detailfrage','budget_erwaehnt','naechster_schritt',
                               'zustimmung','konkurrenz','zeitdruck_kunde','monosyllabisch'):
                        if ergebnis.get(_k):
                            factors[_k] = factors.get(_k, 0) + 1
                score_p4, bucket_p4 = compute_readiness_score({'score_factors_seen': factors}, [])
                # Build hint candidates
                _now_iso = datetime.utcnow().isoformat()
                candidates = []
                if ergebnis.get('kritischer_fehler'):
                    candidates.append({'type':'critical','priority':1,
                        'text': str(ergebnis.get('kritischer_fehler'))[:120],
                        'color':'red','source':'analyse_loop','ts': _now_iso})
                if bucket_p4 == 'closing' and (ergebnis.get('kb_delta') or 0) > 0:
                    candidates.append({'type':'kaufsignal','priority':2,
                        'text':'Kaufsignal erkannt — jetzt abschließen',
                        'color':'gold','source':'readiness_rule','ts': _now_iso})
                if ergebnis.get('einwand') and ergebnis.get('gegenargument_1'):
                    candidates.append({'type':'einwand','priority':3,
                        'text': str(ergebnis.get('gegenargument_1'))[:120],
                        'color':'orange','source':'analyse_loop','ts': _now_iso})
                if cold_inf and cold_inf.get('recommended_next'):
                    candidates.append({'type':'phase','priority':4,
                        'text': str(cold_inf['recommended_next'])[:120],
                        'color':'blue','source':'cold_call_infer','ts': _now_iso})
                if ergebnis.get('tipp'):
                    candidates.append({'type':'tipp','priority':5,
                        'text': str(ergebnis.get('tipp'))[:120],
                        'color':'gray','source':'analyse_loop','ts': _now_iso})
                active_hint = select_active_hint(candidates)
                # Dynamic EWB buttons — context-aware (last objection) + phase fallback
                try:
                    if hasattr(ls, 'get_active_profile_ewbs'):
                        base_buttons = ls.get_active_profile_ewbs()
                    else:
                        _pid, _pdata = ls.get_active_profile()
                        base_buttons = None
                        if _pdata:
                            _eins = _pdata.get('einwaende') or []
                            base_buttons = [e.get('einwand') or e.get('kategorie') or ''
                                            for e in _eins if isinstance(e, dict)]
                            base_buttons = [b for b in base_buttons if b]
                except Exception:
                    base_buttons = None
                # Track last objection type for context-based buttons
                _last_ewb_typ = None
                if ergebnis.get('einwand') and ergebnis.get('typ'):
                    _last_ewb_typ = ergebnis['typ']
                elif not ergebnis.get('einwand'):
                    # No new objection — check if there's a recent one in state
                    with ls.state_lock:
                        _last_ewb_typ = ls.state.get('last_einwand_typ')
                if ergebnis.get('einwand') and ergebnis.get('typ'):
                    with ls.state_lock:
                        ls.state['last_einwand_typ'] = ergebnis['typ']
                ewb_buttons = dynamic_ewb_buttons(cur_phase_p4, base_buttons,
                                                  last_einwand_typ=_last_ewb_typ)
                with ls.state_lock:
                    ls.state['score_factors_seen'] = factors
                    ls.state['readiness_score'] = score_p4
                    ls.state['readiness_bucket'] = bucket_p4
                    ls.state['kaufbereitschaft'] = score_p4  # legacy mirror (RESEARCH Q2 R2)
                    ls.state['active_hint'] = active_hint
                    ls.state['ewb_buttons'] = ewb_buttons
                ls.kaufbereitschaft = score_p4  # module global mirror
            except Exception as e:
                print(f"[readiness/active_hint] loop error: {e}")
        except Exception as e:
            print(f"[Claude-1] Fehler: {e}")
            with ls.kb_lock:
                kb_aktuell = ls.kaufbereitschaft
            with ls.state_lock:
                ls.state['ergebnis']         = {'einwand': False, 'notiz': f'Fehler: {e}'}
                ls.state['line_id']          = line_id
                ls.state['aktiv']            = False
                ls.state['version']         += 1
                ls.state['kaufbereitschaft'] = kb_aktuell


# ── Phase 08.5: QA-Pipeline Dispatch Helpers ─────────────────────────────────
# Extracted as module-level functions so analyse_loop stays readable and tests
# can target them directly.

def _qa_load_tabu(active_profile_id, profile_daten=None):
    """Load tabu_begriffe list for the active profile. MUST NOT raise.
    Returns [] on any error. Tries profile daten dict first (already loaded),
    falls back to DB query if profile_daten is None.
    """
    try:
        # Fast path: use already-loaded profile data from live_session module
        if profile_daten and isinstance(profile_daten, dict):
            basis = profile_daten.get('basis', {})
            if isinstance(basis, dict):
                tabu = basis.get('tabu_begriffe', [])
            else:
                tabu = profile_daten.get('tabu_begriffe', [])
            if isinstance(tabu, list):
                return tabu
        # Slow path: DB query (when profile_daten not provided)
        if active_profile_id:
            from database.db import SessionLocal
            from database.models import Profile
            import json as _json
            _db = SessionLocal()
            try:
                _p = _db.query(Profile).filter_by(id=active_profile_id).first()
                if _p and _p.daten:
                    _pdata = _json.loads(_p.daten) if isinstance(_p.daten, str) else (_p.daten or {})
                    _basis = _pdata.get('basis', {})
                    if isinstance(_basis, dict):
                        tabu = _basis.get('tabu_begriffe', [])
                    else:
                        tabu = _pdata.get('tabu_begriffe', [])
                    if isinstance(tabu, list):
                        return tabu
            finally:
                _db.close()
    except Exception as _e:
        print(f"[QA-INT] _qa_load_tabu skip: {_e}")
    return []


def _qa_load_faqs(active_profile_id):
    """Load profile_faqs list for the active profile from DB. MUST NOT raise.
    Returns [] on any error.
    """
    if not active_profile_id:
        return []
    try:
        from database.db import SessionLocal
        from database.models import ProfileFaq
        _db = SessionLocal()
        try:
            _rows = _db.query(ProfileFaq).filter_by(profile_id=active_profile_id).all()
            return [
                {'id': r.id, 'frage_muster': r.frage_muster,
                 'antwort': r.antwort, 'kategorie': r.kategorie}
                for r in _rows
            ]
        finally:
            _db.close()
    except Exception as _e:
        print(f"[QA-INT] _qa_load_faqs skip: {_e}")
    return []


def _qa_pipeline_dispatch(neuer_text, line_id, kontext, ls, sio):
    """Phase 08.5: Classify utterance and dispatch to qa_pipeline.

    Called from analyse_loop after the Phase 06.3 comment block.
    Guards:
      - D-02: Skip when kw_fired_for_line == current line_id (Keyword-Matcher already fired)
      - Phase 06.2 Slot-1 mutex: Skip when slot1_variant_busy_until in future

    Emits:
      - qa_slot1      — full response text for Slot 1
      - qa_soft_hint  — D-04 LOCKED text for low-confidence / tabu / empty paths

    MUST NOT raise into the calling loop.
    """
    import time as _time
    try:
        with ls.state_lock:
            _kw_fired_for = ls.state.get('kw_fired_for_line')
            _user_id = ls.state.get('user_id') or 0
            _anrede = ls.state.get('session_anrede') or 'Sie'
            _slot1_busy_until = ls.state.get('slot1_variant_busy_until', 0.0)
            _active_sid = ls.state.get('active_sid')
            _active_profile_id = ls.state.get('active_profile_id')

        # D-02: Keyword-Matcher already fired for this utterance → skip
        if _kw_fired_for == line_id:
            print(f"[QA-INT] D-02 skip: kw_fired_for_line={_kw_fired_for} == line_id={line_id}")
            return

        # Phase 06.2 Slot-1 mutex: Slot 1 busy from keyword-match → skip
        if _time.monotonic() < _slot1_busy_until:
            print(f"[QA-INT] slot1 busy skip (busy_until={_slot1_busy_until:.1f})")
            return

        # No active session → skip (no point emitting to nobody)
        if not _active_sid:
            return

        from services.qa_pipeline import (
            classify_utterance, generate_qa_response,
            match_faq, apply_tabu_filter
        )
        from config import CLASSIFIER_CONFIDENCE_THRESHOLD

        # Load profile data for context (already in memory via live_session)
        import services.live_session as _ls_ref
        try:
            _profile_name, _profile_daten = _ls_ref.get_active_profile()
        except Exception:
            _profile_daten = {}

        _tabu_begriffe = _qa_load_tabu(_active_profile_id, _profile_daten)

        _qa_result = classify_utterance(neuer_text, kontext, _user_id)
        _kat = _qa_result.get('kategorie', 'smalltalk_none')
        _conf = _qa_result.get('confidence', 0.0)
        print(f"[QA-INT] classify kategorie={_kat} conf={_conf:.2f} line={line_id}")

        def _emit_soft_hint(reason=''):
            """Emit D-04 LOCKED soft-hint text to active session."""
            try:
                sio.emit('qa_soft_hint', {
                    'text': 'Neuer Einwand \u2014 noch kein Vorschlag',
                    'reason': reason,
                }, room=_active_sid)
                print(f"[QA-INT] soft_hint emitted reason={reason}")
            except Exception as _e:
                print(f"[QA-INT] emit soft_hint skip: {_e}")

        def _emit_qa_slot1(text):
            try:
                sio.emit('qa_slot1', {'text': text}, room=_active_sid)
                # Mark Slot 1 busy for ~8s (Phase 06.2 mutex pattern)
                with ls.state_lock:
                    ls.state['slot1_variant_busy_until'] = _time.monotonic() + 8.0
                print(f"[QA-INT] qa_slot1 emitted len={len(text)}")
            except Exception as _e:
                print(f"[QA-INT] emit qa_slot1 skip: {_e}")

        if _kat == 'einwand_unknown':
            if _conf < CLASSIFIER_CONFIDENCE_THRESHOLD:
                _emit_soft_hint(reason='low_confidence')
            else:
                _antwort = generate_qa_response(
                    neuer_text, 'einwand_unknown', _profile_daten, _anrede,
                    confidence=float(_conf), user_id=_user_id
                )
                if not _antwort:
                    _emit_soft_hint(reason='empty_response')
                elif apply_tabu_filter(_antwort, _tabu_begriffe):
                    _emit_soft_hint(reason='tabu_filtered')
                    print(f"[QA-INT] response tabu-filtered len={len(_antwort)}")
                else:
                    _emit_qa_slot1(_antwort)

        elif _kat == 'frage':
            _faqs = _qa_load_faqs(_active_profile_id)
            _matched_faq = match_faq(neuer_text, _faqs, threshold=0.75) if _faqs else None

            if _matched_faq:
                _faq_antwort = _matched_faq.get('antwort', '')
                if apply_tabu_filter(_faq_antwort, _tabu_begriffe):
                    _emit_soft_hint(reason='tabu_filtered_faq')
                else:
                    _emit_qa_slot1(_faq_antwort)
                    # Increment FAQ used_count (best-effort)
                    try:
                        from database.db import SessionLocal as _SL
                        from database.models import ProfileFaq as _PF
                        _db2 = _SL()
                        try:
                            _row = _db2.query(_PF).filter_by(id=_matched_faq['id']).first()
                            if _row:
                                _row.used_count = (_row.used_count or 0) + 1
                                _db2.commit()
                        finally:
                            _db2.close()
                    except Exception as _uc_e:
                        print(f"[QA-INT] used_count inc skip: {_uc_e}")
            else:
                # No FAQ match → fall back to generated response
                if _conf < CLASSIFIER_CONFIDENCE_THRESHOLD:
                    _emit_soft_hint(reason='no_faq_low_conf')
                else:
                    _antwort = generate_qa_response(
                        neuer_text, 'frage', _profile_daten, _anrede,
                        confidence=float(_conf), user_id=_user_id
                    )
                    if not _antwort:
                        _emit_soft_hint(reason='no_faq_empty')
                    elif apply_tabu_filter(_antwort, _tabu_begriffe):
                        _emit_soft_hint(reason='no_faq_tabu')
                    else:
                        _emit_qa_slot1(_antwort)
        # smalltalk_none / einwand_known → no action (Slot bleibt wie es ist)

    except Exception as _qa_int_e:
        print(f"[QA-INT] _qa_pipeline_dispatch failed: {_qa_int_e}")


def coaching_loop():
    """Call 2 — Berater-Coaching (Haiku, parallel). [04.8 P07: Sonnet→Haiku]"""
    import services.live_session as ls
    from extensions import socketio as sio
    _bof_count_local = 0  # local ref updated via ls._bof_lock
    while True:
        ls.coaching_trigger.wait(timeout=ANALYSE_INTERVALL)
        ls.coaching_trigger.clear()
        with ls.pause_lock:
            if ls.is_paused:
                continue
        with ls.coaching_lock:
            if not ls.coaching_buffer:
                continue
            segmente  = list(ls.coaching_buffer)
            t_start_c = ls.coaching_buffer[0].get('t_start', time.monotonic())
            ls.coaching_buffer.clear()

        # BOF-Zähler aktualisieren
        with ls._bof_lock:
            for s in segmente:
                if s['speaker'] == 'Berater':
                    if '?' in s['text']:
                        ls._bof_count = 0
                    else:
                        ls._bof_count += 1
            bof_snapshot = ls._bof_count

        kontext = " ".join(ls.analysiert_bisher[-10:])
        try:
            result    = analysiere_coaching(segmente, kontext)
            latency_c = round(time.monotonic() - t_start_c, 2)
            ts        = datetime.now().strftime('%H:%M:%S')
            tipp      = result.get('tipp')
            painpoint = result.get('painpoint')
            kategorie = result.get('kategorie') or ''
            kb_delta  = result.get('kb_delta', 0) or 0

            # Kaufbereitschaft via Claude-Delta anpassen
            if isinstance(kb_delta, (int, float)) and kb_delta != 0:
                ls.update_kaufbereitschaft(int(kb_delta))
                with ls.kb_lock:
                    kb_aktuell = ls.kaufbereitschaft
                with ls.state_lock:
                    ls.state['kaufbereitschaft'] = kb_aktuell

            if kategorie == 'frage' and bof_snapshot < 2:
                tipp      = None
                kategorie = ''

            # ── Verhaltensbasierte Tipps (deterministisch, kein Claude-Call) ──
            try:
                stats = ls.get_speech_stats()
                if stats['tempo'] > 160 and not tipp:
                    tipp      = f"Langsamer sprechen — dein Tempo liegt bei {stats['tempo']} WPM."
                    kategorie = 'redeanteil'
                elif stats['redeanteil'] > 65 and not tipp:
                    tipp      = f"Lass den Kunden mehr zu Wort kommen — dein Redeanteil: {stats['redeanteil']}%."
                    kategorie = 'redeanteil'
                elif stats.get('monolog', 0) > 30 and not tipp:
                    tipp      = f"Dein letzter Monolog war {stats['monolog']} Sekunden — stelle eine Frage."
                    kategorie = 'redeanteil'
            except Exception:
                pass

            if not tipp and not painpoint:
                continue

            print(f"[Claude-2] tipp={tipp!r}  pain={painpoint!r}  Latenz={latency_c}s")

            with ls.log_lock:
                ls.conversation_log.append({
                    'ts': ts, 'type': 'latenz_coaching', 'latency': latency_c,
                })

            if painpoint:
                with ls.painpoints_lock:
                    if ls.ist_painpoint_duplikat(painpoint, ls.painpoints):
                        print(f"[Claude-2] Painpoint Duplikat: {painpoint!r}")
                        painpoint = None
                    else:
                        ls.painpoints.append({'ts': ts, 'text': painpoint})
                if painpoint:
                    with ls.log_lock:
                        ls.conversation_log.append({
                            'ts': ts, 'type': 'painpoint', 'text': painpoint,
                        })

            if tipp:
                with ls.log_lock:
                    ls.conversation_log.append({
                        'ts': ts, 'type': 'tipp', 'text': tipp, 'kategorie': kategorie,
                    })

            # ── Coaching-WebSocket-Emit entfernt (Phase 06.6 / RULE-01-Erweiterung) ──
            # Der coaching-Channel landete im Frontend via _showProactiveTipp auf Slot 1
            # und hat die EWB-Antwort nach Stream-Ende ueberschrieben. Coaching-Daten
            # bleiben vollstaendig erhalten fuer Post-Call-Scoring: conversation_log
            # (oben), _write_ft_assistant_event (unten) und der [Claude-2]-Log-Print.
            # Live-Anzeige waehrend des Calls war kontraproduktiv — der Berater kann
            # nicht gleichzeitig lesen und zuhoeren.

            # ── FT logging hook (Phase 04.7.1) ────────────────────────────────
            try:
                _coach_text_parts = []
                if tipp:
                    _coach_text_parts.append(f"tipp: {tipp}")
                if painpoint:
                    _coach_text_parts.append(f"painpoint: {painpoint}")
                _coach_text = ' | '.join(_coach_text_parts)
                if _coach_text:
                    _write_ft_assistant_event(
                        module='coaching_live',
                        hint_type='coaching',
                        hint_text=_coach_text,
                        model_used=config.MODEL_COACHING,
                        context={
                            'hint_category': 'coaching',
                        },
                    )
            except Exception as _e:
                print(f"[FT] coaching_live hook skipped: {_e}")
        except Exception as e:
            print(f"[Claude-2] Fehler: {e}")
