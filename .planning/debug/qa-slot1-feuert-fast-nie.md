---
slug: qa-slot1-feuert-fast-nie
status: diagnosed
trigger: "KI-Antwort im Live-Assistenten (qa_slot1, rechtes PiP) feuert fast nie — Prod-Logs 14 Tage: nur 3x emittiert trotz mehrerer Call-Sessions; an Call-Tagen mit mehreren Gesprächen (5. Juni) gar nicht."
created: 2026-06-08
updated: 2026-06-08
---

# Debug: qa_slot1 feuert fast nie

## Symptoms
- qa_slot1 (KI-Antwort, rechtes PiP) nur 3x in 14 Tagen emittiert.
- An Call-Tagen mit Volumen (5. Juni) 0x.
- Logging-First-Direktive (CLAUDE.md Punkt 15): kein Fix im ersten Pass.

## Method
KEIN neues Logging nötig — die QA-Pipeline hat bereits reichhaltige `[QA-INT]`-Marker
(claude_service.py:1279/1284/1310/1319/1335/1398). 14-Tage-Prod-Logs (read-only via
`ssh nerve_vps … journalctl -u nerve --since "14 days ago"`) ausgewertet, Marker
gezählt, Klassifikator-Verdikte per `line_id` mit dem Utterance-Text aus
`[Claude-1] … Analysiere (line N): …` gejoint.

## Evidence (Prod, 14 Tage)
- `[Claude-1] Analysiere`: **124** (Utterances analysiert)
- `[QA-INT] classify`: **113** → QA-Dispatch wird zu ~91% erreicht (NICHT abgewürgt)
- kategorie-Verteilung: **93 smalltalk_none (82%)**, 16 frage, 4 einwand_known, **0 einwand_unknown**
- frage-conf-Werte: 0.45, 0.55, 0.65×7, 0.72×2, 0.75×2, 0.95×3
- `soft_hint`: **13** — alle Grund `no_faq_low_conf` (conf < Threshold, kein FAQ-Match)
- `qa_slot1 emitted`: **3** — exakt die drei `frage conf=0.95`
- `CLASSIFIER_CONFIDENCE_THRESHOLD = 0.80` (config.py:42)
- `[phase_classify] loop error: '>' not supported between instances of 'int' and 'str'`: **8x**
- Call-Tage (Analysiere): 27.5.(17), 28.5.(8), 30.5.(8), 31.5.(19), 3.6.(29), **5.6.(43)**
- Utterance-Text-Join: die klassifizierten Sätze sind **fast ausschließlich das Verkäufer-
  Skript** ("Guten Tag, mein Name ist…", "Erstens, Einwände werden zu spät erkannt…",
  "Hätten Sie Dienstag 14 Uhr Zeit?"). Kein Kunden-Turn in der Stichprobe. Die 3 qa_slot1
  waren die **eigenen Termin-Fragen des Verkäufers** (frage 0.95).

## Root Cause
Die 14-Tage-Daten sind **Single-Speaker-Skript-Testcalls** (Andres TTS-Cold-Call-Demo).
Deepgram sieht nie einen zweiten Sprecher → `roles_confirmed = ls._second_sp_seen`
(deepgram_service.py:71) bleibt den ganzen Call **False**. Damit lässt das QA-Gate
`if not roles_confirmed or speaker != 0:` (live_session.py:695) **alle** Utterances in
die QA-Pipeline — d.h. das komplette Verkäufer-Monolog-Skript. Der Klassifikator
unterdrückt das **korrekt** als `smalltalk_none` (Prompt qa_pipeline.py:64: "Berater liest
fertigen Vertriebs-Satz vor → smalltalk_none"). Es gelangen **nie Kunden-Einwände** in den
Klassifikator, weil in diesen Aufnahmen kein Kunde spricht. → qa_slot1 hat fast nichts
Legitimes zum Feuern. Garbage-in, nicht Pipeline-Bug.

Design ist eigentlich korrekt: nach `roles_confirmed` füttert nur `speaker != 0` = Kunde
(sp_map {0:Berater, 1:Kunde}, live_session.py:886) die QA. Aber bei Single-Voice-Tests
greift dieser Schutz nie.

## Hypothesen-Verdikt
- **H1 (phase_classify würgt qa-dispatch ab): VERWORFEN.** Struktur: qa-dispatch läuft
  Zeile 909 VOR dem phase-classify-Block (986+); phase_classify hat eigenes inneres
  try/except (claude_service.py:987–1075), das äußere except sitzt bei 1161. Empirisch:
  classify lief 113x trotz 8 phase-Fehlern.
- **H2 (Pipeline filtert sich weg): TEILWAHR als Mechanismus, aber korrektes Verhalten.**
  Der Funnel unterdrückt Verkäufer-Monolog richtig. ECHTES Sekundär-Problem: Threshold 0.80
  unterdrückt 13 legitime `frage` bei conf 0.45–0.75 (Haiku-Confidence clustert um 0.65).
- **H3 (wenig echte Calls): TEILWAHR, aber nicht die Erklärung.** 5.6. hatte 43 Utterances
  und 0 qa_slot1 → kein Volumen-Problem, sondern Single-Speaker-Funnel.
- **H4 (emergent, stärkste): Pipeline-Input ist Verkäufer-Sprache** mangels zweitem Sprecher.

## Independent Bug (mitgenommen)
`[phase_classify] loop error: '>' not supported between 'int' and 'str'` (8x). Real,
unabhängig von QA. Disabled die Phasen-Klassifikation (gefangen in innerem except
claude_service.py:1075). Wahrscheinlich `current_phase` als String im Session-State
(JSON/DB-Roundtrip "1" statt 1), verglichen mit `>` in detect_phase/classify_phase-Pfad.
NICHT in Pass 1 gefixt (Logging-First-Direktive).

## Current Focus
hypothesis: Root cause diagnostiziert aus bestehenden Logs (kein neues Logging nötig).
next_action: Mit André entscheiden — (a) Echter Zwei-Sprecher-Call zur End-to-End-
  Bestätigung des Kunden-Pfads, (b) Threshold-Tuning 0.80→? , (c) phase_classify int/str-Fix.
reasoning_checkpoint: Offen ist NUR, ob bei bestätigten Rollen Kunden-Einwände tatsächlich
  qa_slot1 erzeugen — das braucht einen echten/zwei-stimmigen Call, nicht mehr Logging.

## Eliminated
- hypothesis: phase_classify-Fehler blockiert qa-dispatch — REJECTED (Reihenfolge + getrenntes except + 113 classify trotz 8 errors)
- hypothesis: niedrige Call-Zahl ist Ursache — REJECTED als Haupt­ursache (5.6.: 43 Utt / 0 slot1)
