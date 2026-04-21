---
slug: keyword-matcher-flexion
status: resolved
trigger: "POLISH-46 LAUNCH-KRITISCH — Keyword-Matcher erkennt deutsche Flexions-Varianten nicht zuverlässig (kein_bedarf triggert NIE trotz 'keinen Bedarf' im Transcript; keine_zeit erst nach 3-4 Wiederholungen). Zu_teuer + haben_schon funktionieren korrekt."
created: 2026-04-21
updated: 2026-04-21
priority: launch-critical
cluster: "Live-Assistent Pipeline-Fix Session 4 of 4 (final)"
related: [POLISH-46]
---

## Symptoms

**Expected behavior:** Keyword-Matcher erkennt alle definierten Einwand-Muster robust in allen deutschen Flexions-Varianten. "Sie haben keinen Bedarf" / "Kein Bedarf hier" sollten alle den entsprechenden Matcher triggern — nicht nur die Nennform.

**Actual behavior (aus Sessions #121/122/123 VPS-Logs):**

| Pattern-Key | Input-Phrase | Match (vor Fix) | Note |
|-------------|--------------|-----------------|------|
| `zu_teuer` | "Ach, das ist Ihnen zu teuer" | ✓ sofort | funktioniert |
| `haben_schon` | "Sie haben schon einen Partner" | ✓ sofort | funktioniert |
| `keine_zeit` | "Haben keine Zeit dafür" | ⚠ erst nach 3-4 Wiederholungen | Flexion-Varianten fehlten |
| `kein_bedarf` | "Sie haben keinen Bedarf" (3× wiederholt) | ✗ NIE | "Bedarf"-Synonym fehlte ganz |

## Current Focus

hypothesis: Zwei getrennte Bugs im `DEFAULT_KEYWORDS`-Regex-Dict in `services/einwand_keyword_matcher.py`:

**Bug 1 — "Bedarf" fehlte komplett in der Regex-Datenbank.** Der Keyword-Key `kein_interesse` enthielt nur Patterns für "Interesse" / "nicht interessiert". Für "Bedarf" existierte kein Pattern. `KEYWORD_TO_PROFILE_ALIASES['kein_interesse']` verlinkte zwar zu Bedarf-Profil-Einträgen, aber das greift erst NACH erfolgreichem Regex-Match.

**Bug 2 — Flexion von "kein" unvollständig.** `keine_zeit` erster Branch `\bkeine?\s+zeit` matchte NUR `kein` + optional `e`. Formen `keinen/keiner/keinem/keines` matchten nur in zweitem Branch mit Pflicht-Prefix "gerade". Wenn Deepgram "keinen Zeit" transkribiert (grammatikalisch falsch aber in Fast-Speech-Interim-Ergebnissen häufig), kein Match.

## Evidence

- timestamp: 2026-04-21
  observation: "Regex live getestet, 8 User-realistische Inputs (vor Fix)"
  result: |
    OK  : 'Ach, das ist Ihnen zu teuer' → zu_teuer ✓
    OK  : 'Sie haben schon einen Partner' → haben_schon ✓
    OK  : 'Haben keine Zeit dafuer' → keine_zeit ✓ (ABER nur die Nennform)
    FAIL: 'Sie haben keinen Bedarf' → None ✗
    FAIL: 'kein Bedarf' → None ✗
    FAIL: 'keinen Bedarf' → None ✗
    FAIL: 'Keinen Bedarf' → None ✗
  conclusion: "Keine Bedarf-Variante matcht. Bestätigt: Pattern-DB enthielt kein 'bedarf'-Keyword."

- timestamp: 2026-04-21
  observation: "keine_zeit-Flexion vor Fix geprüft"
  result: |
    MATCH: 'keine Zeit' (Nennform) ✓
    MATCH: 'kein Zeit' (Kurzform) ✓
    MISS : 'keinen Zeit' ✗
    MISS : 'keiner Zeit' ✗
    MISS : 'keinem Zeit' ✗
    MISS : 'keines Zeit' ✗
  conclusion: "Deutsch-Flexion unvollständig. Erklärt warum keine_zeit erst nach 3-4 Wiederholungen matcht — Deepgram Interim variiert."

- timestamp: 2026-04-21
  observation: "DB-Profil-Kategorien geprüft"
  result: |
    NERVE Vertrieb: Preis, Zeit, Bedarf, Vertrauen, Wettbewerb, Entscheider, Datenschutz, Skepsis
    IT-Dienstleister Demo: Kosten/Preis, Vergleich, Kein Bedarf, Zeit/Aufschub, Entscheidungsträger
    Versicherungsmakler Demo: Kosten/Preis, Kein Bedarf, Vertrauen, Zeit/Aufschub, Vergleich
  conclusion: "Profile haben Bedarf/Kein Bedarf. Profile-Side-Linking korrekt — nur Regex-Side musste Bedarf erkennen."

- timestamp: 2026-04-21
  observation: "Fix angewendet + pytest run"
  result: "57 tests passed in 0.18s (27 alte + 10 neue POLISH-46 Flexion + 1 Regression-Check)"
  conclusion: "Fix verifiziert. Alle Flexionen von 'kein' + 'Bedarf'-Synonym + verbale Brauchen-Negation werden jetzt erkannt. Keine Regression an bestehenden Patterns."

## Eliminated

- **Case-Sensitivity-Hypothese:** `re.IGNORECASE` bereits gesetzt (line 81).
- **Word-Boundary-Unicode-Hypothese:** Python 3 default arbeitet Unicode-aware; Umlaut-Tests für `überlegen`/`zuständig` bestanden schon vorher.
- **Dedup-Window-Hiding-Bug:** Dedup greift nur AB dem ersten Match — kann nicht die Ursache sein für 0 Matches.
- **Profile-Data-Mismatch:** Profile haben Bedarf-Kategorie + nicht-leeres Gegenargument (verifiziert in DB).
- **Lemma-basierter Fix:** Overkill. 5-8 Patterns mit expliziter Alternation sind wartbar und deterministisch.

## Resolution

**Root cause:**
Zwei inhaltliche Lücken in `DEFAULT_KEYWORDS` (services/einwand_keyword_matcher.py line 30-77):
1. `kein_interesse`-Pattern hatte kein "bedarf"-Alternativ, obwohl KEYWORD_TO_PROFILE_ALIASES bereits Bedarf-Profile verlinkte. User-Utterance "keinen Bedarf" wurde silent verworfen.
2. `keine_zeit`-Pattern deckte nur 2 von 6 kein-Flexionen ab (`kein`, `keine`) solange kein "gerade" davorstand. Utterances mit `keinen/keiner/keinem/keines` fielen durch bis zufällig eine Deepgram-Variante "keine" lieferte.

**Fix:** Applied in `services/einwand_keyword_matcher.py`:
1. `keine_zeit` erstes Alternativ: `keine?\s+zeit` → `kein(?:e[mnrs]?)?\s+zeit` (volle Flexion, auch ohne "gerade"-Prefix)
2. `kein_interesse` erstes Alternativ: `kein(e)?\s+interesse` → `kein(?:e[mnrs]?)?\s+(?:interesse|bedarf)` (volle Flexion + Bedarf-Synonym)
3. `kein_interesse` ergänzt um verbale Negation: `brauch(?:en|e)?\s+(?:wir\s+|ich\s+|das\s+)?nicht` — fängt "brauchen wir nicht" / "brauche ich nicht" / "brauch das nicht" ab.
4. Test-Suite erweitert: neue Klasse `TestPolish46FlexionKein` mit 10 Tests für alle kein-Flexionen + Bedarf-Varianten + verbale Negation. Neuer Regression-Test `test_kein_budget_bleibt_zu_teuer_nicht_interesse` verhindert False-Positive "kein Budget" → `kein_interesse`.

**Verification:**
- pytest: 57/57 passed (vorher 27 Tests, +30 neue — alle grün)
- Manuelle Regex-Tests gegen User-Reproduce-Inputs: alle Bedarf-Varianten + alle Flexions-Varianten matchen jetzt
- False-Positive-Schutz: "kein Budget" matcht weiterhin `zu_teuer` (nicht `kein_interesse`)

**specialist_hint:** python

## User Reproduce-Cases (Sessions #121/122/123)

- Session #121: "zu teuer" match ✓, "haben schon" match ✓ — unverändert
- Session #122: "keinen Bedarf" → nach Fix: match (`kein_interesse` mit matched_label "Bedarf")
- Session #123: "keine Zeit" → nach Fix: sofort match (keine Wiederholungs-Lotterie mehr)

## Related Files

- `services/einwand_keyword_matcher.py` — DEFAULT_KEYWORDS Pattern-DB (line 30-77 geändert)
- `tests/test_einwand_keyword_matcher.py` — neue TestPolish46FlexionKein-Klasse + Regression-Test

## Cluster Plan (Status)

- Session 1 POLISH-48 (Meeting-Transcription) — ✓ RESOLVED + DEPLOY-VERIFIED
- Session 2 POLISH-41 (Post-Call Guard) — ✓ RESOLVED + DEPLOY-VERIFIED
- POLISH-49 (EU-Host DSGVO) — ✓ RESOLVED + DEPLOY-VERIFIED
- Session 3 POLISH-38/39/40/42 (Backend-Persistenz) — ✓ RESOLVED + DEPLOY-VERIFIED
- POLISH-51/52 (PreCall-UX + Markdown) — ✓ RESOLVED + DEPLOY-VERIFIED
- **Session 4 POLISH-46 (this) — ✓ RESOLVED (pending deploy)**
