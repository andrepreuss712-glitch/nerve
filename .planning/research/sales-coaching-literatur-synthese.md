# Sales-Coaching-Literatur-Synthese

**Stand:** 2026-04-27
**Phase:** 08.18 — Block N Phase B
**Zweck:** Thematische Synthese aller 13 Sales-Literatur-Autoren (8 EN + 5 DE) als Input für Phase 08.19 (Pydantic-Schema-Redesign) und Phase 08.20 (Pipeline-Re-Wire)

---

## Methodik

**Autoren-Auswahl:** 13 Autoren/Systeme (8 EN-Klassiker + 5 DE/DACH-Spezialisten). Ein Autor wurde bewusst ausgeschlossen (Begründung in 08.18-CONTEXT.md D-02).

**Analyse-Dimensionen je Autor:**
1. **Profil-Inputs** — Welche Vorinformationen braucht das System?
2. **Frame-Struktur** — Welche Gesprächs-Architektur wird empfohlen?
3. **Einwand-Muster** — Welche Einwand-Kategorien und Behandlungs-Logiken?
4. **No-Gos** — Was nie sagen, was nie tun?

**Darstellungsform:** Thematisch quervergleichend (nicht per-Autor-Kapitel) — nach Entscheidung D-03. Tabellen wo Vergleich, Bullets wo Liste, Fließtext wo Nuancierung nötig.

**NERVE-Bezug:** NERVE nutzt aktuell nur 10/48 Profil-Felder im EWB-Prompt (21% Integration). Sektion E markiert explizit: ✅ = bereits in NERVE, ❌ = noch nicht integriert.

---

## Autoren-Übersicht

| # | Autor/System | Hauptwerk | Herkunft | Kern-Claim |
|---|---|---|---|---|
| 1 | Neil Rackham | SPIN Selling (1988) | UK/USA | Discovery vor Lösung: Situation → Problem → Implication → Need-Payoff-Fragen erzeugen Kaufdruck |
| 2 | Matthew Dixon + Brent Adamson | The Challenger Sale (2011) | USA | Top-Performer lehren, fordern heraus, kontrollieren — Relationship Seller sind die schwächste Gruppe |
| 3 | David Sandler | The Sandler Rules (1999) | USA | Pain-Budget-Decision-Dreiklang + Upfront-Contracts verhindern Zeit-Verschwendung |
| 4 | Jordan Belfort | Way of the Wolf (2017) | USA | Straight-Line-Rapport-to-Close: Tonalität ist Überzeugung, Certainty-Stack bei Einwänden |
| 5 | Julie Thomas / ValueSelling Associates | Value Selling Framework | USA | Business Value schlägt Features: ROI-Calc und differenzierter Nutzen-Nachweis |
| 6 | Aaron Ross | Predictable Revenue (2011) | USA | Spezialisierte Rollen (SDR/AE), systematischer Cold-Outbound, ICP-Definition als Fundament |
| 7 | Jeffrey Gitomer | Little Red Book of Selling (2004) | USA | Attitude + Value-First: Kaufmotiv des Kunden > Produktfeatures, Beziehung schlägt Pitch |
| 8 | Oren Klaff | Pitch Anything (2011) | USA | Frame-Control: Status-Dynamiken steuern, STRONG-Framework, Croc-Brain ansprechen |
| 9 | Tim Taxis | Heiß auf Kalt (2011) | DE | Kalt-Akquise-Systematik für DACH: Rückzugs-Technik, Entscheider-Erstgespräch-Logik |
| 10 | Dirk Kreuter | Entscheidung Erfolg (mehrere Werke) | DE | Abschluss-orientiertes Denken, Trial-Close-Methodik, DACH-spezifische Einwand-Behandlung |
| 11 | Stephan Heinrich | Verkaufen an Top-Entscheider (2013) | DE | Consultative Selling für C-Level: Fragen-Dominanz, Kundenprozess verstehen, kein Pitchen ohne Bedarf |
| 12 | Martin Limbeck | Das neue Hardselling (2009) | DE | Abschluss-orientiert, Limbeck-Formel, Einwand = Kaufinteresse, kein Nachgeben ohne Gegenleistung |
| 13 | Hans-Uwe Köhl | Koehlerian Selling | DE | Emotionaler Verkauf: Vertrauen als Fundament, emotionale vs. rationale Einwände unterscheiden |

---

## Sektion A — Einwand-Muster

### A.1 Preis-/Budget-Einwand

**Konsens aller 13 Autoren:** Preis-Einwand = Symptom einer Value-Lücke, nicht des Preises selbst.

**Differenzierungen:**

| Behandlungs-Logik | Autoren | NERVE-Relevanz |
|---|---|---|
| Value-Rekonstruktion ("Was kostet das Nicht-Kaufen?") | Rackham (Need-Payoff), Value Selling (ROI-Calc), Gitomer | Gegenargument-Baustein: ROI-Frage statt Preis-Verteidigung |
| Einwand-Umformulierung ("Also wenn der Preis stimmt, kaufen Sie?") | Limbeck, Kreuter | Bestätigung ob echter Einwand oder Vorwand |
| Certainty-Stack (Sicherheit aufbauen: Produkt, Unternehmen, Verkäufer) | Belfort | Alle 3 Certainty-Ebenen müssen adressiert sein |
| Frame-Shift: Preis ist nicht das Problem, Statusquo ist das Problem | Challenger | Teach the customer warum Status-Quo teurer ist |
| Kein Rabatt ohne Gegenleistung | Sandler, Limbeck | Absolutes No-Go: unilateraler Rabatt |
| Emotionale Ebene prüfen: Ist es echter Preis-Widerstand oder Vertrauens-Mangel? | Köhl | Oft ist Preis-Einwand ein Beziehungs-Einwand |

