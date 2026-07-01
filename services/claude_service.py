import json
import os
import time
import threading
from datetime import datetime
import anthropic
import config
from config import ANTHROPIC_API_KEY, ANALYSE_INTERVALL, KATEGORIE_LABEL

# Anthropic minimum: 1024 tokens ≈ 4096 chars
_CACHE_MIN_CHARS = 4096

# ── Circuit-Breaker fuer EWB Sonnet TTFT (D-07 Phase 08.20) ──────────────────
# Tracks TTFT for last 5 EWB auto-variant calls. If 3/5 exceed threshold:
# fallback to Haiku for 30 seconds (DACH: Sonnet->Haiku, USA: Haiku->Haiku).
# Rollback: set ENV MODEL_PIP_AUTOVAR=claude-haiku-4-5-20251001 to disable Sonnet entirely.
import collections as _collections
_ewb_ttft_history: _collections.deque = _collections.deque(maxlen=5)  # last 5 TTFT values in ms
_ewb_fallback_until: float = 0.0    # monotonic timestamp — Haiku fallback active until this time
_ewb_circuit_lock = threading.Lock()
# CLAUDE.md: MODEL_ANALYSE (analyse_loop) stays Haiku — not touched here.
# This circuit-breaker only affects MODEL_PIP_AUTOVAR (EWB streaming).

# Welle 6 (Aufraeumen 2026-06-18): die EWB-Prompt-Pipeline-Importe (build_ewb_prompt aus
# services.ewb_pipeline, resolve_prompt_version aus services.prompt_pipeline) sind hier
# entfernt — nach dem MEDFIX (SYSTEM_PROMPT_BASE) hatte dieser EWB-Pfad in claude_service
# keinen lebenden Aufrufer mehr (grep-belegt). resolve_prompt_version lebt weiter in
# services/prompt_pipeline.py (classifier/qa_pipeline + training_* nutzen es aktiv).

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

Ordne den erkannten Einwand zusätzlich in EINE der folgenden Schubladen ein (intent_type, geteilte Taxonomie):
- echter_einwand: konkretes, faktenbasiertes, verhandelbares Problem
- vorwand: vage/generisch, früh, Gesprächsabbruch-Schutz
- reflexeinwand: automatische Abwehr auf die Unterbrechung selbst
- kaufsignal: Detail-Frage = "überzeug mich"
- aufschub: will vertagen
- info_frage: Produktwissen-Frage, kein Einwand
- gatekeeper: "stelle durch / darf nicht weitergeben"
- wettbewerber_referenz: "nutzen schon X"
- hard_opt_out: "löschen Sie meine Nummer / nie wieder anrufen"
- commitment: nackte Zustimmung / grünes Licht
- meta_kommunikation: "höre Sie schlecht / bin im Auto"
Wähle den treffendsten Wert EXAKT aus dieser Liste (kleingeschrieben, mit Unterstrich).

Antworte IMMER als valides JSON, nichts anderes:

Falls KEIN Einwand:
{"einwand": false, "notiz": "Kurze Beschreibung was stattdessen gesagt wurde (max 1 Satz)"}

Falls Einwand erkannt:
{"einwand": true, "typ": "Einwand-Typ", "intent_type": "echter_einwand", "confidence": 0.8, "intensitaet": "mittel oder hoch", "ist_vorwand": false, "einwand_zitat": "Wörtliches Zitat max 15 Wörter", "gegenargument_1": "Erster Ansatz, direkt, 2-3 Sätze reiner Text, mit offener Gegenfrage", "gegenargument_2": "Alternativer Ansatz, weicher oder aus anderer Perspektive, 2-3 Sätze reiner Text, mit offener Gegenfrage"}
- intent_type: die treffendste Schublade aus der Liste oben
- confidence: deine Sicherheit 0.0-1.0, dass dieser Einwand-Typ zutrifft

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


def _build_coaching_prompt(sid: str = None) -> str:
    import services.live_session as ls
    # D-05: get_active_profile() deprecated else-Zweig entfernt (Phase 08.19.4 Plan 04)
    _, pdata = ls.get_profile_for_sid(sid) if sid else ('', {})
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

# Phase 08.23.2.C — Modus-spezifische Phasen-Listen (Req-2).
# Phase-Namen sind englische Lowercase-Tokens (Code-Identifier, ASCII per CLAUDE.md).
_PHASE_NAMES_COLD_CALL = {
    1: 'opener',
    2: 'permission',
    3: 'reason',
    4: 'pitch',
    5: 'discovery',
    6: 'closing',
}
_PHASE_NAMES_MEETING = {
    1: 'intro',
    2: 'agenda',
    3: 'discovery',
    4: 'pitch',
    5: 'objection',
    6: 'closing',
}
_PHASE_NAMES_GATEKEEPER = {
    1: 'greeting',
    2: 'identify',
    3: 'bypass',
    4: 'handoff',
}

# Hilfs-Mapping fuer Modus -> (phasen_dict, max_phase).
_PHASE_NAMES_BY_MODE = {
    'cold_call':   (_PHASE_NAMES_COLD_CALL, 6),
    'meeting':     (_PHASE_NAMES_MEETING, 6),
    'gatekeeper':  (_PHASE_NAMES_GATEKEEPER, 4),
}

# Backward-Compat-Alias fuer bestehende Callers (Z.970/974/983/984 im Analyse-Loop).
# Callers haben keinen Modus-Kontext — Alias bleibt erhalten.
_PHASE_NAMES = {
    1: 'Opener',
    2: 'Qualifizierung',
    3: 'Bedarfsanalyse',
    4: 'Pitch',
    5: 'Einwandbehandlung',
    6: 'Abschluss',
}

PHASE_CLASSIFIER_PROMPT = """Du klassifizierst die aktuelle Phase eines B2B-Verkaufsgesprächs im Modus '{mode}'.

Phasen fuer diesen Modus: {labels}
Aktuelle Phase: {current_phase}, seit {elapsed_s}s im Gespräch.

Anhaltspunkte je Phase (Cues):
{cues}

Letzte Gesprächsaussagen (chronologisch):
{transcript_window}

Bestimme die AKTUELLE Phase basierend auf den letzten Aussagen.
Eine Phase kann bestehen bleiben. Wähle die wahrscheinlichste Phase.
WICHTIG — Termin: unterscheide VORSCHLAG von echter VEREINBARUNG.
- VORGESCHLAGEN (Berater bietet an, noch KEINE Zusage): "darf ich Sie Donnerstag
  anrufen?", "ich schicke Ihnen mal einen Termin/Kalender-Eintrag", "wir koennten
  naechste Woche sprechen" → das ist NOCH NICHT Abschluss → bleibe Phase 4/5.
- BESTAETIGT/VEREINBART (beidseitige, feste Zusage): "passt, machen wir", "ja,
  Dienstag 10 Uhr", "abgemacht", oder der Berater fasst die feste Abmachung
  zusammen ("super, dann Dienstag 10 Uhr, ich trage es ein") → Phase
  Abschluss/Terminvereinbarung; bleibe dann NICHT auf Bedarfsanalyse haengen.
Im COLD CALL hoerst du NUR den Berater (die Kunden-Zusage ist NICHT hoerbar) — sei
KONSERVATIV: werte nur als Abschluss, wenn der Berater die Vereinbarung als
BESTAETIGT formuliert/zusammenfasst. Berater-Optimismus oder ein blosser Vorschlag
ist KEIN Abschluss.

Antworte NUR als JSON:
{{"phase": <1-N>, "confidence": <0.0-1.0>, "grund": "<max 10 Wörter>"}}"""

