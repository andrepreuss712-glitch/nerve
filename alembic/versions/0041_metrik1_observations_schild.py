"""rubric_score.observations_jsonb: Schild nachziehen (METRIK-1 Plan 05/07, Punkt 23)

Revision ID: 0041
Revises: 0040
Create Date: 2026-08-15

Phase 08.23.2.METRIK-1. REINE COMMENT-ON-MIGRATION: sie legt KEINE Spalte an, loescht keine
und aendert keinen Typ. Sie zieht das Schild von rubric_score.observations_jsonb auf den
Zustand nach dieser Phase nach — Aktualitaets-Pflicht (CLAUDE.md Punkt 23): ein Schild wird
in DERSELBEN Aenderung nachgezogen, die seine Bedeutung aendert. Weil die Plaene 05, 06 und 07
GEMEINSAM ausgerollt werden, ist dieses Ausrollen die "dieselbe Aenderung" — die Schild-Schuld
aus Plan 05 wird hier eingeloest und war dort ausdruecklich benannt, nicht uebersehen.

WAS SICH AN DER BEDEUTUNG AENDERT:
  observations_jsonb - das alte Schild beschrieb ausschliesslich die Dimensions-Form
                 dim_key auf Liste von Beobachtungen und nannte genau EINEN Schreiber
                 (services/judge_runner.py). Beides stimmt seit Plan 05 nicht mehr.
                 1. ZWEITER SCHREIBER: services/slow_lane.py schreibt seither in dieselbe
                    Spalte (Zitat-Pruefung, Kopfzeilen-Pruefung, Fokus-Berechnung). Ein Schild,
                    das einen aktiven Schreiber verschweigt, ist schlimmer als kein Schild —
                    es taeuscht eine falsche Wahrheit vor (Andre 2026-06-25).
                 2. DREI UNTERSTRICH-SCHLUESSEL neben den Dimensionen: _compliance (bestand
                    schon, war aber nie im Schild), _kopfzeile und _fokus (beide neu aus
                    Plan 05). Wer sie fuer Dimensionen haelt, zaehlt sie in jede Auswertung
                    mit hinein.
                 3. focus_key NULL hat eine BEDEUTUNG (ehrlich kein Kriterium verletzt) und
                    ist kein fehlender Wert — auf deutschem Bestand ist es der Normalfall,
                    weil der Fokus-Katalog englisch ist.

WARUM ALEMBIC UND NICHT _migrate(): app._migrate() returnt auf Postgres frueh (app.py) —
das Muster ist auf dem Live-Server wirkungslos und ausserdem das Alt-Muster (Punkt 29).

Prod-Kopf bei Planung (inspect.sh migrations, 2026-08-14): version_num = 0040.
Vom Executor am 2026-08-15 read-only gegen Production erneut gezogen: version_num = 0040.

REIHENFOLGE BEIM AUSROLLEN: Diese Migration legt keine Spalte an und aendert keinen Typ, sie
setzt nur COMMENT ON. Sie ist damit in BEIDE Richtungen unkritisch. Festgelegt ist trotzdem
eine Reihenfolge: Migration ZUERST, dann deploy.sh production — damit der Schild-Waechter im
Test-Tor gegen den bereits gesetzten Kommentar laeuft.
⚠ Die ZEITSTEMPEL-1-Regel "Migration vor Deploy" gilt nur fuer NEUE NULLABLE SPALTEN und wird
hier ausdruecklich NICHT blind uebertragen — hier gibt es keine neue Spalte.

Die Texte unten spiegeln database/models.py (comment=) ZEICHENGLEICH (Punkt 23).
"""
from alembic import op
import sqlalchemy as sa

revision = '0041'
down_revision = '0040'
branch_labels = None
depends_on = None

