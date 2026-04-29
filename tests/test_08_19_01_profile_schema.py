"""
tests/test_08_19_01_profile_schema.py
──────────────────────────────────────────────────────────────────────
Phase 08.19 Plan 01 — TDD Tests fuer services/profile_schema.py

Tests pruefen Runtime-Verhalten (Instanziierung, Validation, Migration),
keine Source-Presence-Tests.
"""
from __future__ import annotations

import typing

import pytest


# ── Imports werden erst in den Tests gemacht, damit RED-Phase korrekt
#    mit ImportError fehlschlaegt wenn Datei fehlt. ──────────────────


class TestProfileSchemaImport:
    """Test 1: ProfileSchema instanziierbar mit Default-Werten."""

    def test_import_ok(self):
        from services.profile_schema import ProfileSchema, ProfileReadSchema, _migrate_profile_data
        assert ProfileSchema is not None
        assert ProfileReadSchema is not None
        assert callable(_migrate_profile_data)

    def test_profile_schema_default_instanziierung(self):
        from services.profile_schema import ProfileSchema
        s = ProfileSchema()
        assert s.schema_version == 2

    def test_unternehmensgroesse_enum_import(self):
        from services.profile_schema import UnternehmensgroesseEnum
        args = typing.get_args(UnternehmensgroesseEnum)
        # Test 9 (Reviews v2 Enum-Sync): exakt diese 5 Werte, keine anderen
        assert set(args) == {'<10', '10-50', '50-250', '250-1000', '1000+'}
        assert len(args) == 5


class TestMigrateProfileData:
    """Tests fuer _migrate_profile_data() Funktion."""

    def test_entfernt_opener(self):
        """Test 3: opener wird entfernt (D-01). pitch bleibt (transitional dual-write)."""
        from services.profile_schema import _migrate_profile_data
        result = _migrate_profile_data({'opener': 'X', 'pitch': 'Y'})
        assert 'opener' not in result
        # pitch bleibt als transitional dual-write bis 08.20

    def test_entfernt_b2c_felder_behaelt_vorwissen(self):
        """Test 4: alter entfernt, vorwissen bleibt."""
        from services.profile_schema import _migrate_profile_data
        result = _migrate_profile_data({
            'zielgruppe': {'alter': '28', 'vorwissen': 'hoch'}
        })
        zg = result.get('zielgruppe', {})
        assert 'alter' not in zg
        assert zg.get('vorwissen') == 'hoch'

    def test_migration_hebt_auf_v3(self):
        """Test 5: schema_version=2 wird auf v3 migriert (Phase 08.19.1)."""
        from services.profile_schema import _migrate_profile_data
        original = {'schema_version': 2, 'basis': {'produktbeschreibung': 'Test'}}
        result = _migrate_profile_data(original.copy())
        assert result.get('schema_version') == 3

    def test_setzt_schema_version_bei_leerem_dict(self):
        """Test 6: leeres Dict bekommt schema_version=3 (v1->v2->v3 Pipeline)."""
        from services.profile_schema import _migrate_profile_data
        result = _migrate_profile_data({})
        assert result.get('schema_version') == 3

    def test_migration_setzt_schema_version(self):
        """_migrate_profile_data setzt schema_version=3 (v2->v3 in Phase 08.19.1)."""
        from services.profile_schema import _migrate_profile_data
        result = _migrate_profile_data({'opener': 'Hallo'})
        assert result['schema_version'] == 3
        assert 'opener' not in result

    def test_erlaubnis_transitional(self):
        """erlaubnis bleibt als transitional dual-write bis 08.20 (wird nicht entfernt)."""
        from services.profile_schema import _migrate_profile_data
        result = _migrate_profile_data({'erlaubnis': True})
        # erlaubnis wird NICHT entfernt — transitional bis Phase 08.20
        # ProfileSchema hat kein erlaubnis-Feld, daher kommt es nie durch model_validate
        assert result.get('schema_version') == 3

    def test_ki_stil_wird_in_ton_gemergt(self):
        """ki.stil wandert in ki.ton, stil wird entfernt."""
        from services.profile_schema import _migrate_profile_data
        result = _migrate_profile_data({'ki': {'stil': 'direkt', 'ton': ''}})
        ki = result.get('ki', {})
        assert ki.get('ton') == 'direkt'
        assert 'stil' not in ki

    def test_ki_stil_ueberschreibt_nicht_vorhandenes_ton(self):
        """ki.stil ueberschreibt NICHT wenn ki.ton bereits gesetzt."""
        from services.profile_schema import _migrate_profile_data
        result = _migrate_profile_data({'ki': {'stil': 'direkt', 'ton': 'sachlich'}})
        ki = result.get('ki', {})
        assert ki.get('ton') == 'sachlich'  # ton bleibt unveraendert

    def test_entfernt_schmerzen_trigger(self):
        """schmerzen.trigger wird entfernt (D-06)."""
        from services.profile_schema import _migrate_profile_data
        result = _migrate_profile_data({
            'schmerzen': {'trigger': 'Preis', 'schmerzpunkte': [{'schmerz': 'x'}]}
        })
        schmerzen = result.get('schmerzen', {})
        assert 'trigger' not in schmerzen
        assert schmerzen.get('schmerzpunkte') == [{'schmerz': 'x'}]

    def test_idempotent_zweiter_aufruf(self):
        """Zweiter Aufruf auf schema_version=2-Dict aendert nichts."""
        from services.profile_schema import _migrate_profile_data
        d = {'schema_version': 2, 'basis': {}, 'ki': {'ton': 'sachlich'}}
        d_after_first = _migrate_profile_data(d.copy())
        d_after_second = _migrate_profile_data(d_after_first.copy())
        assert d_after_first == d_after_second


