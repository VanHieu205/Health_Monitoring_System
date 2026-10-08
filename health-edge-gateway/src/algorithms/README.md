# Lớp thuật toán (không I/O)

Phiên bản: `4.0.0-hospital-news2` — bám `DACN_HuongTrienKhai.pdf`.

Thư mục này chỉ chứa công thức, cổng chất lượng và fusion. Không MQTT, không SQLite.

| File | Việc |
|------|------|
| `news2.py` | Bảng NEWS2 đủ 7 tham số, Scale 1/2, làm tròn, `L_news`, Θ nhập tay |
| `news2_branch.py` | Ghép nguồn measured/estimated/manual, C, cận dưới S, `needs_confirmation` |
| `vitals_estimate.py` | HR từ IBI, SpO2 từ R, RR từ ba điều biến PPG |
| `fall_confirm.py` | Cửa sổ 30 s trên Pi: xác nhận / tự hủy / hủy nút; mất gói → xác nhận |
| `fall_pipeline.py` | Luật phía đồng hồ (mô phỏng): va chạm, tư thế, bất động |
| `trend_branch.py` | `L_trend = min(L_news+1, 2)` khi `p_det ≥ τ` |
| `device_status.py` | Kênh kỹ thuật, không trộn vào L |
| `fusion.py` | `L = max(L_news, L_fall, L_trend)` + hysteresis |
| `motion_gate.py` / `ppg_sqi.py` / `physio_rule.py` | Cổng PPG (yên, IQR) |
| `imu_fall_gate.py` | Cổng kỹ thuật IMU (không hạ té ngã đã xác nhận) |

## Fusion

- Học máy không hạ NEWS2.
- Té ngã không phụ thuộc PPG.
- `signal_poor` không ghi vào L; tham số tương ứng thành **thiếu**.
- S = 0 và C < 1 → `L_news = 1` (thiếu dữ liệu không phải nguy cơ thấp).

## FL

`arch.snn`, `arch.sqi`, `arch.trend`. Không federate bảng NEWS2.

```text
python scripts/verify_news2.py
python scripts/verify_alert_fusion.py
```
