#!/bin/bash
# ── NERVE Deploy-Hygiene: Waisen-Prune ──────────────────────────────────────
# Phase 08.23.2.DEPLOY-PRUNE. Raeumt im Repo geloeschte CODE-Dateien server-seitig
# ab (tar-over-ssh MERGT nur -> deploy.sh:78-79 laesst server-only Dateien liegen).
#
# Mechanik = Manifest-Diff (Weg 1, Andre-Entscheidung): git-Manifest (was getrackt
# SEIN soll) vs. find im App-Verzeichnis -> Waisen = find MINUS Manifest MINUS Exclude.
#
# FUENF Sicherheits-Schichten:
#   D-01 Scope-Whitelist (nur Code-Dirs) -> logs/+database/ strukturell AUSSERHALB.
#   D-02 Cap PRUNE_MAX (default 30) + leeres-Manifest-Abbruch -> keine Massen-Loeschung.
#   D-03 Dry-Run default; scharf nur bei PRUNE_APPLY=1 (woertlich "1").
#   D-04 Quarantaene statt rm (mv -> /opt/nerve/trash/<ts>/, Retention) -> reversibel.
#   D-05 logs/database-Hard-Abort (belt-and-suspenders, auch wenn strukturell unerreichbar).
#
# FUNKTIONS-STRUKTUR (Fable MUST-3): die Guards sind aufrufbare Funktionen + ein
# BASH_SOURCE-Main-Guard, damit der Test das Skript SOURCEN und prune_guard_customer_data
# direkt mit synthetischer Kandidatenliste treffen kann (der Hard-Abort ist aus dem
# Whitelist-Scan nicht erreichbar). Die Whitelist ist NICHT env-ueberschreibbar
# (kein Prod-Scope-Override); nur Output-Pfade (Report/Trash) sind fuer Tests uebersteuerbar.
set -euo pipefail

# ── Prod-Scope: NICHT env-ueberschreibbar (Fable MUST-3) ────────────────────
PRUNE_DIRS=(templates static routes services scripts tests alembic config tools nerve_rt docs)
PRUNE_TOP_FILES=(app.py config.py extensions.py)

# ── Env-Parameter ───────────────────────────────────────────────────────────
APP_DIR="${APP_DIR:-/opt/nerve/app}"
MANIFEST="${MANIFEST:-/root/nerve_prune_manifest}"
PRUNE_MAX="${PRUNE_MAX:-30}"
PRUNE_APPLY="${PRUNE_APPLY:-0}"
REPORT_RETENTION="${REPORT_RETENTION:-10}"
TRASH_RETENTION="${TRASH_RETENTION:-2}"
# Output-Pfade fuer Tests uebersteuerbar (KEIN Scope, harmlos):
REPORT_DIR="${PRUNE_REPORT_DIR:-/opt/nerve}"
TRASH_BASE="${PRUNE_TRASH_BASE:-/opt/nerve/trash}"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
TRASH_DIR="$TRASH_BASE/$TS"
REPORT_FILE="$REPORT_DIR/prune_report_$TS.txt"

log() { echo "$@" >&2; }