class TestProfileSchemaValidation:
    """Test 7+8: ProfileSchema/ProfileReadSchema Validierung."""

    def test_model_validate_mit_neuen_feldern(self):
        """Test 7: ProfileReadSchema.model_validate mit neuen Feldern ohne Fehler."""
        from services.profile_schema import ProfileReadSchema
        data = {
            'schema_version': 2,
            'basis': {'produktbeschreibung': 'Test'},
            'zielkunde': {'unternehmensgroesse': '<10'}
        }
        ps = ProfileReadSchema.model_validate(data)
        assert ps.zielkunde.unternehmensgroesse == '<10'

    def test_unternehmensgroesse_ungueltig_schlaegt_fehl(self):
        """Test 8: Ungueltige unternehmensgroesse schlaegt beim Write-Schema fehl."""
        from services.profile_schema import ProfileSchema
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ProfileSchema(
                schema_version=2,
                zielkunde={'unternehmensgroesse': '9999'}
            )

    def test_read_schema_ignoriert_unbekannte_felder(self):
        """ProfileReadSchema.model_validate ignoriert unbekannte Felder (extra='ignore')."""
        from services.profile_schema import ProfileReadSchema
        # Darf KEINE Exception werfen
        ps = ProfileReadSchema.model_validate({
            'schema_version': 2,
            'UNBEKANNTES_FELD': 'X',
            'noch_ein_fremdes_feld': 42
        })
        assert ps.schema_version == 2

    def test_write_schema_wirft_bei_unbekannten_feldern(self):
        """ProfileSchema (extra='forbid') wirft ValidationError bei unbekannten Feldern.
        Phase 08.19.1 Plan-05: extra='forbid' aktiviert nach Schema-Kalibrierung + v3-Migration.
        """
        from services.profile_schema import ProfileSchema
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ProfileSchema(**{'schema_version': 3, 'UNGUELTIG': 'X'})

    def test_profile_schema_alle_pflicht_felder_vorhanden(self):
        """ProfileSchema hat alle 6 neuen Felder aus D-07."""
        from services.profile_schema import ProfileSchema
        s = ProfileSchema()
        # Neue B2B-Felder in zielkunde
        assert hasattr(s.zielkunde, 'unternehmensgroesse')
        assert hasattr(s.zielkunde, 'buying_committee')
        assert hasattr(s.zielkunde, 'statusquo')
        assert hasattr(s.zielkunde, 'zeithorizont')
        # value.roi_argumente
        assert hasattr(s.value, 'roi_argumente')
        # einwaende_detail (EinwandDetailSchema mit einwand_typ)
        assert hasattr(s, 'einwaende_detail')

    def test_eliminierte_felder_nicht_im_schema(self):
        """Eliminierte Felder sind NICHT im ProfileSchema (D-06)."""
        from services.profile_schema import ProfileSchema
        s = ProfileSchema()
        # zielgruppe hat keine B2C-Felder mehr
        assert not hasattr(s.zielgruppe, 'alter')
        assert not hasattr(s.zielgruppe, 'einkommensniveau')
        assert not hasattr(s.zielgruppe, 'lebenssituation')
        # schmerzen hat kein trigger
        assert not hasattr(s.schmerzen, 'trigger')
        # ki hat kein stil
        assert not hasattr(s.ki, 'stil')
        # kein erlaubnis auf Top-Level
        assert not hasattr(s, 'erlaubnis')

    def test_training_felder_bleiben_in_zielgruppe(self):
        """zielgruppe.vorwissen und .entscheidungsverhalten bleiben erhalten (NICHT eliminiert)."""
        from services.profile_schema import ProfileSchema
        s = ProfileSchema()
        assert hasattr(s.zielgruppe, 'vorwissen')
        assert hasattr(s.zielgruppe, 'entscheidungsverhalten')

    def test_opener_pitch_nicht_im_schema(self):
        """opener und pitch sind NICHT im ProfileSchema (D-01)."""
        from services.profile_schema import ProfileSchema
        s = ProfileSchema()
        assert not hasattr(s, 'opener')
        assert not hasattr(s, 'pitch')
