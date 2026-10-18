# Domain layer (no I/O)

Version: `4.0.0-hospital-news2` — follows `DACN_HuongTrienKhai.pdf`.

This folder holds formulas, quality gates, and fusion only. No MQTT, no SQLite.

| File | Role |
|------|------|
| `news2.py` | Full 7-parameter NEWS2, Scale 1/2, rounding, `L_news`, manual TTL Θ |
| `news2_branch.py` | Merge measured/estimated/manual sources, C, lower-bound S, `needs_confirmation` |
| `vitals_estimate.py` | HR from IBI, SpO2 from R, RR from three PPG modulations |
| `fall_confirm.py` | 30 s Pi window: confirm / auto-cancel / button-cancel; missing packets confirm |
| `fall_pipeline.py` | On-watch rules (lab sim): impact, posture, inactivity |
| `trend_branch.py` | `L_trend = min(L_news+1, 2)` when `p_det ≥ τ` |
| `device_status.py` | Technical channel, never mixed into L |
| `fusion.py` | `L = max(L_news, L_fall, L_trend)` + hysteresis |
| `motion_gate.py` / `ppg_sqi.py` / `physio_rule.py` | PPG gate (rest, IQR) |
| `imu_fall_gate.py` | IMU technical gate (does not downgrade a confirmed fall) |

## Fusion

- Machine learning must not lower NEWS2.
- Fall alerts do not depend on PPG.
- `signal_poor` is not written into L; the matching vital becomes **missing**.
- S = 0 and C < 1 → `L_news = 1` (missing data is not low risk).

## FL

`arch.snn`, `arch.sqi`, `arch.trend`. Do not federate the NEWS2 table.

```text
python scripts/clinical/verify_news2.py
python scripts/clinical/verify_alert_fusion.py
```
