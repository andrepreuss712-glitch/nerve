"""scripts/_crm_leak_count.py — dynamischer crm-Leak-Count fuer den deploy.sh POST-SUITE-Check (D-G16/D-G17/D-G18, Req-9 crm-Haelfte).

Wrapper, der tests/_schema_introspect.derive_baseline_tables mit schemas=('crm',) aufruft,
table_list aus dem Tupel entpackt und iterativ per crm-Tabelle einen SELECT count(*) summiert.
Eine einzige Gesamt-Zahl wird auf stdout ausgegeben (print(total)).

Aufruf (postgres peer in deploy.sh):
    sudo -u postgres bash -c "cd /opt/nerve/app && \
        DATABASE_URL=postgresql://postgres@/$TEST_DB \
        /opt/nerve/venv/bin/python scripts/_crm_leak_count.py"

ASCII-Identifier (CLAUDE.md). Verify = deploy.sh production (HART: kein Local-Dev).
"""
import os
import sys

# sys.path-Einfuegen wie conftest.py:9-13, damit tests._schema_introspect aufgeloest wird.
# Das Script liegt in scripts/ — der App-Root ist eine Ebene hoeher.
_APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _APP_ROOT not in sys.path:
    sys.path.insert(0, _APP_ROOT)

from tests._schema_introspect import derive_baseline_tables  # noqa: E402


def main():
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        # Fallback: postgres peer auf der aktuell gemounteten DB (nerve_test via deploy.sh)
        dsn = "postgresql://postgres@/nerve_test"

    # (a) Tupel von derive_baseline_tables entpacken — NUR table_list wird hier gebraucht
    #     (reverse_fk_delete_order + foundation_register sind fuer den Leak-Count irrelevant,
    #      Gemini-Fund #4: crm-Liste dynamisch via pg_tables -> table_list -> iterativer count).
    table_list, _reverse_fk_delete_order, _foundation_register = derive_baseline_tables(
        dsn,
        schemas=('crm',),
    )

    # (b) ITERATIV pro Tabelle ein SELECT count(*) ausfuehren und summieren.
    #     Identifier ausschliesslich aus der katalog-abgeleiteten table_list (pg_tables
    #     schemaname='crm') — NIE aus interpoliertem User-Input. Req-9: eine neu angelegte
    #     crm-Tabelle wird automatisch mit-bewacht, ohne deploy.sh-Hand-Edit.
    import psycopg2  # noqa: PLC0415 — importiert nach path-setup

    conn = psycopg2.connect(dsn)
    conn.autocommit = True
    try:
        total = 0
        cur = conn.cursor()
        for qualified_table in table_list:
            # table_list enthaelt schema-qualifizierte Eintraege ('crm.accounts' etc.)
            # Nur crm.*-Tabellen zaehlen (derive_baseline_tables wurde mit schemas=('crm',) aufgerufen)
            cur.execute(f"SELECT count(*) FROM {qualified_table}")  # noqa: S608
            row = cur.fetchone()
            total += row[0] if row else 0
        cur.close()
    finally:
        conn.close()

    # (c) Eine einzige Gesamt-Zahl auf stdout ausgeben (deploy.sh liest via $(...))
    print(total)


if __name__ == "__main__":
    main()
