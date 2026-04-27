---
audit: profil-prompt-integration
phase: A
erstellt: 2026-04-24
aktualisiert: 2026-04-27
autor: Claudian (initial) / Claude Sonnet 4.6 (update 2026-04-27)
stand_code: salesnerve/ HEAD 2026-04-27 (post Phase 08.14)
zweck: Matrix über welche Profil-Felder in welchem Prompt-Pfad landen. Basis für Profil-Redesign (Phase 08.18 Sales-Literatur-Research, Phase 08.19 Pydantic-Schema-Redesign).
---

# Profil-Prompt-Integrations-Audit — Matrix + Findings

## TL;DR für André

**Dein Bauchgefühl stimmt: ca. 50-60% der Profil-Felder landen niemals in einem Live-Prompt. Die EWB (PiP-Kasten) nutzt extrem wenig.** Konkret:

1. Der alte große System-Prompt (`_build_system_prompt`) mit allen Feldern — Einwände, Zielgruppe, Wettbewerber, No-Gos, Übergänge, KI-Stil-Details — **ist seit Phase 08.8 vollständig gelöscht** (nicht mehr nur dead code, sondern tatsächlich entfernt). Nur noch `build_ewb_prompt` → `build_profile_context` läuft, das nur ca. 10 Felder liest.
2. Das **PreCall-Briefing fließt NICHT mehr in den EWB-Prompt** — früher über ls.state['precall_briefing'] in `_build_system_prompt`, jetzt tatsächlich weg. Deine Recherche landet nur noch in der UI, nicht im LLM.
3. Der **Manual-EWB-Button-Klick-Pfad** (`streame_manual_ewb_variante`) hat einen HARDCODED Coach-Prompt ohne jeden Profil-Kontext. Nur das eine Profil-Gegenargument wird in den User-Message gepackt.
4. Die Einwände-Liste (mit `einwand`, `varianten`, `gegenargument`, `technik`, `intensitaet`) ist im **Live-EWB-Prompt NICHT enthalten**. Nur über Keyword-Matcher (Regex) wird bei Treffer das entsprechende Gegenargument direkt ausgespielt — aber das LLM sieht die Liste nicht und kann sie nicht nutzen wenn kein Keyword matcht.
5. FAQs (Phase 08.5) werden **nur im FAQ-Match-Pfad** verwendet (Embedding-Vergleich) — nicht als Kontext im EWB-Prompt.

---

## Aenderungen seit Audit v1 (2026-04-24)

| Delta | Phase | Wirkung auf Matrix |
|-------|-------|-------------------|
| `_build_system_prompt` geloescht | 08.8 | Alle 🧟 → ❌ (kein Zombie mehr, tatsaechlich absent — Funktion nicht mehr im Code) |
| `analysiere_mit_claude_streaming` geloescht | 08.8 | Pfad 1+2 Beschreibung aktualisiert: nur noch `analysiere_mit_claude` |
| `finetune_logging` / `log_pipeline_event` geloescht | 08.8 | Kein Matrix-Impact (war nie prompt-relevant) |
| LB-3 Fix: profile_data in QA-Pipeline | 08.9 | Pfad 4 technisch korrekt verdrahtet: profile_data korrekt uebergeben. ABER nur `tabu_begriffe` + `einwaende[].gegenargument` (protected_words) extrahiert — KEINE neuen Felder im Prompt. Status unveraendert. |
| Classic-View-Deprecation | 08.11 | Kein Matrix-Impact (Classic-Routen hatten keine eigenen Profil-Reads die abwichen) |
| Prompt-Caching EWB+QA+analyse_loop | 08.13 | Kein Impact auf welche Felder gelesen werden — nur Performance (cache_control: ephemeral wrapper wenn Prompt > 4096 Zeichen) |
| Block E: claude_client-Konsolidierung (5 inline Clients → shared claude_client, system= kwarg) | 08.13 | system= als separater Kwarg in ALLEN API-Calls bestaetigt (claude_service.py L496/590/699/779, qa_pipeline.py L312/429, training_service.py L820/880). Prompt-Assembly-Struktur UNVERAENDERT — kein Kontext wurde von messages=[] in system= verschoben. |
| MODEL_*-Konstanten Date-Suffix-Swap (claude-sonnet-4-5 → claude-sonnet-4-5-20251022) | 08.14 | Kein Prompt-Assembly-Impact (nur Versions-String in 9 Konstanten geaendert) |

---

## Status-Symbol-Definitionen (zwingend konsistent anwenden)

**✅** = Feld wird aus dem Profil gelesen UND tatsaechlich in den finalen String/Content-List eingebaut der an das LLM gesendet wird.
Beispiel: `f"Kaufsignale: {profil['kaufsignale']}"` gefolgt von Append in den Prompt-String.

**⚠️** = PARTIAL — Feld wird an die Funktion/den API-Call weitergereicht, aber NICHT tatsaechlich in den finalen String/Content-List eingefuegt der ans LLM geht.
Konkrete Faelle:
- Feld ist im profile_data-Dict das uebergeben wird, aber wird nie extrahiert (z.B. profile_data als Param aber `profile_data.get('kaufsignale')` kommt nirgendwo vor)
- Feld wird extrahiert aber nur fuer Metadata/Logging verwendet, nicht fuer Prompt-Content
- Feld wird in einer Hilfsfunktion gelesen aber der Rueckgabewert wird vom Aufrufer ignoriert
Beispiel: `generate_qa_response(profile_data=profile_data)` — profile_data kommt an, aber
in der Funktion wird nur `tabu_begriffe` extrahiert, `kaufsignale` nie.

