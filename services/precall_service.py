# ── Phase 04.13: PreCall Intelligence ────────────────────────────────────────
# Brave Search API + Claude Briefing fuer Firmen-Recherche vor dem Call.
# PreCall-Briefing: einmaliger User-Trigger vor dem Anruf — Sonnet korrekt (kein Live-Loop)
# Keine Rohdaten-Speicherung (D-03 DSGVO).

import re
import time
import requests
import config
from config import BRAVE_SEARCH_API_KEY
from services.claude_service import claude_client
from database.db import get_session
from database.models import ProfileOpener

BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"

# ── In-Memory Cache (D-discretion: 5 Min TTL) ───────────────────────────────
_briefing_cache = {}   # firmenname_lower -> (briefing_dict, timestamp)
_CACHE_TTL_S = 300     # 5 Minuten

# ── System Prompt (D-07: kompaktes Format, DSGVO-konform) ────────────────────
PRECALL_SYSTEM_PROMPT = """Du bist ein Vertriebsassistent der kompakte Call-Briefings erstellt.

Du erhaeltst Web-Suchergebnisse zu einer Firma. Erstelle daraus ein Briefing fuer einen Vertriebler.

Format:
## Firmen-Insights (3-5 Bullet-Points)
- [Konkrete, relevante Information]

## Gespraechs-Empfehlungen (2-3 Punkte)
- [Konkreter Tipp fuer den Call]

Regeln:
- Verwende NUR Informationen aus den Suchergebnissen
- Erfinde KEINE Fakten. Wenn wenig Daten vorhanden, sage das ehrlich
- Maximal 250 Woerter gesamt
- Auf Deutsch
- Fokus auf vertriebsrelevante Informationen: Groesse, Branche, aktuelle News, Wachstum, Tech-Stack
- Keine persoenlichen Daten ausser berufliche Rolle des Ansprechpartners
- Wenn ein Vertriebsprofil mitgegeben wird: Verknuepfe die Firmen-Insights mit dem Produkt/Pitch des Beraters. Zeige auf wo das Produkt zum Bedarf der Firma passen koennte
- Deine Antwort darf keine ##-Markdown-Header enthalten — nur Fließtext und einfache Bullet-Listen (-).
"""


def recherche_firma(firmenname, ansprechpartner=None, branche=None, profil_daten=None, user_id=None, profile_id=None, sid: str = None):
    """Web-Recherche + Claude-Briefing fuer eine Firma.
    Returns: (briefing_dict, error_msg) — per existing service tuple pattern.
    """
    try:
        if not firmenname or not firmenname.strip():
            return (None, "Firmenname ist Pflicht")

        firmenname = firmenname.strip()

        # T-04.13-01: Input-Validierung (3-200 Zeichen, Steuerzeichen entfernen)
        firmenname = re.sub(r'[\x00-\x1f\x7f]', '', firmenname)
        if len(firmenname) < 3 or len(firmenname) > 200:
            return (None, "Firmenname muss zwischen 3 und 200 Zeichen lang sein")

        # Abgelaufene Cache-Eintraege entfernen
        now = time.time()
        stale_keys = [k for k, (_, ts) in _briefing_cache.items() if now - ts >= _CACHE_TTL_S]
        for k in stale_keys:
            del _briefing_cache[k]

        # Cache pruefen
        cache_key = firmenname.strip().lower()
        cached = _briefing_cache.get(cache_key)
        if cached and (time.time() - cached[1]) < _CACHE_TTL_S:
            print(f"[PreCall] Cache hit: {firmenname}")
            return (cached[0], None)

        # API-Key pruefen
        if not BRAVE_SEARCH_API_KEY:
            return (None, "BRAVE_SEARCH_API_KEY nicht konfiguriert")

        # 1. Brave Search
        suchergebnisse = _brave_search(firmenname, ansprechpartner, branche)
        if not suchergebnisse:
            return (None, "Keine Suchergebnisse gefunden")

        # 2. Claude Haiku Briefing
        briefing = _generiere_briefing(firmenname, ansprechpartner, branche, suchergebnisse, profil_daten, user_id=user_id, profile_id=profile_id)
        if not briefing:
            return (None, "Briefing-Generierung fehlgeschlagen")

        # Cache speichern
        _briefing_cache[cache_key] = (briefing, time.time())

        # D-09: Briefing per SID in _session_state cachen (Ghost-SID-Guard in set_briefing_for_sid)
        if briefing and briefing.get('text') and sid:
            try:
                from services.live_session import set_briefing_for_sid
                set_briefing_for_sid(sid, briefing['text'])
                print(f"[PreCall] Briefing gecacht fuer SID={sid} ({len(briefing['text'])} chars)")
            except Exception as _sid_e:
                print(f"[PreCall] set_briefing_for_sid failed (non-fatal): {_sid_e}")

        return (briefing, None)

    except Exception as e:
        print(f"[PreCall] recherche_firma Fehler: {e}")
        return (None, f"Recherche fehlgeschlagen: {e}")


def _brave_search(firmenname, ansprechpartner=None, branche=None):
    """Brave Search API call. Returns list of result dicts or None."""
    query = firmenname
    if ansprechpartner:
        query += f" {ansprechpartner}"
    if branche:
        query += f" {branche}"

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
    """Claude Haiku generates compact briefing from search results."""
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
        # Neue Profile via wizard_create() haben 0 ProfileOpener-Eintraege — das ist by design
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
        _system = PRECALL_SYSTEM_PROMPT + '\n\n' + _branchen_hint
    except Exception as _bhe:
        print(f"[PreCall] branchen_hint build failed (non-fatal): {_bhe}")
        _system = PRECALL_SYSTEM_PROMPT

    try:
        _t0 = time.time()
        msg = claude_client.messages.create(
            model=config.MODEL_PRECALL,
            max_tokens=800,
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

        return {
            "text": msg.content[0].text,
            "firmenname": firmenname,
            "ansprechpartner": ansprechpartner,
            "quellen_count": len(suchergebnisse),
        }
    except Exception as e:
        print(f"[PreCall] Claude Briefing Fehler: {e}")
        return None


def ist_verfuegbar():
    """Returns True if Brave Search API key is configured."""
    return bool(BRAVE_SEARCH_API_KEY)
