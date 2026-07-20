"""Phase 08.23.2.KOSTEN-1 R3.1 — beide Live-STT-Pfade fahren dasselbe Modell.

ANLASS: `nerve_rt` fuhr `nova-2`, die Haupt-App `nova-3` — unbemerkt auseinandergelaufen,
weil die beiden Pfade in verschiedenen Prozessen leben und niemand sie nebeneinander liest.
Das ist teuer UND falsch: verschiedene Modelle heissen verschiedene Preise und verschiedene
Erkennungsqualitaet, und der Kosten-Log haette ein Modell behauptet, das gar nicht lief.
Andre-Direktive beim Freigeben von Weg A: "irgendwo wo wir definitiv drueberstolpern" —
das hier ist die Stolperstelle, und sie blockiert den Deploy.

BEWUSST AUSGENOMMEN: der Training-Prerecorded-Pfad (`routes/training.py`, nova-2-prerecorded).
Der hat einen anderen Zweck (Batch statt Live) und einen anderen Preis — dort ist eine
Abweichung KEIN Drift, sondern Absicht.

Reiner Text-Sweep, kein Import der Module (nerve_rt zieht sonst deepgram/fastapi-Abhaengigkeiten
in den Test-Prozess). Kein DB-Zugriff, keine Writes.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# (Pfad, Regex mit genau einer Gruppe = der Modell-String an der LiveOptions-Stelle)
# Gemeint ist AUSSCHLIESSLICH der Modell-Parameter der LiveOptions — deshalb zeilen-verankert.
# Ohne den Anker faengt `model\s*=` auch `_dg_model = 'nova-3-diarize'` aus dem Kosten-Hook,
# und der Test verglich dann Kosten-Strings statt der tatsaechlich gefahrenen Modelle.
LIVE_STT_PFADE = (
    ('services/deepgram_service.py', r'^\s*model\s*=\s*["\']([a-z0-9\-]+)["\']\s*,\s*$'),
    ('nerve_rt/services/stt/deepgram_adapter.py', r'^\s*"model"\s*:\s*"([a-z0-9\-]+)"\s*,\s*$'),
)


def _modelle(datei: str, muster: str) -> list[str]:
    src = (REPO_ROOT / datei).read_text(encoding='utf-8')
    # Nur Treffer, die wie ein Deepgram-Modell aussehen — `model=config.X` und die
    # Anthropic-Aufrufe derselben Datei sollen hier nicht mitzaehlen.
    return [m for m in re.findall(muster, src, re.MULTILINE) if m.startswith('nova')]


def test_beide_live_stt_pfade_fahren_dasselbe_modell():
    gefunden = {}
    for datei, muster in LIVE_STT_PFADE:
        treffer = set(_modelle(datei, muster))
        assert treffer, (
            f"In {datei} wurde GAR KEIN nova-Modell gefunden. Das ist selbst ein Befund: "
            f"entweder ist der Sweep kaputt (Muster passt nicht mehr) oder der STT-Aufruf ist "
            f"umgezogen. In beiden Faellen wacht dieser Test gerade ueber nichts."
        )
        gefunden[datei] = treffer

    alle = set().union(*gefunden.values())
    assert len(alle) == 1, (
        "Die beiden Live-STT-Pfade fahren VERSCHIEDENE Deepgram-Modelle — verschiedene Preise, "
        "verschiedene Qualitaet, und der Kosten-Log behauptet eines von beiden:\n  "
        + "\n  ".join(f"{d}: {sorted(m)}" for d, m in gefunden.items())
        + "\n\nFix: beide auf dasselbe Modell ziehen (KOSTEN-1 R3.1 hat nerve_rt auf nova-3 "
          "gehoben). Wenn die Abweichung ABSICHT ist, gehoert sie hier begruendet eingetragen — "
          "nicht stillschweigend."
    )
