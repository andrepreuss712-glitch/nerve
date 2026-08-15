# -*- coding: utf-8 -*-
"""METRIK-1 Plan 04, Task 2 — Zaehlregel-Tests des Fokus-Katalogs (Ersatz fuer Kriterium d).

WARUM DIESE TESTS DAS GESTRICHENE KRITERIUM (d) ERSETZEN: (d) haette geprueft, ob das vom
Modell genannte Kriterium im Transkript nachweisbar verletzt ist. Beim Rechenweg prueft sich das
SELBST — der Code nennt nur, was er selbst gezaehlt hat. Ein Waechter, der immer ja sagt.
Was NICHT selbstpruefend ist, sind die ZAEHLREGELN. Genau die stehen hier.

Die fuenf Kanten aus D-09, jede als EIGENE Funktion (keine Schleife ueber die Kanten):
Wortgrenzen · Platzhalter aus der Anonymisierung · Gross-/Kleinschreibung · die EWB-Knopf-Zeile ·
die "ab 4x"-Schwelle exakt auf der Kante (3x darf nicht ausloesen, 4x muss).

Alle Assertions sind RUECKGABEWERT-Assertions (CLAUDE.md Test-Qualitaets-Regel). Es wird kein
Quelltext gelesen und keine blosse Symbol-Existenz geprueft — solche Tests waeren gruen, solange
der Code nur DASTEHT, auch wenn er nie laeuft.
"""

import services.fokus_katalog as fk


# ── Kante 1+2: Wortgrenzen (D-09) ────────────────────────────────────────────────────────

def test_wortgrenze_we_trifft_nicht_in_week():
    """'we' darf NICHT in 'week' treffen — Teilstring-Vergleich waere hier ein stiller Fehler."""
    norm = fk._normalize('Next week we are ready.')
    assert fk._zaehle('we', norm) == 1
    assert fk._zaehle('week', norm) == 1


def test_wortgrenze_i_trifft_nicht_in_it():
    """'i' darf NICHT in 'it'/'inside' treffen — sonst waere jede we/I-Zaehlung Rauschen."""
    assert fk._zaehle('i', 'it is inside') == 0
    assert fk._zaehle('i', 'i am here') == 1


# ── Kante 3: Gross-/Kleinschreibung ──────────────────────────────────────────────────────

def test_grossschreibung_egal():
    """'We Provide' und 'we provide' zaehlen gleich (D-09, erledigt in _normalize)."""
    gross = fk._normalize('We Provide the best')
    klein = fk._normalize('we provide the best')
    assert gross == klein
    assert fk._zaehle('we provide', gross) == 1
    assert fk._zaehle('we provide', klein) == 1


# ── Kante 4: Platzhalter der Anonymisierung ──────────────────────────────────────────────

def test_platzhalter_erzeugt_keine_treffer():
    """Ein geschwaerztes Transkript erzeugt keinen Fokus — auch die Firmenname-Teilregel nicht.

    Das ist zugleich die belegte Grenze aus dem SUMMARY: ein erkannter Firmenname steht im
    gespeicherten Transkript als Platzhalter-Token, nicht im Klartext.
    """
    texte = [
        'Guten Tag [PERSON_A], hier spricht [PERSON_B] von [ORG_C].',
        'Wir haben gesehen, dass [ORG_C] gerade waechst.',
        '[nicht gespeichert]',
        'Darf ich Ihnen kurz erklaeren, worum es geht?',
    ]
    norm = fk._normalize(' '.join(texte))
    assert fk._zaehle('acme', norm) == 0
    assert fk.waehle_fokus(texte, firmenname='Acme') is None
    assert fk.waehle_fokus(texte) is None


# ── Kante 5: die EWB-Knopf-Zeile ─────────────────────────────────────────────────────────

def test_ewb_zeile_zaehlt_nicht():
    """Ein Knopfdruck ist kein Satz — mit gepaartem Positiv-Fall in derselben Funktion.

    Ohne den Positiv-Fall waere 'None' nicht von 'die Funktion tut ueberhaupt nichts' zu
    unterscheiden.
    """
    mit_knopf = ['we provide *ewb button*'] * 4
    assert fk.waehle_fokus(mit_knopf) is None

    ohne_knopf = ['we provide value'] * 4
    ergebnis = fk.waehle_fokus(ohne_knopf)
    assert ergebnis is not None
    assert ergebnis['focus_key'] == 'negative_phrases'


# ── Kante 6+7: die "ab 4x"-Schwelle exakt auf der Kante (bewusst ZWEI Funktionen) ────────

def test_schwelle_drei_mal_loest_nicht_aus():
    """Genau 3x 'we provide' liegt UNTER der belegten Schwelle 4 — kein Fokus."""
    texte = ['we provide value.', 'we provide support.', 'we provide training.']
    assert fk.waehle_fokus(texte) is None


def test_schwelle_vier_mal_loest_aus():
    """Genau 4x 'we provide' erreicht die belegte Schwelle 4 — Fokus mit Kappungs-Satz."""
    texte = ['we provide value.', 'we provide support.',
             'we provide training.', 'we provide more.']
    ergebnis = fk.waehle_fokus(texte)
    assert ergebnis is not None
    assert ergebnis['focus_key'] == 'negative_phrases'
    assert ergebnis['count'] == 4
    assert ergebnis['limit'] == 4
    assert 'top reps cap it at 3' in ergebnis['satz']
    assert ergebnis['katalog_version'] == fk.KATALOG_VERSION


