# Decision fusion pipeline (Phase 2)

**Algorithm version:** `2.0.0-news2-subset`

Tài liệu này mô tả **luồng đo kiosk trên Edge Gateway**: từ SQLite Phase 1 đến chỉ số **tập hợp NEWS2 trên các dấu hiệu sinh tồn máy đo được**. Đây **không** phải chẩn đoán, **không** phải NEWS2 đầy đủ, và **không** phải xác suất bệnh.

Phần mềm liên quan:

| File | Vai trò |
|------|---------|
| `src/fusion_worker.py` | Tiến trình độc lập MQTT; chỉ **đọc** `data/local_buffer.db` |
| `sliding_win.py` | Giao thức settle / acquire, lọc plausibility, **median / IQR** |
| `motion_gate.py` | SQI IMU (RMS gia tốc động) — **cổng chất lượng, fail-closed** |
| `physio_rule.py` | Bảng NEWS2 **mạch** và **SpO2 Scale 1** |
| `temp_rule.py` | Bảng NEWS2 **nhiệt độ** + offset hiệu chuẩn da→lõi |
| `news2_subset.py` | Cut-point RCP NEWS2 (2017) + phiên bản thuật toán |
| `fusion.py` | Abstain nếu đo không đạt; nếu đạt thì **cộng điểm** các thành phần |

`mqtt_subscriber.py` **không** bị thay: hai process chỉ dùng chung SQLite.

---

## 1. Nguyên tắc thiết kế (sản phẩm y tế)

1. **Fail-closed.** SQI không `pass`, hoặc phiên chưa đủ protocol → **không** xuất `subset_total`. Không nhân “độ tin cậy” để ra một số giả lâm sàng.
2. **Tách lớp.** (A) tính hợp lệ đo → (B) điểm sinh lý theo guideline → (C) tổng tập hợp. IMU **không** phải nguy cơ bệnh.
3. **Không stub trên đường chính.** TinyML **không** cộng vào `subset_total`. Biến `TINYML_P_PHYSIO` chỉ log nghiên cứu (`tinyml_p_physio_unvalidated`).
4. **Không bịa nhiệt độ.** Thiếu cột `temp` → bỏ thành phần nhiệt, gắn cờ `temperature_omitted_partial_subset`. Bật `REQUIRE_TEMPERATURE=1` nếu bắt buộc đủ 3 kênh.
5. **Cấm dùng band NEWS2** (low / medium / high / escalation). Band đó giả định đủ RR, huyết áp, ACVPU, oxy bổ sung.

Nguồn cut-point: Royal College of Physicians (2017). *National Early Warning Score (NEWS) 2*. London: RCP. Triển khai kiosk chỉ lấy **ba bảng** (pulse, SpO2 Scale 1, temperature).

---

## 2. Pipeline tổng

```text
ESP32  --MQTT-->  mqtt_subscriber  -->  SQLite local_buffer.db
                                              |
                         fusion_worker (đọc, không ghi sensor)
                                              |
                    ┌─────────────────────────┴─────────────────────────┐
                    ▼                                                   │
            sliding_win.py                                              │
            t_end = max(timestamp) hoặc wall-clock                      │
            [settle 10 s — BỎ] [acquire 45 s — GIỮ]                     │
            lọc HR∈[30,220], SpO2∈[70,100], T∈[32,43] °C                │
            median + IQR                                                │
            protocol_ok?  (≥30 mẫu hợp lệ / kênh, ≥80% thời lượng)      │
                    │                                                   │
        ┌───────────┼───────────────────┐                               │
        ▼           ▼                   ▼                               │
  motion_gate   physio_rule         temp_rule                           │
  a_dyn = a−μ    NEWS2 pulse         T_core = T_sensor + δ              │
  RMS [g]        NEWS2 SpO2 S1       NEWS2 temperature                  │
  pass/marg/fail                                                        │
        └───────────┬───────────────────┘                               │
                    ▼                                                   │
               fusion.py                                                │
        protocol fail  → status=incomplete_protocol, không total        │
        SQI ≠ pass     → status=invalid_measurement,  không total       │
        SQI pass       → subset_total = HR + SpO2 [+ Temp]              │
                    ▼                                                   │
              JSON log / FUSION_ONCE                                    │
```

