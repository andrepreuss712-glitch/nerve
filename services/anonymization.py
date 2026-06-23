"""
DSGVO-Anonymisierungs-Foundation-Modul fuer NERVE.
Pipeline-Reihenfolge: Art-9-Filter (Schritt 0) -> Regex (Schritt 1) -> spaCy+GLiNER NER (Schritt 2)
Phase: 08.23.2.B + 08.23.2.C (GLiNER Union-Voting)
"""
import os
import re
import time
import threading
import concurrent.futures
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


# ── GLiNER Lazy-Load (Thread-safe Double-Checked Locking) ── Phase 08.23.2.C ─

_gliner_model = None
_gliner_lock = threading.Lock()


def _get_gliner():
    """Thread-safe lazy load von GLiNER gliner_multi-v2.1.
    Analog _get_nlp(). Bei Load-Fehler: is_pipeline_healthy=False, return None.
    GLiNER-Import bleibt innerhalb dieser Funktion (Cross-AI-Finding 1: kein Modul-Level-Import).
    """
    global _gliner_model, is_pipeline_healthy
    if _gliner_model is not None:
        return _gliner_model
    with _gliner_lock:
        if _gliner_model is not None:
            return _gliner_model
        try:
            from gliner import GLiNER
            _gliner_model = GLiNER.from_pretrained('urchade/gliner_multi-v2.1')
            print('[ANON] GLiNER gliner_multi-v2.1 geladen')
        except Exception as e:
            print(f'[ANON] KRITISCH: GLiNER nicht ladbar: {type(e).__name__}: {e}')
            is_pipeline_healthy = False
            _gliner_model = None
    return _gliner_model


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


# ── GLiNER-Konfidenz-Schwelle (Phase 08.23.2.D.UX.3 Task R3) ──────────────────
# 0.5 (GLiNER-Default) liess Low-Confidence-Fehlalarme durch ('nach dem Anruf'->LOC).
# Code-Default bewusst 0.55 (NICHT 0.6): Cross-AI Gemini HIGH — 0.6 riskiert
# False Negatives bei echten Namen mit score ~0.55 (DSGVO Art. 32, PII-Leck).
# 0.55 = milder Precision-Schwenk; echte Namen haben score typ. >0.85, bleiben getaggt.
# ENV-Override erlaubt Live-Tuning ohne Redeploy (Production-only-Verify, Task R6/Task 4).
# Eine Anhebung auf 0.6 ist eine BEWUSSTE Folge-Entscheidung NACH Korpus-Validierung
# (Task 4: 5-10 historische Prod-Calls), NICHT im Code festgeschrieben.
GLINER_THRESHOLD = float(os.environ.get('GLINER_THRESHOLD', '0.55'))

# ── Pronomen-Whitelist (Phase 08.23.2.D.UX.3 Task R2) ─────────────────────────
# NIE anonymisieren — sonst landen 'ich'/'Sie' im Cache und zerreissen via
# Substring-Replace ganze Woerter (Wortteil-Bug). Lowercase-Vergleich.
# DATEN-Strings -> echte Umlaute erlaubt (CLAUDE.md UTF-8-Regel, Identifier ASCII).
# Bewusst KONSERVATIV: nur eindeutige Funktionswoerter (kein echter Kontakt heisst so).
# Known-Limitation (Gemini LOW): .lower()-Vergleich koennte theoretisch 'Wir GmbH'
# (falls GLiNER nur 'Wir' taggt) ueberspringen — bei B2B-Cold-Calls akzeptabel.
PRONOMEN_WHITELIST = frozenset({
    'ich', 'mich', 'mir', 'mein', 'meine', 'meiner', 'meinem', 'meinen', 'meins',
    'du', 'dich', 'dir', 'dein', 'deine', 'deiner', 'deinem', 'deinen',
    'sie', 'ihr', 'ihre', 'ihrer', 'ihrem', 'ihren', 'ihres',
    'er', 'es', 'ihm', 'ihn', 'seiner', 'sein', 'seine',
    'wir', 'uns', 'unser', 'unsere', 'unserer', 'unserem', 'unseren',
    'man', 'wer', 'wen', 'wem',
    # Ueber-Schaerfe-Fix (Req 11/FOLD A-2): fehlende Dativ-/2.-Pers.-Pl.-/Reflexiv-Funktionswoerter
    # nachgetragen ('Ihnen' wurde als PERSON->[PERSON_A] ueber-geschwaerzt, weil die Dativform fehlte).
    # Deckt via _is_whitelisted automatisch alle 6 NER-Pfade (sequenziell+parallel, spaCy+GLiNER).
    # DSGVO: keine realen Nachnamen, kein Heuristik-Lockern — reine Funktionswort-Whitelist.
    'ihnen', 'euch', 'euer', 'eure', 'sich', 'einander',
})

