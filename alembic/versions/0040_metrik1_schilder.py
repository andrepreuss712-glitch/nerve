"""rubric_score: Schilder von status und payload_jsonb nachziehen (METRIK-1, Punkt 23)

Revision ID: 0040
Revises: 0039
Create Date: 2026-08-14

Phase 08.23.2.METRIK-1. REINE COMMENT-ON-MIGRATION: sie legt KEINE Spalte an, loescht keine
und aendert keinen Typ. Sie zieht die Schilder von rubric_score.status und
rubric_score.payload_jsonb auf den Zustand nach dieser Phase nach — Aktualitaets-Pflicht
(CLAUDE.md Punkt 23): ein Schild wird in DERSELBEN Aenderung nachgezogen, die seine Bedeutung
aendert.

WAS SICH AN DER BEDEUTUNG AENDERT:
  status       - der Alt-Grund too_few_high_confidence_events wird NICHT mehr geschrieben
                 (das Einwand-Momente-Tor ist entfallen). An seine Stelle tritt
                 too_little_speech. Alt-Zeilen mit dem Alt-Grund bleiben in der Datenbank
                 stehen, der Anzeige-Zweig dafuer bleibt deshalb bewusst erhalten.
  payload_jsonb - traegt ab jetzt ZWEI feste Bereiche: den beleg_check-Zaehler der
                 Zitat-Pruefung (Plan 01) und die Messwerte samt Tor-Zweig jeder Ablehnung
                 (Plan 02). Beide sind mit diesem einen Ausrollen entstanden (D-01).

WARUM ALEMBIC UND NICHT _migrate(): app._migrate() returnt auf Postgres frueh (app.py) —
das Muster ist auf dem Live-Server wirkungslos und ausserdem das Alt-Muster (Punkt 29).

Prod-Kopf bei Planung (inspect.sh migrations, 2026-08-13): version_num = 0039.
Vom Executor am 2026-08-14 read-only gegen Production erneut gezogen: version_num = 0039.

REIHENFOLGE BEIM AUSROLLEN: Diese Migration legt keine Spalte an und aendert keinen Typ, sie
setzt nur COMMENT ON. Sie ist damit in BEIDE Richtungen unkritisch und darf vor oder nach dem
Deploy laufen. Festgelegt ist: Migration ZUERST, dann deploy.sh production — damit der
Schild-Waechter im Test-Tor gegen den bereits gesetzten Kommentar laeuft.
⚠ Die ZEITSTEMPEL-1-Regel "Migration vor Deploy" gilt nur fuer NEUE NULLABLE SPALTEN und wird
hier ausdruecklich NICHT blind uebertragen — hier gibt es keine neue Spalte.

Die Texte unten spiegeln database/models.py (comment=) ZEICHENGLEICH (Punkt 23).
"""
from alembic import op
import sqlalchemy as sa

revision = '0040'
down_revision = '0039'
branch_labels = None
depends_on = None

_SCHILD_RUBRIC_STATUS = 'Bewertungs-Status. Werte judged, scored, pending, judge_failed, transcript_not_resolved, not_gradable. NULL bedeutet noch nicht gelaufen. Bei not_gradable steht der Grund in payload_jsonb unter dem Schluessel reason. Ab METRIK-1 gibt es zwei lebende Gruende - poor_audio_health (Audio-Tor, unveraendert) und too_little_speech (Sprech-Substanz-Tor, weniger als zwanzig gesprochene Berater-Woerter; die Zahl der Redeabschnitte ist reiner Messwert und KEINE Bedingung). Welcher Weg genommen wurde, steht daneben im Schluessel tor_zweig. Der Alt-Grund too_few_high_confidence_events wird seit METRIK-1 NICHT mehr geschrieben, steht aber weiter auf Alt-Zeilen in der Datenbank - der Anzeige-Zweig dafuer bleibt deshalb erhalten. Schreibt services/slow_lane.py; liest routes/dashboard.py und templates/session_detail.html.'
_SCHILD_RUBRIC_PAYLOAD = 'Reserve, Training-only-Felder (was_correct, scenario_id, ground_truth_score) und ab METRIK-1 zwei feste Bereiche. Bei not_gradable die Begruendung samt Messwerten - reason, schema, berater_woerter, redeabschnitte, sprechzeit_ms, high_conf_events, tor_zweig. redeabschnitte ist dort ein reiner Diagnose-Wert und keine Bedingung. tor_zweig nennt den genommenen Weg - genug_woerter, zu_wenig_woerter, keine_berater_zeile oder wortzahl_unbekannt_durchgelassen; der letzte laesst bewusst DURCH und erscheint deshalb nur an judged-Zeilen. Eine Zahl NULL heisst dort UNBEKANNT, nie null Woerter; sie ist die Grundlage der Tor-Nachjustierung nach rund hundert echten Anrufen. Bei judged der Zaehler der Zitat-Pruefung unter dem Schluessel beleg_check mit geprueft, treffer, near_miss, verworfen und compliance_beleg_verworfen. Dieser Zaehler ist ein ABSOLUTWERT des Laufs - der Upsert ersetzt payload_jsonb vollstaendig (ON CONFLICT DO UPDATE), ein Wiederholungslauf desselben Anrufs zaehlt daher per Bauart nicht doppelt. Schreibt services/slow_lane.py; liest routes/dashboard.py, templates/session_detail.html und services/beleg_check_counter.py (Prozess-Zaehler der Founder-Sicht).'

# Die heutigen Fassungen — fuer downgrade() (verbatim aus database/models.py, 2026-08-14).
_SCHILD_STATUS_ALT = 'Bewertungs-Status: scored|pending|not_gradable (D-09 poor_audio_health). NULL = noch nicht gelaufen.'
_SCHILD_PAYLOAD_ALT = 'Reserve + Training-only-Felder (was_correct, scenario_id, ground_truth_score) ohne spaetere Migration. SPEC Req 1.'


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
    _comment('COLUMN rubric_score.status', _SCHILD_RUBRIC_STATUS)
    _comment('COLUMN rubric_score.payload_jsonb', _SCHILD_RUBRIC_PAYLOAD)


def downgrade():
    _comment('COLUMN rubric_score.status', _SCHILD_STATUS_ALT)
    _comment('COLUMN rubric_score.payload_jsonb', _SCHILD_PAYLOAD_ALT)
