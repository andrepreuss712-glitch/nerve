# -*- coding: utf-8 -*-
"""METRIK-1 Plan 04 — Fokus-Katalog v1: die EINE Sache fuers naechste Mal, vom CODE gewaehlt.

Quelle des Inhalts: Nerve-Vault/07 Referenz "US-Vertrieb — belegte Zahlen + Praktiker-Wissen
(2026-08-07)", ueber SPEC Requirement 7. DARAUS gebaut, nicht neu erfunden.

D-07/D-08: Der CODE prueft die vier Zaehlregeln, waehlt nach FESTER Rangfolge, zieht den
belegenden Satz DIREKT aus dem Transkript und setzt die gezaehlte Zahl in eine von vier festen
englischen Satz-Schablonen. KEIN Modell in der Auswahl, KEINES in der Formulierung, KEIN
zusaetzlicher KI-Aufruf. Daher gibt es in diesem Modul KEINEN Import einer KI-Bibliothek und
KEINEN Import des Bewerter-Dienstes — die Import-Liste unten ist die ganze Wahrheit.

WARUM DER CODE ZAEHLT UND NICHT DAS MODELL: Sprachmodelle zaehlen notorisch schlecht. Und das
erzwungene Antwort-Schema des Bewerters (services/judge_runner.py, forced tool_choice mit
Pflichtfeldern) MUSS einen Schluessel liefern — bei einem guten Anruf ohne Verstoss muesste das
Modell einen erfinden. Genau der Fehler, den die Abnahme suchen sollte, waere einprogrammiert.

D-10: Verletzt kein Kriterium, liefert waehle_fokus None — der Aufrufer zeigt dann ehrlich
"Nothing flagged this time.". Auf deutschem Bestand ist das der NORMALFALL, nicht die Ausnahme:
der Katalog ist englisch (D-11), alle bisherigen Anrufe sind deutsch. Niemals eine erfundene
Sache, niemals eine leere Stelle.

D-11: Alle nutzersichtbaren Texte sind ENGLISCH (erste Scheibe des US-Coaching-Gehirns). Die
SCHLUESSEL bleiben ASCII-Identifier (CLAUDE.md ASCII-Pflicht in Code-Identifiern).

VIER SCHABLONEN, FUENF SAETZE — damit niemand spaeter einen Verstoss daraus liest:
Die Negativ-Listen-Regel hat ZWEI Auspraegungen derselben Schablone — den Kappungs-Satz und den
Rabatt-Satz. Der Rabatt-Satz ist noetig, weil die Schwelle dort 1 ist und "cap it at 0" unsinnig
waere. Gezaehlt wird EINE Schablone je Fokus-Schluessel — also VIER Schablonen bei FUENF
moeglichen Saetzen. D-07 ("vier feste Satz-Schablonen") ist damit eingehalten.

BELEGT vs. GESETZT — bitte nicht verwechseln:
Belegt aus der US-Referenz sind allein die Schwellen der Negativ-Liste (4/4/4/6) und die
Effekt-Prozente. ICH_SCHWELLE und BUZZWORD_SCHWELLE sind VON UNS GESETZT, weil die Quelle dort
ein Verhaeltnis bzw. eine Quote nennt, keine Schwelle. Sie sind Kandidaten fuer die
Nachjustierung nach rund hundert echten Anrufen — dieselbe Nachjustierung wie beim Substanz-Tor.
Wer sie aendert, aendert eine GESETZTE Zahl, keine belegte.

NICHT ENTHALTEN und nicht nachtraeglich aufzunehmen:
  - Sorte B (vier Zeitmasse) — Vorbedingung sind die zwei Rechen-Korrekturen aus
    Roadmap-Punkt 4.0.2, der NACH dieser Phase laeuft.
  - Sorte C (Live-Symbol) — Roadmap-Punkt 4c.
  - STREICHLISTE, genauso verbindlich wie die Aufnahmeliste: Fuellwoerter (500.000 Gespraeche,
    null Zusammenhang) · Weichmacher (die vorsichtige Form ist die BESSERE Form) · Tonfall (aus
    Text nicht messbar) · Fragenanzahl ("zero statistical difference") · die Eroeffnungsfrage
    nach dem ungelegenen Zeitpunkt.

BENANNTE GRENZEN (Punkt-31-Haltung — dieses Modul behauptet nichts ueber eine Fehlerklasse im
Repo, seine fachlichen Grenzen gehoeren trotzdem hierher, weil Schweigen als Beweis gelesen wird):
  - Die Firmenname-Teilregel schlaegt in der Praxis selten an: das gespeicherte Transkript ist
    anonymisiert, ein erkannter Firmenname steht dort als Platzhalter-Token.
  - Der Sprach-Riegel ist eine Funktionswort-Heuristik, kein Spracherkenner. Ein deutscher Anruf
    mit vielen englischen Fachwoertern kann ihn passieren.
  - Die Zaehlung sieht nur das gerade Apostroph. Ein typografisches Apostroph im Transkript
    laesst die betroffene Phrase durchrutschen — Fehlerrichtung "zu wenig", nie "erfunden".

waehle_fokus ist eine REINE Funktion: kein DB-Zugriff, kein LLM, kein Seiteneffekt, bei gleicher
Eingabe deterministisch dasselbe Ergebnis.
"""