**Widerspruch dokumentiert:** Belfort würde sofort in den Certainty-Stack einsteigen und Sicherheit durch Tonalität aufbauen. Köhl würde zuerst die emotionale Grundlage prüfen. Beide Wege können korrekt sein — abhängig vom Kunden-Typ.

---

### A.2 Zeit-/Prioritäts-Einwand ("Kein Interesse", "Kein Bedarf gerade")

**DACH-Spezifik:** Taxis und Kreuter behandeln DE-spezifische Erstgespräch-Abwimmel-Einwände ausführlich.

| Einwand-Typ | Behandlung | Autor |
|---|---|---|
| "Kein Interesse" (Kalt-Akquise) | Rückzugs-Technik: "Dann ist es gut, dass ich Sie nicht lange aufhalte. Darf ich trotzdem eine Frage stellen?" | Taxis |
| "Schicken Sie mir Unterlagen" (Abwimmel) | "Mit Vergnügen — was genau interessiert Sie besonders, damit ich das Richtige schicke?" | Taxis, Heinrich |
| "Kein Budget gerade" | Pain-Funnel: "Wie lange haben Sie das Problem schon?" → Implication-Fragen | Rackham, Sandler |
| "Wir haben das intern schon" | Challenger: Statusquo-Bias aufbrechen — Insight over Rapport | Challenger (Dixon/Adamson) |
| "Haben schon einen Anbieter" | Probe: "Was würde Sie dazu bewegen, eine Alternative zu prüfen?" | Kreuter, Sandler |

**Konsens:** Zeit-Einwand = Statusquo-Bias. Niemand gibt ohne Grund seinen Status Quo auf. Die Lösung ist nicht Druck, sondern Insight (Challenger) oder Pain-Amplifikation (Rackham/Sandler).

---

### A.3 Kompetenz-/Trust-Einwand

| Behandlungs-Logik | Autor | Spezifik |
|---|---|---|
| Rational: Proof-Points, Case Studies, References | Value Selling, Rackham | Zahlen, Daten, Fakten |
| Emotional: Vertrauen aufbauen durch echtes Interesse | Köhl, Gitomer | Rapport > Pitch; Beziehung ist der Beweis |
| Frame-Control: Status-Signals senden statt Kompetenz erklären | Klaff | Beta-Signale vermeiden; Alpha-Frame halten |
| Referenz-Stories aus ähnlicher Branche | Heinrich | Kundenprozess-Verständnis signalisieren |

**Widerspruch:** Klaff würde NIEMALS um Erlaubnis fragen oder Kompetenz erklären — das ist Beta. Köhl würde aber bewusst Vulnerabilität zeigen als Vertrauenssignal. Für NERVE: Kontext-abhängig; Klaff-Ansatz für C-Level (Klaff-Frame); Köhl-Ansatz für Mid-Management.

---

### A.4 Authority-Einwand ("Muss mit meinem Vorgesetzten reden")

| Behandlung | Autor |
|---|---|
| Upfront-Contract: Entscheider-Prozess VOR dem Pitch klären | Sandler |
| "Wer wäre noch dabei wenn Sie Ja sagen?" → Buying-Committee aufdecken | Sandler, Challenger |
| Challenger: Auf multi-stakeholder navigieren, nicht nur einen Kontakt | Dixon/Adamson |
| "Welche Informationen braucht Ihr Vorgesetzter?" | Heinrich (consultative) |
| Reverse: "Wenn Sie selbst entscheiden könnten — würden Sie es kaufen?" | Kreuter |

**Konsens:** Buying-Committee muss frühzeitig identifiziert werden. Authority-Einwand spät ist ein Sales-Fehler, kein Kunden-Problem.

---

### A.5 Bedarf-/Fit-Einwand ("Passt nicht zu uns")

| Einwand-Quelle | Ursache laut Autor | Behandlung |
|---|---|---|
| Zu frühe Lösungspräsentation | Rackham | Zurück zur Discovery; Implication-Fragen |
| Falsche Zielgruppe angesprochen | Ross (ICP) | ICP-Mismatch = kein Verkauf; Qualifikation wichtiger als Pitchen |
| Unklare Differenzierung | Value Selling | USP-Rehearsal; Was macht Produkt einzigartig in dieser Situation? |
| Fehlende Branchen-Relevanz | Heinrich, Taxis | Branchenwissen zeigen; "In der Maschinenbau-Branche sehen wir oft..." |

---

### A.6 Vorschiebe-Einwand vs. Echter Einwand

Dies ist einer der wichtigsten Unterschiede zwischen Systemen:

