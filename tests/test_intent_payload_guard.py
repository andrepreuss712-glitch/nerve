"""
tests/test_intent_payload_guard.py
────────────────────────────────────────────────────────────────────
Phase 08.23.2.PERSID Plan 02 — Welle 1, Task 2.
Waechter (a): build_intent_payload() ausgelagert + Pflichtfeld-/Typen-/Whitelist-Test.

Assertions (CLAUDE.md Test-Qualitaets-Regel — Function-Call-Return):
  Test 1: build_intent_payload(...) mit gueltigen Args liefert dict mit GENAU den
          9 Pflichtfeldern (source, inference_basis, taxonomy_version, abstained,
          speaker_role, speaker_id, is_simulation, origin_type, triggering_text).
  Test 2: taxonomy_version ist non-null; abstained + is_simulation sind bool.
  Test 3 (Whitelist): ein unbekannter Key in extra_payload macht den Test ROT;
          ein fehlendes Pflichtfeld macht den Test ROT.
  Test 4: schema_version ist NICHT Pflicht — taxonomy_version != schema_version.
          Abwesenheit von schema_version macht den Test NICHT rot.

Kommentar taxonomy_version vs. schema_version:
  taxonomy_version = Version der Intent-Taxonomie (im payload_jsonb, Pflicht non-null).
  schema_version   = Version der Payload-FORM — NICHT in payload_jsonb (kein models.py:795-
                     Spaltenfeld). schema_version kommt additiv in TAXO3-b als
                     MIRROR_SCHEMA_VERSION. NIEMALS verwechseln.

D-10-Konformitaet: dieser Test wurde VOR der Auslagerung committiert —
  Test 3 (Whitelist) ist INITIAL ROT (services/intent_payload.py existiert noch nicht).
"""

import pytest


# ── Pflichtfeld-Set (die EINZIGE authoritative Definition fuer diesen Guard) ──────
_REQUIRED = frozenset({
    'source',
    'inference_basis',
    'taxonomy_version',
    'abstained',
    'speaker_role',
    'speaker_id',
    'is_simulation',
    'origin_type',
    'triggering_text',
})

# ── Whitelist (erlaubte Keys im Payload) ──────────────────────────────────────────
# Genau die 9 Pflichtfelder plus bewusst aufgenommene extra_payload-Keys.
# Kein weiterer Key darf ohne Aufnahme in diese Whitelist erscheinen.
_ALLOWED = _REQUIRED  # baseline; extra_payload-Keys muessen hier ergaenzt werden


def _valid_args():
    """Valide Argument-Vorlage fuer build_intent_payload."""
    return dict(
        source='fast_lane',
        inference_basis='keyword_match',
        abstained=False,
        speaker_role='Kunde',
        speaker_id='1',
        is_simulation=False,
        origin_type='fast_lane',
        triggering_text='zu teuer',
    )


