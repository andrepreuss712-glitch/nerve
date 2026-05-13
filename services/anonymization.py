"""
DSGVO-Anonymisierungs-Foundation-Modul fuer NERVE.
Pipeline-Reihenfolge: Art-9-Filter (Schritt 0) -> Regex (Schritt 1) -> spaCy NER (Schritt 2)
Phase: 08.23.2.B
"""
import os
import re
import time
import threading
from typing import Optional, Tuple, Dict, List

# ── Modul-Level-Import: ART9_KEYWORDS (PFLICHT hier — NICHT in _check_art9()) ──────────────
# Per-Call-Import in _check_art9() waere Anti-Pattern (Cross-AI-Review Finding 1).
from services.art9_keywords import ART9_KEYWORDS

# ── Modul-Level-Zustand ──────────────────────────────────────────────────────

is_pipeline_healthy: bool = True   # D-08 Kat. A: False wenn spaCy nicht ladbar
_error_timestamps: list = []       # Monotonic-Timestamps fuer Rolling-Error-Rate
_error_lock = threading.Lock()

ROLLING_ERROR_THRESHOLD = int(os.environ.get('ANON_ERROR_THRESHOLD', '5'))
ROLLING_ERROR_WINDOW_S  = int(os.environ.get('ANON_ERROR_WINDOW_S', '600'))  # 10 min

# ── spaCy Lazy-Load (Thread-safe Double-Checked Locking) ────────────────────

_nlp = None
_nlp_lock = threading.Lock()


def _get_nlp():
    """Thread-safe lazy load von de_core_news_lg. Einmal pro Prozess geladen."""
    global _nlp, is_pipeline_healthy
    if _nlp is None:
        with _nlp_lock:
            if _nlp is None:
                try:
                    import spacy
                    _nlp = spacy.load('de_core_news_lg')
                    print('[ANON] de_core_news_lg geladen')
                except Exception as e:
                    print(f'[ANON] KRITISCH: de_core_news_lg nicht ladbar: {type(e).__name__}')
                    is_pipeline_healthy = False
    return _nlp


# ── Custom Exception ─────────────────────────────────────────────────────────

class AnonymizationPipelineUnavailable(Exception):
    """Raised wenn is_pipeline_healthy=False (spaCy-Lade-Fehler, D-08 Kat. A)."""
    pass


# ── Regex-PII-Patterns (Schritt 1) ───────────────────────────────────────────

_RE_IBAN = re.compile(
    r'\bDE\d{2}[\s]?[A-Z0-9]{4}[\s]?[A-Z0-9]{4}[\s]?[A-Z0-9]{4}[\s]?[A-Z0-9]{4}[\s]?[A-Z0-9]{2}\b',
    re.IGNORECASE
)
_RE_EMAIL = re.compile(r'\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b')
_RE_USTID = re.compile(r'\bDE\s*\d{9}\b', re.IGNORECASE)
_RE_STEUERNR = re.compile(r'\b\d{2,3}[\s/]\d{3}[\s/]\d{4,5}\b')
_RE_DATUM_KONTEXT = re.compile(
    r'(?:geboren|geb\.|geburtstag|geburtsdatum)\s*:?\s*(\d{1,2}[./]\d{1,2}[./]\d{2,4})',
    re.IGNORECASE
)
_RE_KREDITKARTE = re.compile(r'(?<!\d)(?:\d[\s\-]?){13,19}(?!\d)')


# ── AnrufAnonymisierer-Klasse (D-03) ─────────────────────────────────────────

class AnrufAnonymisierer:
    """Thread-safe Token-Cache fuer einen Anruf.
    Lifecycle: init_session_state -> pop_session_state (D-06).
    Cache NIEMALS in DB persistieren (BfDI-Konsultation).
    """

    def __init__(self):
        self._lock = threading.Lock()
        self.mapping: dict = {}            # 'Mueller' -> '[PERSON_A]'
        self.counters: dict = {'PERSON': 0, 'ORG': 0, 'LOC': 0}

    def get_or_assign_token(self, entity_text: str, entity_type: str) -> str:
        """Gibt stabilen Token fuer entity_text zurueck (erstellt neuen bei erstem Auftritt).
        >26 Treffer: [PERSON_AA], [PERSON_AB], ...
        Thread-safe via self._lock.
        entity_type: beliebiger String (PERSON, ORG, LOC, IBAN, EMAIL, TEL, USTID, STEUERNR, KREDITKARTE, ...)
        """
        with self._lock:
            if entity_text in self.mapping:
                return self.mapping[entity_text]
            idx = self.counters.setdefault(entity_type, 0)
            if idx < 26:
                suffix = chr(ord('A') + idx)
            else:
                suffix = 'A' + chr(ord('A') + (idx - 26))
            token = f'[{entity_type}_{suffix}]'
            self.mapping[entity_text] = token
            self.counters[entity_type] += 1
            return token