# TAXO1-Welle 4 Addition B: Phasen-Cues je Modus — gibt dem Klassifikator klare
# Anhaltspunkte (vorher nur nackte Label-Woerter). Besonders Phase 5
# (Einwandbehandlung) + Phase 6 (Abschluss/Terminvereinbarung) explizit, damit ein
# gebuchter Termin die Phase tatsaechlich auf 6 dreht (vorher blieb sie auf 3).
_PHASE_CUES_COLD_CALL = {
    1: 'Begruessung, Vorstellung, Aufhaenger',
    2: 'Erlaubnis-Frage, "haben Sie kurz Zeit", Gespraechs-Rahmen abklaeren',
    3: 'Grund des Anrufs, Nutzenversprechen, erste Einordnung',
    4: 'Pitch/Loesung praesentieren, konkretes Angebot',
    5: 'Einwandbehandlung: Kunde bringt Bedenken/Einwand, Berater entkraeftet',
    6: 'Abschluss/Terminvereinbarung: Termin BESTAETIGT/fest vereinbart, Berater '
       'fasst die feste Abmachung zusammen ("passt, machen wir", "ja Dienstag '
       '10 Uhr", "super, dann Dienstag, ich trage es ein"). NICHT bei blossem '
       'Vorschlag ("darf ich anrufen?", "schicke Ihnen einen Termin") — der bleibt '
       'Phase 4/5 (im Cold Call ist die Kunden-Zusage nicht hoerbar → konservativ)',
}
_PHASE_CUES_MEETING = {
    1: 'Begruessung, Smalltalk, Vorstellung',
    2: 'Agenda/Ablauf abstimmen, Ziele des Termins',
    3: 'Bedarfsanalyse, Fragen, Discovery, Situation des Kunden',
    4: 'Pitch/Loesung praesentieren, Demo, konkretes Angebot',
    5: 'Einwandbehandlung: Kunde bringt Bedenken/Einwand, Berater entkraeftet',
    6: 'Abschluss/Terminvereinbarung: Termin/Folgetermin BEIDSEITIG bestaetigt/'
       'vereinbart, Vertrag/Angebot-Zusage, fester naechster Schritt. Ein blosser '
       'Vorschlag ohne Zusage ist noch Phase 4/5.',
}
_PHASE_CUES_GATEKEEPER = {
    1: 'Begruessung des Gatekeepers',
    2: 'Identifikation, wen man erreichen will',
    3: 'Bypass-Versuch, Durchstellen erbitten',
    4: 'Uebergabe an Zielperson / Termin fuer Rueckruf',
}
_PHASE_CUES_BY_MODE = {
    'cold_call':  _PHASE_CUES_COLD_CALL,
    'meeting':    _PHASE_CUES_MEETING,
    'gatekeeper': _PHASE_CUES_GATEKEEPER,
}


def classify_phase(transcript_window, current_phase, elapsed_s, mode, sid: str = None):
    """Modus-bewusster Phasen-Klassifikator (Phase 08.23.2.C Req-2).

    Args:
        transcript_window: List[str] der letzten Berater-Saetze.
        current_phase: int — aktuell aktive Phasen-Nummer.
        elapsed_s: float — Sekunden seit Gespraechs-Start.
        mode: 'cold_call' | 'meeting' | 'gatekeeper'.

    Returns:
        dict {'phase': int (1..max_phase), 'confidence': float (0..1), 'grund': str}
        oder None bei API-Fehler / ungueltigem Output.
    """
    if not transcript_window:
        return None

    # Modus-Dispatch: waehle Phasen-Liste + max_phase basierend auf mode.
    phase_names, max_phase = _PHASE_NAMES_BY_MODE.get(
        mode, (_PHASE_NAMES_COLD_CALL, 6)  # Fallback: cold_call
    )

    labels_str = ', '.join(f'{i}={name}' for i, name in phase_names.items())
    formatted = "\n".join(f"- {t}" for t in transcript_window[-10:])
    # Addition B: Phasen-Cues je Modus (Phase 5/6 explizit, Termin -> Phase 6).
    _cue_map = _PHASE_CUES_BY_MODE.get(mode, _PHASE_CUES_COLD_CALL)
    cues_str = "\n".join(f"- {i}={name}: {_cue_map.get(i, '')}"
                         for i, name in phase_names.items())
    prompt = PHASE_CLASSIFIER_PROMPT.format(
        labels=labels_str,
        cues=cues_str,
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
                             context_tag='phase_classify', session_id=sid)
                log_api_cost('anthropic', 'haiku-4-5', user_id=None,
                             units=out_tok/1000.0, unit_type='per_1k_output_tokens',
                             context_tag='phase_classify', session_id=sid)
        except Exception as _e:
            print(f"[CostHook] claude phase_classify skipped: {_e}")
        # ────────────────────────────────────────────────────────────────────
        if not resp.content:
            print(f"[claude] empty content from API (module=phase_classify)")
            return None
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
        # Range-Validation per Modus (Req-2 Acceptance, T-08.23.2.C-15).
        if 1 <= phase <= max_phase and 0.0 <= conf <= 1.0:
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


def infer_customer_state(seller_transcript, phase, sid: str = None):
    """Haiku call for D-05 cold-call customer-state inference.
    Returns dict or None on empty input / parse failure.
    sid (TAXO1-03 B-B): per-SID Kosten-Attribution an log_api_cost."""
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
                             context_tag='coldcall_infer', session_id=sid)
                log_api_cost('anthropic', 'haiku-4-5', user_id=None,
                             units=out_tok/1000.0, unit_type='per_1k_output_tokens',
                             context_tag='coldcall_infer', session_id=sid)
        except Exception as _e:
            print(f"[CostHook] claude coldcall_infer skipped: {_e}")
        # ────────────────────────────────────────────────────────────────────
        if not resp.content:
            print(f"[claude] empty content from API (module=coldcall_infer)")
            return None
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


