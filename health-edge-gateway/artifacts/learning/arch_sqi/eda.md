# EDA `arch.sqi`

Nguồn: `synthetic_dalia_like`

- **source**: synthetic_dalia_like
- **n_windows**: 480
- **n_subjects**: 8
- **n_good**: 376
- **n_bad**: 104
- **yield**: 0.7833333333333333
## features
```json
{
  "iqr_hr": {
    "mean_good": 6.881150245666504,
    "mean_bad": 17.8383846282959
  },
  "n_beats": {
    "mean_good": 29.60904312133789,
    "mean_bad": 17.951923370361328
  },
  "rms_acc_g": {
    "mean_good": 0.0640258714556694,
    "mean_bad": 0.1471601128578186
  },
  "ac_dc": {
    "mean_good": 0.025386495515704155,
    "mean_bad": 0.013523297384381294
  },
  "motion_code": {
    "mean_good": 0.789893627166748,
    "mean_bad": 1.759615421295166
  }
}
```
## Ghi chú
- Nhãn y=1 khi |HR_ppg - HR_ref| <= 5 bpm. Không lấy nhãn từ luật IQR.
- PPG-DaLiA không có SpO2 tham chiếu — cổng SpO2 vẫn dùng luật.