| Autor | Differenzierung | Methode |
|---|---|---|
| Köhl | Emotionaler Vorschiebe-Einwand ("Preis") vs. echter rationaler Einwand | Emotion prüfen zuerst: "Wie fühlen Sie sich mit dem Angebot insgesamt?" |
| Sandler | Taktik-Einwand vs. echtes Hindernis | Reversive Technik: "Angenommen wir lösen das — gibt es sonst noch etwas?" |
| Limbeck | Einwand = Kaufinteresse | Umformulierung: "Das freut mich, dass Sie das ansprechen..." |
| Rackham | Früher Einwand = verfrühte Präsentation | Discovery nicht abgeschlossen |
| Kreuter | Training für Einwand-Behandlung | Jeder Einwand hat Standard-Antwort; trainierbare Fertigkeit |

**NERVE-Relevanz:** Das `einwaende[].intensitaet`-Feld im Profil (aktuell überall ❌ tot) würde genau diese Unterscheidung ermöglichen.

---

## Sektion B — Frame-Strukturen

### B.1 Tabellarischer Rahmen-Vergleich

| Autor/System | Frame-Typ | Einstieg | Kern-Mechanismus | Abschluss-Logik |
|---|---|---|---|---|
| SPIN (Rackham) | Discovery-First | Situation-Fragen (neutral) | Problem→Implication→Need-Payoff | Implizierter Bedarf wird zu explizitem Bedarf |
| Challenger (Dixon/Adamson) | Insight-First | Commercial Insight / "Reframe" | Teach→Tailor→Take-Control | Kontrollierter Dialog, nicht Rapport-Verhandlung |
| Sandler | Pain-First | Upfront-Contract (Agenda + Ende definieren) | Pain-Funnel→Budget→Decision | "Ja" oder "Nein" — kein Vielleicht |
| Straight Line (Belfort) | Rapport-First | Rapport aufbauen, Kontrolle übernehmen | Tonalitäts-Control, Certainty-Stack | Loop-System: Einwand → Back to Rapport → Pitch |
| Value Selling | Value-First | Business-Issue des Kunden | ROI-Calc + Differenzierung | Entscheidung basiert auf demonstriertem Value |
| Predictable Revenue (Ross) | Process-First | SDR qualifiziert, AE pitcht | Spezialisierte Rollen | Systematischer Handoff, nicht Ad-hoc |
| Gitomer | Attitude-First | Echtes Interesse zeigen | Wert liefern vor dem Pitch | Kauf kommt von Vertrauen, nicht von Druck |
| Pitch Anything (Klaff) | Frame-Control-First | Prize-Frame setzen (du bist wertvoll) | STRONG-Framework | "Ich brauche dich nicht so sehr wie du denkst" |
| Taxis (DE) | Rückzug-First (Kalt-Akquise) | Entscheidet-Kontakt per Leitfaden | Gesprächsführung durch Fragen + Rückzug | Ersttermin als Ziel, nicht Abschluss |
| Heinrich (DE) | Fragen-Dominanz | "Was ist aktuell Ihre größte Herausforderung bei X?" | Consultative Discovery | Keine Lösung ohne vollständige Bedarfs-Analyse |
| Kreuter (DE) | Abschluss-Orientiert | Trial-Close früh ("Wenn X, würden Sie dann...?") | Entscheidungs-Druck erzeugen | Kein Aufgeben beim ersten Einwand |
| Limbeck (DE) | Abschluss-Orientiert | Direktheit + Klarheit | Limbeck-Formel: Einwand → Reformulierung → Probe | Hardselling mit Respekt |
| Köhl (DE) | Vertrauen-First | Emotionale Verbindung herstellen | Vertrauen → Bedarf → Lösung | Abschluss als natürliche Folge des Vertrauens |

### B.2 Synthese: Drei Gesprächs-Architekturen

**Typ 1 — Discovery-zentriert** (Rackham, Heinrich, Sandler):
Einstieg mit Fragen, Lösung erst nach vollständiger Bedarfs-Analyse. Gilt universell für komplexe B2B-Deals. NERVE PreCall sollte Gesprächs-Phase "Bedarfsanalyse" immer als Pflicht-Phase einbauen.

**Typ 2 — Frame-zentriert** (Challenger, Klaff, Belfort):
Wer die Konversation führt, gewinnt. Insight oder Status-Dominanz als Einstieg. Besonders wirksam bei C-Level-Kontakten und Erstkontakten.

**Typ 3 — Beziehungs-zentriert** (Gitomer, Köhl, Taxis):
Vertrauen und Rapport als Fundament; kein Pitch ohne echte Verbindung. Besonders wirksam bei deutschen Mittelstand-Einkäufern (DACH-Kultur: Vertrauen > Argumente).

**NERVE-Empfehlung:** Das `basis.branche`-Feld (Enum, aktuell ❌ tot in EWB) sollte den Frame-Typ mitbestimmen. SaaS-Vertrieb → eher Typ 2 (Challenger); Maschinenbau → eher Typ 3 (Köhl/Vertrauen).

---

## Sektion C — Fragen-Techniken

### C.1 Konsens-Patterns über alle Autoren

**Offene Entdeckungs-Fragen** (Situation/Problem-Ebene):
- Rackham Situation-Fragen: "Wie lösen Sie das aktuell?", "Wie viele Mitarbeiter sind betroffen?"
- Sandler Pain-Funnel: "Wie lange besteht das Problem?", "Was haben Sie bisher versucht?"
- Heinrich: "Was ist Ihre größte Herausforderung in diesem Bereich?"
- Taxis: "Was ist der Anlass, dass Sie sich damit beschäftigen?"
- Gitomer: "Was ist Ihnen bei einem Anbieter am wichtigsten?"

