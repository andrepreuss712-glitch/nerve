"""transcript_segments: Sprech-Zeiten (start_ms/end_ms/word_count) + Schild-Nachzug

Revision ID: 0039
Revises: 0038
Create Date: 2026-08-10

Phase 08.23.2.ZEITSTEMPEL-1. DREI nullable Spalten, kein Backfill, keine Bestandszeile
angefasst (D-03: die Deepgram-Rohzeiten alter Anrufe existieren nicht mehr, es gibt kein
Nachtragen — genau deshalb ist diese Phase nicht nachholbar).

WARUM DREI UND NICHT VIER: eine vierte Spalte seam_before war geplant und wurde nach dem
Cross-AI-Review vom 2026-08-10 (zwei Sichten, beide unabhaengig DEFER) gestrichen — zusammen
mit dem Reconnect-Versatz, weil beide ein Paar sind. Es gibt bereits ZWEI Uhren: bei einer
Naht laeuft ts_ms (Wall-Clock) weiter, waehrend die Deepgram-Uhr steht; die Divergenz IST das
Naht-Signal. Und ohne Versatz wird naechster.start_ms minus voriger.end_ms nach einer neuen
Verbindung NEGATIV - physikalisch unmoeglich und damit ein selbsterklaerendes unbekannt, das
auch ein Leser fasst, der nie von Naehten gehoert hat. Nur den Marker zu streichen und den
Versatz zu behalten waere die schlechteste der drei Varianten gewesen: dann faellt die Naht
still auf 0 zusammen und nichts zeigt es an.

WARUM ALEMBIC UND NICHT _migrate(): app._migrate() returnt auf Postgres frueh (app.py:140) —
das Muster ist auf dem Live-Server wirkungslos und ausserdem das Alt-Muster (Punkt 29).

REIHENFOLGE BEIM AUSROLLEN (D-16, umgedreht nach Cross-AI): diese Migration laeuft auf
Production VOR dem Deploy des neuen Codes. Der Alt-Code ist vorwaerts-kompatibel (er schreibt
nur die vier Bestandsspalten), neue nullable Spalten bleiben schlicht NULL - damit gibt es
GAR KEIN Fenster. Umgekehrt braeche gegen Schema 0038 mit neuem ORM JEDER der fuenf
Entity-Leser mit UndefinedColumn, nicht nur der Schreiber.

Prod-Kopf bei Planung (inspect.sh migrations, 2026-08-10): version_num = 0038.
Vom Executor am 2026-08-10 read-only gegen Production erneut gezogen: version_num = 0038.

Die Texte unten spiegeln database/models.py (comment=) ZEICHENGLEICH (Punkt 23).
"""
from alembic import op
import sqlalchemy as sa

revision = '0039'
down_revision = '0038'
branch_labels = None
depends_on = None

