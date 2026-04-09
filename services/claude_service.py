import json
import time
from datetime import datetime
import anthropic
from config import ANTHROPIC_API_KEY, ANALYSE_INTERVALL, KATEGORIE_LABEL

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


def _get_erfolgsquoten() -> str:
    """Lädt Gegenargument-Erfolgsquoten aus der DB und gibt Lern-Kontext zurück."""
    try:
        from database.db import get_session
        from database.models import ConversationLog
        db = get_session()
        try:
            logs = (db.query(ConversationLog)
                    .filter(ConversationLog.gegenargument_details.isnot(None))
                    .order_by(ConversationLog.created_at.desc())
                    .limit(50).all())
            if len(logs) < 5:
                return ''
            typ_stats = {}
            for log in logs:
                try:
                    details = json.loads(log.gegenargument_details)
                except Exception:
                    continue
                for ga in details:
                    typ = ga.get('einwand_typ', '')
                    if not typ:
                        continue
                    if typ not in typ_stats:
                        typ_stats[typ] = {'gesamt': 0, 'erfolg': 0, 'option_1': 0, 'option_2': 0}
                    typ_stats[typ]['gesamt'] += 1
                    if ga.get('erfolgreich'):
                        typ_stats[typ]['erfolg'] += 1
                    if ga.get('gewaehlte_option') == 1:
                        typ_stats[typ]['option_1'] += 1
                    elif ga.get('gewaehlte_option') == 2:
                        typ_stats[typ]['option_2'] += 1
            if not typ_stats:
                return ''
            result_lines = ['\n--- LERNDATEN AUS ECHTEN GESPRÄCHEN ---',
                            'Basierend auf den letzten Gesprächen:']
            for typ, stats in sorted(typ_stats.items(), key=lambda x: -x[1]['gesamt']):
                if stats['gesamt'] < 3:
                    continue
                quote = round(stats['erfolg'] / stats['gesamt'] * 100)
                pref  = '1' if stats['option_1'] >= stats['option_2'] else '2'
                result_lines.append(
                    f'- {typ}: Erfolgsquote {quote}%, bevorzugte Option: {pref} '
                    f'(aus {stats["gesamt"]} Gesprächen)'
                )
            if len(result_lines) <= 2:
                return ''
            result_lines.append(
                'Priorisiere Gegenargumente die dem bevorzugten Stil und den '
                'erfolgreichen Mustern aus echten Gesprächen entsprechen.'
            )
            return '\n'.join(result_lines)
        finally:
            db.close()
    except Exception as e:
        print(f'[Lernloop] Fehler: {e}')
        return ''


