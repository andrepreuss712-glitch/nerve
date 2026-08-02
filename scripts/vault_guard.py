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
die hier kuriert wird.

PRUEFKATALOG (CLAUDE.md: "Ein gruener Waechter beweist nur, was in seinem
Pruefkatalog steht"). Dieser Waechter prueft:
  1. Fehlende Kopfzeilen (status / beschreibung)
  2. Dateien auf "aktiv", die seit >60 Tagen niemand angefasst hat
  3. Groessen-Schwellen (Log, CLAUDE.md, Datei-Anzahl in 03 Planung)
  4. Alter von "02 Stand" (die Datei, die als einzige Wahrheit gilt)
  5. Log-Luecken: Tage mit Code-Commits ohne Log-Eintrag
  6. Kaputte Wikilinks (Ziel existiert nicht)

BEKANNTE LUECKE — was er NICHT faengt:
  - ob der INHALT einer Datei stimmt (nur ob sie gepflegt aussieht)
  - ob ein Log-Eintrag vollstaendig ist (nur ob es ihn gibt)
  - Drift zwischen Vault-Roadmap und GSD-Roadmap
  - ob eine Entscheidung noch zur Marktrichtung passt (US-first)
Wer diesen Katalog erweitert: Luecken-Liste hier mitpflegen.

AUFRUF:  python scripts/vault_guard.py [--kurz]
EXIT:    0 = sauber, 1 = rote Befunde
"""

import io
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta

VAULT = r"C:\Users\andre\OneDrive\Desktop\Nerve-Vault"
REPO = r"C:\Users\andre\dev\salesnerve"

# --- Schwellen. Reissen sie, ist das ein roter Befund, kein Gefuehl. ---
MAX_LOG_ZEILEN = 1000
MAX_CLAUDE_ZEILEN = 500
MAX_PLANUNG_DATEIEN = 25
MAX_AKTIV_TAGE = 60          # "aktiv", aber so lange nicht angefasst = verdaechtig
MAX_STAND_TAGE = 30          # "02 Stand" gilt als einzige Wahrheit ueber den Systemzustand
LOG_LUECKE_TAGE = 2          # Code-Commits ohne Log-Eintrag binnen 2 Tagen = rot

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


def tage_her(pfad):
    return (datetime.now() - datetime.fromtimestamp(os.path.getmtime(pfad))).days


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


def log_tage(text):
    """Datumsangaben der Eintraege in 05 Log.md."""
    return set(re.findall(r"^##\s+(\d{4}-\d{2}-\d{2})", text, re.M))


def main():
    kurz = "--kurz" in sys.argv
    rot, gelb = [], []
    dateien = md_dateien()

    # ---------- 1+2: Kopfzeilen + verdaechtig alte "aktiv"-Dateien ----------
    uebersicht, ohne_kopf, alt_aktiv = [], [], []
    for p in dateien:
        rel = os.path.relpath(p, VAULT).replace("\\", "/")
        k = kopf(lies(p))
        status = k.get("status", "")
        beschr = k.get("beschreibung", "")
        alter = tage_her(p)
        uebersicht.append((rel, status or "-", alter, beschr))

        if os.path.basename(p) not in KEIN_KOPF_NOETIG:
            if not status or not beschr:
                fehlt = " + ".join(
                    x for x, y in (("status", status), ("beschreibung", beschr)) if not y
                )
                ohne_kopf.append(f"{rel}  (fehlt: {fehlt})")
        if status == "aktiv" and alter > MAX_AKTIV_TAGE:
            alt_aktiv.append(f"{rel}  ({alter} Tage nicht angefasst)")

    if ohne_kopf:
        rot.append((f"{len(ohne_kopf)} Datei(en) ohne vollstaendige Kopfzeile "
                    f"— unauffindbar, weil sie in keiner Uebersicht auftauchen", ohne_kopf))
    if alt_aktiv:
        rot.append((f"{len(alt_aktiv)} Datei(en) stehen auf 'aktiv', wurden aber seit "
                    f">{MAX_AKTIV_TAGE} Tagen nicht angefasst — erledigt? dann Status setzen "
                    f"+ archivieren", alt_aktiv))

    # ---------- 3: Groessen-Schwellen ----------
    schwellen = []
    for datei, grenze in (("05 Log.md", MAX_LOG_ZEILEN), ("CLAUDE.md", MAX_CLAUDE_ZEILEN)):
        p = os.path.join(VAULT, datei)
        if os.path.exists(p):
            z = zeilen(p)
            if z > grenze:
                schwellen.append(f"{datei}: {z} Zeilen (Grenze {grenze}) — komprimieren, NICHT splitten")

    pl = os.path.join(VAULT, "03 Planung")
    if os.path.isdir(pl):
        anz = len([f for f in os.listdir(pl) if f.endswith(".md")])
        if anz > MAX_PLANUNG_DATEIEN:
            schwellen.append(f"03 Planung/: {anz} Dateien (Grenze {MAX_PLANUNG_DATEIEN}) "
                             f"— Erledigtes ins Archiv")
    if schwellen:
        rot.append(("Groessen-Schwellen gerissen", schwellen))

    # ---------- 4: "02 Stand" — die gefaehrlichste Datei ----------
    stand = os.path.join(VAULT, "02 Stand.md")
    if os.path.exists(stand):
        a = tage_her(stand)
        if a > MAX_STAND_TAGE:
            rot.append((f"'02 Stand' ist {a} Tage alt (Grenze {MAX_STAND_TAGE})", [
                "Diese Datei gilt als EINZIGE WAHRHEIT ueber den Systemzustand.",
                "Veraltet erzeugt sie falsche Entscheidungen — schlimmer als eine zu grosse Datei.",
                "Gegen den echten Code verifizieren, nicht aus dem Kopf fortschreiben.",
            ]))

    # ---------- 5: Log-Luecken (haette den 31.07. gefangen) ----------
    logp = os.path.join(VAULT, "05 Log.md")
    if os.path.exists(logp):
        vorhanden = log_tage(lies(logp))
        grenze = (datetime.now() - timedelta(days=LOG_LUECKE_TAGE)).strftime("%Y-%m-%d")
        fehlend = [t for t in commit_tage() if t not in vorhanden and t < grenze]
        if fehlend:
            rot.append((f"{len(fehlend)} Tag(e) mit Code-Aenderungen ohne Log-Eintrag", [
                *fehlend[:10],
                "→ Genau dieser Ausfall (31.07.) hat den Vault-Aufraeum-Auftrag ausgeloest.",
            ]))

    # ---------- 6: Kaputte Wikilinks ----------
    namen = {os.path.splitext(os.path.basename(p))[0] for p in dateien}
    pfade = {os.path.relpath(p, VAULT).replace("\\", "/")[:-3] for p in dateien}
    kaputt = {}
    for p in dateien:
        for ziel in re.findall(r"\[\[([^\]|#]+)", lies(p)):
            z = ziel.strip().rstrip("/")
            if not z or z in namen or z in pfade or z.split("/")[-1] in namen:
                continue
            kaputt.setdefault(z, []).append(os.path.relpath(p, VAULT).replace("\\", "/"))
    if kaputt:
        gelb.append((f"{len(kaputt)} Verweis-Ziel(e) existieren nicht", [
            f"[[{z}]]  ← verlinkt in: {', '.join(q[:2])}" for z, q in sorted(kaputt.items())[:15]
        ]))

    # ================= AUSGABE =================
    out = []
    out.append("=" * 72)
    out.append(f"  VAULT-WAECHTER — {datetime.now():%Y-%m-%d %H:%M}")
    out.append("=" * 72)

    if not kurz:
        out.append("\n### BESTAND (live aus den Dateien erzeugt, keine gespeicherte Liste)\n")
        aktuell = None
        for rel, status, alter, beschr in uebersicht:
            ordner = rel.rsplit("/", 1)[0] if "/" in rel else "(Wurzel)"
            if ordner != aktuell:
                out.append(f"\n  {ordner}/")
                aktuell = ordner
            name = rel.rsplit("/", 1)[-1][:-3]
            out.append(f"    {name[:44]:<44} {status[:11]:<11} {alter:>4}d  {beschr[:46]}")

    out.append("\n" + "=" * 72)
    if rot:
        out.append(f"  ROT — {len(rot)} Befund(e), VOR der Arbeit ansehen")
        out.append("=" * 72)
        for titel, punkte in rot:
            out.append(f"\n  [ROT] {titel}")
            for pt in punkte[:12]:
                out.append(f"        - {pt}")
            if len(punkte) > 12:
                out.append(f"        ... und {len(punkte) - 12} weitere")
    else:
        out.append("  ROT — keine Befunde.")
        out.append("=" * 72)

    for titel, punkte in gelb:
        out.append(f"\n  [GELB] {titel}")
        for pt in punkte[:12]:
            out.append(f"         - {pt}")

    out.append("\n" + "-" * 72)
    out.append(f"  {len(dateien)} Dateien | Log {zeilen(logp) if os.path.exists(logp) else 0} Z. "
               f"| Regeln {zeilen(os.path.join(VAULT, 'CLAUDE.md'))} Z.")
    out.append("  Dieser Waechter prueft NICHT: ob Inhalte stimmen, ob ein Log-Eintrag")
    out.append("  vollstaendig ist, ob beide Roadmaps synchron sind, ob Entscheidungen")
    out.append("  noch zur Marktrichtung (US-first) passen. Bekannte Luecke, bewusst benannt.")
    out.append("-" * 72)

    text = "\n".join(out)
    try:
        print(text)
    except UnicodeEncodeError:                      # Windows-Konsole, alter Zeichensatz
        print(text.encode("ascii", "replace").decode("ascii"))

    return 1 if rot else 0


if __name__ == "__main__":
    sys.exit(main())
