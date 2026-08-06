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
import textwrap
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
    # Plan 04 Familie B: _merge_lock (S4: EIN Lock = _session_state_lock) + _merge_pending (per-SID)
    '_merge_lock',
    '_merge_pending',
    # Plan 04: toter Post-Migration-Code (0 externe Reader nach per-SID-Migration)
    'transcript_buffer',
    'analysiert_bisher',
    # Plan 05 Familie C: alle per-SID migriert; Modul-Globale + ihre Locks geloescht
    'conversation_log',
    'log_lock',
    'painpoints',
    'painpoints_lock',
    'gegenargument_log',
    'gegenargument_log_lock',
    'phasen_log',
    'phasen_log_lock',
    'covered_phases',
    'covered_phases_lock',
    'kaufbereitschaft',
    'kaufbereitschaft_verlauf',
    'kb_lock',
    'aktive_phase_idx',
    'phase_lock',
    # Plan 06 Familie E: Speaker-Globale per-SID migriert (2026-07-04)
    '_log_last_sp',
    '_log_sp_lock',
    '_second_sp_seen',
    '_sp2_lock',
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
    # painpoints_lock GELOESCHT (Plan 05, Familie C per-SID migriert)
    # gegenargument_log_lock GELOESCHT (Plan 05, Familie C per-SID migriert)
    'hilfe_log_lock',
    'quick_action_log_lock',
    # phasen_log_lock GELOESCHT (Plan 05, Familie C per-SID migriert)
    'session_meta_lock',
    # log_lock GELOESCHT (Plan 05, Familie C: conversation_log per-SID migriert)
    'roles_lock',
    '_log_sp_lock',
    '_sp2_lock',
    '_speaker_lock',
    '_bof_lock',
    # kb_lock GELOESCHT (Plan 05, Familie C: kaufbereitschaft per-SID migriert)
    # phase_lock GELOESCHT (Plan 05, Familie C: aktive_phase_idx per-SID migriert — B5)
    # covered_phases_lock GELOESCHT (Plan 05, Familie C: covered_phases per-SID migriert)
    # _merge_lock GELOESCHT (Plan 04, S4: EIN Lock = _session_state_lock)
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
    # transcript_buffer/analysiert_bisher ENTFERNT (Plan 04 geloescht — in _KILLED_MODULE_GLOBALS)
    # _merge_pending ENTFERNT (Plan 04 geloescht — in _KILLED_MODULE_GLOBALS)
    # painpoints ENTFERNT (Plan 05 Familie C — in _KILLED_MODULE_GLOBALS)
    # gegenargument_log ENTFERNT (Plan 05 Familie C — in _KILLED_MODULE_GLOBALS)
    # phasen_log ENTFERNT (Plan 05 Familie C — in _KILLED_MODULE_GLOBALS)
    # conversation_log ENTFERNT (Plan 05 Familie C — in _KILLED_MODULE_GLOBALS)
    # covered_phases ENTFERNT (Plan 05 Familie C — in _KILLED_MODULE_GLOBALS)
    'coaching_buffer',
    'hilfe_log',
    'quick_action_log',
    # State-Dict (Modul-Global, PENDING-MIGRATION — Zustand wird schrittweise per-SID)
    'state',
    # Kaufbereitschaft ENTFERNT (Plan 05 Familie C — in _KILLED_MODULE_GLOBALS)
    # aktive_phase_idx ENTFERNT (Plan 05 Familie C B5 — in _KILLED_MODULE_GLOBALS)
    # Sprecher-Stabilisierung (noch Modul-Global — _confirmed_speaker/_pending_speaker/_pending_since
    # sind per-SID-Seed vorhanden UND Modul-Global fuer stabilize_speaker; Plan 06 hat sie nicht migriert).
    '_confirmed_speaker',
    '_pending_speaker',
    '_pending_since',
    # _log_last_sp GELOESCHT (Plan 06 Familie E: per-SID) — in _KILLED_MODULE_GLOBALS
    # _second_sp_seen GELOESCHT (Plan 06 Familie E: per-SID) — in _KILLED_MODULE_GLOBALS
    # _log_sp_lock GELOESCHT — in _KILLED_MODULE_GLOBALS
    # _sp2_lock GELOESCHT — in _KILLED_MODULE_GLOBALS
    # Tenant-neutrale Latenz-Caches (S6 — explizit gewhitelistet)
    # self-contained TTFT-Circuit-Breaker, kein Cross-Tenant-Zustand, 0 externe Reader
    '_ewb_ttft_history',
    '_ewb_fallback_until',
    # Trigger-Events (Signal, kein Zustand)
    'analyse_trigger',
    'coaching_trigger',
    # DEPRECATED-GLOBAL mit explizitem Pending (in _PENDING_MIGRATION aufgenommen)
    'roles_swapped',
    # aktive_phase_idx ENTFERNT (Plan 05 Familie C B5 — per-SID migriert, in _KILLED_MODULE_GLOBALS)
})

