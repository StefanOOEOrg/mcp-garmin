"""Steps tool backed by garmin_client/garth."""
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

log = logging.getLogger(__name__)

class StepsSummary(BaseModel):
    """Pydantic model representing a daily step count summary from Garmin."""
    date: str = Field(
        description="ISO 8601 calendar date the step count applies to."
    )
    total_steps: int | None = Field(
        description="Total number of steps recorded for the day, if measured."
    )
    total_distance_meters: float | None = Field(
        description="Total distance covered by steps, in meters, if measured."
    )
    step_goal: int = Field(
        description="Daily step goal set for the day."
    )

@server.tool()
def get_steps_summary(
    target_date: Annotated[
        date, Field(description="Date in ISO 8601 format (YYYY-MM-DD), e.g. 2023-09-13")
    ],
    period: Annotated[
        int, Field(description="Number of days prior to the target date for step retrieval.")
    ]
) -> list[StepsSummary]:
    """Tool to retrieve daily step count summaries for a specific target date and a
    period of days prior to this target date."""
    try:
        steps_data = garmin_client.get_steps_data(target_date, period)

        result = []
        for entry in steps_data:
            raw = dataclasses.asdict(entry)
            log.debug("Raw steps data: %s", json.dumps(raw, indent=2, default=str))

            calendar_date = raw.get("calendar_date")
            result.append(StepsSummary(
                date=calendar_date.isoformat() if calendar_date else "unknown",
                total_steps=raw.get("total_steps"),
                total_distance_meters=raw.get("total_distance"),
                step_goal=raw.get("step_goal", 0),
            ))
        return result
    except GarthException as exc:
        raise ToolError(f"Garth error getting steps data: {exc}") from exc

# Sample payloads of this endpoint: docs/samples/steps.md
