"""
Unit-Tests fuer services/anonymization.py (Phase 08.23.2.B Plan-08)

Coverage: Req-1 bis Req-6 (anonymize, anonymize_output, register_briefing_pii, AnrufAnonymisierer)

CLAUDE.md Test-Qualitaets-Regel: NUR Runtime-Behavior-Tests.
Kein inspect.getsource(), kein open('file').read() + assert 'string' in src.
"""
import pytest
import threading
from typing import Optional


# ── Modul-State-Reset Fixture ──────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_anonymization_module_state():
    """
    Setzt den globalen Modul-State von services.anonymization vor JEDEM Test zurueck.
    Notwendig weil is_pipeline_healthy und _error_timestamps Modul-Level-Singletons sind.
    Ohne Reset: _get_nlp()-Fehler (z.B. spaCy nicht installiert) setzt is_pipeline_healthy=False
    und alle nachfolgenden anonymize()-Aufrufe raisen AnonymizationPipelineUnavailable.
    Runtime-Behavior-Test: dieser Fixture greift nur auf Modul-State zu (keine Source-Presence).
    """
    import services.anonymization as anon_module
    # State vor dem Test sichern
    original_healthy = anon_module.is_pipeline_healthy
    original_errors = list(anon_module._error_timestamps)
    original_nlp = anon_module._nlp
    # Vor Test: sauberen Zustand herstellen
    anon_module.is_pipeline_healthy = True
    anon_module._error_timestamps.clear()
    yield
    # Nach Test: Original-State wiederherstellen
    anon_module.is_pipeline_healthy = original_healthy
    anon_module._error_timestamps.clear()
    anon_module._error_timestamps.extend(original_errors)
    anon_module._nlp = original_nlp


# ── Imports ───────────────────────────────────────────────────────────────────

def test_import():
    """Req-1: Alle Symbole aus services.anonymization importierbar."""
    from services.anonymization import (
        AnrufAnonymisierer,
        anonymize,
        anonymize_output,
        register_briefing_pii,
        is_pipeline_healthy,
        AnonymizationPipelineUnavailable,
    )
    assert callable(anonymize)
    assert callable(anonymize_output)
    assert callable(register_briefing_pii)
    assert isinstance(is_pipeline_healthy, bool)
    assert issubclass(AnonymizationPipelineUnavailable, Exception)


# ── AnrufAnonymisierer ────────────────────────────────────────────────────────

def test_token_format_buchstaben():
    """D-03: Token-Format [PERSON_A] (Buchstabe), NICHT [PERSON_1] (Zahl)."""
    from services.anonymization import AnrufAnonymisierer
    cache = AnrufAnonymisierer()
    token = cache.get_or_assign_token('Mueller', 'PERSON')
    assert token == '[PERSON_A]', f"Erwartet '[PERSON_A]', erhalten: {token!r}"
    # Zweite Person bekommt B
    token_b = cache.get_or_assign_token('Schmidt', 'PERSON')
    assert token_b == '[PERSON_B]', f"Erwartet '[PERSON_B]', erhalten: {token_b!r}"


def test_token_stable_same_call():
    """Req-3: Gleicher Name -> gleicher Token im selben Anruf-Kontext."""
    from services.anonymization import AnrufAnonymisierer
    cache = AnrufAnonymisierer()
    t1 = cache.get_or_assign_token('Thomas Mueller', 'PERSON')
    t2 = cache.get_or_assign_token('Thomas Mueller', 'PERSON')
    assert t1 == t2, f"Stabiler Token erwartet, aber: {t1!r} vs {t2!r}"


def test_token_cross_session_independent():
    """D-03: Cross-Session-Unabhaengigkeit — zwei Instanzen starten bei A."""
    from services.anonymization import AnrufAnonymisierer
    cache1 = AnrufAnonymisierer()
    cache2 = AnrufAnonymisierer()
    t1 = cache1.get_or_assign_token('Mueller', 'PERSON')
    t2 = cache2.get_or_assign_token('Schmidt', 'PERSON')
    # Beide Instanzen beginnen bei A (keine gemeinsame Zaehlung)
    assert t1 == '[PERSON_A]'
    assert t2 == '[PERSON_A]'


