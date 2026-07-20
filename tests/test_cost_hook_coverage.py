"""Phase 08.23.2.KOSTEN-1 Welle 2 — W2 Hook-Coverage-Waechter (grep, ERST-ROT).

WOFUER: eine bezahlte API aufrufen und **vergessen, die Kosten zu buchen**, ist genauso teuer wie
eine fehlende Rate — nur noch unsichtbarer, weil nicht mal ein Skip-Hinweis entsteht. Beim Audit
2026-07-19 liefen acht bezahlte Call-Sites voellig ungebucht (darunter zwei Sonnet-Laeufe PRO CALL).

WAS DIESER WAECHTER TUT: er sucht im Produktiv-Code nach Aufruf-Mustern bezahlter Dienste und
verlangt, dass in **derselben Datei** mindestens ein `log_api_cost` steht — oder dass die Datei auf
der expliziten, **kommentierten** Allowlist unten steht.

BEWUSSTE GRENZEN (Fable/Gemini, verbindlich — NICHT "verbessern"):
- **Datei-Granularitaet ist ABSICHT, kein Kompromiss.** Funktions-genaues AST-Matching waere der
  Stolperdraht-Verstoss aus dem Bauplan. Eine Datei, die einen bezahlten Dienst ruft und irgendwo
  eine Kosten-Buchung hat, gilt als versorgt — den Feinschliff macht das Code-Review, nicht der Test.
- **ENV-/config-basierte Modellnamen faengt dieser Waechter NICHT** (er sieht nur Aufruf-Muster,
  nicht Namens-Aufloesung). Das ist W3s Aufgabe (`tests/test_cost_skip_counter.py`, Laufzeit).
- **Jeder Allowlist-Eintrag braucht einen Grund im Kommentar.** Ein unkommentierter Eintrag ist
  selbst ein Fehler — sonst wird die Allowlist die Hintertuer, die den Waechter aushoehlt.

Dieser Test ist ERST-ROT gebaut: gegen den Stand vor R2/R3 meldet er judge_runner, adoption_runner,
outcome_service, routes/training.py, coaching_service, precall_service, routes/payments.py und die
beiden nerve_rt-Adapter.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCAN_DIRS = ('services', 'routes', 'nerve_rt')

# Aufruf-Muster bezahlter Dienste. Wer eines davon nutzt, gibt Geld aus.
PAID_CALL_PATTERNS = (
    r'messages\.create',        # Anthropic (Claude)
    r'messages\.stream',        # Anthropic (Streaming)
    r'DeepgramClient',          # Deepgram (prerecorded)
    r'transcribe_file',         # Deepgram (prerecorded)
    r'_open_deepgram',          # Deepgram (live)
    r'api\.elevenlabs\.io',     # ElevenLabs (TTS)
    r'api\.search\.brave\.com',  # Brave (Websuche)
)
_PAID_RE = re.compile('|'.join(PAID_CALL_PATTERNS))
_HOOK_RE = re.compile(r'log_api_cost\s*\(')

# ── Allowlist — Datei -> GRUND. Ohne Grund kein Eintrag (siehe Docstring). ──────────────────
ALLOWLIST: dict[str, str] = {
    # Beispiel-Form (aktuell leer): 'scripts/tts_comparison.py':
    #     'Dev-Vergleichsskript, laeuft nie im Produktivbetrieb — keine Kundenkosten.'
}


def _relpath(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _paid_files_without_hook() -> list[str]:
    offenders: list[str] = []
    for rel in SCAN_DIRS:
        base = REPO_ROOT / rel
        if not base.is_dir():
            continue
        for path in sorted(base.rglob('*.py')):
            try:
                src = path.read_text(encoding='utf-8')
            except OSError:  # pragma: no cover - defensiv
                continue
            if not _PAID_RE.search(src):
                continue
            if _HOOK_RE.search(src):
                continue
            if _relpath(path) in ALLOWLIST:
                continue
            offenders.append(_relpath(path))
    return offenders


def test_every_paid_call_site_books_its_cost():
    """Jede Datei, die eine bezahlte API ruft, muss ihre Kosten buchen (oder begruendet befreit sein)."""
    offenders = _paid_files_without_hook()
    assert not offenders, (
        "Diese Dateien rufen eine BEZAHLTE API, buchen aber keine Kosten "
        "(kein log_api_cost, kein begruendeter Allowlist-Eintrag):\n  "
        + "\n  ".join(offenders)
        + "\n\nFix: Kosten-Hook nach dem Muster claude_service.py:542-568 ergaenzen (KOSTEN-1 R2/R3) "
          "— KEIN Wrapper-Framework um den Client."
    )


def test_allowlist_entries_are_justified():
    """Ein Allowlist-Eintrag ohne Begruendung waere die Hintertuer, die den Waechter aushoehlt."""
    unjustified = [f for f, reason in ALLOWLIST.items() if len((reason or '').strip()) < 20]
    assert not unjustified, (
        "Allowlist-Eintraege ohne belastbare Begruendung: " + ', '.join(unjustified)
    )


def test_allowlist_has_no_dead_entries():
    """Eine Allowlist, die auf verschwundene Dateien zeigt, taeuscht Abdeckung vor."""
    dead = [f for f in ALLOWLIST if not (REPO_ROOT / f).exists()]
    assert not dead, (
        "Allowlist zeigt auf nicht mehr existierende Dateien (bitte entfernen): " + ', '.join(dead)
    )
