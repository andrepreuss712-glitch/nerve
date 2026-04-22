---
phase: 08-ewb-qualit-t-profil-tiefe-launch-kritische-prompt-iteration-
reviewed: 2026-04-22T00:00:00Z
depth: standard
files_reviewed: 29
files_reviewed_list:
  - .env.example
  - .gitignore
  - app.py
  - database/models.py
  - deploy/nerve.service
  - docs/phase-08-training-vs-live-prompt-gap.md
  - routes/admin_ewb.py
  - routes/app_routes.py
  - routes/profiles.py
  - scripts/migrate_branche_to_enum.py
  - services/claude_service.py
  - services/deepgram_service.py
  - services/ewb_pipeline.py
  - services/prompt_pipeline.py
  - static/nerve.css
  - static/pip-launcher.js
  - templates/_beispiel_profil_modal.html
  - templates/_tooltip.html
  - templates/admin/ewb_quality.html
  - templates/admin/ewb_rating_template.html
  - templates/profile_editor.html
  - templates/session_detail.html
  - tests/test_ab_stats.py
  - tests/test_branche_migration.py
  - tests/test_claude_service_phase08.py
  - tests/test_ewb_pipeline.py
  - tests/test_ewb_rate_api.py
  - tests/test_phase_08_migration.py
  - tests/test_phase_08_models.py
  - tests/test_prompt_pipeline.py
findings:
  critical: 2
  warning: 9
  info: 7
  total: 18
status: issues_found
---

# Phase 08: Code-Review-Bericht

**Reviewed:** 2026-04-22
**Depth:** standard
**Files Reviewed:** 29 (Source-Dateien, inkl. 8 Tests)
**Status:** issues_found

## Zusammenfassung

Phase 08 hat eine substantielle Pipeline-Refaktorisierung geliefert (neue `services/ewb_pipeline.py`, `services/prompt_pipeline.py`, EwbRating-Model, 3-State ObjectionEvent.success, A/B-Routing, Anrede-Override, Admin-Dashboard). Die Architektur ist sauber: Fail-open in der Live-Loop, lazy DB-Imports, idempotente Seeds, Strict-Bool-Check via `isinstance(value, bool)`, Ownership-Check auf Rating-API, Hardening via XSS-Allowlist in `markdown_filter` und Whitelist fuer `anrede` (Prompt-Injection-Schutz). Tests decken die TDD-Gates gut ab.

Kritisch sind zwei Punkte im Live-Pfad: (1) im Live-Loop wird `ls.state` außerhalb von `state_lock` gelesen (Race gegen Writer in `deepgram_service` und `analyse_loop`) und (2) `build_profile_context` greift auf `ls.state.get('session_anrede')` ohne Lock zu. Beides kann zu einem einzelnen inkonsistenten Prompt-Build führen, ist aber nicht korrupt-fatal — daher in Critical als "Latent race" klassifiziert.

Warnings konzentrieren sich auf (a) Daten-Integritäts-Gap: `ObjectionEvent.org_id = user.org_id` Zuweisungen können NULL sein (durch Schema-Inkonsistenz zwischen ORM und Altmigration), (b) SQL-Parameter-Lücken im Admin-Quality-Query beim Expand von `conv_ids` (idempotent, aber konstruktionsbedingt fragil), (c) eine Logik-Inkonsistenz in `handle_manual_ewb` (Profil-Match auf `kurzlabel || kategorie` vs. `api_ewb_trigger` Profil-Match auf `typ`), (d) Template-Issue in `ewb_rating_template.html` (rendert `{{ ev.einwand_typ }}` inside `data-key`, aber `path:einwand_key` Route erlaubt Slashes — Enkodierungs-Risk).

Info-Level betreffen vorwiegend Consistency zwischen Legacy und Phase-08-Pipeline (dead Legacy-Kontextblöcke in `_build_system_prompt`, die nicht mehr von EWB-Modul konsumiert werden), Test-Fixture-Duplikation und drei kleine UX-Consistency-Items.

## Critical Issues

### CR-01: Race Condition beim Lesen von `ls.state['session_anrede']` ohne state_lock