Hai process **song song**: subscriber ghi ~1 Hz; worker đánh giá **một phiên acquire**, không fusion từng gói MQTT.

---

## 3. Chi tiết từng bước

### 3.1 `sliding_win.py` — giao thức cửa sổ

Kiosk cần PPG ổn định. Worker lấy `settle + acquire` giây (mặc định **10 + 45 = 55 s**) tính từ `t_end`.

| Pha | Khoảng timestamp | Dùng để scoring? |
|-----|------------------|------------------|
| Settle | `(t_end−55, t_end−45]` | **Không** (đặt đầu dò, lock PPG) |
| Acquire | `(t_end−45, t_end]` | **Có** |

Thống kê trên mẫu **sau lọc plausibility** (gói lỗi / ngoài dải vật lý):

- Trung vị HR, SpO2, nhiệt (không dùng mean làm đầu vào NEWS2).
- IQR để audit độ phân tán.

`protocol_ok = false` nếu thiếu mẫu hợp lệ (mặc định **≥ 30** HR, **≥ 30** SpO2, **≥ 30** IMU) hoặc thời lượng acquire **&lt; 80%** của 45 s. Buffer cũ 14 mẫu (log Phase 2 trước đây) **phải** ra `incomplete_protocol` — đó là hành vi đúng.

### 3.2 `motion_gate.py` — SQI

1. LSB → g (mặc định MPU-6050 **±2 g, 16384 LSB/g** — phải khớp firmware).
2. Trừ mean từng trục trên cửa sổ acquire (gravity/bias gần hằng khi ngồi yên):

   \(\mathbf{a}_{\mathrm{dyn}}(t)=\mathbf{a}(t)-\overline{\mathbf{a}}\)

3. \(\mathrm{RMS}=\sqrt{\mathrm{mean}\|\mathbf{a}_{\mathrm{dyn}}\|^2}\) (đơn vị **g**).

| RMS | Mức | Hành động |
|-----|-----|-----------|
| &lt; 0.05 g | `pass` | Được phép chấm NEWS2 subset |
| 0.05–0.12 g | `marginal` | **Đo lại**, không ra chỉ số |
| ≥ 0.12 g | `fail` | **Đo lại**, motion artefact |

Ngưỡng **0.05 / 0.12 g là tạm trước hiệu chuẩn thiết bị**. Trên phần cứng thật: thu người ngồi yên vs gõ tay / nói chuyện, chọn ngưỡng bằng ROC (nhãn: PPG dùng được / không). Sai full-scale IMU sẽ làm RMS sai hoàn toàn.

### 3.3 `physio_rule.py` — NEWS2 pulse & SpO2 Scale 1

Pulse (bpm): ≤40 → 3; 41–50 → 1; 51–90 → 0; 91–110 → 1; 111–130 → 2; ≥131 → 3.

SpO2 Scale 1 (% nguyên sau làm tròn): ≤91 → 3; 92–93 → 2; 94–95 → 1; ≥96 → 0.

Scale 2 (COPD / tăng CO₂) **không** tự chọn.

### 3.4 `temp_rule.py` — NEWS2 nhiệt

\(T_{\mathrm{core,est}}=T_{\mathrm{sensor}}+\delta\), \(\delta=\) `TEMP_CORE_OFFSET_C` (mặc định 0). \(\delta\) phải đo Bland–Altman vs nhiệt chuẩn theo vị trí (trán, tai, …).

Làm tròn 0.1 °C rồi: ≤35.0 → 3; 35.1–36.0 → 1; 36.1–38.0 → 0; 38.1–39.0 → 1; ≥39.1 → 2.

Không còn hàm mũ \(1-e^{-k\Delta T}\) (không có trong guideline).

### 3.5 `fusion.py` — hợp nhất

