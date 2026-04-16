"""
tests/test_einwand_keyword_matcher.py
────────────────────────────────────────────────────────────────────
Unit-Tests fuer services/einwand_keyword_matcher.py

Abdeckung:
 - Positiv-Tests fuer jeden Keyword-Typ
 - False-Positive-Schutz (kein versehentlicher Match)
 - Umlaut + ae/ue/oe-Varianten
 - Dedup-Guard: zweiter identischer Match wird unterdrueckt
 - reset_keyword(): nach Reset wieder positiv
 - reset_all(): loescht kompletten State
 - Profil ohne Gegenargument: kein Match
 - Kein Match wenn profile_einwaende leer

pytest-kompatibel.
"""

import time
import pytest

from services.einwand_keyword_matcher import (
    EinwandKeywordMatcher,
    match_keyword,
)


# ── Test-Fixtures ────────────────────────────────────────────────────────────

def _einwand(kategorie: str, gegenargument: str = "Unser Preis ist gerechtfertigt.",
             typ: str = "") -> dict:
    """Erstellt ein minimales Profil-Einwand-Dict fuer Tests."""
    entry = {
        'kategorie': kategorie,
        'gegenargument': gegenargument,
    }
    if typ:
        entry['typ'] = typ
    return entry


def _einwand_kein_ga(kategorie: str) -> dict:
    """Profil-Einwand ohne Gegenargument (gegenargument leer)."""
    return {'kategorie': kategorie, 'gegenargument': ''}


# Repraesentative Profil-Liste mit echten DB-Feldnamen
PROFIL_EINWAENDE = [
    _einwand('Preis',       'Unser ROI liegt bei 3x innerhalb 6 Monaten.'),
    _einwand('Zeit',        'Das Setup dauert nur 15 Minuten.', typ='Zeit/Aufschub'),
    _einwand('Bedarf',      'Viele unserer Kunden dachten das auch.'),
    _einwand('Vertrauen',   'Hier sind drei Referenzen aus Ihrer Branche.'),
    _einwand('Wettbewerb',  'Was unterscheidet uns: Echtzeit-Coaching.', typ='Vergleich'),
    _einwand('Entscheider', 'Ich kann gerne einen kurzen Entscheider-Call vorbereiten.',
             typ='Entscheidungstraeger'),
    _einwand('Datenschutz', 'Server stehen in Deutschland, DSGVO-konform.'),
    _einwand('Skepsis',     'Hier ist ein Fallstudie mit messbaren Ergebnissen.'),
]


# ── Positiv-Tests: ein Test pro Keyword ─────────────────────────────────────

