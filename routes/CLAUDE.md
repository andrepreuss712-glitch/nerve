# routes/ — Spezifische Regeln

## url_for-Verifikation (PFLICHT vor jedem url_for()-Aufruf)

Bevor ein `url_for()`-Aufruf in eine Route geschrieben wird, drei Schritte:

### Schritt 1: Endpoint-Funktion pruefen
```bash
grep -rn "def <endpoint_name>" routes/
```
Beispiel: `grep -rn "def login" routes/` → prueft ob `login()` in routes/ existiert.

### Schritt 2: Blueprint-Name verifizieren
```bash
grep -rn "_bp = Blueprint(" routes/
```
Der erste Argument-String ist der Blueprint-Name fuer url_for().
Beispiel: `auth_bp = Blueprint('auth', __name__)` → url_for('auth.login')

### Schritt 3: Aufloesbarkeit pruefen — ⛔ NICHT LOKAL (korrigiert 2026-08-11)

**Hier stand bis 11.08. ein `flask shell`-Aufruf.** Das ist lokales Ausfuehren von Anwendungs-Code und verstoesst gegen die harte Regel „Kein Local-Dev" (`salesnerve/CLAUDE.md`) — die kennt **keine Ausnahmen**, auch nicht fuer eine schnelle Probe. Lokal gelten andere Voreinstellungen, andere Pfade, andere Paket-Versionen: eine lokal aufloesbare Route sagt **nichts** ueber den Live-Server.

**Stattdessen, in dieser Reihenfolge:**
1. **Statisch pruefen** (kostet nichts, faengt den haeufigsten Fall): Blueprint-Name und Funktionsname am Code greppen — beides, nicht nur eines. Bau-Regel 9: **Endpoint-Namen nie raten.**
2. **Bau-Regel 20 beachten:** Neben die Abwesenheits-Pruefung immer einen **Existenz-Anker** setzen (`grep -c` auf ein bekannt vorhandenes Muster == 1). Sonst ist „nichts gefunden" nicht von „nichts gelesen" zu unterscheiden.
3. **Echte Abnahme laeuft auf dem Live-Server:** commit → push → `bash deploy.sh production` → Test-Tor auf dem Server → im Browser mit dem Test-Konto aufrufen. Erst das beweist, dass die Route aufloest.
4. Den Bestand der Routen auf dem Server abfragen: `scripts/inspect.sh routes` (nur lesen).

⚠ *Anlass: Ein `BuildError` durch einen geratenen Namen ging schon einmal live, obwohl alle Pruefungen gruen waren — gefangen erst im Browser. Genau dagegen ist Schritt 3 gedacht; er muss deshalb dort laufen, wo es zaehlt.*

## Haeufiger Fehler
`url_for('auth.login')` schlaegt fehl wenn Blueprint-Name nicht 'auth' ist.
Immer Schritt 2 vor dem Schreiben ausfuehren.

## Blueprint-Uebersicht (Stand 2026-08-03)

> ⚠ **Diese Tabelle ist eine Kopie und veraltet still.** Sie stand von 2026-04-27 bis 2026-08-03
> unveraendert da und hatte `crm_export.py` (seit 01.06. im Repo) nie enthalten.
> **Im Zweifel gilt der grep-Dreischritt darueber, nicht diese Tabelle.**

| Datei              | Blueprint-Instanz    | Blueprint-Name   |
|--------------------|----------------------|------------------|
| auth.py            | auth_bp              | 'auth'           |
| dashboard.py       | dashboard_bp         | 'dashboard'      |
| app_routes.py      | app_routes_bp        | 'app_routes'     |
| profiles.py        | profiles_bp          | 'profiles'       |
| training.py        | training_bp          | 'training'       |
| coach.py           | coach_bp             | 'coach'          |
| settings.py        | settings_bp          | 'settings'       |
| organisations.py   | orgs_bp              | 'orgs'           |
| payments.py        | payments_bp          | 'payments'       |
| onboarding.py      | onboarding_bp        | 'onboarding'     |
| oauth.py           | oauth_bp             | 'oauth'          |
| feedback.py        | feedback_bp          | 'feedback'       |
| learning.py        | learning_bp          | 'learning'       |
| logs_routes.py     | logs_bp              | 'logs'           |
| performance.py     | performance_bp       | 'performance'    |
| legal.py           | legal_bp             | 'legal'          |
| changelog.py       | changelog_bp         | 'changelog'      |
| waitlist.py        | waitlist_bp          | 'waitlist'       |
| admin_dashboard.py | admin_dashboard_bp   | 'admin_dashboard' |
| admin_ewb.py       | admin_ewb_bp         | 'admin_ewb'      |
| crm_export.py      | crm_export_bp        | 'crm_export'     |

Hinweis: organisations.py nutzt `orgs_bp` mit Blueprint-Name `'orgs'` (nicht 'organisations').
Fehler-Quelle: url_for('organisations.foo') schlaegt fehl — korrekt ist url_for('orgs.foo').

## Route-Aenderungen (Phase 08.19.5)

- POST /api/session-rating (app_routes_bp) — post-call star rating (renamed from /api/feedback, D-02)
- POST /api/feedback (feedback_bp) — bug-report widget (feedback.py, bleibt unveraendert)
