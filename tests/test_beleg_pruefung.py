# -*- coding: utf-8 -*-
"""METRIK-1 Plan 01 Task 2 — Verhaltens-Tests der Zitat-Pruefung (slow_lane._pruefe_belege).

Beweist Runtime-Verhalten (CLAUDE.md Test-Qualitaets-Regel — KEIN Source-Presence):
die Drei-Wege-Behandlung (treffer / near_miss / no_match), dass ein erfundenes Zitat die GANZE
Beobachtung mitnimmt, dass das Compliance-Flag einen Zitat-Fehler ueberlebt, und dass der
Zaehler ein ABSOLUTWERT des Laufs ist (kein Aufaddieren im Helfer — sonst zaehlte ein
Wiederholungslauf desselben Anrufs doppelt, D-23).

Reine Funktions-Tests: _pruefe_belege ist eine reine Funktion, kein DB-Zugriff noetig.
"""

from types import SimpleNamespace

from services.beleg_check import beleg_im_transkript
from services.judge_dimensions import DIMENSIONS
from services.slow_lane import _pruefe_belege
from services.transkript_renderer import pruef_fenster, render_transkript

DIM = DIMENSIONS[0]['key']

# Drei weit auseinanderliegende Aussagen (SEG_A/SEG_C/SEG_E) und zwei Fueller dazwischen.
# Die Fueller tragen KEIN Wort des Zitats — sonst verschoebe sich der Wort-Mengen-Score.
SEG_FUELLER_1 = 'Verstehe.'
SEG_FUELLER_2 = 'Okay.'
SEG_A = 'Ich sage Ihnen ganz offen: unsere Maschinen stehen still.'
SEG_C = 'Der Einkauf hat uns das Budget komplett zusammengestrichen.'
SEG_E = 'Und mein Chef will vor September gar nichts entscheiden.'

TEIL_A = 'unsere Maschinen stehen still'
TEIL_C = 'Der Einkauf hat uns das Budget'
TEIL_E = 'mein Chef will vor September'

# Aus DREI Bruchstuecken dreier NICHT benachbarter Segmente zusammengesetzt — jedes einzelne
# Fenster traegt hoechstens ein Bruchstueck.
ZITAT_UEBER_GRENZE = TEIL_A + ' ' + TEIL_C + ' ' + TEIL_E
# Ueber genau EINE Naht zusammengesetzt — die typische Trennung der Spracherkennung.
ZITAT_UEBER_NAHT = TEIL_A + ' ' + TEIL_C


def _seg(idx=1, speaker='kunde', ts_ms=1000, text=''):
    """transcript_segments-Row-Attrappe (kein ORM, kein DB)."""
    return SimpleNamespace(id=idx, ts_ms=ts_ms, speaker=speaker, text=text)


def _pruef_arg(text):
    """Das zweite Argument von _pruefe_belege: die Pruef-Fenster.

    Ein einzelner Text ist ein einzelnes Fenster. Task 2 uebergab hier noch den Gesamt-Korpus
    als String; seit Task 5 prueft _pruefe_belege gegen eine Fenster-LISTE.
    """
    return [text]


def _obs(dim_key=DIM, beobachtung='Der Berater fragte offen nach.', beleg_zitat=''):
    """observations_jsonb-Form aus judge_runner._parse_judge_output (eine Dimension befuellt)."""
    leer = {d['key']: [] for d in DIMENSIONS}
    leer[dim_key] = [{'beobachtung': beobachtung, 'beleg_zitat': beleg_zitat}]
    leer['_compliance'] = {'verletzt': False, 'beleg_zitat': ''}
    return leer


def test_erfundenes_zitat_loescht_die_ganze_beobachtung():
    """no_match -> die GANZE Beobachtung faellt weg, nicht nur das Zitat."""
    korpus = 'Guten Tag, hier ist Anna.'
    observations = _obs(beleg_zitat='Wir liefern morgen nach Sizilien')

    geprueft, zaehler = _pruefe_belege(observations, _pruef_arg(korpus))

    assert geprueft[DIM] == []
    assert zaehler['verworfen'] == 1
    assert zaehler['treffer'] == 0
    assert zaehler['geprueft'] == 1