def analysiere_mit_claude(neuer_text: str, kontext: str, sid: str = None) -> dict:
    user_msg = f"""Bisheriger Gesprächskontext (zur Orientierung, letzte Aussagen):
{kontext if kontext else "(Kein vorheriger Kontext)"}

Neues Gesprächssegment (analysiere NUR dieses auf Einwände):
{neuer_text}"""
    # ── Klassifikations-System-Prompt ──────────────────────────────────────────
    # MEDFIX (2026-06-18): SYSTEM_PROMPT_BASE (JSON-Einwand-Schema, oben) statt des
    # frueheren build_ewb_prompt (EWB-ANTWORT-Prosa-Prompt) — sonst lieferte Haiku Prosa
    # → _parse_json {} → Medium-Lane-Emit feuerte nie. Historie im Log (taxo1-04-Diagnose).
    # Welle 6 (Aufraeumen 2026-06-18): der tote build_ewb_prompt-Pfad + die nur dafuer
    # berechneten per-SID user_id/anrede-Reads sind entfernt (0 Reads nach MEDFIX, Punkt 14).
    # analysiere_mit_claude KLASSIFIZIERT nur; die Live-ANTWORT laeuft separat
    # (streame_auto_variante / Matcher), nicht hier (Phase-06.3-Invariante).
    _system_prompt = SYSTEM_PROMPT_BASE
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
                         context_tag='live_haiku', session_id=sid)
            log_api_cost('anthropic', 'haiku-4-5', user_id=None,
                         units=out_tok/1000.0, unit_type='per_1k_output_tokens',
                         context_tag='live_haiku', session_id=sid)
        # Cache-Token-Logging (B1 Review-Finding)
        _cache_hits = getattr(getattr(msg, 'usage', None), 'cache_read_input_tokens', 0) or 0
        _cache_writes = getattr(getattr(msg, 'usage', None), 'cache_creation_input_tokens', 0) or 0
        if _cache_hits > 0:
            log_api_cost('anthropic', 'haiku-4-5', user_id=None,
                         units=_cache_hits/1000.0, unit_type='per_1k_cache_read_tokens',
                         context_tag='analyse', call_site='analyse', session_id=sid)
        if _cache_writes > 0:
            log_api_cost('anthropic', 'haiku-4-5', user_id=None,
                         units=_cache_writes/1000.0, unit_type='per_1k_cache_write_tokens',
                         context_tag='analyse', call_site='analyse', session_id=sid)
    except Exception as _e:
        print(f"[CostHook] claude live_haiku skipped: {_e}")
    # ────────────────────────────────────────────────────────────────────
    if not msg.content:
        print(f"[claude] empty content from API (module=analyse)")
        return {}
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
    # _ewb_fallback_until ist modul-global (Z.19) und wird unten (Fallback-Zweig)
    # zugewiesen → ohne diese Deklaration macht Python die Variable funktions-lokal,
    # und der LESE-Zugriff im Circuit-Breaker-Check (vor der Zuweisung) wirft
    # UnboundLocalError. global behebt das (einziger reassignierte Modul-Global hier).
    global _ewb_fallback_until
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
    # D-07 Circuit-Breaker: check if TTFT fallback is active
    import time as _time_autovar
    with _ewb_circuit_lock:
        _cb_in_fallback = _time_autovar.monotonic() < _ewb_fallback_until
    _model_autovar = config.MODEL_PIP_AUTOVAR
    if _cb_in_fallback:
        _model_autovar = 'claude-haiku-4-5-20251001'  # DACH fallback (CLAUDE.md: Haiku only in fallback)
        print(f"[CircuitBreaker-EWB] Haiku fallback active sid={sid}")

    print(f"[PiP-AutoVar] ENTRY trigger={trigger} sid={sid} slot={slot} text={neuer_text[:60]!r}")
    sio.emit('pip_stream_start', {'slot': slot, 'raw_text': True}, room=sid)
    full_text = ''
    _first_token_autovar = True
    try:
        _t_stream_start = _time_autovar.monotonic()
        with claude_client.messages.stream(
            model=_model_autovar,
            max_tokens=200,
            system=_system_autovar,
            messages=[{'role': 'user', 'content': user_msg}]
        ) as stream:
            for token in stream.text_stream:
                if _first_token_autovar:
                    _ttft_ms = (_time_autovar.monotonic() - _t_stream_start) * 1000
                    _first_token_autovar = False
                    with _ewb_circuit_lock:
                        _ewb_ttft_history.append(_ttft_ms)
                        _threshold_ms = int(os.getenv('EWB_SONNET_FALLBACK_TTFT_MS', '1500'))
                        _history_snap = list(_ewb_ttft_history)
                        if len(_history_snap) >= 5:
                            _above_count = sum(1 for t in _history_snap if t > _threshold_ms)
                            if _above_count >= 3 and not _cb_in_fallback:
                                _ewb_fallback_until = _time_autovar.monotonic() + 30.0
                                print(f"[CircuitBreaker-EWB] TRIGGERED: {_above_count}/5 calls > {_threshold_ms}ms "
                                      f"(last={_ttft_ms:.0f}ms) — Haiku fallback 30s sid={sid}")
                    print(f"[EWB-TTFT] {_ttft_ms:.0f}ms model={_model_autovar} sid={sid}")
                full_text += token
                sio.emit('pip_token', {'slot': slot, 'token': token, 'raw_text': True}, room=sid)
        # ── FOLD A-2 / Req 11: Anzeige roh (echte Namen, Live-Nutzen), Storage anonymisiert (DSGVO) ──
        # Analog Knopf-Pfad (streame_manual_ewb_variante:823 + deepgram_service.py Knopf-Storage).
        # Die dem Berater LIVE gezeigte Antwort behaelt die ECHTEN Namen — [PERSON_A] waere unbrauchbar.
        # Frueher reassignte diese Stelle den Anzeige-Text via anonymize_output -> die ANZEIGE wurde
        # anon (Bug); der WR-01-Zweck (anonymisierte Persistenz) wandert in die Storage-Version unten.
        cleaned_display = full_text.strip()
        # Anzeige ZUERST emittieren (Punkt 25 Latenz: Berater hat die Antwort, bevor die
        # Hintergrund-Storage berechnet wird — der seltene frische Fallback verzoegert nie die Anzeige).
        # WICHTIG (DSGVO): EIGENES Payload-Dict fuer die Anzeige — NIE dasselbe Objekt wie das
        # Rueckgabe-result mutieren. Sonst koennte (je nach SocketIO-Serialisierungs-Timing) die
        # spaeter angehaengte anonymisierte Storage-Version ans Client-Payload leaken.
        display_result = {'einwand': True, 'typ': 'AUTO', 'gegenargument_1': cleaned_display}
        sio.emit('pip_token_done', {'slot': slot, 'result': display_result, 'raw_text': True}, room=sid)
        # Separate anonymisierte Storage-Version (Vertrag fuer Plan 08 record_suggestion_offer):
        # anonymize_for_storage garantiert nie roh / nie verloren / Notweg geloggt.
        try:
            from services.anonymization import anonymize_for_storage
            cleaned_storage = anonymize_for_storage(cleaned_display, sid)
        except Exception as _anon_av_err:
            # Helfer faengt intern schon ab; dieser Guard ist Defense-in-depth (nie roh nach aussen).
            print(f"[ANON] anonymize_for_storage AutoVar failed (non-fatal): {_anon_av_err}")
            cleaned_storage = '[ANON_FEHLER]'
        # Rueckgabe-result ist ein SEPARATES Dict (traegt _storage_text fuer Plan 08, geht NIE an die Anzeige).
        result = {'einwand': True, 'typ': 'AUTO',
                  'gegenargument_1': cleaned_display, '_storage_text': cleaned_storage}
        print(f"[PiP-AutoVar] DONE sid={sid} slot={slot} chars={len(cleaned_display)}")
        try:
            from services.cost_tracker import log_api_cost
            final_msg = stream.get_final_message()
            u = getattr(final_msg, 'usage', None)
            if u is not None:
                in_tok = getattr(u, 'input_tokens', 0) or 0
                out_tok = getattr(u, 'output_tokens', 0) or 0
                log_api_cost('anthropic', _model_autovar, user_id=None,
                             units=in_tok/1000.0, unit_type='per_1k_input_tokens',
                             context_tag='pip_autovar', session_id=sid)
                log_api_cost('anthropic', _model_autovar, user_id=None,
                             units=out_tok/1000.0, unit_type='per_1k_output_tokens',
                             context_tag='pip_autovar', session_id=sid)
            # Cache-Token-Logging (B1 Review-Finding)
            _cache_hits = getattr(getattr(final_msg, 'usage', None), 'cache_read_input_tokens', 0) or 0
            _cache_writes = getattr(getattr(final_msg, 'usage', None), 'cache_creation_input_tokens', 0) or 0
            if _cache_hits > 0:
                log_api_cost('anthropic', _model_autovar, user_id=None,
                             units=_cache_hits/1000.0, unit_type='per_1k_cache_read_tokens',
                             context_tag='ewb', call_site='ewb', session_id=sid)
            if _cache_writes > 0:
                log_api_cost('anthropic', _model_autovar, user_id=None,
                             units=_cache_writes/1000.0, unit_type='per_1k_cache_write_tokens',
                             context_tag='ewb', call_site='ewb', session_id=sid)
        except Exception as _e:
            print(f"[CostHook] pip_autovar skipped: {_e}")
        # ── TAXO2-08 (FOLD A): Vorschlag erfassen (Slot B Auto-Variante) ──────────
        # Latenz-neutral (Punkt 25): NUR ein RAM-Append in record_suggestion_offer.
        # B1: interaction_id via get_or_open_moment IMMER setzen (RAM-Lookup, kein DB/Netz).
        # Anon-Vertrag (Plan 09): suggestion_text = cleaned_storage (die anonymisierte
        # Storage-Version, _storage_text) — NICHT der roh angezeigte cleaned_display.
        # try/except: der Live-Loop crasht nie.
        try:
            import services.live_session as _ls_av
            import time as _t_av
            _av_mode = (_ls_av._session_state.get(sid) or {}).get('mode', 'cold_call')
            _av_iid = None
            with _ls_av._session_state_lock:
                _av_iid = _ls_av.get_or_open_moment(sid, mode=_av_mode, now=_t_av.monotonic())
            _ls_av.record_suggestion_offer(
                slot='B', source='auto_variante', model=_model_autovar,
                suggestion_text=cleaned_storage, interaction_id=_av_iid,
            )
        except Exception as _av_cap_e:
            print(f"[PiP-AutoVar] record_suggestion_offer skip sid={sid}: {type(_av_cap_e).__name__}")
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

    # ── Phase 08.20: _user_id fuer build_profile_context (per-SID — WR-01) ──────
    try:
        import services.live_session as _ls_manual
        with _ls_manual._session_state_lock:
            _user_id = (_ls_manual._session_state.get(sid) or {}).get('user_id') or 0
    except Exception:
        _user_id = 0

    # ── Phase 08.13/08.20: Prompt-Caching EWB Manual (CACHE_EWB=True default) ───
    # D-01/08.20: Replace hardcoded system prompt with Voll-Profil context
    # build_profile_context() reads from _session_state[sid]['_profile_cache'] — no DB in hot path
    try:
        from services.prompt_pipeline import build_profile_context as _bpc_manual
        _ewb_manual_system = _bpc_manual(user_id=_user_id or 0, sid=sid)
        if not _ewb_manual_system:
            _ewb_manual_system = (
                "Du bist NERVE, ein Vertriebs-KI-Assistent im DACH-B2B. "
                "Liefere EINE sofort vorlesbare Gegenargumentation in 2-3 Saetzen. "
                "Kein Fachjargon, keine Floskeln. Ende mit Gegenfrage."
            )
    except Exception as _bpc_e:
        print(f"[EWB] profile_context error: {_bpc_e}")
        return {'error': f'profile_context failed: {_bpc_e}', 'gegenargument_1': None}
    if config.CACHE_EWB and len(_ewb_manual_system) >= _CACHE_MIN_CHARS:
        _system_manual = [{"type": "text", "text": _ewb_manual_system, "cache_control": {"type": "ephemeral"}}]
    else:
        _system_manual = _ewb_manual_system
    print(f"[Cache-Check] manual-ewb: {len(_ewb_manual_system)} chars, "
          f"cache={'on' if len(_ewb_manual_system) >= _CACHE_MIN_CHARS else 'off'}")
    # ──────────────────────────────────────────────────────────────────────────
    print(f"[PiP-Variante] ENTRY sid={sid} slot={slot} typ={typ!r}")
    # Phase 08.23.2.PIP-01 (Item a): source=manual_button kennzeichnet den EINZIGEN
    # legitimen Lese-Zonen-(slot 1)-Schreiber. Das FE-Source-Gate (pip-launcher.js)
    # laesst NUR diese Quelle in pip-slot-body-1 schreiben (zweite Verteidigungslinie).
    sio.emit('pip_stream_start', {'slot': slot, 'raw_text': True, 'source': 'manual_button'}, room=sid)
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
                    sio.emit('pip_token', {'slot': slot, 'token': token, 'raw_text': True, 'source': 'manual_button'}, room=sid)
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
        sio.emit('pip_token_done', {'slot': slot, 'result': result, 'raw_text': True, 'source': 'manual_button'}, room=sid)
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
                             context_tag='pip_variante', session_id=sid)
                log_api_cost('anthropic', 'haiku-4-5', user_id=None,
                             units=out_tok/1000.0, unit_type='per_1k_output_tokens',
                             context_tag='pip_variante', session_id=sid)
            # Cache-Token-Logging (B1 Review-Finding)
            _cache_hits = getattr(getattr(final_msg, 'usage', None), 'cache_read_input_tokens', 0) or 0
            _cache_writes = getattr(getattr(final_msg, 'usage', None), 'cache_creation_input_tokens', 0) or 0
            if _cache_hits > 0:
                log_api_cost('anthropic', 'haiku-4-5', user_id=None,
                             units=_cache_hits/1000.0, unit_type='per_1k_cache_read_tokens',
                             context_tag='ewb', call_site='ewb', session_id=sid)
            if _cache_writes > 0:
                log_api_cost('anthropic', 'haiku-4-5', user_id=None,
                             units=_cache_writes/1000.0, unit_type='per_1k_cache_write_tokens',
                             context_tag='ewb', call_site='ewb', session_id=sid)
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


