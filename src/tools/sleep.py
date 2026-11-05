"""Sleep summary tool backed by garmin_client/garth."""
import dataclasses
import json
import logging
from datetime import date
from typing import Annotated

from garth.exc import GarthException
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel, Field

import garmin_client
from server_instance import server
from tools._shared import NIGHT_DATE_DESCRIPTION, local_iso, no_night_data

log = logging.getLogger(__name__)

class SleepSummary(BaseModel):
    """Pydantic model representing a sleep summary from Garmin."""
    sleep_start: str = Field(description="ISO 8601 timestamp when sleep started.")
    sleep_end: str = Field(description="ISO 8601 timestamp when sleep ended.")
    total_sleep_minutes: int = Field(description="Total time asleep, in minutes.")
    deep_sleep_minutes: int = Field(description="Minutes spent in deep sleep.")
    light_sleep_minutes: int = Field(description="Minutes spent in light sleep.")
    rem_sleep_minutes: int = Field(description="Minutes spent in REM sleep.")
    awake_minutes: int = Field(description="Minutes spent awake during the sleep window.")
    awake_count: int = Field(description="Number of times the user woke up.")
    nap_time_minutes: int = Field(description="Minutes napped, separate from main sleep.")
    overall_sleep_score: int = Field(description="Garmin overall sleep score, 0-100.")
    overall_score_label: str = Field(description="Qualitative label for the score, e.g. FAIR.")
    feedback: str = Field(description="Garmin's textual feedback code for the night.")
    sleep_score_insight: str = Field(description="Additional Garmin insight text, if any.")
    average_respiration_value: float = Field(description="Average breaths per minute.")
    lowest_respiration_value: float = Field(description="Lowest breaths per minute.")
    highest_respiration_value: float = Field(description="Highest breaths per minute.")
    lowest_sp_o2_value: int | None = Field(description="Lowest blood oxygen %, if measured.")
    highest_sp_o2_value: int | None = Field(description="Highest blood oxygen %, if measured.")

@server.tool()
def get_sleep_summary(
    target_date: Annotated[
        date, Field(description=NIGHT_DATE_DESCRIPTION)
    ]
) -> SleepSummary:
    """Tool to retrieve sleep summary data for a specific date."""
    try:
        sleep_data = garmin_client.get_sleep_data(target_date)
        if sleep_data is None:
            raise ToolError(no_night_data("sleep data", target_date))

        raw = dataclasses.asdict(sleep_data.daily_sleep_dto)
        log.debug("Raw sleep data: %s", json.dumps(raw, indent=2, default=str))

        overall_score = raw.get("sleep_scores", {}).get("overall", {})
        result = {
            "sleep_start": local_iso(raw.get("sleep_start_timestamp_local")),
            "sleep_end": local_iso(raw.get("sleep_end_timestamp_local")),
            "average_respiration_value": raw.get("average_respiration_value", 0.0),
            "lowest_respiration_value": raw.get("lowest_respiration_value", 0.0),
            "highest_respiration_value": raw.get("highest_respiration_value", 0.0),
            "overall_sleep_score": overall_score.get("value", 0),
            "awake_count": raw.get("awake_count", 0),
            "sleep_score_insight": raw.get("sleep_score_insight", "UNKNOWN"),
            "highest_sp_o2_value": raw.get("highest_sp_o2_value"),
            "lowest_sp_o2_value": raw.get("lowest_sp_o2_value"),
            "nap_time_minutes": raw.get("nap_time_seconds", 0) // 60,
            "total_sleep_minutes": raw.get("sleep_time_seconds", 0) // 60,
            "deep_sleep_minutes": raw.get("deep_sleep_seconds", 0) // 60,
            "light_sleep_minutes": raw.get("light_sleep_seconds", 0) // 60,
            "rem_sleep_minutes": raw.get("rem_sleep_seconds", 0) // 60,
            "awake_minutes": raw.get("awake_sleep_seconds", 0) // 60,
            "feedback": raw.get("sleep_score_feedback", "UNKNOWN"),
            "overall_score_label": overall_score.get("qualifier_key", "UNKNOWN"),
        }
        return SleepSummary(**result)
    except GarthException as exc:
        raise ToolError(f"Garth error getting sleep data: {exc}") from exc