def test_treffer_bleibt_stehen():
    """Ein woertliches Zitat aus dem Korpus bleibt stehen und zaehlt als Treffer."""
    korpus = 'Guten Tag, hier ist Anna. Ich rufe wegen Ihrer Anfrage an.'
    observations = _obs(beleg_zitat='Ich rufe wegen Ihrer Anfrage an.')

    geprueft, zaehler = _pruefe_belege(observations, _pruef_arg(korpus))

    assert len(geprueft[DIM]) == 1
    assert geprueft[DIM][0]['beleg_zitat'] == 'Ich rufe wegen Ihrer Anfrage an.'
    assert zaehler['treffer'] == 1
    assert zaehler['verworfen'] == 0


def test_beinahe_treffer_bleibt_stehen_und_wird_gezaehlt():
    """Eine Schwaerzung erzeugt einen Beinahe-Treffer — der bleibt stehen UND wird gezaehlt."""
    korpus = 'Guten Tag, hier ist Anna Schmidt von der Firma Nordwind.'
    zitat = 'Guten Tag, hier ist [PERSON_A] [PERSON_B] von der Firma [ORG_A].'

    # Die Schwelle nicht raten: den Befund zuerst an beleg_im_transkript selbst festnageln,
    # sonst prueft dieser Test bei einer Schwellen-Aenderung still etwas anderes.
    _ok, _score, befund = beleg_im_transkript(zitat, korpus)
    assert befund == 'near_miss', f"Testaufbau liefert '{befund}' statt 'near_miss' (score={_score})"

    geprueft, zaehler = _pruefe_belege(_obs(beleg_zitat=zitat), _pruef_arg(korpus))

    assert len(geprueft[DIM]) == 1
    assert zaehler['near_miss'] == 1
    assert zaehler['verworfen'] == 0


def test_alle_beobachtungen_verworfen_ergibt_leere_dimensionen():
    """Alle vier Dimensionen mit erfundenen Zitaten -> jede Liste leer, aber alle Keys da."""
    korpus = 'Guten Tag, hier ist Anna.'
    observations = {d['key']: [{'beobachtung': 'x', 'beleg_zitat': 'Voellig erfundener Satz ueber Sizilien'}]
                    for d in DIMENSIONS}
    observations['_compliance'] = {'verletzt': False, 'beleg_zitat': ''}

    geprueft, zaehler = _pruefe_belege(observations, _pruef_arg(korpus))

    for dim in DIMENSIONS:
        assert geprueft[dim['key']] == []
        # Der Anzeige-Zweig "Nicht genug zum Bewerten." haengt an observations_display,
        # NICHT an fehlenden Keys — die vier Schluessel muessen weiter vorhanden sein.
        assert dim['key'] in geprueft
    assert zaehler['verworfen'] == 4


def test_compliance_zitat_erfunden_flag_bleibt():
    """Sicherheits-Hard-Gate: das Flag ueberlebt einen Zitat-Fehler, nur das Zitat faellt."""
    korpus = 'Guten Tag, hier ist Anna.'
    observations = _obs(beleg_zitat='Ich rufe wegen Ihrer Anfrage an.')
    observations['_compliance'] = {'verletzt': True, 'beleg_zitat': 'Nie gesagter Satz ueber Sizilien'}

    geprueft, zaehler = _pruefe_belege(observations, _pruef_arg(korpus))

    assert geprueft['_compliance']['verletzt'] is True
    assert geprueft['_compliance']['beleg_zitat'] == ''
    assert zaehler['compliance_beleg_verworfen'] == 1


def test_unbekannte_unterstrich_schluessel_bleiben():
    """Vorwaerts-Vertraeglichkeit (Plan 05): unbekannte Unterstrich-Schluessel gehen unveraendert durch."""
    korpus = 'Guten Tag, hier ist Anna.'
    observations = _obs(beleg_zitat='Guten Tag, hier ist Anna.')
    observations['_kopfzeile'] = {'x': 1}

    geprueft, _zaehler = _pruefe_belege(observations, _pruef_arg(korpus))

    assert geprueft['_kopfzeile'] == {'x': 1}


def test_zaehler_ist_absolutwert():
    """Zweimal dieselbe Eingabe -> zweimal derselbe Zaehler (kein Aufaddieren im Helfer, D-23)."""
    korpus = 'Guten Tag, hier ist Anna.'
    observations = _obs(beleg_zitat='Erfundener Satz ueber Sizilien')

    _g1, zaehler1 = _pruefe_belege(observations, _pruef_arg(korpus))
    _g2, zaehler2 = _pruefe_belege(observations, _pruef_arg(korpus))

    assert zaehler1 == zaehler2
    assert zaehler1['verworfen'] == 1


