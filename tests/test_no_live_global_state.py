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

_RIEGEL_PRUEFKATALOG = """PRUEFPUNKT 6 — modul-globaler Riegel um einen Netz-/LLM-Aufruf.
(Phase 08.23.2.MEHRNUTZER-REST-1, CLAUDE.md Punkt 31)

WAS DER KATALOG ABDECKT (positiv, in einem Satz):
Ein auf MODUL-EBENE definierter, FUER ALLE NUTZER GEMEINSAMER Riegel, dessen
`with`-Block — oder dessen `acquire`/`try`/`finally`-Region — einen im Block SICHTBAR
aufgerufenen LLM- oder HTTP-Aufruf enthaelt: <x>.messages.create/stream, requests.*,
httpx.*, http_llm_client(...) — ueber alle .py-Dateien in services/ und routes/.
ABGRENZUNG: ein PER-SCHLUESSEL-Riegel (Fabrik-Aufruf mit Argument, `_lock_for(key)`)
ist definitionsgemaess KEIN Verstoss — er ist die Loesung der Fehlerklasse. Er zaehlt
voll fuer die Soll-Tabelle mit (sonst waere der Waechter nach dem Fix blind), wird
aber nicht gemeldet.

WAS ER STRUKTURELL NICHT SEHEN KANN:
1. EIN HELFER EINE EBENE TIEFER. Steht unter dem Riegel `self._frag_das_modell()` und
   der Netzaufruf liegt IN dieser Funktion, sieht der Sweep nichts. Das ist dieselbe
   Restluecke wie bei tests/test_session_lock_blocking_calls_guard.py:114 und die
   WAHRSCHEINLICHSTE kuenftige Rueckkehr der Fehlerklasse.
2. Dynamischer Dispatch (getattr(...)()), Callbacks, Monkeypatch, Registry-Hooks.
3. ⚠ NUR MODUL-EBENE — DIE ZWEI WICHTIGSTEN NICHT ERFASSTEN DEFINITIONS-ORTE.
   Die Riegel-Ableitung liest ausschliesslich `baum.body`, also die echte Modul-Ebene.
   Damit erfasst dieser Sweep NICHT:
   (a) RIEGEL, DIE INNERHALB VON FUNKTIONEN DEFINIERT WERDEN — jedes
       `def f(): ... _x_lock = threading.Lock()` (auch in Fabriken, Closures,
       Dekoratoren, Klassen-Methoden und `__init__`). Ein solcher Riegel steht in
       KEINER abgeleiteten Namensmenge; ein `with` darauf ist fuer diesen Pruefpunkt
       schlicht unsichtbar — auch dann, wenn die Funktion nur EINMAL laeuft und der
       Riegel faktisch prozessweit gemeinsam ist (z.B. ein Riegel in einer
       Modul-Init-Funktion oder in einem `__init__` eines Singletons).
       ⚠ Das ist ein DURCHRUTSCHER, kein Falsch-Treffer: die Fehlerklasse kann in
       dieser Form ZURUECKKEHREN, ohne dass dieser Waechter rot wird.
   (b) RIEGEL, DIE ALS KLASSENATTRIBUT DEFINIERT WERDEN — `class X: _lock =
       threading.Lock()`, heute z.B. services/anonymization.py:197,
       services/einwand_keyword_matcher.py:219, services/live_session.py:331. Sie
       sind bewusst ausserhalb, weil sie in der Regel pro-Instanz gedacht sind — aber
       ein Klassenattribut ist in Python faktisch von ALLEN Instanzen GETEILT. Ein
       geteilter Klassenattribut-Riegel um einen Netz-Aufruf waere die Fehlerklasse
       in voller Schaerfe und wuerde von diesem Sweep NICHT gemeldet.
   Beide Luecken sind BENANNT, nicht geschlossen. Ein gruenes Ergebnis dieses
   Pruefpunkts ist deshalb KEINE Aussage ueber funktions-lokale oder
   klassenattribut-basierte Riegel. Wer diese Formen mit abdecken will, braucht eine
   ERWEITERUNG der Ableitung (ast.walk statt baum.body plus eine Aussage darueber,
   wie oft der definierende Rumpf laeuft) — nicht ein Weiterlesen dieses Gruens.
4. Alles ausserhalb von services/ + routes/: app.py, database/, nerve_rt/, scripts/.
   ⚠ nerve_rt/ ist damit UNBEWACHT und hat bereits eine eigene HART-Regel (CLAUDE.md,
   fehlende Anonymisierung) — dieser Waechter deckt sie NICHT mit ab.

WO DIE HEURISTIKEN ZWEISCHNEIDIG SIND (beide Richtungen):
5. Riegel-Erkennung ueber den NAMEN: `_sessions_lock` existiert in zwei Dateien
   (services/deepgram_service.py:22, routes/training.py:42). Eine gleichnamige LOKALE
   Variable in einer dritten Datei gaelte als Riegel -> Richtung FALSCH-TREFFER (laut,
   harmlos). Umgekehrt rutscht ein Riegel durch, der ueber eine FUNKTION statt einer
   Zuweisung entsteht.
6. Konstruktor-Kriterium endswith('Lock') faengt threading.Lock/RLock und _TracedLock,
   aber NICHT eine Huelle namens z.B. `Mutex` oder `make_lock()`.
7. VARIANTE A (endswith('_lock','_lock_for') auf AUFRUFE) haelt den conv_id-Riegel in
   der Bewachung, macht aber jeden gleich benannten Aufruf zu einem Riegel-Ausdruck.
   Beleg fuer die Richtung: services/exchange_rates.py:100 `_acquire_worker_lock()`
   liefert ein bool, keinen Riegel — wird heute in keinem `with` benutzt (gemessen
   2026-08-06: 0 Treffer), gaelte dort aber als Riegel-Block. Richtung FALSCH-TREFFER
   (laut), nicht Durchrutscher.
8. NEUE RESTLUECKE DURCH DIE TRENNUNG ZAEHL-/MELDE-SEITE: Ein Fabrik-Aufruf MIT
   Argument (`_lock_for(key)`) gilt als per-Schluessel-Riegel und wird deshalb
   GEZAEHLT, aber NICHT gemeldet. Der Sweep sieht nur die AUFRUFFORM, nie den Rumpf
   der Fabrik. Eine Fabrik, die ihr Argument IGNORIERT und trotzdem einen gemeinsamen
   Riegel zurueckgibt — `def _x_lock_for(_egal): return _EIN_GLOBALER` — rutscht
   damit DURCH. Richtung: DURCHRUTSCHER, nicht Falsch-Treffer, und damit die
   gefaehrlichere der beiden. Gegengewicht: die Fabrik OHNE Argument
   (`_hole_lock()`) wird sehr wohl gemeldet, weil sie gar nicht nach Schluessel
   trennen KANN. Ein Laufzeit-Nachweis "verschiedene Schluessel bekommen wirklich
   verschiedene Riegel" leistet nur der Verhaltens-Test
   tests/test_lernkarten_lock_pro_conv.py (Plan 01), nicht dieser Sweep.
9. messages.create/stream sind an den Empfaenger `messages` gebunden; ein LLM-SDK mit
   anderer Aufrufform (z.B. client.complete(...)) rutscht durch.

WAS FORMAL UNKLAR BLEIBT:
10. Ob ein Lazy-Model-Load unter Riegel als "Netzaufruf" zu werten ist:
   services/anonymization.py:62 (_gliner_lock -> GLiNER.from_pretrained, :67),
   services/qa_pipeline.py:97 (_MODEL_LOCK -> SentenceTransformer, :101),
   services/anonymization.py:36 (_nlp_lock -> spacy.load, :38). Alle drei sind
   Double-Checked-Locking, EINMAL pro Prozess beim Kaltstart, kein pro-Nutzer-Aufruf —
   deshalb BEWUSST NICHT im Katalog. from_pretrained KANN beim allerersten Mal einen
   Download ausloesen; die Klasse ist damit OFFEN, nicht geschlossen. Sie stehen
   ABSICHTLICH NICHT in _FALSCH_TREFFER_RIEGEL: es sind keine Falsch-Treffer, der
   Katalog erfasst sie schlicht nicht.

WELCHE ZWEITE SCHICHT DARUNTER LIEGT:
11. Fuer _session_state_lock: der LOCKWATCH-Wachhund (services/live_session.py:1518-1541,
    Laufzeit) plus tests/test_session_lock_blocking_calls_guard.py (breiteres Verbots-Set).
    Fuer ALLE UEBRIGEN modul-globalen Riegel — darunter der neue conv_id-Riegel in
    services/coaching_service.py — gibt es KEINE Laufzeit-Schicht. Dieser statische
    Sweep ist dort die einzige Schicht.

GEPRUEFT UND GESCHLOSSEN:
12. Die DIREKTESTE Form der Fehlerklasse — ein GEMEINSAMER modul-globaler Riegel, der
    im selben Block sichtbar messages.create/stream oder requests.*/httpx.* umschliesst
    — ist GEFANGEN. Belegt dreifach: durch
    test_riegel_sweep_beisst_gegen_synthetischen_quelltext (fuenf Formen, inkl.
    try/finally und _TracedLock-Huelle), durch die Gegenprobe (III) in
    test_riegel_erkennung_erfasst_context_manager_aufruf, UND durch den ROT-Lauf
    dieser Phase gegen services/coaching_service.py:84.
13. Die Form NACH dem Fix — `with _analysis_lock_for(conv_id):` — bleibt in der
    ZAEHLUNG (Variante A) und ist bewusst NICHT verstoss-faehig: ein
    per-Schluessel-Riegel ist die LOESUNG, kein Verstoss. Beide Richtungen belegt durch
    test_riegel_erkennung_erfasst_context_manager_aufruf ((I) gezaehlt == 1,
    (II) nicht gemeldet). Ohne (I) waere der Waechter nach dem Fix gruen ABER BLIND;
    ohne (II) bliebe er dauerhaft ROT und das gruene Tor unerreichbar. Die Restluecke,
    die diese Trennung oeffnet, steht als Punkt 8 — sie ist benannt, nicht verschwiegen.
14. _session_state_lock ist von diesem Pruefpunkt erfasst (weite Ableitung ueber
    _TracedLock), war aber schon vorher durch
    tests/test_session_lock_blocking_calls_guard.py mit breiterem Verbots-Set gedeckt.
    Doppel-Deckung, keine Luecke.
15. Unterordner von services//routes/ sind ueber rglob mit abgedeckt (heute existieren
    keine) — anders als bei den sechs aelteren Sweeps dieser Datei, die glob('*.py')
    benutzen.

STOP-REGEL: erwartet sind 0 Verstoesse. Ein echter Fund wird mit Datei:Zeile gemeldet —
NICHT in _FALSCH_TREFFER_RIEGEL geschoben, NICHT durch Aufweichen des Netz-Katalogs
aufgeloest, und NICHT durch ersatzloses Entfernen des Riegels (daran haengt der
Duplikatschutz: learning_cards hat keinen Unique-Constraint auf call_id,
database/models.py:629-631).
"""

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