# ── Generic-Berufs-/Org-Nomen-Whitelist (Phase 08.23.2.D.UX.3 Task R4) ────────
# Generische Berufs- UND Org-Nomen werden nie als ORG tokenisiert.
# Real-Daten-Befund: sichtbarer ORG-Laerm kommt v.a. von generischen Nomen
# ('Firmen'/'Unternehmen'), nicht Berufen -> beide Listen (Claude's Discretion,
# sinnvoller Default = beides, da billig; RESEARCH Open Question 1 + A3).
GENERIC_BERUF_WHITELIST = frozenset({
    # Berufe
    'vertriebler', 'berater', 'beraterin', 'manager', 'managerin',
    'verkäufer', 'verkäuferin', 'geschäftsführer', 'geschäftsführerin',
    'mitarbeiter', 'mitarbeiterin', 'kollege', 'kollegin', 'chef', 'chefin',
    'kunde', 'kundin', 'ansprechpartner', 'ansprechpartnerin',
    'entscheider', 'entscheiderin', 'leiter', 'leiterin',
    # Generische Org-/Abteilungs-Nomen
    'firma', 'firmen', 'unternehmen', 'betrieb', 'betriebe', 'gesellschaft',
    # Folge-Fix 2026-06-05 (Prod-Log Call 15:04): generische Abteilungs-/Funktions-Nomen,
    # die als ORG/PERSON ueber-geschwaerzt wurden ('Vertriebsteams'->ORG, 'Einkauf'->ORG).
    'team', 'teams', 'vertrieb', 'vertriebsteam', 'vertriebsteams', 'einkauf',
    'abteilung', 'abteilungen', 'geschäftsführung', 'vorstand', 'marketing',
    'personal', 'buchhaltung', 'einkaufsabteilung', 'vertriebsabteilung',
})

# Folge-Fix 2026-06-05: Mehrwort-Span-Stopwords — Artikel/Quantoren, die NIE allein PII
# sind. Nur fuer den Mehrwort-Check in _is_whitelisted (siehe dort): ein Span wird NUR
# uebersprungen, wenn JEDES Token unkritisch ist (Pronomen/Generic/Stopword) -> ein
# echter Name im Span macht die Bedingung sofort False (kein PII-Leak).
_MULTIWORD_STOPWORDS = frozenset({
    'der', 'die', 'das', 'den', 'dem', 'des',
    'ein', 'eine', 'einen', 'einem', 'einer', 'eines', 'kein', 'keine',
    'viele', 'viel', 'manche', 'einige', 'alle', 'jede', 'jeder', 'jedes',
    'und', 'oder', 'von', 'vom', 'zur', 'zum', 'im', 'in', 'bei', 'mit',
})


