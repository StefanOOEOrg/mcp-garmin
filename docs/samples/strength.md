# Sample payloads: strength.py

============= sample exercise sets data from garth (strength session, shortened)=============
{
 "activityId": 12345678903,
 "exerciseSets": [
  {
   "exercises": [{"category": "SQUAT", "name": "BARBELL_BACK_SQUAT", "probability": 100.0}],
   "duration": 48.601,
   "repetitionCount": 8,
   "weight": 40000.0,                    <- grams
   "setType": "ACTIVE",
   "startTime": "2026-01-15T09:02:00.0", <- UTC, shifted to local via _utc_offset
   "wktStepIndex": null,
   "messageIndex": null,
   "avgConcentricMeanVelocity": null,    <- ~20 velocity-based-training fields,
   ...                                      all null without a velocity sensor
  },
  {
   "exercises": [],
   "duration": 84.11,
   "repetitionCount": null,
   "weight": -1.0,
   "setType": "REST",
   "startTime": null,
   ...
  }
 ]
}
Non-strength activities (e.g. cycling) return {"activityId": ..., "exerciseSets": null}.
============= end sample exercise sets data from garth (strength session)=============