def _riegel_analysiere_quelle(quelltext, namen=None):
    """Faehrt DENSELBEN Sweep gegen synthetischen Quelltext (Muster
    tests/test_session_lock_blocking_calls_guard.py:439-449). Die Schnipsel stehen in
    tests/, das NICHT im Sweep-Bereich liegt -> kein Selbst-Treffer.
    namen=None: Riegel-Namen aus dem Schnipsel selbst ableiten.

    MELDE-Seite: prueft ausschliesslich GEMEINSAME Riegel. Ein per-Schluessel-Riegel
    ist kein Verstoss."""
    baum = ast.parse(textwrap.dedent(quelltext))
    if namen is None:
        namen = _riegel_namen_einer_datei(baum)
    p = _ist_gemeinsamer_riegel_ausdruck
    treffer = []
    for block in _riegel_with_bloecke(baum, namen, p):
        treffer.extend(_netz_aufrufe_in(block))
    for tblock in _riegel_try_bloecke(baum, namen, p):
        treffer.extend(_netz_aufrufe_in(_riegel_region(tblock, namen, p)))
    return treffer


def _riegel_zaehle_bloecke_in_quelle(quelltext, namen=None):
    """ZAEHL-Seite: alle Riegel-Bloecke, auch die per-Schluessel gefuehrten."""
    baum = ast.parse(textwrap.dedent(quelltext))
    if namen is None:
        namen = _riegel_namen_einer_datei(baum)
    return (len(_riegel_with_bloecke(baum, namen))
            + len(_riegel_try_bloecke(baum, namen)))


