#!/usr/bin/env bash
# ── scripts/triage.sh — Server-Triage-Harness (bleibendes Werkzeug / Ratchet) ──────────────
#
# Zweck: Empirische Triage (Plan 04) + Determinismus-Identifikation (Plan 05) ohne Deploy.
#        Provisioniert nerve_test 1:1 wie der deploy.sh-Gate-Block (pg_dump-Restore +
#        alembic upgrade head + 4 DSNs + Whitelist-Guard + trap-DROP), laeuft dann NUR
#        die uebergebenen Tests (targeted pytest via Argument-Forwarding) und deployt NIE
#        (kein Service-Restart, kein Deploy-Meta-Write).
#
# Usage:
#   bash scripts/triage.sh <pytest-args>
#   z.B. bash scripts/triage.sh tests/test_eur_calculator.py -v --tb=long
#   z.B. bash scripts/triage.sh tests/test_schema_introspect.py -v
#   z.B. bash scripts/triage.sh tests/test_schild_guard.py::test_alle_tabellen_haben_schild -v
#
# Laeuftt NUR auf dem Server (178.104.82.166) als postgres-peer (sudo-faehig).
# Kein Local-Dev (CLAUDE.md HART). Prod-nerve wird NIE beruehrt — nur nerve_test (Wegwerf-DB).
#
# Bleibendes Werkzeug (Ratchet, Andre-Direktive 15.06.): nicht loeschen/umschreiben.
# Diagnose-Prints gehoeren in iterative Test-Instrumentierung (Plan 04), NICHT hier.
#
# Abhaengig von Plan 01 (Auto-Reset-Waechter) + Plan 02 (Marker-Registrierung) — der Harness
# laeuft die Suite, die Plan 01+02 bereits geaendert haben (sonst triagiert er gegen den alten Stand).
#
# ─────────────────────────────────────────────────────────────────────────────────────────────

set -euo pipefail

# ── (1) Whitelist-Guard (D-02, T-PGTEST-05, Req-5/10): TEST_DB ist EINZIGE Namensquelle.
#        != nerve_test -> Abbruch statt Raten (Prod-Schutz).
TEST_DB="nerve_test"
if [ "$TEST_DB" != "nerve_test" ]; then
  echo "[triage] FATAL: Test-DB-Name != nerve_test — Abbruch (Prod-Schutz D-02)"; exit 1
fi

# ── (2) trap cleanup EXIT (D-06, T-PGTEST-10, T-PGTEST-GREEN-11):
#        DROP nerve_test garantiert auch bei Test-Fehler/SIGTERM — rueckstandsfrei.
cleanup() { sudo -u postgres psql -c "DROP DATABASE IF EXISTS \"$TEST_DB\";" 2>/dev/null || true; }
trap cleanup EXIT

# ── (3) Pre-Run-DROP (D-06): verwaiste nerve_test (existiert evtl. von hartem Vorlauf-Abbruch) wegraeumen.
sudo -u postgres psql -c "DROP DATABASE IF EXISTS \"$TEST_DB\";" \
  || { echo "[triage] FEHLER: Pre-Run-DROP nerve_test fehlgeschlagen"; exit 1; }

# ── (4) CREATE OWNER postgres (T-PGTEST-09, T-PGTEST-GREEN-10): NICHT nerve_app —
#        sonst crm-Tabellen owner-bypass RLS (False-Green).
sudo -u postgres psql -c "CREATE DATABASE \"$TEST_DB\" OWNER postgres;" \
  || { echo "[triage] FEHLER: CREATE DATABASE nerve_test fehlgeschlagen"; exit 1; }

# ── (5) Schema-Dump vom Prod-nerve (read-only auf nerve), MIT owners+privileges
#        (NICHT --no-privileges/--no-owner — die GRANTs/Owner tragen die RLS-Treue).
#        set -o pipefail (T-PGTEST-08, T-PGTEST-GREEN-13): sonst maskiert psql-Exit-0 einen
#        pg_dump-Crash -> leere DB -> silent False-Green.
sudo -u postgres bash -c "set -o pipefail; pg_dump --schema-only nerve | psql -v ON_ERROR_STOP=1 -d $TEST_DB" \
  || { echo "[triage] FEHLER: pg_dump --schema-only nerve -> nerve_test fehlgeschlagen"; exit 1; }

# ── (6) Stamp-Row-Dump (alembic_version = prod-head) MIT pipefail,
#        damit upgrade head nur neue Revs anwendet (T-PGTEST-15) — keine 0002-Kollision.
sudo -u postgres bash -c "set -o pipefail; pg_dump --data-only --table=alembic_version nerve | psql -v ON_ERROR_STOP=1 -d $TEST_DB" \
  || { echo "[triage] FEHLER: alembic_version-Stamp-Dump -> nerve_test fehlgeschlagen"; exit 1; }

# ── (7) alembic upgrade head (NICHT hardcoden, D-09): wendet nur Revs ueber prod-head an.
sudo -u postgres bash -c "cd /opt/nerve/app && DATABASE_URL=postgresql://postgres@/$TEST_DB /opt/nerve/venv/bin/alembic upgrade head" \
  || { echo "[triage] FEHLER: alembic upgrade head gegen nerve_test fehlgeschlagen"; exit 1; }

