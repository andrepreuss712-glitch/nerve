# ── Phase 04.13: PreCall Intelligence ────────────────────────────────────────
# Brave Search API + Claude Briefing fuer Firmen-Recherche vor dem Call.
# PreCall-Briefing: einmaliger User-Trigger vor dem Anruf — Sonnet korrekt (kein Live-Loop)
# Phase 08.20.2: 3-Schicht-Architektur — strukturierte Felder (Schicht-1), Fließtext (Schicht-2),
#                Empfehlungen (Schicht-3). Anti-Halluzinations-Constraints. JSON-Output.
# Keine Rohdaten-Speicherung (D-03 DSGVO).

import re
import json
import time
import threading
import requests
import config
from config import BRAVE_SEARCH_API_KEY
from services.claude_service import claude_client
from database.db import get_session
from database.models import ProfileOpener

BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"

# ── In-Memory Cache (D-discretion: 5 Min TTL) ───────────────────────────────
_briefing_cache = {}              # cache_key -> (briefing_dict, timestamp)
_cache_lock = threading.Lock()    # guards reads, writes and eviction of _briefing_cache
_CACHE_TTL_S = 300                # 5 Minuten

# ── Pflichtfelder-Konstanten ─────────────────────────────────────────────────
REQUIRED_FIELDS = ['geschaeftsfuehrer', 'branche', 'mitarbeiterzahl', 'hauptprodukt']
NOT_FOUND_FIELD = {"value": "not_found", "source_url": None, "confidence": "not_found"}

