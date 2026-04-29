"""
tests/test_profile_schema_v3.py
Phase 08.19.1: Verifikation ProfileSchema v3 (extra='forbid') + _migrate_profile_data v2->v3

Test-Kategorien:
  A) extra='forbid' Enforcement (unbekannte Keys werden abgelehnt)
  B) _migrate_profile_data v2->v3 Semantik (D-02 Merge-Logik)
  C) Lokale Profil-Validierung (alle DB-Profile durchlaufen ProfileSchema ohne Fehler)
"""
import json
import os
import sys

import pytest
from pydantic import ValidationError

# Sicherstellen dass das Projektverzeichnis im Pfad ist
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.profile_schema import (
    ProfileSchema,
    BasisSchema,
    KiSchema,
    ZielgruppeSchema,
    ProfileReadSchema,
    _migrate_profile_data,
)


# ── A) extra='forbid' Enforcement ────────────────────────────────────────────

class TestExtraForbid:
    def test_profileschema_rejects_unknown_toplevel_key(self):
        """ProfileSchema muss unbekannte Top-Level-Keys ablehnen."""
        with pytest.raises(ValidationError) as exc_info:
            ProfileSchema.model_validate({'schema_version': 3, 'unbekannter_key': 'test'})
        assert 'unbekannter_key' in str(exc_info.value)

    def test_basisschema_rejects_unknown_key(self):
        """BasisSchema muss unbekannte Keys ablehnen (Sub-Schema strict)."""
        with pytest.raises(ValidationError):
            BasisSchema.model_validate({'unbekannter_basis_key': 'x'})

    def test_kischema_rejects_unknown_key(self):
        """KiSchema muss unbekannte Keys ablehnen."""
        with pytest.raises(ValidationError):
            KiSchema.model_validate({'anrede': 'Sie', 'unbekannt': 'x'})

    def test_profilereadschema_accepts_unknown_key(self):
        """ProfileReadSchema bleibt permissiv (extra='ignore') — Read-Pfad."""
        result = ProfileReadSchema.model_validate({
            'schema_version': 3,
            'unbekannter_key': 'x',
            'noch_ein_key': [1, 2, 3],
        })
        assert result.schema_version == 3

    def test_minimal_valid_profileschema(self):
        """Minimales gueltiges ProfileSchema (nur schema_version) muss durchgehen."""
        result = ProfileSchema.model_validate({'schema_version': 3})
        assert result.schema_version == 3

    def test_profileschema_with_known_keys_validates(self):
        """Vollstaendiges gueltiges Profil-Dict muss ohne Fehler validieren."""
        valid_data = {
            'schema_version': 3,
            'einwaende': [{'einwand': 'Zu teuer', 'gegenargument': 'ROI'}],
            'phasen': [{'name': 'Opening'}],
            'basis': {'unternehmen': 'Testfirma', 'produktbeschreibung': 'SaaS'},
            'ki': {'anrede': 'Sie', 'ton': 'professionell'},
        }
        result = ProfileSchema.model_validate(valid_data)
        assert result.schema_version == 3
        assert len(result.einwaende) == 1


# ── B) _migrate_profile_data v2->v3 Semantik ─────────────────────────────────

