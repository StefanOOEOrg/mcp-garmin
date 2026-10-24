# Sample payloads: calories.py

======== daily summary sample (calorie fields only, anonymized) ========
call: garth.connectapi("/usersummary-service/usersummary/daily/?calendarDate=2026-10-02")
=========================================================================
  "calendarDate": "2026-10-02",
  "totalKilocalories": 2612.0,
  "activeKilocalories": 370.0,
  "bmrKilocalories": 2242.0,
  "wellnessKilocalories": 2612.0,
  "netCalorieGoal": 2000,
  "restingCaloriesFromActivity": 119.0,
  "durationInMilliseconds": 86400000
today at 15:20 (open day): bmr 1425, active 340, duration 55200000 ms
  -> 1425 / 15.33 h * 24 h + 340 = 2570 (watch showed 2571)
