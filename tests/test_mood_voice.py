"""Tests for mood-to-voice-settings mapping and secretary voice presets."""
import pytest


def test_mood_positiv_zone():
    from services.training_service import mood_to_voice_settings
    result = mood_to_voice_settings(5)
    assert result['stability'] == pytest.approx(0.65, abs=0.05)
    assert result['style'] == pytest.approx(0.15, abs=0.05)
    assert result['similarity_boost'] == 0.75


def test_mood_neutral_zone():
    from services.training_service import mood_to_voice_settings
    result = mood_to_voice_settings(0)
    assert result['stability'] == pytest.approx(0.50, abs=0.05)
    assert result['style'] == pytest.approx(0.00, abs=0.05)
    assert result['similarity_boost'] == 0.75


def test_mood_gereizt_zone():
    from services.training_service import mood_to_voice_settings
    result = mood_to_voice_settings(-2)
    assert result['stability'] == pytest.approx(0.35, abs=0.05)
    assert result['style'] == pytest.approx(0.45, abs=0.05)
    assert result['similarity_boost'] == 0.75


def test_mood_wuetend_zone():
    from services.training_service import mood_to_voice_settings
    result = mood_to_voice_settings(-5)
    assert result['stability'] == pytest.approx(0.20, abs=0.05)
    assert result['style'] == pytest.approx(0.70, abs=0.05)
    assert result['similarity_boost'] == 0.75


def test_boundary_plus1_is_neutral():
    from services.training_service import mood_to_voice_settings
    result = mood_to_voice_settings(1)
    assert result['stability'] == pytest.approx(0.50, abs=0.05)
    assert result['style'] == pytest.approx(0.00, abs=0.05)


def test_boundary_minus1_is_neutral():
    from services.training_service import mood_to_voice_settings
    result = mood_to_voice_settings(-1)
    assert result['stability'] == pytest.approx(0.50, abs=0.05)
    assert result['style'] == pytest.approx(0.00, abs=0.05)


def test_boundary_plus2_is_positiv():
    from services.training_service import mood_to_voice_settings
    result = mood_to_voice_settings(2)
    assert result['stability'] == pytest.approx(0.65, abs=0.05)
    assert result['style'] == pytest.approx(0.15, abs=0.05)


def test_boundary_minus3_is_gereizt():
    from services.training_service import mood_to_voice_settings
    result = mood_to_voice_settings(-3)
    assert result['stability'] == pytest.approx(0.35, abs=0.05)
    assert result['style'] == pytest.approx(0.45, abs=0.05)


def test_boundary_minus4_is_wuetend():
    from services.training_service import mood_to_voice_settings
    result = mood_to_voice_settings(-4)
    assert result['stability'] == pytest.approx(0.20, abs=0.05)
    assert result['style'] == pytest.approx(0.70, abs=0.05)


def test_every_zone_has_correct_keys():
    from services.training_service import MOOD_VOICE_ZONES
    expected_keys = {'stability', 'similarity_boost', 'style'}
    for zone_name, zone_dict in MOOD_VOICE_ZONES.items():
        assert set(zone_dict.keys()) == expected_keys, f"Zone '{zone_name}' has wrong keys: {zone_dict.keys()}"


def test_every_zone_has_similarity_boost_075():
    from services.training_service import MOOD_VOICE_ZONES
    for zone_name, zone_dict in MOOD_VOICE_ZONES.items():
        assert zone_dict['similarity_boost'] == 0.75, f"Zone '{zone_name}' similarity_boost is {zone_dict['similarity_boost']}"


def test_blockerin_voice_settings():
    from services.training_service import SEKRETAERIN_TYPES
    vs = SEKRETAERIN_TYPES['blockerin']['voice_settings']
    assert vs['stability'] == pytest.approx(0.60, abs=0.05)
    assert vs['style'] == pytest.approx(0.10, abs=0.1)  # "low"


def test_helferin_voice_settings():
    from services.training_service import SEKRETAERIN_TYPES
    vs = SEKRETAERIN_TYPES['helferin']['voice_settings']
    assert vs['stability'] == pytest.approx(0.45, abs=0.05)
    assert vs['style'] == pytest.approx(0.25, abs=0.1)  # "slightly high"


def test_abwimmlerin_voice_settings():
    from services.training_service import SEKRETAERIN_TYPES
    vs = SEKRETAERIN_TYPES['abwimmlerin']['voice_settings']
    assert vs['stability'] == pytest.approx(0.35, abs=0.05)
    assert vs['style'] == pytest.approx(0.50, abs=0.1)  # "high"


def test_all_secretary_presets_have_similarity_boost():
    from services.training_service import SEKRETAERIN_TYPES
    for typ_name, typ_data in SEKRETAERIN_TYPES.items():
        vs = typ_data['voice_settings']
        assert vs['similarity_boost'] == 0.75, f"Secretary '{typ_name}' similarity_boost is {vs['similarity_boost']}"


def test_mood_to_voice_settings_returns_copy():
    from services.training_service import mood_to_voice_settings, MOOD_VOICE_ZONES
    result = mood_to_voice_settings(0)
    result['stability'] = 999
    # Original dict must be unchanged
    assert MOOD_VOICE_ZONES['neutral']['stability'] != 999