def test_prozess_zaehler_summiert():
    """Die Anzeige-Schicht ADDIERT, waehrend der DB-Wert je Anruf ein Absolutwert ist.

    Beide Semantiken stehen bewusst nebeneinander (D-23) — dieser Test nagelt die
    Summen-Seite fest, test_zaehler_ist_absolutwert die Absolutwert-Seite.
    """
    from services.beleg_check_counter import (
        get_beleg_check_counts,
        record_beleg_check,
        reset_beleg_check_counts,
    )

    reset_beleg_check_counts()
    try:
        record_beleg_check({'schema': 1, 'geprueft': 4, 'treffer': 2, 'near_miss': 1,
                            'verworfen': 1, 'compliance_beleg_verworfen': 0})
        record_beleg_check({'schema': 1, 'geprueft': 3, 'treffer': 1, 'near_miss': 0,
                            'verworfen': 2, 'compliance_beleg_verworfen': 1})

        summen = get_beleg_check_counts()

        assert summen['geprueft'] == 7
        assert summen['treffer'] == 3
        assert summen['near_miss'] == 1
        assert summen['verworfen'] == 3
        assert summen['compliance_beleg_verworfen'] == 1
        assert 'schema' not in summen
    finally:
        reset_beleg_check_counts()


# ── Task 5: die Segment-Grenze wird beim Pruefen wirklich respektiert ─────────────────────

def _fenster_fuer(segmente):
    """Das zweite Argument von _pruefe_belege, aus Segmenten gebaut.

    Task 2 baute hier den GESAMT-Korpus (ein Text ueber alle Segmente); seit Task 5 sind es
    Segment- und Nachbarpaar-Fenster. Genau dieser Wechsel macht den Unterschied, den die
    beiden Tests unten festnageln.
    """
    return pruef_fenster(segmente)


def test_zitat_ueber_segmentgrenze_wird_verworfen():
    """Ein Zitat aus zwei NICHT benachbarten Segmenten wird verworfen (Minute 2 + Minute 10)."""
    segs = [
        _seg(1, 'kunde', 1000, SEG_A),
        _seg(2, 'berater', 2000, SEG_FUELLER_1),
        _seg(3, 'kunde', 3000, SEG_C),
        _seg(4, 'berater', 4000, SEG_FUELLER_2),
        _seg(5, 'kunde', 5000, SEG_E),
    ]

    # Gegenprobe: gegen den GESAMT-Korpus ist genau dieses Zitat ein 'treffer' (Score B ist eine
    # reine Wort-MENGE ohne Reihenfolge). Das belegt, dass die FENSTER den Unterschied machen —
    # nicht der Testaufbau.
    korpus = render_transkript(segs, mit_tags=False)
    _ok, _score, befund_korpus = beleg_im_transkript(ZITAT_UEBER_GRENZE, korpus)
    assert befund_korpus == 'treffer', (
        f"Gegenprobe traegt nicht: gegen den Gesamt-Korpus liefert das zusammengesetzte Zitat "
        f"'{befund_korpus}' (score={_score}) statt 'treffer'."
    )

    geprueft, zaehler = _pruefe_belege(_obs(beleg_zitat=ZITAT_UEBER_GRENZE), _fenster_fuer(segs))

    assert geprueft[DIM] == []
    assert zaehler['verworfen'] == 1
    assert zaehler['treffer'] == 0


def test_zitat_ueber_benachbarte_segmente_bleibt():
    """Die Regel gegen ein Zuviel: ueber eine BENACHBARTE Naht bleibt das Zitat stehen.

    Die Spracherkennung trennt Aussagen mitten im Satz — ein Zitat ueber genau eine solche
    Naht ist echt."""
    segs = [
        _seg(1, 'berater', 500, SEG_FUELLER_1),
        _seg(2, 'kunde', 1000, SEG_A),
        _seg(3, 'kunde', 2000, SEG_C),
    ]

    geprueft, zaehler = _pruefe_belege(_obs(beleg_zitat=ZITAT_UEBER_NAHT), _fenster_fuer(segs))

    assert len(geprueft[DIM]) == 1
    assert zaehler['verworfen'] == 0
    assert zaehler['treffer'] == 1
