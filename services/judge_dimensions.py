# -*- coding: utf-8 -*-
"""Feste Dimensions-Liste fuer den LLM-Verhaltens-Bewerter (Beobachtung statt Note).

Erweitern = ein Listen-Eintrag. KEINE Gewichte/Scores (Urteil von Rechnung getrennt,
Soll-Verhalten §6 / Entscheidung.md). Reine Daten + eine Versions-Konstante + Hilfsfunktion
fuer den Prompt-Bau. KEIN LLM, KEIN DB-Zugriff, KEINE Gewichte, KEINE Score-Rechnung
(Leitsatz 2 / Punkt 27).

Phase: 08.23.2.TAXO2.HANDLING-TIMING Plan 02
"""

# DIMENSIONS_VERSION = 2
# Bump 1 → 2 (Cross-AI-Finding 1, 2026-06-28): Dimension 1 wurde von der Technik
# fragen_offen_geschlossen auf das Ziel bedarfs_ermittlung umgedeutet — eine semantische
# Vertragsaenderung. Alte rubric_score-Zeilen mit score_schema_version=1 bleiben damit
# von Version-2-Zeilen unterscheidbar (Vergleichbarkeit ueber die Zeit).
DIMENSIONS_VERSION = 2

# Finale 4 Dimensionen (festgezurrt, Soll-Verhalten §6 + Entscheidung.md + Cross-AI-Finding 1).
# Je Dimension: key ASCII-Identifier (DB/Prompt-Anker), name (Anzeige, Umlaute OK),
# definition (Ein Satz, Umlaute OK), bars (schwach/ok/stark mit je einem Beispiel).
DIMENSIONS = [
    {
        'key': 'bedarfs_ermittlung',
        'name': 'Bedarfsermittlung',
        'definition': (
            'Bringt der Berater den Kunden zum Reden und grabt dessen echten Bedarf/Schmerz aus?'
        ),
        'bars': {
            'schwach': (
                'Fast nur Ja/Nein-Fragen, kaum Bedarf sichtbar; Kunde kommt kaum zu Wort. '
                'Beispiel: "Hätten Sie nicht auch gern mehr Sicherheit?"'
            ),
            'ok': (
                'Teils offene Fragen, aber oft wieder geschlossen; Bedarf nur ansatzweise erkennbar. '
                'Beispiel: "Wie lösen Sie das heute? … Also brauchen Sie X, oder?"'
            ),
            'stark': (
                'Offene Fragen, echter Bedarf/Schmerz herausgearbeitet; der Kunde redet und öffnet sich. '
                'Beispiel: "Was wäre für Sie der größte Hebel?"'
            ),
        },
        # Cross-AI-Finding 1 (Plan 02): Dimension 1 ist das ZIEL bedarfs_ermittlung, NICHT die
        # Technik. Das offene-vs-Ja/Nein-Fragen-Signal bleibt als konkretes Coaching-Signal im
        # BARS-Text (schwach = fast nur Ja/Nein-Fragen, stark = offene Fragen) — es ist KEINE
        # eigene Technik-Dimension mehr.
    },
    {
        'key': 'gespraechs_eroeffnung',
        'name': 'Gesprächseröffnung',
        'definition': (
            'Schafft der Berater einen klaren, erklärenden Einstieg, der den Kunden neugierig '
            'macht und das Gespräch gut verankert?'
        ),
        'bars': {
            'schwach': (
                'Kein erklärbarer Einstieg, sofort ins Angebot oder ins Produkt gesprungen. '
                'Beispiel: "Ich rufe wegen unserem neuen Produkt an…"'
            ),
            'ok': (
                'Eröffnung vorhanden, aber wenig prägnant oder schwer zu verankern. '
                'Beispiel: "Wir helfen Unternehmen wie Ihrem, effizienter zu werden…"'
            ),
            'stark': (
                'Klarer, erklärbarerer Nutzen-Opener; Kunde weiß sofort warum der Anruf relevant ist. '
                'Beispiel: "Ich rufe an, weil Unternehmen Ihrer Größe bei X typischerweise Y verlieren — '
                'das kenne ich von Ihrem Mitbewerber Z. Stimmt das bei Ihnen auch?"'
            ),
        },
    },
    {
        'key': 'einwand_behandlung',
        'name': 'Einwandbehandlung',
        'definition': (
            'Nimmt der Berater Einwände und Vorwände des Kunden ernst, hinterfragt sie gezielt '
            'und überführt sie in ein konstruktives Gespräch statt sie wegzubügeln?'
        ),
        'bars': {
            'schwach': (
                'Einwand sofort mit Gegenargument überrollt oder ignoriert; kein Zuhören. '
                'Beispiel: "Ja aber unser Produkt ist wirklich das Beste am Markt…"'
            ),
            'ok': (
                'Einwand angenommen, aber nur oberflächlich behandelt; kein wirkliches Hinterfragen. '
                'Beispiel: "Das verstehe ich, aber lassen Sie mich erklären warum das trotzdem sinnvoll ist."'
            ),
            'stark': (
                'Einwand gelabelt, mit einer offenen Frage isoliert und aufgelöst; Kunde fühlt sich gehört. '
                'Beispiel: "Das höre ich öfter — darf ich kurz fragen, was konkret bisher nicht gepasst hat?"'
            ),
        },
    },
    {
        'key': 'gespraechsfuehrung',
        'name': 'Gesprächsführung',
        'definition': (
            'Steuert der Berater das Gespräch aktiv, hält den roten Faden und wahrt eine '
            'ausgewogene Gesprächsdynamik ohne aufzudrängen?'
        ),
        'bars': {
            'schwach': (
                'Berater redet zu viel (Monolog), verliert den Faden oder drängt nach mehrfacher '
                'klarer Ablehnung weiter auf — das ist nicht Verkauf, sondern Belästigung. '
                'Beispiel: Klient sagt dreimal "Nein danke", Berater pitcht weiter.'
                # Hard-Cap-Hinweis (Report-Ergänzung 4): Weiterdrücken nach mehrfacher klarer
                # Ablehnung deckelt diese Dimension auf hoechstens schwach.
                # Das binaere Compliance-Flag compliance_violation (Cross-AI-Finding 2) sitzt
                # SEPARAT in observations_jsonb (Plan 03) — hier ist es nur Coaching-Text.
            ),
            'ok': (
                'Redeanteil und Steuerung teils unausgewogen, aber Berater gibt dem Kunden Raum. '
                'Ziel Kaltakquise: Berater ca. 55%, Kunde ca. 45% Redeanteil (Gong Cold-Call-Norm). '
                'Beispiel: Berater erklärt länger als nötig, fragt dann aber nach.'
            ),
            'stark': (
                'Gespräch gut gesteuert, Berater hält roten Faden, gibt Kunden genug Raum. '
                'Kaltakquise: ~55% Berater / ~45% Kunde (Gong Cold-Call-Norm). '
                'Berater stoppt rechtzeitig wenn Kunde klar ablehnt. '
                'Beispiel: Berater leitet gezielt von Bedarf zu konkretem Nutzen über, fragt nochmal nach.'
            ),
        },
    },
]


def dimensions_for_prompt() -> str:
    """Rendert die Dimensions-Liste als Klartext-Block fuer den Judge-Prompt.

    Gibt Name + Definition + BARS schwach/ok/stark zurueck (Pflicht-Technik:
    BARS als Klartext im Prompt, Entscheidung.md). Rein String-Bau, kein LLM.
    Plan 03 ruft diese Funktion beim Prompt-Bau auf.
    """
    lines = []
    for i, dim in enumerate(DIMENSIONS, start=1):
        lines.append(f"--- Dimension {i}: {dim['name']} ---")
        lines.append(f"Definition: {dim['definition']}")
        lines.append("Ausprägungen (BARS):")
        lines.append(f"  schwach: {dim['bars']['schwach']}")
        lines.append(f"  ok:      {dim['bars']['ok']}")
        lines.append(f"  stark:   {dim['bars']['stark']}")
        lines.append("")
    return "\n".join(lines).strip()
