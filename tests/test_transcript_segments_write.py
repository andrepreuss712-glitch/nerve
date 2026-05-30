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
