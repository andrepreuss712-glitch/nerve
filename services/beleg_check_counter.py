# -*- coding: utf-8 -*-
"""METRIK-1 Plan 01 Task 3 — Prozess-Zaehler der Beleg-Zitat-Pruefung (Anzeige-Schicht).

Der DAUERHAFTE Ort des Zaehlers ist rubric_score.payload_jsonb['beleg_check'] (D-23,
geschrieben in services/slow_lane.py::_judge_step). Dieses Modul ist NUR die Founder-Anzeige.

WARUM NICHT ueber die Tabelle aggregiert: rubric_score steht unter FORCE ROW LEVEL SECURITY.
Eine mandanten-uebergreifende Founder-Abfrage liefert als nerve_app STILL 0 Zeilen statt eines
Fehlers — eine leere Kachel waere von "keine Verwuerfe" nicht zu unterscheiden. Muster und
Grenze sind wortgleich zu services/cost_tracker.py::get_skip_counts.

BEWUSSTE GRENZE: RAM, pro Prozess (Gunicorn-Worker), seit Deploy. Ein Neustart setzt auf 0.
Der Zaehler ist tenant-NEUTRAL (nur Summen, keine call_id, keine tenant_id, kein Text) — damit
faellt er nicht unter Punkt 28 (kein globaler Zustand fuer pro-Nutzer-Daten).

SEMANTIK-UNTERSCHIED (bewusst, beide Formen stehen nebeneinander): der DB-Wert je Anruf ist ein
ABSOLUTWERT des Laufs (UPSERT ersetzt, D-23); dieser Prozess-Zaehler SUMMIERT ueber alle Laeufe
seit Deploy.
"""

import threading

_SCHLUESSEL = ('geprueft', 'treffer', 'near_miss', 'verworfen', 'compliance_beleg_verworfen')

# Modul-Summen. Tenant-NEUTRAL (nur Zahlen) — bewusste Ausnahme zu Punkt 28, siehe Docstring.
_lock = threading.Lock()
_counts = {k: 0 for k in _SCHLUESSEL}


def record_beleg_check(zaehler: dict) -> None:
    """Addiert einen Lauf-Zaehler auf die Modul-Summen.

    Fehlertolerant (try/except, raist NIE): ein Anzeige-Zaehler darf die Nachbearbeitung
    niemals kippen.
    """
    try:
        if not isinstance(zaehler, dict):
            return
        with _lock:
            for k in _SCHLUESSEL:
                wert = zaehler.get(k, 0)
                if isinstance(wert, bool) or not isinstance(wert, int):
                    continue
                _counts[k] += wert
    except Exception as e:  # noqa: BLE001 — Anzeige-Zaehler darf nie den Aufrufer kippen
        print(f"[BelegCheckCounter] record skipped: {e}")


def get_beleg_check_counts() -> dict:
    """Die Modul-Summen seit Prozess-Start (Founder-Anzeige)."""
    with _lock:
        return dict(_counts)


def reset_beleg_check_counts() -> None:
    """Setzt die Modul-Summen zurueck — NUR fuer Tests."""
    with _lock:
        for k in _SCHLUESSEL:
            _counts[k] = 0