# ── Schicht-1+2 System Prompt (D-03, D-04, D-07: Confidence-Algorithmus + Quellen-Hierarchie) ──
PRECALL_FIELDS_SYSTEM_PROMPT = """Du bist ein professioneller Unternehmens-Rechercheur fuer B2B-Vertrieb im DACH-Markt.

AUFGABE: Analysiere die bereitgestellten Web-Suchergebnisse zu einer Firma und gib AUSSCHLIESSLICH ein valides JSON-Objekt zurueck — kein Markdown, kein erklaerende Text, keine Code-Fences.

Das JSON-Objekt hat exakt zwei Top-Level-Keys: "fields" und "text".

═══════════════════════════════════════════════════════════════
SCHEMA "fields"
═══════════════════════════════════════════════════════════════

"fields" enthaelt immer GENAU diese 4 Pflichtfelder:
  - geschaeftsfuehrer
  - branche
  - mitarbeiterzahl
  - hauptprodukt

Jedes Feld ist ein Objekt mit exakt 3 Keys:
  {
    "value": "<Wert als String>",
    "source_url": "<URL der Quelle als String oder null>",
    "confidence": "high" | "medium" | "not_found"
  }

Optionale Felder (NUR einschliessen wenn confidence != "not_found"):
  - standorte
  - gruendungsjahr
  - usp_positionierung
  - aktuelle_news

Wenn ein optionales Feld nicht mit ausreichender Sicherheit bestimmt werden kann:
NICHT in "fields" aufnehmen. Niemals mit value="not_found" einfuegen.

═══════════════════════════════════════════════════════════════
CONFIDENCE-REGELN (D-03, D-04)
═══════════════════════════════════════════════════════════════

"high" — Wert ist bestaetigt wenn:
  - ≥2 unabhaengige Quellen denselben Wert nennen, ODER
  - genau 1 Primaerquelle (siehe Quellenranking unten) den Wert nennt

"medium" — Wert ist wahrscheinlich wenn:
  - genau 1 Sekundaerquelle den Wert nennt

"not_found" — Kein Wert ableitbar wenn:
  - Kein Suchergebnis enthält belastbare Information
  - NIEMALS Daten erfinden — lieber not_found setzen
  - Bei Widerspruch (≥2 Quellen mit unterschiedlichen Werten fuer dasselbe Feld) → not_found

Bei "not_found" MUSS gelten: value = "not_found", source_url = null

Aktualitaetsschwelle: Quellen aelter als 36 Monate NICHT fuer faktische Aussagen verwenden.
Ausnahme: gruendungsjahr (aendert sich nicht).

═══════════════════════════════════════════════════════════════
QUELLENRANKING (D-07)
═══════════════════════════════════════════════════════════════

PRIMAER — 1 Quelle reicht fuer confidence: "high":
  - Impressum der offiziellen Unternehmens-Website
  - Handelsregister (handelsregister.de)
  - Bundesanzeiger
  - Offizielle Unternehmens-Website (Über-uns, Produkt-Seiten)

SEKUNDAER — 1 Quelle ergibt confidence: "medium":
  - LinkedIn (Unternehmens-Profil)
  - Crunchbase
  - North Data (northdata.de)
  - Wikipedia (Sekundaerquelle — kann veraltet sein)
  - Branchenverzeichnisse (Wer-liefert-was, Kompass, Hoppenstedt)
  - Wirtschaftsmedien (Handelsblatt, WirtschaftsWoche, manager magazin, Gruenderszene)
  - Offizielle Pressemitteilungen

AUSGESCHLOSSEN — zaehlen NICHT fuer Confidence-Berechnung:
  - Forum-Posts (Reddit, gutefrage, Quora)
  - AI-generierte Inhalte
  - Anonyme Bewertungsplattformen (Kununu, Glassdoor, Trustpilot)
  - Inhalte ohne klare Primaerquelle oder ohne Datum

═══════════════════════════════════════════════════════════════
SCHICHT-2 "text" — Anti-Halluzinations-Regeln (REQ-5)
═══════════════════════════════════════════════════════════════

"text" ist ein Fließtext-Briefing auf Deutsch (max. 250 Woerter, vertriebsrelevant).

Regeln:
  - Jede Faktenaussage MUSS aus einem confidence="high" oder confidence="medium" Feld ableitbar sein
  - Annahmen und unverifiable Aussagen MUESSEN als "(Annahme)" oder "(nicht verifiziert)" gekennzeichnet sein
  - NIEMALS Zahlen (Umsatz, Mitarbeiterzahl) ohne bestaettigtes Schicht-1-Feld erraten
  - Quellen aelter als 36 Monate: nicht fuer faktische Aussagen verwenden
  - Keine persoenlichen Daten ausser berufliche Rolle
  - Fokus: vertriebsrelevante Informationen (Groesse, Branche, Wachstum, aktuelle News, Marktposition)

═══════════════════════════════════════════════════════════════
POSITIVES BEISPIEL (Few-Shot)
═══════════════════════════════════════════════════════════════

{
  "fields": {
    "geschaeftsfuehrer": {
      "value": "Christian Klein",
      "source_url": "https://www.sap.com/about/company/leadership.html",
      "confidence": "high"
    },
    "branche": {
      "value": "Enterprise-Software / ERP",
      "source_url": "https://www.sap.com/about.html",
      "confidence": "high"
    },
    "mitarbeiterzahl": {
      "value": "ca. 105.000",
      "source_url": "https://northdata.de/SAP+SE",
      "confidence": "medium"
    },
    "hauptprodukt": {
      "value": "not_found",
      "source_url": null,
      "confidence": "not_found"
    }
  },
  "text": "SAP SE ist Weltmarktfuehrer fuer ERP-Software mit Sitz in Walldorf. Christian Klein fuehrt das Unternehmen seit 2020. Mit ca. 105.000 Mitarbeitern (nicht verifiziert — Angabe von North Data) gehoert SAP zu den groessten Softwareunternehmen Europas. Hauptprodukt konnte aus den vorliegenden Suchergebnissen nicht eindeutig bestimmt werden."
}
"""