def _build_system_prompt() -> str:
    import services.live_session as ls
    _, pdata = ls.get_active_profile()
    if not pdata:
        return SYSTEM_PROMPT_BASE
    basis      = pdata.get('basis', {})
    zielgruppe = pdata.get('zielgruppe', {})
    schmerzen  = pdata.get('schmerzen', {})
    einwaende  = pdata.get('einwaende', [])
    fragen     = pdata.get('fragen', [])
    nogos      = pdata.get('nogos', [])
    wettbew    = pdata.get('wettbewerber', [])
    techniken  = pdata.get('techniken', {})
    uebergaenge= pdata.get('uebergaenge', [])
    ki         = pdata.get('ki', {})
    lines = [SYSTEM_PROMPT_BASE, '\n--- AKTIVES VERKAUFSPROFIL ---']
    if basis.get('unternehmen'):
        lines.append(f'Unternehmen: {basis["unternehmen"]}')
    if basis.get('produktbeschreibung'):
        lines.append(f'Produkt: {basis["produktbeschreibung"]}')
    if basis.get('preismodell'):
        lines.append(f'Preismodell: {basis["preismodell"]}')
    if basis.get('usps'):
        lines.append(f'Alleinstellungsmerkmale (USPs): {", ".join(basis["usps"])}')
    if basis.get('konsequenz'):
        lines.append(f'Konsequenz wenn Kunde nicht kauft: {basis["konsequenz"]}')
    zg_parts = []
    if zielgruppe.get('alter'): zg_parts.append(f'Alter: {zielgruppe["alter"]}')
    if zielgruppe.get('berufsstatus'): zg_parts.append(f'Beruf: {zielgruppe["berufsstatus"]}')
    if zielgruppe.get('einkommensniveau'): zg_parts.append(f'Einkommen: {zielgruppe["einkommensniveau"]}')
    if zielgruppe.get('lebenssituation'): zg_parts.append(f'Lebenssituation: {zielgruppe["lebenssituation"]}')
    if zielgruppe.get('beruflicher_hintergrund'): zg_parts.append(f'Hintergrund: {", ".join(zielgruppe["beruflicher_hintergrund"])}')
    if zielgruppe.get('vorwissen'): zg_parts.append(f'Vorwissen: {zielgruppe["vorwissen"]}')
    if zielgruppe.get('entscheidungsverhalten'): zg_parts.append(f'Entscheidungsverhalten: {", ".join(zielgruppe["entscheidungsverhalten"])}')
    if zg_parts:
        lines.append(f'\nZielgruppe: {" | ".join(zg_parts)}')
    trigger = schmerzen.get('trigger', {})
    _trigger_map = {
        'verlust':      ('Verlust',        'Formuliere aus dem Verlust-Winkel — was verliert der Kunde wenn er nicht handelt. Gegenfrage beginnt mit "Was verlieren Sie wenn…"'),
        'familie':      ('Familie/Soziales','Betone persönlichen und familiären Nutzen. Gegenfrage beginnt mit "Für wen tun Sie das eigentlich…"'),
        'status':       ('Status',         'Betone Ansehen, Reputation und Wettbewerbsvorsprung. Gegenfrage beginnt mit "Was sagen Ihre Kunden/Kollegen wenn…"'),
        'zahlen':       ('Zahlen/Fakten',  'Führe konkrete Zahlen, ROI und Fakten an. Gegenfrage lädt zu konkreten Zahlen ein.'),
        'dringlichkeit':('Dringlichkeit',  'Betone Opportunitätskosten und Zeitdruck. Gegenfrage beginnt mit "Je länger Sie warten…"'),
        'micro':        ('Micro',          'Mach das Risiko klein — biete einen ersten kleinen Schritt an. Gegenfrage beginnt mit "Was wäre ein erster kleiner Schritt…"'),
    }
    sorted_triggers = sorted(
        [(k, int(trigger.get(k, 0))) for k in _trigger_map if trigger.get(k)],
        key=lambda x: x[1], reverse=True
    )
    active_triggers = [(k, v) for k, v in sorted_triggers if v > 3]
    if active_triggers:
        lines.append('\nGegenargument-Stil (basierend auf Kundenprofil):')
        if len(active_triggers) >= 1:
            k1, v1 = active_triggers[0]
            label1, style1 = _trigger_map[k1]
            lines.append(f'gegenargument_1 → {label1}-Trigger ({v1}/10): {style1}')
        if len(active_triggers) >= 2:
            k2, v2 = active_triggers[1]
            label2, style2 = _trigger_map[k2]
            lines.append(f'gegenargument_2 → {label2}-Trigger ({v2}/10): {style2}')
        elif len(active_triggers) == 1:
            lines.append('gegenargument_2 → alternativer Winkel, sachlich und lösungsorientiert')
    if einwaende:
        lines.append('\nProfilspezifische Einwände und Gegenargumente:')
        for e in einwaende:
            typ      = e.get('kategorie') or e.get('typ', '')
            text     = e.get('einwand', '')
            gegen    = e.get('gegenargument', '')
            technik  = e.get('technik', '')
            intens   = e.get('intensitaet', '')
            varianten= e.get('varianten', [])
            var_str  = ' / '.join(v for v in (varianten if isinstance(varianten, list) else [varianten]) if v)
            line = f'- [{typ}]'
            if text:    line += f' "{text}"'
            if var_str: line += f' (Varianten: {var_str})'
            if gegen:   line += f' → {gegen}'
            if technik: line += f' | Technik: {technik}'
            if intens:  line += f' | Intensität: {intens}'
            lines.append(line)
    if fragen:
        lines.append('\nHäufige Kundenfragen:')
        for f in fragen[:5]:
            if f.get('frage'):
                lines.append(f'- F: "{f["frage"]}" → A: {f.get("antwort","")}')
    if wettbew:
        lines.append('\nWettbewerber:')
        for w in wettbew:
            if w.get('name'):
                lines.append(f'- {w["name"]}: Schwäche: {w.get("schwaeche","")}')
    if nogos:
        lines.append('\nDisqualifikationskriterien (No-Gos):')
        for n in nogos:
            krit = n.get('kriterium') or n.get('krit', '')
            if krit:
                lines.append(f'- {krit}: {n.get("beschreibung","")}')
    verboten = techniken.get('verboten', [])
    if verboten:
        lines.append(f'\nVerbotene Phrasen/Techniken (nie verwenden): {", ".join(verboten)}')
    aktiv = techniken.get('aktiv', [])
    if aktiv:
        lines.append(f'Bevorzugte Verkaufstechniken: {", ".join(aktiv)}')
    if techniken.get('offene_fragen'):
        lines.append(f'Offene Fragen Vorlage: {techniken["offene_fragen"]}')
    if uebergaenge:
        lines.append('\nGesprächsübergänge:')
        for u in uebergaenge:
            if u.get('von') or u.get('nach'):
                lines.append(f'- {u.get("von","")} → {u.get("nach","")}: "{u.get("bruecke","")}"')
    if ki.get('ansprache'):
        lines.append(f'\nKundenansprache: {ki["ansprache"]} (immer einhalten)')
    if ki.get('antwortlaenge'):
        lines.append(f'Antwortlänge: {ki["antwortlaenge"]}')
    if ki.get('sensitivitaet'):
        lines.append(f'Sensitivität: {ki["sensitivitaet"]}')
    if ki.get('ton'):
        lines.append(f'Ton: {ki["ton"]}')
    if ki.get('zusatz'):
        lines.append(f'Zusatz-Anweisung: {ki["zusatz"]}')
    lerndaten = _get_erfolgsquoten()
    if lerndaten:
        lines.append(lerndaten)
    return '\n'.join(lines)


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
    start = raw.find('{')
    end   = raw.rfind('}') + 1
    return json.loads(raw[start:end])


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
            model='claude-haiku-4-5-20251001',
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
            model='claude-haiku-4-5-20251001',
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
    msg = claude_client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=400,
        system=_build_system_prompt(),
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
    except Exception as _e:
        print(f"[CostHook] claude live_haiku skipped: {_e}")
    # ────────────────────────────────────────────────────────────────────
    return _parse_json(msg.content[0].text.strip())


