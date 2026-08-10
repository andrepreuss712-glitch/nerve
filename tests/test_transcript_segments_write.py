# Phase 08.23.2.D.UX.1 — Plan 02 (WARN-3) — Function-Call-Return Test fuer die
# reine Transcript-Transform. KEIN Source-Presence-Test (CLAUDE.md Test-Qualitaets-Regel):
# importiert den echten Helper und assertiert auf den Rueckgabewert.
# Idempotenz lebt im DB-INSERT-Pfad (Reentrance-Guard in api_beenden) und wird live via
# Plan 05 DT-03 verifiziert — NICHT hier mit einem Source-Presence-Check gefaket.
from routes.app_routes import _transcript_entries_to_segments


def test_transform_maps_speaker_and_derives_ts_ms():
    entries = [
        {'type': 'transcript', 'ts': '00:00:01', 'speaker': 0, 'text': 'Hallo'},
        {'type': 'transcript', 'ts': '00:00:05', 'speaker': 1, 'text': 'Guten Tag'},
        {'type': 'coaching',   'ts': '00:00:06', 'speaker': 0, 'text': 'tip'},   # non-transcript -> skipped
        {'type': 'transcript', 'ts': '00:00:09', 'speaker': 9, 'text': 'Ende'},  # unknown speaker -> 'system'
    ]
    segs = _transcript_entries_to_segments(entries)
    assert len(segs) == 3                                  # coaching entry dropped
    assert [s['speaker'] for s in segs] == ['berater', 'kunde', 'system']
    assert all(s['speaker'] in ('berater', 'kunde', 'system') for s in segs)   # CHECK-safe
    ts = [s['ts_ms'] for s in segs]
    assert ts == sorted(ts)                                # monoton non-decreasing (Ordnung erhalten)
    # WARN-4: ts_ms ist ms-ab-Call-Start (relativ zum ersten Entry), NICHT Tageszeit.
    assert ts[0] == 0                                      # erster Entry -> Offset 0
    assert ts == [0, 4000, 8000]                           # 00:00:01 base -> +4s, +8s


def test_speaker_none_maps_to_system():
    # deepgram_service.py:116 schreibt speaker=None solange Rollen nicht bestaetigt sind.
    segs = _transcript_entries_to_segments([
        {'type': 'transcript', 'ts': '00:00:01', 'speaker': None, 'text': 'Wer spricht?'},
    ])
    assert len(segs) == 1
    assert segs[0]['speaker'] == 'system'                  # None -> 'system' (CHECK-safe)


def test_empty_and_nontranscript_entries_dropped():
    segs = _transcript_entries_to_segments([
        {'type': 'transcript', 'ts': '00:00:01', 'speaker': 0, 'text': ''},   # empty text -> dropped
        {'type': 'system',     'ts': '00:00:02', 'speaker': 0, 'text': 'x'},  # non-transcript -> dropped
    ])
    assert segs == []


def test_monotonic_clamp_on_clock_wrap():
    # Wall-Clock kann rueckwaerts springen (Mitternacht). ts_ms muss trotzdem monoton bleiben.
    segs = _transcript_entries_to_segments([
        {'type': 'transcript', 'ts': '23:59:59', 'speaker': 0, 'text': 'vor Mitternacht'},
        {'type': 'transcript', 'ts': '00:00:02', 'speaker': 1, 'text': 'nach Mitternacht'},
    ])
    ts = [s['ts_ms'] for s in segs]
    assert ts == sorted(ts)                                # kein Ruecksprung trotz Wrap
    assert ts[0] == 0


# ── Phase 08.23.2.ZEITSTEMPEL-1 — Sprech-Zeiten durch die reine Transform ──────────────
# ROT gegen den Stand vor dieser Phase: die Transform gibt heute nur ts_ms/speaker/text
# zurueck, der Zugriff auf 'start_ms' wirft KeyError. Function-Call-Return-Test, kein
# Source-Presence-Check (CLAUDE.md Test-Qualitaets-Regel).

def test_transform_reicht_sprechzeiten_durch():
    segs = _transcript_entries_to_segments([
        {'type': 'transcript', 'ts': '00:00:01', 'speaker': 0, 'text': 'Guten Tag',
         'start_ms': 1200, 'end_ms': 4300, 'word_count': 7},
    ])
    assert len(segs) == 1
    assert segs[0]['start_ms'] == 1200
    assert segs[0]['end_ms'] == 4300
    assert segs[0]['word_count'] == 7


def test_knopfzeile_ohne_wortzeiten_wird_null():
    # Die EWB-Knopf-Zeile (services/deepgram_service.py:1094-1105) setzt die drei
    # Schluessel schlicht nicht. D-04: dann NULL, ausdruecklich nicht 0 —
    # word_count=0 hiesse "hat nichts gesagt", None heisst "unbekannt".
    segs = _transcript_entries_to_segments([
        {'type': 'transcript', 'ts': '00:00:01', 'speaker': 1,
         'text': 'preis *ewb button*', 'data': {'ewb_button': True}},
    ])
    assert len(segs) == 1
    assert segs[0]['start_ms'] is None
    assert segs[0]['end_ms'] is None
    assert segs[0]['word_count'] is None


def test_platzhalterzeile_behaelt_ihre_sprechzeiten():
    # Weg C (Andre 2026-08-10): ein Abschnitt mit Art-9-Treffer oder Anonymisierungs-
    # Fehler wird NICHT mehr verworfen, sondern mit neutralem Platzhalter-Text und
    # ECHTEN Zeiten geschrieben. Sonst fehlte seine Sprech-Zeit in Zaehler UND Nenner
    # des Redeanteils und die Luecke wuerde als Pause fehlgelesen.
    segs = _transcript_entries_to_segments([
        {'type': 'transcript', 'ts': '00:00:01', 'speaker': 1,
         'text': '[nicht gespeichert]', 'start_ms': 2000, 'end_ms': 32000,
         'word_count': 61},
    ])
    assert len(segs) == 1
    assert segs[0]['text'] == '[nicht gespeichert]'
    assert segs[0]['end_ms'] - segs[0]['start_ms'] == 30000
    assert segs[0]['word_count'] == 61


def test_ts_ms_bleibt_unberuehrt_von_den_neuen_spalten():
    # D-02: zwei getrennte Achsen. Die Deepgram-Zeiten duerfen die ts_ms-Arithmetik
    # (Wall-Clock, relativ zum ersten Entry, monoton geklemmt) NICHT veraendern.
    segs = _transcript_entries_to_segments([
        {'type': 'transcript', 'ts': '00:00:01', 'speaker': 0, 'text': 'a',
         'start_ms': 500,  'end_ms': 900,  'word_count': 1},
        {'type': 'transcript', 'ts': '00:00:05', 'speaker': 1, 'text': 'b',
         'start_ms': 4100, 'end_ms': 4800, 'word_count': 2},
        {'type': 'transcript', 'ts': '00:00:09', 'speaker': 9, 'text': 'c',
         'start_ms': 8200, 'end_ms': 9000, 'word_count': 2},
    ])
    assert [s['ts_ms'] for s in segs] == [0, 4000, 8000]