def recherche_firma(firmenname, ansprechpartner=None, branche=None, profil_daten=None, user_id=None, profile_id=None, sid: str = None):
    """Web-Recherche + Claude-Briefing fuer eine Firma (3-Schicht-Architektur).
    Returns: (briefing_dict, error_msg) — per existing service tuple pattern.
    briefing_dict keys: fields, text, empfehlungen, firmenname, ansprechpartner, quellen_count
    """
    try:
        if not firmenname or not firmenname.strip():
            return (None, "Firmenname ist Pflicht")

        firmenname = firmenname.strip()

        # T-04.13-01: Input-Validierung (3-200 Zeichen, Steuerzeichen entfernen)
        firmenname = re.sub(r'[\x00-\x1f\x7f]', '', firmenname)
        if len(firmenname) < 3 or len(firmenname) > 200:
            return (None, "Firmenname muss zwischen 3 und 200 Zeichen lang sein")

        # Abgelaufene Cache-Eintraege entfernen + Cache pruefen (thread-safe)
        cache_key = f"{firmenname.strip().lower()}_{profile_id}"
        with _cache_lock:
            now = time.time()
            stale_keys = [k for k, (_, ts) in _briefing_cache.items() if now - ts >= _CACHE_TTL_S]
            for k in stale_keys:
                del _briefing_cache[k]
            cached = _briefing_cache.get(cache_key)

        if cached and (time.time() - cached[1]) < _CACHE_TTL_S:
            print(f"[PreCall] Cache hit: {firmenname}")
            # WR-04: empfehlungen are session-specific (Section 8 of build_profile_context
            # depends on the live session's sid). On a cache hit we must regenerate Schicht-3
            # for the current sid so the caller does not receive a stale session's empfehlungen.
            cached_briefing = dict(cached[0])  # shallow copy — do not mutate cached original
            if sid:
                try:
                    from services.live_session import set_briefing_for_sid
                    _sid_text = cached_briefing.get('text', '')
                    set_briefing_for_sid(sid, _sid_text)
                except Exception:
                    pass
            cached_briefing['empfehlungen'] = _generiere_empfehlungen(
                sid, firmenname, cached_briefing.get('fields', {}), user_id=user_id
            )
            return (cached_briefing, None)

        # API-Key pruefen
        if not BRAVE_SEARCH_API_KEY:
            return (None, "BRAVE_SEARCH_API_KEY nicht konfiguriert")

        # 1. Brave Search
        suchergebnisse = _brave_search(firmenname, ansprechpartner, branche)
        if not suchergebnisse:
            return (None, "Keine Suchergebnisse gefunden")

        # 2. Schicht-1+2: Claude generiert strukturiertes JSON (fields + text)
        briefing = _generiere_briefing(firmenname, ansprechpartner, branche, suchergebnisse, profil_daten, user_id=user_id, profile_id=profile_id)
        if not briefing:
            return (None, "Briefing-Generierung fehlgeschlagen")

        # Build Schicht-1-Summary (kompakt, fuer EWB-Context — NOT empfehlungen)
        _gf = briefing['fields'].get('geschaeftsfuehrer', {}).get('value', 'nicht gefunden')
        _br = briefing['fields'].get('branche', {}).get('value', 'nicht gefunden')
        _ma = briefing['fields'].get('mitarbeiterzahl', {}).get('value', 'nicht gefunden')
        _pr = briefing['fields'].get('hauptprodukt', {}).get('value', 'nicht gefunden')
        schicht1_summary = f"Geschäftsführer: {_gf} | Branche: {_br} | MA: {_ma} | Produkt: {_pr}"

        # D-09: Cache Schicht-1-Summary + Schicht-2-Text in _per_sid_briefing (NOT empfehlungen)
        if sid:
            try:
                from services.live_session import set_briefing_for_sid
                _sid_text = schicht1_summary + "\n\n" + briefing.get('text', '')
                set_briefing_for_sid(sid, _sid_text)
                print(f"[PreCall] Briefing gecacht fuer SID={sid} ({len(_sid_text)} chars)")
            except Exception as _sid_e:
                print(f"[PreCall] set_briefing_for_sid failed (non-fatal): {_sid_e}")

        # 3. Schicht-3: separater Call NACH set_briefing_for_sid (build_profile_context braucht Section 8)
        empfehlungen = _generiere_empfehlungen(sid, firmenname, briefing['fields'], user_id=user_id)
        briefing['empfehlungen'] = empfehlungen

        # Cache speichern NACH empfehlungen-Setzen — Cache-Hit liefert vollstaendiges 6-Key-Dict
        with _cache_lock:
            _briefing_cache[cache_key] = (briefing, time.time())

        return (briefing, None)

    except Exception as e:
        print(f"[PreCall] recherche_firma Fehler: {e}")
        return (None, f"Recherche fehlgeschlagen: {e}")