**File:** `services/prompt_pipeline.py:196-204` (`_resolve_anrede`) + `services/claude_service.py:659,722` (Read-Sites) + `services/deepgram_service.py:299-301` (Write-Site)
**Issue:** `_resolve_anrede` liest `state.get('session_anrede')` ohne `state_lock`. Parallel dazu schreibt `handle_start_live_session` in `deepgram_service.py:299-301` den Key *unter* `state_lock`. Außerdem lesen `analysiere_mit_claude` (Zeile 659) und `analysiere_mit_claude_streaming` (Zeile 722) `ls.state.get('user_id')` und `ls.state.get('session_anrede')` ebenfalls ohne Lock.

In Python CPython ist ein dict-`get` zwar atomar bzgl. Single-Byte-Corruption (GIL), aber das Zusammenspiel mit anderen state-Writern aus `analyse_loop` (z.B. `ls.state['ergebnis']`, `ls.state['version']`) schafft ein nicht-triviales Memory-Consistency-Fenster: der EWB-Prompt könnte z.B. mit einem veralteten `user_id` aus der vorherigen Session + neuem `session_anrede` der aktuellen Session gebaut werden. Das korrumpiert kein Datum, aber der A/B-Routing-Schluss (`user_id % len(variants)`) wird inkonsistent und der FT-Log wird mit falscher Zuordnung geschrieben.

Das restliche Projekt folgt konsequent dem Pattern `with ls.state_lock: x = ls.state.get('...')` (siehe `routes/app_routes.py:136-153`, `deepgram_service.py:290-291,306-307`). Phase 08 Code ist die einzige Stelle, die diese Konvention bricht.

**Fix:**
```python
# services/prompt_pipeline.py _resolve_anrede:
def _resolve_anrede(ls: Any, ki: dict) -> str:
    """Anrede priority: session_anrede > ki.ansprache > 'Sie' (D-14 + D-15)."""
    try:
        session_anrede = None
        state_lock = getattr(ls, 'state_lock', None)
        state = getattr(ls, 'state', None)
        if isinstance(state, dict):
            if state_lock is not None:
                with state_lock:
                    session_anrede = state.get('session_anrede')
            else:
                session_anrede = state.get('session_anrede')
        if session_anrede:
            return session_anrede
    except Exception:
        pass
    return ki.get('ansprache') or 'Sie'

# services/claude_service.py analysiere_mit_claude + _streaming:
import services.live_session as ls
with ls.state_lock:
    _user_id = ls.state.get('user_id') or 0
    _anrede = ls.state.get('session_anrede') or 'Sie'
```

### CR-02: Weak Whitelist für `anrede` — Mixed-Case / Whitespace umgeht D-15 Prompt-Lock

**File:** `services/deepgram_service.py:297-301`
**Issue:** Die Whitelist `anrede_raw in ('Du', 'Sie')` verlangt *exakte* Matches. Ein Client, der `'du'`, `' Du'`, `'DU'` sendet, trifft die Whitelist *nicht* — und `session_anrede` bleibt ungesetzt. Das Fall-Back `ki.get('ansprache') or 'Sie'` aus `prompt_pipeline.py:205` greift dann, was im Normalfall harmlos ist.

Gefährlicher: das Frontend in `static/pip-launcher.js:983` sendet bereits bewusst `'Du' | 'Sie'` nach einem Ternary-Filter:
```js
var anredeForSession = (state.precallFormData && state.precallFormData.anrede === 'Du') ? 'Du' : 'Sie';
```
Das ist defense-in-depth. Aber wenn ein anderer Client (Integration, API-Consumer in der Zukunft) die Socket.IO-Eventschnittstelle nutzt und `'DU'` oder `'Du '` mit Trailing-Space sendet, wird der Prompt leise mit dem Profile-Default gebaut — nicht mit dem User-Wunsch. Für eine UAT-kritische Phase mit hartem D-15-Wortlaut-Lock ("Wechsle NIEMALS innerhalb einer Antwort zwischen Du und Sie") ist das ein Silent-Failure-Pfad.

Test `test_anrede_whitelist_rejects_invalid` in `tests/test_ewb_rate_api.py:256-263` verifiziert nur den Extrem-Fall `'Hallo; drop table'`, nicht Mixed-Case/Whitespace.

**Fix:**
```python
# services/deepgram_service.py:297-301
anrede_raw = (data or {}).get('anrede') if isinstance(data, dict) else None
if isinstance(anrede_raw, str):
    anrede_norm = anrede_raw.strip().capitalize()  # 'du'->'Du', 'SIE'->'Sie', ' Du '->'Du'
    if anrede_norm in ('Du', 'Sie'):
        with ls.state_lock:
            ls.state['session_anrede'] = anrede_norm
        print(f"[Phase08] session_anrede={anrede_norm} set from PreCall")
    else:
        print(f"[Phase08] invalid anrede rejected: {anrede_raw!r}")
```

