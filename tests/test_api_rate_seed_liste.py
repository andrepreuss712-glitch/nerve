"""Phase 08.23.2.KOSTEN-1 R1b — Invarianten der EINEN Rate-Seed-Liste (`app._API_RATE_SOLL`).

HERKUNFT (Stale-Test-Retarget, Punkt 18 / AUTH-2-Lehre):
Diese Datei hiess `test_08_14_apirate_seed.py` und spiegelte den Phase-08.14-Seed als **Kopie**:
sie baute eine eigene `SEED_ROWS`-Liste, schrieb sie mit eigenem Raw-SQL in eine in-memory-SQLite
und pruefte danach ihre eigenen Zeilen. Damit haette sie auch dann gruen gemeldet, wenn der echte
Seed geloescht wird — was in KOSTEN-1 R1b genau passiert ist (der 08.14-Block lag in `_migrate()`
und war auf Postgres ohnehin tot, siehe app.py-Kommentar an der Fundstelle). Ein Test, der eine
Vertrags-Aenderung nicht bemerkt, prueft nichts mehr; deshalb ist er hier auf den **neuen** Vertrag
retargetet statt geloescht oder gruengemacht zu werden.

WAS HIER GEPRUEFT WIRD: die Liste selbst, denn sie ist ab R1b die einzige Quelle der Preise.
Ihre Struktur-Fehler sind genau die, die im Betrieb still weh tun:
  * ein doppeltes Tripel -> `uix_api_rate_active` laesst nur eines aktiv werden, das zweite
    kollidiert beim Seed und wird uebersprungen (Preis bleibt still der falsche).
  * ein Preis <= 0 -> der Call wird zwar geloggt, aber mit 0 Kosten (unsichtbar wie ein Skip).
  * Waehrungs-/Tippfehler -> `api_rates.currency` ist VARCHAR(3).
Der Abgleich "wird jedes geloggte Tripel wirklich bepreist?" gehoert NICHT hierher — den macht
`tests/test_api_rate_coverage.py` gegen die echte, geseedete Postgres-Tabelle (real-PG).

Kein DB-Zugriff, keine Writes -> nichts aufzuraeumen (PGTEST-Cleanup-Regel n/a).
"""
from __future__ import annotations

from collections import Counter
from decimal import Decimal


def _soll():
    """Import erst im Test: `app` bootet beim Import die Flask-App (Seeder inklusive)."""
    from app import _API_RATE_SOLL
    return _API_RATE_SOLL


def test_liste_ist_nicht_leer():
    """Eine leere Liste wuerde jeden Coverage-Check trivial gruen machen."""
    assert len(_soll()) >= 20, (
        "Die Rate-Soll-Liste ist verdaechtig kurz — nach R1 stehen dort alle Anthropic-Token-"
        "Einheiten, die Deepgram-Minuten-Varianten und die uebrigen Provider."
    )


def test_keine_doppelten_tripel():
    """(provider, model, unit_type) muss eindeutig sein — sonst kollidiert der Seed am UNIQUE.

    uix_api_rate_active = UNIQUE(provider, model, unit_type, active): ein zweites Vorkommen
    desselben Tripels kann nicht zusaetzlich aktiv werden. Der Seed faengt den IntegrityError ab
    und macht weiter — der Preis der zweiten Zeile landet also NIE in der DB, ohne dass etwas
    rot wird. Genau diese Stille faengt dieser Test frueher ab.
    """
    tripel = [(p, m, u) for p, m, u, _price, _cur in _soll()]
    doppelt = [t for t, n in Counter(tripel).items() if n > 1]
    assert not doppelt, (
        "Doppelte Tripel in _API_RATE_SOLL — nur das erste wird geseedet:\n  "
        + "\n  ".join(f"{p}/{m}/{u}" for p, m, u in sorted(doppelt))
    )


def test_alle_preise_positiv():
    """Ein 0-Preis loggt 0 Kosten — das ist so unsichtbar wie ein fehlender Eintrag.

    Anlass: Brave stand zur Diskussion, mit 0.0 angelegt zu werden, weil es mal einen Free-Tier
    gab. Der ist seit 02/2026 weg (Andre-Entscheid 2026-07-20) — ein 0-Preis waere ein zweites
    stilles Loch gewesen, nur eines, das der Coverage-Waechter gruen meldet.
    """
    null_preise = [(p, m, u) for p, m, u, price, _cur in _soll() if Decimal(str(price)) <= 0]
    assert not null_preise, (
        "Preis <= 0 in _API_RATE_SOLL (loggt 0 Kosten statt echter):\n  "
        + "\n  ".join(f"{p}/{m}/{u}" for p, m, u in null_preise)
    )


def test_waehrungen_sind_dreistellige_codes():
    """`api_rates.currency` ist VARCHAR(3); alles andere wird beim Insert stumpf abgeschnitten."""
    falsch = [(p, m, u, cur) for p, m, u, _price, cur in _soll()
              if not (isinstance(cur, str) and len(cur) == 3 and cur.isupper())]
    assert not falsch, f"Unzulaessige Waehrungs-Codes: {falsch}"


def test_deepgram_diarize_variante_ist_teurer_als_basis():
    """Diarization ist ein Add-on (+$0.0020/min), keine Alternative zum Basis-Preis.

    Waere die `-diarize`-Zeile versehentlich gleich teuer oder billiger als die Basis-Zeile,
    haette die Modus-Aufteilung aus `deepgram_service.py:497` keinen Zweck mehr — Meetings
    wuerden wieder zu billig gerechnet, und zwar unauffaellig.
    """
    preise = {(p, m): Decimal(str(price)) for p, m, u, price, _cur in _soll() if u == 'per_minute'}
    for basis in ('nova-3', 'nova-2'):
        variante = f'{basis}-diarize'
        assert ('deepgram', basis) in preise, f"deepgram/{basis}/per_minute fehlt in der Soll-Liste"
        assert ('deepgram', variante) in preise, f"deepgram/{variante}/per_minute fehlt in der Soll-Liste"
        assert preise[('deepgram', variante)] > preise[('deepgram', basis)], (
            f"deepgram/{variante} ist nicht teurer als /{basis} — der Diarization-Aufpreis fehlt."
        )