```text
nếu !protocol_ok     → incomplete_protocol
else nếu SQI ≠ pass  → invalid_measurement
else                 → subset_total = score_HR + score_SpO2 [+ score_T]
```

`max_subset = 3 × số thành phần`. Cảnh báo JSON luôn nhắc: **không áp dụng escalation NEWS2**.

---

## 4. Chạy worker

Từ thư mục `health-edge-gateway` (WSL hoặc Pi), MQTT subscriber đang ghi DB:

```bash
export FUSION_ONCE=1
python src/fusion_worker.py
```

Lặp mỗi 10 s (dev). **Sản phẩm** nên gọi một lần khi UI kiosk bấm “Hoàn tất đo”, không ticker trên DB đứng:

```bash
python src/fusion_worker.py
```

Copy `health-edge-gateway/.env.example` → `.env` (đã có sẵn trên máy dev). Subscriber, SQLite và `fusion_worker` cùng đọc file này qua `src/common/config.py`. Trên Pi: copy `.env` hoặc `GATEWAY_ENV_FILE=/etc/health-gateway/gateway.env`.

### Biến môi trường

| Biến | Mặc định | Ý nghĩa |
|------|----------|---------|
| `SQLITE_PATH` | `.../data/local_buffer.db` | File Phase 1 |
| `SENSOR_TABLE` | `sensor_raw_data` | Bảng |
| `SETTLE_SECONDS` | `10` | Bỏ đầu phiên |
| `ACQUIRE_SECONDS` | `45` | Cửa sổ chấm điểm |
| `FUSION_INTERVAL_S` | `10` | Chu kỳ loop |
| `RMS_PASS_G` / `RMS_FAIL_G` | `0.05` / `0.12` | Ngưỡng SQI (hiệu chuẩn lại) |
| `TEMP_CORE_OFFSET_C` | `0` | δ da→lõi |
| `REQUIRE_TEMPERATURE` | `0` | `1` = thiếu nhiệt thì abstain |
| `TINYML_P_PHYSIO` | tắt | Stub nghiên cứu, **không** vào tổng |
| `FUSION_ONCE` | — | In một JSON rồi thoát |

---

## 5. Đọc JSON

| Trường | Ý nghĩa |
|--------|---------|
| `ok` | `true` chỉ khi `status=scored` |
| `status` | `scored` / `incomplete_protocol` / `invalid_measurement` |
| `median_hr` / `median_spo2` / `median_temp` | Đầu vào bảng NEWS2 |
| `hr_score` / `spo2_score` / `temp_score` | Điểm 0–3 từng kênh |
| `subset_total` | Tổng tập hợp hoặc `null` nếu abstain |
| `sqi_level` / `rms_dyn_g` | Chất lượng IMU |
| `reasons` | Vì sao abstain / thiếu nhiệt |
| `warning` | Ràng buộc diễn giải lâm sàng |
| `temperature_missing` | Phase 1 chưa có cột nhiệt |

Ví dụ **đúng** khi buffer ngắn: `ok=false`, `status=incomplete_protocol`, `subset_total=null`.

Ví dụ **scored** (minh họa): median HR 80, SpO2 98, không nhiệt, SQI pass → điểm 0+0, `subset_total=0`, `n_components=2`, `reasons` chứa omitted temperature.

---

## 6. Việc còn lại trước tuyên bố y tế

1. Hiệu chuẩn IMU (ROC ngồi yên / nhiễu) và khớp LSB/g firmware.
2. Hiệu chuẩn SpO2/HR vs thiết bị đối chứng (hướng ISO 80601-2-61).
3. Bland–Altman nhiệt + \(\delta\).
4. Gắn nhiệt vào packet ESP32 nếu cần 3 thành phần.
5. TinyML chỉ sau **calibration xác suất** và **không** thay bảng NEWS2.
6. Validation trên người, protocol đạo đức, phiên bản thuật toán (IEC 62304) khi đổi ngưỡng.

Thay đổi cut-point hoặc ngưỡng RMS = **đổi `ALGORITHM_VERSION`**, không sửa thầm.
