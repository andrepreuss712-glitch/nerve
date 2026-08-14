# -*- coding: utf-8 -*-
"""Gemeinsamer Transkript-Renderer fuer Bewerter-Auftrag und Zitat-Pruef-Korpus.

Herkunft: Phase 08.23.2.METRIK-1, Plan 01, Task 1 (D-04 / D-05 / D-06).

Dieses Modul ist eine REINE TRANSFORM-SCHICHT: kein DB-Zugriff, kein LLM-Aufruf, keine
Seiteneffekte. Es bekommt eine bereits geladene Segment-Liste und macht daraus Text.
(Bauform-Vorbild: services/handling_markers.py — Modul-Docstring mit Herkunft,
Konstanten als Modul-Konstanten, reine Funktionen.)

Warum EIN Renderer: Bewerter-Auftrag und Zitat-Pruef-Korpus muessen aus derselben
gefilterten Segment-Liste in derselben Reihenfolge entstehen. Zwei getrennte Renderings
erzeugen hausgemachte Beinahe-Treffer (SPEC NACHTRAG 2 Punkt 8).

Warum der Pruef-Korpus ohne Tag-Praefix gerendert wird: Der Praefix `[#1 berater 500ms]` ist
Prompt-Rahmen, kein gesprochener Text. Im Pruef-Korpus wuerde er den Token-Overlap-Nenner von
beleg_check (Score B, services/beleg_check.py:79-86) mit Rahmen-Woertern fuellen und damit
Halluzinate kuenstlich anheben. Gleich sind: Segment-Menge, Filter und Reihenfolge — genau die
drei Dinge, die D-05 schuetzt.

Warum der Filter am Text haengt und nicht an einem Flag: die EWB-Knopf-Pseudo-Zeile wird mit
dem dokumentierten Text-Suffix geschrieben (services/deepgram_service.py:1187-1191); das
RAM-Flag `data={'ewb_button': True}` ueberlebt den Persist NICHT. Die Schreib-Seite bleibt
unangetastet (D-03), gefiltert wird an genau ZWEI Lese-Stellen (D-04): hier (Bewerter-Auftrag)
und im Pruef-Korpus. Die Nutzer-Anzeige (routes/learning.py:628-637) bleibt ungefiltert.

Nummerierung: `#i` laeuft ueber die GEFILTERTE Liste — eine entfernte EWB-Zeile hinterlaesst
also KEINE Luecke in den Tags. Das ist gewollt (der Bewerter soll keine Leerstelle deuten).
"""

# Kanonischer Marker der EWB-Knopf-Pseudo-Zeile (services/deepgram_service.py:1187-1191).
# Der Wert ist uebernommen, nicht erfunden.
EWB_MARKER = '*ewb button*'


def _seg_text(seg) -> str:
    """Der Text eines Segments als String — nie None (Hilfsfunktion, eine Stelle fuer alle Leser)."""
    return getattr(seg, 'text', '') or ''


def ist_ewb_zeile(seg) -> bool:
    """True, wenn das Segment die EWB-Knopf-Pseudo-Zeile ist (Text-Suffix-Marker)."""
    return EWB_MARKER in _seg_text(seg)


def segmente_ohne_ewb(segments) -> list:
    """Die EWB-Knopf-Zeilen aus der Segment-Liste entfernen. Reihenfolge bleibt erhalten."""
    return [s for s in (segments or []) if not ist_ewb_zeile(s)]


def render_transkript(segments, *, mit_tags: bool = True) -> str:
    """Rendert die Segmente als Transkript-Block. EWB-Zeilen sind IMMER herausgefiltert.

    mit_tags=True  -> Bewerter-Auftrag: Kopfzeile + '[#i speaker ts_msms] text'
    mit_tags=False -> Zitat-Pruef-Korpus: nur die Segment-Texte, eine Zeile je Segment.

    Args:
        segments: Liste von TranscriptSegment-artigen Objekten (text/speaker/ts_ms), ts_ms ASC.
        mit_tags: Tag-Praefix und Kopfzeile mitrendern (Bewerter) oder nicht (Pruef-Korpus).

    Returns:
        str. Bei leerer Liste: mit_tags=True -> Kopfzeile + '(Keine Transkript-Segmente
        verfuegbar)'; mit_tags=False -> '' (leerer Korpus, beleg_check gibt dann fuer jedes
        Zitat 'no_match' zurueck — services/beleg_check.py:52-53).
    """
    gefiltert = segmente_ohne_ewb(segments)
    if not mit_tags:
        return '\n'.join(_seg_text(s) for s in gefiltert)
    lines = ['== TRANSKRIPT (chronologisch, ts_ms ASC) ==']
    if gefiltert:
        for i, seg in enumerate(gefiltert, start=1):
            speaker = getattr(seg, 'speaker', 'unbekannt')
            ts_ms = getattr(seg, 'ts_ms', 0)
            text = _seg_text(seg)
            lines.append(f'[#{i} {speaker} {ts_ms}ms] {text}')
    else:
        lines.append('(Keine Transkript-Segmente verfuegbar)')
    return '\n'.join(lines)


def pruef_fenster(segments) -> list:
    """Die Fenster, gegen die ein Beleg-Zitat geprueft wird — NICHT der Gesamt-Korpus.

    Jedes gefilterte Segment einzeln UND jedes Paar BENACHBARTER Segmente.

    WARUM NICHT der Gesamt-Korpus: beleg_check normalisiert Trennzeichen weg
    (services/beleg_check.py:18-19 — Satzzeichen werden zu Leerzeichen, Leerraum wird
    kollabiert) und bildet als Score B eine reine Wort-MENGE ohne Reihenfolge (:80-86, Endwert
    :89 ist max(score_a, score_b)). Gegen einen Gesamt-Korpus erreicht deshalb JEDES Zitat 1.0,
    dessen Woerter irgendwo vorkommen — auch eines, das Minute 2 und Minute 10 mischt. Ein
    blosses Trennzeichen loest das nicht: weder ein '|' noch ein Zeilenumbruch ueberlebt die
    Normalisierung.

    WARUM AUCH PAARE: die Spracherkennung trennt Aussagen mitten im Satz. Ein Zitat ueber genau
    eine solche Naht ist echt und muss stehenbleiben. Zwei weit auseinanderliegende Segmente
    sind nie benachbart.

    BENANNTE GRENZE: ein Zitat, dessen Woerter alle in EINEM Segment vorkommen, aber umgestellt
    sind, bleibt fuer Score B ein Treffer. Die Fenster loesen die Grenz-Ueberschreitung, nicht
    die Reihenfolge-Blindheit. Wer das schliessen will, muss an beleg_check.py — ausdruecklich
    nicht in dieser Phase.

    Returns:
        list[str]. Bei 0 Segmenten [], bei 1 Segment genau ein Fenster (kein Paar).
    """
    gefiltert = segmente_ohne_ewb(segments)
    fenster = [render_transkript([s], mit_tags=False) for s in gefiltert]
    fenster += [render_transkript(gefiltert[i:i + 2], mit_tags=False)
                for i in range(len(gefiltert) - 1)]
    return fenster