**❌** = Feld wird in diesem Prompt-Pfad weder gelesen noch uebergeben — vollstaendig ignoriert.

**🧟** = War frueher in einer Funktion gelesen die jetzt deleted/unreachable ist (Zombie-Code-Erbe).
NUR verwenden wenn die urspruengliche Funktion noch im Code existiert aber nie aufgerufen wird.
Wenn Funktion tatsaechlich geloescht: ❌ verwenden (kein Zombie mehr, tatsaechlich absent).

**N/A** = Dieses Feld ist fuer diesen Prompt-Pfad konzeptionell irrelevant.

---

## Prompt-Pfade — Was sie tatsächlich lesen

Aus Code-Analyse (services/*.py) — verifiziert gegen Stand post Phase 08.14:

### Pfad 1: Cold-Call Live-EWB (Haiku, Hauptsystem)

**Funktion:** `claude_service.analysiere_mit_claude` (Zeile 453)

**Hinweis 08.8:** `analysiere_mit_claude_streaming` wurde in Phase 08.8 geloescht. Nur noch `analysiere_mit_claude`.

**System-Prompt:** `build_ewb_prompt(version, user_id)` (ewb_pipeline.py Z. 31) → ladet Template aus DB (module='ewb') + `build_profile_context()` (prompt_pipeline.py Z. 111)

**User-Message:** Enthält `kontext` (letzte Transkript-Zeilen) + `neuer_text` (aktuelle Utterance).

**Gelesen aus Profil (via build_profile_context, prompt_pipeline.py Z. 149-195):**
- `basis.unternehmen` (Z. 149)
- `basis.produktbeschreibung` (Z. 151)
- `basis.preismodell` (Z. 153)
- `basis.usps` (Z. 155)
- `basis.konsequenz` (Z. 158)
- `basis.branche_kontext` (Phase 08 D-11, Z. 162)
- `basis.eigene_formulierungen` (Phase 08 D-07, Z. 166)
- `basis.beweise` (Phase 08 D-08, Z. 172)
- `basis.tabu_begriffe` (ueber `build_tabu_instruction`, Phase 08.5 Korrektur 1, Z. 191-196)
- `ki.ton` (Z. 180)
- `ki.ansprache` (Anrede-Resolution, Z. 184-188 — full value used in prompt)
- **Session-Overrides:** `ls.state['session_anrede']` (Z. 184)

**NICHT gelesen (tot im Live-EWB-Prompt):**
- `basis.name` (Nutzername)
- `basis.branche` (Enum!)
- `opener`, `erlaubnis`, `pitch`
- ALLE Zielgruppe-Felder (`alter`, `berufsstatus`, `einkommen`, `lebenssituation`, `hintergrund`, `vorwissen`, `entscheidung`)
- `einwaende[]` (die Array-Liste mit Gegenargumenten — nur ueber Keyword-Matcher, siehe unten)
- `faqs[]`
- `kaufsignale`, `nogos`, `wettbewerber`, `uebergaenge`
- `techniken_aktiv`, `techniken_verboten`, `offene_fragen`
- `ki.stil`, `ki.antwortlaenge`, `ki.sensitivitaet`, `ki.zusatz`
- `schmerzen.trigger`, `schmerzen.schmerzpunkte`
- `consent_text`
- **`ls.state['precall_briefing']`** — PreCall-Recherche-Ergebnis fliesst NICHT rein (Injektionspunkt war _build_system_prompt, jetzt geloescht)

### Pfad 2: Meeting-Modus Live-EWB

**Gleicher Pfad wie Cold-Call** (`analysiere_mit_claude` Z. 453). Deepgram-Diarisierung gibt im Meeting-Modus sowohl Berater- als auch Kunden-Utterances. System-Prompt identisch — **dieselben Felder wie Pfad 1**.

### Pfad 3: Manual-EWB-Button-Klick (Slot-1-Variante)

**Funktion:** `claude_service.streame_manual_ewb_variante` (Zeile 638)

**System-Prompt:** HARDCODED — `"Du bist ein erfahrener Sales-Coach im DACH-B2B. Antworte knapp, praktisch, menschlich — keine Fuellwoerter, keine Meta-Kommentare."`. **Kein Profil-Kontext.**

**User-Message:** Enthält typ-Name + `profile_einwand.gegenargument_1` (oder `gegenargument`/`text`) + `kontext` (Gesprächsverlauf).

**Gelesen aus Profil:**
- `einwaende[].gegenargument_1` (bzw. `gegenargument`/`text`) fuer den geklickten Typ (im User-Msg, Z. 651-655)

**NICHT gelesen:** ALLES andere. Keine `ton`, keine `ki_ansprache`, keine `usps`, keine `beweise`, keine `tabu_begriffe`. **Button-Pfad umgeht das ganze Profil.**

### Pfad 4: Unknown-Einwand-Antwort / Rückfrage-Generator (Phase 08.5)

**Funktion:** `qa_pipeline.generate_qa_response` (Zeile 357)

**System-Prompt:** `_SYSTEM_PROMPT_QA` Template (Z. 78-90) + `build_tabu_instruction(profile_data)` fuer Tabu-Block.

**LB-3 Fix Status (Phase 08.9):** profile_data wird korrekt uebergeben (Fix in _qa_pipeline_dispatch beide generate_qa_response-Aufrufe). Aber: `_SYSTEM_PROMPT_QA` hat nur `{tabu_block}` und `{anrede}` Placeholder — kein `{profile_context}`. Die `_FALLBACK_QA_RESPONSE_PROMPT` mit `{profile_context}` Placeholder wird vom Code NICHT fuer den primary path genutzt. Fazit: LB-3 ist ein technischer Fix (korrekte Parameter-Uebergabe), aber KEINE inhaltliche Erweiterung des Profil-Kontexts in Pfad 4.

**Gelesen aus Profil:**
- `basis.tabu_begriffe` (Tabu-Instruction + Safety-Net, Z. 370)
- `einwaende[].gegenargument*` (nur fuer `build_protected_words` — Schutz von User-Woertern vor Tabu-Filter, Z. 444)
- `anrede` (Session-Override, Z. 389)

**NICHT gelesen:** Alle Basis-Felder (`unternehmen`, `produkt`, `usps`, `beweise`, `eigene_formulierungen`), Zielgruppe, FAQs, Wettbewerber, etc.

**→ Kritisch:** Der Unknown-Einwand-Antworter hat KEINE Ahnung wer der User ist oder was er verkauft. Nur Tabu-Woerter + Anrede. Kein Wunder dass "Frag nach: Wie meinen Sie das genau?" generisch wird.

### Pfad 5: Klassifikator (Phase 08.5)

**Funktion:** `qa_pipeline.classify_utterance` (Zeile 289)

**System-Prompt:** Fixes Template (`_FALLBACK_CLASSIFIER_PROMPT`). **Keine Profil-Integration.** Klassifiziert rein semantisch.

**Gelesen aus Profil:** NICHTS.

### Pfad 6: FAQ-Match (Phase 08.5)

**Funktion:** `qa_pipeline.match_faq` (Zeile 489)

**Kein LLM-Call** — sentence-transformers Embedding-Vergleich.

**Gelesen aus Profil:**
- `faqs[].frage_muster` (fuer Embedding)
- `faqs[].antwort` (wird returned — wird ausgespielt, nicht in einem Prompt)

### Pfad 7: Einwand-Keyword-Matcher (pre-LLM Regex)

**Funktion:** `einwand_keyword_matcher.match_keyword`

**Kein LLM-Call** — Regex-Match auf Keyword-Tabelle, mapped auf Einwand-Kategorie, zieht `gegenargument_1`/`gegenargument`/`text` aus Profil-Einwand und spielt direkt in Slot 0 aus (client-side). Umgeht LLM komplett.

**Gelesen aus Profil:**
- `einwaende[].kurzlabel` / `kategorie` / `typ` (fuer Alias-Match)
- `einwaende[].gegenargument*` (wird direkt ausgespielt)

**NICHT gelesen:** varianten, technik, intensitaet der Einwaende.

### Pfad 8: Training-Modus Kunden-Simulation

**Funktion:** `training_service.build_customer_prompt` (Zeile 569)

**Gelesen aus Profil:**
- `basis.produktbeschreibung` (Z. 579)
- `zielgruppe.vorwissen` (wirkt nur wenn 'hoch' oder 'gering', Z. 593)
- `zielgruppe.entscheidungsverhalten` (Z. 597)
- `einwaende[]` — erste 6 mit `einwand` + `varianten` (Z. 581)
- `wettbewerber[].name` (erste 3, Z. 603)
- `ki.ansprache` (Z. 605)
- `schmerzen.schmerzpunkte[0].situation` (Z. 600)

**NICHT gelesen:** `unternehmen`, `usps`, `konsequenz`, `branche_kontext`, `eigene_formulierungen`, `beweise`, `opener`/`pitch`, `faqs`, `kaufsignale`, `nogos`, `uebergaenge`, `techniken_*`, `ton`, `antwortlaenge`, `sensitivitaet`, `zusatz`, `tabu_begriffe`, `consent_text`.

### Pfad 8b: Training-Modus Personality-Prompt (Phase 04.9)

**Funktion:** `training_service.build_personality_prompt` (Zeile 724)

**Gelesen aus Profil:**
- `produkt` (flach, nicht `basis.produktbeschreibung`, Z. 731)
- `branche` (flach, Z. 732)
- `einwaende[]` (Z. 733)

**Rest kommt aus `personality_data`-Tabelle** (separate Trainings-Personas, kein Verkaufsprofil). NICHT gelesen werden die meisten Profil-Felder.

### Pfad 9: Training-Modus Scoring

**Template:** `_SCORING_FALLBACK_TEMPLATE` — generisch, **keine Profil-Integration.** Scoring-Prompt wird zur Laufzeit mit `gespraech`, `einwaende`, `kaufsignale` aus der Session gefuettert, aber das Profil-Schema selbst wird nicht referenziert.

### Pfad 10: PreCall-Briefing (Brave Search + Haiku)

**Funktion:** `precall_service.recherche_firma` (Z. 42) / `_generiere_briefing` (Zeile 126)

**Gelesen aus Profil:**
- `basis.produktbeschreibung` (Z. 144)
- `basis.usps` (Z. 146)
- `zielgruppe.berufsstatus` (Z. 148)
- `opener` (TOP-LEVEL, nicht unter leitfaden — Schema-Inkonsistenz!, Z. 150)
- `pitch` (TOP-LEVEL, Z. 151)

**NICHT gelesen:** Rest.

**Kritisch:** Das Ergebnis (`briefing_dict`) wird in der UI angezeigt und in `ls.state['precall_briefing']` geschrieben — aber von KEINEM der Live-LLM-Pfade mehr gelesen. Der eine Pfad der es nutzte (`_build_system_prompt`) ist seit Phase 08.8 **geloescht**.

### Pfad 11: Coaching-Live (Haiku, separat vom EWB)

**Funktion:** `claude_service.analysiere_coaching` (Zeile 768) → `_build_coaching_prompt` (Zeile 210)

**Gelesen aus Profil (via _build_coaching_prompt, Z. 210-266):**
- `basis.produktbeschreibung` (Z. 224)
- `basis.unternehmen` (Z. 226)
- `zielgruppe.vorwissen` (Z. 229)
- `zielgruppe.entscheidungsverhalten` (Z. 230)
- `kaufsignale[]` ✅ (nur hier gelesen!, Z. 233-238)
- `schmerzen.schmerzpunkte` (Z. 239-245)
- `wettbewerber[]` (Z. 246-250)
- `uebergaenge[]` ✅ (nur hier gelesen!, Z. 251-255)
- `phasen[]` + aktuelle Phase aus `ls.aktive_phase_idx` (Z. 256-261)
- `ki.ansprache` (Z. 262)
- `ki.zusatz` (Z. 263)

**NICHT gelesen:** Einwaende-Array, usps, konsequenz, branche, branche_kontext, eigene_formulierungen, beweise, opener, pitch, nogos, techniken, tabu_begriffe, faqs, consent_text, precall.

### Pfad 12: Post-Call Coach (Sonnet)

**Funktion:** `coaching_service.generate_postcall_analysis` (Zeile 49)

**Gelesen aus Profil:** **NICHTS.** Nur aus der Conversation (einwaende-Events, kaufsignale-Events, painpoints, kb_start/end, redeanteil, ga_details). `profile_data` wird als Parameter entgegen genommen, aber im `POSTCALL_PROMPT` Template nicht referenziert — hat kein `{profile_context}` Placeholder.

### Pfad 13: Lernkarten-Validierung

**Funktion:** `coaching_service.validate_user_text` (Zeile 144)

**Gelesen aus Profil:** NICHTS. Nur `lernziel` + `user_text`.

---

## Matrix: Feld × Pfad × Status

Legende: **✅** integriert · **⚠️** teilweise/indirekt · **❌** nicht integriert · **N/A** irrelevant

Hinweis 08.8: Alle ehemaligen 🧟 Zombie-Code-Eintraege sind jetzt ❌ (sauber entfernt). `_build_system_prompt` ist seit Phase 08.8 tatsaechlich geloescht — kein Zombie-Code mehr in der Codebase.

| Profil-Feld | 1-2 EWB-Live | 3 Manual-Btn | 4 Unknown-EWB | 5 Klassif | 6 FAQ-Match | 7 KW-Match | 8 Training-Kunde | 10 PreCall | 11 Coach-Live | 12 Postcall |
|---|---|---|---|---|---|---|---|---|---|---|
| `basis.name` | ❌ | ❌ | ❌ | N/A | N/A | N/A | ❌ | ❌ | ❌ | ❌ |
| `basis.branche` (Enum) | ❌ | ❌ | ❌ | N/A | N/A | N/A | ⚠️ (nur in personality-Pfad, flach) | ❌ | ❌ | ❌ |
| `basis.branche_kontext` | ✅ | ❌ | ❌ | N/A | N/A | N/A | ❌ | ❌ | ❌ | ❌ |
| `basis.unternehmen` | ✅ | ❌ | ❌ | N/A | N/A | N/A | ❌ | ❌ | ✅ | ❌ |
| `basis.produktbeschreibung` | ✅ | ❌ | ❌ | N/A | N/A | N/A | ✅ | ✅ | ✅ | ❌ |
| `basis.preismodell` | ✅ | ❌ | ❌ | N/A | N/A | N/A | ❌ | ❌ | ❌ | ❌ |
| `basis.usps` | ✅ | ❌ | ❌ | N/A | N/A | N/A | ❌ | ✅ | ❌ | ❌ |
| `basis.konsequenz` | ✅ | ❌ | ❌ | N/A | N/A | N/A | ❌ | ❌ | ❌ | ❌ |
| `basis.eigene_formulierungen` | ✅ | ❌ | ❌ | N/A | N/A | N/A | ❌ | ❌ | ❌ | ❌ |
| `basis.beweise` | ✅ | ❌ | ❌ | N/A | N/A | N/A | ❌ | ❌ | ❌ | ❌ |
| `basis.tabu_begriffe` | ✅ | ❌ | ✅ | N/A | N/A | N/A | ❌ | ❌ | ❌ | ❌ |
| `opener` (top-level) | ❌ | ❌ | ❌ | N/A | N/A | N/A | ❌ | ✅ | ❌ | ❌ |
| `erlaubnis` | ❌ | ❌ | ❌ | N/A | N/A | N/A | ❌ | ❌ | ❌ | ❌ |
| `pitch` (top-level) | ❌ | ❌ | ❌ | N/A | N/A | N/A | ❌ | ✅ | ❌ | ❌ |
| `zielgruppe.alter` | ❌ | ❌ | ❌ | N/A | N/A | N/A | ❌ | ❌ | ❌ | ❌ |
| `zielgruppe.berufsstatus` | ❌ | ❌ | ❌ | N/A | N/A | N/A | ❌ | ✅ | ❌ | ❌ |
| `zielgruppe.einkommensniveau` | ❌ | ❌ | ❌ | N/A | N/A | N/A | ❌ | ❌ | ❌ | ❌ |
| `zielgruppe.lebenssituation` | ❌ | ❌ | ❌ | N/A | N/A | N/A | ❌ | ❌ | ❌ | ❌ |
| `zielgruppe.beruflicher_hintergrund` | ❌ | ❌ | ❌ | N/A | N/A | N/A | ❌ | ❌ | ❌ | ❌ |
| `zielgruppe.vorwissen` | ❌ | ❌ | ❌ | N/A | N/A | N/A | ✅ | ❌ | ✅ | ❌ |
| `zielgruppe.entscheidungsverhalten` | ❌ | ❌ | ❌ | N/A | N/A | N/A | ✅ | ❌ | ✅ | ❌ |
| `einwaende[].einwand` | ❌ | ⚠️ (nur wenn Button matcht) | ❌ | N/A | N/A | ⚠️ (Alias-Match) | ✅ (6 Einw.) | ❌ | ❌ | ❌ |
| `einwaende[].varianten` | ❌ | ❌ | ❌ | N/A | N/A | ❌ | ✅ | ❌ | ❌ | ❌ |
| `einwaende[].gegenargument` | ❌ | ✅ (wenn Button) | ⚠️ (nur build_protected_words) | N/A | N/A | ✅ (direkt ausgespielt) | ❌ | ❌ | ❌ | ❌ |
| `einwaende[].technik` | ❌ | ❌ | ❌ | N/A | N/A | ❌ | ❌ | ❌ | ❌ | ❌ |
| `einwaende[].intensitaet` | ❌ | ❌ | ❌ | N/A | N/A | ❌ | ❌ | ❌ | ❌ | ❌ |
| `einwaende[].kurzlabel` | ❌ | ❌ | ❌ | N/A | N/A | ✅ (Alias) | ❌ | ❌ | ❌ | ❌ |
| `einwaende[].kategorie` | ❌ | ❌ | ❌ | N/A | N/A | ✅ (Alias) | ❌ | ❌ | ❌ | ❌ |
| `faqs[].frage_muster` | ❌ | ❌ | ❌ | N/A | ✅ | N/A | ❌ | ❌ | ❌ | ❌ |
| `faqs[].antwort` | ❌ | ❌ | ❌ | N/A | ✅ | N/A | ❌ | ❌ | ❌ | ❌ |
| `kaufsignale[]` | ❌ | ❌ | ❌ | N/A | N/A | N/A | ❌ | ❌ | ✅ | ⚠️ (aus Event-Log) |
| `nogos[]` | ❌ | ❌ | ❌ | N/A | N/A | N/A | ❌ | ❌ | ❌ | ❌ |
| `wettbewerber[]` | ❌ | ❌ | ❌ | N/A | N/A | N/A | ✅ | ❌ | ✅ | ❌ |
| `uebergaenge[]` | ❌ | ❌ | ❌ | N/A | N/A | N/A | ❌ | ❌ | ✅ | ❌ |
| `techniken.aktiv` | ❌ | ❌ | ❌ | N/A | N/A | N/A | ❌ | ❌ | ❌ | ❌ |
| `techniken.verboten` | ❌ | ❌ | ❌ | N/A | N/A | N/A | ❌ | ❌ | ❌ | ❌ |
| `techniken.offene_fragen` | ❌ | ❌ | ❌ | N/A | N/A | N/A | ❌ | ❌ | ❌ | ❌ |
| `schmerzen.trigger` | ❌ | ❌ | ❌ | N/A | N/A | N/A | ❌ | ❌ | ❌ | ❌ |
| `schmerzen.schmerzpunkte` | ❌ | ❌ | ❌ | N/A | N/A | N/A | ✅ (1. Pkt) | ❌ | ✅ | ❌ |
| `phasen[]` | ❌ | ❌ | ❌ | N/A | N/A | N/A | ❌ | ❌ | ✅ | ❌ |
| `ki.ton` | ✅ | ❌ | ❌ | N/A | N/A | N/A | ❌ | ❌ | ❌ | ❌ |
| `ki.stil` | ❌ | ❌ | ❌ | N/A | N/A | N/A | ❌ | ❌ | ❌ | ❌ |
| `ki.ansprache` | ✅ (Anrede-Resolution, voller Wert) | ❌ | ✅ (Anrede) | N/A | N/A | N/A | ✅ | ❌ | ✅ | ❌ |
| `ki.antwortlaenge` | ❌ | ❌ | ❌ | N/A | N/A | N/A | ❌ | ❌ | ❌ | ❌ |
| `ki.sensitivitaet` | ❌ | ❌ | ❌ | N/A | N/A | N/A | ❌ | ❌ | ❌ | ❌ |
| `ki.zusatz` | ❌ | ❌ | ❌ | N/A | N/A | N/A | ❌ | ❌ | ✅ | ❌ |
| `consent_text` | ❌ | ❌ | ❌ | N/A | N/A | N/A | ❌ | ❌ | ❌ | ❌ |
| `ls.state['precall_briefing']` | ❌ | ❌ | ❌ | N/A | N/A | N/A | ❌ | N/A (Output) | ❌ | ❌ |
| `aktives_skript_inhalt` + `skript_bloecke` | ❌ | ❌ | ❌ | N/A | N/A | N/A | ❌ | ❌ | ❌ | ❌ |

---

## Findings — sortiert nach Wirkung

### 🔴 Kritisch (direkt gegen Andrés Bauchgefühl)

1. **`_build_system_prompt` ist seit Phase 08.8 tatsaechlich geloescht** (nicht mehr nur dead code, sondern aus dem Codebase entfernt). Alle Felder die nur hier eingebaut waren sind **effektiv tatsaechlich absent**: `nogos`, `wettbewerber` (ex-EWB), `uebergaenge` (ex-EWB), `techniken_*`, `schmerzen.trigger`, `ki.antwortlaenge`, `ki.sensitivitaet`, `ki.zusatz` (ex-EWB), Einwaende-Array als Liste, Lerndaten-Erfolgsquoten, `precall_briefing`, `aktives_skript`. Alle ehemaligen Zombie-Eintraege (🧟) sind sauber ❌.

2. **Einwaende-Array wird im EWB-Prompt NICHT gezeigt.** Die grossen `einwaende[]` Objekte mit `einwand`, `varianten`, `gegenargument`, `technik`, `intensitaet` sind im Live-Prompt UNSICHTBAR. Das LLM "sieht" nur USPs, Beweise, eigene Formulierungen, Tabus — aber nicht die konkreten Gegenargumente des Users. Matcht der Keyword-Matcher einen Treffer, wird das Gegenargument direkt ausgespielt (LLM umgangen). Matcht er nicht (neuer Einwand, anders formuliert), hat das LLM keine Referenz.

3. **PreCall-Briefing fliesst nicht in EWB ein.** Brave-Research + Haiku-Briefing laeuft, wird in UI angezeigt und in `ls.state['precall_briefing']` geparkt — aber weder `build_profile_context` noch `build_ewb_prompt` lesen es. Frueherer Injektionspunkt (`_build_system_prompt`) ist seit 08.8 geloescht.

4. **Manual-Button-Klick-Variante hat keinen Profil-Kontext.** `streame_manual_ewb_variante` (Z. 638) nutzt hardcoded "Du bist ein erfahrener Sales-Coach…". Weder `ton`, `ansprache`, `usps`, `beweise`, `tabu_begriffe` kommen an. Nur das eine Profil-Gegenargument wird im User-Msg beigegeben.

5. **Unknown-Einwand-Antwort (QA-Pipeline, Phase 08.5) hat fast keinen Profil-Kontext.** LB-3 Fix (08.9) hat die Parameteruebergabe korrekt gemacht, aber KEINE neuen Felder in den Prompt gebracht. Nur Tabu-Block + Anrede. Keine USPs, keine Beweise, keine Branche, kein Ton.

### 🟡 Mittelschwer

6. **`opener` / `pitch` liegen auf Top-Level, nicht unter `leitfaden.*`.** Schema-Inkonsistenz zwischen Profil-Editor-UI (gruppiert als "Leitfaden") und DB-Struktur. Einzige Stelle die sie liest: PreCall (Z. 150-151) — und die liest `profil_daten.get('opener')` flach, nicht `leitfaden.opener`.

7. **`erlaubnis` wird NIRGENDS gelesen.** Komplett totes Feld im Profil-Editor.

8. **`consent_text` wird NIRGENDS gelesen.** Meeting-Modus-Consent-Vorlesetext steht im Profil, wird in UI angezeigt, aber kein Prompt referenziert ihn. (Evtl. nur fuer UI — akzeptabel, sollte dokumentiert werden.)

9. **Zielgruppe fast vollstaendig tot im EWB-Prompt.** Von 7 Zielgruppe-Feldern: 0 in EWB, 2 in Training-Kunde, 2 in Coaching-Live, 1 in PreCall. `alter`, `einkommen`, `lebenssituation`, `hintergrund` werden NIRGENDS im Live-Pfad gelesen.

10. **`ki.stil` wird NIRGENDS gelesen.** Getrennt von `ki.ton` (welches nur in EWB gelesen wird). Dupletten-Verdacht — bestaetigt Andrés Kritik "`eigene_formulierungen` ueberschneidet sich mit ton/stil".

11. **`techniken_aktiv` / `techniken_verboten` / `offene_fragen` (Fliesstext) — alles tot.**

12. **`kaufsignale` nur im Coaching-Live (separater Prompt, kein EWB).** Postcall-Coach nutzt nur die Events aus der Conversation, nicht die Profil-Definitionen.

13. **`nogos` — vollstaendig tot.** War in _build_system_prompt, jetzt geloescht. Kein Pfad liest nogos.

14. **`wettbewerber` lebt nur noch in Coaching-Live + Training-Kunde.** EWB ignoriert vollstaendig.

15. **Postcall-Coach nutzt `profile_data` Parameter, aber referenziert ihn im Prompt nicht.** `POSTCALL_PROMPT` hat kein `{profile_context}` Placeholder. Argument-Boilerplate, null Effekt.

### 🟢 Funktioniert wie dokumentiert

16. **Phase 08-Erweiterungen (`branche_kontext`, `eigene_formulierungen`, `beweise`) sind korrekt integriert** im Live-EWB-Pfad. ✅

17. **Tabu-Begriffe-System (Phase 08.5 Korrektur 1+3)** sauber in EWB + QA-Response integriert mit Safety-Net. ✅

18. **Keyword-Matcher + Einwand-Alias-Match** funktioniert unabhaengig vom LLM — stabil, deterministisch, <1ms Latenz. ✅

19. **Phase 08.13 Block E (claude_client-Konsolidierung):** Kein neuer Inline-Client irgendwo — alle 5 Module nutzen shared `claude_client` aus claude_service. system= als separater Kwarg in allen API-Calls. Keine Aenderung an welche Felder gelesen werden. ✅

---

## Tote Felder — Kandidaten für Entfernung oder Re-Integration

| Feld | Aktueller Status | Empfehlung |
|---|---|---|
| `basis.name` | Nie in Prompt | Entfernen (nur UI-Anzeige fuer User, kein LLM-Bedarf) |
| `basis.branche` (Enum) | Nie in Prompt | Entweder in EWB-Kontext rein ODER entfernen |
| `opener` | Nur in PreCall | In EWB-Prompt aufnehmen ODER klar als "nur Teleprompter-UI" positionieren |
| `erlaubnis` | Nirgends | Entfernen oder in EWB aufnehmen |
| `pitch` | Nur in PreCall | Wie `opener` |
| `zielgruppe.alter` | Nirgends live | Entfernen ODER in EWB+Training+PreCall aufnehmen |
| `zielgruppe.einkommensniveau` | Nirgends live | Wie oben |
| `zielgruppe.lebenssituation` | Nirgends live | Wie oben |
| `zielgruppe.beruflicher_hintergrund` | Nirgends live | Wie oben |
| `zielgruppe.vorwissen` | Nur Training + Coaching | In EWB aufnehmen (wichtig fuer Tiefe der Antwort) |
| `zielgruppe.entscheidungsverhalten` | Nur Training + Coaching | In EWB aufnehmen |
| `einwaende[].varianten` | Nur Training | In EWB-Prompt aufnehmen als Fallback-Liste wenn Keyword nicht matcht |
| `einwaende[].gegenargument` | Nur via KW-Match direkt + Manual-Btn | In EWB-Prompt als Referenz-Liste aufnehmen |
| `einwaende[].technik` | Nirgends live | In EWB aufnehmen ODER entfernen |
| `einwaende[].intensitaet` | Nirgends live | Entfernen oder nutzen |
| `faqs[]` | Nur FAQ-Match | Optional in EWB-Prompt als Zusatz-Kontext |
| `kaufsignale[]` | Nur Coaching-Live | In EWB oder entfernen (eigentlich aber Coach-Job, passt dort) |
| `nogos[]` | Nirgends live (tatsaechlich absent seit 08.8) | In EWB aufnehmen (kritisch: KI sollte nicht bei No-Go-Profilen pitchen) |
| `wettbewerber[]` | Nur Coaching + Training | In EWB aufnehmen (wichtig wenn Kunde Konkurrent erwaehnt) |
| `uebergaenge[]` | Nur Coaching-Live | OK dort, aber evtl auch im EWB fuer Abschluss-Trigger |
| `techniken_aktiv` | Nirgends live | In EWB aufnehmen oder entfernen |
| `techniken_verboten` | Nirgends live | In EWB aufnehmen (wichtig — "sagt NIE diese Phrase") |
| `offene_fragen` (Fliesstext) | Nirgends live | Schema-Klaerung: Liste oder Fliesstext? Aktuell nie gelesen. |
| `schmerzen.trigger` | Nirgends live | **Entfernen** — grosses schickes Slider-UI ohne Wirkung |
| `schmerzen.schmerzpunkte` | Training + Coaching | OK dort, evtl. auch in EWB |
| `ki.stil` | Nirgends live | Mit `ki.ton` zusammenlegen oder entfernen |
| `ki.antwortlaenge` | Nirgends live | In EWB aufnehmen (direkt relevant) oder entfernen |
| `ki.sensitivitaet` | Nirgends live | In EWB aufnehmen oder entfernen |
| `ki.zusatz` | Nur Coaching-Live | In EWB aufnehmen (User hat darauf Zugriff als "freie KI-Instruktion" — sollte ueberall gelten) |
| `consent_text` | Nirgends gelesen | Dokumentieren dass es UI-only ist |
| `precall_briefing` (State, nicht Profil) | Nicht in EWB | **Re-Integrieren** — urspruengliche Intention |
| `aktives_skript` | Nicht in EWB | Re-Integrieren oder Skript-Feature abbauen |

---

## Verifikation Andrés Verdacht-Liste (2026-04-27)

| Feld | Andrés Verdacht | Verifikation | Fund (Datei:Zeile) |
|------|----------------|--------------|-------------------|
| `kaufsignale` | tot | ❌ WIDERLEG: lebt in Coaching-Live | claude_service.py:218 (_build_coaching_prompt) |
| `nogos` | tot | ✅ BESTAETIGT TOT | Nicht in services/ oder core/ gefunden |
| `wettbewerber` | tot | ❌ WIDERLEG: lebt in Training + Coaching | claude_service.py:220, training_service.py:577 |
| `uebergaenge` | tot | ❌ WIDERLEG: lebt in Coaching-Live | claude_service.py:219 |
| `offene_fragen` | tot | ✅ BESTAETIGT TOT | Nicht in services/ gefunden |
| `vorwissen` | tot | ❌ WIDERLEG: lebt in Training + Coaching | claude_service.py:229, training_service.py:593 |
| `entscheidungsverhalten` | tot | ❌ WIDERLEG: lebt in Training + Coaching | claude_service.py:230, training_service.py:597 |
| `hintergrund` / `beruflicher_hintergrund` | tot | ✅ BESTAETIGT TOT | Nicht in services/ gefunden |
| `techniken_verboten` | tot | ✅ BESTAETIGT TOT | Nicht in services/ gefunden |
| `antwortlaenge` | tot | ✅ BESTAETIGT TOT | Nicht in services/ gefunden |
| `sensitivitaet` | tot | ✅ BESTAETIGT TOT | Nicht in services/ gefunden |

## Top-Ueberraschungen

**Ueberraschung 1 — kaufsignale lebt:** Andrés Verdacht war "tot". Realitaet: kaufsignale wird von `_build_coaching_prompt` (claude_service.py Z. 218) aktiv gelesen und in den Coaching-Live-Prompt injiziert. Lebt also im Coach-Pfad, nur nicht im EWB-Pfad.

**Ueberraschung 2 — wettbewerber lebt in 2 Pfaden:** Andrés Verdacht war "tot". Realitaet: Wettbewerber werden in Coaching-Live (Z. 220) UND Training-Kunden-Simulation (training_service.py Z. 577) gelesen. EWB ignoriert sie komplett — das ist das eigentliche Problem.

**Ueberraschung 3 — uebergaenge lebt im Coach:** Andrés Verdacht war "tot". Realitaet: `uebergaenge[]` wird in `_build_coaching_prompt` (Z. 219) gelesen — inkl. `von`, `nach`, `bruecke`-Felder. Lebt also im Coaching-Pfad.

**Ueberraschung 4 — vorwissen + entscheidungsverhalten leben doppelt:** Beide Felder sind in Training-Kunde-Simulation (training_service.py) UND Coaching-Live (claude_service.py) aktiv — nur im EWB-Pfad nicht.

---

## Wichtigste Architektur-Fehler

1. **`build_profile_context` ist bewusst minimalistisch** (Phase 08 Intent: schlanker Prompt fuer Baustein-Struktur) — aber inzwischen fehlen dadurch alle Profil-Felder die dem LLM Kontext geben wuerden. Die Baustein-Logik ist ohne Einwaende/Varianten/Wettbewerber/No-Gos limitiert.

2. **Keyword-Matcher vs. LLM-Generation sind nicht integriert.** Wenn KW matcht → Gegenargument direkt ausgespielt (gut, schnell). Wenn KW nicht matcht → LLM hat keine Einwand-Liste als Referenz. → Klassisches Hybrid-System-Problem.

3. **Manual-Button-Pfad (`streame_manual_ewb_variante`) nutzt einen komplett anderen System-Prompt** als die Auto-EWB. Inkonsistenter Stil zwischen Auto und Manual.

4. **QA-Pipeline (Phase 08.5) teilt sich `build_profile_context` nicht.** Sie hat nur Tabu-Block + Anrede. Hat also noch weniger Kontext als die EWB. LB-3 Fix hat nur die Parameteruebergabe gefixt, nicht den inhaltlichen Profil-Kontext erweitert.

5. **PreCall-Briefing** wird generiert und angezeigt, aber von keinem LLM-Pfad mehr gelesen.

---

## Offene Fragen (fuer Klaerung vor Phase 08.18/08.19)

1. Ist `aktives_skript` (Teleprompter) noch ein aktives Feature? Wenn ja: wird es aktuell irgendwo im LLM genutzt?
2. Soll PreCall-Briefing automatisch in EWB fliessen oder nur auf User-Toggle?
3. Sind `opener`/`pitch` Top-Level oder `leitfaden.*`-Feld? DB-Schema vs. Editor-UI klaeren.
4. Soll der QA-Pipeline Pfad 4 inhaltlichen Profil-Kontext bekommen (Phase 08.19 Task)?
5. Soll `ki.zusatz` ("freie KI-Instruktion") auch im EWB gelten oder nur im Coach?

---

## Datenbasis fuer Phase B/C

- **Dead fields count (post 08.8):** ~14 definitiv nie in Live-Prompt (nirgends-Kategorie — kein Zombie mehr, tatsaechlich absent)
- **Partial fields:** ~11 (nur in einem der Pfade oder indirekt / ⚠️)
- **Voll integriert im EWB (dem wichtigsten Pfad):** **10 Felder** (unverändert zu v1)
- **Gesamte Profil-Felder (gezaehlt):** **~48**
- **→ EWB-Integration-Quote: 10/48 = 21%** (unveraendert zu v1 — kein neuer Kontext durch 08.8-08.14)
- → Andrés "gefuehlt 90% kommen nicht an" ist real. Realwert: **~79% der Profil-Felder kommen nicht in den EWB-Prompt.**

**Hinweis: Audit verifiziert gegen Post-08.14 Code-Stand (2026-04-27)**

---

*Audit v1 abgeschlossen 2026-04-24 durch Code-Reading von services/ewb_pipeline.py, prompt_pipeline.py, qa_pipeline.py, claude_service.py, training_service.py, precall_service.py, coaching_service.py, einwand_keyword_matcher.py.*

*Audit v2 aktualisiert 2026-04-27 durch vollstaendige Re-Verifikation aller 7 Dateien + Breit-Grep services/ nach Phasen 08.8-08.14 Aenderungen. Neue Dateien: keine (kein core/-Verzeichnis, keine neuen prompt_utils.py / context_builder.py). Alle Deltas A-F verifiziert. Andrés Verdacht-Liste komplett durchgeprueft.*