def _is_whitelisted(ent_text: str, token_type: str) -> bool:
    """Zentrale Whitelist-Filterlogik (Phase 08.23.2.D.UX.3, Gemini-Review MEDIUM).
    EINZIGE Quelle der Wahrheit — an allen 3 NER-Stellen aufgerufen, nie inline
    dupliziert (verhindert Gatekeeper-Inkonsistenz). Pronomen typ-unabhaengig,
    Generic-Nomen nur fuer ORG.
    """
    low = ent_text.strip().lower()
    if low in PRONOMEN_WHITELIST:
        return True
    # Folge-Fix 2026-06-05: Generic-Nomen jetzt TYP-UNABHAENGIG (auch PERSON, nicht nur ORG).
    # Real-Daten Call 15:04: 'Vertriebler' wurde als PERSON getaggt -> ORG-only-Check griff nicht.
    if low in GENERIC_BERUF_WHITELIST:
        return True
    # Folge-Fix 2026-06-05: Mehrwort-Span ('wir Vertriebler', 'Viele Firmen') -> skip NUR wenn
    # JEDES Token unkritisch ist (Pronomen/Generic/Stopword). DSGVO-sicher: ein echter Name im
    # Span macht die all()-Bedingung False -> Span wird weiter geschwaerzt.
    tokens = low.split()
    if len(tokens) > 1 and all(
        (t in PRONOMEN_WHITELIST or t in GENERIC_BERUF_WHITELIST or t in _MULTIWORD_STOPWORDS)
        for t in tokens
    ):
        return True
    return False


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


def _dedup_overlapping_spans(
    spans: List[Tuple[int, int, str, str]]
) -> List[Tuple[int, int, str, str]]:
    """Entfernt ueberlappende/verschachtelte Entity-Spans VOR dem Reverse-Replace
    (Phase 08.23.2.D.UX.3 Folge-Fix 2026-06-05).

    Union-Voting (spaCy OR GLiNER) liefert oft ueberlappende Spans fuer denselben
    Namen, z.B. 'Frau Berg' [0:9] UND 'Berg' [5:9]. Der Reverse-Replace nimmt
    NICHT-ueberlappende Spans an — ueberlappende korrumpieren sonst die Offsets
    ('[PERSON_E]SON_D]'-Doppel-Klammer-Bug, Prod-Log Call 15:04) ODER lassen PII
    teils im Klartext ('[PERSON_J] Brennecke GmbH').

    Strategie: laengster Span gewinnt (maximale PII-Abdeckung), ueberlappende
    kuerzere werden verworfen. DSGVO: bevorzugt mehr Schwaerzung, nie weniger.
    Returns: nicht-ueberlappende Spans, nach start aufsteigend sortiert.
    """
    uniq = list(set(spans))
    # laengster Span zuerst -> greedy behalten, kuerzere Overlaps fallen raus
    uniq.sort(key=lambda s: (s[1] - s[0]), reverse=True)
    kept: List[Tuple[int, int, str, str]] = []
    for s in uniq:
        s_start, s_end = s[0], s[1]
        # Overlap iff NICHT (s_end <= k_start ODER s_start >= k_end)
        if not any((not (s_end <= k[0] or s_start >= k[1])) for k in kept):
            kept.append(s)
    kept.sort(key=lambda s: s[0])
    return kept


