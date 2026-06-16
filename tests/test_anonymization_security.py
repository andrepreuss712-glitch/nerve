"""
Sicherheits-Test: Re-Identifikations-Versuch auf 50 deutschen Mitschrift-Snippets (Phase 08.23.2.B Req-11).

Ausfuehren:
  ANTHROPIC_API_KEY=<key> pytest tests/test_anonymization_security.py -m security -v

WICHTIG: Dieser Test macht echte Claude-API-Calls (ca. 50 Requests).
Wird in CI-Umgebung geskippt (kein ANTHROPIC_API_KEY).
Manuell vor Phase-Abschluss durch Andre ausfuehren.

Acceptance-Kriterium: Re-ID-Rate < 5% (max 2 von 50 Snippets).
"""
import os
import pytest
from services.anonymization import AnrufAnonymisierer, anonymize


# 50 Deutsche B2B-Vertriebs-Mitschrift-Snippets mit echten PII
# (simuliert — repraesentativ fuer NERVE-Einsatz-Szenario)
SNIPPETS = [
    "Thomas Mueller von der Commerzbank Frankfurt hat wegen des Angebots angerufen",
    "Frau Schneider von Siemens AG moechte den Vertrag bis Freitag ueberpruefen",
    "Herr Dr. Weber, Geschaeftsfuehrer bei Bosch GmbH, lehnt den Preis ab",
    "Maria Schmidt aus Hamburg, Einkaufsleiterin bei ThyssenKrupp, braucht mehr Zeit",
    "Klaus Fischer von BMW AG sagt, das Budget sei bereits ausgeschoepft",
    "Petra Braun von der Deutschen Bank fragt nach einem Rabatt von 20 Prozent",
    "Michael Wagner, Vertriebsleiter bei SAP, ist skeptisch gegenueber der Loesung",
    "Sabine Hoffmann vom RWE Konzern hat Bedenken wegen der Implementierungszeit",
    "Stefan Meyer von Lufthansa sagt, die IT-Abteilung muesse noch zustimmen",
    "Andrea Wolf von Volkswagen AG moechte erst intern besprechen",
    "Juergen Bauer, CEO von Phoenix Contact, will einen Piloten durchfuehren",
    "Christine Richter von BASF SE bittet um ein schriftliches Angebot",
    "Frank Keller von der Allianz sagt, das sei nicht im diesjaehrigen Budget",
    "Monika Zimmermann von Henkel AG fragt nach Referenzkunden in der Branche",
    "Rainer Schulze von Daimler-Benz moechte die Entscheidung verschieben",
    "Diana Krause von der Telekom benoetigt eine technische Zertifizierung",
    "Bernd Hartmann von MAN SE sagt, der Preis sei zu hoch fuer die Qualitaet",
    "Silvia Lange von Bayer AG will erst die Testphase abwarten",
    "Markus Seidel von Continental AG ist interessiert aber hat keine Entscheidung",
    "Inge Sauer von Fresenius bittet um ein zweites Gespraech mit dem Vorstand",
    "Heinz Braun von der DHL Express GmbH fragt nach Support-Level-Agreements",
    "Susanne Koch von ALDI SuedEinkauf braucht Genehmigung vom Mutterkonzern",
    "Herbert Mueller von Lidl Stiftung fragt nach Datenschutz-Zertifizierung",
    "Gabi Vogel von Merck KGaA sagt, die ROI-Rechnung ist noch nicht klar",
    "Otto Kaiser von der Zara Deutschland GmbH moechte einen Kostenvergleich",
    "Ingrid Frank von Porsche AG lehnt das Angebot wegen interner Vorgaben ab",
    "Werner Huber von Munich Re fragt nach einer flexibleren Preisgestaltung",
    "Claudia Brandt von Infineon Technologies will erst ein POC sehen",
    "Dieter Fuchs von der Wacker Chemie AG hat Bedenken bei der Datenmigration",
    "Hildegard Simon von Sartorius AG fragt nach einem Partnermodell",
    "Roland Metz von Evonik Industries sagt, das sei strategisch nicht passend",
    "Ursula Beck von Osram Licht AG benoetigt interne Freigabe vom Compliance-Team",
    "Ewald Gross von Krones AG ist interessiert aber wartet auf Budgetfreigabe",
    "Renate Neumann von Draeger SE fragt ob es eine Testversion gibt",
    "Horst Zimmermann von Stabilus GmbH fragt nach einer Demo-Praesentation",
    "Karin Richter von Heidelberger Druckmaschinen moechte Referenzgespraeche",
    "Guenter Schreiber von Fielmann AG sagt, das Timing sei schlecht",
    "Hannelore Kraus von Trigon Chemie fragt nach der Skalierbarkeit der Loesung",
    "Achim Vogt von Rademacher GmbH benoetigt technische Zertifizierung ISO 27001",
    "Lieselotte Becker von Windreich AG fragt nach dem Unterschied zum Wettbewerb",
    "Norbert Haase von ProDV Software sagt, die Loesung sei zu komplex fuer das Team",
    "Beate Ritter von Agilent Technologies will erst einen Budgetplan erstellen",
    "Burkhard Kuhn von Knoll GmbH hat bereits eine aehnliche Loesung im Einsatz",
    "Christoph Seiler von Hueck Folien bittet um schriftliche Garantien",
    "Dorothea Schaefer von Weidmueller Interface fragt nach einer Testlizenz",
    "Eckhard Schuster von Koenig & Bauer AG sagt, die IT-Kapazitaeten fehlen",
    "Friederike Gross von Tetra Pak GmbH moechte mehr Referenzen aus der Branche",
    "Gottfried Winter von Hella KGaA braucht noch 4 Wochen bis zur Entscheidung",
    "Hannelore Bauer von Sick AG fragt nach der Datensicherheit bei Cloud-Nutzung",
    "Ingo Schroeder von Schuller GmbH sagt, das Projekt sei fuer naechstes Jahr geplant",
]

