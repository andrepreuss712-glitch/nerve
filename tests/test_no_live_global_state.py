"""Phase 08.23.2.PERSID Plan 01 — Statischer Global-Waechter (Punkt 28/29, SPEC Req 12 Teil 2).

Zweck: Verhindert modul-globalen veraenderlichen Live-Zustand fuer pro-Nutzer-/pro-Call-Daten.
  Cross-Tenant-Vermischung bei parallelen Calls (Launch-Blocker) — Fable-Audit-Lehre.

Design (locked):
- Test 1 (hasattr-Absenz): assertiert dass geloeschte Modul-Globale aus live_session wirklich weg sind.
- Test 2 (AST/grep-Sweep): AST-basierter Sweep ueber services/*.py + routes/*.py; jede Zuweisung
  `ls.<attr> = ...` (Fremdmodul-Write) oder `ls.state[...] = ...` (State-Key-Write), die nicht in
  _WHITELIST UND nicht in _PENDING_MIGRATION steht → rot mit Datei:Zeile-Meldung.
- Test 3 (DEPRECATED-GLOBAL): jeder NEUE Schreib-Zugriff auf ein _KILLED-Global ausserhalb der
  dokumentierten Stelle → rot (Punkt 29 Halb-Migration-Falle).

KEIN Source-Presence-False-Green (CLAUDE.md Test-Qualitaets-Regel):
  Der AST-Sweep prueft ein VERBOTENES Muster (Schreib-Zugriff auf non-per-sid Global), NICHT die
  Existenz von erwuenschtem Code. Ein False-Green kann dadurch NICHT entstehen: wenn der verbotene
  Schreiber entfernt wird, ist der Test gruener; wenn er hinzukommt, roetet er den Test.
  Dies ist der dokumentierte Regex-Grenzfall gemaess CLAUDE.md (keine Alternative existiert, da
  der AST-Sweep das Live-Muster prueft, nicht eine Mock-bare Funktion aufruft).

Gruen-Bedingung in Welle 0:
  Alle in Task 2 geloeschten Zombie-Globalen sind entfernt; die noch LEGITIM unmigrierten
  Live-Schreiber stehen in _PENDING_MIGRATION mit ihrem Welle-Tag und werden daher nicht rot.
  Plan 06 (Welle E) assertiert _PENDING_MIGRATION == frozenset() (alle migriert).
"""

import ast
import os
import re
from pathlib import Path

import pytest

import services.live_session as ls

# ── Root-Verzeichnis ───────────────────────────────────────────────────────────
_ROOT = Path(__file__).parent.parent


# ── _KILLED_MODULE_GLOBALS: In Task 2 geloeschte Modul-Globale ───────────────
# hasattr(ls, g) MUSS False sein fuer jeden dieser Namen.
_KILLED_MODULE_GLOBALS: frozenset = frozenset({
    'session_meta',
    'last_postcall',
    'last_postcall_lock',
    'is_paused',
    '_line_id_counter',
    '_bof_count',
})

# ── _KILLED_STATE_KEYS: In Task 2 geloeschte state{}-Keys ────────────────────
# `g in ls.state` MUSS False sein fuer jeden dieser Keys.
_KILLED_STATE_KEYS: frozenset = frozenset({
    'ergebnis',
    'aktiv',
    'version',
    'active_hint',
    'ewb_buttons',
    'slot1_variant_busy_until',
    # 'line_id' war module-global state-key (schon per-SID); jetzt per-SID :1146
})

