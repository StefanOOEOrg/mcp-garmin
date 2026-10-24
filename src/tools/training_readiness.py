"""Training readiness tool backed by garmin_client/garth."""
import dataclasses
import logging
import json
from datetime import date
from typing import Annotated
from pydantic import BaseModel, Field
from mcp.server.mcpserver.exceptions import ToolError
from garth.exc import GarthException
import garmin_client
from tools._shared import NIGHT_DATE_DESCRIPTION, no_night_data
from server_instance import server

log = logging.getLogger(__name__)

class TrainingReadinessSummary(BaseModel):
    """Pydantic model representing a training readiness summary from Garmin."""
    calendar_date: str = Field(
        description="ISO 8601 calendar date the training readiness score applies to."
    )
    level: str = Field(
        description="Overall training readiness level, e.g. MODERATE."
    )
    feedback_short: str = Field(
        description="Garmin's short textual feedback code for the reading."
    )
    score: int = Field(
        description="Overall training readiness score (unitless, 0-100)."
    )
    sleep_score: int | None = Field(
        description="Garmin sleep score contributing to readiness, 0-100, if measured."
    )
    sleep_score_factor_feedback: str = Field(
        description="Qualitative label for the sleep score factor, e.g. MODERATE."
    )
    recovery_time: float | None = Field(
        description="Recommended recovery time, in minutes, if measured."
    )
    recovery_time_factor_percent: int = Field(
        description="Contribution of recovery time to the score, as a percentage."
    )
    recovery_time_factor_feedback: str = Field(
        description="Qualitative label for the recovery time factor, e.g. GOOD."
    )
    acwr_factor_percent: int = Field(
        description="Contribution of the acute:chronic workload ratio, as a percentage."
    )
    acwr_factor_feedback: str = Field(
        description="Qualitative label for the acute:chronic workload ratio factor."
    )
    acute_load: int = Field(
        description="Acute training load score (unitless)."
    )
    stress_history_factor_percent: int = Field(
        description="Contribution of stress history to the score, as a percentage."
    )
    stress_history_factor_feedback: str = Field(
        description="Qualitative label for the stress history factor, e.g. GOOD."
    )
    hrv_factor_percent: int = Field(
        description="Contribution of heart rate variability to the score, as a percentage."
    )
    hrv_factor_feedback: str = Field(
        description="Qualitative label for the HRV factor, e.g. GOOD."
    )
    hrv_weekly_average: int = Field(
        description="Weekly average heart rate variability, in milliseconds."
    )
    sleep_history_factor_percent: int = Field(
        description="Contribution of sleep history to the score, as a percentage."
    )
    sleep_history_factor_feedback: str = Field(
        description="Qualitative label for the sleep history factor, e.g. MODERATE."
    )

@server.tool()
def get_training_readiness_summary(
    target_date: Annotated[
        date, Field(description=NIGHT_DATE_DESCRIPTION)
    ]
) -> TrainingReadinessSummary:
    """Tool to retrieve the most recent training readiness summary for a specific date."""
    try:
        readiness_data = garmin_client.get_training_readiness_data(target_date)
        if not readiness_data:
            raise ToolError(no_night_data("training readiness data", target_date))

        # Garmin recalculates readiness several times a day; verified live against
        # a 3-entry response that index 0 is the newest (descending by timestamp).
        raw = dataclasses.asdict(readiness_data[0])
        log.debug("Raw training readiness data: %s", json.dumps(raw, indent=2, default=str))

        calendar_date = raw.get("calendar_date")
        result = {
            "calendar_date": calendar_date.isoformat() if calendar_date else "unknown",
            "level": raw.get("level", "UNKNOWN"),
            "feedback_short": raw.get("feedback_short", "UNKNOWN"),
            "score": raw.get("score", 0),
            "sleep_score": raw.get("sleep_score"),
            "sleep_score_factor_feedback": raw.get("sleep_score_factor_feedback", "UNKNOWN"),
            "recovery_time": raw.get("recovery_time"),
            "recovery_time_factor_percent": raw.get("recovery_time_factor_percent", 0),
            "recovery_time_factor_feedback": raw.get("recovery_time_factor_feedback", "UNKNOWN"),
            "acwr_factor_percent": raw.get("acwr_factor_percent", 0),
            "acwr_factor_feedback": raw.get("acwr_factor_feedback", "UNKNOWN"),
            "acute_load": raw.get("acute_load", 0),
            "stress_history_factor_percent": raw.get("stress_history_factor_percent", 0),
            "stress_history_factor_feedback": raw.get(
                "stress_history_factor_feedback", "UNKNOWN"
            ),
            "hrv_factor_percent": raw.get("hrv_factor_percent", 0),
            "hrv_factor_feedback": raw.get("hrv_factor_feedback", "UNKNOWN"),
            "hrv_weekly_average": raw.get("hrv_weekly_average", 0),
            "sleep_history_factor_percent": raw.get("sleep_history_factor_percent", 0),
            "sleep_history_factor_feedback": raw.get(
                "sleep_history_factor_feedback", "UNKNOWN"
            ),
        }
        return TrainingReadinessSummary(**result)
    except GarthException as exc:
        raise ToolError(f"Garth error getting training readiness data: {exc}") from exc

# Sample payloads of this endpoint: docs/samples/training_readiness.md
