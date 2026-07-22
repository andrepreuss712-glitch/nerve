"""
tests/test_h1_merge_parse.py
──────────────────────────────────────────────────────────────────────────
Phase 08.23.2.H1 Plan 02 (WEG 1, Welle 2 — MERGE + TRUNC)

TDD-RED (Task 1) -> GRUEN (Task 2) fuer den truncation-festen, sektionsweisen
Parser `_parse_merged_sections(raw)` in services/claude_service.py.

WARUM SEKTIONSWEISE (Ist-Falle): der heutige `_parse_json` ist MONOLITHISCH
(erstes `{` bis letztes `}`, ein `json.loads`, all-or-nothing). Beim Merge
liefert EIN Haiku-Call BEIDE Sektionen (Einwand top-level + QA nested unter
"qa"). Wird das JSON abgeschnitten (max_tokens erreicht), killt `_parse_json`
ALLE Konsumenten — auch die frueh-emittierte Einwand-Sektion. `_parse_merged_sections`
rettet die Einwand-Sektion, auch wenn die QA-Sektion fehlt (fail-open qa={}).

Reine String->Dict-Parser-Tests (CLAUDE.md Test-Qualitaets-Regel: Runtime-
Verhalten via Function-Call-Return). KEIN Live-Call, kein Mock, kein Netz.

──────────────────────────────────────────────────────────────────────────
ERST-ROT-DISZIPLIN
- Task 1 (RED): `_parse_merged_sections` existiert noch nicht -> ImportError ->
  ALLE 8 Tests ROT. Vorab-Signal in Task-1-<verify>.
- Test 6 (B-1 Adversarial-Kollision) diskriminiert zusaetzlich den ANKER:
  gegen den naiven `rfind('"qa"')` (OHNE Doppelpunkt) ist er ROT (der Anker
  trifft den Einwand-WERT `"qa"` in `einwand_zitat` und schneidet mitten in
  die Einwand-Sektion -> `typ`/`gegenargument_*`/Readiness-Flags dahinter gehen
  still verloren); gegen den kollisionssicheren `rfind('"qa":')` (MIT Doppel-
  punkt) ist er GRUEN. Der Doppelpunkt-Anker ist Pflicht (Plan B-1).
──────────────────────────────────────────────────────────────────────────
"""

import json
import unittest


def _parser():
    from services.claude_service import _parse_merged_sections
    return _parse_merged_sections


# Vollstaendiges Merged-JSON: Einwand-Sektion FLACH top-level (= heutiges
# ergebnis-Schema) + QA-Sektion NESTED unter "qa" (Nesting Pflicht, sonst
# kollidieren confidence + einwand_zitat zwischen den Sektionen).
_FULL = json.dumps({
    "einwand": True,
    "typ": "Kosten/Preis",
    "intent_type": "echter_einwand",
    "confidence": 0.82,
    "intensitaet": "mittel",
    "ist_vorwand": False,
    "einwand_zitat": "das ist mir zu teuer",
    "gegenargument_1": "Ansatz A mit offener Frage?",
    "gegenargument_2": "Ansatz B mit offener Frage?",
    "detailfrage": False,
    "monosyllabisch": False,
    "qa": {"kategorie": "einwand_unknown", "confidence": 0.30, "einwand_zitat": "zu teuer"},
})