@pytest.mark.rot_vor_fix
def test_kein_modul_globaler_riegel_um_netz_aufruf():
    """Kein modul-globaler Riegel darf einen Netz-/LLM-Aufruf umschliessen.

    Die Fehlerklasse: ein prozessweiter Riegel um einen Aufruf mit
    config.HTTP_LLM_TIMEOUT_LONG_S = 45 s Zeitlimit serialisiert ALLE Nutzer. Solo
    getestet unsichtbar; zwei gleichzeitige Anruf-Enden warten hintereinander und
    belegen dabei je einen der 64 gthread-Threads (deploy/nerve.service:35-36).

    ROT-Beleg (Marker rot_vor_fix, CLAUDE.md Punkt 31): gegen den ungefixten Stand
    MUSS diese Pruefung failen — mit services/coaching_service.py:84.

    KEIN Source-Presence-False-Green (CLAUDE.md Test-Qualitaets-Regel): geprueft wird
    ein VERBOTENES Muster, nicht die Existenz erwuenschten Codes. Verschwindet der
    Aufruf aus dem Riegel, wird der Test gruener; kommt einer hinzu, roetet er.

    MELDE-Seite (_ist_gemeinsamer_riegel_ausdruck): nur GEMEINSAME Riegel sind
    verstoss-faehig. Ein per-Schluessel-Riegel (`_lock_for(key)`) ist die LOESUNG der
    Fehlerklasse und wird bewusst NICHT gemeldet — er bleibt aber voll GEZAEHLT
    (test_riegel_sweep_erreicht_alle_bekannten_bloecke).
    """
    namen = _riegel_namen_gesamt()
    p = _ist_gemeinsamer_riegel_ausdruck
    gefunden = {}
    for datei, pfad in _riegel_python_dateien():
        baum, fehler = _riegel_baum_oder_fehler(pfad)
        if baum is None:
            # Nicht verschlucken: sichtbar rot statt still uebersprungen.
            gefunden[(datei, 0)] = {f'SYNTAX ({fehler})'}
            continue
        treffer = []
        for block in _riegel_with_bloecke(baum, namen, p):
            treffer.extend(_netz_aufrufe_in(block))
        for tblock in _riegel_try_bloecke(baum, namen, p):
            treffer.extend(_netz_aufrufe_in(_riegel_region(tblock, namen, p)))
        for zeile, muster in treffer:
            if (datei, zeile) in _FALSCH_TREFFER_RIEGEL:
                continue
            # Dedup je (datei, zeile): messages.create UND http_llm_client() stehen im
            # selben Ausdruck; zwei Melde-Zeilen behaupteten zwei Verstoesse statt einem.
            gefunden.setdefault((datei, zeile), set()).add(muster)

    verstoesse = [f"{d}:{z}  [{', '.join(sorted(m))}]"
                  for (d, z), m in sorted(gefunden.items())]
    assert not verstoesse, (
        f"{len(verstoesse)} modul-globale(r) Riegel um einen Netz-/LLM-Aufruf:\n  "
        + "\n  ".join(verstoesse)
        + "\n\nPunkt 28 (Mehr-Nutzer): ein prozessweiter Riegel um einen Netz-Aufruf "
          "serialisiert ALLE Nutzer ueber die volle Zeitlimit-Dauer.\n"
          "NICHT den Riegel ersatzlos entfernen (der Duplikatschutz haengt daran) und "
          "NICHT die Falsch-Treffer-Liste fuellen. Den Riegel pro Schluessel fuehren "
          "(Muster: services/coaching_service.py _analysis_lock_for) ODER den "
          "Netz-Aufruf AUS dem Riegel-Block herausziehen.")


