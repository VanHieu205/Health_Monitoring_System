# EDA `arch.snn`

Source: `weda_fall`

- **source**: weda_fall
- **n_windows**: 8393
- **n_subjects**: 25
## class_counts
```json
{
  "sit_stand": 1618,
  "walk": 5548,
  "fall_like": 1227
}
```
- **imbalance_ratio**: 4.52159739201304
## per_class
```json
{
  "sit_stand": {
    "n": 1618,
    "smv_peak_mean": 1.4961649179458618,
    "smv_peak_p95": 2.5357120037078857
  },
  "walk": {
    "n": 5548,
    "smv_peak_mean": 2.1222712993621826,
    "smv_peak_p95": 4.470596790313721
  },
  "fall_like": {
    "n": 1227,
    "smv_peak_mean": 3.7289819717407227,
    "smv_peak_p95": 6.1336541175842285
  }
}
```
## Notes
- 2 s windows on a uniform 50 Hz grid; split by subject, young/elder stratified for WEDA ids.
- Accel stored in g. Gyro stored in deg/s (WEDA rad/s × 180/π).
- fall_like requires ≥50% overlap with the annotated interval, or the trial SMV peak inside that interval.
- Training head is sit_stand, walk, fall_like. rest and not_worn are omitted.
