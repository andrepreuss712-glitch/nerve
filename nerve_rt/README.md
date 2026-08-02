# nerve_rt — Real-Time Engine

## ⛔ STOPP — LIES DAS, BEVOR DU DIESE ENGINE SCHARF SCHALTEST

**Diese Engine hat KEINE Anonymisierung. Null. Im gesamten Unterverzeichnis gibt es
keinen einzigen Aufruf von `services.anonymization`.**

Belegt am 2026-08-02 (Cross-AI-Audit, Fable am echten Code):

| Was | Wo |
|---|---|
| Roher Deepgram-Text wird ungefiltert gepuffert | `nerve_rt/services/session_manager.py:298` — `transcript_buffer.append(result.text)` |
| Derselbe rohe Text geht an die Anthropic-API | `nerve_rt/services/session_manager.py:337-351` → `nerve_rt/services/llm/claude_adapter.py:92` |
| Grep `anonym` im gesamten `nerve_rt/` | **0 Treffer** |

**Zustand am 2026-08-02:** Der Dienst laeuft seit dem 28.07. auf Produktion
(`systemctl is-active nerve-rt` = active, nginx routet `/ws/` auf Port 8001),
hatte aber in der Zeit **0 Verbindungen** — kein einziger Call ist je durchgelaufen.
Es ist also bislang **kein roher Text** ueber diesen Weg an ein LLM gegangen.
**Das bleibt nur so, solange niemand die Engine anschliesst.**

## Was VOR dem Scharfschalten gebaut sein muss

Die Haupt-App macht es richtig — als Vorlage nehmen, nicht neu erfinden:

1. **Anonymisieren vor jedem LLM-Aufruf und vor jedem DB-Insert.**
   Vorbild: `services/deepgram_service.py:148-179`. Roher STT-Text geht ausschliesslich
   an den Browser des eigenen Nutzers (das ist gewollt); in Puffer, Prompts und
   Datenbank landet **nur** das Ergebnis von `anonymize()`.
2. **Fail-closed, nicht fail-open.** Faellt die Anonymisierung aus
   (`AnonymizationPipelineUnavailable`, `[ART9_REDACTED]`, `[ANON_FEHLER]`),
   wird das Segment **komplett verworfen** — es darf NICHT roh weiterlaufen.
   Vorbild: `deepgram_service.py:154-179` setzt `_text_for_analysis = None`,
   `:231` verwirft daraufhin still. Genau dieses Verhalten nachbauen.
3. **Kein Schalter, der die Anonymisierung abschalten kann.** Die Haupt-App hat
   bewusst keinen. Baue hier auch keinen.
4. **Ein Waechter, nicht nur dieser Kommentar.** Fable-These, die sich hier schon
   einmal bewahrheitet hat: *„Eine Prosa-Regel ohne Waechter kommt wieder."*
   Vorbild existiert bereits fuer genau diese Zwei-Pfade-Klasse:
   `tests/test_stt_model_parity.py` (faengt, dass Haupt-App und `nerve_rt`
   unbemerkt auseinanderlaufen). Analog bauen: ein AST-/Grep-Test, der rot wird,
   wenn in `nerve_rt/` ein LLM-Adapter mit Text aufgerufen wird, der nicht
   nachweislich durch `anonymize()` lief.
   **Und: den Pruefkatalog des Waechters dokumentieren, inklusive seiner bekannten
   Luecke** (Punkt 31 in `CLAUDE.md` — ein gruener Waechter beweist nur, was in
   seinem Katalog steht).

## Warum das nicht verhandelbar ist

- **DSGVO gilt weiter**, auch bei US-first: Andre ist deutscher Einzelunternehmer.
- **US-Recht:** Die Klagewelle gegen Otter.ai und Invoca stuetzt sich darauf, dass
  der Anbieter zum „heimlichen Dritten" im Gespraech wird, sobald er Daten fuer
  **eigene Zwecke** nutzt. Ungeschwaerzter Gespraechstext an ein LLM ist genau
  dieses Muster.
- **Das Produktversprechen lautet „NERVE zeichnet nichts auf."** Eine Engine, die
  rohe Kundendaten an einen US-Dienst schickt, bricht es — unabhaengig davon, ob
  jemand es merkt.

Kanonische Quelle: `Nerve-Vault/04 Entscheidungen/NERVE Konstrukt - Soll-Verhalten.md` §1
und `Nerve-Vault/04 Entscheidungen/NERVE DSGVO Analyse.md`.
Hergang: `Nerve-Vault/05 Log.md`, Eintrag 2026-08-02.