# ── Exclude-Filter — laeuft VOR dem Cap-Count (Fable SHOULD-b/MUST-1a) ───────
# Server traegt >60 __pycache__ + 16 tests/tts_samples/*.mp3 (untracked, .gitignore);
# ungefiltert wuerden sie den Cap sofort sprengen (Sisyphus). case = set-e-safe.
_is_excluded() {
  local rel="$1"
  case "$rel" in
    */__pycache__/*|__pycache__/*) return 0 ;;
    *.pyc)                         return 0 ;;
    *.db*)                         return 0 ;;
    tests/tts_samples/*)           return 0 ;;
  esac
  return 1
}

# ── Manifest laden (NUL-delimitiert) — Guard a: leer/fehlt -> Abbruch ────────
declare -A MANIFEST_SET=()
prune_load_manifest() {
  if [ ! -s "$MANIFEST" ]; then
    log "[PRUNE][ABORT] Manifest fehlt oder leer ($MANIFEST) — NICHTS bewegt (Guard a, D-02)"
    return 1
  fi
  local rel
  while IFS= read -r -d '' rel; do
    [ -n "$rel" ] && MANIFEST_SET["$rel"]=1
  done < "$MANIFEST"
  if [ "${#MANIFEST_SET[@]}" -eq 0 ]; then
    log "[PRUNE][ABORT] Manifest enthaelt 0 Eintraege — NICHTS bewegt (Guard a, D-02)"
    return 1
  fi
  return 0
}

# ── Kandidaten sammeln: find MINUS Manifest MINUS Exclude (NUL-safe) ─────────
CANDIDATES=()
prune_compute_candidates() {
  CANDIDATES=()
  local base rel f
  for base in "${PRUNE_DIRS[@]}"; do
    [ -d "$APP_DIR/$base" ] || continue
    while IFS= read -r -d '' f; do
      rel="${f#"$APP_DIR"/}"
      _is_excluded "$rel" && continue                 # Exclude VOR Cap
      [ -n "${MANIFEST_SET[$rel]:-}" ] && continue     # im Manifest -> behalten
      CANDIDATES+=("$rel")
    done < <(find "$APP_DIR/$base" -type f -print0)
  done
  for f in "${PRUNE_TOP_FILES[@]}"; do
    [ -f "$APP_DIR/$f" ] || continue
    _is_excluded "$f" && continue
    [ -n "${MANIFEST_SET[$f]:-}" ] && continue
    CANDIDATES+=("$f")
  done
}

# ── Guard b (D-05): HARTER Abbruch bei logs/ oder database/ Kandidat ─────────
# Sourc-bar + direkt mit Kandidatenliste aufrufbar (Fable MUST-3).
prune_guard_customer_data() {
  local c
  for c in "$@"; do
    case "$c" in
      logs/*|database/*)
        log "[PRUNE][ABORT] Kundendaten-Pfad als Kandidat ('$c') — HARTER Abbruch, NICHTS bewegt (D-05, Guard b)"
        return 1 ;;
    esac
  done
  return 0
}

# ── Guard c (D-02): Cap ─────────────────────────────────────────────────────
prune_guard_cap() {
  local count="$1"
  if [ "$count" -gt "$PRUNE_MAX" ]; then
    log "[PRUNE][ABORT] Kandidatenzahl $count > Cap $PRUNE_MAX — NICHTS bewegt (Guard c, D-02). PRUNE_MAX zum Uebersteuern."
    return 1
  fi
  return 0
}

# ── Retention-Helfer (set-e-safe) ───────────────────────────────────────────
_prune_retention_reports() {
  local keep="$1" files i
  mapfile -t files < <(ls -1t "$REPORT_DIR"/prune_report_*.txt 2>/dev/null || true)
  for ((i=keep; i<${#files[@]}; i++)); do rm -f "${files[$i]}" || true; done
}
_prune_retention_trash() {
  local keep="$1" dirs i
  mapfile -t dirs < <(ls -1dt "$TRASH_BASE"/*/ 2>/dev/null || true)
  for ((i=keep; i<${#dirs[@]}; i++)); do rm -rf "${dirs[$i]}" || true; done
}

# ── Dry-Run-Report (default) — bewegt NICHTS ────────────────────────────────
prune_write_report() {
  mkdir -p "$REPORT_DIR"
  local c
  {
    echo "# Prune Dry-Run Report $TS"
    echo "# APP_DIR=$APP_DIR  Kandidaten=${#CANDIDATES[@]}  Cap=$PRUNE_MAX"
    for c in "${CANDIDATES[@]}"; do echo "$c"; done
  } > "$REPORT_FILE"
  log "[PRUNE][DRY-RUN] ${#CANDIDATES[@]} Kandidat(en) -> Report $REPORT_FILE (NICHTS bewegt)"
  for c in "${CANDIDATES[@]}"; do log "  [DRY-RUN] $c"; done
  _prune_retention_reports "$REPORT_RETENTION"
}

# ── Apply (PRUNE_APPLY=1) — Quarantaene statt rm (D-04) ──────────────────────
prune_apply() {
  mkdir -p "$TRASH_DIR"
  local c dest
  for c in "${CANDIDATES[@]}"; do
    dest="$TRASH_DIR/$c"
    mkdir -p "$(dirname "$dest")"
    mv "$APP_DIR/$c" "$dest"
    log "  [APPLIED] $c -> $dest"
  done
  log "[PRUNE][APPLIED] ${#CANDIDATES[@]} Kandidat(en) nach $TRASH_DIR verschoben (mv, reversibel)"
  _prune_retention_trash "$TRASH_RETENTION"
}

# ── Ablauf ──────────────────────────────────────────────────────────────────
prune_main() {
  log "[PRUNE] Start $TS  APP_DIR=$APP_DIR  MANIFEST=$MANIFEST  APPLY=$PRUNE_APPLY  CAP=$PRUNE_MAX"
  prune_load_manifest || exit 1                          # Guard a
  prune_compute_candidates
  local n="${#CANDIDATES[@]}"
  if [ "$n" -gt 0 ]; then
    prune_guard_customer_data "${CANDIDATES[@]}" || exit 1   # Guard b (D-05)
  fi
  prune_guard_cap "$n" || exit 1                         # Guard c (D-02)
  if [ "$n" -eq 0 ]; then
    log "[PRUNE] 0 Kandidaten — nichts zu tun (Server == Repo fuer Code)."
    return 0
  fi
  if [ "$PRUNE_APPLY" = "1" ]; then
    prune_apply
  else
    prune_write_report
  fi
}

# ── Main-Guard (Fable MUST-3): gesourct laeuft NICHTS (Test sourct nur) ──────
if [ "${BASH_SOURCE[0]:-$0}" = "$0" ]; then
  prune_main
fi