class TestKeywordPositivMatches:

    def test_keine_zeit_direkt(self):
        result = match_keyword("keine Zeit dafuer", PROFIL_EINWAENDE)
        assert result is not None
        assert result['keyword'] == 'keine_zeit'

    def test_keine_zeit_im_satz(self):
        result = match_keyword("Habe gerade echt keine Zeit dafuer", PROFIL_EINWAENDE)
        assert result is not None
        assert result['keyword'] == 'keine_zeit'

    def test_keine_zeit_gerade_keinen(self):
        result = match_keyword("Ich habe gerade keinen Zeit fuer sowas", PROFIL_EINWAENDE)
        assert result is not None
        assert result['keyword'] == 'keine_zeit'

    def test_keine_zeit_stress(self):
        result = match_keyword("Ich hab gerade Stress auf der Arbeit", PROFIL_EINWAENDE)
        assert result is not None
        assert result['keyword'] == 'keine_zeit'

    def test_zu_teuer(self):
        result = match_keyword("Das ist zu teuer fuer uns", PROFIL_EINWAENDE)
        assert result is not None
        assert result['keyword'] == 'zu_teuer'

    def test_zu_teuer_budget(self):
        result = match_keyword("Wir haben kein Budget dafuer", PROFIL_EINWAENDE)
        assert result is not None
        assert result['keyword'] == 'zu_teuer'

    def test_zu_teuer_viel_zu_teuer(self):
        result = match_keyword("Das ist viel zu teuer", PROFIL_EINWAENDE)
        assert result is not None
        assert result['keyword'] == 'zu_teuer'

    def test_kein_interesse(self):
        result = match_keyword("kein Interesse daran", PROFIL_EINWAENDE)
        assert result is not None
        assert result['keyword'] == 'kein_interesse'

    def test_kein_interesse_nicht_interessiert(self):
        result = match_keyword("Ich bin nicht interessiert", PROFIL_EINWAENDE)
        assert result is not None
        assert result['keyword'] == 'kein_interesse'

    def test_ueberlegen_umlaut(self):
        """Umlaut-Variante: 'muss überlegen'"""
        result = match_keyword("Ich muss noch überlegen", PROFIL_EINWAENDE)
        assert result is not None
        assert result['keyword'] == 'ueberlegen'

    def test_ueberlegen_ae_variante(self):
        """ae-Fallback: 'muss ueberlegen'"""
        result = match_keyword("Ich muss ueberlegen", PROFIL_EINWAENDE)
        assert result is not None
        assert result['keyword'] == 'ueberlegen'

    def test_ueberlegen_darueber_umlaut(self):
        """'darüber nachdenken' mit Umlaut"""
        result = match_keyword("Ich muss darüber nachdenken", PROFIL_EINWAENDE)
        assert result is not None
        assert result['keyword'] == 'ueberlegen'

    def test_ueberlegen_darueber_ae(self):
        """'darueber nachdenken' ae-Fallback"""
        result = match_keyword("Ich muss darueber nachdenken", PROFIL_EINWAENDE)
        assert result is not None
        assert result['keyword'] == 'ueberlegen'

    def test_ueberlegen_schlaf_drueber_umlaut(self):
        result = match_keyword("Ich schlaf mal drüber", PROFIL_EINWAENDE)
        assert result is not None
        assert result['keyword'] == 'ueberlegen'

    def test_skeptisch_direkt(self):
        result = match_keyword("ich bin skeptisch", PROFIL_EINWAENDE)
        assert result is not None
        assert result['keyword'] == 'skeptisch'

    def test_skeptisch_vertraue_nicht(self):
        result = match_keyword("Ich vertraue das nicht", PROFIL_EINWAENDE)
        assert result is not None
        assert result['keyword'] == 'skeptisch'

    def test_haben_schon(self):
        result = match_keyword("Wir haben schon etwas in dem Bereich", PROFIL_EINWAENDE)
        assert result is not None
        assert result['keyword'] == 'haben_schon'

    def test_haben_schon_nutzen(self):
        result = match_keyword("Wir nutzen schon ein anderes Tool", PROFIL_EINWAENDE)
        assert result is not None
        assert result['keyword'] == 'haben_schon'

    def test_haben_schon_versorgt(self):
        result = match_keyword("Wir sind schon versorgt", PROFIL_EINWAENDE)
        assert result is not None
        assert result['keyword'] == 'haben_schon'

    def test_falscher_ansprechpartner(self):
        result = match_keyword("Ich bin nicht der Richtige dafuer", PROFIL_EINWAENDE)
        assert result is not None
        assert result['keyword'] == 'falscher_ansprechpartner'

    def test_falscher_ansprechpartner_direkt(self):
        result = match_keyword("Das ist ein falscher Ansprechpartner", PROFIL_EINWAENDE)
        assert result is not None
        assert result['keyword'] == 'falscher_ansprechpartner'

    def test_falscher_ansprechpartner_nicht_zustaendig_umlaut(self):
        result = match_keyword("Ich bin nicht zuständig dafuer", PROFIL_EINWAENDE)
        assert result is not None
        assert result['keyword'] == 'falscher_ansprechpartner'

    def test_falscher_ansprechpartner_nicht_zustaendig_ae(self):
        """ae-Fallback: 'nicht zustaendig'"""
        result = match_keyword("Dafuer bin ich nicht zustaendig", PROFIL_EINWAENDE)
        assert result is not None
        assert result['keyword'] == 'falscher_ansprechpartner'

    def test_kompliziert(self):
        result = match_keyword("Das ist zu kompliziert", PROFIL_EINWAENDE)
        assert result is not None
        assert result['keyword'] == 'kompliziert'

    def test_kompliziert_aufwaendig_umlaut(self):
        """Umlaut: 'zu aufwändig'"""
        result = match_keyword("Das ist zu aufwändig fuer uns", PROFIL_EINWAENDE)
        assert result is not None
        assert result['keyword'] == 'kompliziert'

    def test_kompliziert_aufwaendig_ae(self):
        """ae-Fallback: 'zu aufwaendig'"""
        result = match_keyword("Ist uns zu aufwaendig", PROFIL_EINWAENDE)
        assert result is not None
        assert result['keyword'] == 'kompliziert'

    def test_kompliziert_zu_viel_arbeit(self):
        result = match_keyword("Das macht zu viel Arbeit", PROFIL_EINWAENDE)
        assert result is not None
        assert result['keyword'] == 'kompliziert'