# ── Hilfsfunktionen ──────────────────────────────────────────────────────────

def _luhn_check(number_str: str) -> bool:
    digits = [int(d) for d in number_str if d.isdigit()]
    if len(digits) < 13:
        return False
    odd_digits = digits[-1::-2]
    even_digits = digits[-2::-2]
    total = sum(odd_digits)
    for d in even_digits:
        total += sum(divmod(d * 2, 10))
    return total % 10 == 0


def _parse_phone_de(text: str) -> list:
    """DE-Telefonnummern via phonenumbers mit Regex-Fallback."""
    found = []
    try:
        import phonenumbers
        for match in phonenumbers.PhoneNumberMatcher(text, 'DE'):
            found.append(text[match.start:match.end])
    except Exception:
        for m in re.finditer(r'(?:\+49|0049|0)\s*\d{2,5}[\s/\-]?\d{3,}[\s\d]{0,10}', text):
            found.append(m.group())
    return found


def _apply_regex_filter(text: str, cache: Optional[AnrufAnonymisierer]) -> Tuple[str, str]:
    """Regex-Vorfilter: ersetzt strukturierte PII durch [TYP_X]-Tokens.
    Gibt (bearbeiteter_text, quality_tier) zurueck. quality_tier='A' wenn kein Edge-Case.
    """
    tier = 'A'

    # WR-02 fix: collect phone matches from original text BEFORE any mutation
    # (IBAN/email replacements insert tokens that could confuse phone regex fallback)
    _phone_vals = _parse_phone_de(text)

    # IBAN
    for m in _RE_IBAN.finditer(text):
        iban_val = m.group()
        if cache:
            token = cache.get_or_assign_token(iban_val, 'IBAN')
        else:
            token = '[IBAN_X]'
        text = text.replace(iban_val, token)

    # E-Mail
    for m in _RE_EMAIL.finditer(text):
        email_val = m.group()
        if cache:
            token = cache.get_or_assign_token(email_val, 'EMAIL')
        else:
            token = '[EMAIL_X]'
        text = text.replace(email_val, token)

    # Telefon (phonenumbers-Library) — apply pre-collected matches from original text
    for phone_val in _phone_vals:
        if cache:
            token = cache.get_or_assign_token(phone_val, 'TEL')
        else:
            token = '[TEL_X]'
        text = text.replace(phone_val, token)

    # USt-ID
    for m in _RE_USTID.finditer(text):
        ustid_val = m.group()
        if cache:
            token = cache.get_or_assign_token(ustid_val, 'USTID')
        else:
            token = '[USTID_X]'
        text = text.replace(ustid_val, token)

    # Steuernummer
    for m in _RE_STEUERNR.finditer(text):
        nr_val = m.group()
        if cache:
            token = cache.get_or_assign_token(nr_val, 'STEUERNR')
        else:
            token = '[STEUERNR_X]'
        text = text.replace(nr_val, token)

    # Kreditkarte (nur mit Luhn-Check)
    for m in _RE_KREDITKARTE.finditer(text):
        cc_val = m.group()
        if _luhn_check(cc_val):
            if cache:
                token = cache.get_or_assign_token(cc_val, 'KREDITKARTE')
            else:
                token = '[KREDITKARTE_X]'
            text = text.replace(cc_val, token)

    # Geburtsdatum mit Kontext-Marker
    text = _RE_DATUM_KONTEXT.sub('[DATUM]', text)

    return (text, tier)