def analysiere_coaching(segmente: list, kontext: str) -> dict:
    gespraech = "\n".join(f"[{s['speaker']}] {s['text']}" for s in segmente)
    user_msg  = f"""Bisheriger Gesprächskontext:
{kontext if kontext else "(Kein vorheriger Kontext)"}

Aktuelles Gesprächssegment:
{gespraech}"""
    # Phase 04.8 P07: migrated Sonnet→Haiku per Haiku-only-live constraint
    msg = claude_client.messages.create(
        model="claude-haiku-4-5-20251001",
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
        print(f"[Claude-1] Analysiere (line {line_id}): {neuer_text[:80]}…")
        with ls.state_lock:
            ls.state['aktiv'] = True
        try:
            ergebnis  = analysiere_mit_claude(neuer_text, kontext)
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
                    model_used='claude-haiku-4-5-20251001',
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
                            if new_phase != cur_phase:
                                ls.state['current_phase'] = new_phase
                                ls.state['current_phase_name'] = _PHASE_NAMES.get(new_phase, '')
                                ls.state['phase_changed_at'] = datetime.utcnow().isoformat()
                                ls.state['phase_change_count'] = phase_change_count + 1
                                ls.state['_phase_cycle_at_last_change'] = _phase_cycle_counter
                                print(f"[phase_classify] {cur_phase}→{new_phase} ({_PHASE_NAMES.get(new_phase,'')}) conf={new_conf:.2f} grund={raw.get('grund','')}")
                            ls.state['phase_confidence'] = new_conf
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

            sio.emit('coaching', {
                'tipp': tipp, 'painpoint': painpoint,
                'kategorie': kategorie, 'ts': ts,
            })
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
                        model_used='claude-haiku-4-5-20251001',
                        context={
                            'hint_category': 'coaching',
                        },
                    )
            except Exception as _e:
                print(f"[FT] coaching_live hook skipped: {_e}")
        except Exception as e:
            print(f"[Claude-2] Fehler: {e}")