# ── False-Positive-Tests ─────────────────────────────────────────────────────

class TestFalsePositiveSchutz:

    def test_meine_zeit_ist_kostbar_kein_match(self):
        """'meine Zeit ist kostbar' darf NICHT 'keine_zeit' triggern."""
        result = match_keyword("Meine Zeit ist kostbar", PROFIL_EINWAENDE)
        # koennte kein_interesse oder anderes treffen — aber NICHT keine_zeit
        if result:
            assert result['keyword'] != 'keine_zeit'

    def test_leerer_transcript_kein_match(self):
        result = match_keyword("", PROFIL_EINWAENDE)
        assert result is None

    def test_none_transcript_kein_match(self):
        result = match_keyword(None, PROFIL_EINWAENDE)
        assert result is None

    def test_leere_profile_einwaende_kein_match(self):
        result = match_keyword("Ich habe keine Zeit", [])
        assert result is None

    def test_normaler_satz_kein_match(self):
        result = match_keyword(
            "Ich schaue mir das gerne mal an, klingt interessant",
            PROFIL_EINWAENDE,
        )
        assert result is None

    def test_konkurrent_klingt_gut_match_skeptisch(self):
        """'klingt zu gut' triggert 'skeptisch' — das ist korrekt, kein false-positive."""
        result = match_keyword("Das klingt zu gut um wahr zu sein", PROFIL_EINWAENDE)
        # Wenn match, dann skeptisch
        if result:
            assert result['keyword'] == 'skeptisch'


# ── Profil-Gegenargument-Tests ───────────────────────────────────────────────

class TestProfilGegenargument:

    def test_profil_ohne_gegenargument_kein_match(self):
        """Profil mit leerem gegenargument soll KEINEN Match liefern."""
        einwaende_ohne_ga = [_einwand_kein_ga('Preis')]
        result = match_keyword("Das ist zu teuer", einwaende_ohne_ga)
        assert result is None

    def test_profil_mit_gegenargument_1_fallback(self):
        """Fallback auf 'gegenargument_1' wenn 'gegenargument' fehlt."""
        einwaende = [{
            'kategorie': 'Preis',
            'gegenargument_1': 'ROI-Argument hier.',
        }]
        result = match_keyword("Das ist zu teuer", einwaende)
        assert result is not None
        assert result['keyword'] == 'zu_teuer'

    def test_profil_match_feldprioritaet_kurzlabel(self):
        """kurzlabel hat hoehere Prioritaet als kategorie/typ."""
        einwaende = [{
            'kurzlabel': 'Preis',
            'kategorie': 'Sonstiges',
            'typ': 'Sonstiges',
            'gegenargument': 'ROI-Argument.',
        }]
        result = match_keyword("Das ist zu teuer", einwaende)
        assert result is not None
        assert result['matched_label'] == 'Preis'

    def test_profil_match_typ_wenn_kein_kurzlabel(self):
        """Fallback auf typ wenn kurzlabel und kategorie nicht matchen."""
        einwaende = [{
            'kategorie': 'Sonstiges',
            'typ': 'Kosten/Preis',
            'gegenargument': 'ROI-Argument.',
        }]
        result = match_keyword("Das ist zu teuer", einwaende)
        assert result is not None
        assert result['keyword'] == 'zu_teuer'


# ── Dedup-Tests ──────────────────────────────────────────────────────────────