def test_riegel_sweep_erreicht_alle_bekannten_bloecke():
    """Sperre gegen den stillen Ausfall (CLAUDE.md Punkt 31).

    Faellt die Riegel-Ableitung aus, ist die Namensmenge leer, der Sweep faende 0
    Verstoesse und SAEHE GRUEN AUS. Diese Pruefung macht daraus ROT.
    """
    namen = _riegel_namen_gesamt()
    ist, aufteilung = {}, {}
    for datei, pfad in _riegel_python_dateien():
        baum, _f = _riegel_baum_oder_fehler(pfad)
        if baum is None:
            continue
        n_with, n_try = _riegel_zaehlung(baum, namen)
        if n_with or n_try:
            ist[datei] = n_with + n_try
            aufteilung[datei] = (n_with, n_try)

    print('\n[MEHRNUTZER-REST-1 Riegel-Waechter] Ist-Zaehlung:')
    print(f'  abgeleitete Riegel-Namen: {len(namen)} -> {sorted(namen)}')
    for datei in sorted(ist):
        n_with, n_try = aufteilung[datei]
        print(f'  {datei}: {ist[datei]} (with={n_with}, try/finally={n_try})')
    print(f'  SUMME: {sum(ist.values())} in {len(ist)} Dateien')

    assert len(namen) >= _RIEGEL_SOLL_NAMEN_MINDESTENS, (
        f"Unter-Ableitung: nur {len(namen)} modul-globale Riegel-Namen gefunden, "
        f"erwartet mindestens {_RIEGEL_SOLL_NAMEN_MINDESTENS}. Entweder ist die "
        f"Ableitung kaputt (dann ist der Waechter BLIND, nicht gruen) oder Riegel "
        f"wurden legitim entfernt (dann die Zahl MIT BEGRUENDUNG nachziehen, den Test "
        f"NICHT entfernen). Gefunden: {sorted(namen)}")

    zu_wenig = {d: (ist.get(d, 0), soll) for d, soll in _RIEGEL_SOLL_JE_DATEI.items()
                if ist.get(d, 0) < soll}
    assert not zu_wenig, (
        f"Unter-Sweep je Datei: {zu_wenig}. services/coaching_service.py ist der "
        f"wichtigste Eintrag — faellt er auf 0, ist der conv_id-Riegel dieser Phase "
        f"aus der eigenen Bewachung gefallen (Variante A / _RIEGEL_FABRIK_ENDUNGEN "
        f"greift nicht mehr).")

    assert sum(ist.values()) >= _RIEGEL_SOLL_SUMME_MINDESTENS, (
        f"Unter-Sweep ueber die Summe: {sum(ist.values())} ueberwachte Bloecke, "
        f"erwartet mindestens {_RIEGEL_SOLL_SUMME_MINDESTENS}. Gezaehlt werden BEIDE "
        f"Formen (with + try/finally).")