# Test-only DELETE-Grant (GREEN Wave-4): spiegelt deploy.sh — der anonymizer-logic-Teardown raeumt
# SEINE EIGENEN training.transcript_archive-Test-Rows als nerve_anon_worker. Prod-DPO-Tresor UNVERAENDERT
# (nerve_anon_worker dort NUR INSERT+SELECT). HART: Ziel IMMER $TEST_DB (nerve_test) — NIEMALS @/nerve.
sudo -u postgres psql -d "$TEST_DB" -c "GRANT DELETE ON training.transcript_archive TO nerve_anon_worker" \
  || { echo "[triage] FEHLER: Test-only training-DELETE-Grant gegen nerve_test fehlgeschlagen"; exit 1; }

# ── (8) DUMP-TREUE-KATALOG-GATE (1:1 aus deploy.sh, Gemini-HIGH, T-PGTEST-09):
#        fail-closed Counts — wenn der Dump RLS/FORCE/GRANTs NICHT treu trug, bricht hier ab.
POLICIES=$(sudo -u postgres psql -tAc "SELECT count(*) FROM pg_policies WHERE schemaname='crm';" -d "$TEST_DB")
[ "$POLICIES" -ge 7 ] \
  || { echo "[triage] FEHLER: crm-RLS-Policies < 7 (Dump trug RLS nicht treu -> False-Green-Schutz)"; exit 1; }
FORCED=$(sudo -u postgres psql -tAc "SELECT count(*) FROM pg_class WHERE relnamespace=(SELECT oid FROM pg_namespace WHERE nspname='crm') AND relkind='r' AND relforcerowsecurity;" -d "$TEST_DB")
[ "$FORCED" -ge 5 ] \
  || { echo "[triage] FEHLER: crm FORCE ROW LEVEL SECURITY nicht auf allen 5 Tabellen"; exit 1; }
GRANTS=$(sudo -u postgres psql -tAc "SELECT count(*) FROM information_schema.role_table_grants WHERE table_schema='crm' AND grantee='nerve_anon_worker' AND privilege_type='SELECT';" -d "$TEST_DB")
[ "$GRANTS" -ge 5 ] \
  || { echo "[triage] FEHLER: nerve_anon_worker SELECT-GRANTs auf crm.* fehlen (Dump-Treue)"; exit 1; }
echo "[triage] Dump-Treue-Katalog-Gate OK: crm-Policies=$POLICIES, FORCE=$FORCED, anon-SELECT-GRANTs=$GRANTS"

# ── (9) Targeted pytest gegen nerve_test — ANON_PW via Env an sudo, single-quoted inner bash -c
#        (T-PGTEST-06: PW nie als String-Literal interpoliert), 4 DSNs + DATABASE_URL alle @/${TEST_DB}.
#
#        ARGUMENT-FORWARDING (Gemini-Re-Review R2 / Fund #5, T-PGTEST-GREEN-12, BLOCKER):
#        Das innere `pytest "$@"` steht INNERHALB des single-quoted bash -c Blocks.
#        $@ wird dort von der AEUSSEREN Shell NICHT expandiert (single-quote).
#        FIX: ' _ "$@"' nach dem schliessenden single-quote reicht die Argumente HART
#        in die innere bash durch: _ belegt $0, danach folgen $1,$2,... der aeusseren Shell.
#        OHNE dieses Forwarding wuerde jeder Triage-Lauf die GANZE Suite laufen (Fund #5).
#
#        KEIN POST-SUITE-Check, KEIN Deploy-Meta-Write, KEIN Service-Restart (D-G08, Req-5/10).
ANON_PW=$(sudo grep ^NERVE_ANON_WORKER_DB_PASSWORD= /etc/nerve/ionos-s3.env | cut -d= -f2-)
echo "[triage] pytest (targeted) gegen DATABASE_URL=postgresql://nerve_app@/$TEST_DB (+ 4 Test-DSNs)"
echo "[triage] Argumente: $*"
sudo -u nerve_app env ANON_PW="$ANON_PW" TEST_DB="$TEST_DB" bash -c '
  cd /opt/nerve/app && \
  DATABASE_URL="postgresql://nerve_app@/${TEST_DB}" \
  TEST_DATABASE_URL="postgresql://nerve_app@/${TEST_DB}" \
  NERVE_APP_TEST_DSN="postgresql://nerve_app@/${TEST_DB}" \
  NERVE_SCHILD_TEST_DSN="postgresql://nerve_app@/${TEST_DB}" \
  ANON_WORKER_TEST_DSN="postgresql://nerve_anon_worker:${ANON_PW}@127.0.0.1:5432/${TEST_DB}" \
  /opt/nerve/venv/bin/pytest "$@"
' _ "$@" \
  || { echo "[triage] FEHLER: pytest gegen nerve_test ROT (kein Restart, kein Deploy)"; exit 1; }
echo "[triage] pytest gegen nerve_test bestanden — nerve_test wird per trap gedroppt"

# D-G08: kein Service-Neustart, kein Deploy-Meta-Schreiben — nur Triage (Req-5/10).
# POST-SUITE-Baseline-Check gehoert in deploy.sh, nicht hierher.
# trap cleanup EXIT droppt nerve_test rueckstandsfrei (auch bei Fehler oben).