# ── Der Beleg-Satz: per Bauart echt, nicht per Pruefung ──────────────────────────────────

def test_beleg_ist_woertlich_aus_dem_transkript():
    """Der Beleg ist IDENTISCH mit einem der uebergebenen Texte — die Kern-Zusage aus D-07."""
    texte = ['Hello there.', 'we provide value.', 'we provide support.',
             'we provide training.', 'we provide more.']
    ergebnis = fk.waehle_fokus(texte)
    assert ergebnis is not None
    assert ergebnis['beleg'] in texte
    assert ergebnis['beleg'] == 'we provide value.'


def test_deterministisch():
    """Gleiche Eingabe -> identisches Dict. Keine Zufallsquelle, keine Zeit, kein Modell."""
    texte = [
        'Our solution is innovative and scalable.',
        'It is a robust solution for your team.',
        'That is the seamless part.',
    ]
    erst = fk.waehle_fokus(texte)
    zweit = fk.waehle_fokus(texte)
    assert erst is not None
    assert erst == zweit
    assert erst['focus_key'] == 'problem_language'
    assert '"solution" most often' in erst['satz']


# ── D-10: der "diesmal nichts"-Zweig ist der NORMALFALL ──────────────────────────────────

def test_kein_kriterium_verletzt_liefert_none():
    """Ein sauberer englischer Anruf mit frueh genanntem Anruf-Grund -> ehrlich None."""
    texte = [
        'Hi Sarah, the reason for my call is that your team is hiring three new reps.',
        'We saw the job posts and we wondered how you are onboarding them today.',
        'What is the biggest problem you are running into with that?',
    ]
    assert fk._ist_englisch(fk._normalize(' '.join(texte)))
    assert fk.waehle_fokus(texte) is None


def test_deutscher_anruf_liefert_none():
    """Ein deutscher Cold-Call loest NICHTS aus — SPEC NACHTRAG 2 (1) plus Sprach-Riegel.

    Ohne den Riegel wuerde reason_for_call hier feuern, weil sie auf ABWESENHEIT prueft.
    """
    texte = [
        'Guten Tag Herr Meier, mein Name ist Anna Schmidt von der Vertriebsberatung.',
        'Ich rufe an, weil wir mit mittelstaendischen Maschinenbauern arbeiten.',
        'Viele unserer Kunden berichten, dass die Termin-Quote im Aussendienst einbricht.',
        'Haben Sie dazu gerade fuenf Minuten?',
    ]
    assert not fk._ist_englisch(fk._normalize(' '.join(texte)))
    assert fk.waehle_fokus(texte) is None


def test_englischer_anruf_ohne_anruf_grund_loest_reason_for_call_aus():
    """Der Gegenbeweis: der Riegel sperrt nicht generell, er sperrt nur die falsche Sprache."""
    texte = [
        'Hi, is this a good moment to talk with you for a second?',
        'You are the one who is looking after the field team, right?',
        'We help teams that are losing meetings, and we wanted to ask how you handle it.',
    ]
    ergebnis = fk.waehle_fokus(texte)
    assert ergebnis is not None
    assert ergebnis['focus_key'] == 'reason_for_call'
    assert ergebnis['count'] == 3
    assert ergebnis['beleg'] == texte[0]
    assert 'top reps name it in the first line' in ergebnis['satz']


# ── Rangfolge und Sonderregeln ───────────────────────────────────────────────────────────

def test_rangfolge_negative_phrases_schlaegt_we_not_i():
    """Sind BEIDE Regeln verletzt, gewinnt die mit dem staerkeren belegten Effekt."""
    texte = [
        'I think we provide the best service, and I know my team agrees.',
        'we provide support, I checked it myself.',
        'we provide training for you, my team runs it.',
        'we provide reporting, and I own that part.',
    ]
    norm = fk._normalize(' '.join(texte))
    ich = sum(fk._zaehle(w, norm) for w in fk.ICH_WOERTER)
    wir = sum(fk._zaehle(w, norm) for w in fk.WIR_WOERTER)
    assert ich >= fk.ICH_SCHWELLE and ich > wir      # we_not_i waere fuer sich verletzt
    ergebnis = fk.waehle_fokus(texte)
    assert ergebnis is not None
    assert ergebnis['focus_key'] == 'negative_phrases'


def test_absolutely_und_perfect_werden_addiert():
    """Die Quelle beschreibt beide als EINE Regel — 3x + 1x loest aus, 2x + 1x nicht."""
    loest_aus = ['absolutely right.', 'absolutely fine.',
                 'absolutely sure.', 'that is perfect.']
    ergebnis = fk.waehle_fokus(loest_aus)
    assert ergebnis is not None
    assert ergebnis['focus_key'] == 'negative_phrases'
    assert ergebnis['count'] == 4
    assert 'top reps cap it at 3' in ergebnis['satz']

    loest_nicht_aus = ['absolutely right.', 'absolutely fine.', 'that is perfect.']
    assert fk.waehle_fokus(loest_nicht_aus) is None


def test_leere_eingabe_liefert_none():
    """Leere/nur-Leerraum-Eingabe -> None, kein Fehler (der Nichts-Ausgang ist ein Weg)."""
    assert fk.waehle_fokus([]) is None
    assert fk.waehle_fokus(None) is None
    assert fk.waehle_fokus(['', '   ']) is None
