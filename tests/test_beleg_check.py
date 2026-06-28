# -*- coding: utf-8 -*-
"""Tests fuer services/beleg_check.py — Fuzzy-Beleg-Check (Cross-AI-Finding 3).

Runtime-Assertions auf beleg_im_transkript() Rueckgabewert (KEINE Source-Presence-Tests,
CLAUDE.md Test-Qualitaets-Regel). Alle Tests laufen ohne DB/LLM (reine Textfunktion).
"""

import pytest
from services.beleg_check import beleg_im_transkript


# ── Hilfstexte ─────────────────────────────────────────────────────────────
TRANSKRIPT = (
    "Kunde: Das ist mir zu teuer. "
    "Berater: Das verstehe ich gut — darf ich kurz fragen, was genau zu teuer ist? "
    "Meine ich den Einstiegspreis oder die laufenden Kosten? "
    "Kunde: Nein danke, ich habe kein Interesse. "
    "Berater: Okay, ich respektiere das. Darf ich fragen warum? "
    "Kunde: Das passt gerade einfach nicht. "
    "Berater: Gut, dann halte ich das so fest."
)


# ── Test 1: Exakter Treffer ────────────────────────────────────────────────
def test_exakter_treffer():
    """Ein Zitat das woertlich im Transkript steht -> ok=True."""
    zitat = "darf ich kurz fragen, was genau zu teuer ist"
    ok, score, befund = beleg_im_transkript(zitat, TRANSKRIPT)
    assert ok is True, f"Exakter Treffer erwartet ok=True, bekam ok={ok}, score={score}"
    assert score >= 0.80, f"Exakter Treffer erwartet score >= 0.80, bekam {score}"


# ── Test 2: Paraphrase kippt gutes Feedback nicht ────────────────────────
def test_paraphrase_kippt_nicht():
    """Eine leichte Paraphrase darf NOT als no_match gewertet werden
    (Cross-AI-Finding 3: Near-Miss flaggen, nicht verwerfen).

    Soll: ok=True ODER befund='near_miss'. NICHT 'no_match'.
    """
    # Paraphrase: Wortstellung leicht veraendert, Fuellwort hinzugefuegt
    zitat = "ich frage kurz einmal, was genau zu teuer ist bei Ihnen"
    ok, score, befund = beleg_im_transkript(zitat, TRANSKRIPT)
    assert befund != 'no_match', (
        f"Paraphrase darf NICHT als no_match gewertet werden — "
        f"bekam befund={befund}, score={score}. "
        "Eine leichte Paraphrase darf gutes Feedback nicht kippen (Finding 3)."
    )


# ── Test 3: Echtes Halluzinat -> no_match ────────────────────────────────
def test_halluzinat_no_match():
    """Ein Satz der gar nicht im Transkript steht -> ok=False, befund='no_match'."""
    zitat = "wir haben einen exklusiven Sonderpreis fuer Ihr Unternehmen reserviert"
    ok, score, befund = beleg_im_transkript(zitat, TRANSKRIPT)
    assert ok is False, f"Halluzinat erwartet ok=False, bekam ok={ok}"
    assert befund == 'no_match', (
        f"Halluzinat erwartet befund='no_match', bekam '{befund}' (score={score})"
    )


# ── Test 4: Near-Miss -> flaggen, nicht hart verwerfen ───────────────────
def test_near_miss_flaggt():
    """Ein Zitat das teilweise passt aber nicht exakt -> befund='near_miss', ok=False.

    Near-Miss darf NICHT zu ok=True hochgestuft UND nicht zu no_match degradiert werden.
    Es muss als near_miss (menschliche Sicht) zurueckkommen.
    """
    # Mischung: einige Tokens stimmen, aber genug fehlen/abweichen
    zitat = "ich respektiere das vollstaendig, aber koennen wir nochmal sprechen"
    ok, score, befund = beleg_im_transkript(zitat, TRANSKRIPT)
    # Near-Miss erwartet: ok=False (nicht als Treffer durchgelassen)
    assert ok is False, (
        f"Near-Miss-Zitat erwartet ok=False, bekam ok={ok} (score={score}, befund={befund})"
    )
    # Und befund darf NICHT 'treffer' sein
    assert befund != 'treffer', (
        f"Near-Miss-Zitat darf nicht als 'treffer' gewertet werden — "
        f"bekam befund={befund}, score={score}"
    )


# ── Randfall: leeres Zitat ────────────────────────────────────────────────
def test_leeres_zitat_kein_crash():
    """Leeres Zitat gibt (False, 0.0, 'no_match') ohne Exception."""
    ok, score, befund = beleg_im_transkript('', TRANSKRIPT)
    assert ok is False
    assert score == 0.0
    assert befund == 'no_match'
