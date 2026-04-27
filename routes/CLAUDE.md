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

### Schritt 3: Route im Flask-Shell-Kontext testen
```bash
flask shell
```
```python
from flask import url_for
with app.test_request_context():
    print(url_for('auth.login'))
```
Wenn kein BuildError: Route ist aufloesbar.

## Haeufiger Fehler
`url_for('auth.login')` schlaegt fehl wenn Blueprint-Name nicht 'auth' ist.
Immer Schritt 2 vor dem Schreiben ausfuehren.

## Blueprint-Uebersicht (verifiziert 2026-04-27)
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

Hinweis: organisations.py nutzt `orgs_bp` mit Blueprint-Name `'orgs'` (nicht 'organisations').
Fehler-Quelle: url_for('organisations.foo') schlaegt fehl — korrekt ist url_for('orgs.foo').