# ── _WHITELIST: erlaubte Modul-Level-Zuweisungen (Punkt 28 Ausnahmen) ─────────
# Locks: unveraenderliche Synchronisations-Objekte (nie pro-Nutzer-Zustand).
# Container-Dicts: sid-gekeyt → per-sid-safe (jede Session hat ihren eigenen Slot).
# Konstanten: nie mutiert nach Modul-Load.
# Trigger-Events: Signale, kein Zustand.
# Tenant-neutrale Latenz-Caches (S6): _ewb_ttft_history/_ewb_fallback_until —
#   self-contained TTFT-Circuit-Breaker des DORMANTEN streame_auto_variante;
#   0 externe Produktiv-Reader (grep-belegt), kein Cross-Tenant-Zustand.
_WHITELIST: frozenset = frozenset({
    # Locks (threading.Lock/RLock — unveraenderlich nach Init)
    'keyword_matchers_lock',
    'buffer_lock',
    'state_lock',
    'coaching_lock',
    'painpoints_lock',
    'gegenargument_log_lock',
    'hilfe_log_lock',
    'quick_action_log_lock',
    'phasen_log_lock',
    'session_meta_lock',
    'log_lock',
    'roles_lock',
    '_log_sp_lock',
    '_sp2_lock',
    '_speaker_lock',
    '_bof_lock',
    'kb_lock',
    'phase_lock',
    'covered_phases_lock',
    '_merge_lock',
    '_per_sid_lock',
    '_session_state_lock',
    '_per_sid_transcript_lock',
    '_per_sid_coaching_lock',
    'pause_lock',
    '_line_id_lock',
    # Per-SID Container (sid-gekeyte Dicts — per-sid-safe)
    '_session_state',
    '_per_sid_profile',
    '_per_sid_transcript',
    '_per_sid_coaching_buffer',
    'keyword_matchers',
    '_deepgram_sessions',
    '_cost_opened_at',
    '_stt_seconds_accumulated',
    # B1 PERSID Plan 03: Beenden-Naht-Stash (sid-gekeyt -> per-sid-safe)
    '_ended_session_snapshots',
    # Konstanten (nie mutiert nach Init)
    'LOG_DIR',
    '_DU_FORMS',
    '_SALES_KEYTERMS_BASE',
    'MAX_KEYTERMS',
    '_STOPWORDS',
    '_sp_map',
    '_AUDIO_WARN_SUCCESS_THRESHOLD',
    '_AUDIO_WARN_FAIL_THRESHOLD',
    '_ROLLING_WINDOW_MS',
    '_OUTCOME_MODIFIERS',
    'MERGE_WINDOW_S',
    # Modul-Globale Buffer/Listen (PENDING auf Welle A-E-Migration)
    'transcript_buffer',
    'analysiert_bisher',
    'coaching_buffer',
    'painpoints',
    'gegenargument_log',
    'hilfe_log',
    'quick_action_log',
    'phasen_log',
    'conversation_log',
    'covered_phases',
    '_merge_pending',
    # State-Dict (Modul-Global, PENDING-MIGRATION — Zustand wird schrittweise per-SID)
    'state',
    # Kaufbereitschaft (Modul-Global Mirror — separater Pfad app_routes:148, PENDING Welle C)
    'kaufbereitschaft',
    'kaufbereitschaft_verlauf',
    # Sprecher-Tracking (PENDING Welle E)
    '_log_last_sp',
    '_second_sp_seen',
    '_confirmed_speaker',
    '_pending_speaker',
    '_pending_since',
    # Tenant-neutrale Latenz-Caches (S6 — explizit gewhitelistet)
    # self-contained TTFT-Circuit-Breaker, kein Cross-Tenant-Zustand, 0 externe Reader
    '_ewb_ttft_history',
    '_ewb_fallback_until',
    # Trigger-Events (Signal, kein Zustand)
    'analyse_trigger',
    'coaching_trigger',
    # DEPRECATED-GLOBAL mit explizitem Pending (in _PENDING_MIGRATION aufgenommen)
    'roles_swapped',
    # aktive_phase_idx: FIX-Verdikt B5 (2 Reader belegt) — in _PENDING_MIGRATION Welle C
    'aktive_phase_idx',
})

