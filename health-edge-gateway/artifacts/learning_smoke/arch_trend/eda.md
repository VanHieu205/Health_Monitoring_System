# EDA `arch.trend`

Source: `synthetic_mimic_like`

- **source**: synthetic_mimic_like
- **n_windows**: 40
- **n_subjects**: 5
- **n_rise**: 9
- **n_stable**: 31
- **positive_rate**: 0.225
## l_news_now_hist
```json
{
  "1": 27,
  "2": 9,
  "3": 4
}
```
## feature_means
```json
{
  "hr_median": 82.19929504394531,
  "hr_slope": 2.5924267768859863,
  "hr_std": 6.669632911682129,
  "spo2_median": 95.6648941040039,
  "spo2_slope": -0.462050199508667,
  "spo2_std": 1.1364185810089111,
  "rr_median": 16.913619995117188,
  "rr_slope": 0.4505467414855957,
  "rr_std": 1.322338581085205,
  "temp_median": 36.90985107421875,
  "temp_slope": 0.05740761756896973,
  "temp_std": 0.15186920762062073,
  "l_news": 1.4249999523162842
}
```
## Notes
- Self-label: L_news(t+2h) > L_news(t). Positive cases are usually rare.
- MIMIC is ICU bedside — domain shift vs a wristband; Hybrid FL is a proof of concept.