**Konsens:** Offene W-Fragen dominieren die Discovery-Phase. Jeder Autor betont: Mehr fragen als reden. Optimal: 70% Zuhören, 30% Reden.

**Implikations-Fragen** (Problem → Kosten):
- Rackham Implication: "Was passiert wenn das Problem weiter besteht?", "Welche Abteilungen sind betroffen?"
- Challenger: "Was wenn das in drei Jahren noch so ist?"
- Sandler: "Was kostet Sie das Nicht-Lösen pro Quartal?"
- Köhl: "Wie fühlt sich das für Ihr Team an?"

**Zweck:** Den Schmerzpunkt vom latenten zum expliziten Bedarf entwickeln. Ohne Implication-Fragen bleibt der Einwand "kein Bedarf" unwiderlegt.

**Commitment-/Trial-Close-Fragen:**
- Kreuter: "Wenn wir das genau so lösen können — sind wir im Geschäft?"
- Sandler Upfront-Contract: "Was müsste ich Ihnen zeigen, damit Sie am Ende Ja sagen können?"
- Rackham Need-Payoff: "Wäre es hilfreich wenn Sie X lösen könnten ohne Y zu riskieren?"

**Reframe-Fragen:**
- Klaff Frame-Shift: "Ich arbeite nur mit Unternehmen zusammen, die X bereits verstanden haben — wo stehen Sie?"
- Taxis Rückzugs-Frage: "Wenn Sie gerade kein Interesse haben — wann wäre ein besserer Zeitpunkt?"

### C.2 Divergenzen

**Gitomer:** Lehnt manipulative Fragen ab ("Techniken-Sales" ist unecht). Fragt aus echtem Interesse, nicht als Technik.

**Belfort:** Nutzt Tonalitäts-Kontrolle als Quasi-Fragen-Ersatz. Nicht "Verstehen Sie das?" sondern Rückfrage mit Tonalität ("Sie verstehen das, richtig?"). Die Frage selbst ist Bestätigung, keine Information.

**Challenger:** Stellt die wichtigste Frage nicht direkt, sondern leadet mit einem Commercial Insight ("Wussten Sie, dass Unternehmen wie Ihres im Schnitt X% verlieren weil...?"). Die Frage entsteht beim Kunden selbst.

### C.3 NERVE-Relevanz

Die `techniken.offene_fragen` und `techniken.aktiv`-Felder im Profil sind aktuell ❌ tot (nirgends in Live-EWB). Das bedeutet: NERVE kann keine kontext-spezifischen Rückfrage-Vorschläge machen, wenn die Fragen-Bibliothek nicht im Prompt ist.

---

## Sektion D — No-Gos

### D.1 Universelle No-Gos (Konsens aller oder fast aller Autoren)

| No-Go | Autoren (Konsens) | Warum |
|---|---|---|
| Feature-Dump ohne Value-Nachweis | Rackham, Value Selling, Gitomer, Challenger | Kunden kaufen Ergebnisse, nicht Features |
| Preis-Entschuldigung / sofortiger Rabatt | Limbeck, Sandler, Gitomer | Signalisiert Unsicherheit über eigenen Wert |
| Zu frühe Lösungspräsentation | Rackham, Challenger | Einwände entstehen durch fehlende Discovery |
| Unilaterale Zugeständnisse | Sandler, Limbeck | Kein Rabatt ohne Gegenleistung |
| Standard-Pitch-Einstieg ohne Rapport/Frage | Taxis, Heinrich | DACH-Markt: Vertrauen vor Pitch |
| Klagen über Markt / Konkurrenz / Preise | Gitomer | Negativität zerstört Buying-Energie |
| Erster-Einwand-Aufgabe | Kreuter, Limbeck | Statistisch: 80% der Abschlüsse nach dem 5. Follow-up |
| Beta-Verhalten (Permission-Seeking) | Klaff, Belfort | "Darf ich kurz...?", "Wäre das okay für Sie?" = Statusverlust |
| Annahmen über Kundenproblem ohne Fragen | Heinrich, Rackham | Gut gemeinte Lösung für falsches Problem |
| Produktnamen als Einstieg (Kalt-Akquise) | Taxis | Trigger sofortigen Gesprächs-Abbruch |

### D.2 Divergenzen zwischen Autoren

**Belfort's Tonalitäts-Push vs. Köhl's Emotion-First:**
Belfort würde bei Ablehnung sofort mit Tonalitäts-Kontrolle ("Nein-Rahmen" mit Freude) reagieren. Köhl würde innehalten und fragen: "Was stört Sie an dem Angebot eigentlich?" Beide sind No-Go-Verletzungen für die jeweils andere Schule.

**Klaff's "Ich brauche Sie nicht" vs. Gitomer's Beziehungspflege:**
Klaff würde explicit zeigen, dass er Kunden ablehnt. Gitomer würde dies als Beziehungs-Killer sehen. Auflösung: Frame-Control ist für C-Level und Erstgespräch; Gitomer-Beziehungspflege für Multi-Touchpoint-Deals.