def _apply_ner(text: str, cache: Optional[AnrufAnonymisierer], nlp) -> Tuple[str, str]:
    """Union-Voting: spaCy OR GLiNER fuer Personen-/Organisations-/Ortsnamen.
    Recall maximieren — DSGVO-Pflicht (D-01 Anonymisierungs-Pipeline).
    Review Finding 1: native GLiNER-Offsets bevorzugt, re.finditer() als Fallback.
    quality_tier='B' wenn unsichere spaCy-Treffer (strukturelle Heuristik).
    """
    tier = 'A'
    all_spans: List[Tuple[int, int, str, str]] = []  # (start, end, token_type, original_text)

    # spaCy-Treffer (Char-Offsets verfuegbar via ent.start_char / ent.end_char)
    if nlp:
        doc = nlp(text)
        for ent in doc.ents:
            if ent.label_ in ('PER', 'LOC', 'ORG'):
                token_type = 'PERSON' if ent.label_ == 'PER' else ent.label_
                # quality_tier='B' Heuristik (kein spaCy-Confidence-Score verfuegbar)
                is_uncertain = (
                    len(ent.text) < 3
                    or not ent.text[0].isupper()
                    or any(c in ent.text for c in ['/', '\\', '@', '#'])
                )
                if is_uncertain:
                    tier = 'B'
                if _is_whitelisted(ent.text, token_type):
                    continue
                all_spans.append((ent.start_char, ent.end_char, token_type, ent.text))

    # GLiNER-Treffer — native Offsets preferred, re.finditer() als Fallback (Review Finding 1)
    gliner = _get_gliner()
    if gliner is not None:
        try:
            results = gliner.predict_entities(
                text,
                ['person', 'organisation', 'location'],
                threshold=GLINER_THRESHOLD,
            )
            for ent in results:
                ent_text = ent.get('text', '')
                if not ent_text:
                    continue
                ent_label = ent.get('label', '').lower()
                if ent_label == 'person':
                    token_type = 'PERSON'
                elif ent_label == 'organisation':
                    token_type = 'ORG'
                elif ent_label == 'location':
                    token_type = 'LOC'
                else:
                    continue

                if _is_whitelisted(ent_text, token_type):
                    continue

                # Native Offsets wenn GLiNER sie liefert (Standard-Lib gliner_multi-v2.1)
                if 'start' in ent and 'end' in ent:
                    all_spans.append((ent['start'], ent['end'], token_type, ent_text))
                else:
                    # Fallback: re.finditer findet ALLE Vorkommen (robuster als text.find-Loop)
                    for m in re.finditer(re.escape(ent_text), text):
                        all_spans.append((m.start(), m.end(), token_type, ent_text))
        except Exception as e:
            print(f'[ANON] GLiNER predict_entities Fehler: {type(e).__name__}')
            # Kein Fail-Hard — spaCy-only-Treffer reichen fuer Fallback

    # Folge-Fix 2026-06-05: ueberlappende/verschachtelte Spans mergen (laengster gewinnt) —
    # verhindert Offset-Korruption beim Reverse-Replace (Doppel-Klammer + ORG-Teil-Leak).
    unique_spans = _dedup_overlapping_spans(all_spans)
    _merged = len(set(all_spans)) - len(unique_spans)
    if _merged > 0:
        print(f'[ANON] {_merged} ueberlappende Span(s) gemergt (Reverse-Replace-Schutz)')

    # Replacement (reverse so spaetere Spans nicht offset-shiften)
    result = text
    for start, end, token_type, original in reversed(unique_spans):
        if cache:
            token = cache.get_or_assign_token(original, token_type)
        else:
            # Kein Cache (Ghost-SID, Pitfall 3): anonymer Token ohne Mapping-Persistenz
            token = f'[{token_type}_X]'
        result = result[:start] + token + result[end:]

    return (result, tier)