## Warnings

### WR-01: `ObjectionEvent.org_id` NULL-Risk beim Manual-EWB-Click

**File:** `services/deepgram_service.py:463-464` (manual_ewb-Handler) + `services/live_session.py` (record_ewb_click, nicht gelesen, aber aus Kontext ersichtlich)
**Issue:** `record_ewb_click(typ, success=_ewb_success)` wird aus `handle_manual_ewb` aufgerufen, bevor `api_beenden` die `ObjectionEvent`-Rows persistiert (`routes/app_routes.py:462-471`). Dabei wird `org_id=g.org.id` beim DB-Insert gesetzt. Die Spalte erlaubt laut `models.py:348` `nullable=True`, aber das A/B-Query in `routes/admin_ewb.py:39-51` filtert *nicht* auf `org_id` — wenn in einer zukünftigen Multi-User-Phase ein Event ohne `org_id` landet (z.B. weil `g.org` in einem Hintergrund-Job nicht gesetzt ist), taucht es in einem anderen Org-Admin-Dashboard auf.

Das ist heute kein akutes Problem (Solo-Founder-Launch), wird aber zur Zeitbombe sobald Early-Access-Kunden onboarden.

**Fix:**
```python
# routes/admin_ewb.py ewb_quality:
ab_rows = db.execute(text("""
    SELECT ftoe.prompt_version AS version,
           COUNT(*) AS n,
           AVG(CASE WHEN oe.success = 1 THEN 1.0 ELSE 0.0 END) AS success_rate
    FROM ft_objection_events ftoe
    JOIN ft_call_sessions fcs ON fcs.id = ftoe.ft_session_id
    JOIN objection_events oe
      ON oe.conversation_log_id = fcs.conversation_log_id
     AND oe.einwand_typ = ftoe.objection_type
    WHERE oe.success IS NOT NULL
      AND (oe.org_id = :org_id OR :is_super = 1)
    GROUP BY ftoe.prompt_version
    ORDER BY ftoe.prompt_version
"""), {'org_id': g.org.id, 'is_super': 1 if g.user.is_superadmin else 0}).fetchall()
```
Für die Pre-Launch-Phase reicht ein Kommentar-TODO. Aber spätestens bei Multi-Tenancy muss der Filter kommen — und als Superadmin-Only-Route ist er auch heute nicht strictly noetig.

### WR-02: Dynamisch konstruiertes `IN (:id0, :id1, ...)` ist SQL-sicher, aber fragil

**File:** `routes/admin_ewb.py:71-82`
**Issue:** Das Konstruieren des IN-Clauses via String-Interpolation (`placeholders = ','.join(f':id{i}' for i in range(len(ids_list)))`) ist *nicht* injection-gefährdet (die Werte gehen über `params`-Dict), aber es umgeht SQLAlchemy's Native-Bindparams-API, die identischen Schutz mit besserer Diagnostik bietet. Außerdem: wenn `rated_conv_ids` leer ist, läuft der else-Zweig (korrekt), aber wenn die Menge über 1000 Einträge wächst, trifft der Code die SQLite-Parameter-Limit-Grenze (`SQLITE_MAX_VARIABLE_NUMBER` = 999 per default vor 3.32).

Für Phase 08 mit ~100 EWBs passt's; für den Moment wo geratete Sessions in 4-stelligen Zahlen liegen wird's brechen.

**Fix:**
```python
from sqlalchemy import bindparam
# ...
if rated_conv_ids:
    stmt = text("""
        SELECT COALESCE(kb_end, 0) AS s FROM conversation_logs
        WHERE id IN :ids
    """).bindparams(bindparam('ids', expanding=True))
    score_rows = db.execute(stmt, {'ids': list(rated_conv_ids)}).fetchall()
```

### WR-03: `handle_manual_ewb` Match-Chain weicht von Live-Pfad ab

**File:** `services/deepgram_service.py:432-439`
**Issue:** Der Match gegen `profile.einwaende` in `handle_manual_ewb` prüft `kurzlabel || short_label || kategorie`:
```python
label = (e.get('kurzlabel') or e.get('short_label') or e.get('kategorie') or '').lower().strip()
```
In `routes/app_routes.py:1175-1178` macht `api_ewb_trigger` das anders — er prüft `e.get('typ', '').lower() == einwand_typ.lower()`. In `services/claude_service.py:330` (Legacy-Prompt) steht: `typ = e.get('kategorie') or e.get('typ', '')`.