from __future__ import annotations

import re

# Der Marker der EWB-Knopf-Pseudo-Zeile kommt aus dem gemeinsamen Renderer (Plan 01) — EINE
# Quelle der Wahrheit statt einer zweiten Kopie des Strings.
# Warum hier nicht transkript_renderer.ist_ewb_zeile aufgerufen wird: diese Funktion erwartet
# SEGMENT-Objekte (sie liest das text-Attribut). Dieses Modul bekommt reine Zeichenketten; ein
# Aufruf auf einer Zeichenkette liefert per Bauart immer False und waere ein stiller Ausfall.
from services.transkript_renderer import EWB_MARKER


KATALOG_VERSION = 1

# Die vier Katalog-Punkte. DIESE REIHENFOLGE IST DIE RANGFOLGE (D-07: "waehlt unter den
# verletzten nach fester Rangfolge") — sortiert nach der Groesse des BELEGTEN Effekts:
# "we provide" -22 % ist der staerkste Einzelwert der Negativ-Liste, danach das we/I-Verhaeltnis
# (+35 %/+55 %), dann Problem-Sprache (16 % gg. 5,5 %), zuletzt der Anruf-Grund (2,1x, aber am
# schwaechsten maschinell fassbar).
FOKUS_SCHLUESSEL = (
    'negative_phrases',   # A4 — Gongs Negativ-Liste
    'we_not_i',           # A2 — we/our statt I/my
    'problem_language',   # A3 — Problem-Sprache statt Modewoerter
    'reason_for_call',    # A1 — Grund des Anrufs frueh nennen
)

# Gongs Negativ-Liste (519.000 Gespraeche): (phrase, schwelle, effekt_prozent).
# DIE SCHWELLEN SIND BELEGT, NICHT GESETZT. Die Reihenfolge ist die Rangfolge innerhalb der
# Regel — sortiert nach Effekt-Groesse.
NEGATIVE_PHRASES = (
    ('we provide',   4, -22),
    ('discount',     1, -17),   # ohne "ab N x" in der Quelle -> schon einmal zaehlt
    ('absolutely',   4, -16),
    ('perfect',      4, -16),
    ('show you how', 4, -13),
)

# Die Quelle beschreibt diese beiden als EINE Regel ("absolutely/perfect ab 4x"). FESTGELEGT:
# die beiden Zaehlungen werden ADDIERT, nicht getrennt gewertet — sonst kaeme ein Anruf mit
# 3x absolutely und 3x perfect (zusammen 6) durch, obwohl die Quelle das Verhalten als eines
# beschreibt.
ADDIERTE_PHRASEN = ('absolutely', 'perfect')

FIRMENNAME_SCHWELLE = 6      # -19 %, belegt

ICH_WOERTER = ('i', 'my', 'me', 'mine')
WIR_WOERTER = ('we', 'our', 'us', 'ours')