assert len(SNIPPETS) == 50, f"Genau 50 Snippets benoetigt, erhalten: {len(SNIPPETS)}"


# Phase 08.23.2.PGTEST.GREEN Plan 05: live-Marker (Re-ID-RATE-MESSUNG braucht das ECHTE NER-Modell +
# Korpus -> kann im Gate nicht deterministisch laufen; aus dem Gate via -m "not live" exkludiert).
# Das ist KEIN Maskieren der Anonymisierungs-LOGIK: die deterministische should_persist/Filter/Hash-Logik
# laeuft IM Gate (test_anonymizer_worker, grün). reid_rate ist eine statistische Qualitaets-Messung.
@pytest.mark.live
@pytest.mark.security
@pytest.mark.skipif(
    not os.environ.get('ANTHROPIC_API_KEY'),
    reason="Re-ID-Test erfordert ANTHROPIC_API_KEY (nur manuell ausfuehren: ANTHROPIC_API_KEY=<key> pytest -m security)"
)
def test_reid_rate_below_5_percent():
    """
    Req-11: Re-Identifikations-Rate < 5% (max 2 von 50).

    Ablauf:
    1. Jeden Snippet durch anonymize() jagen
    2. Anonymisierten Output an Claude schicken mit Re-ID-Anfrage
    3. Antwort auf Treffer pruefen
    4. Treffer-Rate berechnen und assertieren

    Ausfuehren: ANTHROPIC_API_KEY=<key> pytest tests/test_anonymization_security.py -m security -v
    """
    import anthropic

    cache = AnrufAnonymisierer()
    anon_snippets = []

    # Schritt 1: Alle 50 Snippets anonymisieren
    for snippet in SNIPPETS:
        result = anonymize(snippet, cache)
        anon_text, tier = result
        anon_snippets.append(anon_text)

    # Schritt 2+3: Claude Re-ID-Versuch
    client = anthropic.Anthropic()
    hits = 0
    hit_details = []

    for orig, anon in zip(SNIPPETS, anon_snippets):
        if anon == '[ART9_REDACTED]':
            # Art-9-Treffer: Snippet verworfen — kein Re-ID-Risiko
            continue

        resp = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=150,
            messages=[{
                'role': 'user',
                'content': (
                    f'Du siehst einen anonymisierten Text aus einem Vertriebs-Gespraech: '
                    f'"{anon}"\n\n'
                    f'Versuche die echte Person oder Firma dahinter zu benennen. '
                    f'Antworte nur mit: Name/Firma oder "Nicht erkennbar".'
                )
            }]
        )
        answer = resp.content[0].text.strip().lower()

        # Pruefe ob Antwort einen originalen Namen enthaelt (case-insensitive)
        original_words = set(
            w.lower() for w in orig.split()
            if len(w) > 3 and w[0].isupper()  # Nur Worte die wie Namen aussehen
        )
        is_hit = any(word in answer for word in original_words if word not in ('gmbh', 'gruppe', 'einer', 'nicht'))

        if is_hit:
            hits += 1
            hit_details.append(f"TREFFER: '{orig[:50]}...' -> '{answer[:50]}'")
            print(f"[Security] RE-ID HIT #{hits}: '{orig[:60]}' -> '{answer[:60]}'")

    hit_rate = hits / len(SNIPPETS)
    print(f"\n[Security] Re-ID-Rate: {hit_rate:.1%} ({hits}/{len(SNIPPETS)} Treffer)")
    if hit_details:
        print("[Security] Treffer-Details:")
        for d in hit_details:
            print(f"  {d}")

    assert hit_rate < 0.05, (
        f"Re-ID-Rate {hit_rate:.1%} >= 5% — SICHERHEITSTEST FEHLGESCHLAGEN!\n"
        f"Treffer: {hits}/{len(SNIPPETS)}\n"
        f"Details: {hit_details}"
    )


def test_snippets_count():
    """Smoke-Test: Sicherstellt dass 50 Snippets definiert sind (kein API-Call)."""
    assert len(SNIPPETS) == 50
    # Jeder Snippet enthaelt einen Namen (Verifikation der Snippet-Qualitaet)
    snippets_with_capitalized_words = [
        s for s in SNIPPETS
        if any(w[0].isupper() for w in s.split() if len(w) > 2)
    ]
    assert len(snippets_with_capitalized_words) == 50, "Alle Snippets sollen Namen enthalten"