class TestMigrateV3:
    def test_basis_einwaende_upward_merge_when_toplevel_absent(self):
        """basis.einwaende wird nach top-level verschoben wenn top-level fehlt."""
        daten = {'schema_version': 2, 'basis': {'einwaende': ['Test-Einwand']}}
        result = _migrate_profile_data(daten)
        assert result['einwaende'] == ['Test-Einwand']
        assert 'einwaende' not in result.get('basis', {})

    def test_basis_einwaende_not_overwritten_when_toplevel_empty_list(self):
        """Leeres top-level einwaende=[] bleibt (User-Intent 'alles geloescht')."""
        daten = {'schema_version': 2, 'basis': {'einwaende': ['A']}, 'einwaende': []}
        result = _migrate_profile_data(daten)
        assert result['einwaende'] == []

    def test_basis_einwaende_upward_merge_when_toplevel_null(self):
        """top-level einwaende=None gilt als nicht vorhanden — basis.* wird hochgezogen."""
        daten = {'schema_version': 2, 'basis': {'einwaende': ['B']}, 'einwaende': None}
        result = _migrate_profile_data(daten)
        assert result['einwaende'] == ['B']

    def test_phasen_upward_merge(self):
        """basis.phasen wird nach top-level verschoben wenn top-level fehlt."""
        daten = {'schema_version': 2, 'basis': {'phasen': [{'name': 'Opening'}]}}
        result = _migrate_profile_data(daten)
        assert result['phasen'] == [{'name': 'Opening'}]
        assert 'phasen' not in result.get('basis', {})

    def test_fragen_key_removed(self):
        """fragen-Key wird aus daten entfernt (war gesetzt auf [] in 08.19.3)."""
        daten = {'schema_version': 2, 'fragen': []}
        result = _migrate_profile_data(daten)
        assert 'fragen' not in result

    def test_branche_toplevel_removed(self):
        """branche top-level wird entfernt (lebt auf Profile.branche DB-Column)."""
        daten = {'schema_version': 2, 'branche': 'saas_b2b'}
        result = _migrate_profile_data(daten)
        assert 'branche' not in result

    def test_schema_version_bumped_to_3(self):
        """schema_version wird auf 3 gesetzt."""
        daten = {'schema_version': 2}
        result = _migrate_profile_data(daten)
        assert result['schema_version'] == 3

    def test_idempotent_v3(self):
        """v3-Profile werden unveraendert zurueckgegeben (Idempotenz)."""
        daten = {'schema_version': 3, 'einwaende': ['X'], 'phasen': [{'name': 'Test'}]}
        result = _migrate_profile_data(daten)
        assert result == daten

    def test_toplevel_einwaende_wins_over_basis(self):
        """Wenn top-level einwaende vorhanden: basis.einwaende wird gedroppt (top-level gewinnt)."""
        daten = {
            'schema_version': 2,
            'einwaende': ['Top-Level'],
            'basis': {'einwaende': ['Basis-Wert']},
        }
        result = _migrate_profile_data(daten)
        assert result['einwaende'] == ['Top-Level']
        assert 'einwaende' not in result.get('basis', {})

    def test_real_drift_profile_basis_einwaende(self):
        """Simuliert Drift-Profil wie in Production: einwaende noch in basis.einwaende.

        Synthetisches Fixture: lokale DB-Profile sind bereits v3 (nach Batch-Migration Plan-04),
        keines hat mehr basis.einwaende. Dieses Fixture deckt den KEY-FINDINGS.md Drift-Fall ab.
        einwaende als List[dict] — kanonisches Format seit Phase 08 (Editor schreibt Dicts).
        """
        einwaende_dicts = [
            {'einwand': 'Zu teuer', 'gegenargument': 'ROI in 3 Monaten'},
            {'einwand': 'Kein Budget', 'gegenargument': 'Flexibles Pricing'},
        ]
        daten = {
            'schema_version': 2,
            'basis': {
                'unternehmen': 'Drift-Testfirma',
                'einwaende': einwaende_dicts,  # Drift: noch in basis
            }
        }
        result = _migrate_profile_data(daten)
        assert result['einwaende'] == einwaende_dicts
        assert 'einwaende' not in result.get('basis', {})
        ProfileSchema.model_validate(result)  # Muss gegen strict-Schema validieren


# ── C) Lokale Profil-Validierung ──────────────────────────────────────────────

class TestLocalProfileValidation:
    """Alle lokalen Profile durchlaufen nach Migration ProfileSchema ohne Fehler.

    HINWEIS: Diese Tests erfordern eine lokale DB-Verbindung.
    Werden bei fehlendem DB-File uebersprungen (pytest.mark.skipif).
    """

    @pytest.fixture
    def local_profiles(self):
        """Laedt alle lokalen Profile aus der Dev-DB."""
        db_path = os.path.join(os.path.dirname(__file__), '..', 'database', 'salesnerve.db')
        if not os.path.exists(db_path):
            pytest.skip("Lokale DB nicht gefunden — Test uebersprungen")
        from database.db import get_session
        from database.models import Profile
        db = get_session()
        try:
            profiles = db.query(Profile).all()
            result = []
            for p in profiles:
                try:
                    daten = json.loads(p.daten) if p.daten else {}
                except Exception:
                    daten = {}
                result.append((p.id, p.name, daten))
            return result
        finally:
            db.close()

    def test_all_local_profiles_validate_after_migration(self, local_profiles):
        """Alle lokalen Profile durchlaufen ProfileSchema.model_validate() nach v3-Migration."""
        errors = []
        for pid, pname, daten in local_profiles:
            migrated = _migrate_profile_data(daten.copy())
            try:
                ProfileSchema.model_validate(migrated)
            except ValidationError as e:
                errors.append(f"Profil {pid} ({pname[:30]}): {e.error_count()} Fehler — {e.errors()[0]}")
        assert not errors, f"Validation-Fehler in {len(errors)} Profilen:\n" + "\n".join(errors)

    def test_all_local_profiles_have_v3_after_migration(self, local_profiles):
        """Nach Migration haben alle Profile schema_version=3."""
        for pid, pname, daten in local_profiles:
            migrated = _migrate_profile_data(daten.copy())
            assert migrated.get('schema_version') == 3, (
                f"Profil {pid} hat schema_version={migrated.get('schema_version')} nach Migration"
            )


