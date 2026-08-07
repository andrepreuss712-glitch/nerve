#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VAULT-WAECHTER — laeuft bei jedem Claudian-Sitzungsstart.

WARUM ES DAS GIBT (Vault-Audit 2026-08-01):
Das Vault hatte kein "Erledigt". 46 von 50 Planungs-Dateien standen auf
"aktiv" — auch laengst gebaute. Die Regeln dagegen EXISTIERTEN alle:
Status-Pflicht, Roadmap-Pflege, Log-Pflicht. Gehalten hat keine davon.
Belegte Ausfaelle: die Roadmap-Orientierung stand 3 Monate veraltet ganz
oben; der 31.07. fehlte komplett im Log — beides fiel niemandem auf.

Der Code hat Tore, Tests, Waechter. Das Vault hatte NICHTS, was etwas
erzwingt. Dieses Skript ist die Vault-Ausgabe der Test-Netz-Ratsche:
einmal drin, prueft es jede Sitzung.

ENTWURFS-ENTSCHEIDUNG: Die Uebersicht wird bei JEDEM Lauf LIVE aus dem
echten Datei-Bestand erzeugt. Es gibt bewusst KEINE gespeicherte
Index-Datei — die koennte veralten, und genau das ist die Krankheit,
die hier kuriert wird. (Einzige Ausnahme seit 07.08.: eine winzige
Zustands-Datei, die NUR Erst-Melde-DATEN von Gelb-Befunden haelt, keinen
Bestand — Herleitung unten bei GELB_ESKALATION_TAGE.)

================================================================================
UMBAU 2026-08-07 — WARUM DIESER WAECHTER FRUEHER DAUERROT WAR
================================================================================
Andrés Befund: "das scheint fuer uns so nicht zu funktionieren."
Gegengelesen von Gemini (Konzept) und Fable (am echten Code + Bestand).
Beide fanden unabhaengig dieselben drei Konstruktionsfehler:

FEHLER 1 — EIN-STUFEN-MODELL. Alles landete in derselben rot-Liste und
demselben Exit 1: "ein Arbeitstag fehlt im Changelog" (echtes Wahrheits-
Risiko, die Gruendungs-Krankheit) stand gleichrangig neben "Log hat 1029
statt 1000 Zeilen" (Hausarbeit ohne Risiko). Weil die Hausarbeits-Checks
strukturell dauernd rissen (Fehler 2), war fast immer rot — und die
Alarm-Muedigkeit, vor der die eigene Ablage-Regel §7③ warnt, frisst dann
auch die ECHTEN Befunde daneben.
  -> BEHOBEN: zwei Stufen. ROT nur fuer Wahrheits-Risiko. GELB fuer
     Hausarbeit — mit Verfallsdatum, sonst wird Gelb ein Friedhof.