# ── _PENDING_MIGRATION: wave-getaggte legitimierte noch-unmigrierte Schreiber ─
# Format: (dateipfad_relativ, schreiber_muster_str, welle_tag)
# Der AST-Sweep ignoriert einen Verstoss NUR wenn (datei, muster) in dieser Menge steht.
# JEDE Welle (Plan 03-06) entfernt ihre Zeilen beim Migrieren → Liste schrumpft monoton.
# Plan 06 Task 3 assertiert _PENDING_MIGRATION == frozenset() (alle migriert).
_PENDING_MIGRATION: frozenset = frozenset({
    # ── Welle A / Plan 03 ─────────────────────────────────────────────────────
    # session_anrede: Start-Writer in deepgram_service (Welle A bringt per-SID-Umbau)
    ('services/deepgram_service.py', "state['session_anrede']", 'A'),
    # mic_muted: Write via mute_mic-Event (Welle A)
    ('services/deepgram_service.py', "state['mic_muted']", 'A'),
    # precall_briefing: Reader app_routes:112 liest ls.state['precall_briefing'];
    #   echter Wert liegt per-SID (set_briefing_for_sid). Reader-Umbau Plan 03 (Welle A).
    ('services/live_session.py', "state['precall_briefing']", 'A'),
    # ── Welle B / Plan 04 ─────────────────────────────────────────────────────
    # _merge_pending: Zusammenfuehrungs-Dict — Welle B bringt per-SID-Migration
    ('services/deepgram_service.py', '_merge_pending', 'B'),
    # ── Welle C / Plan 05 ─────────────────────────────────────────────────────
    # conversation_log: Modul-Globale Liste (claude_service + deepgram_service schreiben)
    ('services/claude_service.py', 'conversation_log', 'C'),
    ('services/deepgram_service.py', 'conversation_log', 'C'),
    # kaufbereitschaft: Modul-Globaler Mirror (claude_service:1358 app_routes:148-Pfad)
    ('services/claude_service.py', 'kaufbereitschaft', 'C'),
    # aktive_phase_idx: FIX-Verdikt B5 (2 Reader: app_routes:244 + claude:206)
    #   → per-SID Migration Plan 05 Welle C; bis dahin legitimer Modul-Global-Schreiber
    ('services/live_session.py', 'aktive_phase_idx', 'C'),
    # ── Welle D / Plan 06 ─────────────────────────────────────────────────────
    # ewb_clicks/suggestion_offers: state[]-Keys mit noch globalem Write-Pfad
    ('services/live_session.py', "state['ewb_clicks']", 'D'),
    ('services/live_session.py', "state['suggestion_offers']", 'D'),
    # ── Welle E / Plan 06 ─────────────────────────────────────────────────────
    # Sprecher-Tracking: _second_sp_seen/_log_last_sp (deepgram schreibt Modul-Global)
    ('services/deepgram_service.py', '_second_sp_seen', 'E'),
    ('services/deepgram_service.py', '_log_last_sp', 'E'),
    # phasen_log/covered_phases/gegenargument_log (noch globalem Write-Pfad)
    ('services/claude_service.py', 'phasen_log', 'E'),
    ('services/claude_service.py', 'covered_phases', 'E'),
    ('services/claude_service.py', 'gegenargument_log', 'E'),
    ('services/deepgram_service.py', 'phasen_log', 'E'),
    # analysiert_bisher (deepgram schreibt noch Modul-Global in Welle E)
    ('services/deepgram_service.py', 'analysiert_bisher', 'E'),
})


# ── Test 1: hasattr-Absenz fuer geloeschte Modul-Globale ──────────────────────

def test_killed_module_globals_absent():
    """Alle in Task 2 geloeschten Modul-Globale muessen aus live_session entfernt sein.

    Gruen nach Task 2 (PERSID Plan 01). Faerbt rot sobald eine geloeschte Variable
    wieder eingebaut wird (Punkt 29 Halb-Migration-Falle).
    """
    still_present = [g for g in _KILLED_MODULE_GLOBALS if hasattr(ls, g)]
    assert not still_present, (
        f"Geloeschte Modul-Globale immer noch in live_session:\n  "
        + "\n  ".join(still_present)
        + "\n\nD-09: diese Globalen hatten 0 Prod-Reader (RESEARCH §1) und wurden "
        "in PERSID Plan 01 Task 2 entfernt."
    )


