---
audit: profil-prompt-integration
phase: A
erstellt: 2026-04-24
autor: Claudian
stand_code: salesnerve/ HEAD 2026-04-24 (nach Phase 08.5 Fix-Runs)
zweck: Matrix über welche Profil-Felder in welchem Prompt-Pfad landen. Basis für Profil-Redesign.
---

# Profil-Prompt-Integrations-Audit — Matrix + Findings

## TL;DR für André

**Dein Bauchgefühl stimmt: ca. 50-60% der Profil-Felder landen niemals in einem Live-Prompt. Die EWB (PiP-Kasten) nutzt extrem wenig.** Konkret:

1. Der alte große System-Prompt (`_build_system_prompt`) mit allen Feldern — Einwände, Zielgruppe, Wettbewerber, No-Gos, Übergänge, KI-Stil-Details — **wird nicht mehr aufgerufen**. Nur noch im Code stehen. Seit Phase 08 läuft die Live-EWB über `build_ewb_prompt` → `build_profile_context`, das nur ca. 10 Felder liest.
2. Das **PreCall-Briefing fließt NICHT mehr in den EWB-Prompt** — früher über ls.state['precall_briefing'] in `_build_system_prompt`, jetzt tot. Deine Recherche landet nur noch in der UI, nicht im LLM.
3. Der **Manual-EWB-Button-Klick-Pfad** (`streame_manual_ewb_variante`) hat einen HARDCODED Coach-Prompt ohne jeden Profil-Kontext. Nur das eine Profil-Gegenargument wird in den User-Message gepackt.
4. Die Einwände-Liste (mit `einwand`, `varianten`, `gegenargument`, `technik`, `intensitaet`) ist im **Live-EWB-Prompt NICHT enthalten**. Nur über Keyword-Matcher (Regex) wird bei Treffer das entsprechende Gegenargument direkt ausgespielt — aber das LLM sieht die Liste nicht und kann sie nicht nutzen wenn kein Keyword matcht.
5. FAQs (Phase 08.5) werden **nur im FAQ-Match-Pfad** verwendet (Embedding-Vergleich) — nicht als Kontext im EWB-Prompt.

---

## Prompt-Pfade — Was sie tatsächlich lesen

