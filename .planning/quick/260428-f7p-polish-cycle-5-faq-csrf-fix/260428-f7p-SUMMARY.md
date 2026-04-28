# Quick Task 260428-f7p — Summary

## Was wurde gemacht

- CSRF-Fix in `persistFaq()` PUT-Branch: `X-CSRFToken`-Header ergänzt, `.catch` durch `.then(r.ok-Check) + .catch` ersetzt — Flask-WTF gab vorher silent HTTP 400 zurück, Daten gingen bei Blur-Events verloren
- CSRF-Fix + r.ok-Guard in `deleteFaq()` DELETE: `X-CSRFToken`-Header ergänzt, `row.remove()` nur noch bei `r.ok` — verhindert silent DOM-Entfernung bei Server-Fehler
- Anti-Drift-Fix in `saveTabuToServer()` POST: `r.json()` jetzt via `r.ok ? r.json() : Promise.reject(r.status)` gesichert
- Click-Handler in `renderFaqRow()` um `.faq-delete`-Guard erweitert: `if (e.target.closest('.faq-delete')) return;` — Klick auf Trash-Icon löst kein Accordion-Toggle mehr aus
- FAQ-Card-Template umgebaut: Trash-Icon + Used-Count aus `.faq-meta`-div (im Body) in `.block-hd.faq-hd` Header verschoben — konsistent mit Skripte/Opener/Einwände-Cards; `faq-meta`-div entfernt

## Bugs Fixed

- **POLISH-CSRF-FAQ** (`static/profile_editor.js`, Z.160–165): `persistFaq()` PUT ohne X-CSRFToken → HTTP 400 → FAQ-Änderungen bei Blur nicht persistent
- **POLISH-CSRF-FAQ** (`static/profile_editor.js`, Z.187–194): `deleteFaq()` DELETE ohne X-CSRFToken → HTTP 400 → row.remove() lief trotzdem, silent data loss
- **Anti-Drift** (`static/profile_editor.js`, Z.455): `saveTabuToServer()` POST: kein r.ok-Guard vor r.json() → unbehandelte 4xx/5xx
- **POLISH-FAQ-TRASH** (`templates/profile_editor.html`, Z.500–538): Trash-Icon nur im expanded Body sichtbar, nicht im collapsed Header

## Files Changed

- `static/profile_editor.js`
- `templates/profile_editor.html`

## Commits

- `bab3c81` — fix(260428-f7p-01): FAQ CSRF + r.ok guards + trash-click isolation
- `fcdf456` — fix(260428-f7p-02): FAQ-Trash-Icon in Card-Header verschieben

## Self-Check

- `static/profile_editor.js`: FOUND (modified, committed bab3c81)
- `templates/profile_editor.html`: FOUND (modified, committed fcdf456)
- Both commits verified in git log

## Self-Check: PASSED