**DACH-Spezifik:** Taxis und Heinrich betonen, dass im deutschen Mittelstand Aggressivität (Limbeck's Hardselling) als Kultur-Clash erlebt wird. NERVE braucht `basis.branche`-abhängige No-Go-Filter.

### D.3 NERVE-Audit-Bezug

Das `nogos[]`-Feld ist aktuell ❌ vollständig tot (geloescht mit `_build_system_prompt` in Phase 08.8). Die Literatur zeigt: No-Go-Regeln sind kritisch — ohne sie gibt das LLM Antworten die der Nutzer nie sagen darf (Branche-Tabu, Unternehmens-spezifische Verbote). Das `basis.tabu_begriffe`-Feld (✅ in EWB) adressiert nur Wort-Level, nicht Verhaltensmuster-Level.

---

## Sektion E — Profil-Felder (Schema-Input)

### E.1 Kontext-Felder (Wer ist der Käufer?)

Diese Felder setzen ALLE guten Sales-Systeme voraus — explizit oder implizit:

| Feld | Literatur-Basis | NERVE-Status | Neue Empfehlung |
|---|---|---|---|
| Branche / Sektor | Challenger (Brancheninsights), Heinrich (Branchenwissen zeigen), Taxis (DACH-Spezifik), Ross (ICP) | ❌ `basis.branche` tot in EWB | In EWB-Prompt integrieren |
| Unternehmens-Größe | Ross (ICP), Sandler (Budget-Realism), Value Selling | ❌ nicht im Profil-Schema | Neues Feld: `zielkunde.unternehmensgroesse` |
| Entscheider-Rolle / Titel | Klaff (Status-Level), Sandler (Decision-Check), Heinrich (C-Level-Selling) | ❌ `zielgruppe.berufsstatus` nur in PreCall | In EWB-Prompt integrieren |
| Buying-Committee-Größe | Challenger (Multi-Stakeholder), Sandler (Authority-Check) | ❌ kein Feld im Schema | Neues Feld: `zielkunde.buying_committee` |
| Budget-Rahmen | Sandler (Budget-Dreiklang), Value Selling (ROI-Baseline) | ❌ kein Feld | Optional: `zielkunde.budget_indikator` |

### E.2 Problem-Felder (Was schmerzt?)

| Feld | Literatur-Basis | NERVE-Status | Empfehlung |
|---|---|---|---|
| Pain-Statements / Schmerzpunkte | Rackham (Problem/Implication), Sandler (Pain-Funnel), Challenger (Statusquo-Insight) | ⚠️ `schmerzen.schmerzpunkte` nur in Training + Coaching, nicht EWB | In EWB-Prompt integrieren |
| Statusquo-Beschreibung | Challenger (Statusquo zuerst beschreiben um ihn dann zu reframen) | ❌ kein Feld | Neues Feld: `zielkunde.statusquo` |
| Implied Needs / latente Schmerzen | Rackham Implication, Sandler Pain-Funnel | ❌ kein Feld | Optional: `schmerzen.trigger` (aktuell tot, repurposen) |
| Branche-spezifische Schmerzpunkte | Heinrich, Taxis (Branchenkenntnis voraussetzen) | ❌ kein Feld | Aus Branchen-Spezifika-Recherche (08.18 Plan 02) |

### E.3 Value-Felder (Was bringt die Lösung?)

| Feld | Literatur-Basis | NERVE-Status | Empfehlung |
|---|---|---|---|
| ROI-Argumente / Kennzahlen | Value Selling, Rackham (Need-Payoff), Challenger (Teach) | ❌ kein Feld | Neues Feld: `value.roi_argumente` |
| Differenzierungs-Punkte (USPs) | Value Selling, Gitomer, Challenger | ✅ `basis.usps` in EWB | Behalten; evtl. strukturieren |
| Proof-Points / Referenzen | Value Selling, Gitomer, Heinrich | ✅ `basis.beweise` in EWB | Behalten |
| Eigene Formulierungen / Phrasen | Belfort (Scripted Language), Taxis (Leitfaden) | ✅ `basis.eigene_formulierungen` in EWB | Behalten |

### E.4 Einwand-Felder (Was wird kommen?)

| Feld | Literatur-Basis | NERVE-Status | Empfehlung |
|---|---|---|---|
| Einwand-Kategorien mit Gegenargumenten | Alle Autoren — Einwand-Behandlung ist zentrales Thema | ❌ `einwaende[]` nicht im EWB-Prompt | Kritischster Handlungsbedarf: In EWB-Prompt |
| Einwand-Varianten (alternative Formulierungen) | Rackham, Sandler, Kreuter | ❌ `einwaende[].varianten` tot | In EWB aufnehmen als "So könnte er es auch sagen" |
| Vorschiebe vs. Echter Einwand | Köhl, Sandler, Limbeck | ❌ `einwaende[].intensitaet` tot | Repurposen oder umbenennen zu `einwand_typ` |
| Branchen-typische Einwände | Taxis, Kreuter, Heinrich | ❌ kein Feld | Aus Branchen-Spezifika-Recherche (08.18 Plan 02) |
| Vorbereitete Einwand-Techniken | Sandler (Pain-Funnel), Kreuter (Trial-Response) | ❌ `techniken_aktiv` tot | In EWB als Technik-Hinweis |

### E.5 Kommunikations-Felder

| Feld | Literatur-Basis | NERVE-Status | Empfehlung |
|---|---|---|---|
| Tonalität (direkt/consultant/emotional) | Belfort (Tonalitäts-Control), Köhl (Emotion-First) | ✅ `ki.ton` in EWB | Behalten |
| Anrede Du/Sie | Taxis (DE-Erstgespräch-Standard: immer Sie), alle DE-Autoren | ✅ `ki.ansprache` in EWB | Behalten |
| Kommunikations-Stil | Gitomer (Attitude), Heinrich (Consultative) | ❌ `ki.stil` tot | Mit `ki.ton` zusammenlegen |
| Antwort-Länge / Tiefe | Heinrich (keine Monologe), Belfort (kurz und direkt) | ❌ `ki.antwortlaenge` tot | In EWB aufnehmen |
| Freie KI-Instruktion | Individuell | ❌ `ki.zusatz` nur in Coaching-Live | In EWB aufnehmen |
| Verbotene Techniken / No-Gos | Sandler, Limbeck, Köhl | ❌ `techniken_verboten` + `nogos[]` tot | Kritisch: Mindestens ein "No-Go-Block" in EWB |
| Tabu-Begriffe (Wort-Level) | Belfort (Sprach-Präzision), DACH-spezifisch | ✅ `basis.tabu_begriffe` in EWB | Behalten |

### E.6 Prozess-Felder

| Feld | Literatur-Basis | NERVE-Status | Empfehlung |
|---|---|---|---|
| Entscheidungs-Prozess / Buying-Journey | Sandler (Decision-Dreiklang), Challenger (Tailor) | ❌ `zielgruppe.entscheidungsverhalten` nur in Coaching | In EWB aufnehmen |
| Zeithorizont / Dringlichkeit | Sandler, Value Selling | ❌ kein Feld | Optional: `zielkunde.zeithorizont` |
| Wettbewerber-Landschaft | Heinrich, Taxis, Kreuter | ❌ `wettbewerber[]` nur in Coaching + Training, nicht EWB | In EWB aufnehmen |
| PreCall-Briefing / Recherche-Ergebnis | Taxis (Vorbereitung-Logik), Heinrich (Wissens-Basis) | ❌ `ls.state['precall_briefing']` fließt nicht in EWB | Re-Integrieren (Phase 08.20) |

### E.7 Zusammenfassung: Neue Felder vs. Vorhandene

**Vorhandene Felder die aus Literatur-Sicht bleiben sollten (✅ oder ⚠️ aufwerten):**
- `basis.unternehmen`, `basis.produktbeschreibung`, `basis.preismodell`, `basis.usps`, `basis.konsequenz`
- `basis.branche_kontext`, `basis.eigene_formulierungen`, `basis.beweise`, `basis.tabu_begriffe`
- `ki.ton`, `ki.ansprache`

**Felder die sterben sollten (kein Literatur-Konsens, kein Prompt-Impact):**
- `zielgruppe.alter`, `zielgruppe.einkommensniveau`, `zielgruppe.lebenssituation` (B2C-Felder, NERVE ist B2B)
- `schmerzen.trigger` (Slider-Widget ohne Wirkung)
- `ki.stil` (Duplikat zu `ki.ton`)
- `erlaubnis` (nirgendsgelesen)
- `consent_text` (UI-only, kein LLM-Input)

**Neue Felder die Literatur empfiehlt und NERVE nicht hat:**
1. `zielkunde.unternehmensgroesse` (Ross ICP; Sandler Budget-Realism)
2. `zielkunde.buying_committee` (Challenger; Sandler Authority)
3. `zielkunde.statusquo` (Challenger — Statusquo reframen ist der Kern-Insight)
4. `zielkunde.zeithorizont` (Sandler, Value Selling)
5. `value.roi_argumente` (Value Selling, Rackham Need-Payoff)
6. `einwaende[].einwand_typ` (echt vs. Vorschiebe — Köhl, Sandler, Limbeck)

---

## Sektion F — Reihenfolge im Voll-Profil-Prompt

### F.1 Anthropic: Lost-in-Middle-Effekt

**Quelle:** Anthropic Prompt Engineering — Long Context Tips (https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/long-context-tips)

**Befund:** Sprachmodelle haben eine Tendenz, Informationen in der **Mitte** langer Kontexte weniger zu gewichten als Informationen am **Anfang** oder **Ende**. Bekannt als "Lost-in-the-Middle"-Problem.

**Implikation für NERVE:** Kritische Profil-Felder (Einwand-Gegenargumente, No-Gos, Tabu-Begriffe) müssen ans **Anfang** oder **Ende** des System-Prompts, NICHT in die Mitte.

**Anthropic-Empfehlung:**
- Stabile Kern-Informationen an den Anfang des `system=`-Parameters
- Variable Gesprächs-Informationen in `messages=[user]` (User-Message, nicht System)
- Long-Tail-Details (weniger kritisch) können in die Mitte

---

### F.2 Anthropic: System vs. User-Message Split

**Faustregel (Anthropic Prompt Engineering Guide):**

| Gehört in `system=` | Gehört in `messages=[user]` |
|---|---|
| Stabile Identität und Rolle des Assistenten | Aktueller Konversations-Kontext (letzte N Sätze) |
| Profil-Kontext des Vertriebers | Aktuell detektierter Einwand-Text |
| Einwand-Repertoire (vorbereitet) | PreCall-Briefing (variiert pro Gesprächs-Session) |
| No-Gos und Tabu-Regeln | Gesprächs-Phase (variiert pro Moment) |
| Kommunikations-Regeln (Ton, Anrede) | Spezifische Anfrage/Frage des Vertriebers |
| USPs und Beweise | Spontaner Kontext ("gerade sagte der Kunde:") |

**NERVE-Status:** `build_ewb_prompt()` packt aktuell alles in `system=`. Das ist korrekt für den stabilen Profil-Kontext. Der `kontext` (Transcript-Buffer) ist bereits in der User-Message. **Kein Handlungsbedarf für den Split — aber Reihenfolge im System-Prompt optimieren.**

---

### F.3 Anthropic: Cache-Anchor-Position

**Caching-Strategie (Anthropic Prompt Caching Guide):**

`cache_control: ephemeral` soll nach dem **ersten großen stabilen Block** gesetzt werden. Das ermöglicht Anthropic, diesen Block zu cachen und bei Folge-Calls wiederzuverwenden.

**Für NERVE's `build_ewb_prompt()`:**
- Block 1 (stable): Firma + Produkt + Branche + USPs — **Cache-Anchor hier setzen**
- Block 2 (stable): Einwand-Repertoire + No-Gos + Kommunikationsregeln — profitiert vom Cache
- Block 3 (variable): Aktueller Gesprächs-Kontext → in User-Message, kein Cache

**Vorteil:** Profil-Kontext > 4096 Zeichen (was bei Voll-Profil sicher überschritten wird) → Cache-Read statt Cache-Write → Kosten sinken um ~90% pro EWB-Call.

**NERVE-Status:** Caching-Schwellenwert-Guard existiert bereits (Phase 08.13). Aber der Profil-Kontext ist derzeit zu kurz (10 Felder, unter 4096 Zeichen). Bei Voll-Profil-Integration wird Threshold automatisch überschritten.

---

### F.4 Sales-Trainer-Konsens zur Vorbereitung-Reihenfolge

**Taxis und Heinrich:** Vorbereitung folgt der Logik "Kontext zuerst, Ziel dann, Taktik zuletzt":
1. Wer ist der Gesprächspartner? (Rolle, Unternehmen, Branche)
2. Was ist das Gesprächs-Ziel? (Erstgespräch, Demo, Closing)
3. Welche Einwände sind wahrscheinlich? (Branche, Rolle)
4. Wie reagiere ich? (Gegenargumente, Techniken)

**Klaff:** Frame-Setting zuerst. Bevor du in den Call gehst, musst du wissen: Wer hat den höheren Status? Was ist dein Prize-Frame? Erst dann Taktik.

**Challenger (Dixon/Adamson):** Commercial-Insight zuerst — welcher Branchen-Insight kann ich lehren? Dann Tailoring für die Rolle.

---

### F.5 Empfohlene Reihenfolge für NERVE's `build_profile_context()`

Auf Basis von Anthropic Best-Practices + Sales-Trainer-Konsens:

```
BLOCK 1 — STABILER KERN (Cache-Anchor-Kandidat):
  1a. Firma + Produkt + Branche + Unternehmenskontext
      → Lost-in-Middle: Am ANFANG = höchste Gewichtung
      → Anthropic: Cache-Anchor nach diesem Block
      → Literatur: Taxis/Heinrich Kontext-zuerst + Klaff Frame-Setting

  1b. Zielkunden-Profil + Kaufmotive + Statusquo
      → Challenger (Statusquo-Reframe), Sandler (Pain-Budget-Decision)
      → Neue Felder: unternehmensgroesse, buying_committee, statusquo

BLOCK 2 — TAKTISCHER KERN (nach Cache-Anchor):
  2a. Einwand-Repertoire (Liste: Einwand → Gegenargument → Varianten)
      → Rackham, Sandler, Kreuter, Limbeck, Köhl
      → Aktuell: ❌ fehlt komplett im EWB-Prompt

  2b. Value-Argumente + ROI-Argumente + Beweise + Differenzierung
      → Value Selling, Rackham Need-Payoff, Challenger Teach
      → Aktuell: ✅ USPs + Beweise + eigene Formulierungen

  2c. No-Gos + Verbotene Techniken + Tabu-Begriffe
      → Sandler, Limbeck, Klaff, alle DACH-Autoren
      → Aktuell: ⚠️ Tabu-Begriffe OK; No-Gos tot

BLOCK 3 — KOMMUNIKATIONS-REGELN:
  3a. Ton + Anrede + Stil + Freie KI-Instruktion
      → Belfort (Tonalität), Köhl (Emotion), alle DACH-Autoren
      → Aktuell: ✅ ton + ansprache; ❌ zusatz + antwortlaenge tot

BLOCK 4 — VARIABLE DATEN (User-Message, kein Cache):
  4a. Gesprächs-Phase + PreCall-Briefing
      → Taxis/Heinrich Phasen-Logik, PreCall-Vorbereitung
      → In User-Message! (variiert pro Session/Moment)

  4b. Aktueller Gesprächs-Kontext (Transcript-Buffer)
      → Bereits korrekt in User-Message
```

**Begründung je Schritt:**

| Block | Anthropic-Quelle | Literatur-Quelle |
|---|---|---|
| 1a zuerst | Lost-in-Middle: Anfang = höchste Gewichtung | Taxis: Kontext zuerst; Klaff: Frame zuerst |
| Cache-Anchor nach 1a | Anthropic Caching Guide: nach stabilem Block | — |
| 2a Einwand-Repertoire | Middle ist OK wenn Anfang/Ende wichtiger | Alle Autoren: Einwand-Vorbereitung ist Kern |
| 3a Kommunikation spät | Lost-in-Middle: Ende = zweithöchste Gewichtung | Belfort: Tonalität muss persistent sein |
| 4a in User-Message | Anthropic: System = stabil; User = variabel | Taxis: PreCall ist Gesprächs-Session-spezifisch |

---

## Schema-Empfehlungen für 08.19 (Kompakt-Bullets)

Maximal 20 actionable Bullets für Phase 08.19 Pydantic-Schema-Redesign:

**Neue Felder hinzufügen:**
- `zielkunde.unternehmensgroesse` (Enum: <10 / 10-50 / 50-250 / 250-1000 / 1000+) — Ross ICP, Sandler Budget-Realism
- `zielkunde.buying_committee` (String: wer entscheidet außer Gesprächspartner?) — Challenger, Sandler Authority-Check
- `zielkunde.statusquo` (Text: wie löst der Kunde das Problem aktuell?) — Challenger Kern-Konzept; ohne Statusquo kein Reframe
- `zielkunde.zeithorizont` (Enum: sofort / 3 Monate / 6 Monate / kein Druck) — Sandler, Value Selling
- `value.roi_argumente` (Liste: ROI-Calc-Bausteine, Kosteneinsparungs-Argumente) — Value Selling, Rackham Need-Payoff
- `einwaende[].einwand_typ` (Enum: echt / vorschiebe / unbekannt) — Köhl, Sandler, Limbeck Einwand-Differenzierung

**Bestehende Felder reparieren (in EWB-Prompt integrieren, aktuell tot):**
- `basis.branche` (Enum) → In `build_profile_context()` einfügen; steuert Frame-Typ und Branchen-Insight
- `einwaende[]` (vollständige Liste) → In EWB-Prompt als Referenz-Block; LLM soll Gegenargumente bei Nicht-Keyword-Match nutzen
- `zielkunde.statusquo` → In EWB: Challenger-Reframe-Basis
- `wettbewerber[]` → In EWB aufnehmen (EWB ignoriert sie komplett; Coaching-Live hat sie)
- `ki.zusatz` → In EWB aufnehmen (User hat "freie KI-Instruktion" definiert — sollte überall gelten)
- `ki.antwortlaenge` → In EWB aufnehmen (Direkt prompt-relevant: kurz vs. ausführlich)
- `nogos[]` → Neuer Block im EWB-Prompt; kein Gegenargument-Vorschlag der ein No-Go triggert

**Felder eliminieren (kein Literatur-Konsens, kein Prompt-Impact):**
- `zielgruppe.alter` — B2C-Feld; NERVE ist B2B; kein Autor-Konsens für B2B-Sales
- `zielgruppe.einkommensniveau` — B2C; eliminieren
- `zielgruppe.lebenssituation` — B2C; eliminieren
- `schmerzen.trigger` — Slider-UI ohne Wirkung; eliminieren oder in `zielkunde.statusquo` aufgehen lassen
- `ki.stil` — Duplikat zu `ki.ton`; zusammenlegen
- `erlaubnis` — nirgendsgelesen; eliminieren
- `consent_text` — UI-only, kein LLM-Input; als `meta.consent_text` markieren

**Reihenfolge in `build_profile_context()`:**
- Block 1: `unternehmen` + `produktbeschreibung` + `branche` + `branche_kontext` (Cache-Anchor-Kandidat)
- Block 2: `zielkunde.*` + `schmerzen.schmerzpunkte` (Käufer-Kontext)
- Block 3: `einwaende[]` vollständig (Kern-Taktik)
- Block 4: `wettbewerber[]` + `value.roi_argumente` + `usps` + `beweise` + `konsequenz`
- Block 5: `nogos[]` + `techniken_verboten` + `tabu_begriffe` (No-Go-Block, am Ende = zweithöchste Gewichtung)
- Block 6: `ki.ton` + `ki.ansprache` + `ki.antwortlaenge` + `ki.zusatz`
- PreCall-Briefing → User-Message (nicht System), da Session-variabel

**System vs. User-Message Split:**
- `system=`: Alles oben (Blöcke 1-6) — stabil, gecacht
- `messages=[user]`: Gesprächs-Phase + PreCall-Briefing + Transcript-Buffer — variabel, kein Cache

**EWB-Integration-Quote-Ziel für 08.19/08.20:**
- Aktuell: 10/48 = 21% — nach Schema-Redesign und Pipeline-Re-Wire: Ziel ≥ 30/48 = 62%

---

*Erstellt: 2026-04-27 | Phase 08.18 Plan 01 | Für Phase 08.19 (Pydantic-Schema-Redesign)*