# ⚠ BELEGT vs. GESETZT — bitte nicht verwechseln. Belegt aus der US-Referenz sind allein die
# Schwellen der Negativ-Liste (4/4/4/6) und die Effekt-Prozente. ICH_SCHWELLE und
# BUZZWORD_SCHWELLE sind VON UNS GESETZT, weil die Quelle dort ein Verhaeltnis (+35 %/+55 %)
# bzw. eine Quote (16 % gg. 5,5 %) nennt, KEINE Schwelle. Beide sind Kandidaten fuer die
# Nachjustierung nach rund hundert echten Anrufen — dieselbe Nachjustierung wie beim
# Substanz-Tor. Wer sie aendert, aendert eine GESETZTE Zahl, keine belegte.
ICH_SCHWELLE = 4          # GESETZT, nicht belegt — siehe Kommentar darueber

BUZZWORDS = ('solution', 'solutions', 'synergy', 'synergies', 'cutting-edge',
             'innovative', 'world-class', 'best-in-class', 'leverage', 'seamless',
             'game-changer', 'disruptive', 'holistic', 'robust', 'scalable')
BUZZWORD_SCHWELLE = 3     # GESETZT, nicht belegt — siehe Kommentar darueber

REASON_PHRASES = ('the reason for my call', 'the reason i am calling',
                  "the reason i'm calling", 'the reason for the call',
                  'reason for my call')

# Bis zu welcher Position (0-basiert, exklusiv) der Anruf-Grund gefallen sein muss, damit die
# Regel NICHT anschlaegt. 2 = "in den ersten zwei Berater-Texten".
REASON_MAX_POSITION = 2

# Sprach-Riegel: Funktionswoerter, KEIN Spracherkenner. Nur reason_for_call braucht ihn.
ENGLISCH_ANKER = ('the', 'and', 'you', 'is', 'are', 'to', 'we', 'i', 'for', 'with')
ENGLISCH_MIN_TREFFER = 5


# ── Zaehl-Kern (D-09: Wortgrenzen statt Teilstring) ──────────────────────────────────────

def _normalize(text: str) -> str:
    """Kleinschreibung + kollabierte Whitespaces. Reine Hilfsfunktion (kein Seiteneffekt)."""
    return re.sub(r"\s+", " ", (text or '').strip().lower())


def _zaehle(phrase: str, norm: str) -> int:
    """Zaehlt VORKOMMEN einer Phrase mit Wortgrenzen — 'we' trifft NICHT in 'week'.

    (?<!\\w)...(?!\\w) statt \\b: robust auch fuer Phrasen, die mit einem Nicht-Wortzeichen
    beginnen oder enden (z.B. 'cutting-edge'), wo \\b an der falschen Stelle greift. Dieselbe
    Form benutzt der Ausgabe-Pfad der Anonymisierung.

    Gross/Kleinschreibung ist bereits durch _normalize erledigt (D-09).
    """
    if not phrase:
        return 0
    return len(re.findall(r'(?<!\w)' + re.escape(phrase) + r'(?!\w)', norm or ''))


def _ist_englisch(norm: str) -> bool:
    """Grobe Sprach-Weiche ueber Funktionswoerter — KEIN Spracherkenner, bewusst simpel.

    Nur die Regel reason_for_call braucht sie: sie ist die einzige Regel, die auf ABWESENHEIT
    prueft und wuerde auf jedem deutschen Anruf feuern. Auf einem deutschen Transkript ist das
    Kriterium nicht VERLETZT, sondern NICHT ANWENDBAR — der Unterschied ist der ganze Punkt.

    Die drei anderen Regeln brauchen den Riegel NICHT: sie zaehlen englische Woerter, kommen auf
    Deutsch also von selbst auf 0 (SPEC NACHTRAG 2 (1)).

    GRENZE, ehrlich benannt: ein deutscher Anruf mit vielen englischen Fachwoertern kann den
    Riegel passieren. Fehlerrichtung bewusst — er nennt dann eine zutreffende englische Regel.
    """
    return sum(1 for w in ENGLISCH_ANKER if _zaehle(w, norm) > 0) >= ENGLISCH_MIN_TREFFER


# ── Hilfsfunktionen fuer Beleg und Satz ──────────────────────────────────────────────────