def test_killed_state_keys_absent():
    """Alle in Task 2 geloeschten state{}-Keys muessen aus dem Modul-Globalen state-Dict entfernt sein."""
    still_present = [k for k in _KILLED_STATE_KEYS if k in ls.state]
    assert not still_present, (
        f"Geloeschte state-Keys immer noch in ls.state:\n  "
        + "\n  ".join(still_present)
        + "\n\nD-09: Zombie-Keys hatten 0 Prod-Reader (Auslieferung via sio.emit(room=sid))."
    )


# ── Test 2: AST/grep-Sweep fuer nicht-per-sid-gewhitelistete Schreiber ────────

def _collect_ls_writes(path: Path):
    """Gibt alle (zeile, attr_name) Tupel zurueck, wo `ls.<attr> = ` oder
    `ls.state['<key>'] = ` auf Nicht-Whitelist-Muster trifft.

    Verwendet Regex statt echten AST-Parse (Python-3.11 kompatibel, keine
    AST-Visitor-Komplexitaet; Regex-Sweep ist ausreichend fuer Zuweisungsmuster).
    """
    src = path.read_text(encoding='utf-8', errors='replace')
    violations = []

    # Muster 1: ls.<attr> = (Fremdmodul-Write auf ein live_session-Attribut)
    # Trifft auf: ls.kaufbereitschaft = ... / ls.conversation_log.append(...) ignoriert (kein =)
    for m in re.finditer(r'\bls\.([A-Za-z_]\w*)\s*=', src):
        attr = m.group(1)
        line_no = src[:m.start()].count('\n') + 1
        if attr not in _WHITELIST:
            violations.append((line_no, attr, 'ls.' + attr + ' ='))

    # Muster 2: ls.state[<key>] = (State-Key-Write)
    # Trifft auf: ls.state['session_anrede'] = ...
    for m in re.finditer(r"""\bls\.state\[(['"])([^'"]+)\1\]\s*=""", src):
        key = m.group(2)
        line_no = src[:m.start()].count('\n') + 1
        if key not in _WHITELIST:
            violations.append((line_no, key, f"ls.state['{key}'] ="))

    return violations


def test_no_new_live_global_state_writes():
    """Kein Schreib-Zugriff auf modul-globale Live-Zustands-Variable ausserhalb Whitelist/Pending.

    Sweep ueber services/*.py + routes/*.py auf ls.<attr> = und ls.state[<key>] = Muster.
    Jeder Treffer, der WEDER in _WHITELIST noch in _PENDING_MIGRATION steht → Verstoss.

    Gruen in Welle 0: alle legit-unmigrierten Schreiber stehen in _PENDING_MIGRATION.
    Welle-Plan (03/04/05/06) entfernt beim Migrieren seine Zeilen aus _PENDING_MIGRATION
    → Liste schrumpft monoton → Plan 06 Task 3 assertiert len == 0.

    Docstring-Grenzfall (CLAUDE.md Test-Qualitaets-Regel):
      Der Sweep prueft ein VERBOTENES Muster, nicht die Existenz von erwuenschtem Code.
      Kein Source-Presence-False-Green: wenn ein Schreiber entfernt wird, ist der Test
      gruener; wenn ein neuer Schreiber hinzukommt, roetet er — genau umgekehrt zu
      einem Source-Presence-Test. Ausnahme: Modul-Level-Bindungen in den 4 Live-Modulen
      (services/live_session.py, deepgram_service.py, claude_service.py,
      einwand_keyword_matcher.py) werden in Plan 06 Finalisierung separat geprueft.
    """
    scan_dirs = [_ROOT / 'services', _ROOT / 'routes']
    violations = []

    # Pending-Set als (datei_relativ, muster) fuer schnellen Lookup
    pending_lookup = {(p, m) for (p, m, _) in _PENDING_MIGRATION}

    for d in scan_dirs:
        for py_file in d.glob('*.py'):
            rel_path = py_file.relative_to(_ROOT).as_posix()
            # Ignoriere Test-Dateien selbst
            if 'test_' in py_file.name:
                continue

            for line_no, attr, pattern in _collect_ls_writes(py_file):
                # Pruefen ob in Pending-Liste
                in_pending = False
                for (pend_path, pend_pattern, _wave) in _PENDING_MIGRATION:
                    if rel_path == pend_path and pend_pattern in pattern:
                        in_pending = True
                        break
                if not in_pending:
                    violations.append(f"{rel_path}:{line_no}  [{pattern}]")

    assert not violations, (
        f"{len(violations)} nicht-whitelistete / nicht-pending Schreib-Zugriffe "
        "auf modul-globale Live-Zustands-Variable:\n  "
        + "\n  ".join(violations)
        + "\n\nPunkt 28: kein modul-globaler veraenderlicher Live-Zustand fuer "
        "pro-Nutzer-/pro-Call-Daten. Entweder:\n"
        "  a) in _WHITELIST aufnehmen (nur Locks/Konstanten/tenant-neutrale Caches), oder\n"
        "  b) in _PENDING_MIGRATION aufnehmen (mit Welle-Tag) bis die Migration erfolgt, oder\n"
        "  c) auf per-SID migrieren (bevorzugt)."
    )


