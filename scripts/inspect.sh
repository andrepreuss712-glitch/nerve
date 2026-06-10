#!/bin/bash
# scripts/inspect.sh — Read-only Staging/Production-Inspection-Wrapper.
#
# Verankert 2026-05-27 als Folge HART-Regel "Kein Local-Dev mehr"
# (CLAUDE.md). Pflicht-Werkzeug für GSD-Plan-Author + Research-Phase +
# Pre-Execute-Audit — alle DB-/Schema-/Daten-/Routes-/Logs-Inspections
# laufen über dieses Wrapper-Skript, NICHT mehr lokal.
#
# Alle Befehle sind READ-ONLY. Tabellen-Namen werden gegen Whitelist
# geprüft (SQL-Injection-Safety). env-keys gibt NUR Variablen-Namen,
# niemals Werte (Secret-Safety).
#
# Usage:
#     bash scripts/inspect.sh <command> [args]
#
# Remote via SSH (GSD-Plan-Author-Pattern):
#     ssh -i ~/.ssh/id_ed25519_nerve root@staging.getnerve.app \
#         'cd /opt/nerve/app && bash scripts/inspect.sh schema calls'

set -euo pipefail

# ─── Konfiguration ──────────────────────────────────────────────────────────

ENV_FILE="${ENV_FILE:-/etc/nerve/.env}"
DB_NAME="${DB_NAME:-nerve}"
DB_USER="${DB_USER:-nerve_app}"
APP_DIR="${APP_DIR:-/opt/nerve/app}"

# DB-Werte aus .env überschreiben wenn vorhanden
if [ -f "$ENV_FILE" ]; then
    _env_db_name=$(grep -E "^DB_NAME=" "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2 | tr -d '"' | tr -d "'" || true)
    _env_db_user=$(grep -E "^DB_USER=" "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2 | tr -d '"' | tr -d "'" || true)
    [ -n "${_env_db_name:-}" ] && DB_NAME="$_env_db_name"
    [ -n "${_env_db_user:-}" ] && DB_USER="$_env_db_user"
fi

# Service-Name: staging vs. production
SERVICE_NAME="nerve"
if [ -f /etc/systemd/system/nerve-staging.service ]; then
    SERVICE_NAME="nerve-staging"
fi

# ─── Safety-Helpers ─────────────────────────────────────────────────────────

_validate_table() {
    if ! [[ "$1" =~ ^[a-z_][a-z0-9_]*$ ]]; then
        echo "FEHLER: Tabellen-Name muss [a-z_][a-z0-9_]* matchen (Read-only Safety)." >&2
        exit 2
    fi
}

_validate_integer() {
    if ! [[ "$1" =~ ^[0-9]+$ ]]; then
        echo "FEHLER: '$1' muss Integer sein." >&2
        exit 2
    fi
}

_run_psql() {
    # Phase 08.23.2.D Hotfix 2026-05-27 — psql via sudo -u nerve_app weil Postgres
    # peer-auth den System-User mit dem DB-User matchen muss. Wenn das Skript als
    # root via SSH läuft, scheitert direktes psql -U nerve_app mit "Peer authentication
    # failed". sudo -u $DB_USER wechselt den System-User vor psql-Aufruf.
    # Fallback: wenn sudo nicht vorhanden, direkter Aufruf (z.B. Tests in CI).
    if command -v sudo >/dev/null 2>&1 && [ "$(whoami)" != "$DB_USER" ]; then
        sudo -u "$DB_USER" psql -d "$DB_NAME" "$@" 2>&1 || {
            echo "FEHLER: psql-Aufruf via sudo -u $DB_USER gescheitert. DB-Name=$DB_NAME" >&2
            return 1
        }
    else
        psql -U "$DB_USER" -d "$DB_NAME" -h /var/run/postgresql "$@" 2>&1 || {
            echo "FEHLER: psql-Aufruf gescheitert. DB-User=$DB_USER DB-Name=$DB_NAME" >&2
            echo "Hinweis: Wenn peer-auth via Unix-Socket nicht passt, prüfe sudo -u postgres oder DB-User-Setup." >&2
            return 1
        }
    fi
}

# ─── Commands ───────────────────────────────────────────────────────────────

CMD="${1:-help}"

case "$CMD" in
    # ── DB-Inspection ──────────────────────────────────────────────────────
    schema)
        _validate_table "${2:?schema needs table name}"
        _run_psql -c "\d $2"
        ;;
    sample)
        _validate_table "${2:?sample needs table name}"
        LIMIT="${3:-10}"
        _validate_integer "$LIMIT"
        _run_psql -c "SELECT * FROM $2 LIMIT $LIMIT;"
        ;;
    count)
        _validate_table "${2:?count needs table name}"
        _run_psql -c "SELECT COUNT(*) FROM $2;"
        ;;
    tables)
        _run_psql -c "\dt"
        ;;
    migrations)
        _run_psql -c "SELECT version_num FROM alembic_version;"
        ;;
    columns)
        _validate_table "${2:?columns needs table name}"
        _run_psql -c "SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_name = '$2' ORDER BY ordinal_position;"
        ;;
    constraints)
        _validate_table "${2:?constraints needs table name}"
        _run_psql -c "SELECT con.conname, pg_get_constraintdef(con.oid) FROM pg_constraint con JOIN pg_class rel ON rel.oid = con.conrelid WHERE rel.relname = '$2';"
        ;;

    # ── App-Inspection ─────────────────────────────────────────────────────
    alembic-current)
        cd "$APP_DIR" && source venv/bin/activate 2>/dev/null && alembic current
        ;;
    routes)
        cd "$APP_DIR" && source venv/bin/activate 2>/dev/null && python -c "