# ── D) F1: ki.sensitivitaet entfernen ────────────────────────────────────────

class TestF1KiSensitivitaet:
    def test_migration_drops_ki_sensitivitaet(self):
        """ki.sensitivitaet wird in v2->v3 Migration entfernt (Phase 08.19.2 Entscheidung)."""
        daten = {'schema_version': 2, 'ki': {'sensitivitaet': 'hoch', 'ton': 'sachlich'}}
        result = _migrate_profile_data(daten)
        assert 'sensitivitaet' not in result.get('ki', {})
        assert result.get('ki', {}).get('ton') == 'sachlich'  # ton bleibt

    def test_kischema_rejects_sensitivitaet(self):
        """KiSchema wirft ValidationError bei sensitivitaet (extra='forbid')."""
        with pytest.raises(ValidationError):
            KiSchema.model_validate({'anrede': 'Sie', 'sensitivitaet': 'x'})


# ── E) F3: ZielgruppeSchema Legacy-Felder entfernen ──────────────────────────

class TestF3ZielgruппeLegacy:
    def test_migration_drops_zielgruppe_legacy_keys(self):
        """zielgruppe.position/unternehmen/branche werden in v2->v3 Migration entfernt."""
        daten = {
            'schema_version': 2,
            'zielgruppe': {'position': 'CEO', 'unternehmen': 'KMU', 'branche': 'IT', 'berufsstatus': 'angestellt'}
        }
        result = _migrate_profile_data(daten)
        zg = result.get('zielgruppe', {})
        assert 'position' not in zg
        assert 'unternehmen' not in zg
        assert 'branche' not in zg
        assert zg.get('berufsstatus') == 'angestellt'  # berufsstatus bleibt

    def test_zielgruppeschema_rejects_position(self):
        with pytest.raises(ValidationError):
            ZielgruppeSchema.model_validate({'position': 'CEO'})

    def test_zielgruppeschema_rejects_unternehmen(self):
        with pytest.raises(ValidationError):
            ZielgruppeSchema.model_validate({'unternehmen': 'KMU'})

    def test_zielgruppeschema_rejects_branche(self):
        with pytest.raises(ValidationError):
            ZielgruppeSchema.model_validate({'branche': 'IT'})


# ── F) F4: ProfileSchema.produkt entfernen + Migration merge ─────────────────

class TestF4Produkt:
    def test_migration_merges_produkt_when_basis_empty(self):
        """produkt wird in basis.produktbeschreibung gerettet wenn dort leer."""
        daten = {'schema_version': 2, 'produkt': 'CRM-Tool', 'basis': {'produktbeschreibung': ''}}
        result = _migrate_profile_data(daten)
        assert 'produkt' not in result
        assert result.get('basis', {}).get('produktbeschreibung') == 'CRM-Tool'

    def test_migration_drops_produkt_when_basis_filled(self):
        """produkt wird gedroppt (kein Overwrite) wenn basis.produktbeschreibung bereits gesetzt."""
        daten = {'schema_version': 2, 'produkt': 'X', 'basis': {'produktbeschreibung': 'Y'}}
        result = _migrate_profile_data(daten)
        assert 'produkt' not in result
        assert result.get('basis', {}).get('produktbeschreibung') == 'Y'

    def test_profileschema_rejects_produkt(self):
        """ProfileSchema wirft ValidationError bei produkt-Key (extra='forbid')."""
        with pytest.raises(ValidationError):
            ProfileSchema.model_validate({'schema_version': 3, 'produkt': 'x'})