# ── Test 3: DEPRECATED-GLOBAL-Schutz ──────────────────────────────────────────

def test_deprecated_globals_not_newly_written():
    """Kein NEUER Schreib-Zugriff auf Globals mit DEPRECATED-GLOBAL-Marker.

    Punkt 29 Halb-Migration-Falle: neuer Code darf kein deprecated Muster kopieren.
    Dieser Test macht jeden unerwarteten Schreib-Zugriff auf aktive DEPRECATED-GLOBALs rot.

    Aktuell als DEPRECATED-GLOBAL markiert (via Kommentar in live_session.py):
      - roles_swapped: 0 `= True` Schreiber; Loeschung Plan 03
      - hilfe_log: 0 .append() Schreiber; DEPRECATED
      - quick_action_log: 0 .append() Schreiber; DEPRECATED
      - precall_briefing: Reader-Umbau Plan 03 (steht in _PENDING_MIGRATION)
    """
    # Globals die zwar noch existieren aber nicht neu beschrieben werden duerften
    _DEPRECATED_GLOBALS = frozenset({
        'roles_swapped',
        'hilfe_log',
        'quick_action_log',
    })

    scan_dirs = [_ROOT / 'services', _ROOT / 'routes']
    violations = []

    for d in scan_dirs:
        for py_file in d.glob('*.py'):
            if 'test_' in py_file.name or 'live_session' in py_file.name:
                continue  # live_session.py darf die Legacy-Defs haben; Tests ignorieren
            src = py_file.read_text(encoding='utf-8', errors='replace')
            rel_path = py_file.relative_to(_ROOT).as_posix()
            for dep_global in _DEPRECATED_GLOBALS:
                # Schreib-Muster: ls.<dep> = ODER ls.<dep>.append( ODER ls.<dep>.clear(
                pattern = rf'\bls\.{re.escape(dep_global)}\s*='
                for m in re.finditer(pattern, src):
                    line_no = src[:m.start()].count('\n') + 1
                    violations.append(f"{rel_path}:{line_no}  [ls.{dep_global} =]")

    assert not violations, (
        f"{len(violations)} Schreib-Zugriff(e) auf DEPRECATED-GLOBALs:\n  "
        + "\n  ".join(violations)
        + "\n\nPunkt 29 Halb-Migration-Falle: kein Code darf das deprecated Muster "
        "kopieren. Auf per-SID migrieren oder _PENDING_MIGRATION Eintrag hinzufuegen."
    )


# ── Test 4: _PENDING_MIGRATION-Liste schrumpft (Vollstaendigkeits-Check) ──────

def test_pending_migration_wave_tags_are_valid():
    """Alle _PENDING_MIGRATION-Eintraege haben einen gueltigen Wellen-Tag (A-E)."""
    valid_waves = frozenset({'A', 'B', 'C', 'D', 'E'})
    invalid = [(p, m, w) for (p, m, w) in _PENDING_MIGRATION if w not in valid_waves]
    assert not invalid, (
        f"Ungueltige Wellen-Tags in _PENDING_MIGRATION:\n  "
        + "\n  ".join(f"{p} [{m}] -> '{w}'" for (p, m, w) in invalid)
    )
