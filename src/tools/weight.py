"""Weight summary tool backed by garmin_client/garth."""
import dataclasses
import logging
import json
from datetime import date
from typing import Annotated
from pydantic import BaseModel, Field
from mcp.server.mcpserver.exceptions import ToolError
from garth.exc import GarthException
import garmin_client
from server_instance import server
from tools._shared import grams_to_kg, local_iso

log = logging.getLogger(__name__)

class WeightSummary(BaseModel):
    """Pydantic model representing a weight summary from Garmin."""
    date: str = Field(
        description="ISO 8601 calendar date of the weigh-in."
    )
    timestamp: str = Field(
        description="ISO 8601 timestamp of the measurement."
    )
    source_type: str = Field(
        description="Source of the measurement, e.g. INDEX_SCALE."
    )
    weight_kg: float = Field(
        description="Body weight, in kilograms."
    )
    weight_delta_kg: float | None = Field(
        description="Change in weight since the previous measurement, in kilograms, "
                    "if measured."
    )
    bmi: float | None = Field(
        description="Body mass index (unitless), if measured."
    )
    body_fat_percent: float | None = Field(
        description="Body fat percentage, if measured."
    )
    body_water_percent: float | None = Field(
        description="Body water percentage, if measured."
    )
    bone_mass_kg: float | None = Field(
        description="Bone mass, in kilograms, if measured."
    )
    muscle_mass_kg: float | None = Field(
        description="Muscle mass, in kilograms, if measured."
    )
    physique_rating: float | None = Field(
        description="Garmin physique rating score (unitless), if measured."
    )
    visceral_fat: float | None = Field(
        description="Visceral fat rating (unitless), if measured."
    )
    metabolic_age: int | None = Field(
        description="Estimated metabolic age, in years, if measured."
    )

@server.tool()
def get_weight_summary(
    target_date: Annotated[
        date, Field(description="Date in ISO 8601 format (YYYY-MM-DD), e.g. 2023-09-13")
    ]
) -> WeightSummary:
    """Tool to retrieve weight summary data for a specific date."""
    try:
        weight_data = garmin_client.get_weight_data(target_date)
        if weight_data is None:
            raise ToolError("No weight data found for the specified date.")

        raw = dataclasses.asdict(weight_data)
        log.debug("Raw weight data: %s", json.dumps(raw, indent=2, default=str))

        calendar_date = raw.get("calendar_date")
        result = {
            "date": calendar_date.isoformat() if calendar_date else "unknown",
            "timestamp": local_iso(raw.get("timestamp_local")),
            "source_type": raw.get("source_type", "UNKNOWN"),
            "weight_kg": grams_to_kg(raw.get("weight")) or 0.0,
            "weight_delta_kg": grams_to_kg(raw.get("weight_delta")),
            "bmi": raw.get("bmi"),
            "body_fat_percent": raw.get("body_fat"),
            "body_water_percent": raw.get("body_water"),
            "bone_mass_kg": grams_to_kg(raw.get("bone_mass")),
            "muscle_mass_kg": grams_to_kg(raw.get("muscle_mass")),
            "physique_rating": raw.get("physique_rating"),
            "visceral_fat": raw.get("visceral_fat"),
            "metabolic_age": raw.get("metabolic_age"),
        }
        return WeightSummary(**result)
    except GarthException as exc:
        raise ToolError(f"Garth error getting weight data: {exc}") from exc

# Sample payloads of this endpoint: docs/samples/weight.md
