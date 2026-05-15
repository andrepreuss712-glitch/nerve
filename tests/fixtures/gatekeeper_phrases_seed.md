# Gatekeeper-Phrases Seed-Entwurf (Phase 08.23.2.C)

**Andre-Gate:** Bitte vor Execute-Start prüfen und ggf. editieren.
Plan-Author hat aus `Nerve-Vault/03 Planung/gatekeeper detection.md` (Abschnitte B.6, B.7, Bonus-Block) extrahiert.

**Template-Variablen:** {branche}, {detail}, {vorname}, {nachname} — werden im PiP aus Briefing-Daten + classify_contact()-Output gefüllt.

---

## Button 1: "Verbündeten-Bitte"
*Source: Stephan Heinrich + Ulrike Knauer — "Sekretär als Verbündeten gewinnen"*

Varianten (3):

1. "{vorname}, dürfte ich Sie um Ihre Einschätzung bitten — wer wäre bei Ihnen für {branche} der richtige Ansprechpartner?"
2. "Ich brauche kurz Ihre Hilfe — können Sie mir sagen, wer bei Ihnen für {branche} zuständig ist?"
3. "Sie sind gerade die einzige Person, die mir helfen kann — wer wäre bei Ihnen verantwortlich für {detail}?"

**Quellen-Hinweis:**
- Stephan Heinrich: „Ich brauche Ihre Hilfe, können Sie mir bitte sagen, wer für den Bereich [Thema] zuständig ist?"
- Ulrike Knauer: Variante der einfachen direkten Bitte um Namen/Weitervermittlung.
- Voss-Stil ergänzend: „Sie sind gerade die einzige Person..." als Rapport-Opener.

---

## Button 2: "Insider-Antwort"
*Source: Tim Taxis + Eduard Klein — "Klingt wie Insider, nicht wie Sales"*

Varianten (3):

1. "Es geht um {detail} — könnten Sie mich bitte mit der zuständigen Person verbinden?"
2. "Sie wollen ja sicherlich wissen, worum es geht, bevor Sie mich mit {nachname} verbinden — es geht um {detail}."
3. "Konkret: {detail}. Wer ist bei Ihnen dafür der richtige Ansprechpartner?"

**Quellen-Hinweis:**
- Tim Taxis: „Guten Morgen Frau Vorzimmer, mein Name ist Tim Taxis. Sie wollen ja sicherlich wissen, worum es geht, bevor Sie mich mit [Vorname Nachname] verbinden, gell!" — dann: „Es geht um [Branchen-Begriff], speziell [Detail]."
- Eduard Klein: „Es geht um die SX-Baureihe, speziell den neuen Prototypen. Bitte stellen Sie mich durch." — sehr kurz, sehr selbstbewusst.

---

## Button 3: "Voss-Label"
*Source: Chris Voss — "Never Split the Difference", Tactical Empathy / Labeling-Technik*

Varianten (2):

1. "Es klingt so, als ob Sie das tagtäglich filtern müssen — was wäre der einfachste Weg, mich kurz durchzustellen?"
2. "Es scheint, als hätten Sie viele solcher Anfragen — was bräuchten Sie, damit Sie sich sicher fühlen mich weiterzuleiten?"

**Quellen-Hinweis:**
- Chris Voss „Never Split the Difference" S. 50-70: „It sounds like..." / „Es klingt, als..." als Labeling-Technik.
- Übertragung auf DACH aus Vault: „Es klingt, als würden Sie viele solche Anrufe bekommen — und ich kann verstehen, dass Sie da streng filtern müssen."
- Vault-Bonus-Block: Voss-Stil bei „Kein Interesse"-Antwort des Sekretärs: Mirror + Label + Calibrated Question.

---

## Button 4: "Vornamen-Pause"
*Source: Martin Limbeck — Vornamenspause, Pattern-Interrupt*

Varianten (2):

1. "{vorname} ... (Pause) ... ich brauche genau zwei Minuten."
2. "{vorname} — kurz: {detail}. Reicht das für Ihre Einschätzung?"

**Quellen-Hinweis:**
- Martin Limbeck: „Schönen guten Tag. Hier ist Martin Limbeck. *(kleine Pause)* DER Martin Limbeck. *(kleine Pause)* Sagen Sie mal, ist denn der Herbert … *(kleine Pause)* … der Herbert Meier im Hause?"
- Begründung Limbeck: Vornamen suggerieren Vertrautheit, Pause bricht das Automatik-Filter-Pattern der Sekretärin.
- Vault-Abschnitt B.7, Limbeck-Methode: „Im Hause" statt „zu sprechen" — letzteres signalisiert sofort einen Wunsch und aktiviert den Filter.

---

**Insert-Format für Alembic 0003 (zur Information, nicht für André's Review):**
Pro Variante eine Row in `phrases` mit: text, mode='gatekeeper', user_id=1 (Admin-MVP-Lösung per RESEARCH.md A7), objection_type='gatekeeper_button_<N>', quality_tier='A'.

**Offen / TODO André prüfen:**
- Button 4 Variante 2: Formulierung „Reicht das für Ihre Einschätzung?" klingt möglicherweise zu direkt — bitte prüfen ob das für DACH-Tonalität passt oder ob eine weichere Variante besser wäre.
- Anzahl der Varianten pro Button: aktuell 3 / 3 / 2 / 2. Falls du mehr Varianten willst (z.B. 3 pro Button) — sag Bescheid, können aus B.6/B.7 weitere extrahiert werden.