def analysiere_coaching(segmente: list, kontext: str, sid: str = None) -> dict:
    gespraech = "\n".join(f"[{s['speaker']}] {s['text']}" for s in segmente)
    user_msg  = f"""Bisheriger Gesprächskontext:
{kontext if kontext else "(Kein vorheriger Kontext)"}

Aktuelles Gesprächssegment:
{gespraech}"""
    # Phase 04.8 P07: migrated Sonnet→Haiku per Haiku-only-live constraint
    msg = claude_client.messages.create(
        model=config.MODEL_COACHING,
        max_tokens=200,
        system=_build_coaching_prompt(sid=sid),
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
                         context_tag='coaching_haiku', session_id=sid)
            log_api_cost('anthropic', 'haiku-4-5', user_id=None,
                         units=out_tok/1000.0, unit_type='per_1k_output_tokens',
                         context_tag='coaching_haiku', session_id=sid)
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
        # Phase 08.19.4 D-03: Iterate over all active SIDs
        # O(N) SEQUENTIAL: Claude-Calls laufen sequentiell pro SID — Loop-Zeit waechst linear.
        # SKALIERUNG: Loop-Cycle-Dauer bei N parallelen Sessions messen.
        # Schwellwerte (Messung ausstehend):
        #   N=1: ~1-3s, N=5: ~5-15s (KRITISCH), N=20: >20s (nicht mehr Echtzeit)
        # Ab N=5 und Cycle-Zeit > 3s: Migration zu ThreadPoolExecutor.
        # Naechste Phase: Block-M (08.19.5 oder spaeter). Accepted for EA (50 users max).
        with ls._session_state_lock:
            active_sids = list(ls._session_state.keys())
        if not active_sids:
            continue

        _loop_start = time.monotonic()
        for sid in active_sids:
            # Re-check SID still alive (may have disconnected since snapshot)
            with ls._session_state_lock:
                sid_state = ls._session_state.get(sid)
            if not sid_state:
                continue
            if sid_state.get('state', {}).get('is_paused', False):
                continue  # per-SID pause — only skip this SID

            # Read per-SID transcript buffer (D-02 — implemented in Task 1 this plan)
            with ls._per_sid_transcript_lock:
                buf = ls._per_sid_transcript.get(sid, [])
                if not buf:
                    continue
                neuer_text = " ".join(e['text'] for e in buf)
                line_id    = buf[-1]['line_id']
                t_start    = buf[0].get('t_start', time.monotonic())
                kontext    = " ".join(sid_state.get('analysiert_bisher', [])[-20:])
                # WR-02: cap at 200 entries (rolling window) to bound memory per session
                _existing = sid_state.get('analysiert_bisher', [])
                _existing.extend(e['text'] for e in buf)
                sid_state['analysiert_bisher'] = _existing[-200:]
                ls._per_sid_transcript[sid] = []  # clear consumed entries

            # D-09: Inject active learning cards into kontext (per-SID — WR-02 Phase 08.19.5.1)
            with ls._session_state_lock:
                _lk_cards = ls._session_state.get(sid, {}).get('state', {}).get('active_learning_cards', [])
            if _lk_cards:
                _lk_ctx = "\n\n[Aktive Lernkarten des Beraters - bei passender Situation mit lernkarte_match=true markieren]:\n"
                for _c in _lk_cards[:5]:
                    _lk_ctx += f"- [{_c['category']}] {_c['final_text'][:80]}\n"
                kontext = kontext + _lk_ctx
            print(f"[Claude-1] SID={sid} Analysiere (line {line_id}): {neuer_text[:80]}…")
            with ls.state_lock:
                ls.state['aktiv'] = True
            try:
                # Phase 06.3: analyse_loop no longer renders into PiP slots.
                # Keyword-Matcher (06.2) is sole primary for Slot 0 + Slot 1.
                # Non-streaming call preserves ergebnis for FT-events, Kaufbereitschaft,
                # Phase-Classifier, Cold-Call-Inference, Active-Hint-Orchestration.
                ergebnis = analysiere_mit_claude(neuer_text, kontext, sid=sid)
                # SID liveness check after Claude API call
                with ls._session_state_lock:
                    if sid not in ls._session_state:
                        print(f"[analyse_loop] SID {sid} gone during Claude call — silent drop")
                        continue

                # ── TAXO1-Welle 4 (Task 2): Medium-Lane-Cutover (intent_event) ───
                # mode-Quelle per-SID (TAXO1-07: W7 erledigt — globales _session_modes
                # geloescht, dieser Read jetzt aus _session_state[sid]['mode']).
                _med_mode = (ls._session_state.get(sid) or {}).get('mode', 'cold_call')
                # FUND B (Gemini-R2): confidence aus dem neuen Haiku-JSON-Feld; NIE None
                # (Default 0.7 — Haiku-Einwand-Erkennung ist konservativ getriggert,
                # "eher sicher"; bewusster Interim, TAXO3 baut den EWB-Prompt ohnehin um).
                _mc = ergebnis.get('confidence')
                try:
                    _med_conf = float(_mc)
                    if not (0.0 <= _med_conf <= 1.0):
                        _med_conf = 0.7
                except (TypeError, ValueError):
                    _med_conf = 0.7
                if ergebnis.get('einwand'):
                    # intent_type aus §1 (validiert); Fallback echter_einwand wenn Haiku
                    # einen ungueltigen/fehlenden Wert liefert (kein Drop des Events).
                    from services.intent_taxonomy import is_valid_intent_type
                    _it = ergebnis.get('intent_type')
                    if not (isinstance(_it, str) and is_valid_intent_type(_it)):
                        _it = 'echter_einwand'
                    # Per-SID-Kontext + Moment-Fenster oeffnen + IL-2-Write (alles unter
                    # _session_state_lock; get_or_open_moment ist lock-frei). VOR dem
                    # Antwort-Trigger (_qa_pipeline_dispatch) — IL-2-Vertrag.
                    _iid = None
                    _med_user_id = None
                    _med_org_id = None
                    _med_phase = None
                    _med_cid = None
                    with ls._session_state_lock:
                        _med_sd = ls._session_state.get(sid) or {}
                        _med_user_id = _med_sd.get('user_id')
                        _med_org_id = _med_sd.get('org_id')
                        _med_st = _med_sd.get('state')
                        if _med_st is not None:
                            _med_phase = _med_st.get('current_phase')
                            # CI-1: durable call_id DIREKT aus dem schon-gehaltenen state lesen
                            # (reiner Guard, kein Re-Lock — kein Deadlock auf den plain Lock).
                            _med_cid = ls._durable_call_id(_med_st.get('call_id'))
                            # IL-2: primary_intent + confidence per-SID VOR dem Trigger
                            _med_st['primary_intent'] = _it
                            _med_st['confidence'] = _med_conf
                            _iid = ls.get_or_open_moment(
                                sid, mode=_med_mode, now=time.monotonic())
                    # TAXO1-07 (Task 3, Decision 2): Sprecher-Bug-Fix ueber die Registry.
                    # cold_call -> berater/local/advisor_paraphrase (Berater-Paraphrase,
                    # NICHT 'kunde'); meeting -> kunde/direct_customer_utterance (Medium-Lane
                    # hat keinen pro-Sprecher-Wert -> speaker=None -> Default kunde).
                    from services.mode_strategy import MODE_REGISTRY
                    _med_strategy = MODE_REGISTRY.get(_med_mode) or MODE_REGISTRY['cold_call']
                    try:
                        _med_attr = _med_strategy.extract_intent(speaker=None, confidence=_med_conf)
                    except Exception:
                        # Edge 2 (Steckplatz/NotImplemented) -> cold_call-Default, kein Live-Crash.
                        _med_attr = MODE_REGISTRY['cold_call'].extract_intent(speaker=None, confidence=_med_conf)
                    _med_conf_out = _med_attr.get('confidence', _med_conf)
                    # FUND 3 (TAXO1-07): anonymisierter Ausloeser-Wortlaut (defensiv, DSGVO).
                    from services.anonymization import anonymize_output as _anon_out_med
                    _med_trig = None
                    try:
                        _med_trig = _anon_out_med(neuer_text, ls.get_anonymisierer(sid))
                        if not _med_trig or _med_trig in ('[ART9_REDACTED]', '[ANON_FEHLER]'):
                            _med_trig = None
                    except Exception:
                        _med_trig = None
                    try:
                        from services.intent_event_writer import emit_intent_event
                        emit_intent_event(
                            session_id=sid, mode=_med_mode, intent_type=_it,
                            phase=_med_phase, source='llm_inferred',
                            inference_basis=_med_attr['inference_basis'],
                            confidence=_med_conf_out,
                            speaker_role=_med_attr['speaker_role'],
                            speaker_id=_med_attr['speaker_id'],
                            user_id=_med_user_id, org_id=_med_org_id,
                            call_id=_med_cid,
                            interaction_id=_iid, triggering_text=_med_trig,
                        )
                    except Exception as _emit_e:
                        print(f"[intent_event] Medium-Lane emit skip (sid={sid}): {type(_emit_e).__name__}")
                else:
                    # Cold-Call-PRIMAER-Schliesser (FUND A): Single-Speaker -> kein
                    # Einwand-Echo = der Berater ANTWORTET. Substanzielle Wendung
                    # (>= SUBSTANTIAL_TURN_MIN_WORDS) schliesst das offene Fenster.
                    from config import SUBSTANTIAL_TURN_MIN_WORDS
                    _substantiell = len((neuer_text or '').split()) >= SUBSTANTIAL_TURN_MIN_WORDS
                    if _med_mode == 'cold_call' and _substantiell:
                        with ls._session_state_lock:
                            ls.close_moment(sid, reason='advisor_answered')

                # ── Phase 08.5: Universal Response Loop ──────────────────────────
                # Classifies utterance via qa_pipeline when kw_fired_for_line != line_id
                # (D-02 guard). Emits qa_slot1 or qa_soft_hint to active session.
                _qa_pipeline_dispatch(neuer_text, line_id, kontext, ls, sio, sid=sid)
                # SID liveness check after _qa_pipeline_dispatch
                with ls._session_state_lock:
                    if sid not in ls._session_state:
                        print(f"[analyse_loop] SID {sid} gone during qa dispatch — silent drop")
                        continue
                latency_e = round(time.monotonic() - t_start, 2)
                print(f"[Claude-1] SID={sid} Ergebnis (Latenz {latency_e}s): {ergebnis}")
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
                    # Phase 08.23.2.B: OUTPUT-PFAD Anonymisierung (D-01, Req-8)
                    # anonymize_output() ersetzt bekannte Namen (Briefing) via Cache-Reverse-Lookup
                    # Finding 4: anonymize_output() gibt keine Sentinel-Werte zurueck — kein Skip-Check noetig.
                    try:
                        from services.anonymization import anonymize_output
                        _anon_cache = ls.get_anonymisierer(sid)
                        _einwand_zitat_anon = anonymize_output(
                            ergebnis.get('einwand_zitat', ''), _anon_cache
                        )
                        _gegenarg_1_anon = anonymize_output(
                            ergebnis.get('gegenargument_1', ''), _anon_cache
                        )
                        _gegenarg_2_anon = anonymize_output(
                            ergebnis.get('gegenargument_2', ''), _anon_cache
                        )
                    except Exception as _anon_err:
                        print(f'[ANON] anonymize_output Fehler (gegenargument_log, sid={sid!r}): {type(_anon_err).__name__}')
                        # Fallback: originale Werte verwenden (fail-open fuer Output-Pfad)
                        _einwand_zitat_anon = ergebnis.get('einwand_zitat', '')
                        _gegenarg_1_anon = ergebnis.get('gegenargument_1', '')
                        _gegenarg_2_anon = ergebnis.get('gegenargument_2', '')
                    with ls.gegenargument_log_lock:
                        # Vorherigen Eintrag mit kb_nachher aktualisieren
                        if ls.gegenargument_log:
                            last = ls.gegenargument_log[-1]
                            if last['kb_nachher'] is None:
                                last['kb_nachher'] = kb_vor_einwand
                                last['kb_delta']   = kb_vor_einwand - last['kb_vorher']
                                last['erfolgreich'] = last['kb_delta'] > 0
                        # Neuen Eintrag anlegen (Freitext-Felder anonymisiert)
                        # TAXO1-Welle 4 (§0.1): die alten parallelen D2-Keys (freier
                        # typ-String + ist_vorwand-Boolean aus dem Haiku-Output) sind
                        # auf intent_type (§1) MIGRIERT — nicht blind geloescht, weil
                        # der gegenargument_log->ga_details->vorwaende_erkannt-Reader
                        # (app_routes:354 + ConversationLog) live davon liest. einwand_typ
                        # = intent_type; ist_vorwand wird aus intent_type=='vorwand'
                        # ABGELEITET (eine Quelle, kein zweiter Haiku-Pfad).
                        ls.gegenargument_log.append({
                            'ts':               ts,
                            'einwand_typ':      _it,                          # §1 intent_type (migriert)
                            'einwand_zitat':    _einwand_zitat_anon,          # anonymisiert
                            'ist_vorwand':      (_it == 'vorwand'),           # abgeleitet aus §1, kein Haiku-Boolean
                            'gegenargument_1':  _gegenarg_1_anon,             # anonymisiert
                            'gegenargument_2':  _gegenarg_2_anon,             # anonymisiert
                            'gewaehlte_option': None,
                            'kb_vorher':        kb_aktuell,
                            'kb_nachher':       None,
                            'kb_delta':         None,
                            'erfolgreich':      None,
                        })
                with ls.state_lock:
                    ls.state['ergebnis']        = ergebnis
                    ls.state['aktiv']           = False
                    ls.state['version']        += 1
                # Phase 08.23.2.TAXO1-03 (§0.1 P4 B-A line_id / P7 kaufbereitschaft): per-SID.
                # War global ls.state['line_id'] (einziger Reader Keyword-Matcher, jetzt per-SID)
                # + ls.state['kaufbereitschaft'] (dict-key ohne Reader, Rider nur WRITE). GELOESCHT.
                with ls._session_state_lock:
                    _sid_li = (ls._session_state.get(sid) or {}).get('state')
                    if _sid_li is not None:
                        _sid_li['line_id'] = line_id
                        _sid_li['kaufbereitschaft'] = kb_aktuell
                # ── Phase 04.8: phase classifier (every 5th cycle) ────────────
                # TAXO1-Welle 4 Addition A (§0.1): phase_cycle_counter per-SID statt
                # global function-attribute. analyse_loop ist EIN Daemon-Thread ueber
                # ALLE SIDs (app.py:2302) -> der alte globale Zaehler wurde von allen
                # parallelen Calls geteilt -> erratische Phasen-Kadenz. Jetzt single-
                # source in _session_state[sid]['state'] (wie _phase_cycle_at_last_change,
                # das schon per-SID ist -> die cycles_since_change-Arithmetik bleibt korrekt).
                with ls._session_state_lock:
                    _pcc_st = (ls._session_state.get(sid) or {}).get('state')
                    if _pcc_st is not None:
                        _phase_cycle_counter = (_pcc_st.get('phase_cycle_counter', 0) or 0) + 1
                        _pcc_st['phase_cycle_counter'] = _phase_cycle_counter
                    else:
                        _phase_cycle_counter = 0
                if _phase_cycle_counter % 5 == 0:
                    try:
                        from services.ki_logik import detect_phase
                        transcript_window = list(sid_state.get('analysiert_bisher', [])[-10:])
                        with ls._session_state_lock:
                            _sid_phase_st = (ls._session_state.get(sid) or {}).get('state', {})
                            cur_phase = _sid_phase_st.get('current_phase', 1) or 1
                            phase_change_count = _sid_phase_st.get('phase_change_count', 0) or 0
                            last_change_cycle = _sid_phase_st.get('_phase_cycle_at_last_change', 0) or 0
                            mode = (ls._session_state.get(sid) or {}).get('mode', 'meeting')
                        elapsed_s = (time.time() - ls.session_start_ts) if hasattr(ls, 'session_start_ts') else 0
                        raw = classify_phase(transcript_window, cur_phase, elapsed_s, mode, sid=sid)
                        if raw:
                            cycles_since_change = _phase_cycle_counter - last_change_cycle
                            new_phase, new_conf = detect_phase(
                                raw_phase=raw['phase'],
                                raw_confidence=raw['confidence'],
                                current_phase=cur_phase,
                                phase_change_count=phase_change_count,
                                cycles_since_change=cycles_since_change,
                            )
                            with ls._session_state_lock:
                                _sid_phase_st2 = (ls._session_state.get(sid) or {}).get('state')
                                if _sid_phase_st2 is not None:
                                    phase_did_change = (new_phase != cur_phase)
                                    if phase_did_change:
                                        _sid_phase_st2['current_phase'] = new_phase
                                        _sid_phase_st2['current_phase_name'] = _PHASE_NAMES.get(new_phase, '')
                                        _sid_phase_st2['phase_changed_at'] = datetime.utcnow().isoformat()
                                        _sid_phase_st2['phase_change_count'] = phase_change_count + 1
                                        _sid_phase_st2['_phase_cycle_at_last_change'] = _phase_cycle_counter
                                        print(f"[phase_classify] {cur_phase}→{new_phase} ({_PHASE_NAMES.get(new_phase,'')}) conf={new_conf:.2f} grund={raw.get('grund','')}")
                                    _sid_phase_st2['phase_confidence'] = new_conf
                                else:
                                    phase_did_change = False
                            # TAXO1-Welle 4 (Task 2 c3): Cold-Call-SEKUNDAER-Schliesser.
                            # phase_did_change ist NICHT der Primaer-Schliesser (zu grob,
                            # Gemini-R2) — nur ein zusaetzliches frueheres Close, wenn der
                            # Phasenwechsel feuert (schliesst nur frueher, verklumpt nie).
                            if phase_did_change and mode == 'cold_call':
                                with ls._session_state_lock:
                                    ls.close_moment(sid, reason='phase_shift')
                            # POLISH-39 + POLISH-42: propagate AI phase-change to phasen_log (for
                            # ConversationLog.phasen_details) and covered_phases (for skript_abdeckung).
                            # Done outside state_lock to avoid nested-lock stalls.
                            if phase_did_change:
                                try:
                                    old_phase_name = _PHASE_NAMES.get(cur_phase, str(cur_phase))
                                    new_phase_name = _PHASE_NAMES.get(new_phase, str(new_phase))
                                    ts = datetime.now().strftime('%H:%M:%S')
                                    seg_count = len(sid_state.get('analysiert_bisher', []))
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
                                        _, _pdata = ls.get_profile_for_sid(sid)
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
                            with ls._session_state_lock:
                                _sid_cc_st = (ls._session_state.get(sid) or {})
                                cc_mode = _sid_cc_st.get('mode', 'meeting')
                                cc_phase = (_sid_cc_st.get('state') or {}).get('current_phase', 1) or 1
                            if cc_mode == 'cold_call':
                                seller_window = list(sid_state.get('analysiert_bisher', []))[-6:]
                                inference = infer_cold_call_context(
                                    seller_window, cc_phase, cc_mode,
                                    haiku_caller=infer_customer_state,
                                    sid=sid,  # TAXO1-03 B-B: per-SID Kosten-Attribution
                                )
                                with ls._session_state_lock:
                                    _sid_cc_target = (ls._session_state.get(sid) or {}).get('state')
                                    if _sid_cc_target is not None:
                                        _sid_cc_target['cold_call_inference'] = inference
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
                    # Phase 08.23.2.TAXO1-03 (§0.1 Putzliste P2/P3/P5): per-SID single-source.
                    # War global ls.state.get(...) (split-brain: phase_classify schrieb per-SID
                    # :1012, dieser Block las den toten Global → cur_phase immer 1). Jetzt aus
                    # _session_state[sid]['state'] (Muster claude:1061). Globaler Read geloescht.
                    with ls._session_state_lock:
                        _sid_p4_st = (ls._session_state.get(sid) or {}).get('state') or {}
                        factors = dict(_sid_p4_st.get('score_factors_seen') or {})
                        cur_phase_p4 = int(_sid_p4_st.get('current_phase', 1) or 1)
                        cold_inf = _sid_p4_st.get('cold_call_inference')
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
                            _, _pdata = ls.get_profile_for_sid(sid)
                            base_buttons = None
                            if _pdata:
                                _eins = _pdata.get('einwaende_detail') or _pdata.get('einwaende') or []
                                base_buttons = [e.get('einwand') or e.get('kategorie') or ''
                                                for e in _eins if isinstance(e, dict)]
                                base_buttons = [b for b in base_buttons if b]
                    except Exception:
                        base_buttons = None
                    # Track last objection type for context-based buttons
                    # Phase 08.23.2.TAXO1-03 (§0.1 P6): last_einwand_typ per-SID single-source.
                    # War global ls.state['last_einwand_typ'] (read+write) — Cross-Session-Leak
                    # bei parallelen Calls. Jetzt _session_state[sid]['state']. Globale rw GELOESCHT.
                    _last_ewb_typ = None
                    if ergebnis.get('einwand') and ergebnis.get('typ'):
                        _last_ewb_typ = ergebnis['typ']
                    elif not ergebnis.get('einwand'):
                        # No new objection — check if there's a recent one in per-SID state
                        with ls._session_state_lock:
                            _le_st = (ls._session_state.get(sid) or {}).get('state') or {}
                            _last_ewb_typ = _le_st.get('last_einwand_typ')
                    if ergebnis.get('einwand') and ergebnis.get('typ'):
                        with ls._session_state_lock:
                            _le_st_w = (ls._session_state.get(sid) or {}).get('state')
                            if _le_st_w is not None:
                                _le_st_w['last_einwand_typ'] = ergebnis['typ']
                    ewb_buttons = dynamic_ewb_buttons(cur_phase_p4, base_buttons,
                                                      last_einwand_typ=_last_ewb_typ)
                    # Phase 08.23.2.TAXO1-03 (§0.1 P5/P7/P8 Rider): noten-nahe Werte NUR
                    # per-SID WRITE-konsistent — KEINE Scoring-Formel geaendert (compute_readiness_score
                    # unveraendert; TAXO2 entscheidet Scoring). score_factors_seen-Read wurde in Task 1
                    # bereits per-SID gemacht — hier der zugehoerige WRITE. Globale dict-Key-Writes
                    # GELOESCHT. (active_hint/ewb_buttons NICHT in §0.1 → bleiben global; ls.kaufbereitschaft
                    # Modul-Mirror bleibt — separater Reader app_routes:148.)
                    with ls._session_state_lock:
                        _sid_p4_w = (ls._session_state.get(sid) or {}).get('state')
                        if _sid_p4_w is not None:
                            _sid_p4_w['score_factors_seen'] = factors
                            _sid_p4_w['readiness_score'] = score_p4
                            _sid_p4_w['readiness_bucket'] = bucket_p4
                            _sid_p4_w['kaufbereitschaft'] = score_p4  # legacy mirror (RESEARCH Q2 R2)
                    with ls.state_lock:
                        ls.state['active_hint'] = active_hint
                        ls.state['ewb_buttons'] = ewb_buttons
                    ls.kaufbereitschaft = score_p4  # module global mirror (separater Pfad, app_routes:148)
                except Exception as e:
                    print(f"[readiness/active_hint] loop error: {e}")
            except Exception as e:
                print(f"[Claude-1] SID={sid} Fehler: {e}")
                with ls.kb_lock:
                    kb_aktuell = ls.kaufbereitschaft
                with ls.state_lock:
                    ls.state['ergebnis']         = {'einwand': False, 'notiz': f'Fehler: {e}'}
                    ls.state['aktiv']            = False
                    ls.state['version']         += 1
                # Phase 08.23.2.TAXO1-03 (§0.1 P4 line_id / P7 kaufbereitschaft): per-SID (Fehler-Pfad).
                with ls._session_state_lock:
                    _sid_li_err = (ls._session_state.get(sid) or {}).get('state')
                    if _sid_li_err is not None:
                        _sid_li_err['line_id'] = line_id
                        _sid_li_err['kaufbereitschaft'] = kb_aktuell


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
                 'antwort': r.antwort, 'kategorie': r.kategorie, 'mode': r.mode}
                for r in _rows
            ]
        finally:
            _db.close()
    except Exception as _e:
        print(f"[QA-INT] _qa_load_faqs skip: {_e}")
    return []