Damit gibt es drei Code-Pfade, die den "Einwand-Typ" aus dem Profil *anders* auflösen. Ein User, der einen Einwand im Profile-Editor mit `kurzlabel='Preis'` und `kategorie='Kosten'` anlegt, bekommt je nach Pfad einen anderen gefundenen Match. Das führt zu inkonsistenter UAT-Erfahrung zwischen Button-Klick-EWB und Auto-Analyse-EWB.

**Fix:** Einheitliche Helper-Funktion extrahieren:
```python
# services/live_session.py (neue Utility):
def match_einwand_by_label(einwaende: list, label: str) -> dict | None:
    """Single source of truth: match profile-einwand by kurzlabel/kategorie/typ."""
    if not isinstance(einwaende, list) or not label:
        return None
    needle = label.lower().strip()
    for e in einwaende:
        if not isinstance(e, dict):
            continue
        for field in ('kurzlabel', 'short_label', 'kategorie', 'typ'):
            v = (e.get(field) or '').lower().strip()
            if v and v == needle:
                return e
    return None
```
Dann in `deepgram_service.py`, `api_ewb_trigger` und `_build_system_prompt` nur noch diesen Helper nutzen.

### WR-04: Template-Encoding `{{ ev.einwand_typ }}` in `data-key` + URL

**File:** `templates/admin/ewb_rating_template.html:66` + `routes/admin_ewb.py:145`
**Issue:** Die Route `@admin_ewb_bp.post('/rating-template/<int:conv_id>/<path:einwand_key>/rate')` nutzt `<path:einwand_key>`, was Slashes erlaubt. Das Template rendert `data-key="{{ ev.einwand_typ }}"` ohne URL-Encoding; das JS ruft dann:
```js
fetch('/admin/ewb/rating-template/' + convId + '/' + encodeURIComponent(key) + '/rate', ...)
```
`encodeURIComponent` encodet `/` zu `%2F`, was dem `path:`-Converter — der Slashes erwartet — widerspricht. Wenn ein Einwand-Typ jemals einen Slash enthält (z.B. `'Zeit/Aufschub'` — das steht wortwörtlich als Kategorie in `services/claude_service.py:20`!), produziert `encodeURIComponent` `%2F`, Flask dekodiert das aber nicht als Separator, sondern als Teil des Path-Segments — und der Route-Match scheitert (404 oder falsche Parameter-Extraktion).

Der Test `test_ewb_rate_api.py` nutzt den einfachen Typ `'Preis'` und trifft den Bug nicht. Aber die Kategorien-Liste im SYSTEM_PROMPT (`claude_service.py:18-28`) enthält explizit `"Zeit/Aufschub"`, `"Entscheidungsträger"`, `"Kein Bedarf"` — alle diese landen als `einwand_typ` in `objection_events` und damit in der Rating-UI.

**Fix:** Nicht `<path:...>` nutzen, sondern `<string:...>` mit custom URL-Enkodierung:
```python
# routes/admin_ewb.py — replace:
@admin_ewb_bp.post('/rating-template/<int:conv_id>/rate')
@login_required
@superadmin_required
def ewb_rating_save(conv_id):
    data = request.get_json(silent=True) or {}
    einwand_key = data.get('einwand_typ_key', '').strip()
    if not einwand_key or len(einwand_key) > 100:
        return jsonify({'error': 'invalid_key'}), 400
    # ... rest
```
Und in `ewb_rating_template.html` den key im POST-Body statt in der URL senden.

### WR-05: `_seed_ewb_v2` ist fragil gegen geänderte `is_default`-Flags

**File:** `app.py:816-834`
**Issue:** Der Code reconciled `exists.is_default` bei jedem App-Start auf den Seed-Wert. Das bricht Admin-Overrides: wenn Andre über die DB (Superadmin-Admin-UI zukünftig, oder direkt per SQL) `v2-modular.is_default=True` setzt um die Default-Variante zu schalten, überschreibt der nächste Deploy die Änderung.

Phase 08 D-26 hat das Flag genau für *manuelles* Umschalten eingeführt (siehe Kommentar `app.py:820-823`). Die aktuelle Reconcile-Logik verhindert das.