def _apply_ner(text: str, cache: Optional[AnrufAnonymisierer], nlp) -> Tuple[str, str]:
    """spaCy NER: ersetzt PER/LOC/ORG durch stabile [TYP_X]-Tokens.
    quality_tier='B' wenn unsichere NER-Treffer (strukturelle Heuristik).
    HINWEIS: spaCy de_core_news_lg liefert KEINE Confidence-Scores fuer NER (Pitfall 1).
    quality_tier='B' via: Token-Laenge < 3 Zeichen, keine Grossbuchstaben, Sonderzeichen.
    """
    tier = 'A'
    doc = nlp(text)
    # Offset-basiertes Replacement (Entities von hinten nach vorne um Offset-Shift zu vermeiden)
    spans = [(ent.start_char, ent.end_char, ent.label_, ent.text) for ent in doc.ents
             if ent.label_ in ('PER', 'LOC', 'ORG')]
    # Sortiere von hinten nach vorne
    spans.sort(key=lambda x: x[0], reverse=True)
    for start, end, label, ent_text in spans:
        # Typ-Mapping: PER->PERSON, LOC->LOC, ORG->ORG
        token_type = 'PERSON' if label == 'PER' else label
        # quality_tier='B' Heuristik (kein spaCy-Confidence-Score verfuegbar)
        is_uncertain = (
            len(ent_text) < 3
            or not ent_text[0].isupper()
            or any(c in ent_text for c in ['/', '\\', '@', '#'])
        )
        if is_uncertain:
            tier = 'B'
        if cache:
            token = cache.get_or_assign_token(ent_text, token_type)
        else:
            # Kein Cache (Ghost-SID, Pitfall 3): anonymer Token ohne Mapping-Persistenz
            token = f'[{token_type}_X]'
        text = text[:start] + token + text[end:]
    return (text, tier)


def _check_art9(text: str) -> bool:
    """Prueft ob text Art-9-DSGVO-Keywords enthaelt. 0% False-Negative Pflicht.
    WICHTIG: ART9_KEYWORDS ist Modul-Level-Import (NICHT hier importieren —
    Cross-AI-Review Finding 1: per-call Import ist Anti-Pattern).
    """
    text_lower = text.lower()
    for keywords in ART9_KEYWORDS.values():
        for kw in keywords:
            if kw in text_lower:
                return True
    return False


def _register_error() -> None:
    """Prueft Rolling-Error-Rate und setzt is_pipeline_healthy bei Schwellenwert (D-08 Kat. C)."""
    global is_pipeline_healthy
    now = time.monotonic()
    with _error_lock:
        _error_timestamps.append(now)
        cutoff = now - ROLLING_ERROR_WINDOW_S
        while _error_timestamps and _error_timestamps[0] < cutoff:
            _error_timestamps.pop(0)
        if len(_error_timestamps) > ROLLING_ERROR_THRESHOLD:
            is_pipeline_healthy = False   # Kat. C: degraded


# ── Public-Funktionen ────────────────────────────────────────────────────────

def anonymize(text: str, cache: Optional[AnrufAnonymisierer]) -> Tuple[str, str]:
    """
    DSGVO-Anonymisierungs-Pipeline (INPUT-PFAD: rohes STT-Material).

    Pipeline-Reihenfolge:
      Schritt 0: Art-9-Filter (ZUERST — 0% False-Negative Pflicht)
      Schritt 1: Regex-Vorfilter (IBAN, Email, Tel, USt-ID, Steuernr, Kreditkarte, Datum)
      Schritt 2: spaCy NER (PER/LOC/ORG -> Buchstaben-Tokens)

    Returns: Tuple[str, str] — (anonymized_text, quality_tier)
      quality_tier='A': sauber anonymisiert, keine Art-9-Treffer
      quality_tier='B': Edge-Cases (unsichere NER-Treffer via Heuristik)
      quality_tier='C': Art-9-Treffer -> '[ART9_REDACTED]', oder Exception -> '[ANON_FEHLER]'

    WICHTIG (D-05 vs. Req-4 Aufloesung): Bei Art-9-Treffer return ('[ART9_REDACTED]', 'C').
    Caller-Code prueft: if anon_text == '[ART9_REDACTED]': skip_insert()
    Alternativ: if not should_persist(anon_text): skip_insert()
    Cache=None: Regex-Only-Modus + NER ohne Mapping-Persistenz (Ghost-SID-Fallback, Pitfall 3).
    """
    global is_pipeline_healthy

    # D-08 Kat. A: Pipeline-Lade-Fehler
    if not is_pipeline_healthy:
        raise AnonymizationPipelineUnavailable('[ANON] Pipeline nicht verfuegbar (is_pipeline_healthy=False)')

    if not text or not text.strip():
        return ('', 'A')

    # Schritt 0: Art-9-Filter (MUSS VOR Regex+NER laufen — D-04)
    try:
        if _check_art9(text):
            # Ganzer Snippet verworfen — kein Partial-Replace (DSGVO-Pflicht)
            return ('[ART9_REDACTED]', 'C')
    except Exception as e:
        _register_error()
        print(f'[ANON] Art9-Check-Fehler (len={len(text)}): {type(e).__name__}')
        return ('[ANON_FEHLER]', 'C')

    # Schritt 1: Regex-Vorfilter
    try:
        text, tier = _apply_regex_filter(text, cache)
    except Exception as e:
        _register_error()
        print(f'[ANON] Regex-Fehler (len={len(text)}): {type(e).__name__}')
        return ('[ANON_FEHLER]', 'C')

    # Schritt 2: spaCy NER
    try:
        nlp = _get_nlp()
        if nlp and is_pipeline_healthy:
            text, ner_tier = _apply_ner(text, cache, nlp)
            if ner_tier == 'B':
                tier = 'B'
    except AnonymizationPipelineUnavailable:
        raise
    except Exception as e:
        _register_error()
        print(f'[ANON] NER-Fehler (len={len(text)}): {type(e).__name__}')
        return ('[ANON_FEHLER]', 'C')

    return (text, tier)