Aus Code-Analyse (services/*.py):

### Pfad 1: Cold-Call Live-EWB (Haiku, Hauptsystem)

**Funktion:** `claude_service.analysiere_mit_claude` / `analysiere_mit_claude_streaming` (Zeile 647 / 704)

**System-Prompt:** `build_ewb_prompt(version, user_id)` → lädt Template aus DB (module='ewb') + `build_profile_context()` (prompt_pipeline.py)

**User-Message:** Enthält `kontext` (letzte Transkript-Zeilen) + `neuer_text` (aktuelle Utterance).

**Gelesen aus Profil:**
- `basis.unternehmen`
- `basis.produktbeschreibung`
- `basis.preismodell`
- `basis.usps`
- `basis.konsequenz`
- `basis.branche_kontext` (Phase 08 D-11)
- `basis.eigene_formulierungen` (Phase 08 D-07)
- `basis.beweise` (Phase 08 D-08)
- `basis.tabu_begriffe` (über `build_tabu_instruction`, Phase 08.5 Korrektur 1)
- `ki.ton`
- `ki.ansprache` (nur für Anrede-Gate, sonst ungenutzt)
- **Session-Overrides:** `ls.state['session_anrede']`

**NICHT gelesen (tot im Live-EWB-Prompt):**
- `basis.name` (Nutzername)
- `basis.branche` (Enum!)
- `opener`, `erlaubnis`, `pitch`
- ALLE Zielgruppe-Felder (`alter`, `berufsstatus`, `einkommen`, `lebenssituation`, `hintergrund`, `vorwissen`, `entscheidung`)
- `einwaende[]` (die Array-Liste mit Gegenargumenten — **nur über Keyword-Matcher, siehe unten**)
- `faqs[]`
- `kaufsignale`, `nogos`, `wettbewerber`, `uebergaenge`
- `techniken_aktiv`, `techniken_verboten`, `offene_fragen`
- `ki.stil`, `ki.antwortlaenge`, `ki.sensitivitaet`, `ki.zusatz`
- `schmerzen.trigger`, `schmerzen.schmerzpunkte`
- `consent_text`
- **`ls.state['precall_briefing']`** — PreCall-Recherche-Ergebnis fließt NICHT mehr rein

### Pfad 2: Meeting-Modus Live-EWB

**Gleicher Pfad wie Cold-Call** (`analysiere_mit_claude*`). Deepgram-Diarisierung gibt im Meeting-Modus sowohl Berater- als auch Kunden-Utterances. System-Prompt identisch — **dieselben Felder wie Pfad 1**.

### Pfad 3: Manual-EWB-Button-Klick (Slot-1-Variante)

**Funktion:** `claude_service.streame_manual_ewb_variante` (Zeile 897)

**System-Prompt:** HARDCODED — `"Du bist ein erfahrener Sales-Coach im DACH-B2B. Antworte knapp, praktisch, menschlich..."`. **Kein Profil-Kontext.**

**User-Message:** Enthält typ-Name + `profile_einwand.gegenargument_1` (oder `gegenargument`/`text`) + `kontext` (Gesprächsverlauf).

**Gelesen aus Profil:**
- `einwaende[].gegenargument_1` (bzw. `gegenargument`/`text`) für den geklickten Typ (im User-Msg)

**NICHT gelesen:** ALLES andere. Keine `ton`, keine `ki_ansprache`, keine `usps`, keine `beweise`, keine `tabu_begriffe`. **Button-Pfad umgeht das ganze Profil.**

### Pfad 4: Unknown-Einwand-Antwort / Rückfrage-Generator (Phase 08.5)

**Funktion:** `qa_pipeline.generate_qa_response` (Zeile 364)

**System-Prompt:** `_SYSTEM_PROMPT_QA` Template + `build_tabu_instruction(profile_data)` für Tabu-Block.

**Gelesen aus Profil:**
- `basis.tabu_begriffe` (Tabu-Instruction + Safety-Net)
- `einwaende[].gegenargument*` (nur für `build_protected_words` — Schutz von User-Wörtern vor Tabu-Filter)
- `anrede` (Session-Override)

**NICHT gelesen:** Alle Basis-Felder (`unternehmen`, `produkt`, `usps`, `beweise`, `eigene_formulierungen`), Zielgruppe, FAQs, Wettbewerber, etc.

**→ Kritisch:** Der Unknown-Einwand-Antworter hat KEINE Ahnung wer der User ist oder was er verkauft. Nur Tabu-Wörter + Anrede. Kein Wunder dass "Frag nach: Wie meinen Sie das genau?" generisch wird.

### Pfad 5: Klassifikator (Phase 08.5)

**Funktion:** `qa_pipeline.classify_utterance` (Zeile 285)

**System-Prompt:** Fixes Template (`_FALLBACK_CLASSIFIER_PROMPT`). **Keine Profil-Integration.** Klassifiziert rein semantisch.

**Gelesen aus Profil:** NICHTS.

### Pfad 6: FAQ-Match (Phase 08.5)

**Funktion:** `qa_pipeline.match_faq` (Zeile 484)

**Kein LLM-Call** — sentence-transformers Embedding-Vergleich.

**Gelesen aus Profil:**
- `faqs[].frage_muster` (für Embedding)
- `faqs[].antwort` (wird returned — wird ausgespielt, nicht in einem Prompt)

### Pfad 7: Einwand-Keyword-Matcher (pre-LLM Regex)

**Funktion:** `einwand_keyword_matcher.match_keyword`

**Kein LLM-Call** — Regex-Match auf Keyword-Tabelle, mapped auf Einwand-Kategorie, zieht `gegenargument_1`/`gegenargument`/`text` aus Profil-Einwand und spielt direkt in Slot 0 aus (client-side). Umgeht LLM komplett.

**Gelesen aus Profil:**
- `einwaende[].kurzlabel` / `kategorie` / `typ` (für Alias-Match)
- `einwaende[].gegenargument*` (wird direkt ausgespielt)

**NICHT gelesen:** varianten, technik, intensitaet der Einwände.

### Pfad 8: Training-Modus Kunden-Simulation

**Funktion:** `training_service.build_customer_prompt` (Zeile 569)

**Gelesen aus Profil:**
- `basis.produktbeschreibung`
- `zielgruppe.vorwissen` (wirkt nur wenn 'hoch' oder 'gering')
- `zielgruppe.entscheidungsverhalten`
- `einwaende[]` — erste 6 mit `einwand` + `varianten`
- `wettbewerber[].name` (erste 3)
- `ki.ansprache`
- `schmerzen.schmerzpunkte[0].situation`

**NICHT gelesen:** `unternehmen`, `usps`, `konsequenz`, `branche_kontext`, `eigene_formulierungen`, `beweise`, `opener`/`pitch`, `faqs`, `kaufsignale`, `nogos`, `uebergaenge`, `techniken_*`, `ton`, `antwortlaenge`, `sensitivitaet`, `zusatz`, `tabu_begriffe`, `consent_text`.

### Pfad 8b: Training-Modus Personality-Prompt (Phase 04.9)

**Funktion:** `training_service.build_personality_prompt` (Zeile 724)

**Gelesen aus Profil:**
- `produkt` (flach, nicht `basis.produktbeschreibung`)
- `branche` (flach)
- `einwaende[]`

**Rest kommt aus `personality_data`-Tabelle** (separate Trainings-Personas, kein Verkaufsprofil). NICHT gelesen werden die meisten Profil-Felder.

### Pfad 9: Training-Modus Scoring

**Template:** `_SCORING_FALLBACK_TEMPLATE` — generisch, **keine Profil-Integration.** Scoring-Prompt wird zur Laufzeit mit `gespraech`, `einwaende`, `kaufsignale` aus der Session gefüttert, aber das Profil-Schema selbst wird nicht referenziert.

### Pfad 10: PreCall-Briefing (Brave Search + Haiku)

**Funktion:** `precall_service.recherche_firma` / `_generiere_briefing` (Zeile 127)

**Gelesen aus Profil:**
- `basis.produktbeschreibung`
- `basis.usps`
- `zielgruppe.berufsstatus`
- `opener` (TOP-LEVEL, nicht unter leitfaden — Schema-Inkonsistenz!)
- `pitch` (TOP-LEVEL)

**NICHT gelesen:** Rest.

**Kritisch:** Das Ergebnis (`briefing_dict`) wird in der UI angezeigt und in `ls.state['precall_briefing']` geschrieben — aber von KEINEM der Live-LLM-Pfade mehr gelesen. Der eine Pfad der es nutzte (`_build_system_prompt`) ist **dead code**.

### Pfad 11: Coaching-Live (Haiku, separat vom EWB)

**Funktion:** `claude_service.analysiere_coaching` (Zeile 1006) → `_build_coaching_prompt` (Zeile 404)

**Gelesen aus Profil:**
- `basis.produktbeschreibung`
- `basis.unternehmen`
- `zielgruppe.vorwissen`, `entscheidungsverhalten`
- `kaufsignale[]` ✅ (nur hier gelesen!)
- `schmerzen.schmerzpunkte`
- `wettbewerber[]`
- `uebergaenge[]` ✅ (nur hier gelesen!)
- `phasen[]` + aktuelle Phase aus `ls.aktive_phase_idx`
- `ki.ansprache`, `ki.zusatz`

**NICHT gelesen:** Einwände-Array, usps, konsequenz, branche, branche_kontext, eigene_formulierungen, beweise, opener, pitch, nogos, techniken, tabu_begriffe, faqs, consent_text, precall.

### Pfad 12: Post-Call Coach (Sonnet)

**Funktion:** `coaching_service.generate_postcall_analysis` (Zeile 51)

**Gelesen aus Profil:** **NICHTS.** Nur aus der Conversation (einwaende-Events, kaufsignale-Events, painpoints, kb_start/end, redeanteil, ga_details). `profile_data` wird als Parameter entgegen genommen, aber im Prompt nicht verwendet (Argument wird gesetzt, aber `POSTCALL_PROMPT` referenziert es nicht).

### Pfad 13: Lernkarten-Validierung

**Funktion:** `coaching_service.validate_user_text` (Zeile 145)

**Gelesen aus Profil:** NICHTS. Nur `lernziel` + `user_text`.

---

## Matrix: Feld × Pfad × Status

Legende: **✅** integriert · **⚠️** teilweise/indirekt · **❌** nicht integriert · **N/A** irrelevant · **🧟** Zombie-Code (nur in dead `_build_system_prompt`)

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
| `einwaende[].einwand` | ❌ (🧟 tot) | ⚠️ (nur wenn Button matcht) | ❌ | N/A | N/A | ⚠️ (Alias-Match) | ✅ (6 Einw.) | ❌ | ❌ | ❌ |
| `einwaende[].varianten` | ❌ (🧟) | ❌ | ❌ | N/A | N/A | ❌ | ✅ | ❌ | ❌ | ❌ |
| `einwaende[].gegenargument` | ❌ (🧟) | ✅ (wenn Button) | ⚠️ (nur build_protected_words) | N/A | N/A | ✅ (direkt ausgespielt) | ❌ | ❌ | ❌ | ❌ |
| `einwaende[].technik` | ❌ (🧟) | ❌ | ❌ | N/A | N/A | ❌ | ❌ | ❌ | ❌ | ❌ |
| `einwaende[].intensitaet` | ❌ (🧟) | ❌ | ❌ | N/A | N/A | ❌ | ❌ | ❌ | ❌ | ❌ |
| `einwaende[].kurzlabel` | ❌ | ❌ | ❌ | N/A | N/A | ✅ (Alias) | ❌ | ❌ | ❌ | ❌ |
| `einwaende[].kategorie` | ❌ | ❌ | ❌ | N/A | N/A | ✅ (Alias) | ❌ | ❌ | ❌ | ❌ |
| `faqs[].frage_muster` | ❌ | ❌ | ❌ | N/A | ✅ | N/A | ❌ | ❌ | ❌ | ❌ |
| `faqs[].antwort` | ❌ | ❌ | ❌ | N/A | ✅ | N/A | ❌ | ❌ | ❌ | ❌ |
| `kaufsignale[]` | ❌ | ❌ | ❌ | N/A | N/A | N/A | ❌ | ❌ | ✅ | ⚠️ (aus Event-Log) |
| `nogos[]` | ❌ (🧟) | ❌ | ❌ | N/A | N/A | N/A | ❌ | ❌ | ❌ | ❌ |
| `wettbewerber[]` | ❌ (🧟) | ❌ | ❌ | N/A | N/A | N/A | ✅ | ❌ | ✅ | ❌ |
| `uebergaenge[]` | ❌ (🧟) | ❌ | ❌ | N/A | N/A | N/A | ❌ | ❌ | ✅ | ❌ |
| `techniken.aktiv` | ❌ (🧟) | ❌ | ❌ | N/A | N/A | N/A | ❌ | ❌ | ❌ | ❌ |
| `techniken.verboten` | ❌ (🧟) | ❌ | ❌ | N/A | N/A | N/A | ❌ | ❌ | ❌ | ❌ |
| `techniken.offene_fragen` | ❌ (🧟) | ❌ | ❌ | N/A | N/A | N/A | ❌ | ❌ | ❌ | ❌ |
| `schmerzen.trigger` | ❌ (🧟) | ❌ | ❌ | N/A | N/A | N/A | ❌ | ❌ | ❌ | ❌ |
| `schmerzen.schmerzpunkte` | ❌ (🧟) | ❌ | ❌ | N/A | N/A | N/A | ✅ (1. Pkt) | ❌ | ✅ | ❌ |
| `phasen[]` | ❌ | ❌ | ❌ | N/A | N/A | N/A | ❌ | ❌ | ✅ | ❌ |
| `ki.ton` | ✅ | ❌ | ❌ | N/A | N/A | N/A | ❌ | ❌ | ❌ | ❌ |
| `ki.stil` | ❌ | ❌ | ❌ | N/A | N/A | N/A | ❌ | ❌ | ❌ | ❌ |
| `ki.ansprache` | ⚠️ (nur Anrede-Gate) | ❌ | ✅ (Anrede) | N/A | N/A | N/A | ✅ | ❌ | ✅ | ❌ |
| `ki.antwortlaenge` | ❌ (🧟) | ❌ | ❌ | N/A | N/A | N/A | ❌ | ❌ | ❌ | ❌ |
| `ki.sensitivitaet` | ❌ (🧟) | ❌ | ❌ | N/A | N/A | N/A | ❌ | ❌ | ❌ | ❌ |
| `ki.zusatz` | ❌ (🧟) | ❌ | ❌ | N/A | N/A | N/A | ❌ | ❌ | ✅ | ❌ |
| `consent_text` | ❌ | ❌ | ❌ | N/A | N/A | N/A | ❌ | ❌ | ❌ | ❌ |
| `ls.state['precall_briefing']` | ❌ (🧟) | ❌ | ❌ | N/A | N/A | N/A | ❌ | N/A (Output) | ❌ | ❌ |
| `aktives_skript_inhalt` + `skript_bloecke` | ❌ (🧟) | ❌ | ❌ | N/A | N/A | N/A | ❌ | ❌ | ❌ | ❌ |

---

## Findings — sortiert nach Wirkung

### 🔴 Kritisch (direkt gegen Andrés Bauchgefühl)

1. **`_build_system_prompt` ist komplett dead code.** Definiert in claude_service.py Z. 265, aber kein Aufruf mehr (nur Tests prüfen dass es existiert). Seit Phase 08 läuft `analysiere_mit_claude*` ausschließlich über `build_ewb_prompt`. → Alle Felder die nur hier eingebaut waren (🧟 in Matrix) sind **effektiv tot**: `nogos`, `wettbewerber`, `uebergaenge`, `techniken_*`, `schmerzen.trigger`, `ki.antwortlaenge`, `ki.sensitivitaet`, `ki.zusatz`, Einwände-Array als Liste, Lerndaten-Erfolgsquoten, `precall_briefing`, `aktives_skript`.

2. **Einwände-Array wird im EWB-Prompt NICHT gezeigt.** Die großen `einwaende[]` Objekte mit `einwand`, `varianten`, `gegenargument`, `technik`, `intensitaet` sind im Live-Prompt UNSICHTBAR. Das LLM "sieht" nur USPs, Beweise, eigene Formulierungen, Tabus — aber nicht die konkreten Gegenargumente des Users. Matcht der Keyword-Matcher einen Treffer, wird das Gegenargument direkt ausgespielt (LLM umgangen). Matcht er nicht (neuer Einwand, anders formuliert), hat das LLM keine Referenz. → Erklärt warum Haiku bei "zu teuer"-Variationen generische Antworten generiert.

3. **PreCall-Briefing fließt nicht in EWB ein.** Brave-Research + Haiku-Briefing läuft, wird in UI angezeigt und in `ls.state['precall_briefing']` geparkt — aber weder `build_profile_context` noch `build_ewb_prompt` lesen es. Früherer Injektionspunkt (`_build_system_prompt` Z. 386-390) ist tot. → Deine Recherche hat Null Einfluss auf das was die KI in der EWB vorschlägt.

4. **Manual-Button-Klick-Variante hat keinen Profil-Kontext.** `streame_manual_ewb_variante` nutzt hardcoded "Du bist ein erfahrener Sales-Coach…". Weder `ton`, `ansprache`, `usps`, `beweise`, `tabu_begriffe` kommen an. Nur das eine Profil-Gegenargument wird im User-Msg beigegeben. → Die Slot-1-Variante ist generisch, auch wenn das Profil detailliert ist.

5. **Unknown-Einwand-Antwort (QA-Pipeline, Phase 08.5) hat fast keinen Profil-Kontext.** Nur Tabu-Block + Anrede. Keine USPs, keine Beweise, keine Branche, kein Ton. → Haiku "erfindet" Rückfragen/Antworten ohne zu wissen was der User verkauft. Erklärt warum der Phase 08.5 Universal Response Loop dünne, generische Rückfragen produziert.

### 🟡 Mittelschwer

6. **`opener` / `pitch` liegen auf Top-Level, nicht unter `leitfaden.*`.** Schema-Inkonsistenz zwischen Profil-Editor-UI (gruppiert als "Leitfaden") und DB-Struktur. Einzige Stelle die sie liest: PreCall (Z. 151-156) — und die liest `profil_daten.get('opener')` flach, nicht `leitfaden.opener`.

7. **`erlaubnis` wird NIRGENDS gelesen.** Komplett totes Feld im Profil-Editor.

8. **`consent_text` wird NIRGENDS gelesen.** Meeting-Modus-Consent-Vorlesetext steht im Profil, wird in UI angezeigt, aber kein Prompt referenziert ihn. (Evtl. nur für UI — akzeptabel, sollte dokumentiert werden.)

9. **Zielgruppe fast vollständig tot im EWB-Prompt.** Von 7 Zielgruppe-Feldern: 0 in EWB, 2 in Training-Kunde, 2 in Coaching-Live, 1 in PreCall. `alter`, `einkommen`, `lebenssituation`, `hintergrund` werden NIRGENDS im Live-Pfad gelesen — nur im dead `_build_system_prompt`.

10. **`ki.stil` wird NIRGENDS gelesen.** Getrennt von `ki.ton` (welches nur in EWB gelesen wird). Dupletten-Verdacht — bestätigt Andrés Kritik "`eigene_formulierungen` überlappt mit ton/stil".

11. **`techniken_aktiv` / `techniken_verboten` / `offene_fragen` (Fließtext) — alles tot.** Nur in dead `_build_system_prompt`.

12. **`kaufsignale` nur im Coaching-Live (separater Prompt, kein EWB).** Postcall-Coach nutzt nur die Events aus der Conversation, nicht die Profil-Definitionen.

13. **`nogos` und `wettbewerber` nur in dead code + `wettbewerber` noch in Coaching-Live + Training-Kunde.** EWB ignoriert beide komplett.

14. **Postcall-Coach nutzt `profile_data` Parameter, aber referenziert ihn im Prompt nicht.** Argument-Boilerplate, null Effekt.

### 🟢 Funktioniert wie dokumentiert

15. **Phase 08-Erweiterungen (`branche_kontext`, `eigene_formulierungen`, `beweise`) sind korrekt integriert** im Live-EWB-Pfad. ✅

16. **Tabu-Begriffe-System (Phase 08.5 Korrektur 1+3)** sauber in EWB + QA-Response integriert mit Safety-Net. ✅

17. **Keyword-Matcher + Einwand-Alias-Match** funktioniert unabhängig vom LLM — stabil, deterministisch, <1ms Latenz. ✅

---

## Tote Felder — Kandidaten für Entfernung oder Re-Integration

| Feld | Aktueller Status | Empfehlung |
|---|---|---|
| `basis.name` | Nie in Prompt | Entfernen (nur UI-Anzeige für User, kein LLM-Bedarf) |
| `basis.branche` (Enum) | Nie in Prompt | Entweder in EWB-Kontext rein ODER entfernen (aktuell totes Profil-Metadatum) |
| `opener` | Nur in PreCall | In EWB-Prompt aufnehmen ODER klar als "nur Teleprompter-UI" positionieren |
| `erlaubnis` | Nirgends | Entfernen oder in EWB aufnehmen |
| `pitch` | Nur in PreCall | Wie `opener` |
| `zielgruppe.alter` | Nirgends live | Entfernen ODER in EWB+Training+PreCall aufnehmen |
| `zielgruppe.einkommensniveau` | Nirgends live | Wie oben |
| `zielgruppe.lebenssituation` | Nirgends live | Wie oben |
| `zielgruppe.beruflicher_hintergrund` | Nirgends live | Wie oben |
| `zielgruppe.vorwissen` | Nur Training + Coaching | In EWB aufnehmen (wichtig für Tiefe der Antwort) |
| `zielgruppe.entscheidungsverhalten` | Nur Training + Coaching | In EWB aufnehmen |
| `einwaende[].varianten` | Nur Training | In EWB-Prompt aufnehmen als Fallback-Liste wenn Keyword nicht matcht |
| `einwaende[].gegenargument` | Nur via KW-Match direkt + Manual-Btn | In EWB-Prompt als Referenz-Liste aufnehmen |
| `einwaende[].technik` | Nirgends live | In EWB aufnehmen ODER entfernen |
| `einwaende[].intensitaet` | Nirgends live | Entfernen oder nutzen |
| `faqs[]` | Nur FAQ-Match | Optional in EWB-Prompt als Zusatz-Kontext (vielleicht wäre es aber Prompt-Bloat) |
| `kaufsignale[]` | Nur Coaching-Live | In EWB oder entfernen (eigentlich aber Coach-Job, passt dort) |
| `nogos[]` | Nirgends live | In EWB aufnehmen (kritisch: KI sollte nicht bei No-Go-Profilen pitchen) |
| `wettbewerber[]` | Nur Coaching + Training | In EWB aufnehmen (wichtig wenn Kunde Konkurrent erwähnt) |
| `uebergaenge[]` | Nur Coaching-Live | OK dort, aber evtl auch im EWB für Abschluss-Trigger |
| `techniken_aktiv` | Nirgends live | In EWB aufnehmen oder entfernen |
| `techniken_verboten` | Nirgends live | In EWB aufnehmen (wichtig — "sagt NIE diese Phrase") |
| `offene_fragen` (Fließtext) | Nirgends live | Schema-Klärung: Liste oder Fließtext? Aktuell nie gelesen. |
| `schmerzen.trigger` | Nirgends live | **Entfernen** — großes schickes Slider-UI ohne Wirkung |
| `schmerzen.schmerzpunkte` | Training + Coaching | OK dort, evtl. auch in EWB |
| `ki.stil` | Nirgends live | Mit `ki.ton` zusammenlegen oder entfernen |
| `ki.antwortlaenge` | Nirgends live | In EWB aufnehmen (direkt relevant) oder entfernen |
| `ki.sensitivitaet` | Nirgends live | In EWB aufnehmen oder entfernen |
| `ki.zusatz` | Nur Coaching-Live | In EWB aufnehmen (User hat darauf Zugriff als "freie KI-Instruktion" — sollte überall gelten) |
| `consent_text` | Nirgends gelesen | Dokumentieren dass es UI-only ist |
| `precall_briefing` (State, nicht Profil) | Nicht in EWB | **Re-Integrieren** — ursprüngliche Intention |
| `aktives_skript` | Nicht in EWB | Re-Integrieren oder Skript-Feature abbauen |

---

## Wichtigste Architektur-Fehler

1. **Zwei Prompt-Generatoren ohne klare Owner-Trennung.** `_build_system_prompt` (Legacy, reichhaltig, tot) und `build_profile_context` (neu, sparse, live) wurden parallel gehalten, Doku sagt Legacy-Module brauchen ihn — aber kein Live-Pfad benutzt ihn. Muss geklärt werden: endgültig löschen oder ALLE Felder in `build_profile_context` migrieren.

2. **`build_profile_context` ist bewusst minimalistisch** (Phase 08 Intent: schlanker Prompt für Baustein-Struktur) — aber inzwischen fehlen dadurch alle Profil-Felder die dem LLM Kontext geben würden. Die Baustein-Logik ist ohne Einwände/Varianten/Wettbewerber/No-Gos limitiert.

3. **Keyword-Matcher vs. LLM-Generation sind nicht integriert.** Wenn KW matcht → Gegenargument direkt ausgespielt (gut, schnell). Wenn KW nicht matcht → LLM hat keine Einwand-Liste als Referenz. → Klassisches Hybrid-System-Problem.

4. **Manual-Button-Pfad (`streame_manual_ewb_variante`) nutzt einen komplett anderen System-Prompt** als die Auto-EWB. Inkonsistenter Stil zwischen Auto und Manual.

5. **QA-Pipeline (Phase 08.5) teilt sich `build_profile_context` nicht.** Sie hat nur Tabu-Block + Anrede. Hat also noch weniger Kontext als die EWB.

---

## Offene Fragen (für Klärung vor Phase B)

1. Ist `_build_system_prompt` wirklich tot oder wird es über einen Pfad gecallt den ich übersehen habe? → **Verifikationsvorschlag:** Print-Log in `_build_system_prompt` einbauen und eine Session laufen lassen. Wenn Log nie feuert → bestätigt tot.
2. Ist `aktives_skript` (Teleprompter) noch ein aktives Feature? Wenn ja: wird es aktuell irgendwo im LLM genutzt?
3. Soll PreCall-Briefing automatisch in EWB fließen oder nur auf User-Toggle?
4. Sind `opener`/`pitch` Top-Level oder `leitfaden.*`-Feld? DB-Schema vs. Editor-UI klären.
5. Ist die UI im Profil-Editor State-synced mit DB oder gibt es Schreib-Wege die diese Felder niemals speichern?

---

## Datenbasis für Phase B/C

- Dead fields count: **~15** definitiv nie in Live-Prompt (🧟 + nirgends-Kategorie)
- Partial fields: **~10** (nur in einem der 13 Pfade oder indirekt)
- Voll integriert im EWB (dem wichtigsten Pfad): **10 Felder**
- Gesamte Profil-Felder (gezählt): **~48**
- **→ EWB-Integration-Quote: 10/48 = 21%**
- → Andrés "gefühlt 90% kommen nicht an" ist real. Realwert: **~79% der Profil-Felder kommen nicht in den EWB-Prompt.**

---

*Audit abgeschlossen 2026-04-24 durch Code-Reading von services/ewb_pipeline.py, prompt_pipeline.py, qa_pipeline.py, claude_service.py, training_service.py, precall_service.py, coaching_service.py, einwand_keyword_matcher.py.*