def _brave_search(firmenname, ansprechpartner=None, branche=None):
    """Brave Search API call. Returns list of result dicts or None.
    D-01: Query geschaerft mit Primaerquellen-Termen fuer bessere JSON-Feld-Trefferquote.
    """
    # D-01: Schärfung fuer Primaerquellen (Impressum, Geschaeftsfuehrer, Mitarbeiterzahl)
    query = f"{firmenname} Impressum Geschäftsführer Mitarbeiterzahl {branche or ''}"
    if ansprechpartner:
        query += f" {ansprechpartner}"

    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": BRAVE_SEARCH_API_KEY,
    }
    params = {"q": query, "count": 10, "search_lang": "de", "country": "DE"}

    try:
        resp = requests.get(BRAVE_SEARCH_URL, headers=headers, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        results = []
        for r in (data.get("web", {}).get("results", []))[:10]:
            results.append({
                "title": r.get("title", ""),
                "description": r.get("description", ""),
                "url": r.get("url", ""),
            })
        return results if results else None
    except Exception as e:
        print(f"[PreCall] Brave Search Fehler: {e}")
        return None


def _generiere_briefing(firmenname, ansprechpartner, branche, suchergebnisse, profil_daten=None, user_id=None, profile_id=None):
    """Schicht-1+2: Returns {fields, text, firmenname, ansprechpartner, quellen_count}.

    Claude gibt ein valides JSON-Objekt zurueck mit:
    - fields: dict mit 4 Pflichtfeldern (geschaeftsfuehrer, branche, mitarbeiterzahl, hauptprodukt)
              + optionale Felder (nur wenn confidence != not_found)
    - text: Schicht-2-Fließtext (max 250 Woerter, vertriebsrelevant, anti-halluziniert)

    Bei JSON-Parse-Fehler: graceful degradation — alle 4 Pflichtfelder auf not_found.
    """
    search_text = "\n\n".join([
        f"**{r['title']}**\n{r['description']}\nURL: {r['url']}"
        for r in suchergebnisse
    ])

    user_msg = f"Firma: {firmenname}"
    if ansprechpartner:
        user_msg += f"\nAnsprechpartner: {ansprechpartner}"
    if branche:
        user_msg += f"\nBranche: {branche}"
    user_msg += f"\n\nSuchergebnisse:\n{search_text}"

    if profil_daten and isinstance(profil_daten, dict):
        basis = profil_daten.get('basis', {})
        zg = profil_daten.get('zielgruppe', {})
        profile_parts = []
        if basis.get('produktbeschreibung'):
            profile_parts.append(f"Unser Produkt: {basis['produktbeschreibung']}")
        if basis.get('usps'):
            profile_parts.append(f"USPs: {', '.join(basis['usps'])}")
        if zg.get('berufsstatus'):
            profile_parts.append(f"Zielgruppe: {zg['berufsstatus']}")
        # Phase 08.19: opener/pitch aus ProfileOpener-Tabelle lesen (D-01)
        # profil_daten.get('opener') ist nach Migration leer — canonical: profile_opener-Tabelle
        # Graceful degradation: kein profile_id oder keine Eintraege = kein Opener-Block (kein Crash)
        if profile_id:
            try:
                _db = get_session()
                try:
                    _opener_rows = _db.query(ProfileOpener).filter_by(
                        profile_id=profile_id
                    ).order_by(ProfileOpener.sortierung, ProfileOpener.id).all()
                    for _op_row in _opener_rows:
                        if _op_row.inhalt:
                            _label = _op_row.name or 'Opener'
                            profile_parts.append(f"{_label}: {_op_row.inhalt}")
                finally:
                    _db.close()
            except Exception as _e:
                print(f"[PreCall] ProfileOpener-Query fuer Profil {profile_id} fehlgeschlagen: {_e}")
        # Wenn profile_id=None: kein Opener im Briefing (graceful degradation, kein Crash)
        if profile_parts:
            user_msg += f"\n\nVertriebsprofil des Beraters:\n" + "\n".join(profile_parts)

    try:
        from services.branchen_data import build_branchen_hint as _build_branchen_hint
        _branchen_hint = _build_branchen_hint(branche or '')
        _system = PRECALL_FIELDS_SYSTEM_PROMPT + '\n\n' + _branchen_hint
    except Exception as _bhe:
        print(f"[PreCall] branchen_hint build failed (non-fatal): {_bhe}")
        _system = PRECALL_FIELDS_SYSTEM_PROMPT

    try:
        _t0 = time.time()
        msg = claude_client.messages.create(
            model=config.MODEL_PRECALL,
            max_tokens=1200,
            system=_system,
            messages=[{"role": "user", "content": user_msg}],
        )
        _latency_ms = int((time.time() - _t0) * 1000)

        # Cost tracking
        try:
            from services.cost_tracker import log_api_cost
            u = getattr(msg, 'usage', None)
            if u is not None:
                in_tok = getattr(u, 'input_tokens', 0) or 0
                out_tok = getattr(u, 'output_tokens', 0) or 0
                _cost_model = 'sonnet-4-5' if 'sonnet' in config.MODEL_PRECALL else 'haiku-4-5'
                log_api_cost('anthropic', _cost_model, user_id=user_id,
                             units=in_tok/1000.0, unit_type='per_1k_input_tokens',
                             context_tag='precall', latency_ms=_latency_ms,
                             call_site='precall')
                log_api_cost('anthropic', _cost_model, user_id=user_id,
                             units=out_tok/1000.0, unit_type='per_1k_output_tokens',
                             context_tag='precall', call_site='precall')
        except Exception:
            pass

        # ── JSON-Parse mit graceful degradation ─────────────────────────────
        raw = msg.content[0].text.strip()
        # Strip markdown code fences if present: ```json ... ```
        if raw.startswith('```'):
            raw = re.sub(r'^```[a-z]*\n?', '', raw).rstrip('`').strip()

        try:
            parsed = json.loads(raw)
            fields = parsed.get('fields', {})
            text = parsed.get('text', '')
        except (json.JSONDecodeError, Exception) as _je:
            print(f"[PreCall] JSON parse error (graceful degradation): {_je}")
            fields = {}
            text = ''

        # Ensure all 4 Pflichtfelder present
        for key in REQUIRED_FIELDS:
            if key not in fields:
                fields[key] = NOT_FOUND_FIELD.copy()

        # Validate field structure — jedes Feld muss exakt value/source_url/confidence haben
        for key, val in list(fields.items()):
            if not isinstance(val, dict):
                fields[key] = NOT_FOUND_FIELD.copy()
                continue
            if not all(k in val for k in ('value', 'source_url', 'confidence')):
                fields[key] = NOT_FOUND_FIELD.copy()
                continue
            if val.get('confidence') not in ('high', 'medium', 'not_found'):
                fields[key] = NOT_FOUND_FIELD.copy()
                continue
            # Enforce: not_found confidence muss value='not_found' und source_url=None haben
            if val['confidence'] == 'not_found':
                fields[key] = NOT_FOUND_FIELD.copy()
                continue
            # Strip extra keys — exakt {value, source_url, confidence} erzwingen (T-08.20.2-02)
            fields[key] = {k: v for k, v in fields[key].items() if k in ('value', 'source_url', 'confidence')}

        # Remove optional fields that are not_found (REQ-3: optionale Felder NUR bei confidence != not_found)
        optional_keys = ['standorte', 'gruendungsjahr', 'usp_positionierung', 'aktuelle_news']
        for k in optional_keys:
            if k in fields and fields[k].get('confidence') == 'not_found':
                del fields[k]

        return {
            "fields": fields,
            "text": text,
            "firmenname": firmenname,
            "ansprechpartner": ansprechpartner,
            "quellen_count": len(suchergebnisse),
        }

    except Exception as e:
        print(f"[PreCall] Claude Briefing Fehler: {e}")
        return None


def _generiere_empfehlungen(sid, firmenname, fields, user_id=None):
    """Schicht-3: Separater Claude-Call fuer Gesprächs-Empfehlungen.

    Nutzt build_profile_context() (9-Sektionen inkl. Section 8 = frisch gecachtes PreCall-Briefing)
    als System-Kontext. Verwendet nur Felder mit confidence in ('high', 'medium') als Factbase.

    Must be called AFTER set_briefing_for_sid() with a non-None sid for Section 8 to be
    populated in build_profile_context(). When sid=None, Section 8 will be empty and
    empfehlungen will be produced without PreCall context (weaker but non-fatal).
    Returns empfehlungen string or '' on error.
    """
    if sid is None:
        print(f"[PreCall] Empfehlungen: sid=None, Section 8 nicht im Kontext (non-fatal)")

    try:
        from services.prompt_pipeline import build_profile_context
        profil_kontext = build_profile_context(user_id=user_id, sid=sid)
    except Exception as _e:
        print(f"[PreCall] build_profile_context failed (non-fatal): {_e}")
        profil_kontext = ''

    # Factbase aus verifizierten Feldern (nur high/medium)
    verified_facts = []
    for key, val in fields.items():
        if isinstance(val, dict) and val.get('confidence') in ('high', 'medium'):
            label = {
                'geschaeftsfuehrer': 'Geschäftsführer',
                'branche': 'Branche',
                'mitarbeiterzahl': 'Mitarbeiterzahl',
                'hauptprodukt': 'Hauptprodukt',
                'standorte': 'Standorte',
                'gruendungsjahr': 'Gründungsjahr',
                'usp_positionierung': 'USP/Positionierung',
                'aktuelle_news': 'Aktuelle News',
            }.get(key, key)
            verified_facts.append(f"- {label}: {val['value']}")

    if not verified_facts:
        print(f"[PreCall] Empfehlungen: keine verifizierten Felder fuer {firmenname}")
        return ''

    empf_system = (
        "Du bist ein Vertriebscoach. Erstelle 3-5 konkrete Gesprächs-Empfehlungen "
        "für einen B2B-Vertriebler basierend auf den verifizierten Firmendaten und dem Vertriebsprofil. "
        "Nur verifizierte Fakten verwenden. Keine Annahmen. Auf Deutsch. "
        "Format: Bullet-Liste mit je einem konkreten Tipp. Maximal 200 Wörter."
    )
    if profil_kontext:
        empf_system += "\n\nVertriebsprofil:\n" + profil_kontext

    empf_user = f"Firma: {firmenname}\n\nVerifizierte Firmendaten:\n" + "\n".join(verified_facts)

    try:
        _t0 = time.time()
        msg = claude_client.messages.create(
            model=config.MODEL_PRECALL,
            max_tokens=1500,
            system=empf_system,
            messages=[{"role": "user", "content": empf_user}],
        )
        _latency_ms = int((time.time() - _t0) * 1000)

        # Cost tracking (analog zu _generiere_briefing)
        try:
            from services.cost_tracker import log_api_cost
            u = getattr(msg, 'usage', None)
            if u is not None:
                in_tok = getattr(u, 'input_tokens', 0) or 0
                out_tok = getattr(u, 'output_tokens', 0) or 0
                _cost_model = 'sonnet-4-5' if 'sonnet' in config.MODEL_PRECALL else 'haiku-4-5'
                log_api_cost('anthropic', _cost_model, user_id=user_id,
                             units=in_tok/1000.0, unit_type='per_1k_input_tokens',
                             context_tag='precall_empf', latency_ms=_latency_ms,
                             call_site='precall_empf')
                log_api_cost('anthropic', _cost_model, user_id=user_id,
                             units=out_tok/1000.0, unit_type='per_1k_output_tokens',
                             context_tag='precall_empf', call_site='precall_empf')
        except Exception:
            pass

        return msg.content[0].text.strip()
    except Exception as e:
        print(f"[PreCall] Empfehlungen-Call Fehler (non-fatal): {e}")
        return ''


def ist_verfuegbar():
    """Returns True if Brave Search API key is configured."""
    return bool(BRAVE_SEARCH_API_KEY)


# ── Phase 08.20.3: KI-Skript-Personalisierung ─────────────────────────────

def generate_personalized_skript(briefing_dict, opener_inhalt, profil_daten,
                                  user_id=None):
    """Personalisiert einen Opener/Skript-Text mit Lead-Daten aus dem Briefing.

    Returns (personalisierter_text: str, error_msg: str | None).
    Tupel-Return: identisch mit recherche_firma() Muster.

    Args:
        briefing_dict: dict mit 'firmenname', 'text', 'empfehlungen'
        opener_inhalt: str — Original-Opener-Text
        profil_daten: dict — Profil-Daten inkl. 'ki'-Key fuer Stil/Ton
        user_id: int | None — fuer Cost-Tracking
    """
    try:
        firmenname = (briefing_dict or {}).get('firmenname', 'Unbekanntes Unternehmen')
        briefing_text = (briefing_dict or {}).get('text', '')
        empfehlungen = (briefing_dict or {}).get('empfehlungen', [])
        ki_ton = ((profil_daten or {}).get('ki') or {}).get('ton', '')

        # Empfehlungen als kompakter Text
        emp_text = ''
        if empfehlungen and isinstance(empfehlungen, list):
            emp_text = '\n'.join(
                '- ' + (e.get('text') or e if isinstance(e, str) else str(e))
                for e in empfehlungen[:5]
            )

        _system = (
            'Du bist ein erfahrener B2B-Vertriebscoach. '
            'Deine Aufgabe: Passe einen Opener/Skript-Text an einen spezifischen Lead an. '
            'Behalte die Länge und Struktur des Originals bei. '
            'Integriere die Lead-spezifischen Informationen natürlich. '
            'Antworte NUR mit dem angepassten Text — keine Erklärungen, keine Überschriften.'
        )
        if ki_ton:
            _system += f'\nTon: {ki_ton}'

        user_msg = f"""Lead-Informationen:
Unternehmen: {firmenname}

Briefing:
{briefing_text}
"""
        if emp_text:
            user_msg += f"\nHandlungsempfehlungen:\n{emp_text}\n"

        user_msg += f"\nOriginal-Opener/Skript:\n{opener_inhalt}\n\nBitte passe diesen Text an den Lead an:"

        _t0 = time.time()
        msg = claude_client.messages.create(
            model=config.MODEL_PRECALL,
            max_tokens=8000,
            system=_system,
            messages=[{"role": "user", "content": user_msg}],
        )
        _latency_ms = int((time.time() - _t0) * 1000)

        personalisierter_text = ''
        if msg.content and len(msg.content) > 0:
            personalisierter_text = getattr(msg.content[0], 'text', '') or ''

        # Cost tracking — identisch mit _generiere_briefing() Pattern
        try:
            from services.cost_tracker import log_api_cost
            u = getattr(msg, 'usage', None)
            if u is not None:
                in_tok = getattr(u, 'input_tokens', 0) or 0
                out_tok = getattr(u, 'output_tokens', 0) or 0
                _cost_model = 'sonnet-4-5' if 'sonnet' in config.MODEL_PRECALL else 'haiku-4-5'
                log_api_cost('anthropic', _cost_model, user_id=user_id,
                             units=in_tok / 1000.0, unit_type='per_1k_input_tokens',
                             context_tag='personalize_skript', latency_ms=_latency_ms,
                             call_site='personalize_skript')
                log_api_cost('anthropic', _cost_model, user_id=user_id,
                             units=out_tok / 1000.0, unit_type='per_1k_output_tokens',
                             context_tag='personalize_skript', call_site='personalize_skript')
        except Exception:
            pass

        return (personalisierter_text, None)

    except Exception as e:
        print(f"[PreCall] Personalisierung Fehler: {e}")
        return (None, f"Fehler: {e}")