from app import app
for rule in sorted(app.url_map.iter_rules(), key=lambda r: r.rule):
    methods = ','.join(sorted((rule.methods or set()) - {'HEAD', 'OPTIONS'}))
    print(f'{methods:20s} {rule.rule:50s} -> {rule.endpoint}')
"
        ;;
    logs)
        N="${2:-200}"
        _validate_integer "$N"
        journalctl -u "$SERVICE_NAME" -n "$N" --no-pager
        ;;
    logs-errors)
        N="${2:-500}"
        _validate_integer "$N"
        journalctl -u "$SERVICE_NAME" -n "$N" --no-pager | grep -iE "error|fehler|exception|traceback|critical" | tail -50
        ;;
    health)
        curl -s http://localhost/api/health | python3 -m json.tool 2>/dev/null || curl -s http://localhost/api/health || echo "Health-Endpoint nicht erreichbar"
        ;;
    git-stand)
        cd "$APP_DIR" && git log --oneline -3 2>/dev/null && echo "---" && git status --porcelain 2>/dev/null
        ;;
    service-status)
        systemctl status "$SERVICE_NAME" --no-pager -n 5
        ;;

    # ── Code-Inspection ────────────────────────────────────────────────────
    grep)
        PATTERN="${2:?grep needs pattern}"
        cd "$APP_DIR" && grep -rn "$PATTERN" . --include='*.py' --include='*.html' --include='*.css' --include='*.js' 2>/dev/null | head -100
        ;;

    # ── Config-Inspection (Secret-Safe) ────────────────────────────────────
    env-keys)
        # Listet NUR die Variable-NAMEN aus .env, NIEMALS die Werte.
        # Wer die Werte braucht, muss SSH-Shell auf Server haben (manuelle Aktion).
        if [ -f "$ENV_FILE" ]; then
            grep -E "^[A-Z_][A-Z0-9_]*=" "$ENV_FILE" | cut -d= -f1 | sort -u
        else
            echo "FEHLER: $ENV_FILE nicht gefunden." >&2
            exit 1
        fi
        ;;

    # ── Schild-Inspection (Phase 08.23.2.SCHILD) ───────────────────────────
    schilder)
        _validate_table "${2:?schilder needs table name}"
        tbl="$2"
        echo "── Schild: $tbl (Tabelle) ─────────────────────────────────"
        # nerve_app liest pg_description aller 3 Schemas (Plan 01 GUARD_ROLE=nerve_app, bewiesen).
        _run_psql -c "SET search_path TO public, crm, training;
          SELECT n.nspname AS schema, obj_description(c.oid,'pg_class') AS schild
          FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
          WHERE c.relname='$tbl' AND n.nspname IN ('public','crm','training') AND c.relkind='r';"
        echo "── Spalten-Schilder ───────────────────────────────────────"
        _run_psql -c "
          SELECT a.attname AS spalte, col_description(a.attrelid,a.attnum) AS schild
          FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid
          JOIN pg_namespace n ON n.oid=c.relnamespace
          WHERE c.relname='$tbl' AND n.nspname IN ('public','crm','training')
          AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum;"
        echo "── Migrations-Historie (best-effort: Struktur-Ops/COMMENTs die diese Tabelle berühren) ──"
        # Cross-AI-Finding 2 (LOW): präziser als nacktes grep -l "$tbl" (Substring-/Kommentar-False-
        # Positives). Nur echte Alembic-Strukturoperationen, literale COMMENT-Statements ODER die
        # schema-qualifizierte Tupel-Form der 0015-COMMENT-Migration ('schema', 'tabelle',). $tbl ist
        # via _validate_table Whitelist-validiert ([a-z_][a-z0-9_]*) → injection-safe in der Regex.
        { grep -lE "op\.(create_table|alter_table|drop_table|add_column|drop_column)\(['\"]${tbl}['\"]|COMMENT ON (TABLE|COLUMN) [a-z_]*\.?${tbl}([^a-z0-9_]|\$)|\('(public|crm|training)', '${tbl}'," "$APP_DIR"/alembic/versions/*.py 2>/dev/null || true; } | while read -r f; do
            echo "  $(basename "$f"):"
            (cd "$APP_DIR" && git log --oneline -- "$f" 2>/dev/null | head -3) | sed 's/^/      /'
        done
        echo "(best-effort — dynamisch generierte DDL wird nicht erschöpfend erfasst.)"
        ;;

    # ── Help ───────────────────────────────────────────────────────────────
    help|--help|-h|"")
        cat << 'HELP'
inspect.sh — Read-only Staging/Production-Inspection-Wrapper
            HART-Regel "Kein Local-Dev mehr" — Pflicht-Werkzeug ab 2026-05-27.

DB-Inspection (Postgres):
    schema <table>              Schema-Detail (psql \d <table>)
    columns <table>             Spalten + Typen + Nullable
    constraints <table>         CHECK/FK/UNIQUE/PK-Constraints
    sample <table> [limit]      Sample-Rows (default 10)
    count <table>               Row-Count
    tables                      Alle Tabellen
    migrations                  alembic_version-Tabelle
    schilder <table>            Tabellen-Schild + Spalten-Schilder (pg_description,
                                public/crm/training) + best-effort Migrations-Historie

App-Inspection:
    alembic-current             Aktueller Migration-Stand
    routes                      Alle registrierten Flask-Routes
    logs [N]                    Letzte N journalctl-Zeilen (default 200)
    logs-errors [N]             Nur ERROR/Exception-Zeilen aus letzten N
    health                      /api/health JSON-Output
    git-stand                   git HEAD-Commit + Working-Tree-Status
    service-status              systemctl status

Code-Inspection (auf deployed Code-Stand):
    grep <pattern>              grep py/html/css/js in $APP_DIR (max 100)

Config-Inspection (Secret-Safe):
    env-keys                    NUR Variable-Namen aus /etc/nerve/.env
                                (NIEMALS Werte — Secret-Safety)

Hinweise:
    - Alle Befehle READ-ONLY
    - Tabellen-Namen müssen [a-z_][a-z0-9_]* matchen
    - LIMIT/N müssen Integer sein
    - Service: nerve-staging auf Staging, nerve auf Production
    - DB-Verbindung via Unix-Socket (peer auth, kein Passwort)

SSH-Wrapper für GSD-Plan-Author/Research-Phase:
    ssh -i ~/.ssh/id_ed25519_nerve root@staging.getnerve.app \
        'cd /opt/nerve/app && bash scripts/inspect.sh schema calls'

    ssh -i ~/.ssh/id_ed25519_nerve root@staging.getnerve.app \
        'cd /opt/nerve/app && bash scripts/inspect.sh sample calls 50'
HELP
        ;;
    *)
        echo "FEHLER: Unbekannter Befehl '$CMD'. Nutze 'help' für Übersicht." >&2
        exit 2
        ;;
esac