**Fix:** Reconcile nur beim initialen Seed durchführen, nicht bei existierenden Rows:
```python
for version, ptext, is_default in [
    ('v1-legacy', V1_LEGACY_TEXT, True),
    ('v2-modular', V2_MODULAR_TEXT, False),
]:
    exists = (db.query(PromptVersion)
              .filter_by(module='ewb', version=version)
              .first())
    if exists:
        continue  # DO NOT touch is_default — preserve admin override
    db.add(PromptVersion(
        module='ewb', version=version, prompt_text=ptext,
        is_active=True, is_default=is_default,
        changelog=f'Phase 08 Seed ({version})',
    ))
```
Der Block E Backfill (`app.py:607`) `UPDATE prompt_versions SET is_default = 1 WHERE is_active = 1` bleibt ebenfalls problematisch — er wird bei jedem App-Start ausgeführt und setzt ebenfalls *beide* ewb-Varianten auf default=1. Block E muss idempotent werden (z.B. nur wenn `is_default IS NULL`, oder nur einmalig über Marker-Row in audit_log).

### WR-06: `_map_branche_to_enum` Substring-Match kann False-Positives liefern

**File:** `scripts/migrate_branche_to_enum.py:101-113`
**Issue:** Der Substring-Match `if kw in norm` ist aggressiv. Beispiel: der Freitext `'API-Design-Consulting'` wird normalisiert zu `'api-design-consulting'`. Die Heuristik-Reihenfolge:
1. `saas_b2b`: Keywords `['saas', 'b2b', 'software', 'cloud', 'platform', 'api']` → Match auf `'api'` → returnt `'saas_b2b'`

Das ist wahrscheinlich *nicht* was der User wollte (er wollte Consulting/Beratung). Tests decken den Fall nicht ab.

Weiteres Beispiel: `'Berater fuer Maschinenbau'` → `'berater fuer maschinenbau'`. saas_b2b-Keywords matchen nicht, versicherung nicht, `'maschinenbau'` matcht bei maschinenbau → `'maschinenbau'`. Der User wollte aber `beratung`. Dieses Edge-Case ist durch die Priority-Reihenfolge gelöst (maschinenbau vor beratung), aber das Design bleibt brittle.

**Fix:** Tokenize vor dem Match:
```python
def _map_branche_to_enum(freitext: Optional[str]) -> str:
    if not freitext:
        return 'sonstiges'
    if freitext in VALID_ENUMS:
        return freitext
    norm = _normalize_branche(freitext)
    import re
    tokens = set(re.split(r'[\s\-_/]+', norm))
    for enum, keywords in HEURISTIC_MAP:
        for kw in keywords:
            # Wort-Match statt Substring:
            if kw in tokens or any(t.startswith(kw) for t in tokens):
                return enum
    return 'sonstiges'
```
Plus neue Tests für die Edge-Cases `'API-Design-Consulting'`, `'Berater fuer Maschinenbau'`.

### WR-07: `markdown_filter` Allowlist fehlen `img`-Sanitisierung und `span`-Elemente

**File:** `app.py:64-73`
**Issue:** Die Allowlist enthält `a`, aber explizit keine `img`, `span`, `div`. Das ist *korrekt* aus Sicherheits-Sicht (verhindert `<img onerror=...>`). Problem: der Kommentar in Zeile 61 verweist auf LB-01 ("User-Felder firmenname/branche/ansprechpartner/optinfo -> Haiku -> Briefing könnten `<img onerror=...>` enthalten"). Aber die Markdown-Extension `'extra'` rendert `![alt](url)` zu `<img src="url" alt="alt">` — das wird dann von bleach gestrippt (nicht escaped), und User sieht *keinen* Text wo ein Bild stehen sollte.

Zudem erlaubt die Allowlist kein `style="color:red"` oder ähnliches inline-styling, was auch korrekt ist. Aber die `a`-Attribute beschränken `rel` nicht — ein vom Haiku produzierter Link `<a href="https://attacker.com/phishing">`... enthält kein `rel="noopener noreferrer"`.