def _apply_ner_parallel(text: str, cache: Optional[AnrufAnonymisierer], nlp) -> Tuple[str, str]:
    """Concurrent spaCy + GLiNER dispatch fuer Latenz-Reduktion (Review Finding 2).

    Wird verwendet wenn Server-GLiNER-P95 > 100ms bei sequentiellem _apply_ner().
    GIL-Release erlaubt echte Parallelitaet bei I/O-bound-Inferenz.
    """

    def run_spacy() -> List[Tuple[int, int, str, str]]:
        if nlp is None:
            return []
        doc = nlp(text)
        spans: List[Tuple[int, int, str, str]] = []
        for e in doc.ents:
            if e.label_ not in ('PER', 'LOC', 'ORG'):
                continue
            token_type = 'PERSON' if e.label_ == 'PER' else e.label_
            if _is_whitelisted(e.text, token_type):
                continue
            spans.append((e.start_char, e.end_char, token_type, e.text))
        return spans

    def run_gliner() -> List[Tuple[int, int, str, str]]:
        gliner = _get_gliner()
        if gliner is None:
            return []
        spans: List[Tuple[int, int, str, str]] = []
        try:
            results = gliner.predict_entities(
                text,
                ['person', 'organisation', 'location'],
                threshold=GLINER_THRESHOLD,
            )
            for ent in results:
                ent_text = ent.get('text', '')
                if not ent_text:
                    continue
                ent_label = ent.get('label', '').lower()
                if ent_label == 'person':
                    token_type = 'PERSON'
                elif ent_label == 'organisation':
                    token_type = 'ORG'
                elif ent_label == 'location':
                    token_type = 'LOC'
                else:
                    continue
                if _is_whitelisted(ent_text, token_type):
                    continue
                if 'start' in ent and 'end' in ent:
                    spans.append((ent['start'], ent['end'], token_type, ent_text))
                else:
                    for m in re.finditer(re.escape(ent_text), text):
                        spans.append((m.start(), m.end(), token_type, ent_text))
        except Exception as e:
            print(f'[ANON] parallel GLiNER Fehler: {type(e).__name__}')
        return spans

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        f_spacy = pool.submit(run_spacy)
        f_gliner = pool.submit(run_gliner)
        spacy_spans = f_spacy.result()
        gliner_spans = f_gliner.result()

    # Folge-Fix 2026-06-05: ueberlappende Spans mergen (siehe _dedup_overlapping_spans).
    _raw = spacy_spans + gliner_spans
    all_spans = _dedup_overlapping_spans(_raw)
    _merged = len(set(_raw)) - len(all_spans)
    if _merged > 0:
        print(f'[ANON] {_merged} ueberlappende Span(s) gemergt (parallel, Reverse-Replace-Schutz)')

    result = text
    for start, end, token_type, original in reversed(all_spans):
        if cache:
            token = cache.get_or_assign_token(original, token_type)
        else:
            token = f'[{token_type}_X]'
        result = result[:start] + token + result[end:]

    return (result, 'A')


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

    WR-04 Thread-Safety-Hinweis: Der Lock wird nur fuer den Snapshot gehalten
    (items = sorted(...)). Die Ersetzungsschleife laeuft ausserhalb des Locks.
    Das ist korrekt — Tokens sind write-once (get_or_assign_token weist denselben
    Key nie neu zu). Bekannte Einschraenkung: Mapping-Eintraege die NACH dem Snapshot
    via register_briefing_pii() oder get_or_assign_token() in einem anderen Thread
    hinzugefuegt werden, werden in diesem Output-Pass nicht substituiert. Fuer den
    aktuellen Single-Session-Betrieb ist dieses Risiko gering (D-08, WR-04).
    """
    if not text or not cache:
        return text if text else ''
    with cache._lock:
        items = sorted(cache.mapping.items(), key=lambda x: len(x[0]), reverse=True)
    # R5B (defensiv): Keys ueberspringen die selbst wie ein fertiger Token aussehen
    # ([PERSON_A] etc.) — verhindert Re-Tokenisierung/Doppel-Klammer bei Re-Run.
    _token_like = re.compile(r'^\[[A-Z_]+_[A-Z]+\]$')
    items = [(o, t) for (o, t) in items if not _token_like.match(o)]
    for original, token in items:
        if original not in text:
            continue
        # Wortgrenzen-Replace (Phase 08.23.2.D.UX.3 Task R1): Defense-in-depth
        # gegen Substring-Replace mitten im Wort ('ich'->[PERSON_C] in 'wirklich').
        # Lookarounds statt \b — robuster an Umlaut-Grenzen (Pitfall 3).
        # Mehrteilige Keys ('Dr. Mueller') bleiben an den aeusseren Grenzen korrekt.
        # Keys die auf '.'/Ziffer enden (z.B. 'Commerzbank AG', IBAN-Tokens mit
        # Leerzeichen) sitzen korrekt an den aeusseren Wortgrenzen; re.escape
        # neutralisiert Sonderzeichen im Key.
        pattern = r'(?<!\w)' + re.escape(original) + r'(?!\w)'
        text = re.sub(pattern, lambda _m, _t=token: _t, text, flags=re.UNICODE)
    return text


def anonymize_for_storage(text: str, sid: str) -> str:
    """
    FOLD A-2 / Req 11: GEMEINSAMER Storage-Anon-Helper — EINZIGE Quelle der Wahrheit
    fuers "Text fuer die Speicherung saeubern" (wie _is_whitelisted; verhindert Drift
    zwischen den Storage-Stellen Auto-Variante / Knopf-Pfad / Keyword).

    Garantie: nie roh, nie verloren, jeder Notweg geloggt.
      (a) Per-SID-Cache da   -> anonymize_output(text, cache)  (konsistente Tokens wie Transkript)
      (b) Cache None / (a) wirft -> FRISCHE anonymize(text, cache_or_None) — liefert NIE rohe
          Namen ('[PERSON_X]'/Sentinel, Audit-belegt :534/:574), auch ohne Mapping-Persistenz.
      (c) auch (b) wirft     -> geschwaerzte Minimal-Form ('[ANON_FEHLER]') — Zeile bleibt schreibbar.
      (d) bei (b)/(c)        -> '[ANON] storage-fallback ...' Log (Notweg nie still).
    Gibt NIE den rohen Eingabetext zurueck. Die LIVE-Anzeige bleibt davon unberuehrt (immer roh).
    """
    if not text or not text.strip():
        return ''
    # (a) Cache-Replay — nur wenn der Per-SID-Merkzettel WIRKLICH da ist (cache=None-No-Op-Falle meiden)
    cache = None
    try:
        import services.live_session as _ls  # lazy: vermeidet Modul-Zyklus (live_session importiert anon)
        cache = _ls.get_anonymisierer(sid)
    except Exception as _e:
        print(f'[ANON] storage-fallback: get_anonymisierer warf sid={sid!r} grund={type(_e).__name__}')
        cache = None
    if cache is not None:
        try:
            return anonymize_output(text, cache)
        except Exception as _e:
            print(f'[ANON] storage-fallback: cache-replay warf sid={sid!r} '
                  f'grund={type(_e).__name__} -> frische Saeuberung')
    else:
        print(f'[ANON] storage-fallback: kein Per-SID-Cache sid={sid!r} -> frische Saeuberung')
    # (b) Frische Saeuberung — anonymize liefert auch mit cache=None nie rohe Namen
    try:
        anon_text, _tier = anonymize(text, cache)
        return anon_text if anon_text else '[ANON_LEER]'
    except Exception as _e:
        # (c) Last-Resort: nie roh, nie verloren — geschwaerzt + markiert, Zeile bleibt schreibbar
        print(f'[ANON] storage-fallback: frische Saeuberung warf sid={sid!r} '
              f'grund={type(_e).__name__} -> geschwaerzt')
        return '[ANON_FEHLER]'


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


def extract_entities(text: str, cache=None) -> list:
    """Gibt rohe NER-Treffer mit Source-Tag zurueck.

    Fuer Konsens-Voting in services/gatekeeper.classify_contact() (D-01 Gatekeeper-Pfad).

    Args:
        text: Roher Transkript-Text.
        cache: Optional, nicht verwendet — Signatur konsistent mit anonymize().

    Returns:
        List[dict]: [{'text': str, 'type': 'PERSON'|'ORG'|'LOC', 'source': 'spacy'|'gliner'}, ...]
        Leere Liste wenn NER nicht verfuegbar.
    """
    entities: list = []

    nlp = _get_nlp()
    if nlp is not None:
        try:
            doc = nlp(text)
            for ent in doc.ents:
                if ent.label_ in ('PER', 'LOC', 'ORG'):
                    token_type = 'PERSON' if ent.label_ == 'PER' else ent.label_
                    if _is_whitelisted(ent.text, token_type):
                        continue
                    entities.append({
                        'text': ent.text,
                        'type': token_type,
                        'source': 'spacy',
                    })
        except Exception as e:
            print(f'[ANON] extract_entities spaCy Fehler: {type(e).__name__}')

    gliner = _get_gliner()
    if gliner is not None:
        try:
            results = gliner.predict_entities(
                text,
                ['person', 'organisation', 'location'],
                threshold=GLINER_THRESHOLD,
            )
            for ent in results:
                ent_label = ent.get('label', '').lower()
                if ent_label == 'person':
                    token_type = 'PERSON'
                elif ent_label == 'organisation':
                    token_type = 'ORG'
                elif ent_label == 'location':
                    token_type = 'LOC'
                else:
                    continue
                if _is_whitelisted(ent.get('text', ''), token_type):
                    continue
                entities.append({
                    'text': ent.get('text', ''),
                    'type': token_type,
                    'source': 'gliner',
                })
        except Exception as e:
            print(f'[ANON] extract_entities GLiNER Fehler: {type(e).__name__}')

    return entities


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