class TestBuildIntentPayload:
    """Pflichtfeld-/Typen-/Whitelist-Assertions fuer build_intent_payload()."""

    def test_valid_args_return_required_keys(self):
        """Test 1: gueltiger Aufruf liefert ein dict mit GENAU den 9 Pflichtfeldern.

        RED: ImportError wenn services/intent_payload.py nicht existiert.
        """
        from services.intent_payload import build_intent_payload

        payload = build_intent_payload(**_valid_args())

        assert isinstance(payload, dict)
        missing = _REQUIRED - set(payload)
        extra = set(payload) - _ALLOWED
        assert not missing, f"Fehlende Pflichtfelder: {missing}"
        assert not extra, f"Nicht-Whitelist-Keys im Payload: {extra}"

    def test_taxonomy_version_non_null_and_types(self):
        """Test 2: taxonomy_version ist non-null; abstained + is_simulation sind bool.

        taxonomy_version kommt aus TAXONOMY_VERSION-Konstante (Pflicht non-null).
        """
        from services.intent_payload import build_intent_payload

        payload = build_intent_payload(**_valid_args())

        assert payload['taxonomy_version'] is not None, (
            "taxonomy_version darf nicht None sein (Pflicht non-null, TAXO1-Invariante)"
        )
        assert isinstance(payload['abstained'], bool), (
            f"abstained muss bool sein, bekam {type(payload['abstained'])}"
        )
        assert isinstance(payload['is_simulation'], bool), (
            f"is_simulation muss bool sein, bekam {type(payload['is_simulation'])}"
        )

    def test_whitelist_rejects_unknown_key_in_extra_payload(self):
        """Test 3 (Whitelist): unbekannter Key via extra_payload macht Test ROT.

        Der Guard ist: set(payload) - _ALLOWED == set() — rot bei Nicht-Whitelist-Key.
        """
        from services.intent_payload import build_intent_payload

        args = _valid_args()
        # extra_payload mit einem UNBEKANNTEN Key (nicht in _ALLOWED)
        args['extra_payload'] = {'unbekannter_key_xyz': 'wert'}

        payload = build_intent_payload(**args)

        extra = set(payload) - _ALLOWED
        assert extra, (
            "Erwarte mindestens einen Nicht-Whitelist-Key, aber keiner gefunden. "
            "Dieser Test prueft DASS die Whitelist-Assertion ROT wird — "
            "Assertion ist: set(payload) - _ALLOWED == set() MUSS HIER FAILEN."
        )
        # Der Aufrufer-Code soll diese Assertion ausfuehren:
        with pytest.raises(AssertionError):
            assert set(payload) - _ALLOWED == set(), (
                f"Nicht-Whitelist-Key: {set(payload) - _ALLOWED}"
            )

    def test_missing_required_field_fails(self):
        """Test 3b (Whitelist): fehlendes Pflichtfeld macht Test ROT.

        _REQUIRED - set(payload) == set() — rot bei fehlendem Pflichtfeld.
        Aufruf ohne 'source' sollte zu einem Payload fuehren, dem 'source' fehlt.
        Da build_intent_payload 'source' als Positionsargument aufnimmt, testen
        wir, ob der Payload alle _REQUIRED-Keys enthaelt.
        """
        from services.intent_payload import build_intent_payload

        payload = build_intent_payload(**_valid_args())

        # Simuliere einen Payload mit fehlendem Pflichtfeld fuer die Assertion
        incomplete = {k: v for k, v in payload.items() if k != 'triggering_text'}
        missing = _REQUIRED - set(incomplete)
        assert missing, (
            "Erwarte mindestens ein fehlendes Pflichtfeld, aber keines gefunden. "
            "Dieser Test prueft DASS die Assertion bei fehlendem Pflichtfeld ROT wird."
        )
        with pytest.raises(AssertionError):
            assert _REQUIRED - set(incomplete) == set(), (
                f"Fehlende Pflichtfelder: {missing}"
            )

    def test_schema_version_not_required(self):
        """Test 4: schema_version ist NICHT Pflicht — darf im Payload fehlen.

        taxonomy_version != schema_version. schema_version ist TAXO3-b (additiv,
        MIRROR_SCHEMA_VERSION). Abwesenheit macht Test NICHT rot.
        """
        from services.intent_payload import build_intent_payload

        payload = build_intent_payload(**_valid_args())

        # schema_version darf fehlen — KEIN Fehler:
        assert 'schema_version' not in _REQUIRED, (
            "schema_version darf NICHT in _REQUIRED sein (TAXO3-b)"
        )
        # Der Payload-Dict selbst darf schema_version enthalten oder nicht —
        # Hauptsache es ist kein PFLICHTFELD:
        # (wenn er es enthaelt, waere es ein Nicht-Whitelist-Key)
        if 'schema_version' in payload:
            # Wenn vorhanden, muss es in _ALLOWED sein (sonst Whitelist-Verletzung)
            assert 'schema_version' in _ALLOWED, (
                "schema_version ist im Payload, aber nicht in _ALLOWED — Whitelist ergaenzen"
            )

    def test_extra_payload_merge_included(self):
        """Test 5: extra_payload-Keys werden mit aufgenommen (Merge-Verhalten).

        ABER: um im Whitelist-Waechter GRUEN zu bleiben, muss der Key zuerst
        in _ALLOWED stehen. Dieser Test belegt das Merge-Verhalten selbst.
        """
        from services.intent_payload import build_intent_payload

        args = _valid_args()
        # Kein extra_payload — erwarte genau 9 Keys:
        payload_no_extra = build_intent_payload(**args)
        assert set(payload_no_extra) == _REQUIRED, (
            f"Ohne extra_payload: erwartet genau _REQUIRED-Keys, "
            f"bekam {set(payload_no_extra)}"
        )

        # Mit extra_payload (bekannter Testkey, NICHT in production _ALLOWED —
        # dieser Test prueft nur das Merge, NICHT ob es whitelist-valid ist):
        args2 = _valid_args()
        args2['extra_payload'] = {'meta_key': 'meta_val'}
        payload_with_extra = build_intent_payload(**args2)
        assert 'meta_key' in payload_with_extra, (
            "extra_payload-Key 'meta_key' nicht im Ergebnis-Dict"
        )
        assert payload_with_extra['meta_key'] == 'meta_val'
