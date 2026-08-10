# Auftrag an Fable: Was steckt HEUTE schon an Vertriebs-Wissen in unserem Code — und passt es auf den US-Markt?

## Warum gerade du das machst

Parallel laufen fuenf reine Recherchen (vier Web-Agenten + Gemini zu Video/Praktiker-Wissen).
**Du machst als Einziger etwas anderes: die Bestandsaufnahme am echten Code.**

Grund: Bevor wir neues Vertriebs-Wissen einkaufen, muessen wir wissen, **welches wir schon
eingebaut haben** — und ob es aus der deutschen Vertriebskultur stammt. NERVE wurde fuer den
DACH-Markt gebaut und geht jetzt in den US-Markt (Beschluss 04.07.). **Jede Bewertungs-Regel und
jeder Prompt-Satz, der stillschweigend deutsche Gespraechsnormen annimmt, wird im US-Markt falsch
coachen — und niemand wird es merken, weil es plausibel aussieht.**

## Dein Auftrag

Lies im Repo `C:\Users\andre\dev\salesnerve` **nur lesend** und trage zusammen:

### 1. Wo steckt Vertriebs-Wissen im Code?
Alle Stellen, die eine inhaltliche Aussage darueber treffen, was gutes Verkaufen ist. Erwartbare
Orte (nicht abschliessend): `services/judge_dimensions.py` · `services/claude_service.py` (die
Prompt-Bausteine) · `services/ki_logik.py` · `services/coaching_service.py` · `services/outcome_service.py`
· `services/precall_service.py` · alles unter `prompts/` falls vorhanden · Einwand-Kategorien und
Phasen-Definitionen · `routes/app_routes.py` (`_calc_call_score`, `_calc_process_score`).

Pro Fundstelle: **Datei:Zeile · welche inhaltliche Annahme steckt drin · woher stammt sie
vermutlich.**

### 2. Welche dieser Annahmen sind KULTURELL, nicht universell?
Das ist der Kern. Konkrete Beispiele, nach denen zu suchen ist:
- **Redeanteil**: Wir haben drei widerspruechliche Wahrheiten im Code — die Score-Formel belohnt
  40 %, das Dashboard sagt „Ziel unter 40 %", der Judge-Prompt sagt 55:45. Welche Zahl ist woher?
  Ist sie fuer den US-Markt belegt oder aus deutschem Trainingsmaterial?
- **Sprechtempo**: Gibt es irgendwo eine Ziel-Vorgabe? Woher stammt sie?
- **Direktheit / Small Talk**: Bewerten wir irgendwo, ob jemand „zu schnell zum Punkt" kommt?
  Im US-Kontext koennte genau das umgekehrt gelten.
- **Hoeflichkeitsformen, Siezen-Logik, Anrede** — steckt das in Prompts?
- **Einwand-Kategorien**: Sind es die im US-Markt ueblichen? (dort z.B. „send me an email",
  „we already have a vendor", „call me next quarter")
- **Gespraechsphasen**: Entspricht unser Phasen-Modell dem US-ueblichen Ablauf?

### 3. Was ist hart auf Deutsch verdrahtet?
Erkennungs-Muster, Wortlisten, Schwaerzungs-Listen, Tabu-Woerter, Regulaere Ausdruecke — alles, was
bei englischer Eingabe **still** ins Leere laeuft statt zu scheitern. **Still ist hier das
Gefaehrliche:** ein Muster, das nie trifft, meldet keinen Fehler, es liefert einfach nie ein
Ergebnis.

### 4. Was davon faellt bei METRIK-1 ohnehin weg?
Der Scope von METRIK-1 (Ablosung der Bewertung) steht in `.planning/ROADMAP.md`. Von ~30 heute
gefuehrten Werten ueberleben ~9. **Sag ausdruecklich, welche deiner Funde sich dadurch von selbst
erledigen** — wir wollen nichts reparieren, was gerade abgerissen wird.

## Qualitaets-Anforderungen

- **Jede Aussage mit Datei:Zeile belegen.** Keine Aussage aus dem Gedaechtnis oder aus der Doku —
  bei uns gilt: Code ist die Wahrheit, Doku beschreibt Code.
- **Trenne**: „steht so im Code" vs. „ist meine Einschaetzung zur kulturellen Herkunft".
- Wo du eine Annahme findest, deren Herkunft du **nicht** belegen kannst: als offene Frage
  auffuehren, nicht raten.
- **Kein Code aendern, keine Vorschlaege umsetzen.** Reine Bestandsaufnahme.

## Ausgabe

Auf Deutsch. Struktur nach den vier Punkten oben. Am Ende eine priorisierte Liste:
**Welche kulturell gepraegte Annahme wuerde im US-Markt den groessten Schaden anrichten, und warum?**
