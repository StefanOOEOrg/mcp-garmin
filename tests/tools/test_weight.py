"""Tests for tools.weight: field mapping from a fake Garth response to WeightSummary."""
import dataclasses
from datetime import date
from unittest.mock import patch

import garth
import pytest
from mcp.server.mcpserver.exceptions import ToolError

from tools.weight import get_weight_summary


@pytest.fixture(name="fake_weight_data")
def _build_fake_weight_data() -> garth.WeightData:
    """A minimal, realistic fake Garth WeightData response, built from real field
    values recorded during manual testing, with IDs and body data anonymized."""
    return garth.WeightData(
        weight=80000,
        date=1789540364000,
        sample_pk=1,
        calendar_date=date(2026, 9, 16),
        source_type="INDEX_SCALE",
        timestamp_gmt=1789533164000,
        weight_delta=500.0,
        bmi=24.5,
        body_fat=20.0,
        body_water=55.0,
        bone_mass=3500,
        muscle_mass=38000,
    )


@patch("garmin_client.login")
@patch("garth.WeightData.get")
def test_get_weight_summary_maps_fields(mock_weight_data_get, mock_login, fake_weight_data):
    """The happy path: Garth returns real-shaped data, and it lands correctly
    in the returned WeightSummary (grams -> kilograms, timestamp)."""
    mock_weight_data_get.return_value = fake_weight_data

    result = get_weight_summary(date(2026, 9, 16))

    assert result.date == "2026-09-16"
    assert result.timestamp == "2026-09-16T06:32:44"
    assert result.source_type == "INDEX_SCALE"
    assert result.weight_kg == pytest.approx(80.0)
    assert result.weight_delta_kg == pytest.approx(0.5)
    assert result.bmi == pytest.approx(24.5)
    assert result.body_fat_percent == 20.0
    assert result.body_water_percent == 55.0
    assert result.bone_mass_kg == pytest.approx(3.5)
    assert result.muscle_mass_kg == pytest.approx(38.0)
    assert result.physique_rating is None
    assert result.visceral_fat is None
    assert result.metabolic_age is None
    mock_login.assert_called_once()


@patch("garmin_client.login")
@patch("garth.WeightData.get")
def test_get_weight_summary_raises_tool_error_when_no_data(mock_weight_data_get, mock_login):
    """No data for the date is an anticipated failure: ToolError with a
    specific, LLM-readable message, not a generic crash."""
    mock_weight_data_get.return_value = None

    with pytest.raises(ToolError, match="No weight data found"):
        get_weight_summary(date(2026, 9, 16))
    mock_login.assert_called_once()


@dataclasses.dataclass
class _MinimalWeightData:
    """Simulates a future garth-ng version where most fields were renamed or
    removed - Garmin's API has no version field to detect this against."""
    weight: int


@patch("garmin_client.login")
@patch("garth.WeightData.get")
def test_get_weight_summary_missing_fields_fall_back_instead_of_crashing(
    mock_weight_data_get, mock_login
):
    """A field that no longer exists in the response should degrade gracefully
    (see _grams_to_kg / .get(..., default) in tools/weight.py), not crash the
    whole tool with a KeyError or AttributeError."""
    mock_weight_data_get.return_value = _MinimalWeightData(weight=80000)

    result = get_weight_summary(date(2026, 9, 16))

    assert result.weight_kg == pytest.approx(80.0)
    assert result.date == "unknown"
    assert result.timestamp == "unknown"
    assert result.source_type == "UNKNOWN"
    assert result.weight_delta_kg is None
    assert result.bmi is None
    mock_login.assert_called_once()