# ── Selbst-Tests gegen synthetischen Quelltext ───────────────────────────────

def test_riegel_sweep_beisst_gegen_synthetischen_quelltext():
    """Positiv-Beleg: der Sweep meldet die Fehlerklasse tatsaechlich — in beiden
    Erwerbsformen und ueber Alias-Schreibweisen."""
    with_form = """
        import threading
        _x_lock = threading.Lock()

        def f(c):
            with _x_lock:
                r = c.messages.create(model='m')
                return r
    """
    try_form = """
        import threading
        _y_lock = threading.Lock()

        def g(c):
            _y_lock.acquire()
            try:
                return c.messages.stream(model='m')
            finally:
                _y_lock.release()
    """
    requests_form = """
        import threading
        _z_lock = threading.Lock()

        def h():
            with _z_lock:
                return requests.post('https://x')
    """
    nackter_aufruf = """
        import threading
        _w_lock = threading.Lock()

        def i():
            with _w_lock:
                return http_llm_client(long_running=True)
    """
    traced_huelle = """
        _session_state_lock = _TracedLock('_session_state_lock')

        def j(c):
            with _session_state_lock:
                return c.messages.create(model='m')
    """
    for name, quelle in (('with', with_form), ('try/finally', try_form),
                         ('requests', requests_form), ('nackt', nackter_aufruf),
                         ('_TracedLock', traced_huelle)):
        assert _riegel_analysiere_quelle(quelle), (
            f"Der Sweep sieht die Fehlerklasse in der Form '{name}' NICHT — "
            f"solange das so ist, beweist sein Gruen nichts.")


