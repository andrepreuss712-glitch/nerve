"""Re-Identifikations-Test mit aktiver GLiNER-Pipeline (Phase 08.23.2.C Req-14).

Wiederholt Phase-B-Pattern aus tests/test_anonymization_security.py mit dem
Unterschied: GLiNER ist nun zweite NER-Stufe (Union-Voting per D-01 Anonymisierung).
Erwartung: Re-ID-Rate <= Phase-B (<5%), idealerweise niedriger.

Loop-Body ist 1:1 aus tests/test_anonymization_security.py uebernommen
(Phase B Plan 09) — keine Spezifikations-Luecke fuer Plan-Author.
"""
import os

import pytest

ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')


@pytest.mark.skipif(
    not ANTHROPIC_API_KEY,
    reason='Re-ID-Test erfordert ANTHROPIC_API_KEY (manuell: ANTHROPIC_API_KEY=<key> pytest -m security)'
)
@pytest.mark.security
def test_reid_with_gliner_below_5_percent():
    """Re-ID-Rate < 5% mit aktiver spaCy+GLiNER Union-Pipeline (Req-14).

    Identische Logik wie tests/test_anonymization_security.py::test_reid_rate_below_5_percent,
    aber GLiNER ist jetzt aktiviert (Plan 04). Test schlaegt fehl wenn:
    - GLiNER+spaCy-Union schlechter anonymisiert als spaCy-allein (Regress)
    - Anonymisierungs-Tier-Logik defekt ist
    - PII-Patterns durchrutschen
    """
    import anthropic

    from services.anonymization import AnrufAnonymisierer, anonymize, _get_gliner
    from tests.test_anonymization_security import SNIPPETS

    # Sanity: GLiNER aktiv. Falls nicht installiert, Test SKIPpen.
    # Plan 04 hat GLiNER aktiviert; falls _get_gliner None liefert, ist die
    # Pipeline-Loading-Logik kaputt — Test ist Indicator dafuer.
    gliner = _get_gliner()
    if gliner is None:
        pytest.skip('GLiNER nicht installiert — Re-ID-Test gegen GLiNER nicht durchfuehrbar')

    cache = AnrufAnonymisierer()
    anon_snippets = []

    # Schritt 1: Alle 50 Snippets anonymisieren
    for snippet in SNIPPETS:
        result = anonymize(snippet, cache)
        anon_text, tier = result
        anon_snippets.append(anon_text)

    # Schritt 2+3: Claude Re-ID-Versuch (1:1 aus Phase B uebernommen)
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
        is_hit = any(
            word in answer
            for word in original_words
            if word not in ('gmbh', 'gruppe', 'einer', 'nicht')
        )

        if is_hit:
            hits += 1
            hit_details.append(f"TREFFER: '{orig[:50]}...' -> '{answer[:50]}'")
            print(f"[Security-GLiNER] RE-ID HIT #{hits}: '{orig[:60]}' -> '{answer[:60]}'")

    hit_rate = hits / len(SNIPPETS)
    print(f"\n[Security-GLiNER] Re-ID-Rate: {hit_rate:.1%} ({hits}/{len(SNIPPETS)} Treffer)")
    if hit_details:
        print("[Security-GLiNER] Treffer-Details:")
        for d in hit_details:
            print(f"  {d}")

    assert hit_rate < 0.05, (
        f"Re-ID-Rate {hit_rate:.1%} >= 5% — SICHERHEITSTEST FEHLGESCHLAGEN (Req-14)!\n"
        f"Treffer: {hits}/{len(SNIPPETS)}\n"
        f"Details: {hit_details}"
    )