def _erster_beleg(phrase: str, texte: list) -> str:
    """Der ERSTE uebergebene Text, in dem die Phrase vorkommt — woertlich, unveraendert.

    Rueckfall auf den ersten Text, falls die Phrase nur ueber eine Text-Grenze hinweg zustande
    kam (die Gesamt-Zaehlung arbeitet auf dem zusammengefuegten Text). Der Beleg ist damit in
    JEDEM Fall einer der uebergebenen Texte — das ist die Zusage aus D-07 ("per Bauart echt").
    """
    for text in texte:
        if _zaehle(phrase, _normalize(text)) > 0:
            return text
    return texte[0]


def _satz_negativ(phrase: str, count: int, schwelle: int) -> str:
    """Schablone 1 (Kappung) bzw. ihre Sonderform Schablone 2 (Rabatt).

    Bei einer Schwelle von 1 waere "cap it at 0" unsinnig — deshalb die Sonderform. Sie haengt
    an der SCHWELLE, nicht am Wort, damit eine kuenftige Schwelle-1-Phrase nicht stillschweigend
    den unsinnigen Satz bekommt.
    """
    if schwelle <= 1:
        return f'You said "{phrase}" {count} times — top reps let the price stand instead.'
    return f'You said "{phrase}" {count} times — top reps cap it at {schwelle - 1}.'


def _ergebnis(focus_key: str, count: int, limit, satz: str, beleg: str) -> dict:
    """Baut das Rueckgabe-Dict. Eine Stelle fuer alle vier Regeln (kein Drift im Schluessel-Satz)."""
    return {
        'focus_key': focus_key,
        'count': count,
        'limit': limit,
        'satz': satz,
        'beleg': beleg,
        'katalog_version': KATALOG_VERSION,
    }


# ── Die Auswahl ──────────────────────────────────────────────────────────────────────────