**Fix:**
```python
_ALLOWED_TAGS = ['p', 'br', 'strong', 'em', 'code', 'pre', 'ul', 'ol', 'li',
                 'h1', 'h2', 'h3', 'h4', 'blockquote', 'a']
_ALLOWED_ATTRS = {'a': ['href', 'title', 'rel']}  # rel whitelisted explizit

def markdown_filter(value):
    if not value:
        return ''
    rendered = _markdown.markdown(value, extensions=['extra', 'sane_lists'])
    cleaned = bleach.clean(rendered, tags=_ALLOWED_TAGS, attributes=_ALLOWED_ATTRS,
                           strip=True, protocols=['http', 'https', 'mailto'])
    # Add rel="noopener noreferrer" to all links (defense-in-depth)
    cleaned = bleach.linkify(cleaned, callbacks=[
        bleach.callbacks.nofollow,
        lambda attrs, new=False: {**attrs, (None, 'rel'): 'noopener noreferrer'}
    ])
    return cleaned
```

### WR-08: `_build_system_prompt` wird für Phase-08-EWB nicht mehr genutzt, aber Dead-Paths bleiben

**File:** `services/claude_service.py:265-401`
**Issue:** Mit Plan 03 (Task 1) übernimmt `build_ewb_prompt` + `resolve_prompt_version` die System-Prompt-Konstruktion für den EWB-Modul-Pfad. Der Test `test_claude_service_phase08.py:46-47` verifiziert explizit: `assert 'system=_build_system_prompt()' not in src`. 

Aber `_build_system_prompt()` wird nach wie vor von den 4 anderen Modulen (assistant_live, coaching_live, objection_trigger, api_frage, training_persona) genutzt — so zumindest der Kommentar in `services/claude_service.py:8-11`. Suche ich nach Call-Sites: `_build_coaching_prompt()` wird in `analysiere_coaching` verwendet, aber `_build_system_prompt()` selbst habe ich im gelieferten Chunk nirgendwo mehr als Call-Site gesehen (weder in `analysiere_mit_claude` noch `analysiere_mit_claude_streaming` — dort steht inzwischen `build_ewb_prompt`).

Grep-Ergebnis (schnell geprüft):
- `services/claude_service.py:669` → `system=_system_prompt` (= `build_ewb_prompt(...)`)
- `services/claude_service.py:733` → `system=_system_prompt` (= `build_ewb_prompt(...)`)

`_build_system_prompt` wird nur im Test `test_legacy_symbols_preserved` referenziert und damit *preserved for contract*. Real-life Callsite: **keine**. Der 136-Zeilen-Block ist toter Code. Risiko: jede zukünftige Änderung an SYSTEM_PROMPT_BASE macht dort Arbeit, die nirgends greift; ein zukünftiger Refactor-Contributor verliert Zeit.

**Fix:** Entweder die Legacy-Module (api_frage in `app_routes.py:1108-1150`, ewb_trigger in `app_routes.py:1153-1261`) nutzen `_build_system_prompt()` — Verify und Call-Site dokumentieren; oder — falls wirklich niemand es aufruft — mit einem Deprecation-Kommentar markieren:
```python
# DEPRECATED since Phase 08 Plan 03: replaced by build_ewb_prompt() for EWB module.
# Still kept for test_legacy_symbols_preserved contract + potential future re-use.
# DO NOT add new callers — use services.ewb_pipeline.build_ewb_prompt instead.
def _build_system_prompt() -> str:
    ...
```

### WR-09: `EwbRating.quality_score` wird nicht persistiert → teure Re-Compute in Admin-Dashboard

**File:** `database/models.py:377-382` + `routes/admin_ewb.py:61-63`
**Issue:** `quality_score` ist ein Python `@property`, keine DB-Spalte. Das Admin-Dashboard ruft für jede Row einmal `r.quality_score` auf (Zeile 62: `scores = [r.quality_score for r in rating_rows]`). Bei Pre-Launch mit <200 Ratings ist das trivial. Aber mit 1000+ geratigen Events über den Launch wird `db.query(EwbRating).all()` + Python-List-Comprehension in `N+1`-Speicher-Laufzeit.

Das ist kein akutes Performance-Problem (raus aus v1-Scope gemäß Review-Definition), aber die `pct_high`-Berechnung könnte effizienter über SQL laufen:
```sql
SELECT
  COUNT(*) AS total,
  SUM(CASE WHEN (klingt_wie_mensch + 2*keine_halluzination + trifft_einwand) / 4.0 * 100 >= 80 THEN 1 ELSE 0 END) AS high
FROM ewb_ratings
```