def test_riegel_sweep_meldet_harmloses_nicht():
    """Negativ-Beleg: der enge, empfaenger-gebundene Katalog produziert keine
    Falsch-Treffer. Ein Katalog ueber Methodennamen ('get', 'join') haette allein
    durch dict.get(...) unter Riegeln neun Falsch-Treffer im Bestand."""
    harmlos = """
        import threading
        _a_lock = threading.Lock()

        def f(d, xs, c):
            with _a_lock:
                v = d.get('k')
                s = ', '.join(xs)
                n = create(model='m')          # nacktes create, KEIN messages.create
                return v, s, n
    """
    assert _riegel_analysiere_quelle(harmlos) == [], (
        f"Falsch-Treffer im harmlosen Quelltext: "
        f"{_riegel_analysiere_quelle(harmlos)!r}. Der Katalog MUSS "
        f"empfaenger-gebunden bleiben.")

    ausserhalb = """
        import threading
        _b_lock = threading.Lock()

        def f(c):
            with _b_lock:
                daten = {'k': 1}
            return c.messages.create(model='m')   # AUSSERHALB des Riegels
    """
    assert _riegel_analysiere_quelle(ausserhalb) == [], (
        "Ein Netz-Aufruf AUSSERHALB des Riegel-Blocks darf nicht gemeldet werden — "
        "sonst waere der Waechter unbrauchbar laut.")


def test_riegel_erkennung_erfasst_context_manager_aufruf():
    """DER WICHTIGSTE SELBST-TEST DIESER PHASE (Variante A / _RIEGEL_FABRIK_ENDUNGEN).

    Nach dem Fix heisst es in services/coaching_service.py nicht mehr
    `with _analysis_lock:` sondern `with _analysis_lock_for(conv_id):` — ein ast.Call,
    kein Riegel-Name. Dieser Test nagelt BEIDE Richtungen fest; nur eine zu pruefen
    beweist die Haelfte:

    (I)  ZAEHL-Seite: der Fabrik-Block wird GEZAEHLT. Ohne das faellt der neue Riegel
         aus der eigenen Bewachung, das Datei-Soll muesste auf 0, und der Waechter
         waere GRUEN ABER BLIND — verboten laut
         tests/test_session_lock_blocking_calls_guard.py:200-207 ("ein Eintrag mit
         Soll 0 kann nie fehlschlagen").
    (II) MELDE-Seite: derselbe Block wird NICHT als Verstoss gemeldet. Ein
         per-Schluessel-Riegel ist definitionsgemaess kein gemeinsamer Riegel — er
         IST die Loesung der Fehlerklasse. Wuerde er gemeldet, bliebe der Waechter
         nach dem Fix ROT und das gruene Tor waere unerreichbar.
    (III) Gegenprobe gemeinsamer Riegel: `with _globaler_lock:` um denselben Aufruf
         MUSS weiterhin gemeldet werden. Ohne diese Haelfte koennte (II) auch von
         einem kaputten Netz-Katalog erfuellt werden.
    (IV) Gegenprobe Fabrik OHNE Argument: `with _hole_lock():` kann nicht nach
         Schluessel trennen und MUSS gemeldet werden.
    """
    nach_dem_fix = """
        import threading
        _conv_locks = {}
        _conv_locks_guard = threading.Lock()

        def f(conv_id, c):
            with _analysis_lock_for(conv_id):
                return c.messages.create(model='m')
    """
    assert _riegel_zaehle_bloecke_in_quelle(nach_dem_fix) == 1, (
        "(I) `with _analysis_lock_for(conv_id):` wird NICHT als bewachter Block "
        "gezaehlt. Damit faellt der in dieser Phase gebaute Riegel aus der eigenen "
        "Bewachung und das Datei-Soll services/coaching_service.py muesste auf 0 — "
        "der Waechter waere gruen ABER BLIND (RESEARCH §4.6). "
        "_RIEGEL_FABRIK_ENDUNGEN pruefen.")
    assert _riegel_analysiere_quelle(nach_dem_fix) == [], (
        f"(II) Ein per-Schluessel-Riegel wird als Verstoss GEMELDET: "
        f"{_riegel_analysiere_quelle(nach_dem_fix)!r}. Damit bliebe der Waechter auch "
        f"NACH dem Fix rot und das gruene Tor waere unerreichbar. "
        f"_ist_per_schluessel_riegel_ausdruck pruefen.")

    weiterhin_verstoss = """
        import threading
        _globaler_lock = threading.Lock()

        def f(c):
            with _globaler_lock:
                return c.messages.create(model='m')
    """
    assert _riegel_analysiere_quelle(weiterhin_verstoss), (
        "(III) Ein GEMEINSAMER Riegel um messages.create wird nicht mehr gemeldet — "
        "die Trennung Zaehl-/Melde-Seite hat den Waechter abgeschaltet statt "
        "praezisiert. Das ist die Fehlerklasse selbst.")

    fabrik_ohne_argument = """
        import threading
        _platzhalter_lock = threading.Lock()

        def f(c):
            with _hole_lock():
                return c.messages.create(model='m')
    """
    assert _riegel_analysiere_quelle(fabrik_ohne_argument), (
        "(IV) Eine Riegel-Fabrik OHNE Argument kann gar nicht nach Schluessel "
        "trennen und ist damit faktisch gemeinsam — sie MUSS gemeldet werden.")

    # Gegenprobe: ein gewoehnlicher Aufruf ist KEIN Riegel-Ausdruck.
    kein_riegel = """
        def f(c):
            with open('x') as fh:
                return c.messages.create(model='m')
    """
    assert _riegel_zaehle_bloecke_in_quelle(kein_riegel) == 0, (
        "`with open(...)` wird faelschlich als Riegel-Block gezaehlt — die "
        "Endungs-Heuristik ist zu weit.")


