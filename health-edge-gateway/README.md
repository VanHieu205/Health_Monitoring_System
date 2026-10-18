# Health Edge Gateway

Gateway biên theo **DACN_HuongTrienKhai.pdf**: vòng đeo tay tại bệnh viện, NEWS2 đủ tham số, Decision-Level Fusion, SNN vận động (đường lạnh), Federated Learning.

Thuật toán phiên bản `4.0.0-hospital-news2`.

Sản phẩm hỗ trợ điều dưỡng, không chẩn đoán, không thay monitor đầu giường. Cut-point NEWS2 **không** học bằng FL.

---

## 1. Đầu ra

Mức lâm sàng `L ∈ {0,1,2,3}` = `routine` / `watch` / `urgent` / `emergency`.

Kênh kỹ thuật **tách riêng**: `device_ok`, `signal_poor`, `disconnected`, `battery_low`, `not_worn`.

```text
L = max(L_news, L_fall, L_trend)
```

- NEWS2 là sàn: `L ≥ L_news`.
- Té ngã không phụ thuộc chất lượng PPG.
- Học máy chỉ nâng, tối đa `L_trend = 2`.
- Thiếu tham số: S là cận dưới; `S = 0` và `C < 1` → `L_news = 1`.

---

## 2. Microservices (Pi)

Giao tiếp MQTT theo sự kiện. SQLite WAL; mỗi bảng một service ghi chính.

| Service | Entry | Topic vào | Việc |
|---------|-------|-----------|------|
| ingest | `python -m services.ingest` | `watch/+/+`, `sensor/raw/#` | `q_msg`, loại trùng `seq` |
| signal | `python -m services.signal` | `ppg_session`, `temp` | HR/SpO2/RR/nhiệt, cổng IQR, `arch.sqi` |
| news2 | `python -m services.news2` | `gateway/signal`, `gateway/manual` | `S`, `S_max`, `C`, `L_news` |
| fall | `python -m services.fall` | `fall_candidate`, `motion`, `button` | Xác nhận 30 s, `arch.snn` |
| trend | `python -m services.trend` | `gateway/news2/decision` | `L_trend`, `arch.trend` |
| fusion | `python -m services.fusion` | ba nhánh, ack, heartbeat | `L`, hysteresis, `open` không lặp, còi nếu `L≥2` |
| fl-client | `python -m learning.fl_client` | đường lạnh | `arch.snn`, `arch.sqi`, `arch.trend` |

```text
watch ──MQTT──► ingest
            ├─► signal ─► news2 ─┬─► trend ─┐
            └─► fall ─────────────────┴──────────► fusion ─► gateway/alert
```

Lab một process: `python src/application/lab_worker.py` (cửa sổ SQLite 18-byte cũ).

---

## 3. Tách lớp

```text
src/domain/        luật thuần: NEWS2, té ngã, SQI, fusion. Không MQTT, không SQLite
src/contracts/     tên topic và phong bì bản tin
src/runtime/       cấu hình, log, client MQTT
src/services/      một process cho mỗi nhánh: ingest, signal, news2, fall, trend, fusion
src/services/branches/  cổng arch.snn, arch.sqi, arch.trend
src/application/   ghép nhánh cho lab
src/persistence/   SQLite
src/ingress/       BLE và gói 18 byte cũ
src/learning/      train và FL client, đường lạnh

scripts/learning/  chuẩn bị dữ liệu, train, replay, eval
scripts/clinical/  kiểm tra NEWS2 và fusion
scripts/ingress/   giả lập gói BLE 18 byte
deploy/k3s/        manifest của các service trên Pi
artifacts/learning/  model.pt và report của ba nhánh
data/              windows.npz và SQLite cục bộ
```

MPU6050 mặc định **±16 g** (`MPU_LSB_PER_G=2048`) để ngưỡng va chạm 2.5 g đo được.

PPG NEWS2 trong thiết kế PDF đo **phản xạ cổ tay**; điều dưỡng nhập HA, ACVPU, oxy.

---

## 4. Federated Learning

Train cục bộ (EDA → preprocess → tune → evaluate): xem `src/learning/README.md`.

```text
set PYTHONPATH=src
python scripts/learning/verify_training_pipeline.py
python scripts/learning/train_models.py
```

Cùng FedAvg, ba `architecture_version`: SNN vận động, SQI PPG (nhãn máy kẹp ngón), MLP xu hướng (nhãn tự sinh từ lịch sử NEWS2). Không federate bảng điểm hay quy tắc fusion.

---

## 5. Chạy kiểm tra

```text
copy .env.example .env
python scripts/clinical/verify_news2.py
python scripts/clinical/verify_alert_fusion.py
```

Docker đường nóng:

```text
docker compose up --build ingest signal-proc news2 fall trend fusion
```

---

## 6. Ngoài phạm vi giai đoạn này trong repo

Firmware SNN trên ESP32; dashboard / app người nhà; TimescaleDB cloud; thử nghiệm giảm oxy ISO 80601-2-61; FL surrogate gradient thật (client hiện là hợp đồng).

Gói 18 byte BLE chỉ còn `scripts/ingress/ble_packet_simulator.py`. Hợp đồng JSON: `health-shared-contracts/mqtt-json/`.