**Fix:** Admin-Dashboard auf SQL-basierte Aggregation umstellen. Aber da das in v1-Scope "nicht Performance" ist, lieber als TODO markieren. Info-Level, nicht Warning — aber gelistet weil's eine Korrektheitsfrage berührt: wenn `quality_score` jemals geändert wird (z.B. andere Gewichtung), greift die Änderung sofort für alle historischen Ratings — es gibt kein Audit-Trail wie der Score zum Zeitpunkt t war. Phase 08 D-27 lockt das Formel-Pattern, aber wenn die Formel sich ändert ist die historische Konsistenz verloren.

**Korrigiertes Fix-Vorschlag:** Score bei Write snapshotten (neue Column `quality_score_snapshot` mit default=`quality_score`-Berechnung), bei Read darauf zurückgreifen. Oder explizit dokumentieren dass die Formel *nie* geändert werden darf.

## Info

### IN-01: Test `test_anrede_whitelist_rejects_invalid` testet nur den Happy-Path

**File:** `tests/test_ewb_rate_api.py:256-263`
**Issue:** Der Test kopiert die Whitelist-Logik aus `deepgram_service.py` in den Test-Body statt die echte Socket.IO-Handler-Funktion zu testen. Dadurch wird weder die Kopplung an `ls.state_lock` noch ein Mixed-Case-Input tatsächlich durch den Handler-Code geschickt. Siehe CR-02 für Mixed-Case-Fall.
**Fix:** Nutze Socket.IO-Test-Client oder factore die Whitelist in eine pure Funktion `_validate_anrede(raw) -> str | None` aus, dann teste diese direkt.

### IN-02: Doppelter `gegenargument`-Feldname auf Profile-Einwand verursacht latente Ambiguität

**File:** `services/claude_service.py:811` vs `services/deepgram_service.py:434-439` + `static/pip-launcher.js` (nicht zitiert, aber Kontext)
**Issue:** `streame_auto_variante` liest `_e.get('gegenargument_1') or _e.get('gegenargument')`. `profile_editor.html:958` schreibt das Feld als `gegenargument` (ohne Suffix). `_build_system_prompt` liest `gegen = e.get('gegenargument', '')`. Es gibt also zwei Feldnamen im Umlauf: `gegenargument` (Profile-Editor default) und `gegenargument_1` (interne Claude-Response-Semantik aus `SYSTEM_PROMPT_BASE` Zeile 59).
**Fix:** Einheitlich `gegenargument` für den User-editierten Profil-Wert behalten, `gegenargument_1`/`gegenargument_2` nur für Claude-Response reservieren. Migration: Profile-Rows mit `gegenargument_1` in Daten-JSON auf `gegenargument` renamen.

### IN-03: `app.py` Block B rebuildet Tabelle ohne Index-Preservation

**File:** `app.py:534-560`
**Issue:** Der Table-Rebuild (`CREATE TABLE objection_events_new ... / INSERT / DROP / RENAME`) erhält Indizes *nicht*, falls welche existieren. `ObjectionEvent` hat keine expliziten Indizes laut `models.py:344-353`, aber wenn in Zukunft welche hinzukommen, bricht der Rebuild sie.
**Fix:** Nach dem RENAME Indizes neu erstellen:
```python
# Post-rebuild: re-create indexes (idempotent via IF NOT EXISTS)
conn.execute(text("CREATE INDEX IF NOT EXISTS ix_objection_events_conv_log ON objection_events(conversation_log_id)"))
```

### IN-04: `test_ewb_pipeline.py` Fixture `_empty_active_profile` wird nicht von allen Tests genutzt

**File:** `tests/test_ewb_pipeline.py:52-67` + `tests/test_ewb_pipeline.py:119-141`
**Issue:** `test_seed_ewb_v2_idempotent` und `test_seed_ewb_v2_default_flags` importieren `app` (inkl. `from services.live_session import LOG_DIR`). Wenn irgendein anderer Testlauf vorher `ls.state['session_anrede']` gesetzt hat und nicht cleant, leakt State. Die Fixture `_cleanup_session_anrede` in `test_ewb_rate_api.py:228-242` ist dort `autouse=True`, aber nicht in `test_ewb_pipeline.py`.
**Fix:** Ziehe `_cleanup_session_anrede` in eine `conftest.py` mit `autouse=True` scope="module" für alle phase-08-Tests hoch.

### IN-05: Dead Branch `if active_sid:` vs `else:` tun dasselbe

