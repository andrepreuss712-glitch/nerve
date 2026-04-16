# ── Phase 04.13: PreCall Intelligence ────────────────────────────────────────
# Brave Search API + Claude Haiku Briefing fuer Firmen-Recherche vor dem Call.
# Kein Sonnet (CLAUDE.md Constraint: nur Haiku fuer alles Live).
# Keine Rohdaten-Speicherung (D-03 DSGVO).

import re
import time
import requests
import anthropic
from config import ANTHROPIC_API_KEY, BRAVE_SEARCH_API_KEY

claude_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

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
"""


def recherche_firma(firmenname, ansprechpartner=None, branche=None, profil_daten=None):
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
        briefing = _generiere_briefing(firmenname, ansprechpartner, branche, suchergebnisse, profil_daten)
        if not briefing:
            return (None, "Briefing-Generierung fehlgeschlagen")

        # Cache speichern
        _briefing_cache[cache_key] = (briefing, time.time())

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


def _generiere_briefing(firmenname, ansprechpartner, branche, suchergebnisse, profil_daten=None):
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
        opener = profil_daten.get('opener', '')
        pitch = profil_daten.get('pitch', '')
        if opener:
            profile_parts.append(f"Opener: {opener}")
        if pitch:
            profile_parts.append(f"Pitch: {pitch}")
        if profile_parts:
            user_msg += f"\n\nVertriebsprofil des Beraters:\n" + "\n".join(profile_parts)

    try:
        msg = claude_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=800,
            system=PRECALL_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )

        # Cost tracking (Phase 04.7.2 pattern)
        try:
            from services.cost_tracker import log_api_cost
            u = getattr(msg, 'usage', None)
            if u is not None:
                in_tok = getattr(u, 'input_tokens', 0) or 0
                out_tok = getattr(u, 'output_tokens', 0) or 0
                log_api_cost('anthropic', 'haiku-4-5', user_id=None,
                             units=in_tok/1000.0, unit_type='per_1k_input_tokens',
                             context_tag='precall')
                log_api_cost('anthropic', 'haiku-4-5', user_id=None,
                             units=out_tok/1000.0, unit_type='per_1k_output_tokens',
                             context_tag='precall')
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
