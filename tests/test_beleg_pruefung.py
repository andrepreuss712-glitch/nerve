# -*- coding: utf-8 -*-
"""METRIK-1 Plan 01 Task 2 — Verhaltens-Tests der Zitat-Pruefung (slow_lane._pruefe_belege).

Beweist Runtime-Verhalten (CLAUDE.md Test-Qualitaets-Regel — KEIN Source-Presence):
die Drei-Wege-Behandlung (treffer / near_miss / no_match), dass ein erfundenes Zitat die GANZE
Beobachtung mitnimmt, dass das Compliance-Flag einen Zitat-Fehler ueberlebt, und dass der
Zaehler ein ABSOLUTWERT des Laufs ist (kein Aufaddieren im Helfer — sonst zaehlte ein
Wiederholungslauf desselben Anrufs doppelt, D-23).

Reine Funktions-Tests: _pruefe_belege ist eine reine Funktion, kein DB-Zugriff noetig.
"""

from services.beleg_check import beleg_im_transkript
from services.judge_dimensions import DIMENSIONS
from services.slow_lane import _pruefe_belege

DIM = DIMENSIONS[0]['key']


def _pruef_arg(text):
    """Das zweite Argument von _pruefe_belege — Task 2: der Gesamt-Korpus als String."""
    return text


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