**File:** `services/claude_service.py:1053-1060`
**Issue:**
```python
if active_sid:
    ergebnis = analysiere_mit_claude(neuer_text, kontext)
else:
    ergebnis = analysiere_mit_claude(neuer_text, kontext)
```
Beide Zweige rufen identisch `analysiere_mit_claude` auf. Der ursprüngliche Zweck (eigentlich PiP-Streaming-Pfad) wurde in Phase 06.3 entfernt ("Phase 06.3: analyse_loop no longer renders into PiP slots"). Der If-Else ist jetzt totes Gerüst.
**Fix:**
```python
ergebnis = analysiere_mit_claude(neuer_text, kontext)  # Phase 06.3: PiP slots no longer rendered from analyse_loop
```

### IN-06: `_seed_ewb_scenarios` kann unvollständig seeden ohne Log-Warnung

**File:** `app.py:908-911`
**Issue:** Wenn beim ersten App-Start noch keine Organisation existiert, gibt `_seed_ewb_scenarios` ein `print("[DB] Phase 08 _seed_ewb_scenarios skipped: no Organisation yet")` aus und returnt — aber baut keinen Retry-Hook. Der nächste Deploy re-triggert den Seed, weil die Idempotenz-Checks auf `name-based existing-row-check` basieren. Das ist OK, aber anzeigen könnte man es prominenter.
**Fix:** Marker in audit_log schreiben wie bei D-02:
```python
if not first_org:
    try:
        conn.execute(text("""
            INSERT INTO audit_log (action, target_type, details, created_at)
            VALUES ('seed_ewb_scenarios_deferred', 'training_scenarios',
                    '{"reason":"no_organisation_yet"}', CURRENT_TIMESTAMP)
        """))
        conn.commit()
    except Exception:
        pass
    return
```
(Optional; aktuell passt's mit Solo-Founder.)

### IN-07: `topbar-branche` CSS-Klasse definiert aber `vi_branche_select` nutzt `.fs`-Klasse

**File:** `templates/profile_editor.html:26-31` + `:339`
**Issue:** Die CSS-Klasse `.topbar-branche` ist definiert, aber das tatsächliche HTML-Element (Zeile 339) nutzt `class="fs"` (form-select). Die topbar-branche-Klasse wird im Template nirgendwo gesetzt → dead CSS.
**Fix:** `.topbar-branche`-Selector aus CSS entfernen oder das Select mit `class="topbar-branche"` versehen.

---

## Anti-Regression Observations

Drei Dinge sind in Phase 08 *explizit gut* gelöst und sollten bei zukünftigen Änderungen erhalten bleiben:

1. **W-1 Bool-Strict-Check in `api_ewb_rate`** (`routes/app_routes.py:1432-1434`): `isinstance(value, bool)` statt `value in (True, False)`. Python-Gotcha `1 == True` wird abgefangen. Test `test_rate_integer_rejected` lockt das Verhalten. Nicht ändern.
2. **Fail-open in `build_ewb_prompt`** (`services/ewb_pipeline.py:87-89`): DB-Load-Fehler → Fallback-Prompt, kein Crash in Live-Loop. Entspricht CLAUDE.md-Constraint "Live-Loop darf nie crashen".
3. **Lazy DB-Imports in `prompt_pipeline.py`**: `from database.db import SessionLocal` sitzt *innerhalb* der Funktion, nicht am Modul-Kopf. Das vermeidet Import-Zyklen und macht Tests mit `monkeypatch.setattr('database.db.SessionLocal', ...)` sauber.

---

## Empfehlungen für Follow-up-Phase / Launch-Gate

**Pre-Launch MUST-FIX:**
- CR-01 (Lock um `session_anrede`-Read) — 10-Zeilen-Fix
- CR-02 (Anrede-Whitelist normalisieren) — 5-Zeilen-Fix
- WR-04 (`path:einwand_key` + `/`-Enkodierung) — betrifft echte Kategorien mit `/` im Namen (`'Zeit/Aufschub'`)

**Pre-Launch SHOULD-FIX:**
- WR-03 (Einheitlicher Match-Helper) — reduziert UAT-Inkonsistenzen
- WR-05 (`is_default` nicht reconciled) — sonst kann Admin-Override nicht greifen, D-26 halb-broken

**Post-Launch:**
- WR-01 (`org_id`-Filter im Admin-Query) — Multi-Tenant-Phase
- WR-02 (bindparam expanding) — >1000 Ratings
- WR-07 (`rel="noopener"`) — wenn Briefing-Inhalte Links enthalten dürfen
- IN-05 (toter If-Else in `analyse_loop`) — beim nächsten Touch des Files

---

_Reviewed: 2026-04-22_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
