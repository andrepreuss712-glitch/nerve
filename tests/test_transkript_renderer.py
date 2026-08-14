# -*- coding: utf-8 -*-
"""METRIK-1 Plan 01 Task 1 — Verhaltens-Tests fuer den gemeinsamen Transkript-Renderer.

Beweist Runtime-Verhalten (CLAUDE.md Test-Qualitaets-Regel — KEIN Source-Presence):
der EWB-Filter greift in BEIDEN Render-Formen, Bewerter-Auftrag und Pruef-Korpus tragen
dieselbe Segment-Menge (D-05), und der Pruef-Korpus traegt KEINEN Tag-Praefix.

Reine Funktions-Tests: kein DB-Zugriff, keine Flask-App. Das Fake-Segment folgt dem Muster
tests/test_judge_runner.py::_make_segment.
"""

from types import SimpleNamespace

from services.transkript_renderer import (
    EWB_MARKER,
    ist_ewb_zeile,
    render_transkript,
    segmente_ohne_ewb,
)


def _seg(idx=1, speaker='berater', ts_ms=1000, text='Hallo.'):
    """Leichtgewichtige transcript_segments-Row-Attrappe (kein ORM, kein DB)."""
    return SimpleNamespace(id=idx, ts_ms=ts_ms, speaker=speaker, text=text)


def _drei_segmente():
    return [
        _seg(1, 'berater', 500, 'Guten Tag, hier ist Anna.'),
        _seg(2, 'kunde', 1500, 'Kein Interesse. *ewb button*'),
        _seg(3, 'berater', 2500, 'Ich verstehe das.'),
    ]


def test_ewb_zeile_faellt_aus_dem_auftrag():
    """Der Bewerter-Auftrag enthaelt die EWB-Knopf-Zeile nicht mehr (D-04)."""
    segs = _drei_segmente()

    getaggt = render_transkript(segs, mit_tags=True)

    assert 'Guten Tag, hier ist Anna.' in getaggt
    assert 'Ich verstehe das.' in getaggt
    assert EWB_MARKER not in getaggt
    assert 'Kein Interesse.' not in getaggt


def test_ewb_zeile_faellt_aus_dem_pruef_korpus():
    """Der Zitat-Pruef-Korpus enthaelt die EWB-Knopf-Zeile ebenfalls nicht (D-04, zweite Lese-Stelle)."""
    segs = _drei_segmente()

    korpus = render_transkript(segs, mit_tags=False)

    assert 'Guten Tag, hier ist Anna.' in korpus
    assert 'Ich verstehe das.' in korpus
    assert EWB_MARKER not in korpus
    assert len(korpus.splitlines()) == 2


def test_gleiche_segmentmenge_in_beiden_formen():
    """D-05 mechanisch festgenagelt: gleiche Segment-Menge in Auftrag und Pruef-Korpus."""
    segs = _drei_segmente()

    korpus = render_transkript(segs, mit_tags=False)
    getaggt = render_transkript(segs, mit_tags=True)

    assert len(korpus.splitlines()) == getaggt.count('[#')

    # D-05-Abgrenzung: der Pruef-Korpus traegt KEINEN Tag-Praefix — sonst fuellte sich der
    # Token-Overlap-Nenner von beleg_check (Score B) mit Rahmen-Woertern.
    assert '[#' not in korpus, "D-05-Abgrenzung: der Pruef-Korpus traegt KEINEN Tag-Praefix"


def test_nummerierung_ohne_luecke():
    """Eine gefilterte Zeile in der Mitte hinterlaesst keine Luecke in der Tag-Nummerierung."""
    segs = _drei_segmente()

    getaggt = render_transkript(segs, mit_tags=True)

    assert '[#1 berater 500ms]' in getaggt
    assert '[#2 berater 2500ms]' in getaggt
    assert '[#3' not in getaggt


def test_leere_liste():
    """Leere Segment-Liste: Auftrag traegt die Ersatz-Zeile, der Pruef-Korpus ist leer."""
    getaggt = render_transkript([], mit_tags=True)
    korpus = render_transkript([], mit_tags=False)

    assert '== TRANSKRIPT (chronologisch, ts_ms ASC) ==' in getaggt
    assert '(Keine Transkript-Segmente verfuegbar)' in getaggt
    assert korpus == ''


def test_ewb_marker_wird_am_text_erkannt_nicht_am_flag():
    """Der Filter haengt am Text-Suffix, nicht an einem RAM-Flag (das den Persist nicht ueberlebt)."""
    ohne_flag = _seg(1, 'kunde', 900, 'no_interest *ewb button*')
    normal = _seg(2, 'berater', 1800, 'Danke fuer Ihre Zeit.')

    assert ist_ewb_zeile(ohne_flag) is True
    assert ist_ewb_zeile(normal) is False
    assert getattr(ohne_flag, 'data', None) is None

    gefiltert = segmente_ohne_ewb([ohne_flag, normal])
    assert len(gefiltert) == 1
    assert gefiltert[0].text == 'Danke fuer Ihre Zeit.'


def test_pruef_fenster_enthaelt_einzelne_und_paare():
    """3 Segmente -> 5 Fenster (3 einzeln, 2 Paare); 1 Segment -> 1 Fenster; leer -> []."""
    from services.transkript_renderer import pruef_fenster

    segs = [
        _seg(1, 'berater', 500, 'Erster Satz.'),
        _seg(2, 'kunde', 1500, 'Zweiter Satz.'),
        _seg(3, 'berater', 2500, 'Dritter Satz.'),
    ]

    fenster = pruef_fenster(segs)

    assert len(fenster) == 5
    assert 'Erster Satz.' in fenster[0]
    # Ein Paar-Fenster traegt beide Nachbar-Texte, ein Einzel-Fenster nur einen.
    assert 'Erster Satz.\nZweiter Satz.' in fenster
    assert 'Erster Satz.\nDritter Satz.' not in fenster

    assert len(pruef_fenster([segs[0]])) == 1
    assert pruef_fenster([]) == []


def test_pruef_fenster_ohne_ewb_zeile():
    """Der EWB-Filter laeuft VOR der Paar-Bildung — sonst waere die Nachbarschaft eine andere."""
    from services.transkript_renderer import pruef_fenster

    segs = [
        _seg(1, 'berater', 500, 'Vor dem Knopf.'),
        _seg(2, 'kunde', 1500, 'no_interest *ewb button*'),
        _seg(3, 'berater', 2500, 'Nach dem Knopf.'),
    ]

    fenster = pruef_fenster(segs)

    assert all(EWB_MARKER not in f for f in fenster)
    # Zwei Segmente, die im Original durch die EWB-Zeile getrennt waren, bilden EIN Paar-Fenster.
    assert len(fenster) == 3
    assert 'Vor dem Knopf.\nNach dem Knopf.' in fenster
