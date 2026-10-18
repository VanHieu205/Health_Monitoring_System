# EDA `arch.trend`

Nguồn: `synthetic_mimic_like`

- **source**: synthetic_mimic_like
- **n_windows**: 64
- **n_subjects**: 8
- **n_rise**: 15
- **n_stable**: 49
- **positive_rate**: 0.234375
## l_news_now_hist
```json
{
  "1": 43,
  "2": 19,
  "3": 2
}
```
## feature_means
```json
{
  "hr_median": 79.88468170166016,
  "hr_slope": 2.5124149322509766,
  "hr_std": 6.393710136413574,
  "spo2_median": 96.03551483154297,
  "spo2_slope": -0.39930349588394165,
  "spo2_std": 1.0146604776382446,
  "rr_median": 17.06960678100586,
  "rr_slope": 0.5431811809539795,
  "rr_std": 1.3881580829620361,
  "temp_median": 36.861473083496094,
  "temp_slope": 0.045518822968006134,
  "temp_std": 0.12686561048030853,
  "l_news": 1.359375
}
```
## Ghi chú
- Nhãn tự sinh: L_news(t+2h) > L_news(t). Ca dương thường hiếm.
- MIMIC là monitor ICU — lệch miền so với vòng đeo; Hybrid FL là proof-of-concept.