_SCHILD_START_MS = 'Beginn des Abschnitts in ms auf der DEEPGRAM-AUDIO-Achse (Startzeit des ersten Wortobjekts). NICHT dieselbe Achse wie ts_ms (Wall-Clock, auf ganze Sekunden gerundet) - nie gegeneinander rechnen. NULL = unbekannt (Zeile ohne Deepgram-Wortzeiten, z.B. EWB-Knopf-Zeile, oder Anruf vor ZEITSTEMPEL-1). Verworfen wurde die dritte Variante (ts_ms einfach genau machen): dann stuenden Alt-Anrufe sekundengenau und Neu-Anrufe millisekundengenau in DERSELBEN Spalte, ein Vergleich ueber die Zeit ergaebe still Unsinn. UNVERIFIED: ueberlappende Deepgram-Endergebnisse sind nicht ausgeschlossen (endpointing=900 plus smart_format); ein Leser muss end_ms minus start_ms kleiner 0 und negative Luecken abfangen. Eine negative Luecke zum Vorgaenger ist zugleich das gewollte Naht-Signal - es gibt bewusst KEINEN Naht-Marker und keinen Versatz.'
_SCHILD_END_MS = 'Ende des Abschnitts in ms auf der DEEPGRAM-AUDIO-Achse (Endzeit des letzten Wortobjekts). end_ms minus start_ms ist die Sprech-Dauer des Abschnitts - Grundlage fuer Redeanteil, Sprechtempo, Redeblock-Laenge und Pausenlaenge (gerechnet in METRIK-1, nicht hier). NULL = unbekannt, nie 0.'
_SCHILD_WORD_COUNT = 'Anzahl gesprochener Woerter aus den ROHEN Deepgram-Wortobjekten, gezaehlt VOR der Anonymisierung. Nicht aus dem anonymisierten Text zaehlen: der Platzhalter [PERSON_A] steht fuer zwei gesprochene Woerter. NULL = unbekannt; 0 hiesse hat nichts gesagt und wuerde jeden Mittelwert verfaelschen. Bekannte Kante: ein Endergebnis mit Text, aber ohne Wortobjekte (nur Satzzeichen) liefert NULL, obwohl gesprochen wurde.'
_SCHILD_TABELLE_NEU = 'Anonymisierte Transkript-Segmente pro Call (Kind von conversation_logs, Pipeline B). Status: lebt (neue Architektur Phase 08.23.2.A+). ZWEI Zeitachsen, nie mischen: ts_ms = Wall-Clock ab Call-Start auf ganze Sekunden gerundet, nur fuer die Reihenfolge; start_ms/end_ms = Deepgram-Audio-Zeit in ms, nur fuer Messgroessen. Naht-Luecken (neue Verbindung, zurueckgehaltenes Audio) erkennt ein Leser an der Divergenz beider Uhren bzw. an einer negativen Differenz - es gibt bewusst KEINEN Naht-Marker und keinen Versatz. GEPRUEFT UND OFFEN: im Cold-Call-Modus sind Redeanteil und Redeblock-Laenge strukturell NICHT berechenbar (diarize=is_meeting in services/deepgram_service.py:490, log_sp hart 0 in :113-118) - jedes Segment landet als berater, der Redeanteil ist dort IMMER exakt 100 Prozent, eine Konstante die wie eine Messung aussieht. Sprechtempo und Pausenlaenge bleiben im Cold-Call gueltig; im Meeting-Modus kommen alle vier heraus. Abschnitte mit Art-9-Treffer oder Anonymisierungs-Fehler werden seit ZEITSTEMPEL-1 MIT echten Zeiten und dem neutralen Platzhalter-Text [nicht gespeichert] geschrieben (Weg C) - vorher entstand gar keine Zeile und ihre Sprech-Zeit fehlte still in jeder Summe. Gebuendelt am Call-Ende geschrieben - alle created_at einer Gruppe sind identisch, created_at ist KEIN Zeit-Anker (Punkt 26). Schreibt routes/app_routes.py api_beenden (Quelle: RAM-Log aus services/deepgram_service.py on_message und EWB-Knopf); liest services/adoption_runner.py, services/judge_runner.py, services/slow_lane.py (ankert auf created_at), routes/learning.py, routes/settings.py.'

# Die Fassung aus 0015 — fuer downgrade() (verbatim aus inspect.sh schilder, 2026-08-10).
_SCHILD_TABELLE_ALT = 'Anonymisierte Transkript-Segmente pro Call (Kind von conversation_logs, Pipeline B). Status: lebt (neue Architektur Phase 08.23.2.A+). Schreibt Anonymisierungs-Pipeline; liest Analyse-/Anzeige-Pfad.'


def _comment(objekt: str, text: str) -> None:
    op.execute("COMMENT ON {} IS '{}'".format(objekt, text.replace("'", "''")))


def upgrade():
    op.add_column('transcript_segments', sa.Column('start_ms', sa.Integer(), nullable=True))
    op.add_column('transcript_segments', sa.Column('end_ms', sa.Integer(), nullable=True))
    op.add_column('transcript_segments', sa.Column('word_count', sa.Integer(), nullable=True))
    _comment('COLUMN transcript_segments.start_ms', _SCHILD_START_MS)
    _comment('COLUMN transcript_segments.end_ms', _SCHILD_END_MS)
    _comment('COLUMN transcript_segments.word_count', _SCHILD_WORD_COUNT)
    _comment('TABLE transcript_segments', _SCHILD_TABELLE_NEU)


def downgrade():
    _comment('TABLE transcript_segments', _SCHILD_TABELLE_ALT)
    op.drop_column('transcript_segments', 'word_count')
    op.drop_column('transcript_segments', 'end_ms')
    op.drop_column('transcript_segments', 'start_ms')