# ── _PENDING_MIGRATION: wave-getaggte legitimierte noch-unmigrierte Schreiber ─
# Format: (dateipfad_relativ, schreiber_muster_str, welle_tag)
# Der AST-Sweep ignoriert einen Verstoss NUR wenn (datei, muster) in dieser Menge steht.
# JEDE Welle (Plan 03-06) entfernt ihre Zeilen beim Migrieren → Liste schrumpft monoton.
# Plan 06 Task 3 assertiert _PENDING_MIGRATION == frozenset() (alle migriert).
_PENDING_MIGRATION: frozenset = frozenset({
    # ── Welle A / Plan 03 ─────────────────────────────────────────────────────
    # MIGRIERT (Plan 03): session_anrede, mic_muted, precall_briefing — Eintraege entfernt.
    # ── Welle B / Plan 04 ─────────────────────────────────────────────────────
    # MIGRIERT (Plan 04): _merge_pending — Eintrag entfernt.
    # ── Welle C / Plan 05 ─────────────────────────────────────────────────────
    # MIGRIERT (Plan 05): conversation_log, kaufbereitschaft, aktive_phase_idx — Eintraege entfernt.
    # ── Welle D / Plan 06 ─────────────────────────────────────────────────────
    # MIGRIERT (Plan 06 Familie D): ewb_clicks, suggestion_offers — Eintraege entfernt.
    # ── Welle E / Plan 06 ─────────────────────────────────────────────────────
    # MIGRIERT (Plan 06 Familie E): _second_sp_seen, _log_last_sp, analysiert_bisher — Eintraege entfernt.
    # _second_sp_seen + _log_last_sp: deepgram schreibt jetzt per-SID (2026-07-04).
    # analysiert_bisher: war bereits per-SID (kein globaler Write-Pfad), Eintrag war stale.
    # B3 (Plan 06 Task 3): _PENDING_MIGRATION MUSS == frozenset() sein — alle Wellen migriert.
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


# ── Test 5 (B3): _PENDING_MIGRATION MUSS leer sein (Plan 06 Task 3) ───────────

def test_pending_migration_is_empty():
    """B3: _PENDING_MIGRATION MUSS == frozenset() sein (alle Wellen A-E migriert).

    Plan 06 Welle E (letzte Welle) hat alle noch verbliebenen Eintraege geloescht:
    - Welle E: _second_sp_seen, _log_last_sp per-SID (2026-07-04)
    - Welle E: analysiert_bisher war bereits per-SID (Eintrag stale, jetzt entfernt)

    Ab jetzt ist JEDE neue nicht-per-sid Live-Zuweisung sofort rot (kein Pending-Puffer).
    Punkt 29 Halb-Migration-Falle ist vollstaendig geschlossen.
    """
    assert _PENDING_MIGRATION == frozenset(), (
        f"_PENDING_MIGRATION ist NICHT leer — {len(_PENDING_MIGRATION)} Eintrag/Eintraege:\n  "
        + "\n  ".join(f"{p} [{m}] Welle={w}" for (p, m, w) in _PENDING_MIGRATION)
        + "\n\nB3: Plan 06 Task 3 verlangt _PENDING_MIGRATION == frozenset()."
        " Alle Wellen A-E muessen vollstaendig migriert sein."
    )


# ══════════════════════════════════════════════════════════════════════════════
# Pruefpunkt 6 (Phase 08.23.2.MEHRNUTZER-REST-1): modul-globaler Riegel, der einen
# Netz-/LLM-Aufruf umschliesst.
#
# Eigene Konstanten mit eigenem Praefix — _WHITELIST oben wird BEWUSST NICHT
# mitbenutzt: sie listet erlaubte ZUWEISUNGSZIELE fuer `ls.<attr> =` und enthaelt
# dabei Riegel-Namen (state_lock, _per_sid_lock, ...). Wer sie hier mitbenutzte,
# schaltete diesen Pruefpunkt fuer die halbe Riegel-Menge still ab.
# ══════════════════════════════════════════════════════════════════════════════

_RIEGEL_SCAN_DIRS = ('services', 'routes')

# WEITE Riegel-Ableitung: jede Modul-Ebenen-Zuweisung, deren rechte Seite ein Aufruf
# ist, dessen Name auf 'Lock' endet. Faengt threading.Lock(), threading.RLock(),
# _threading.Lock() UND _TracedLock('_session_state_lock')
# (services/live_session.py:374). Ein enges Kriterium "threading.Lock()" wuerde
# ausgerechnet den wichtigsten Riegel des Projekts STILL uebersehen und die
# ueberwachte Blockmenge von 143 auf 40 senken — genau die Punkt-31-Fehlerklasse.
_RIEGEL_KONSTRUKTOR_ENDUNG = 'Lock'

# VARIANTE A (Phase MEHRNUTZER-REST-1, der wichtigste Einzelpunkt): ein Aufruf,
# dessen Funktionsname auf '_lock' oder '_lock_for' endet, gilt ebenfalls als
# Riegel-Ausdruck. OHNE das faellt der in dieser Phase gebaute
# `with _analysis_lock_for(conv_id):` aus der eigenen Bewachung — er ist ein
# ast.Call, kein Riegel-Name -> das Datei-Soll coaching_service.py muesste auf 0,
# und "ein Eintrag mit Soll 0 kann nie fehlschlagen"
# (tests/test_session_lock_blocking_calls_guard.py:200-207). Der Waechter waere
# gruen ABER BLIND. Das ist eine ERWEITERUNG der Bewachung, kein Aufweichen:
# die Menge der bewachten Bloecke wird groesser, nie kleiner.
# Gemessen 2026-08-06: kollidiert mit 0 bestehenden Bloecken.
_RIEGEL_FABRIK_ENDUNGEN = ('_lock', '_lock_for')

# ZAEHL-SEITE != MELDE-SEITE (Praezisierung nach plan-checker, RESEARCH §4.6-Nachtrag).
# Die bewachte FEHLERKLASSE ist ein FUER ALLE NUTZER GEMEINSAMER Riegel um einen
# Netz-Aufruf. Ein PER-SCHLUESSEL-Riegel ist definitionsgemaess KEIN Verstoss — er
# ist die LOESUNG. Wuerde Variante A auch die Melde-Seite erfassen, bliebe der
# Waechter nach dem Fix ROT (der Sonnet-Aufruf steht ja weiterhin im Block) und das
# gruene Tor waere unerreichbar. Deshalb:
#   Fabrik-Aufruf MIT Argument  (`_lock_for(conv_id)`) -> ZAEHLT, meldet NICHT
#   Fabrik-Aufruf OHNE Argument (`_hole_lock()`)       -> ZAEHLT, MELDET (kann gar
#                                                          nicht nach Schluessel trennen)
#   Riegel-NAME (`with _analysis_lock:`)               -> ZAEHLT, MELDET
# Das ist eine PRAEZISIERUNG, keine Aufweichung: die gemeinsame Form roetet
# unveraendert weiter, der ROT-Lauf dieser Phase bleibt Zeile fuer Zeile derselbe.

# Netz-/LLM-Katalog. BEWUSST ENG und EMPFAENGER-GEBUNDEN: ein Katalog ueber
# Methodennamen (z.B. 'get') produzierte allein durch dict.get(...) unter Riegeln
# neun Falsch-Treffer (precall_service.py:219/:285, deepgram_service.py:184/:898,
# routes/training.py:420/:482/:582/:609).
_NETZ_EMPFAENGER_MODULE = frozenset({'requests', 'httpx'})
_NETZ_MESSAGES_METHODEN = frozenset({'create', 'stream'})
_NETZ_NACKTE_NAMEN = frozenset({'http_llm_client'})

# ── Mindest-Soll (CLAUDE.md Punkt 31: Sperre gegen den stillen Ausfall) ───────
# Faellt eine abgeleitete Menge aus, faende der Sweep 0 Verstoesse und SAEHE GRUEN AUS.
# Sinkt eine Zahl: Ursache klaeren und MIT BEGRUENDUNG nachziehen — den Test NIE
# entfernen, die Zahl NIE stillschweigend senken.
_RIEGEL_SOLL_NAMEN_MINDESTENS = 23      # heute exakt 23 distinkte Namen
_RIEGEL_SOLL_SUMME_MINDESTENS = 140     # heute 143 (138 with + 5 try/finally), Puffer 3

# Stand 2026-08-06 (AST-gemessen). services/coaching_service.py ist der WICHTIGSTE
# Eintrag: er sichert, dass der in dieser Phase gebaute conv_id-Riegel auch NACH dem
# Fix noch bewacht ist.
# ⚠ HEUTE 1 (`with _analysis_lock:`). Der Fix in Plan 04 macht daraus DREI Bloecke
#   (1x `with _analysis_lock_for(conv_id):` + 2x `with _conv_locks_guard:`); Plan 04
#   Task 1 zieht den Eintrag deshalb im selben Commit auf 3 HOCH. Das ist Pflicht,
#   nicht Kosmetik: bliebe er bei 1, wuerde ihn schon die Ablage-Riegel-Haelfte allein
#   erfuellen — der Eintrag koennte den Ausfall von Variante A nicht mehr melden.
#   Hier auf 3 vorzugreifen ist NICHT moeglich: dann waere der ROT-Lauf (Plan 03) mit
#   3 statt 2 Fehlschlaegen rot und der Beleg unbrauchbar.
_RIEGEL_SOLL_JE_DATEI = {
    'routes/app_routes.py': 3,
    'routes/training.py': 9,
    'services/anonymization.py': 5,
    'services/claude_service.py': 47,
    'services/coaching_service.py': 1,
    'services/cost_tracker.py': 2,
    'services/deepgram_service.py': 27,
    'services/einwand_keyword_matcher.py': 2,
    'services/live_session.py': 41,
    'services/precall_service.py': 2,
    'services/prompt_pipeline.py': 3,
    'services/qa_pipeline.py': 1,
}

# Falsch-Treffer-Ausnahmen. HEUTE LEER. Jeder Eintrag braucht einen
# '# FALSCH-TREFFER:'-Kommentar mit Datei:Zeile und Begruendung. Ein ECHTER Fund
# gehoert NICHT hierher, sondern gemeldet und behoben.
_FALSCH_TREFFER_RIEGEL = frozenset()    # {(datei, zeile), ...}


# ── Riegel-Ableitung ─────────────────────────────────────────────────────────
def _riegel_namen_einer_datei(baum):
    """Modul-globale Riegel-Namen EINER Datei.

    Nur baum.body (echte Modul-Ebene), nicht ast.walk: ein Riegel in einer Funktion
    oder als Klassen-Attribut ist pro-Instanz und bewusst ausserhalb.
    """
    namen = set()
    for knoten in baum.body:
        if not isinstance(knoten, ast.Assign) or not isinstance(knoten.value, ast.Call):
            continue
        f = knoten.value.func
        aufruf = f.attr if isinstance(f, ast.Attribute) else getattr(f, 'id', '')
        if not aufruf.endswith(_RIEGEL_KONSTRUKTOR_ENDUNG):
            continue
        for ziel in knoten.targets:
            if isinstance(ziel, ast.Name):
                namen.add(ziel.id)
    return namen


def _riegel_namen_gesamt():
    """Vereinigung ueber alle Dateien im Sweep-Bereich. Ueber den NAMEN, nicht ueber
    den Empfaenger — so muss keine Alias-Liste gepflegt werden (Begruendung:
    tests/test_session_lock_blocking_calls_guard.py:229-231)."""
    namen = set()
    for _datei, pfad in _riegel_python_dateien():
        baum, _f = _riegel_baum_oder_fehler(pfad)
        if baum is not None:
            namen |= _riegel_namen_einer_datei(baum)
    return namen


def _ist_gemeinsamer_riegel_ausdruck(expr, namen):
    """VERSTOSS-FAEHIGER Riegel: einer, den ALLE Nutzer teilen.

    - Name/Attribut aus der abgeleiteten Menge (faengt `x`, `ls.x`, `_ls.x`,
      `modul.x` — ueber den ATTRIBUT-Namen).
    - Eine Riegel-Fabrik OHNE Argument (`_hole_lock()`): sie kann gar nicht nach
      Schluessel trennen und ist damit faktisch ein gemeinsamer Riegel.
    """
    if isinstance(expr, ast.Attribute) and expr.attr in namen:
        return True
    if isinstance(expr, ast.Name) and expr.id in namen:
        return True
    if isinstance(expr, ast.Call) and not _ist_per_schluessel_riegel_ausdruck(expr):
        f = expr.func
        aufruf = f.attr if isinstance(f, ast.Attribute) else getattr(f, 'id', '')
        if aufruf.endswith(_RIEGEL_FABRIK_ENDUNGEN):
            return True
    return False


def _ist_per_schluessel_riegel_ausdruck(expr):
    """Fabrik-Muster `_lock_for(key)`: ein Aufruf auf _lock/_lock_for MIT mindestens
    einem Argument. Das ist die LOESUNG der Fehlerklasse, kein Verstoss — er zaehlt
    fuer die Soll-Tabelle, wird aber NICHT gemeldet."""
    if not isinstance(expr, ast.Call):
        return False
    f = expr.func
    aufruf = f.attr if isinstance(f, ast.Attribute) else getattr(f, 'id', '')
    return bool(aufruf.endswith(_RIEGEL_FABRIK_ENDUNGEN)
                and (expr.args or expr.keywords))


def _ist_riegel_ausdruck(expr, namen):
    """ZAEHL-Seite: alles, was ein bewachter Riegel-Block ist — gemeinsam ODER
    per Schluessel. Diese Menge darf nur wachsen, nie schrumpfen."""
    return (_ist_gemeinsamer_riegel_ausdruck(expr, namen)
            or _ist_per_schluessel_riegel_ausdruck(expr))


def _riegel_with_bloecke(baum, namen, praedikat=None):
    """Jedes ast.With, bei dem IRGENDEIN Kontext-Ausdruck ein Riegel ist —
    auch `with anderer, _session_state_lock:`.

    praedikat=None -> ZAEHL-Seite (alle Riegel-Bloecke).
    praedikat=_ist_gemeinsamer_riegel_ausdruck -> MELDE-Seite (nur gemeinsame)."""
    praedikat = praedikat or _ist_riegel_ausdruck
    return [k for k in ast.walk(baum)
            if isinstance(k, ast.With)
            and any(praedikat(i.context_expr, namen) for i in k.items)]


def _ist_riegel_freigabe(call, namen, praedikat=None):
    praedikat = praedikat or _ist_riegel_ausdruck
    f = call.func
    return (isinstance(f, ast.Attribute) and f.attr == 'release'
            and praedikat(f.value, namen))


def _riegel_try_bloecke(baum, namen, praedikat=None):
    """Jedes ast.Try, dessen finally-Zweig einen Riegel FREIGIBT. Verankert an der
    FREIGABE, nicht am Erwerb: das release() markiert das Ende der Region eindeutig,
    waehrend der Erwerb je nach Form eine Zeile hoeher oder im if-Test steht.
    Heute 5 solche Regionen (deepgram_service.py 1, live_session.py 4). Der Sammler
    kommt trotzdem mit: sonst fiele ein kuenftiger Umbau von `with` auf
    `acquire`/`try` STILL aus der Bewachung."""
    return [k for k in ast.walk(baum)
            if isinstance(k, ast.Try)
            and any(isinstance(n, ast.Call)
                    and _ist_riegel_freigabe(n, namen, praedikat)
                    for anw in k.finalbody for n in ast.walk(anw))]


def _riegel_region(try_knoten, namen, praedikat=None):
    """Die Anweisungen, die WIRKLICH unter dem Riegel laufen: body + orelse +
    except-Ruempfe + finally-Anweisungen VOR dem release. Ab dem release ist frei."""
    region = list(try_knoten.body) + list(try_knoten.orelse)
    for behandler in try_knoten.handlers:
        region.extend(behandler.body)
    for anw in try_knoten.finalbody:
        if any(isinstance(n, ast.Call)
               and _ist_riegel_freigabe(n, namen, praedikat)
               for n in ast.walk(anw)):
            break
        region.append(anw)
    return region


# ── Netz-/LLM-Pruefung (genau EINE, fuer beide Formen) ───────────────────────
def _ist_netz_aufruf(call):
    """Melde-Name des Netz-/LLM-Aufrufs, sonst None. EMPFAENGER-gebunden."""
    f = call.func
    if isinstance(f, ast.Name):
        return f.id if f.id in _NETZ_NACKTE_NAMEN else None
    if isinstance(f, ast.Attribute):
        if (f.attr in _NETZ_MESSAGES_METHODEN
                and isinstance(f.value, ast.Attribute) and f.value.attr == 'messages'):
            return 'messages.' + f.attr
        if (isinstance(f.value, ast.Name)
                and f.value.id in _NETZ_EMPFAENGER_MODULE):
            return f'{f.value.id}.{f.attr}'
    return None


def _netz_aufrufe_in(knoten_oder_liste):
    """ast.walk geht auch in verschachtelte with/try/if-Bloecke: ein messages.create
    zwei Ebenen tief im selben Riegel-Block ist genauso schaedlich."""
    knoten = (knoten_oder_liste if isinstance(knoten_oder_liste, list)
              else [knoten_oder_liste])
    treffer = []
    for wurzel in knoten:
        for n in ast.walk(wurzel):
            if isinstance(n, ast.Call):
                name = _ist_netz_aufruf(n)
                if name:
                    treffer.append((getattr(n, 'lineno', 0), name))
    return treffer


# ── Datei-Sweep (uebernommen aus test_session_lock_blocking_calls_guard.py) ──
def _riegel_python_dateien():
    """__pycache__ wird uebersprungen — .pyc ist kein Quelltext, und stale Bytecode war
    in Phase COUNTERPART-03 der einzige verbliebene Falsch-Treffer. rglob statt glob:
    Unterordner von services//routes/ sind damit mit abgedeckt (heute existieren keine)."""
    ergebnis = []
    for d in _RIEGEL_SCAN_DIRS:
        for p in (_ROOT / d).rglob('*.py'):
            if '__pycache__' in p.parts:
                continue
            ergebnis.append((p.relative_to(_ROOT).as_posix(), p))
    return sorted(ergebnis)


def _riegel_baum_oder_fehler(pfad):
    """Kein errors='ignore': ein Dekodier-Fehler soll auffallen, nicht still einen
    Block verschlucken."""
    try:
        return ast.parse(pfad.read_text(encoding='utf-8')), None
    except (SyntaxError, UnicodeDecodeError) as e:
        return None, f'{type(e).__name__}: {e}'


def _riegel_zaehlung(baum, namen):
    """(anzahl_with, anzahl_try) fuer eine Datei."""
    return len(_riegel_with_bloecke(baum, namen)), len(_riegel_try_bloecke(baum, namen))