def test_token_org_and_loc_independent_counter():
    """D-03: PERSON, ORG, LOC haben unabhaengige Zaehler."""
    from services.anonymization import AnrufAnonymisierer
    cache = AnrufAnonymisierer()
    p = cache.get_or_assign_token('Mueller', 'PERSON')
    o = cache.get_or_assign_token('Commerzbank', 'ORG')
    l = cache.get_or_assign_token('Frankfurt', 'LOC')
    assert p == '[PERSON_A]'
    assert o == '[ORG_A]'
    assert l == '[LOC_A]'


def test_token_thread_safe():
    """D-03: threading.Lock() — kein Data-Race bei parallelen Aufrufen."""
    from services.anonymization import AnrufAnonymisierer
    cache = AnrufAnonymisierer()
    results = []

    def assign():
        token = cache.get_or_assign_token('SharedName', 'PERSON')
        results.append(token)

    threads = [threading.Thread(target=assign) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    # Alle 10 Threads muessen denselben Token erhalten
    assert len(set(results)) == 1, f"Data-Race: {set(results)}"
    assert results[0] == '[PERSON_A]'


# ── Regex-Vorfilter ───────────────────────────────────────────────────────────

def test_regex_iban():
    """Req-2: IBAN wird tokenisiert; Original nicht mehr im Output."""
    from services.anonymization import AnrufAnonymisierer, anonymize
    cache = AnrufAnonymisierer()
    text = "Die IBAN DE89370400440532013000 bitte ueberweisen"
    result = anonymize(text, cache)
    assert result is not None
    anon_text, tier = result
    assert 'DE89370400440532013000' not in anon_text, f"IBAN noch im Output: {anon_text!r}"
    assert '[IBAN_' in anon_text, f"IBAN-Token erwartet: {anon_text!r}"


def test_regex_email():
    """Req-2: E-Mail wird tokenisiert."""
    from services.anonymization import AnrufAnonymisierer, anonymize
    cache = AnrufAnonymisierer()
    text = "Schick mir eine Mail an test@firma.de bitte"
    result = anonymize(text, cache)
    assert result is not None
    anon_text, _ = result
    assert 'test@firma.de' not in anon_text, f"Email noch im Output: {anon_text!r}"
    assert '[EMAIL_' in anon_text, f"Email-Token erwartet: {anon_text!r}"


def test_regex_multiple_pii():
    """Req-2: IBAN + Email + alle tokenisiert."""
    from services.anonymization import AnrufAnonymisierer, anonymize
    cache = AnrufAnonymisierer()
    text = "IBAN DE89370400440532013000, Mail test@firma.de"
    result = anonymize(text, cache)
    assert result is not None
    anon_text, _ = result
    assert 'DE89370400440532013000' not in anon_text
    assert 'test@firma.de' not in anon_text


# ── Art-9-Filter ─────────────────────────────────────────────────────────────

def test_art9_hit_returns_tuple():
    """D-05: anonymize() gibt IMMER Tuple zurueck (nicht None) — auch bei Art-9."""
    from services.anonymization import AnrufAnonymisierer, anonymize
    cache = AnrufAnonymisierer()
    result = anonymize("Ich bin nach der Chemo wieder voll arbeitsfaehig", cache)
    assert isinstance(result, tuple), f"Erwartet Tuple, erhalten: {type(result)}"
    assert len(result) == 2


def test_art9_hit_returns_redacted():
    """Req-4 (D-05): Art-9-Treffer -> ('[ART9_REDACTED]', 'C')."""
    from services.anonymization import AnrufAnonymisierer, anonymize
    cache = AnrufAnonymisierer()
    anon_text, tier = anonymize("Ich bin nach der Chemo wieder voll arbeitsfaehig", cache)
    assert anon_text == '[ART9_REDACTED]', f"Erwartet '[ART9_REDACTED]', erhalten: {anon_text!r}"
    assert tier == 'C', f"Erwartet quality_tier='C', erhalten: {tier!r}"


def test_art9_no_hit():
    """Req-4: Nicht-Art-9-Text -> kein [ART9_REDACTED]."""
    from services.anonymization import AnrufAnonymisierer, anonymize
    cache = AnrufAnonymisierer()
    result = anonymize("Der Preis ist zu hoch fuer uns", cache)
    assert result is not None
    anon_text, _ = result
    assert anon_text != '[ART9_REDACTED]', "Nicht-Art-9-Text sollte nicht redacted werden"


def test_art9_multiple_categories():
    """Req-4: Keywords aus verschiedenen Kategorien triggern Art-9."""
    from services.anonymization import AnrufAnonymisierer, anonymize
    cache = AnrufAnonymisierer()
    art9_snippets = [
        "Er ist Gewerkschaftsmitglied",
        "Sie ist Mitglied der Gruenen",
        "Er ist Betriebsrat",
        "Sie ist schwul",
    ]
    for snippet in art9_snippets:
        result = anonymize(snippet, cache)
        anon_text, tier = result
        assert anon_text == '[ART9_REDACTED]', f"Art-9 nicht erkannt: {snippet!r} -> {anon_text!r}"
        assert tier == 'C'


# ── anonymize_output ──────────────────────────────────────────────────────────

def test_anonymize_output_reverse_lookup():
    """Req-8: anonymize_output() ersetzt bekannte Namen aus Cache durch Tokens."""
    from services.anonymization import AnrufAnonymisierer, anonymize_output
    cache = AnrufAnonymisierer()
    # Bekannte Entitaet im Cache registrieren
    cache.get_or_assign_token('Jacob Mueller', 'PERSON')
    # Claude-Output mit dem bekannten Namen
    output = anonymize_output("Jacob Mueller zoegert beim Preis", cache)
    assert 'Jacob Mueller' not in output, f"Name noch im Output: {output!r}"
    assert '[PERSON_A]' in output, f"Token erwartet: {output!r}"


def test_anonymize_output_longer_key_first():
    """anonymize_output() ersetzt laengere Keys zuerst (Partial-Match-Schutz)."""
    from services.anonymization import AnrufAnonymisierer, anonymize_output
    cache = AnrufAnonymisierer()
    cache.get_or_assign_token('Dr. Mueller', 'PERSON')
    cache.get_or_assign_token('Mueller', 'PERSON')
    output = anonymize_output("Dr. Mueller hat angerufen", cache)
    # [PERSON_A] sollte 'Dr. Mueller' ersetzen (laengerer Match zuerst)
    assert 'Dr. Mueller' not in output
    assert 'Mueller' not in output  # kein Rest-'Mueller'


def test_anonymize_output_none_cache():
    """anonymize_output() mit cache=None gibt unveraenderten Text zurueck."""
    from services.anonymization import anonymize_output
    text = "Herr Mueller hat angerufen"
    result = anonymize_output(text, None)
    assert result == text  # unveraendert wenn kein Cache


# ── register_briefing_pii ─────────────────────────────────────────────────────

def test_register_briefing_pii_person():
    """Req-6: Bekannter Name aus Briefing -> konsistenter Token in anonymize()."""
    from services.anonymization import AnrufAnonymisierer, anonymize, register_briefing_pii
    cache = AnrufAnonymisierer()
    register_briefing_pii({"personen": ["Jacob Mueller"]}, cache)
    # Jacob Mueller muss jetzt im Cache-Mapping sein
    assert 'Jacob Mueller' in cache.mapping, f"Jacob Mueller nicht im Cache: {cache.mapping}"
    # Token soll [PERSON_A] sein (Briefing-PII bekommt ersten Buchstaben)
    assert cache.mapping['Jacob Mueller'] == '[PERSON_A]', \
        f"Erwartet [PERSON_A], erhalten: {cache.mapping['Jacob Mueller']!r}"


def test_register_briefing_pii_firma():
    """Req-6: Firmennamen aus Briefing werden im Cache registriert."""
    from services.anonymization import AnrufAnonymisierer, anonymize_output, register_briefing_pii
    cache = AnrufAnonymisierer()
    register_briefing_pii({"firmenname": "Commerzbank AG"}, cache)
    assert "Commerzbank AG" in cache.mapping, f"Firma nicht im Cache: {cache.mapping}"
    output = anonymize_output("Die Commerzbank AG hat angerufen", cache)
    assert 'Commerzbank AG' not in output


def test_register_briefing_pii_empty():
    """Req-6: register_briefing_pii() mit leerem Dict raised keine Exception."""
    from services.anonymization import AnrufAnonymisierer, register_briefing_pii
    cache = AnrufAnonymisierer()
    register_briefing_pii({}, cache)  # kein Fehler
    register_briefing_pii(None, cache)  # kein Fehler auch bei None


# ── Fallback-Architektur (D-08) ───────────────────────────────────────────────

def test_pipeline_unavailable_raises():
    """D-08 Kat. A: is_pipeline_healthy=False -> AnonymizationPipelineUnavailable raised."""
    import services.anonymization as anon_module
    from services.anonymization import AnrufAnonymisierer, anonymize, AnonymizationPipelineUnavailable
    original = anon_module.is_pipeline_healthy
    try:
        anon_module.is_pipeline_healthy = False
        cache = AnrufAnonymisierer()
        with pytest.raises(AnonymizationPipelineUnavailable):
            anonymize("Normaler Text", cache)
    finally:
        anon_module.is_pipeline_healthy = original  # Restore


def test_empty_text_returns_empty_tier_a():
    """Edge-Case: leerer Text -> ('', 'A')."""
    from services.anonymization import AnrufAnonymisierer, anonymize
    cache = AnrufAnonymisierer()
    result = anonymize("", cache)
    assert result == ('', 'A'), f"Erwartet ('', 'A'), erhalten: {result!r}"
    result2 = anonymize("   ", cache)
    assert result2 == ('', 'A'), f"Leerzeichen-Text: {result2!r}"


# ── Art-9 False-Negative Gate (Phasen-Akzeptanz-Test) ────────────────────────

def test_art9_false_negative_30_snippets():
    """
    Phasen-Gate: 30 Art-9-Snippets, 100% muessen ('[ART9_REDACTED]', 'C') zurueckgeben.
    0% False-Negative Pflicht (CONTEXT.md D-04, Acceptance Gates).
    6 Kategorien, >= 5 Snippets pro Kategorie.
    CLAUDE.md: Runtime-Behavior-Test (anonymize() aufrufen, Rueckgabewert pruefen — kein Source-Presence).
    """
    from services.anonymization import AnrufAnonymisierer, anonymize

    # 5 Snippets pro Kategorie, 6 Kategorien = 30 Snippets gesamt
    ART9_TEST_SNIPPETS = [
        # Kategorie: Gesundheit (5 Snippets)
        ("Gesundheit", "Ich bin nach der Chemo wieder voll arbeitsfaehig"),
        ("Gesundheit", "Er hat Diabetes Typ 2 und braucht Insulin taeglich"),
        ("Gesundheit", "Sie ist seit dem Burnout im vergangenen Jahr krankgeschrieben"),
        ("Gesundheit", "Er liegt gerade im Krankenhaus wegen einer Herzrhythmus-Stoerung"),
        ("Gesundheit", "Die Allergie macht ihr das Leben schwer, sie nimmt Medikamente"),

        # Kategorie: Religion (5 Snippets)
        ("Religion", "Er ist streng katholisch und geht jeden Sonntag zur Kirche"),
        ("Religion", "Sie ist muslimisch und haelt das Ramadan-Fasten sehr konsequent"),
        ("Religion", "Der Kunde ist juedisch und beachtet die juedischen Feiertage"),
        ("Religion", "Er ist evangelisch erzogen und war lange Kirchenmitglied"),
        ("Religion", "Sie ist buddhistisch und meditiert taeglich"),

        # Kategorie: Gewerkschaft (5 Snippets)
        ("Gewerkschaft", "Er ist aktives Gewerkschaftsmitglied bei der IG Metall"),
        ("Gewerkschaft", "Sie sitzt im Betriebsrat des Unternehmens"),
        ("Gewerkschaft", "Der Betrieb war am Streik beteiligt letzte Woche"),
        ("Gewerkschaft", "Er verhandelt gerade den Tarifvertrag fuer seine Kollegen"),
        ("Gewerkschaft", "Die Gewerkschaft Verdi hat ihn zu Tarifverhandlungen eingeladen"),

        # Kategorie: Sexuelle_Orientierung (5 Snippets)
        ("Sexuelle_Orientierung", "Er hat uns erwaehnt dass er schwul ist und mit seinem Partner zusammenlebt"),
        ("Sexuelle_Orientierung", "Sie ist lesbisch und sehr aktiv in der LGBTQ-Community"),
        ("Sexuelle_Orientierung", "Der Kunde ist bisexuell und engagiert sich fuer queere Rechte"),
        ("Sexuelle_Orientierung", "Er hat sein Coming out letztes Jahr gehabt"),
        ("Sexuelle_Orientierung", "Sie lebt in einer gleichgeschlechtlichen Partnerschaft"),

        # Kategorie: Politische_Ueberzeugung (5 Snippets)
        ("Politische_Ueberzeugung", "Er ist ueberzeugter CDU-Waehler und sehr konservativ eingestellt"),
        ("Politische_Ueberzeugung", "Sie ist Parteimitglied der SPD und engagiert sich kommunalpolitisch"),
        ("Politische_Ueberzeugung", "Der Kunde waehlte die Gruenen und ist sehr oekologisch orientiert"),
        ("Politische_Ueberzeugung", "Er hat eine sehr linke politische Ueberzeugung, war frueher bei der Linken"),
        ("Politische_Ueberzeugung", "Sie ist AfD-Waehler laut eigenem Bekunden"),

        # Kategorie: Ethnische_Herkunft (5 Snippets)
        ("Ethnische_Herkunft", "Er hat einen Migrationshintergrund, kam als Kind aus der Tuerkei"),
        ("Ethnische_Herkunft", "Sie ist Asylbewerberin und wartet noch auf ihren Aufenthaltstitel"),
        ("Ethnische_Herkunft", "Der Kunde ist Migrant der zweiten Generation mit arabischen Wurzeln"),
        ("Ethnische_Herkunft", "Er gehoert einer ethnischen Minderheit an und berichtet von Diskriminierung"),
        ("Ethnische_Herkunft", "Sie hat die Einbuergerung beantragt nach 10 Jahren in Deutschland"),
    ]

    assert len(ART9_TEST_SNIPPETS) == 30, f"Muss 30 Snippets haben, hat: {len(ART9_TEST_SNIPPETS)}"

    # Kategorien pruefen: mindestens 5 pro Kategorie
    from collections import Counter
    kategorie_counts = Counter(k for k, _ in ART9_TEST_SNIPPETS)
    for kat, count in kategorie_counts.items():
        assert count >= 5, f"Kategorie {kat!r} hat nur {count} Snippets (mind. 5 noetig)"

    # Runtime-Behavior-Test: anonymize() aufrufen und Return-Wert pruefen
    failures = []
    for kat, snippet in ART9_TEST_SNIPPETS:
        cache = AnrufAnonymisierer()  # Frischer Cache pro Snippet
        result = anonymize(snippet, cache)
        anon_text, tier = result
        if anon_text != '[ART9_REDACTED]' or tier != 'C':
            failures.append(
                f"Kategorie={kat!r}: Snippet={snippet[:60]!r} -> got ({anon_text!r}, {tier!r})"
            )

    assert len(failures) == 0, (
        f"Art-9 False-Negative: {len(failures)}/30 Snippets nicht erkannt:\n"
        + "\n".join(failures)
    )
