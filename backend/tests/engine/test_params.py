"""Params are stamped onto published verdicts, so they are a contract too."""

import dataclasses

import pytest

from app.engine.params import PARAMS, PARAMS_VERSION, EngineParams


def test_params_are_frozen() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        PARAMS.match_radius_km = 99.0  # type: ignore[misc]


def test_params_version_is_stamped_and_non_empty() -> None:
    assert PARAMS_VERSION == "2026.09-v1"


def test_bible_values() -> None:
    assert (PARAMS.match_radius_km, PARAMS.visit_tolerance_min) == (0.30, 10)
    assert (PARAMS.search_window_h, PARAMS.tz) == (3, "America/New_York")
    assert (PARAMS.v_strong_kmh, PARAMS.v_moderate_kmh) == (80.0, 40.0)
    assert (PARAMS.adv_simultaneous_min, PARAMS.adv_simultaneous_km) == (5.0, 2.0)
    assert PARAMS.adv_max_per_hour == 12


def test_moderate_threshold_sits_below_strong() -> None:
    """Inverting these would silently flip every prism verdict."""
    assert EngineParams().v_moderate_kmh < EngineParams().v_strong_kmh