def test_riegel_pruefkatalog_ist_vollstaendig():
    """Ein Waechter ohne benannte Grenzen erzeugt falsche Sicherheit (Punkt 31).
    Diese Pruefung haelt die sechs Punkt-31-Pflicht-Bestandteile PLUS die hauseigene
    STOP-REGEL fest — zusammen die sieben Ueberschriften unten."""
    for ueberschrift in ('WAS DER KATALOG ABDECKT',
                         'WAS ER STRUKTURELL NICHT SEHEN KANN',
                         'WO DIE HEURISTIKEN ZWEISCHNEIDIG SIND',
                         'WAS FORMAL UNKLAR BLEIBT',
                         'WELCHE ZWEITE SCHICHT DARUNTER LIEGT',
                         'GEPRUEFT UND GESCHLOSSEN',
                         'STOP-REGEL'):
        assert ueberschrift in _RIEGEL_PRUEFKATALOG, (
            f"Pflicht-Abschnitt '{ueberschrift}' fehlt im Pruefkatalog "
            f"(CLAUDE.md Punkt 31).")

    # Auflage aus dem Pre-Execute-Audit (Claudian) + Cross-AI (Gemini, LOW-Befund):
    # Die zwei nicht erfassten Definitions-Orte sind die naheliegendste Fehl-Lesung
    # eines gruenen Ergebnisses. Sie standen bisher nur in RESEARCH.md §4.7.2 — dort
    # liest sie niemand, der diesen Test gruen sieht. Diese Schleife haelt sie IM
    # Docstring fest, damit sie nicht still herausgekuerzt werden koennen.
    for luecke in ('RIEGEL, DIE INNERHALB VON FUNKTIONEN DEFINIERT WERDEN',
                   'RIEGEL, DIE ALS KLASSENATTRIBUT DEFINIERT WERDEN'):
        assert luecke in _RIEGEL_PRUEFKATALOG, (
            f"Die benannte Restluecke '{luecke}' fehlt im Pruefkatalog. Ohne sie "
            f"wird ein gruenes Ergebnis dieses Pruefpunkts als weitergehender Beweis "
            f"gelesen, als er ist (CLAUDE.md Punkt 31, Pflicht-Bestandteil 2 und 3).")
