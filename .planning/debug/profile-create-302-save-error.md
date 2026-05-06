---
slug: profile-create-302-save-error
status: resolved
trigger: Profile-Erstellen kaputt — 302 Redirect nach POST auf /profiles/new, Frontend zeigt Fehler obwohl Backend erfolgreich speichert
created: 2026-05-06
updated: 2026-05-06
---

## Symptoms

- **Expected:** /profiles → "Neues Profil erstellen" → Namen eingeben → Speichern → Profil wird angelegt, Erfolgsmeldung
- **Actual:** Toast "Fehler beim speichern - bitte nochmal versuchen" erscheint, aber Backend hat erfolgreich gespeichert
- **Error messages:** Toast-Fehlermeldung im Frontend; kein JS-Error in Browser-Console
- **Timeline:** Erstmals aufgetreten in UAT am 2026-05-06 nach Deploy von Phase 08.19.5.6 (25 Commits)
- **Reproduction:** Gehe zu /profiles, klicke "Neues Profil erstellen", gib Namen ein (z.B. "mitnorm"), klicke "Speichern"
- **Network evidence:** POST /profiles/new → 302 Redirect (fetch, 621 B, 22 ms), dann GET /profiles/ → 200 (fetch, 17.3 kB, 37 ms)
- **Proof backend saves:** User klickte 8x auf Speichern → 8 "mitnorm"-Profile wurden in DB angelegt, alle aktivierbar/editierbar

## Hypotheses (pre-loaded from user context)

1. POST /profiles/new antwortet mit 302-Redirect → fetch() folgt redirect → Frontend-Save-Handler interpretiert dies als Fehler (erwartet 200/201)
2. Response-Format-Mismatch: Endpoint gibt HTML zurück, Frontend erwartet JSON → JSON.parse() schlägt fehl → catch-Block zeigt Fehler
3. CSRF-Token oder Session-Cookie fehlt beim ersten Save-Versuch
4. Frontend-Save-Handler prüft falschen Erfolg-Indikator (response.ok false bei 302, oder response.json().success nicht vorhanden)

## Current Focus

hypothesis: "Hypothesen 1+2 kombiniert — beide treffen zu"
test: "Beide Fixes deployed: Backend gibt JSON zurück bei AJAX, Frontend nutzt edit_url für Redirect"
expecting: "Kein Fehler-Toast mehr, User landet auf Edit-Seite des neuen Profils"
next_action: "UAT: einmal neues Profil anlegen"
reasoning_checkpoint: "fix_applied"
tdd_checkpoint: ""

## Evidence

- timestamp: 2026-05-06T00:00Z
  finding: "routes/profiles.py neu() zeigt keinen X-Requested-With-Check — gibt immer redirect(url_for('profiles.liste')) zurück, auch bei AJAX"
  file: routes/profiles.py:85
  significance: high

- timestamp: 2026-05-06T00:00Z
  finding: "bearbeiten() (line 162) hat den AJAX-Check korrekt implementiert: if request.headers.get('X-Requested-With') == 'XMLHttpRequest': return jsonify({'ok': True, 'name': p.name}) — neu() hat ihn nie bekommen"
  file: routes/profiles.py:162
  significance: high

- timestamp: 2026-05-06T00:00Z
  finding: "Frontend fetch() sendet X-Requested-With: XMLHttpRequest, erwartet JSON. fetch() folgt 302 automatisch, landet bei GET /profiles/ (HTML). r.ok=true aber r.json() wirft SyntaxError → catch-Block → Fehler-Toast"
  file: templates/profile_editor.html:1195-1198
  significance: high

## Eliminated

- CSRF/Session-Cookie-Problem (Hypothese 3): eliminiert — 8 Saves funktionieren alle serverseitig, CSRF ist kein Faktor
- response.ok=false bei 302 (Hypothese 4 teilweise): eliminiert — fetch() folgt redirect, response.ok ist tatsächlich true bei 200 des folgenden GET. Das Problem ist r.json() das auf HTML fehlschlägt.

## Resolution

root_cause: "neu()-Route in routes/profiles.py hatte keinen AJAX-Branch — POST /profiles/new gab immer 302+HTML zurück. fetch() folgte dem Redirect, erhielt HTML statt JSON, json()-Parse schlug fehl, catch-Block zeigte Fehler-Toast. bearbeiten() hatte den Fix bereits (X-Requested-With-Check + jsonify), neu() hatte ihn nie bekommen."
fix: "1) routes/profiles.py neu(): nach db.commit() AJAX-Check ergänzt — gibt jsonify({'ok': True, 'name': p.name, 'id': p.id, 'edit_url': ...}) zurück. 2) profile_editor.html .then()-Handler: prüft data.edit_url — wenn vorhanden (neue Profile), redirect zu Edit-Seite; sonst Success-Toast (existierende Profile)."
verification: "UAT: Neues Profil anlegen → kein Fehler-Toast → User landet auf Edit-Seite des neuen Profils. 8 Duplikat-Profile in DB manuell löschen."
files_changed:
  - routes/profiles.py (neu() AJAX-Branch)
  - templates/profile_editor.html (.then()-Handler)
