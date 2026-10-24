# Sample payloads: training_readiness.py

=========== training readiness sample data from garth ===========
call: d = garmin_client.get_training_readiness_data(date.today())
===================================================================
  TrainingReadinessData
  (
    calendar_date=datetime.date(2026, 9, 17),
    level='MODERATE',
    feedback_short='GOOD_SLEEP_HISTORY',
    score=50,
    sleep_score=62,
    sleep_score_factor_feedback='MODERATE',
    recovery_time=518.0,
    recovery_time_factor_percent=86,
    recovery_time_factor_feedback='GOOD',
    acwr_factor_percent=100,
    acwr_factor_feedback='VERY_GOOD',
    acute_load=364,
    stress_history_factor_percent=95,
    stress_history_factor_feedback='GOOD',
    hrv_factor_percent=74,
    hrv_factor_feedback='GOOD',
    hrv_weekly_average=45,
    sleep_history_factor_percent=52,
    sleep_history_factor_feedback='MODERATE',
  ),
  TrainingReadinessData(
    ...
  ),
  TrainingReadinessData(
    ...
  ),
  ...
]
=========== training readiness sample data from garth ===========
