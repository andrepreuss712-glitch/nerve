#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Einmal-Skript: traegt `anker:` in die Kopfzeilen von 03 Planung/ ein.

Sicherheits-Ablauf nach CLAUDE.md ("nie direkt in eine bestehende Datei
schreiben"): kompletten neuen Inhalt im Speicher bauen und pruefen ->
Nebendatei schreiben -> erst dann umbenennen. Scheitert etwas davor, ist
das Original unangetastet.

Laeuft idempotent: eine bereits vorhandene `anker:`-Zeile wird ersetzt,
nicht verdoppelt.
"""
import io
import json
import os
import sys

VAULT = r"C:\Users\andre\OneDrive\Desktop\Nerve-Vault"
ORDNER = os.path.join(VAULT, "03 Planung")
KARTE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "..", ".planning", "anker_zuordnung.json")
TROCKEN = "--schreiben" not in sys.argv


def main():
    with io.open(KARTE, encoding="utf-8") as f:
        karte = json.load(f)

    vorhanden = {d for d in os.listdir(ORDNER) if d.endswith(".md")}
    fehlt_in_karte = sorted(vorhanden - set(karte))
    fehlt_auf_platte = sorted(set(karte) - vorhanden)
    if fehlt_in_karte or fehlt_auf_platte:
        print("ABBRUCH - Karte und Bestand stimmen nicht ueberein:")
        for d in fehlt_in_karte:
            print("   nicht in der Karte :", d)
        for d in fehlt_auf_platte:
            print("   nicht auf Platte   :", d)
        return 1

    getan, uebersprungen = 0, 0
    for name, anker in sorted(karte.items()):
        pfad = os.path.join(ORDNER, name)
        text = io.open(pfad, encoding="utf-8").read()

        if not text.startswith("---"):
            print("UEBERSPRUNGEN (keine Kopfzeile):", name)
            uebersprungen += 1
            continue
        ende = text.find("\n---", 3)
        if ende == -1:
            print("UEBERSPRUNGEN (Kopfzeile nicht geschlossen):", name)
            uebersprungen += 1
            continue

        kopf = text[3:ende].split("\n")
        neu, gesetzt = [], False
        for z in kopf:
            if z.strip().startswith("anker:"):
                neu.append(f"anker: {anker}")
                gesetzt = True
            else:
                neu.append(z)
        if not gesetzt:
            # direkt hinter `status:` einsetzen, sonst ans Ende der Kopfzeile
            ziel = next((i for i, z in enumerate(neu)
                         if z.strip().startswith("status:")), len(neu) - 1)
            neu.insert(ziel + 1, f"anker: {anker}")

        neuer_text = "---" + "\n".join(neu) + text[ende:]

        # Pruefung VOR dem Schreiben: Kopfzeile noch heil, Anker genau einmal drin
        if neuer_text.count("\nanker:") != 1 or not neuer_text.startswith("---"):
            print("ABBRUCH - Ergebnis waere kaputt:", name)
            return 1
        if len(neuer_text) < len(text):
            print("ABBRUCH - Ergebnis kuerzer als das Original:", name)
            return 1

        if TROCKEN:
            print(f"WUERDE SETZEN  anker: {anker:<62} {name[:44]}")
        else:
            tmp = pfad + ".tmp"
            with io.open(tmp, "w", encoding="utf-8", newline="") as f:
                f.write(neuer_text)
            os.replace(tmp, pfad)
            print(f"GESETZT  anker: {anker:<62} {name[:44]}")
        getan += 1

    print(f"\n{'TROCKENLAUF' if TROCKEN else 'GESCHRIEBEN'}: {getan} Datei(en), "
          f"{uebersprungen} uebersprungen.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
