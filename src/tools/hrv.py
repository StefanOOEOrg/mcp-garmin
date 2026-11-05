"""HRV summary tool backed by garmin_client/garth."""
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

class HRVSummary(BaseModel):
    """Pydantic model representing a heart rate variability (HRV) summary from Garmin."""
    hrv_sleep_start: str = Field(description="ISO 8601 timestamp when sleep started.")
    hrv_sleep_end: str = Field(description="ISO 8601 timestamp when sleep ended.")
    hrv_feedback: str = Field(description="Garmin's textual feedback code for the HRV measurement.")
    hrv_last_night_avg: float | None = Field(
        description="Average HRV value from the last night (ms); None if Garmin has no value.")
    hrv_weekly_avg: float | None = Field(
        description="Average HRV value over the last week (ms); None if Garmin has no value.")

@server.tool()
def get_hrv_summary(
    target_date: Annotated[
        date, Field(description=NIGHT_DATE_DESCRIPTION)
    ]
) -> HRVSummary:
    """Tool to retrieve heart rate variability (HRV) summary data for a specific date."""
    try:
        hrv_data = garmin_client.get_hrv_data(target_date)
        if hrv_data is None:
            raise ToolError(no_night_data("HRV data", target_date))

        raw = dataclasses.asdict(hrv_data)
        log.debug("Raw HRV data: %s", json.dumps(raw, indent=2, default=str))

        summary = raw.get("hrv_summary") or {}
        result = {
            "hrv_sleep_start": local_iso(raw.get("sleep_start_timestamp_local")),
            "hrv_sleep_end": local_iso(raw.get("sleep_end_timestamp_local")),
            "hrv_feedback": summary.get("status") or "unknown",
            "hrv_last_night_avg": summary.get("last_night_avg"),
            "hrv_weekly_avg": summary.get("weekly_avg"),
        }

        return HRVSummary(**result)
    except GarthException as exc:
        raise ToolError(f"Garth error getting HRV data: {exc}") from exc