def anonymize_output(text: str, cache: Optional[AnrufAnonymisierer]) -> str:
    """
    OUTPUT-PFAD: Cache-Reverse-Lookup fuer Claude-generierten Text.
    Ersetzt alle bekannten Klartext-Entitaeten aus cache.mapping durch ihre Tokens.
    Laengere Keys zuerst (verhindert Partial-Matches: 'Dr. Mueller' vor 'Mueller').
    Kein NER-Aufruf (Output-Pfad ist Cache-Lookup-Only, A6 aus RESEARCH.md).
    """
    if not text or not cache:
        return text if text else ''
    with cache._lock:
        items = sorted(cache.mapping.items(), key=lambda x: len(x[0]), reverse=True)
    for original, token in items:
        if original in text:
            text = text.replace(original, token)
    return text


def register_briefing_pii(briefing_data: dict, cache: AnrufAnonymisierer) -> None:
    """
    Vorbefuellung des Token-Caches mit PreCall-Briefing-PII.
    Briefing-PII bekommt zuerst Buchstaben (A, B, ...) — Live-Mitschrift danach (D-03).
    Verdrahtung in live_session.py kommt in Phase 08.23.2.G (Account-Memory-Tabelle).
    """
    if not briefing_data or not cache:
        return
    # Personennamen aus Briefing registrieren
    for feld in ('personen', 'ansprechpartner', 'kontakte'):
        personen = briefing_data.get(feld, [])
        if isinstance(personen, list):
            for name in personen:
                if isinstance(name, str) and name.strip():
                    cache.get_or_assign_token(name.strip(), 'PERSON')
    # Firma aus Briefing registrieren
    firmenname = briefing_data.get('firmenname') or briefing_data.get('firma', '')
    if isinstance(firmenname, str) and firmenname.strip():
        cache.get_or_assign_token(firmenname.strip(), 'ORG')


def should_persist(anon_text: str) -> bool:
    """Gibt False zurueck wenn anon_text nicht in die DB persistiert werden soll.
    Verhindert DB-Spam mit literalem '[ART9_REDACTED]' oder '[ANON_FEHLER]' (D-05).
    Caller-Verwendung: if not should_persist(anon_text): continue  # skip DB insert
    """
    return anon_text not in ('[ART9_REDACTED]', '[ANON_FEHLER]')


def _record_snippet_error() -> None:
    """Registriert einen Snippet-Fehler ([ANON_FEHLER]) fuer Rolling-Error-Rate (D-08 Kat. C).
    Thread-safe via _error_lock. Entfernt Eintraege ausserhalb des Zeitfensters.
    """
    now = time.monotonic()
    with _error_lock:
        _error_timestamps.append(now)
        # Prune: Eintraege aelter als ROLLING_ERROR_WINDOW_S entfernen
        cutoff = now - ROLLING_ERROR_WINDOW_S
        while _error_timestamps and _error_timestamps[0] < cutoff:
            _error_timestamps.pop(0)


def get_pipeline_status() -> dict:
    """Gibt pipeline_status und error_count_10min zurueck fuer /api/health Endpoint.
    'ok': Pipeline verfuegbar, keine erhoehlte Fehlerrate
    'degraded': Rolling-Error-Rate ueber Schwellenwert (D-08 Kat. C)
    'unavailable': spaCy nicht ladbar (D-08 Kat. A)
    """
    now = time.monotonic()
    with _error_lock:
        cutoff = now - ROLLING_ERROR_WINDOW_S
        recent_errors = sum(1 for ts in _error_timestamps if ts >= cutoff)
    if not is_pipeline_healthy:
        return {'status': 'unavailable', 'error_count_10min': recent_errors}
    if recent_errors > ROLLING_ERROR_THRESHOLD:
        return {'status': 'degraded', 'error_count_10min': recent_errors}
    return {'status': 'ok', 'error_count_10min': recent_errors}