def _qa_pipeline_dispatch(neuer_text, line_id, kontext, ls, sio, sid: str = None):
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
        # Per-SID state reads (D-02 Phase 08.19.4 / WR-03 Phase 08.19.5.1)
        # WR-01/WR-03: read under _session_state_lock; guard against None (concurrent pop_session_state)
        # Phase 08.23.2.TAXO1-03 (§0.1 P1/P4/P11): per-SID single-source.
        # Der einzige Aufrufer (analyse_loop, claude:909) gibt IMMER sid mit. Der alte
        # globale else-Fallback (ls.state.get user_id/active_sid/active_profile_id/
        # kw_fired_for_line/anrede/slot1_busy_until) war strukturell tot UND ein
        # Cross-Session-Leak-Risiko (las eine Fremd-Session). GELOESCHT — ohne sid
        # gibt es keine aktive Session zu bedienen → früher Ausstieg (kein Raten).
        if not sid:
            return
        with ls._session_state_lock:
            _sid_st = ls._session_state.get(sid) or {}
            _sid_st_state = _sid_st.get('state') or {}
        _user_id = _sid_st.get('user_id') or 0
        _active_sid = sid  # sid IS the active_sid
        _active_profile_id = _sid_st.get('active_profile_id')
        _kw_fired_for = _sid_st_state.get('kw_fired_for_line')
        _anrede = _sid_st_state.get('session_anrede') or 'Sie'
        _slot1_busy_until = _sid_st_state.get('slot1_variant_busy_until', 0.0)

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
            # D-05: get_active_profile() deprecated else-Zweig entfernt (Phase 08.19.4 Plan 04)
            _profile_name, _profile_daten = _ls_ref.get_profile_for_sid(sid) if sid else ('', {})
        except Exception:
            _profile_daten = {}

        _tabu_begriffe = _qa_load_tabu(_active_profile_id, _profile_daten)

        _qa_result = classify_utterance(neuer_text, kontext, _user_id, sid=sid)
        _kat = _qa_result.get('kategorie', 'smalltalk_none')
        _conf = _qa_result.get('confidence', 0.0)
        print(f"[QA-INT] classify kategorie={_kat} conf={_conf:.2f} line={line_id}")

        def _emit_soft_hint(reason=''):
            """Phase 08.23.2.PIP-01 (Item a, Anzeige-Trennung): Der Auto-Erkenner darf
            die Lese-Zone (slot 1) NICHT mehr beschreiben. Frueher emittierte dieser Pfad
            den Literal-Hint 'Neuer Einwand \u2014 noch kein Vorschlag' via qa_soft_hint in
            pip-slot-body-1 (Mit-Ursache Bug B: Ueberschreiben des manuellen Vorschlags).
            Im analyse_loop/QA-Pfad liegt KEIN sauberes kurzes Einwand-Label vor \u2014 nur
            der Literal-Hint-String ODER die _kat-Roh-Enum-Kategorie, beide als
            ewb_signal-typ verboten (Cross-AI HIGH #2 + LOW Geister-Button). Daher: KEIN
            Emit (kein Lese-Zonen-Text, kein Geister-Button). Die abstain-/intent_event-
            Logik liegt im Caller (vor dem Aufruf) und bleibt unangetastet (DSGVO/TAXO)."""
            print(f"[QA-INT] soft_hint suppressed (PIP-01 anzeige-trennung) reason={reason}")

        def _emit_abstain_event(intent_type):
            """TAXO1-Welle 4 (K4/H-4): am ECHTEN low-conf-Drop ein intent_event mit
            abstained festhalten (Funnel sichtbar, nicht droppen) — KEIN lauter Cue.
            NUR an den echten Drops (:low_confidence / :no_faq_low_conf), NICHT am
            kw_fired-/Mutex-/no-sid-Skip (die returnen VOR classify -> kein _conf)."""
            try:
                from config import should_abstain
                from services.intent_event_writer import emit_intent_event
                # mode-Quelle per-SID (TAXO1-07: globales _session_modes geloescht).
                _ab_mode = (ls._session_state.get(sid) or {}).get('mode', 'cold_call')
                _ab_iid = None
                _ab_phase = None
                _ab_uid = None
                _ab_oid = None
                _ab_cid = None
                with ls._session_state_lock:
                    _ab_sd = ls._session_state.get(sid) or {}
                    _ab_uid = _ab_sd.get('user_id')
                    _ab_oid = _ab_sd.get('org_id')
                    _ab_st = _ab_sd.get('state')
                    if _ab_st is not None:
                        _ab_phase = _ab_st.get('current_phase')
                        # CI-1: durable call_id direkt aus dem gehaltenen state (reiner Guard).
                        _ab_cid = ls._durable_call_id(_ab_st.get('call_id'))
                        _ab_iid = ls.get_or_open_moment(
                            sid, mode=_ab_mode, now=_time.monotonic())
                # TAXO1-07 (Task 3, Decision 2): Sprecher-Bug-Fix ueber die Registry.
                from services.mode_strategy import MODE_REGISTRY
                _ab_strategy = MODE_REGISTRY.get(_ab_mode) or MODE_REGISTRY['cold_call']
                try:
                    _ab_attr = _ab_strategy.extract_intent(speaker=None, confidence=_conf)
                except Exception:
                    _ab_attr = MODE_REGISTRY['cold_call'].extract_intent(speaker=None, confidence=_conf)
                # FUND 3 (TAXO1-07): anonymisierter Ausloeser-Wortlaut (neuer_text aus dem
                # _qa_pipeline_dispatch-Closure-Scope). Defensiv, DSGVO.
                from services.anonymization import anonymize_output as _anon_out_ab
                _ab_trig = None
                try:
                    _ab_trig = _anon_out_ab(neuer_text, ls.get_anonymisierer(sid))
                    if not _ab_trig or _ab_trig in ('[ART9_REDACTED]', '[ANON_FEHLER]'):
                        _ab_trig = None
                except Exception:
                    _ab_trig = None
                emit_intent_event(
                    session_id=sid, mode=_ab_mode, intent_type=intent_type,
                    phase=_ab_phase, source='llm_inferred',
                    inference_basis=_ab_attr['inference_basis'],
                    confidence=_conf,
                    abstained=should_abstain(_conf),
                    speaker_role=_ab_attr['speaker_role'],
                    speaker_id=_ab_attr['speaker_id'],
                    user_id=_ab_uid, org_id=_ab_oid, interaction_id=_ab_iid,
                    call_id=_ab_cid,
                    triggering_text=_ab_trig,
                )
            except Exception as _ab_e:
                print(f"[QA-INT] abstain emit skip (sid={sid}): {type(_ab_e).__name__}")

        def _emit_qa_slot1(text):
            # Phase 08.23.2.PIP-01 (Item a, Anzeige-Trennung): Der Auto-Erkenner darf die
            # Lese-Zone (slot 1) NICHT mehr beschreiben. Frueher emittierte dieser Pfad
            # qa_slot1 -> FE schrieb pip-slot-body-1 per textContent (DENSELBEN Node den der
            # manual_ewb-Stream via pip_token beschreibt) -> Ueberschreiben des Knopf-
            # Vorschlags im Vorlesen (Bug B, Wurzel). Hier liegt KEIN sauberes kurzes
            # Einwand-Label vor (nur der volle Haiku-Absatz `text` ODER die _kat-Roh-Enum-
            # Kategorie) — beide als ewb_signal-typ verboten (Cross-AI HIGH #1 + LOW
            # Geister-Button). Daher: KEIN Emit. Der slot1_variant_busy_until-SET entfaellt
            # (Lese-Zonen-Lock obsolet — Auto schreibt slot 1 nicht mehr). Die MP4-WRITE-
            # Instrumentierung entfaellt fuer diesen Pfad, weil hier kein Write mehr passiert
            # (sonst wuerde MP4 einen nicht-existenten Auto-Write vortaeuschen). Der Caller-
            # Pfad (generate_qa_response / FAQ) bleibt unveraendert; nur der Lese-Zonen-
            # Schreib-Seiteneffekt ist entfernt.
            print(f"[QA-INT] qa_slot1 suppressed (PIP-01 anzeige-trennung) len={len(text) if text else 0}")

        if _kat == 'einwand_unknown':
            if _conf < CLASSIFIER_CONFIDENCE_THRESHOLD:
                # H-4 ECHTER LOW-CONF-DROP (einwand_unknown): abstain-Event VOR dem
                # Soft-Hint (kein Dead-Code). _conf ist echt (aus classify_utterance).
                _emit_abstain_event('echter_einwand')
                _emit_soft_hint(reason='low_confidence')
            else:
                _antwort = generate_qa_response(
                    neuer_text, 'einwand_unknown', _profile_daten, _anrede,
                    confidence=float(_conf), user_id=_user_id, sid=_active_sid
                )
                if not _antwort:
                    _emit_soft_hint(reason='empty_response')
                elif apply_tabu_filter(_antwort, _tabu_begriffe):
                    _emit_soft_hint(reason='tabu_filtered')
                    print(f"[QA-INT] response tabu-filtered len={len(_antwort)}")
                else:
                    _emit_qa_slot1(_antwort)

        elif _kat == 'frage':
            _faqs_all = _qa_load_faqs(_active_profile_id)
            _faqs = [f for f in _faqs_all if f.get('mode') == 'literal']
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
                    # H-4 ECHTER LOW-CONF-DROP (frage, kein FAQ): abstain-Event VOR
                    # dem Soft-Hint (kein Dead-Code).
                    _emit_abstain_event('info_frage')
                    _emit_soft_hint(reason='no_faq_low_conf')
                else:
                    _antwort = generate_qa_response(
                        neuer_text, 'frage', _profile_daten, _anrede,
                        confidence=float(_conf), user_id=_user_id, sid=_active_sid
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
    while True:
        ls.coaching_trigger.wait(timeout=ANALYSE_INTERVALL)
        ls.coaching_trigger.clear()
        # Phase 08.19.4 D-03: Iterate over all active SIDs (same pattern as analyse_loop)
        with ls._session_state_lock:
            active_sids = list(ls._session_state.keys())
        if not active_sids:
            continue

        for sid in active_sids:
            # Re-check SID still alive
            with ls._session_state_lock:
                sid_state = ls._session_state.get(sid)
            if not sid_state:
                continue
            if sid_state.get('state', {}).get('is_paused', False):
                continue  # per-SID pause — only skip this SID

            # WR-03: read from per-SID coaching buffer (not module-global) to prevent cross-user leak
            with ls._per_sid_coaching_lock:
                _sid_cbuf = ls._per_sid_coaching_buffer.get(sid, [])
                if not _sid_cbuf:
                    continue
                segmente  = list(_sid_cbuf)
                t_start_c = _sid_cbuf[0].get('t_start', time.monotonic())
                ls._per_sid_coaching_buffer[sid] = []  # drain consumed entries

            # BOF-Zaehler per SID (D-02 — aus _session_state[sid])
            with ls._session_state_lock:
                sid_state_ref = ls._session_state.get(sid)
                if sid_state_ref:
                    for s in segmente:
                        if s['speaker'] == 'Berater':
                            if '?' in s['text']:
                                sid_state_ref['_bof_count'] = 0
                            else:
                                sid_state_ref['_bof_count'] = sid_state_ref.get('_bof_count', 0) + 1
                    bof_snapshot = sid_state_ref.get('_bof_count', 0)
                else:
                    bof_snapshot = 0

            kontext = " ".join(sid_state.get('analysiert_bisher', [])[-10:])
            try:
                result    = analysiere_coaching(segmente, kontext, sid=sid)
                # SID liveness check after Claude API call
                with ls._session_state_lock:
                    if sid not in ls._session_state:
                        print(f"[coaching_loop] SID {sid} gone — silent drop")
                        continue
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
                    # Phase 08.23.2.TAXO1-03 (§0.1 P7 Rider): kaufbereitschaft dict-key per-SID.
                    with ls._session_state_lock:
                        _sid_kb_c = (ls._session_state.get(sid) or {}).get('state')
                        if _sid_kb_c is not None:
                            _sid_kb_c['kaufbereitschaft'] = kb_aktuell

                if kategorie == 'frage' and bof_snapshot < 2:
                    tipp      = None
                    kategorie = ''

                # ── Verhaltensbasierte Tipps (deterministisch, kein Claude-Call) ──
                try:
                    stats = ls.get_speech_stats(sid)
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

                print(f"[Claude-2] SID={sid} tipp={tipp!r}  pain={painpoint!r}  Latenz={latency_c}s")

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
                            # Phase 08.23.2.B: OUTPUT-PFAD Anonymisierung (D-01, Req-8)
                            # Duplikat-Check auf Original-Text (korrekt — vor Anonymisierung)
                            # painpoint IS Claude-Paraphrase von STT-Content und kann Namen enthalten
                            # (D-01 OUTPUT-PFAD: anonymize_output() Pflicht, DSGVO-Blocker-Fix)
                            # Finding 4: anonymize_output() gibt keine Sentinel-Werte zurueck — kein Skip-Check noetig.
                            try:
                                from services.anonymization import anonymize_output
                                _anon_cache = ls.get_anonymisierer(sid)
                                _painpoint_anon = anonymize_output(painpoint, _anon_cache)
                            except Exception as _anon_err:
                                print(f'[ANON] anonymize_output Fehler (painpoint, sid={sid!r}): {type(_anon_err).__name__}')
                                _painpoint_anon = painpoint  # Fallback: Original-Text
                            ls.painpoints.append({'ts': ts, 'text': _painpoint_anon})
                    if painpoint:
                        # Phase 08.23.2.B: conversation_log[type=painpoint] ebenfalls anonymisieren
                        # painpoint-Text ist Claude-Paraphrase von STT-Content (OUTPUT-PFAD per D-01)
                        # und kann Briefing-Namen enthalten — anonymize_output() Pflicht (DSGVO)
                        try:
                            from services.anonymization import anonymize_output
                            _anon_cache = ls.get_anonymisierer(sid)
                            _painpoint_log_anon = anonymize_output(painpoint, _anon_cache)
                        except Exception as _anon_err:
                            print(f'[ANON] anonymize_output Fehler (conv_log painpoint, sid={sid!r}): {type(_anon_err).__name__}')
                            _painpoint_log_anon = painpoint  # Fallback: Original-Text
                        with ls.log_lock:
                            ls.conversation_log.append({
                                'ts': ts, 'type': 'painpoint', 'text': _painpoint_log_anon,
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
                # (oben) und der [Claude-2]-Log-Print.
                # Live-Anzeige waehrend des Calls war kontraproduktiv — der Berater kann
                # nicht gleichzeitig lesen und zuhoeren.
            except Exception as e:
                print(f"[Claude-2] SID={sid} Fehler: {e}")