_SCHILD_RUBRIC_OBSERVATIONS = 'Beobachtungen und WOERTLICHE Beleg-Zitate je fester Dimension (LLM-Verhaltens-Bewerter, Beobachtung statt Note). Form dim_key auf Liste von beobachtung und beleg_zitat. SICHTBAR fuer den Nutzer (als KI-Einschaetzung gelabelt). Drei reservierte Unterstrich-Schluessel stehen daneben und sind KEINE Dimensionen. _compliance traegt das Sicherheits-Hard-Gate mit verletzt und beleg_zitat. _kopfzeile traegt ab METRIK-1 den besten Moment mit beobachtung und beleg_zitat, geliefert vom Modell im SELBEN Aufruf (kein zweiter LLM-Aufruf). _fokus traegt die eine Sache fuers naechste Mal mit focus_key, count, satz und beleg; sie wird vom CODE berechnet (services/fokus_katalog.py), nie vom Modell, und focus_key NULL bedeutet ehrlich kein Kriterium verletzt - auf deutschem Bestand ist das der Normalfall, weil der Katalog englisch ist. JEDES Beleg-Zitat in dieser Spalte ist vor dem Speichern gegen das Transkript geprueft (services/slow_lane.py, Drei-Wege-Behandlung); ein erfundenes Zitat loescht die ganze Beobachtung, ein Beinahe-Treffer bleibt und wird gezaehlt. Status lebt. Schreibt services/judge_runner.py und services/slow_lane.py; liest routes/dashboard.py und templates/session_detail.html.'

# Die heutige Fassung — fuer downgrade() (verbatim aus database/models.py, 2026-08-15).
_SCHILD_OBSERVATIONS_ALT = 'Beobachtungen + WOERTLICHE Beleg-Zitate je fester Dimension (LLM-Verhaltens-Bewerter, Beobachtung statt Note). Form {dim_key:[{beobachtung,beleg_zitat}]}. SICHTBAR fuer den Nutzer (als KI-Einschaetzung gelabelt). Status: lebt (TAXO2 LLM-Bewerter). Schreibt services/judge_runner.py; liest routes/dashboard.py (Preview).'


def _comment(objekt: str, text: str) -> None:
    """COMMENT ON absetzen, ohne dass SQLAlchemy im Schild-Text herumliest.

    NICHT auf op.execute(str) umstellen. Das dreht den String durch sa.text(), und das
    liest jeden Doppelpunkt, dem KEIN Wortzeichen vorausgeht, als Bind-Parameter:
    im Schild stand die Zeilenangabe frei als "in <doppelpunkt>113-118", daraus wurde
    '%(113)s-118' und die Migration starb mit "A value is required for bind parameter
    '113'" (gefangen im Wegwerf-nerve_test am 2026-08-10, bevor Production sie sah).
    Die benachbarte Referenz 'deepgram_service.py:490' ueberlebte, weil dort ein
    Buchstabe vor dem Doppelpunkt steht - die Falle schlaegt also nur bei manchen
    Schreibweisen zu und ist damit genau die Sorte, die beim naechsten Schild wiederkommt.
    Der Schild-Text traegt seither die volle Datei-Referenz statt der nackten Zeilenzahl;
    das allein waere aber nur die Symptom-Haelfte, deshalb zusaetzlich exec_driver_sql.

    exec_driver_sql reicht die Zeichenkette unveraendert an den Treiber durch: keine
    Bind-Parameter-Erkennung, und ohne params auch keine %-Ersetzung durch psycopg2.
    Schild-Texte sind Prosa - sie muessen Doppelpunkte und Prozentzeichen tragen duerfen,
    ohne dass die Migration daran zerbricht.
    """
    op.get_bind().exec_driver_sql(
        "COMMENT ON {} IS '{}'".format(objekt, text.replace("'", "''"))
    )


def upgrade():
    _comment('COLUMN rubric_score.observations_jsonb', _SCHILD_RUBRIC_OBSERVATIONS)


def downgrade():
    _comment('COLUMN rubric_score.observations_jsonb', _SCHILD_OBSERVATIONS_ALT)