FEHLER 2 — ZWEI SCHWELLEN FORDERTEN, WAS ANDERE REGELN VERBIETEN.
  (a) MAX_LOG_ZEILEN = 1000 war mit der eigenen Komprimier-Regel
      MATHEMATISCH UNVEREINBAR. Rechnung (Fable, an echten Daten):
      32 Volltext-Eintraege ueber 22 Tage = ~26 Zeilen/Eintrag,
      ~1,45 Eintraege/Tag = ~270 Zeilen/Woche. Die Regel "4 Wochen
      Volltext behalten" ergibt 4 x 270 = ~1080 Zeilen, plus
      Archiv-Register (166 Z., waechst) = ~1260 Zeilen DAUERZUSTAND.
      Die Grenze 1000 lag UNTER dem regelkonformen Minimum. Gruen war
      nur erreichbar, indem man Eintraege komprimierte, die die Regel
      noch im Volltext haben will — genau das passierte am 03.08., und
      dabei riss ein Datums-Anker (der dokumentierte Fehlalarm).
      Gegenprobe am realen Verlauf: nach der Komprimierung ~815 Zeilen,
      Rest-Luft 185, bei ~50 Zeilen/Tag -> rot nach ~3,7 Tagen.
      Beobachtet: gruen 03.08., rot 07.08. Die Rechnung trifft.
      -> ERSETZT durch KOMPRIMIER_TAGE: gemessen wird jetzt die
         Komprimier-Regel SELBST ("steht Volltext aelter als 4 Wochen
         drin?"). Das hat gar keine Schwelle mehr, die man biegen kann.
  (b) MAX_PLANUNG_DATEIEN = 25 forderte "Erledigtes ins Archiv" fuer
      einen Bestand, in dem es nach eigener Definition NICHTS Erledigtes
      gibt: 26 Dateien, alle inhaltlich zu Recht aktiv, 7 tragen "NICHT
      gebaut", 3 ausdruecklich "NICHT archivieren". Der Archiv-Ausloeser
      aus Ablage-Regel §3 ("Phase ist live") ist fuer sie nie gefeuert.
      Der Waechter mass Anzahl; die Krankheit waere FALSCH-aktiv, und
      falsch-aktiv war 0.
      -> ERSETZT durch den Anker-Check (siehe ANKER_PFLICHT_ORDNER).

FEHLER 3 — DIE MESSGROESSE WAR BLIND. Der 60-Tage-"aktiv"-Check hing am
Datei-Aenderungsdatum (mtime). Beim Aufraeumen am 02.08. wurden ALLE 26
Planungs-Dateien angefasst -> alle Uhren auf null, der Check konnte bis
Anfang Oktober nichts mehr finden. Jede Massen-Operation und sogar ein
OneDrive-Sync blendet ihn erneut. Ausgerechnet der Check, der der echten
Krankheit am naechsten kommt, war der am leichtesten zu taeuschende.
  -> BEHOBEN: gemessen wird das Kopfzeilen-Feld `letzte_aktualisierung`
     (ohnehin Pflicht). Gilt auch fuer "02 Stand".

IST DAS "DIE SCHWELLE BIEGEN, DAMIT ES GRUEN WIRD"? Nein — Lackmustest
aus Ablage-Regel §7③, hier bestanden: "Kaeme dieselbe neue Zahl heraus,
wenn der heutige Istwert ein anderer waere?" Die 1260-Zeilen-Rechnung
kommt aus zwei ANDEREN Regeln plus einer Messung; sie waere identisch
ausgefallen, wenn das Log heute bei 900 stuende. Gebogen waere: "steht
bei 1029, also Grenze 1100." Die sauberste Form ist ohnehin gar keine
Zahl mehr, sondern der Messgroessen-Tausch.

EIN REIN, EINS RAUS (Ablage-Regel §2) — die Gegenbuchungen dieses Umbaus:
  RAUS MAX_LOG_ZEILEN        -> REIN Volltext-aelter-als-4-Wochen (gelb)
  RAUS MAX_PLANUNG_DATEIEN   -> REIN Anker-Check (gelb)
  ERSETZT mtime              -> durch `letzte_aktualisierung` (kein neuer Check)
  NEU ohne Gegenbuchung: die Gelb-Eskalation. Bewusst als offene
  Gegenbuchung vermerkt (Ablage-Regel §2 erlaubt das ausdruecklich,
  verboten ist nur das stille Anhaengen). Eintrag im Log 07.08.

WAS AUSDRUECKLICH BLEIBT, WEIL ES FUNKTIONIERT HAT:
  - Log-Luecken gegen die Code-Historie (Check 5). Die einzige Pruefung
    gegen eine FREMDE Wahrheit statt gegen Selbst-Deklaration, und die
    einzige, die den Gruendungs-Vorfall (fehlender 31.07.) gefangen
    haette. Gemini wollte sie streichen — abgelehnt: die Fehlalarme kamen
    vom Komprimieren, nicht von der Pruefung. Faellt das Hand-Komprimieren
    weg, faellt die Fehlalarm-Quelle mit.
  - Live-Erzeugung ohne Index-Datei.
  - Die Selbst-Deklaration von Pruefkatalog und bekannten Luecken.
  - Die Korrektur-Historie als Kommentar (nicht wegputzen).
  - Der Exit-Code als Tor.
================================================================================

PRUEFKATALOG (CLAUDE.md: "Ein gruener Waechter beweist nur, was in seinem
Pruefkatalog steht"). Dieser Waechter prueft:

  ROT — Wahrheits-Risiko, VOR der Arbeit ansehen:
  R1. Fehlende Kopfzeilen (status / beschreibung)
  R2. "02 Stand" veraltet (die Datei, die als einzige Wahrheit gilt)
  R3. Log-Luecken: Tage mit Code-Commits ohne Log-Eintrag
  R4. Jeder Gelb-Befund, der laenger als GELB_ESKALATION_TAGE offen ist

  GELB — Hausarbeit, blockiert nicht, verfaellt aber:
  G1. Volltext-Log-Eintraege aelter als 4 Wochen (= die Komprimier-Regel)
  G2. Planungs-Dateien ohne gueltigen Geltungs-Anker
  G3. "aktiv", aber seit >60 Tagen nicht aktualisiert
  G4. CLAUDE.md-Wachstums-Alarm (Zeilen) + das belegte Mass (Regel-Anzahl)
  G5. Kaputte Wikilinks

BEKANNTE LUECKE — was er NICHT faengt:
  - ob der INHALT einer Datei stimmt (nur ob sie gepflegt aussieht)
  - ob ein Log-Eintrag vollstaendig ist (nur ob es ihn gibt)
  - Drift zwischen Vault-Roadmap und GSD-Roadmap
  - ob eine Entscheidung noch zur Marktrichtung passt (US-first)
  - der Anker-Check prueft, ob ein Anker EXISTIERT und in der Roadmap
    vorkommt — nicht, ob er der RICHTIGE ist. Ein falsch gesetzter Anker
    ist gruen. Bewusste Restluecke.
Wer diesen Katalog erweitert: Luecken-Liste hier mitpflegen.

AUFRUF:  python scripts/vault_guard.py [--kurz]
EXIT:    0 = sauber (oder nur Gelb), 1 = rote Befunde
"""

import io
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta

VAULT = r"C:\Users\andre\OneDrive\Desktop\Nerve-Vault"
REPO = r"C:\Users\andre\dev\salesnerve"

# --- Die Komprimier-Regel als Messgroesse, nicht als Zeilen-Schwelle. ---
# Ersetzt MAX_LOG_ZEILEN (Herleitung im Kopf, Fehler 2a).
# 28 Tage = die "~4 Wochen" aus Ablage-Regel §4.
# ⚠ WIDERSPRUCH AUFGELOEST 07.08.: Die Kopfzeile von "05 Log.md" sagte
# "~3 Wochen", Ablage-Regel §4 sagte "~4 Wochen", und commit_tage()
# vergleicht gegen 21 Tage. Drei Zahlen fuer dieselbe Sache. Gewaehlt: 28.
# Begruendung — 28 ist die SICHERE Richtung: der Luecken-Check (R3) braucht
# die '## Datum'-Anker der letzten 21 Tage. Wer erst nach 28 Tagen
# komprimiert, laesst sie stehen. Wer nach 21 komprimiert, kann genau den
# Anker abraeumen, den R3 im selben Lauf noch sucht -- exakt der Fehlalarm
# vom 03.08.
KOMPRIMIER_TAGE = 28

# Ab wann gilt ein alter Eintrag als "noch Volltext"? Beobachtet im Bestand:
# komprimierte Stummel sind 5 und 6 Zeilen lang (Datum + Typ + Verweis ins
# Archiv), Volltext-Eintraege im Schnitt 26. Grenze knapp UEBER dem
# beobachteten Stummel-Maximum -- nicht am Istwert eines Volltextes gewaehlt.
VOLLTEXT_ZEILEN = 8

# --- CLAUDE.md: Schwelle am 2026-08-03 UMGEWIDMET, nicht gebogen. ---
# Vorgeschichte: 700 war aus dem belegten Schnitt-Potenzial hergeleitet, nicht aus
# einer Wirkungs-Messung. Am 03.08. wurde recherchiert, was belegt ist:
#   * Anthropic empfiehlt <200 Zeilen -- Herstellerangabe OHNE veroeffentlichte Messung.
#   * Die einzige direkte Studie zu CLAUDE.md-Dateien (McMillan, arXiv 2605.10039,
#     1650 Sitzungen / 16050 Beobachtungen) findet zwischen 25 und 500 Zeilen
#     KEINEN Effekt auf Regel-Befolgung -- mit bestaetigendem Null-Beleg (BF10 0,05-0,10).
#     Auch die Position einer Regel in der Datei: kein Effekt.
#   * Belegt schaedlich ist etwas anderes: die ANZAHL gleichzeitig geltender Regeln.
#     "Prompt Design at Scale" (arXiv 2607.19257, getestet an Sonnet 5):
#     10 Regeln -> 59-94 % aller Regeln eingehalten, 40 Regeln -> 9-31 %, 80 -> ~0 %.
#   * Zweitgroesster belegter Faktor: aehnlich klingende, sich ueberlappende Regeln
#     (Chroma "Context Rot") und Widersprueche -- Anthropic: "Claude may pick one
#     arbitrarily". Das ist der Grund, warum Entdopplung mehr bringt als Kuerzen.
#   * Staerkster gemessener Effekt ueberhaupt: die SITZUNGSlaenge (-5,6 % Befolgungs-
#     Chance je gebauter Funktion), nicht die Dateilaenge.
# FOLGE: Die Zeilen-Schwelle ist KEIN Qualitaetsmass mehr, sondern ein reiner
# WACHSTUMS-ALARM ("hier wurde ergaenzt, ohne gegenzubuchen") -- deshalb 900 statt 700.
# Zeilen sind bei uns ohnehin ein Zerrspiegel: 697 Zeilen = 98.634 Zeichen (~30k Token),
# davon 107 Zeilen ueber 300 Zeichen. Unsere Zeilen sind 3-5x laenger als normale.
# Das ehrliche Mass steht darunter: MAX_DAUER_REGELN.
# ⚠ Seit 07.08. GELB statt ROT: ein Wachstums-Alarm ist Hausarbeit, kein
# Wahrheits-Risiko. Er verfaellt trotzdem (GELB_ESKALATION_TAGE).
MAX_CLAUDE_ZEILEN = 900

# --- Das BELEGTE Mass: Anzahl der IMMER geltenden harten Regeln. ---
# Hergeleitet aus der Sonnet-5-Messkurve oben: ab ~40 gleichzeitig geltenden Regeln
# faellt der Anteil der Antworten, die ALLE einhalten, auf 9-31 %.
# Gezaehlt werden Ueberschriften mit HART / Verbots-Zeichen / PFLICHT / Blitz / Stern.
# Beiss-Test 03.08.: mit Grenze 10 meldete der Zaehler korrekt rot -- nicht blind-gruen.
#
# ⚠ KORRIGIERT 2026-08-03 nach Fable-Gegenpruefung. Der Zaehler hatte einen
# gefaehrlichen blinden Fleck: Er matchte nur GROSS geschriebenes "PFLICHT" und sah
# damit ausgerechnet die RANGHOECHSTE Regel der Datei nicht ("Klartext-Pflicht",
# klein geschrieben, gleich zweimal). Ein Zaehler, der die wichtigste Regel uebersieht,
# meldet beruhigende Zahlen -- exakt der Fehler, gegen den die Regel "ein gruener
# Waechter beweist nur, was in seinem Pruefkatalog steht" ueberhaupt existiert.
# Jetzt case-insensitiv plus ⚡/★ als Marker.
#
# BEKANNTE LUECKEN -- ehrlich benannt, bewusst NICHT behoben.
# (4 und 5 am 03.08. nach Fable-Gegenpruefung ergaenzt -- sie fehlten, obwohl sie die
#  direkteste Form der Fehlerklasse sind. Genau das verbietet Punkt 31.)
#  1. Der Zaehler sieht nur UEBERSCHRIFTEN. Dauer-Pflichten als Aufzaehlungspunkt oder
#     im Fliesstext (Roadmap-Sync, "Ein Rein eins Raus" in Ablage-Regel 2, die 22
#     Bau-Regeln) zaehlen NICHT mit. Der reale Bestand liegt UEBER dem gemeldeten Wert.
#  2. Er sieht Form, nicht Wirkung. Zwei Regeln, die dasselbe sagen, zaehlen als zwei
#     -- das ist ABSICHT (Dopplung ist der belegte Schaden).
#  3. Er erkennt nicht, ob eine Regel inhaltlich noch stimmt.
#  4. UEBERSCHRIFTEN OHNE MARKERWORT zaehlen nicht mit, auch wenn sie Dauer-Pflichten
#     sind: "Git-Regel: Immer pushen", "Kommunikationsregel: Kein Gefaelligkeits-Ja",
#     "Entscheidungs-Kennzeichnung", "Aufwandsschaetzungen", "Test-Netz proaktiv
#     erweitern", "NERVE Architektur-Entscheidungen". Die Zahl ist eine Untergrenze.
#  5. UNTER-Ueberschriften EINER Regel zaehlen MEHRFACH: die Klartext-Pflicht liefert 4
#     Treffer, die Ablage-Regel ebenfalls 4. Es ist also eine Ueberschriften-Zaehlung,
#     KEINE Regel-Zaehlung -- die beiden Fehler (4 zaehlt zu wenig, 5 zu viel) heben
#     sich zufaellig teilweise auf. Wer die 40er-Schwelle interpretiert, muss das wissen.
#  6. Der Zaehler laeuft NUR gegen das Vault. Die GSD-Regeldatei (salesnerve/CLAUDE.md,
#     ~1140 Zeilen, >27 markierte Ueberschriften + Punkte 13-31 + 12 gespiegelte Regeln)
#     wird NICHT gezaehlt -- obwohl die Sonnet-Messkurve, die die Schwelle begruendet,
#     dort haerter zutrifft. Offener Punkt, in der Roadmap vermerkt.
MAX_DAUER_REGELN = 40

MAX_AKTIV_TAGE = 60          # "aktiv", aber so lange nicht aktualisiert = verdaechtig
MAX_STAND_TAGE = 30          # "02 Stand" gilt als einzige Wahrheit ueber den Systemzustand
LOG_LUECKE_TAGE = 2          # Code-Commits ohne Log-Eintrag binnen 2 Tagen = rot

# --- Die Gelb-Eskalation: das Gegengift gegen den Gelb-Friedhof. ---
# Fables Auflage zum Zwei-Stufen-Modell: "GELB braucht eine Eskalation, sonst ist es
# ein Friedhof." Ohne sie landet man in sechs Monaten wieder bei 46-von-50 -- nur
# diesmal mit gutem Gewissen, weil ja nichts rot war.
# 14 Tage: eine Hausarbeit, die zwei Wochen niemand anfasst, ist keine Hausarbeit mehr.
GELB_ESKALATION_TAGE = 14
ZUSTAND_DATEI = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             ".vault_guard_gelb.json")

# Ordner, deren Dateien einen Geltungs-Anker tragen muessen (ersetzt die Datei-Zaehlung).
ANKER_PFLICHT_ORDNER = "03 Planung"
# Anker-Werte, die KEINEN Roadmap-Treffer brauchen, weil sie bewusst etwas anderes sagen.
ANKER_FREI = ("dauerhaft", "verworfen")

SKIP_ORDNER = {".obsidian", ".trash", ".git", ".vault-tools", "node_modules"}
# Dateien ohne Kopfzeilen-Pflicht (Regelwerk + Briefing sind keine Notizen)
KEIN_KOPF_NOETIG = {"CLAUDE.md", "GEMINI.md", "README.md"}


def md_dateien():
    """Alle Notiz-Dateien im Vault, ohne technische Ordner."""
    treffer = []
    for wurzel, ordner, dateien in os.walk(VAULT):
        ordner[:] = [o for o in ordner if o not in SKIP_ORDNER and not o.startswith(".")]
        for d in dateien:
            if d.endswith(".md"):
                treffer.append(os.path.join(wurzel, d))
    return sorted(treffer)


def lies(pfad):
    try:
        return io.open(pfad, encoding="utf-8", errors="replace").read()
    except OSError:
        return ""


def kopf(text):
    """Kopfzeilen (YAML-Frontmatter) einlesen — bewusst simpel, keine Fremd-Bibliothek."""
    if not text.startswith("---"):
        return {}
    ende = text.find("\n---", 3)
    if ende == -1:
        return {}
    daten = {}
    for zeile in text[3:ende].split("\n"):
        if ":" in zeile and not zeile.strip().startswith("#"):
            k, _, v = zeile.partition(":")
            daten[k.strip()] = v.strip().strip("\"'")
    return daten


def alter_tage(kopfdaten, pfad):
    """Alter in Tagen — aus `letzte_aktualisierung`, NICHT aus dem Datei-Datum.

    ⚠ UMGESTELLT 2026-08-07 (Fable-Fund). Vorher haing das am mtime. Beim
    Aufraeumen am 02.08. wurden alle 26 Planungs-Dateien angefasst -> alle
    Uhren auf null, der 60-Tage-Check konnte bis Oktober nichts mehr finden.
    Auch ein OneDrive-Sync setzt mtime zurueck. Das Kopfzeilen-Feld ist eine
    ABSICHTSERKLAERUNG und laesst sich nicht versehentlich zuruecksetzen.
    Rueckfall auf mtime nur, wenn das Feld fehlt oder unlesbar ist -- dann
    wird das im Befund mitgesagt, damit die Zahl nicht faelschlich als
    belegt gilt.
    """
    roh = (kopfdaten.get("letzte_aktualisierung") or "").strip()
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", roh)
    if m:
        try:
            d = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            return (datetime.now() - d).days, True
        except ValueError:
            pass
    try:
        return (datetime.now()
                - datetime.fromtimestamp(os.path.getmtime(pfad))).days, False
    except OSError:
        return 0, False


def zeilen(pfad):
    return lies(pfad).count("\n") + 1


def commit_tage(n=21):
    """Tage der letzten n Tage, an denen im Code-Ordner committet wurde."""
    try:
        roh = subprocess.run(
            ["git", "log", f"--since={n}.days.ago", "--date=short", "--format=%ad"],
            cwd=REPO, capture_output=True, text=True, timeout=25,
        ).stdout
        return sorted(set(z.strip() for z in roh.split("\n") if z.strip()), reverse=True)
    except (OSError, subprocess.SubprocessError):
        return []


def log_eintraege(text):
    """Alle '## JJJJ-MM-TT'-Eintraege als (Datum, Zeilenzahl, Titel).

    Erkennt AUCH Bereichs-Ueberschriften wie '## 2026-07-23/24 — ...'.
    Ohne das meldete der Waechter am 02.08. einen Eintrag als fehlend, der
    sehr wohl existierte -- ein Fehlalarm im eigenen Pruefkatalog. Genau die
    Sorte Fund, die die Regel 'ein gruener Waechter beweist nur, was in
    seinem Katalog steht' auch in die andere Richtung belegt: ein ROTER
    Waechter kann ebenso luegen, wenn sein Muster zu eng ist.
    """
    zeilen_liste = text.split("\n")
    treffer = []
    for i, z in enumerate(zeilen_liste):
        m = re.match(r"^##\s+(\d{4})-(\d{2})-(\d{2})(?:/(\d{1,2}))?\s*(.*)$", z)
        if m:
            treffer.append((i, m, z))
    ergebnis = []
    for idx, (i, m, roh) in enumerate(treffer):
        ende = treffer[idx + 1][0] if idx + 1 < len(treffer) else len(zeilen_liste)
        datum = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        zweittag = (f"{m.group(1)}-{m.group(2)}-{int(m.group(4)):02d}"
                    if m.group(4) else None)
        titel = roh.lstrip("#").strip()
        ergebnis.append({
            "datum": datum, "zweittag": zweittag,
            "zeilen": ende - i, "titel": titel,
        })
    return ergebnis


def gelb_zustand_lesen():
    """Erst-Melde-Daten der Gelb-Befunde. Speichert DATEN, keinen Bestand."""
    try:
        with io.open(ZUSTAND_DATEI, encoding="utf-8") as f:
            d = json.load(f)
            return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def gelb_zustand_schreiben(daten):
    """Schreibt ueber Nebendatei + Umbenennen (CLAUDE.md: nie direkt schreiben)."""
    tmp = ZUSTAND_DATEI + ".tmp"
    try:
        with io.open(tmp, "w", encoding="utf-8") as f:
            f.write(json.dumps(daten, ensure_ascii=False, indent=1, sort_keys=True))
        os.replace(tmp, ZUSTAND_DATEI)
    except OSError:
        try:
            os.remove(tmp)
        except OSError:
            pass


def main():
    kurz = "--kurz" in sys.argv
    rot, gelb = [], []
    heute = datetime.now().strftime("%Y-%m-%d")
    dateien = md_dateien()

    # ---------- R1 + G2 + G3: Kopfzeilen, Geltungs-Anker, alte "aktiv"-Dateien -------
    roadmap_text = lies(os.path.join(VAULT, "01 Roadmap.md"))
    uebersicht, ohne_kopf, alt_aktiv, ohne_anker = [], [], [], []
    for p in dateien:
        rel = os.path.relpath(p, VAULT).replace("\\", "/")
        text = lies(p)
        k = kopf(text)
        status = k.get("status", "")
        beschr = k.get("beschreibung", "")
        a, belegt = alter_tage(k, p)
        uebersicht.append((rel, status or "-", a, belegt, beschr))

        if os.path.basename(p) not in KEIN_KOPF_NOETIG:
            if not status or not beschr:
                fehlt = " + ".join(
                    x for x, y in (("status", status), ("beschreibung", beschr)) if not y
                )
                ohne_kopf.append(f"{rel}  (fehlt: {fehlt})")

        if status == "aktiv" and a > MAX_AKTIV_TAGE:
            quelle = "" if belegt else "  [aus Datei-Datum geschaetzt, Kopfzeilen-Feld fehlt]"
            alt_aktiv.append(f"{rel}  ({a} Tage nicht aktualisiert){quelle}")

        # --- Geltungs-Anker (ersetzt die Datei-Zaehlung) ---
        if rel.startswith(ANKER_PFLICHT_ORDNER + "/"):
            anker = (k.get("anker") or "").strip()
            if not anker:
                ohne_anker.append(f"{rel}  — kein `anker:` in der Kopfzeile")
            elif anker.lower().startswith(ANKER_FREI):
                pass                                  # bewusst erklaert, kein Treffer noetig
            elif anker.upper() == "UNKLAR":
                ohne_anker.append(f"{rel}  — anker: UNKLAR (gilt das noch? wann kommt es dran?)")
            elif anker not in roadmap_text:
                ohne_anker.append(
                    f"{rel}  — anker '{anker}' kommt in 01 Roadmap.md NICHT vor")

    if ohne_kopf:
        rot.append((f"{len(ohne_kopf)} Datei(en) ohne vollstaendige Kopfzeile "
                    f"— unauffindbar, weil sie in keiner Uebersicht auftauchen", ohne_kopf))

    # ---------- R2: "02 Stand" — die gefaehrlichste Datei ----------
    stand = os.path.join(VAULT, "02 Stand.md")
    if os.path.exists(stand):
        a, belegt = alter_tage(kopf(lies(stand)), stand)
        if a > MAX_STAND_TAGE:
            rot.append((f"'02 Stand' ist {a} Tage alt (Grenze {MAX_STAND_TAGE})", [
                "Diese Datei gilt als EINZIGE WAHRHEIT ueber den Systemzustand.",
                "Veraltet erzeugt sie falsche Entscheidungen — schlimmer als eine zu grosse Datei.",
                "Gegen den echten Code verifizieren, nicht aus dem Kopf fortschreiben.",
                "" if belegt else "[aus Datei-Datum geschaetzt — `letzte_aktualisierung` fehlt]",
            ]))

    # ---------- R3: Log-Luecken (haette den 31.07. gefangen) ----------
    logp = os.path.join(VAULT, "05 Log.md")
    eintraege = []
    if os.path.exists(logp):
        logtext = lies(logp)
        eintraege = log_eintraege(logtext)
        vorhanden = set()
        for e in eintraege:
            vorhanden.add(e["datum"])
            if e["zweittag"]:
                vorhanden.add(e["zweittag"])
        grenze = (datetime.now() - timedelta(days=LOG_LUECKE_TAGE)).strftime("%Y-%m-%d")
        fehlend = [t for t in commit_tage() if t not in vorhanden and t < grenze]
        if fehlend:
            rot.append((f"{len(fehlend)} Tag(e) mit Code-Aenderungen ohne Log-Eintrag", [
                *fehlend[:10],
                "→ Genau dieser Ausfall (31.07.) hat den Vault-Aufraeum-Auftrag ausgeloest.",
            ]))

    # ---------- G1: Volltext aelter als 4 Wochen (ersetzt MAX_LOG_ZEILEN) ----------
    stichtag = (datetime.now() - timedelta(days=KOMPRIMIER_TAGE)).strftime("%Y-%m-%d")
    zu_alt = [e for e in eintraege
              if e["datum"] < stichtag and e["zeilen"] > VOLLTEXT_ZEILEN]
    if zu_alt:
        gelb.append(("log_volltext_alt",
                     f"{len(zu_alt)} Log-Eintrag/-Eintraege aelter als {KOMPRIMIER_TAGE} Tage "
                     f"stehen noch im Volltext",
                     [f"{e['datum']}  ({e['zeilen']} Zeilen)  {e['titel'][:58]}"
                      for e in zu_alt[:12]]
                     + ["→ Einzeiler MIT Datum, Volltext ins Archiv. NICHT splitten.",
                        "→ Datums-Anker muessen erhalten bleiben (Regeln verweisen darauf)."]))

    # ---------- G2: Geltungs-Anker ----------
    if ohne_anker:
        gelb.append(("anker_fehlt",
                     f"{len(ohne_anker)} Planungs-Datei(en) ohne gueltigen Geltungs-Anker",
                     ohne_anker[:14]
                     + ["→ `anker: <Roadmap-Punkt>` in die Kopfzeile, oder "
                        "`anker: verworfen (Grund)` / `anker: dauerhaft (Grund)`.",
                        "→ Das ist die Frage 'gilt das noch, und wann kommt es dran?' "
                        "als Pruefung statt als Appell."]))

    # ---------- G3: alte "aktiv"-Dateien ----------
    if alt_aktiv:
        gelb.append(("aktiv_alt",
                     f"{len(alt_aktiv)} Datei(en) stehen auf 'aktiv', wurden aber seit "
                     f">{MAX_AKTIV_TAGE} Tagen nicht aktualisiert", alt_aktiv[:14]))

    # ---------- G4: CLAUDE.md — Wachstums-Alarm + das belegte Mass ----------
    schwellen = []
    p_cl = os.path.join(VAULT, "CLAUDE.md")
    if os.path.exists(p_cl):
        z = zeilen(p_cl)
        if z > MAX_CLAUDE_ZEILEN:
            schwellen.append(
                f"CLAUDE.md: {z} Zeilen (Wachstums-Alarm ab {MAX_CLAUDE_ZEILEN}) — hier wurde "
                f"ergaenzt, ohne gegenzubuchen. Regel: ein Rein, eins Raus.")
        with io.open(p_cl, encoding="utf-8") as f:
            kopfzeilen = [z2 for z2 in f if z2.startswith("#")]
        dauer = [z2.strip() for z2 in kopfzeilen
                 if ("hart" in z2.lower() or "pflicht" in z2.lower()
                     or "⛔" in z2 or "⚡" in z2 or "★" in z2)]
        if len(dauer) > MAX_DAUER_REGELN:
            schwellen.append(
                f"CLAUDE.md: {len(dauer)} immer geltende harte Regeln (Grenze "
                f"{MAX_DAUER_REGELN}) — ab ~40 haelt Sonnet 5 belegt nur noch 9-31 % "
                f"aller Regeln gleichzeitig ein. Zusammenfuehren oder in einen "
                f"Waechter ueberfuehren, NICHT nur kuerzen.")
    if schwellen:
        gelb.append(("claude_wachstum", "Regeldatei-Alarm", schwellen))

    # ---------- G5: Kaputte Wikilinks ----------
    namen = {os.path.splitext(os.path.basename(p))[0] for p in dateien}
    pfade = {os.path.relpath(p, VAULT).replace("\\", "/")[:-3] for p in dateien}
    # ⚠ KORRIGIERT 2026-08-03 (Fable-Fund): Bis hierher kannte der Check NUR .md-Dateien als
    # gueltige Ziele -- ein Verweis auf ein Bild (`[[...png]]`) galt als kaputt, OBWOHL die Datei
    # existierte. Das meldete den Stromlaufplan einen ganzen Tag lang falsch-rot, und der Befund
    # wurde als "Bild fehlt" weitergereicht. Genau die Falsch-Rot-Klasse, vor der die eigene
    # Regel warnt ("ein roter Waechter kann ebenso luegen").
    for _wurzel, _uv, _fs in os.walk(VAULT):
        _uv[:] = [d for d in _uv if d not in SKIP_ORDNER and not d.startswith(".")]
        for _f in _fs:
            if _f.lower().endswith(".md"):
                continue                      # .md steckt schon in namen/pfade
            namen.add(_f)                     # Anhaenge: mit Endung verlinkt (Bild.png)
            namen.add(os.path.splitext(_f)[0])  # und ohne
            _rel = os.path.relpath(os.path.join(_wurzel, _f), VAULT).replace("\\", "/")
            pfade.add(_rel)
    # Ordner sind gueltige Verweis-Ziele (Obsidian oeffnet sie)
    ordner_ziele = set()
    for p in dateien:
        rel = os.path.relpath(p, VAULT).replace("\\", "/")
        teile = rel.split("/")[:-1]
        for i in range(len(teile)):
            ordner_ziele.add("/".join(teile[:i + 1]))
    kaputt = {}
    for p in dateien:
        for ziel in re.findall(r"\[\[([^\]|#]+)", lies(p)):
            z = ziel.strip().rstrip("/")
            # Obsidian erlaubt die .md-Endung im Verweis -- unser Muster muss das auch
            if z.endswith(".md"):
                z = z[:-3]
            if (not z or z in namen or z in pfade or z in ordner_ziele
                    or z.split("/")[-1] in namen):
                continue
            kaputt.setdefault(z, []).append(os.path.relpath(p, VAULT).replace("\\", "/"))
    if kaputt:
        gelb.append(("wikilinks", f"{len(kaputt)} Verweis-Ziel(e) existieren nicht", [
            f"[[{z}]]  ← verlinkt in: {', '.join(q[:2])}" for z, q in sorted(kaputt.items())[:15]
        ]))

    # ---------- R4: Gelb-Eskalation — das Gegengift gegen den Gelb-Friedhof ----------
    zustand = gelb_zustand_lesen()
    offen = {g[0] for g in gelb}
    for k in list(zustand):
        if k not in offen:
            del zustand[k]                    # Befund erledigt -> Uhr zurueck auf null
    for kennung, _t, _p in gelb:
        zustand.setdefault(kennung, heute)
    gelb_zustand_schreiben(zustand)

    eskaliert, gelb_alter = [], {}
    for kennung, titel, _p in gelb:
        seit = zustand.get(kennung, heute)
        try:
            tage = (datetime.now() - datetime.strptime(seit, "%Y-%m-%d")).days
        except ValueError:
            tage = 0
        gelb_alter[kennung] = (seit, tage)
        if tage >= GELB_ESKALATION_TAGE:
            eskaliert.append(f"{titel}  (offen seit {seit}, {tage} Tage)")
    if eskaliert:
        rot.append((f"{len(eskaliert)} Gelb-Befund(e) liegen laenger als "
                    f"{GELB_ESKALATION_TAGE} Tage", eskaliert + [
                        "→ Gelb ohne Verfallsdatum wird ein Friedhof. Jetzt abarbeiten,",
                        "  ODER die Schwelle mit HERLEITUNG kalibrieren, ODER als bewusste",
                        "  Ausnahme dokumentieren. Verboten: auf den Istwert heben.",
                    ]))

    # ================= AUSGABE =================
    out = []
    out.append("=" * 72)
    out.append(f"  VAULT-WAECHTER — {datetime.now():%Y-%m-%d %H:%M}")
    out.append("=" * 72)

    if not kurz:
        out.append("\n### BESTAND (live aus den Dateien erzeugt, keine gespeicherte Liste)\n")
        aktuell = None
        for rel, status, a, belegt, beschr in uebersicht:
            ordner = rel.rsplit("/", 1)[0] if "/" in rel else "(Wurzel)"
            if ordner != aktuell:
                out.append(f"\n  {ordner}/")
                aktuell = ordner
            name = rel.rsplit("/", 1)[-1][:-3]
            marke = "d " if belegt else "d?"
            out.append(f"    {name[:44]:<44} {status[:11]:<11} {a:>4}{marke} {beschr[:45]}")

    out.append("\n" + "=" * 72)
    if rot:
        out.append(f"  ROT — {len(rot)} Befund(e). Wahrheits-Risiko, VOR der Arbeit ansehen")
        out.append("=" * 72)
        for titel, punkte in rot:
            out.append(f"\n  [ROT] {titel}")
            for pt in punkte[:12]:
                if pt:
                    out.append(f"        - {pt}")
            if len(punkte) > 12:
                out.append(f"        ... und {len(punkte) - 12} weitere")
    else:
        out.append("  ROT — keine Befunde. Arbeit kann beginnen.")
        out.append("=" * 72)

    if gelb:
        out.append(f"\n  GELB — {len(gelb)} Hausarbeit(en). Blockiert nicht, verfaellt aber "
                   f"nach {GELB_ESKALATION_TAGE} Tagen zu ROT")
        for kennung, titel, punkte in gelb:
            seit, tage = gelb_alter.get(kennung, (heute, 0))
            rest = GELB_ESKALATION_TAGE - tage
            out.append(f"\n  [GELB] {titel}   (seit {seit} — noch {max(rest, 0)} Tage)")
            for pt in punkte[:12]:
                out.append(f"         - {pt}")
            if len(punkte) > 12:
                out.append(f"         ... und {len(punkte) - 12} weitere")

    out.append("\n" + "-" * 72)
    out.append(f"  {len(dateien)} Dateien | Log {len(eintraege)} Volltext-Eintraege "
               f"| Regeln {zeilen(os.path.join(VAULT, 'CLAUDE.md'))} Z.")
    out.append("  Dieser Waechter prueft NICHT: ob Inhalte stimmen, ob ein Log-Eintrag")
    out.append("  vollstaendig ist, ob beide Roadmaps synchron sind, ob Entscheidungen")
    out.append("  noch zur Marktrichtung (US-first) passen, und ob ein gesetzter Anker")
    out.append("  der RICHTIGE ist. Bekannte Luecken, bewusst benannt.")
    out.append("-" * 72)

    text = "\n".join(out)
    try:
        print(text)
    except UnicodeEncodeError:                      # Windows-Konsole, alter Zeichensatz
        print(text.encode("ascii", "replace").decode("ascii"))

    return 1 if rot else 0


if __name__ == "__main__":
    sys.exit(main())