def waehle_fokus(berater_texte, *, firmenname=None) -> dict | None:
    """Waehlt die EINE Sache fuers naechste Mal — vom Code, nicht vom Modell (D-07).

    Args:
        berater_texte: Liste der Segment-TEXTE des BERATERS, in Sprech-Reihenfolge.
            Der Aufrufer filtert auf speaker == 'berater' und auf die EWB-Knopf-Zeilen
            (services/transkript_renderer.segmente_ohne_ewb). Dieses Modul filtert die
            EWB-Zeilen SICHERHEITSHALBER ein zweites Mal — ein Knopfdruck ist kein Satz, und
            ein vergessener Filter im Aufrufer darf hier keine Zaehlung erzeugen.
        firmenname: Der eigene Firmenname des Beraters, oder None.
            ⚠ BEKANNTE GRENZE: das gespeicherte Transkript ist anonymisiert; ein erkannter
            Firmenname steht dort als Platzhalter-Token. Diese Teilregel schlaegt deshalb in der
            Praxis selten an. Sie bleibt trotzdem drin (belegter Effekt -19 %) und ist bei
            durchgerutschten Nennungen wirksam.

    Returns:
        None  -> kein Kriterium verletzt (D-10, NORMALFALL). Der Aufrufer zeigt dann
                 "Nothing flagged this time." — niemals eine erfundene Sache, niemals leer.
        dict  -> {'focus_key': str, 'count': int, 'limit': int|None, 'satz': str,
                  'beleg': str, 'katalog_version': int}
                 'beleg' ist WOERTLICH einer der uebergebenen Texte — per Bauart aus dem
                 Transkript gezogen, nicht geprueft (D-07).

    Deterministisch: gleiche Eingabe -> gleiches Ergebnis. Keine Zufallsquelle, keine Zeit,
    kein Modell.
    """
    # 1) Texte saeubern: EWB-Knopf-Zeilen raus, leere raus.
    texte = [str(t) for t in (berater_texte or [])
             if t and str(t).strip() and EWB_MARKER not in str(t).lower()]
    if not texte:
        return None

    # 2) Ein Gesamt-Text fuer die Zaehlungen; die Beleg-Suche laeuft je Text.
    norm_gesamt = _normalize(' '.join(texte))

    # 3) negative_phrases — Rangfolge 1 (staerkster belegter Einzeleffekt).
    erledigt = set()
    for phrase, schwelle, _effekt in NEGATIVE_PHRASES:
        if phrase in erledigt:
            continue
        if phrase in ADDIERTE_PHRASEN:
            erledigt.update(ADDIERTE_PHRASEN)
            einzeln = [(p, _zaehle(p, norm_gesamt)) for p in ADDIERTE_PHRASEN]
            count = sum(c for _p, c in einzeln)
            # Deterministisch: bei Gleichstand gewinnt der in ADDIERTE_PHRASEN zuerst
            # stehende Eintrag (max liefert den ERSTEN groessten Wert).
            treffer = max(einzeln, key=lambda pc: pc[1])[0]
        else:
            count = _zaehle(phrase, norm_gesamt)
            treffer = phrase
        if count >= schwelle:
            return _ergebnis('negative_phrases', count, schwelle,
                             _satz_negativ(treffer, count, schwelle),
                             _erster_beleg(treffer, texte))

    # 3b) Der eigene Firmenname (ab 6x, -19 %) — Teil derselben Regel, deshalb hier.
    if firmenname and str(firmenname).strip():
        name = _normalize(str(firmenname))
        n_name = _zaehle(name, norm_gesamt)
        if n_name >= FIRMENNAME_SCHWELLE:
            return _ergebnis('negative_phrases', n_name, FIRMENNAME_SCHWELLE,
                             _satz_negativ(str(firmenname).strip(), n_name, FIRMENNAME_SCHWELLE),
                             _erster_beleg(name, texte))

    # 4) we_not_i — Rangfolge 2 (+35 % / +55 %).
    ich = sum(_zaehle(w, norm_gesamt) for w in ICH_WOERTER)
    wir = sum(_zaehle(w, norm_gesamt) for w in WIR_WOERTER)
    if ich >= ICH_SCHWELLE and ich > wir:
        beleg = texte[0]
        for text in texte:
            norm_text = _normalize(text)
            if any(_zaehle(w, norm_text) > 0 for w in ICH_WOERTER):
                beleg = text
                break
        satz = (f'You said "I" or "my" {ich} times and "we" or "our" {wir} times '
                f'— top reps flip that ratio.')
        return _ergebnis('we_not_i', ich, ICH_SCHWELLE, satz, beleg)

    # 5) problem_language — Rangfolge 3 (16 % gg. 5,5 %).
    treffer_liste = [(w, _zaehle(w, norm_gesamt)) for w in BUZZWORDS]
    n_buzz = sum(c for _w, c in treffer_liste)
    if n_buzz >= BUZZWORD_SCHWELLE:
        # Haeufigstes Buzzword; bei Gleichstand gewinnt das in BUZZWORDS zuerst stehende
        # (max liefert den ERSTEN groessten Wert) — deterministisch, ausdruecklich so gewollt.
        wort = max(treffer_liste, key=lambda wc: wc[1])[0]
        satz = (f'You used buzzwords {n_buzz} times, "{wort}" most often '
                f'— top reps name the problem instead.')
        return _ergebnis('problem_language', n_buzz, BUZZWORD_SCHWELLE, satz,
                         _erster_beleg(wort, texte))

    # 6) reason_for_call — Rangfolge 4 (2,1x). Die EINZIGE Regel, die auf ABWESENHEIT prueft,
    #    und deshalb die einzige mit Sprach-Riegel.
    if _ist_englisch(norm_gesamt):
        position = None
        for i, text in enumerate(texte):
            norm_text = _normalize(text)
            if any(_zaehle(p, norm_text) > 0 for p in REASON_PHRASES):
                position = i
                break
        if position is None or position >= REASON_MAX_POSITION:
            n_vorher = len(texte) if position is None else position
            satz = (f'You spoke {n_vorher} times before naming the reason for your call '
                    f'— top reps name it in the first line.')
            return _ergebnis('reason_for_call', n_vorher, REASON_MAX_POSITION, satz, texte[0])

    # 7) Nichts verletzt — der ehrliche Nichts-Ausgang (D-10, NORMALFALL).
    return None