class TestParseMergedSections(unittest.TestCase):

    def test_1_happy_path_full_json(self):
        """Vollstaendiges JSON -> alle Einwand-Top-Level-Keys + result['qa'] befuellt."""
        parse = _parser()
        out = parse(_FULL)
        self.assertIsInstance(out, dict)
        # Einwand-Sektion (top-level) vollstaendig
        self.assertIs(out.get("einwand"), True)
        self.assertEqual(out.get("intent_type"), "echter_einwand")
        self.assertEqual(out.get("typ"), "Kosten/Preis")
        self.assertEqual(out.get("gegenargument_1"), "Ansatz A mit offener Frage?")
        self.assertEqual(out.get("gegenargument_2"), "Ansatz B mit offener Frage?")
        # QA-Sektion nested + befuellt
        self.assertIsInstance(out.get("qa"), dict)
        self.assertEqual(out["qa"].get("kategorie"), "einwand_unknown")
        self.assertAlmostEqual(out["qa"].get("confidence"), 0.30)

    def test_2_qa_truncated_einwand_survives(self):
        """QA-Sektion mitten in "qa":{... abgeschnitten (kein schliessendes }).
        Einwand-Sektion (alle Top-Level-Keys) kommt VOLLSTAENDIG an; qa == {}
        (fail-open, KEIN Crash, KEIN Verlust der Einwand-Sektion)."""
        parse = _parser()
        raw = (
            '{"einwand": true, "intent_type": "echter_einwand", "confidence": 0.8, '
            '"intensitaet": "mittel", "einwand_zitat": "zu teuer", '
            '"gegenargument_1": "Ansatz A?", "gegenargument_2": "Ansatz B?", '
            '"typ": "Kosten/Preis", "monosyllabisch": false, '
            '"qa": {"kategorie": "einwand_unkn'   # <-- abgeschnitten mitten im qa-Objekt
        )
        out = parse(raw)
        self.assertIsInstance(out, dict)
        self.assertIs(out.get("einwand"), True)
        self.assertEqual(out.get("intent_type"), "echter_einwand")
        self.assertEqual(out.get("typ"), "Kosten/Preis")
        self.assertEqual(out.get("gegenargument_1"), "Ansatz A?")
        self.assertEqual(out.get("gegenargument_2"), "Ansatz B?")
        self.assertIs(out.get("monosyllabisch"), False)
        # fail-open: QA-Sektion fehlt -> leeres Dict, kein Crash
        self.assertEqual(out.get("qa", "MISSING"), {})

    def test_3_einwand_truncated_mid_section_no_crash(self):
        """Auch die Einwand-Sektion selbst unvollstaendig (mitten im String
        abgeschnitten) -> so viel wie moeglich der frueh-emittierten Keys,
        mind. kein Crash; Rueckgabe ist IMMER ein Dict (nie Exception)."""
        parse = _parser()
        raw = (
            '{"einwand": true, "intent_type": "echter_einwand", "confidence": 0.8, '
            '"intensitaet": "mittel", "einwand_zitat": "zu teuer und ausserd'  # abgeschnitten im String
        )
        out = parse(raw)
        self.assertIsInstance(out, dict)   # nie Exception
        # die frueh-emittierten, vollstaendigen Keys sollen ankommen
        self.assertIs(out.get("einwand"), True)
        self.assertEqual(out.get("intent_type"), "echter_einwand")
        self.assertEqual(out.get("intensitaet"), "mittel")

    def test_4_garbage_and_empty(self):
        """'' und Nicht-JSON -> {} (wie heutiges _parse_json)."""
        parse = _parser()
        self.assertEqual(parse(""), {})
        self.assertEqual(parse("kein json hier, nur prosa"), {})
        self.assertEqual(parse(None), {})

    def test_5_nesting_collision_confidence_distinct(self):
        """confidence in der Einwand-Sektion (top-level) ist NICHT von
        qa.confidence ueberschrieben — beide distinkt lesbar."""
        parse = _parser()
        out = parse(_FULL)
        self.assertAlmostEqual(out.get("confidence"), 0.82)          # Einwand-Sektion
        self.assertAlmostEqual(out["qa"].get("confidence"), 0.30)    # QA-Sektion
        self.assertNotEqual(out.get("confidence"), out["qa"].get("confidence"))

    def test_6_adversarial_qa_value_collision_B1(self):
        """★ B-1 Adversarial-Kollision + Anker-Diskriminanz.

        Ein VOLLSTAENDIG emittiertes Einwand-Feld traegt den Substring "qa" als
        WERT (`einwand_zitat` == "qa", `typ` == "qa-Thema"), UND die echte
        qa-Sektion ist abgeschnitten (KEIN "qa":-Schluessel emittiert).

        ERST-ROT-DISZIPLIN (Anker):
        - gegen den NAIVEN Anker `rfind('"qa"')` (ohne Doppelpunkt): ROT — der
          Anker trifft den WERT `"qa"` in einwand_zitat und schneidet dort; alle
          Felder DANACH (gegenargument_1/2, typ, detailfrage, monosyllabisch)
          gehen still verloren.
        - gegen den kollisionssicheren `rfind('"qa":')` (mit Doppelpunkt): GRUEN —
          der Wert `"qa"` hat KEINEN Doppelpunkt dahinter, wird nie getroffen;
          qa_idx == -1 -> sauberes progressives Trimmen -> outer close ->
          ALLE vollstaendig emittierten Einwand-Felder ueberleben, qa == {}.

        Assert: alle vollstaendig emittierten Einwand-Top-Level-Keys kommen an —
        inkl. gegenargument_1/2, typ (EWB-Buttons) und die Readiness-Flags NACH
        dem "qa"-Wert-Feld; result.get('qa', {}) == {}.
        """
        parse = _parser()
        raw = (
            '{"einwand": true, "intent_type": "echter_einwand", "confidence": 0.8, '
            '"intensitaet": "mittel", '
            '"einwand_zitat": "qa", '                       # <-- Wert traegt den Substring "qa"
            '"gegenargument_1": "Ansatz A mit Frage?", '
            '"gegenargument_2": "Ansatz B mit Frage?", '
            '"typ": "qa-Thema", '                           # <-- Wert enthaelt "qa-" (kollidiert nicht mit "qa":)
            '"detailfrage": false, '
            '"monosyllabisch": false'                       # <-- abgeschnitten: kein }, keine qa-Sektion
        )
        out = parse(raw)
        self.assertIsInstance(out, dict)
        self.assertIs(out.get("einwand"), True)
        self.assertEqual(out.get("einwand_zitat"), "qa")
        # DIE Felder, die der naive Anker still verlieren wuerde:
        self.assertEqual(out.get("gegenargument_1"), "Ansatz A mit Frage?")
        self.assertEqual(out.get("gegenargument_2"), "Ansatz B mit Frage?")
        self.assertEqual(out.get("typ"), "qa-Thema")
        self.assertIs(out.get("detailfrage"), False)
        self.assertIs(out.get("monosyllabisch"), False)
        # echte qa-Sektion fehlt -> fail-open leeres Dict
        self.assertEqual(out.get("qa", "MISSING"), {})

    def test_7_order_violation_qa_first(self):
        """KORREKTUR 4 — Test 7 (Order-Violation): Modell emittiert `qa` ZUERST
        trotz STRICT ORDER, danach die (abgeschnittene) Einwand-Sektion. Der
        `rfind('"qa":')`-Schnitt koepft die Einwand-Sektion -> fail-open {}.
        Assert: Rueckgabe ist ein Dict, KEIN Crash. (Akzeptierte Degradation:
        dieser eine Tick verliert die Einwand-Sektion, der naechste 4s-Tick
        heilt selbst. Bewusst akzeptiert, nicht abgefangen.)"""
        parse = _parser()
        raw = (
            '{"qa": {"kategorie": "frage", "confidence": 0.7, "einwand_zitat": null}, '
            '"einwand": true, "intent_type": "echter_einwand", "typ": "Kost'  # abgeschnitten
        )
        out = parse(raw)
        self.assertIsInstance(out, dict)   # KEIN Crash — das ist die Zusicherung

    def test_8_kein_einwand_happy_path(self):
        """KORREKTUR 4 — Test 8 (Kein-Einwand-Happy-Path): der HAEUFIGSTE Fall
        {"einwand": false, "notiz": "...", "qa": {...}} MUSS Happy-Path sein
        (voll geparst), NICHT in den Rescue fallen. Design-Regel: was json.loads
        sauber als Dict parst = Happy-Path; Rescue nur bei echtem Parse-Fehler.
        Der Happy-Path-Check darf NICHT die volle Einwand-Keyliste verlangen."""
        parse = _parser()
        raw = json.dumps({
            "einwand": False,
            "notiz": "Kunde stellt eine Rueckfrage zum Ablauf",
            "qa": {"kategorie": "frage", "confidence": 0.66, "einwand_zitat": "wie laeuft das ab"},
        })
        out = parse(raw)
        self.assertIsInstance(out, dict)
        self.assertIs(out.get("einwand"), False)
        # Kein-Einwand-Zweig: notiz MUSS erhalten bleiben (Leser live_session.py:1139)
        self.assertEqual(out.get("notiz"), "Kunde stellt eine Rueckfrage zum Ablauf")
        # QA-Sektion voll geparst (nicht durch Rescue verworfen)
        self.assertIsInstance(out.get("qa"), dict)
        self.assertEqual(out["qa"].get("kategorie"), "frage")


if __name__ == "__main__":
    unittest.main()