class TestDedup:

    def test_zweiter_match_wird_unterdrueckt(self):
        """Gleicher Keyword-Typ innerhalb Dedup-Fenster: zweiter Match = None."""
        matcher = EinwandKeywordMatcher(dedup_window_sec=10.0)
        r1 = matcher.match_with_dedup("Das ist zu teuer", PROFIL_EINWAENDE)
        r2 = matcher.match_with_dedup("Das ist zu teuer", PROFIL_EINWAENDE)
        assert r1 is not None
        assert r1['keyword'] == 'zu_teuer'
        assert r2 is None

    def test_verschiedene_keywords_nicht_blockiert(self):
        """Verschiedene Keyword-Typen blockieren sich nicht gegenseitig."""
        matcher = EinwandKeywordMatcher(dedup_window_sec=10.0)
        r1 = matcher.match_with_dedup("Das ist zu teuer", PROFIL_EINWAENDE)
        r2 = matcher.match_with_dedup("Ich habe keine Zeit", PROFIL_EINWAENDE)
        assert r1 is not None
        assert r2 is not None
        assert r1['keyword'] == 'zu_teuer'
        assert r2['keyword'] == 'keine_zeit'

    def test_reset_keyword_erlaubt_re_trigger(self):
        """reset_keyword() loescht Dedup-Eintrag → naechster Match positiv."""
        matcher = EinwandKeywordMatcher(dedup_window_sec=10.0)
        r1 = matcher.match_with_dedup("Das ist zu teuer", PROFIL_EINWAENDE)
        assert r1 is not None

        matcher.reset_keyword('zu_teuer')

        r2 = matcher.match_with_dedup("Das ist zu teuer", PROFIL_EINWAENDE)
        assert r2 is not None
        assert r2['keyword'] == 'zu_teuer'

    def test_reset_all_loescht_state(self):
        """reset_all() erlaubt alle Keywords neu zu triggern."""
        matcher = EinwandKeywordMatcher(dedup_window_sec=10.0)
        matcher.match_with_dedup("Das ist zu teuer", PROFIL_EINWAENDE)
        matcher.match_with_dedup("Ich habe keine Zeit", PROFIL_EINWAENDE)

        matcher.reset_all()

        r1 = matcher.match_with_dedup("Das ist zu teuer", PROFIL_EINWAENDE)
        r2 = matcher.match_with_dedup("Ich habe keine Zeit", PROFIL_EINWAENDE)
        assert r1 is not None
        assert r2 is not None

    def test_dedup_ablauf_nach_fenster(self):
        """Nach Ablauf des Dedup-Fensters erlaubt naechster Match."""
        matcher = EinwandKeywordMatcher(dedup_window_sec=0.05)  # 50ms Fenster
        r1 = matcher.match_with_dedup("Das ist zu teuer", PROFIL_EINWAENDE)
        assert r1 is not None

        time.sleep(0.1)  # laenger als Fenster

        r2 = matcher.match_with_dedup("Das ist zu teuer", PROFIL_EINWAENDE)
        assert r2 is not None

    def test_reset_keyword_fremdes_keyword_ignoriert(self):
        """reset_keyword() auf nicht-vorhandenen Key wirft keinen Fehler."""
        matcher = EinwandKeywordMatcher()
        matcher.reset_keyword('nicht_existierendes_keyword')  # kein Fehler


# ── Case-Insensitivity-Tests ─────────────────────────────────────────────────

class TestCaseInsensitivity:

    def test_grosschreibung_matcht(self):
        result = match_keyword("KEINE ZEIT", PROFIL_EINWAENDE)
        assert result is not None
        assert result['keyword'] == 'keine_zeit'

    def test_mixed_case_matcht(self):
        result = match_keyword("Zu Teuer fuer uns", PROFIL_EINWAENDE)
        assert result is not None
        assert result['keyword'] == 'zu_teuer'

    def test_kleinschreibung_kategorie_matcht(self):
        """Profile-Match ist case-insensitive fuer Feldwerte."""
        einwaende = [{'kategorie': 'PREIS', 'gegenargument': 'ROI-Argument.'}]
        result = match_keyword("Das ist zu teuer", einwaende)
        assert result is not None
