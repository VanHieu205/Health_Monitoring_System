# Kế hoạch triển khai tầng Edge Gateway (Raspberry Pi)

Tài liệu gốc: `DACN_HuongTrienKhai.pdf` — *Cảnh báo sớm suy giảm sức khỏe bằng vòng đeo tay cho môi trường bệnh viện: NEWS2, Decision-Level Fusion, SNN và Federated Learning*.

Phạm vi file này: **toàn bộ trách nhiệm của tầng biên** (Raspberry Pi tại một khoa/site). Tầng vòng đeo (firmware ESP32) và tầng cloud chỉ được nhắc ở các điểm giao tiếp với gateway.

Quy ước trong file:

- Mỗi đầu việc là một checkbox `[ ]`. Đánh `[x]` khi đạt **tiêu chí hoàn thành** của module, không phải khi "đã có code".
- Cột "Vị trí mã" chỉ nơi bắt đầu làm việc trong repo. File có ở đó **không** có nghĩa là việc đã xong; mọi module đều phải đi qua rà soát, kiểm thử và nghiệm thu theo kế hoạch này.
- Thời lượng giả định **14 tuần**. Nếu học kỳ dài/ngắn hơn, co giãn Giai đoạn 3–4, giữ nguyên thứ tự các mốc.

---

## Mục lục

1. [Trách nhiệm của tầng gateway](#1-trách-nhiệm-của-tầng-gateway)
2. [Phân công 3 thành viên](#2-phân-công-3-thành-viên)
3. [Đặc tả từng module và hướng giải quyết](#3-đặc-tả-từng-module-và-hướng-giải-quyết)
4. [Các điểm cần xử lý trong mã nguồn hiện tại](#4-các-điểm-cần-xử-lý-trong-mã-nguồn-hiện-tại)
5. [Lịch theo tuần](#5-lịch-theo-tuần)
6. [Mốc nghiệm thu](#6-mốc-nghiệm-thu)
7. [Chiến lược kiểm thử](#7-chiến-lược-kiểm-thử)
8. [Quy trình làm việc nhóm](#8-quy-trình-làm-việc-nhóm)
9. [Rủi ro và phương án dự phòng](#9-rủi-ro-và-phương-án-dự-phòng)
10. [Quyết định cần chốt ở tuần 1](#10-quyết-định-cần-chốt-ở-tuần-1)

---

## 1. Trách nhiệm của tầng gateway

Theo PDF mục 3 và Bảng 10, gateway chịu trách nhiệm toàn bộ **đường nóng** (ra cảnh báo, không phụ thuộc cloud) và phần **client** của **đường lạnh** (FL, OTA).

### 1.1. Service theo PDF (Bảng 10)

| # | Service | Trách nhiệm | Vị trí mã |
|---|---------|-------------|-----------|
| S1 | `ble_ingest` | Kết nối nhiều vòng đeo qua BLE, giải mã gói, loại trùng theo `seq`, sắp xếp theo `t_measured`, gắn `patient_id` theo bảng ghép thiết bị | `src/ingress/*`, `src/services/ingest` |
| S2 | `signal_proc` | HR từ IBI, SpO2 từ R, RR từ RIIV/RIAV/RIFV, nhiệt độ + Δcal; chạy mô hình SQI; áp cổng chất lượng | `src/domain/vitals_estimate.py`, `physio_rule.py`, `ppg_sqi.py`, `motion_gate.py`, `temp_rule.py`, `src/services/signal` |
| S3 | `manual_input` | Nhận tham số điều dưỡng nhập (HA, ACVPU, oxy, RR, nhiệt, Scale 2), quản lý thời hạn hiệu lực Θ | `src/services/news2` (phần `gateway/manual`), bảng `manual_vitals` |
| S4 | `branch_news2` | Chọn giá trị theo Bảng 8, tính `S`, `S_max`, `C`, `L_news`, cờ `needs_confirmation` | `src/domain/news2.py`, `news2_branch.py`, `src/services/news2` |
| S5 | `branch_fall` | Cửa sổ 30 s sau `FALL_CANDIDATE`: xác nhận / tự hủy / hủy nút; mất gói → xác nhận | `src/domain/fall_confirm.py`, `src/services/fall` |
| S6 | `branch_trend` | MLP xu hướng 2 giờ → `p_det` → `L_trend ≤ 2` | `src/domain/trend_branch.py`, `src/services/trend`, `src/ml_inference/*` |
| S7 | `fusion` | `L = max(L_news, L_fall, L_trend)`, chống nhấp nháy, truy vết, vòng đời cảnh báo | `src/domain/fusion.py`, `src/services/fusion` |
| S8 | `local_alert` | Đèn/còi tại quầy, màn hình cục bộ khi `L ≥ 2`, kể cả mất mạng | `gateway/local_alarm` (topic), chưa có process riêng |
| S9 | `cloud_sync` | Đẩy kết quả lên cloud theo hàng đợi, retry + backoff; nhận lệnh và tham số nhập tay từ cloud | `src/persistence/sync_worker.py` |
| S10 | `fl_client` | Huấn luyện cục bộ 3 mô hình, gửi cập nhật, nhận mô hình toàn cục | `src/learning/*` |
| S11 | `ota_agent` | Phân phối firmware và trọng số SNN xuống vòng đeo; rollback | `src/ota_manager/*` |

### 1.2. Trách nhiệm xuyên suốt (không có trong Bảng 10 nhưng gateway phải làm)

| # | Trách nhiệm | Nội dung | Vị trí mã |
|---|-------------|----------|-----------|
| X1 | Hợp đồng bản tin | Schema JSON có phiên bản cho mọi topic watch → Pi và Pi nội bộ | `src/contracts/envelope.py`, `src/contracts/topics.py`, `health-shared-contracts/mqtt-json/` |
| X2 | Lưu trữ cục bộ | SQLite WAL, sở hữu bảng theo service, khôi phục trạng thái sau khởi động lại, dọn dữ liệu cũ | `src/persistence/db_models.py` |
| X3 | Ghép thiết bị – người bệnh | `device_id` ↔ `patient_id` (giả danh), hiệu chuẩn nhiệt độ theo người | chưa có bảng |
| X4 | Lệnh xuống vòng đeo | Khi `L ≥ 2`: lệnh escalate PPG liên tục (PDF 4.2); lệnh đo theo yêu cầu | chưa có topic |
| X5 | Kênh trạng thái kỹ thuật | `device_ok/signal_poor/disconnected/battery_low/not_worn`, watchdog heartbeat | `src/domain/device_status.py` |
| X6 | Bảo mật | BLE LE Secure Connections, MQTT xác thực + TLS, chứng chỉ Pi, không lộ danh tính | `mosquitto.conf` (gốc repo) |
| X7 | Quan sát hệ thống | Log có cấu trúc, metrics (độ trễ, số gói, tỉ lệ loại phiên), health check | `src/runtime/logger.py`, `metrics.py`, `src/api/health_check.py` |
| X8 | Triển khai | Docker Compose (dev) và systemd/restart policy (Pi), cấu hình `.env` | `docker-compose.yml`, `Dockerfile`, `.env.example` |
| X9 | Mô phỏng và dữ liệu thử | Simulator phát đủ loại gói và kịch bản lâm sàng | `scripts/ingress/ble_packet_simulator.py` |
| X10 | Kiểm thử và đánh giá | Kiểm thử biên NEWS2, kịch bản fusion, chạy dài, đo độ trễ | `scripts/verify_*.py` |

---

## 2. Phân công 3 thành viên

Chia theo **ranh giới dữ liệu**, mỗi người sở hữu một đoạn của đường đi dữ liệu để ít giẫm chân nhau:

| Thành viên | Vai trò | Sở hữu chính | Hỗ trợ |
|------------|---------|--------------|--------|
| **TV1 — Dữ liệu vào và tín hiệu** | Mọi thứ từ vòng đeo đến "giá trị sinh hiệu đã qua cổng" | S1, S2, X1, X3, X9 | S11 (giao tiếp BLE xuống vòng đeo) |
| **TV2 — Quyết định lâm sàng** | Từ giá trị đã qua cổng đến mức cảnh báo `L` | S3, S4, S5, S6, S7, S8, X5, X4 | X10 (kịch bản fusion) |
| **TV3 — Nền tảng và học máy** | Hạ tầng chạy, đồng bộ, học liên kết, phát hành mô hình | S9, S10, S11, X2, X6, X7, X8 | S6 (huấn luyện MLP trend), S2 (huấn luyện SQI) |

Nguyên tắc:

- **Một module, một chủ sở hữu**. Người khác muốn sửa thì mở Pull Request cho chủ sở hữu duyệt.
- **Hợp đồng bản tin (X1) chốt chung ở tuần 2** và chỉ đổi qua tăng `schema_version`.
- Phần viết báo cáo chia theo module mình sở hữu, TV1 tổng hợp chương kiến trúc, TV2 chương NEWS2/fusion, TV3 chương FL/triển khai.

Ghi tên thật vào bảng:

| Mã | Họ tên | MSSV | Nhánh git |
|----|--------|------|-----------|
| TV1 | | | `feat/ingest-signal` |
| TV2 | | | `feat/clinical` |
| TV3 | | | `feat/platform-fl` |

---

## 3. Đặc tả từng module và hướng giải quyết

Mỗi module ghi: đầu vào, đầu ra, hướng giải quyết, tiêu chí hoàn thành (DoD).

### S1. `ble_ingest` — TV1

- **Vào:** gói BLE từ nhiều vòng đeo (giai đoạn đầu: JSON qua MQTT từ simulator).
- **Ra:** bản ghi `raw_events` (đã loại trùng), phát lại lên topic nội bộ `watch/{id}/{kind}`.
- **Hướng giải quyết:**
  - Dùng thư viện `bleak` (BlueZ trên Pi) làm BLE central; mỗi vòng đeo một task `asyncio`, kết nối lại có backoff.
  - Tách hai lớp: lớp **transport** (BLE hoặc MQTT) và lớp **codec** (giải mã → envelope). Simulator đi đường MQTT, vòng đeo thật đi đường BLE, cùng một codec.
  - Loại trùng bằng ràng buộc `UNIQUE(device_id, seq)`; phát hiện **mất gói** khi `seq` nhảy, ghi metric.
  - Gói gửi bù sau mất kết nối (vòng đeo đọc từ flash): sắp xếp theo `t_measured`, không theo thời điểm nhận.
  - Gắn `patient_id` theo bảng ghép (X3) ngay tại ingest; gói từ thiết bị chưa ghép thì lưu nhưng không đẩy vào nhánh lâm sàng.
- **DoD:** 3 vòng đeo mô phỏng chạy song song 1 giờ; không trùng, phát hiện đúng 100 % gói mất được bơm; khởi động lại service không mất gói đã nhận.

### S2. `signal_proc` — TV1

- **Vào:** `ppg_session`, `temp`, `motion` (lớp SNN).
- **Ra:** `gateway/signal` gồm giá trị, nguồn (`measured/estimated`), `gate_ok`, lý do.
- **Hướng giải quyết:**
  - HR: lọc IBI ngoài [0,27; 2,0] s và lệch > 20 % trung vị cục bộ, HR = 60 / median(IBI) (PDF công thức 5).
  - SpO2: `SpO2 = aR² + bR + c`, cắt [70, 100] %. **Hệ số phải hiệu chuẩn** trên chính phần cứng bằng đo đồng thời với máy kẹp ngón; hệ số mặc định chỉ là khởi tạo.
  - RR: ba ước lượng RIIV/RIAV/RIFV, lọc 0,1–0,7 Hz, chấp nhận khi lệch ≤ 4 /phút, gắn cờ `estimated`.
  - Nhiệt: `T_est = T_skin + Δcal`, Δcal theo từng người bệnh, cập nhật mỗi lần điều dưỡng nhập nhiệt độ.
  - Cổng chất lượng theo PDF Bảng 5: ≥ 20 nhịp hợp lệ, IQR(HR) ≤ 10, IQR(SpO2) ≤ 2, SNN là `rest`/`sit_stand`, SQI ≥ τ_sqi, DC_IR trong dải.
  - Không đạt cổng → giá trị **thiếu**, không phải bình thường; đẩy `signal_poor` sang kênh kỹ thuật.
- **DoD:** kiểm thử đơn vị cho mỗi công thức; bộ phiên tổng hợp (nhiễu, cử động, thiếu nhịp) cho đúng `gate_ok`; Bland–Altman HR/SpO2 trên dữ liệu thật (tuần 12).

### S3. `manual_input` — TV2

- **Vào:** `gateway/manual` (từ cloud qua S9, hoặc giao diện cục bộ khi mất mạng).
- **Ra:** bảng `manual_vitals` với `valid_until`.
- **Hướng giải quyết:**
  - Tách thành process/handler riêng thay vì nằm trong `news2_service`, để nhánh NEWS2 chỉ đọc.
  - Θ theo PDF công thức 10, tính từ **kết quả NEWS2 gần nhất của người bệnh đó**, không lấy từ nội dung gói nhập tay.
  - `on_oxygen` hiệu lực đến khi đổi; `scale2` chỉ bật theo chỉ định bác sĩ.
  - Kiểm tra miền giá trị (HA 40–300, ACVPU ∈ {A,C,V,P,U}…), từ chối và trả lỗi.
  - Nhắc khi tham số sắp hết hạn: phát `gateway/manual/expiring`.
- **DoD:** kiểm thử chuyển Θ khi nhóm nguy cơ thay đổi; giá trị hết hạn bị coi là thiếu.

### S4. `branch_news2` — TV2

- **Vào:** `gateway/signal`, `manual_vitals`.
- **Ra:** `gateway/news2/decision` (`L_news`, `S`, `S_max`, `C`, `missing`, `needs_confirmation`, nguồn từng tham số).
- **Hướng giải quyết:**
  - Bảng điểm đúng PDF Bảng 6–7; làm tròn trước khi tra (half-up).
  - Ưu tiên `manual` khi cả hai còn hiệu lực.
  - `S` là cận dưới khi thiếu; `S = 0 ∧ C < 1 → L_news = 1`.
  - `needs_confirmation` khi nhóm nguy cơ thay đổi chỉ do tham số `estimated`.
  - Lưu trạng thái giá trị mới nhất vào SQLite để khởi động lại không mất.
- **DoD:** **100 %** trên bộ kiểm thử mọi giá trị biên của Bảng 6–7 và công thức 15; so sánh với tính tay trên ≥ 30 ca mẫu.

### S5. `branch_fall` — TV2

- **Vào:** `fall_candidate`, `motion`, `button`.
- **Ra:** `gateway/fall/decision` (`fall_confirmed / auto_cancelled / manual_cancelled`, `L_fall ∈ {0,1,3}`).
- **Hướng giải quyết:**
  - Máy trạng thái theo từng thiết bị; **bộ hẹn giờ độc lập** với gói đến (thread/`asyncio`), để khi mất gói vẫn xác nhận sau 30 s.
  - Tự hủy khi `walk`/`sit_stand` liên tục ≥ 5 s và không có va chạm mới; xác nhận khi `rest`/`unknown` ≥ 20 s hoặc hết cửa sổ.
  - Thiếu dữ liệu luôn dẫn về xác nhận.
  - Ứng viên mới trong lúc cửa sổ cũ đang mở: gộp vào sự kiện cũ, không mở hai cảnh báo.
- **DoD:** kịch bản: ngã nằm im, ngã rồi đứng dậy đi, ngã rồi bấm nút, ngã rồi mất kết nối, hai ứng viên liên tiếp — đều đúng kết quả và đúng độ trễ.

### S6. `branch_trend` — TV2 (dịch vụ), TV3 (mô hình)

- **Vào:** lịch sử 2 giờ của HR, SpO2, RR, nhiệt, thời gian theo lớp vận động, `L_news` gần nhất.
- **Ra:** `gateway/trend/decision` (`p_det`, `L_trend = min(L_news + 1, 2)` nếu `p_det ≥ τ_det`).
- **Hướng giải quyết:**
  - Đặc trưng: trung vị, độ dốc (hồi quy tuyến tính), độ biến thiên cho mỗi tham số; tỉ lệ thời gian từng lớp SNN.
  - Nhãn tự sinh: `y = 1` nếu `L_news(t + 2h) > L_news(t)`.
  - MLP 2 lớp ẩn (PyTorch CPU), xuất ONNX hoặc giữ PyTorch trên Pi.
  - Khi chưa có mô hình: nhánh trả `L_trend = 0` và lý do `trend_unavailable`.
  - Mã PatchTST/Informer trong `src/ml_inference/` là nền tảng cũ: quyết định ở tuần 1 xóa hay giữ ngoài đường nóng.
- **DoD:** `L_trend` không bao giờ > 2; đánh giá AUROC trên dữ liệu tổng hợp/dataset; thời gian suy luận < 50 ms trên Pi.

### S7. `fusion` — TV2

- **Vào:** ba quyết định nhánh, ack điều dưỡng, kênh kỹ thuật.
- **Ra:** `gateway/alert`, bảng `alerts`.
- **Hướng giải quyết:**
  - `L = max(L_news, L_fall, L_trend)` theo từng người bệnh.
  - Chống nhấp nháy: tăng ngay; chỉ giảm khi mức thấp hơn duy trì **hai phiên đo liên tiếp** hoặc điều dưỡng xác nhận.
  - Vòng đời: `open → acknowledged → resolved`; cùng người bệnh, cùng mức đang mở → không tạo bản ghi mới.
  - Truy vết: lưu giá trị và nguồn từng tham số, `S`, `S_max`, `C`, `L_b` mỗi nhánh, nhánh quyết định, phiên bản thuật toán/mô hình.
  - Kênh kỹ thuật **không** ghi vào `L`.
  - Quyết định nhánh cũ quá hạn (ví dụ NEWS2 > 15 phút) phải được đánh dấu, không dùng như mới.
- **DoD:** bộ kịch bản fusion không vi phạm quy tắc nào (PDF mục 11); không có cảnh báo trùng khi chạy 1 giờ.

### S8. `local_alert` — TV2

- **Vào:** `gateway/local_alarm` (khi `L ≥ 2`).
- **Ra:** còi/đèn GPIO, màn hình cục bộ.
- **Hướng giải quyết:**
  - Process riêng, không phụ thuộc cloud; dùng `gpiozero` cho buzzer + LED.
  - Mẫu tín hiệu khác nhau: `emergency` liên tục, `urgent` ngắt quãng.
  - Màn hình cục bộ: trang web nhỏ (FastAPI + HTML) chạy trên Pi, hiển thị lưới giường và nút xác nhận khi mất mạng.
  - Tắt còi chỉ khi có ack.
- **DoD:** rút cáp WAN, kích hoạt ngã mô phỏng → còi kêu trong < 10 s; ack trên màn hình cục bộ tắt còi.

### S9. `cloud_sync` — TV3

- **Vào:** bảng outbox (cảnh báo, điểm, nhãn), lệnh từ cloud.
- **Ra:** gửi lên cloud qua MQTT/HTTPS TLS; nhận tham số nhập tay, ghép thiết bị, cờ Scale 2.
- **Hướng giải quyết:**
  - Mẫu **transactional outbox**: service ghi kết quả và bản ghi outbox trong cùng giao dịch; `cloud_sync` đọc outbox, gửi, đánh dấu đã gửi.
  - Retry exponential backoff có trần; `event_id` duy nhất để cloud loại trùng.
  - Hai chiều: lệnh/tham số từ cloud → `gateway/manual`, bảng ghép thiết bị.
- **DoD:** ngắt WAN 30 phút rồi nối lại → toàn bộ sự kiện lên đủ, không trùng, đúng thứ tự.

### S10. `fl_client` — TV3

- **Vào:** dữ liệu đã gán nhãn tại site cho từng mô hình.
- **Ra:** cập nhật trọng số gửi FL server; nhận mô hình toàn cục.
- **Hướng giải quyết:**
  - **Ba luồng FedAvg tách biệt** theo `architecture_version`: `arch.snn`, `arch.sqi`, `arch.trend`. Mỗi vòng chỉ một architecture, `n_k` là số mẫu của đúng mô hình đó.
  - Framework gợi ý: **Flower (`flwr`)**, mỗi architecture một strategy FedAvg; hoặc tự viết gRPC đơn giản nếu cần kiểm soát.
  - SNN: **snnTorch**, surrogate gradient (PDF công thức 20), BPTT; lượng tử hóa int8 trước khi giao S11.
  - SQI: nhãn từ đối chiếu với máy đo chuẩn, **không** từ luật IQR.
  - Trend: nhãn tự sinh từ lịch sử NEWS2.
  - Hybrid FL: 1 client thật (Pi) + các client mô phỏng trên PC, chia dataset theo đối tượng (non-IID).
  - Chặn cứng: không bao giờ gửi bảng NEWS2, quy tắc fusion; chỉ gửi trọng số.
- **DoD:** bảng so sánh local-only / FedAvg / centralized (F1, chi phí truyền, số vòng hội tụ) cho ít nhất `arch.snn`.

### S11. `ota_agent` — TV3 (hỗ trợ TV1 phần BLE)

- **Vào:** mô hình toàn cục đã kiểm định, firmware.
- **Ra:** gửi xuống vòng đeo qua BLE, theo dõi phiên bản đang chạy.
- **Hướng giải quyết:**
  - Chỉ phát hành khi trên tập kiểm định của site, độ nhạy `fall_like` không giảm (PDF 8.4).
  - Chia gói, CRC từng khối, xác nhận cuối; vòng đeo giữ phiên bản cũ để rollback.
  - Ghi `model_version` theo từng thiết bị; heartbeat phải báo đúng phiên bản sau OTA.
- **DoD:** OTA một trọng số SNN giả lập xuống vòng đeo thật (hoặc mô phỏng), rollback được khi lỗi.

### X1–X10 — xuyên suốt

| Mục | Chủ | Hướng giải quyết | DoD |
|-----|-----|------------------|-----|
| X1 Hợp đồng bản tin | TV1 | JSON Schema cho mỗi topic, kiểm tra tại ingest; tài liệu trong `health-shared-contracts/mqtt-json/` | Mọi service dùng chung schema; gói sai bị loại và ghi log |
| X2 Lưu trữ | TV3 | SQLite WAL; mỗi bảng một service ghi; khôi phục trạng thái (fall/fusion/news2) khi khởi động; dọn `raw_events` > N ngày | Kill -9 service rồi chạy lại không mất trạng thái |
| X3 Ghép thiết bị | TV1 | Bảng `device_pairing(device_id, patient_id, from, to, temp_dcal)` | Gói từ thiết bị chưa ghép không vào nhánh lâm sàng |
| X4 Lệnh xuống vòng đeo | TV2 (logic), TV1 (BLE) | Topic `gateway/cmd/{id}`: `ppg_continuous_on/off`, `measure_now` | `L ≥ 2` → lệnh escalate; `L < 2` hai phiên → tắt |
| X5 Kênh kỹ thuật | TV2 | Watchdog định kỳ quét `last_seen`, pin, `not_worn`, `signal_poor` sau K phiên lỗi | Mất heartbeat 90 s → `disconnected` mà không cần gói mới |
| X6 Bảo mật | TV3 | Mosquitto bật user/password + ACL theo topic, TLS; BLE pairing; không lưu tên thật trên Pi | Client không xác thực bị từ chối |
| X7 Quan sát | TV3 | Log JSON (`structlog` hoặc `logging`), metric Prometheus (`prometheus_client`), `/healthz` | Dashboard metric: độ trễ đầu–cuối, tỉ lệ phiên bị loại, số gói mất |
| X8 Triển khai | TV3 | Docker Compose dev; trên Pi dùng `restart: always` hoặc systemd unit; script cài đặt một lệnh | Pi khởi động lại → mọi service tự lên |
| X9 Simulator | TV1 | Simulator phát đủ 6 loại gói, nhiều thiết bị, theo kịch bản YAML | Chạy được mọi kịch bản ở mục 7 |
| X10 Kiểm thử | cả nhóm | `pytest` thay cho script rời; CI chạy mỗi PR | CI xanh là điều kiện merge |

---

## 4. Các điểm cần xử lý trong mã nguồn hiện tại

Danh sách dưới đây là việc phải làm, gắn vào checklist tuần. Không coi bất kỳ module nào là hoàn thành trước khi qua rà soát và kiểm thử.

| # | Vị trí | Vấn đề cần xử lý | Chủ | Tuần |
|---|--------|------------------|-----|------|
| 1 | `src/ingress/ble_scanner.py`, `connection_pool.py`, `mqtt_publisher.py` | File khung rỗng; cần BLE central thật bằng `bleak` | TV1 | 3, 9 |
| 2 | `src/services/ingest` | Chưa phát hiện mất `seq`, chưa sắp theo `t_measured`, chưa gắn `patient_id` | TV1 | 3–4 |
| 3 | `src/ingress/packet_decoder.py`, `mqtt_subscriber.py` | Đường gói 18 byte cũ; quyết định giữ cho simulator hay bỏ | TV1 | 2 |
| 4 | `src/services/signal` | Hệ số SpO2 là giá trị khởi tạo; thiếu kiểm DC_IR, thiếu Δcal nhiệt theo người, thiếu mô hình SQI | TV1 | 4–5, 12 |
| 5 | `src/services/news2` | Nhập tay đang nằm chung; Θ đang lấy `s`/`s_max` từ gói nhập tay thay vì kết quả NEWS2 gần nhất; trạng thái chỉ trong RAM | TV2 | 5–6 |
| 6 | `src/services/fall` | Xác nhận chỉ chạy khi có gói đến → mất hết gói thì không bao giờ xác nhận; cần bộ hẹn giờ; trạng thái trong RAM | TV2 | 6 |
| 7 | `src/services/trend` | Chưa có mô hình tính `p_det`; chưa có trích đặc trưng 2 giờ | TV2, TV3 | 8, 10 |
| 8 | `src/services/fusion` | Tuổi heartbeat luôn = 0 (không bao giờ ra `disconnected`); logic cập nhật hysteresis cần rà và kiểm thử; quyết định nhánh quá hạn chưa xử lý; trạng thái trong RAM | TV2 | 7 |
| 9 | `src/services/bus.py` | Mở kết nối MQTT mới cho mỗi lần publish; cần client dài hạn, QoS 1, retain cho trạng thái | TV3 | 3 |
| 10 | `local_alert` | Chưa có process GPIO / màn hình cục bộ | TV2 | 7–8 |
| 11 | `src/persistence/sync_worker.py` | File khung rỗng | TV3 | 8 |
| 12 | `src/learning/local_trainer.py`, `model_diff_encoder.py`, `privacy_guard.py` | File khung rỗng; `fl_client.py` mới là hợp đồng, chưa huấn luyện | TV3 | 9–11 |
| 13 | `src/ota_manager/esp32_model_pusher.py`, `k3s_image_updater.py` | File khung rỗng; `k3s_image_updater` có thể bỏ nếu không dùng k3s | TV3 | 11 |
| 14 | `src/runtime/logger.py`, `metrics.py`, `src/api/health_check.py` | File khung rỗng | TV3 | 4 |
| 15 | `src/api/grpc_server.py`, `Dockerfile` | `CMD` trỏ gRPC server không dùng; Poetry + phụ thuộc cần khớp (`paho-mqtt`, `sqlalchemy`, `bleak`…) | TV3 | 2 |
| 16 | `src/ml_inference/*` | PatchTST/Informer cũ, file rỗng; quyết định xóa hay dùng làm khung cho MLP trend | TV3 | 1 |
| 17 | `src/application/lab_worker.py`, `src/application/session_pipeline.py`, `sliding_win.py` | Đường lab đọc cửa sổ SQLite cũ; giữ làm công cụ thử nghiệm, không chạy trên đường nóng thật | TV2 | 7 |
| 18 | `scripts/clinical/verify_news2.py`, `verify_alert_fusion.py` | Chuyển thành `pytest`, mở rộng biên đủ Bảng 6–7 | TV2 | 5 |
| 19 | `mosquitto.conf`, `docker-compose.yml` | `allow_anonymous true` chỉ cho lab | TV3 | 8 |
| 20 | `scripts/ingress/ble_packet_simulator.py` | Chỉ phát gói 18 byte; cần phát đủ loại gói JSON và kịch bản | TV1 | 2–3 |

---

## 5. Lịch theo tuần

Mỗi tuần có: mục tiêu, checklist từng thành viên, sản phẩm cuối tuần. Họp nhóm 2 buổi/tuần (mục 8).

### Giai đoạn 1 — Nền móng (tuần 1–2)

#### Tuần 1 — Khởi động và chốt thiết kế

Mục tiêu: cả nhóm hiểu cùng một kiến trúc, môi trường chạy được trên mọi máy và trên Pi.

- **Cả nhóm**
  - [ ] Đọc PDF mục 3–8, ghi câu hỏi vào issue.
  - [ ] Chốt các quyết định ở [mục 10](#10-quyết-định-cần-chốt-ở-tuần-1).
  - [ ] Thống nhất quy ước git, review, định dạng commit (mục 8).
- **TV1**
  - [ ] Liệt kê đủ 6 loại gói (PDF Bảng 4) và trường bắt buộc.
  - [ ] Thử `bleak` quét được thiết bị BLE trên Pi (ESP32 bất kỳ).
- **TV2**
  - [ ] Lập bảng tất cả giá trị biên NEWS2 (Bảng 6–7, công thức 10, 15) làm dữ liệu kiểm thử.
  - [ ] Vẽ máy trạng thái nhánh té ngã và vòng đời cảnh báo.
- **TV3**
  - [ ] Cài Raspberry Pi OS, Docker, Mosquitto, Python 3.10+ trên Pi.
  - [ ] Dựng repo: `pytest`, `ruff`, CI chạy kiểm thử mỗi PR.
  - [ ] Quyết định số phận `src/ml_inference/*`, `k3s_image_updater.py`.
- **Sản phẩm:** biên bản quyết định; Pi chạy được `docker compose up local-mqtt`.

#### Tuần 2 — Hợp đồng bản tin và simulator

- **TV1**
  - [ ] Viết JSON Schema cho `heartbeat`, `motion`, `ppg_session`, `temp`, `fall_candidate`, `button` và topic nội bộ.
  - [ ] Cập nhật `health-shared-contracts/mqtt-json/README.md` theo schema.
  - [ ] Viết lại `scripts/ingress/ble_packet_simulator.py`: nhiều thiết bị, đủ loại gói, `seq` tăng dần.
  - [ ] Quyết định giữ/bỏ đường gói 18 byte.
- **TV2**
  - [ ] Định nghĩa schema topic quyết định: `news2/decision`, `fall/decision`, `trend/decision`, `alert`, `ack`, `manual`, `cmd`.
  - [ ] Viết đặc tả kịch bản kiểm thử fusion (≥ 15 kịch bản) dạng YAML.
- **TV3**
  - [ ] Sửa `Dockerfile` và phụ thuộc cho khớp các service; bỏ `CMD` gRPC.
  - [ ] Thiết kế schema SQLite đầy đủ: bảng, chủ sở hữu, chỉ mục, thời gian lưu.
  - [ ] Chọn framework FL (Flower hay tự viết) bằng một bản thử "hello FedAvg" 2 client.
- **Sản phẩm:** schema được cả nhóm duyệt (gắn tag `contracts-v1`); simulator phát được gói.

### Giai đoạn 2 — Đường nóng chạy đầu–cuối với simulator (tuần 3–7)

#### Tuần 3 — Ingest và hạ tầng bus

- **TV1**
  - [ ] Ingest: kiểm tra schema, loại trùng `(device_id, seq)`, phát hiện nhảy `seq`.
  - [ ] Sắp xếp và xử lý gói gửi bù theo `t_measured`.
  - [ ] Kiểm thử: gói trùng, gói sai schema, gói đến muộn.
- **TV2**
  - [ ] Bộ kiểm thử `pytest` cho bảng điểm NEWS2 tất cả giá trị biên.
  - [ ] Rà `src/domain/news2.py` so từng ô với PDF Bảng 6–7.
- **TV3**
  - [ ] Thay `bus.py` bằng client MQTT dài hạn, QoS 1, tự kết nối lại.
  - [ ] Bật WAL, viết lớp truy cập DB dùng chung, migration đơn giản.
- **Sản phẩm:** simulator → ingest → `raw_events` chạy ổn 30 phút.

#### Tuần 4 — Ghép thiết bị, quan sát hệ thống, ước lượng sinh hiệu

- **TV1**
  - [ ] Bảng `device_pairing` và gắn `patient_id` tại ingest.
  - [ ] HR từ IBI, SpO2 từ R, RR từ 3 điều biến: kiểm thử đơn vị với dữ liệu tổng hợp có đáp án.
- **TV2**
  - [ ] `news2_branch`: ưu tiên manual, cận dưới S, `C`, `needs_confirmation`; kiểm thử đủ trường hợp thiếu.
- **TV3**
  - [ ] `logger.py`: log JSON có `device_id`, `patient_id`, `event_id`.
  - [ ] `metrics.py`: số gói, gói mất, độ trễ từng chặng; `health_check.py`: `/healthz` mỗi service.
- **Sản phẩm:** log và metric xem được trong lúc chạy simulator.

#### Tuần 5 — Cổng chất lượng và nhập tay

- **TV1**
  - [ ] Cổng chất lượng đủ PDF Bảng 5 cho HR, SpO2, RR, nhiệt.
  - [ ] Δcal nhiệt theo người bệnh, lấy từ lần điều dưỡng nhập.
  - [ ] Phát `gateway/signal` đúng schema; không đạt cổng → thiếu + `signal_poor`.
- **TV2**
  - [ ] Tách `manual_input` thành handler/process riêng.
  - [ ] Θ theo kết quả NEWS2 gần nhất; kiểm tra miền giá trị; thông báo sắp hết hạn.
  - [ ] Chuyển `scripts/verify_*.py` sang `pytest`.
- **TV3**
  - [ ] Khôi phục trạng thái khi khởi động cho các service có trạng thái (thiết kế chung).
  - [ ] Script cài đặt Pi một lệnh.
- **Sản phẩm:** nhập HA/ACVPU/oxy → NEWS2 đổi đúng; phiên nhiễu → thiếu tham số.

#### Tuần 6 — Nhánh NEWS2 hoàn chỉnh và nhánh té ngã

- **TV1**
  - [ ] Simulator: kịch bản té ngã (nằm im, đứng dậy đi, bấm nút, mất kết nối).
  - [ ] Bắt đầu đọc tài liệu BLE của firmware (GATT service, characteristic).
- **TV2**
  - [ ] `news2_service`: lưu trạng thái giá trị mới nhất vào SQLite; phát `news2/decision` khi có thay đổi.
  - [ ] `fall_service`: máy trạng thái theo thiết bị + **bộ hẹn giờ độc lập**; gộp ứng viên chồng nhau.
  - [ ] Kiểm thử đủ kịch bản té ngã, gồm mất gói.
- **TV3**
  - [ ] Thiết kế outbox cho `cloud_sync` (bảng, giao dịch).
  - [ ] Bản thử FedAvg 2 client mô phỏng cho một MLP nhỏ.
- **Sản phẩm:** ngã mô phỏng → `fall_confirmed` đúng, kể cả khi ngắt simulator giữa chừng.

#### Tuần 7 — Fusion, kênh kỹ thuật, còi tại chỗ — **Mốc M1**

- **TV1**
  - [ ] Hỗ trợ chạy toàn bộ kịch bản fusion qua simulator.
- **TV2**
  - [ ] `fusion_service`: `max`, hysteresis hai phiên, ack, vòng đời, loại trùng; đánh dấu quyết định nhánh quá hạn.
  - [ ] Watchdog kênh kỹ thuật: quét `last_seen` định kỳ → `disconnected`; pin; `not_worn`; `signal_poor` sau K phiên.
  - [ ] `local_alert` bản đầu: GPIO còi + LED.
  - [ ] Truy vết đầy đủ mỗi lần ra `L`.
- **TV3**
  - [ ] Compose đủ service; `restart: always`; đo độ trễ từ gói vào đến `gateway/alert`.
- **Sản phẩm (M1):** demo đầu–cuối với simulator: bình thường, SpO2 thấp, thiếu tham số, PPG nhiễu, té ngã, ngã + PPG nhiễu, mất mạng. Không vi phạm quy tắc fusion.

### Giai đoạn 3 — Phần cứng thật, đồng bộ, học máy (tuần 8–11)

#### Tuần 8 — Đồng bộ cloud, bảo mật, nhánh trend khung

- **TV1**
  - [ ] Kết nối BLE với vòng đeo thật (nếu firmware sẵn sàng) hoặc ESP32 phát gói giả.
- **TV2**
  - [ ] Trích đặc trưng xu hướng 2 giờ từ lịch sử; `trend_service` đọc đặc trưng và gọi mô hình (tạm hằng số).
  - [ ] Màn hình cục bộ (web nhỏ) hiển thị lưới giường và nút ack.
  - [ ] Lệnh escalate `gateway/cmd/{id}` khi `L ≥ 2`.
- **TV3**
  - [ ] `cloud_sync`: outbox, retry backoff, `event_id`; nhận lệnh/tham số từ cloud.
  - [ ] Mosquitto: user/password, ACL theo topic, TLS; bỏ `allow_anonymous`.
- **Sản phẩm:** ngắt WAN 30 phút, nối lại → đồng bộ đủ, không trùng.

#### Tuần 9 — BLE thật và dữ liệu huấn luyện

- **TV1**
  - [ ] `ble_scanner` + `connection_pool`: nhiều vòng đeo, kết nối lại có backoff, gói bù sau mất kết nối.
  - [ ] Ghi metric RSSI, tỉ lệ mất gói theo thiết bị.
- **TV2**
  - [ ] Chạy kịch bản fusion trên dữ liệu thật đầu tiên; ghi lỗi.
- **TV3**
  - [ ] Chuẩn bị dataset IMU công khai, chia theo đối tượng thành client mô phỏng (non-IID).
  - [ ] `local_trainer.py`: huấn luyện SNN bằng snnTorch (surrogate gradient) trên PC.
- **Sản phẩm:** 1–2 vòng đeo thật gửi được dữ liệu qua BLE vào gateway.

#### Tuần 10 — Federated Learning ba luồng

- **TV1**
  - [ ] Thu phiên PPG đồng thời với máy kẹp ngón (tình nguyện viên, có phiếu đồng ý) → dữ liệu hiệu chuẩn SpO2 và nhãn SQI.
- **TV2**
  - [ ] Tạo nhãn trend tự sinh từ lịch sử NEWS2; phối hợp TV3 huấn luyện MLP.
- **TV3**
  - [ ] `fl_client`: ba luồng FedAvg tách theo `architecture_version`; chỉ gửi trọng số.
  - [ ] `model_diff_encoder.py`: đóng gói cập nhật, đo chi phí truyền.
  - [ ] `privacy_guard.py`: chặn gửi bất kỳ thứ gì ngoài trọng số đã khai báo.
  - [ ] Hybrid FL: Pi thật + ≥ 3 client mô phỏng cho `arch.snn`.
- **Sản phẩm:** một vòng FedAvg `arch.snn` hoàn chỉnh có log.

#### Tuần 11 — Phát hành mô hình và OTA

- **TV1**
  - [ ] Hiệu chuẩn hệ số SpO2 `a, b, c` từ dữ liệu tuần 10; cập nhật cấu hình.
  - [ ] Hỗ trợ kênh BLE cho OTA.
- **TV2**
  - [ ] Đưa MLP trend vào `trend_service`; kiểm thử `L_trend ≤ 2`.
- **TV3**
  - [ ] Kiểm định trước phát hành (độ nhạy `fall_like` không giảm); `model_version` theo thiết bị.
  - [ ] `esp32_model_pusher.py`: chia khối, CRC, rollback.
  - [ ] Lượng tử hóa int8 trọng số SNN.
- **Sản phẩm (M2):** mô hình mới đi trọn đường: train → FedAvg → kiểm định → OTA.

### Giai đoạn 4 — Đánh giá và hoàn thiện (tuần 12–14)

#### Tuần 12 — Thí nghiệm theo PDF mục 11

- **TV1**
  - [ ] Sinh hiệu: MAE và Bland–Altman HR, SpO2, RR, nhiệt so với máy chuẩn; tỉ lệ phiên bị loại.
- **TV2**
  - [ ] NEWS2: 100 % trên bộ biên; so nhóm nguy cơ hệ thống với tính tay của người đánh giá.
  - [ ] Té ngã: độ nhạy, báo giả mỗi giờ, tỉ lệ tự hủy đúng (ngã có đệm + ADL).
  - [ ] Fusion: chạy toàn bộ kịch bản tổng hợp, báo cáo vi phạm = 0.
- **TV3**
  - [ ] FL: local-only / FedAvg / centralized — F1, chi phí truyền, số vòng hội tụ.
- **Sản phẩm:** bảng kết quả thô cho báo cáo.

#### Tuần 13 — Chạy dài và độ bền — **Mốc M3**

- **TV1**
  - [ ] Chạy 3 vòng đeo liên tục ≥ 8 giờ; thống kê mất gói, kết nối lại.
- **TV2**
  - [ ] Rà truy vết: chọn ngẫu nhiên 20 cảnh báo, dựng lại đúng lý do từ log/DB.
- **TV3**
  - [ ] Đo độ trễ đầu–cuối (mục tiêu < 10 s từ khi có kết quả đo hợp lệ), CPU/RAM Pi.
  - [ ] Thử lỗi: kill service, rút điện Pi, đầy đĩa, mất WAN.
- **Sản phẩm (M3):** hệ thống chạy ổn định, có số liệu độ trễ và độ bền.

#### Tuần 14 — Báo cáo và bảo vệ

- **Cả nhóm**
  - [ ] Hoàn thiện báo cáo theo chương đã chia (mục 2).
  - [ ] Video demo các kịch bản M1 trên phần cứng thật.
  - [ ] README chạy lại được từ đầu trên máy mới.
  - [ ] Slide, phân vai trình bày, chuẩn bị câu hỏi phản biện (giới hạn PDF mục 12).

---

## 6. Mốc nghiệm thu

| Mốc | Tuần | Điều kiện đạt |
|-----|------|---------------|
| M0 | 2 | Schema bản tin `contracts-v1` được duyệt; Pi chạy broker; CI chạy |
| M1 | 7 | Đường nóng đầu–cuối với simulator, đủ kịch bản fusion, còi tại chỗ khi mất WAN |
| M2 | 11 | BLE thật; một mô hình đi trọn train → FedAvg → kiểm định → OTA |
| M3 | 13 | Kết quả thí nghiệm PDF mục 11; chạy ≥ 8 giờ; độ trễ < 10 s |
| M4 | 14 | Báo cáo, demo, mã chạy lại được |

---

## 7. Chiến lược kiểm thử

| Mức | Công cụ | Nội dung | Chủ |
|-----|---------|----------|-----|
| Đơn vị | `pytest` | Công thức sinh hiệu, bảng NEWS2, máy trạng thái té ngã, fusion | chủ module |
| Hợp đồng | JSON Schema | Mọi gói vào/ra đúng schema | TV1 |
| Tích hợp | `pytest` + broker thật trong Docker | Một luồng topic qua nhiều service | TV3 |
| Kịch bản | Simulator + YAML | Danh sách dưới | TV2 |
| Chạy dài | Simulator nhiều thiết bị | 8 giờ, mất gói, kết nối lại | TV1 |
| Lỗi | Kill process, rút mạng, rút điện | Khôi phục trạng thái, không mất cảnh báo | TV3 |

Bộ kịch bản tối thiểu (mỗi kịch bản có kết quả `L` và kênh kỹ thuật mong đợi):

1. Đủ 7 tham số bình thường → `L = 0`.
2. Chỉ HR, SpO2 bình thường → `L = 1` (thiếu dữ liệu không phải nguy cơ thấp).
3. SpO2 91 % → `S_max = 3` → `L = 2`.
4. Tổng `S = 7` → `L = 3`.
5. RR ước lượng đẩy nhóm nguy cơ lên → `needs_confirmation`.
6. Manual và auto cùng còn hiệu lực → dùng manual.
7. Giá trị nhập tay hết Θ → thành thiếu.
8. PPG nhiễu → tham số thiếu, `signal_poor`, `L` không tăng vì nhiễu.
9. Ngã nằm im → `L = 3`.
10. Ngã + PPG nhiễu → vẫn `L = 3`.
11. Ngã rồi đi lại ≥ 5 s → `auto_cancelled`, `L_fall = 1`.
12. Ngã rồi bấm nút → `manual_cancelled`, `L_fall = 1`.
13. Ngã rồi mất kết nối → `fall_confirmed`.
14. `p_det` cao khi `L_news = 2` → `L_trend = 2`, không lên 3.
15. `L` từ 2 xuống 0: phải qua hai phiên hoặc ack.
16. Gửi trùng gói → một bản ghi.
17. Mất heartbeat 90 s → `disconnected`, `L` không đổi.
18. Mất WAN khi `L = 3` → còi kêu, đồng bộ sau.

---

## 8. Quy trình làm việc nhóm

- **Họp:** thứ Hai (lên kế hoạch tuần, 30 phút), thứ Năm (demo tiến độ, gỡ vướng, 30 phút). Ghi biên bản ngắn trong `docs/meetings/`.
- **Git:**
  - Nhánh chính `main` luôn chạy được; mỗi việc một nhánh `feat/<module>-<mô-tả>`.
  - Pull Request phải có: mô tả, cách kiểm thử, CI xanh, **một người khác duyệt** (chủ module duyệt nếu đụng module người khác).
  - Commit dạng `feat(news2): ...`, `fix(fall): ...`, `test(fusion): ...`.
  - Không commit `.env`, dữ liệu người tham gia, khóa/chứng chỉ.
- **Theo dõi công việc:** mỗi checkbox trong file này thành một issue có nhãn tuần (`w01`…`w14`) và chủ sở hữu.
- **Định nghĩa hoàn thành chung (áp cho mọi đầu việc):**
  - [ ] Có kiểm thử tự động và đang xanh.
  - [ ] Đúng hợp đồng bản tin.
  - [ ] Log và metric cho đường chính.
  - [ ] Cập nhật README / tài liệu module.
  - [ ] Đã demo trong buổi họp thứ Năm.
- **Thay đổi ngưỡng lâm sàng** (`τ_impact`, `τ_snn`, `τ_angle`, `τ_sqi`, `τ_det`, IQR…): phải tăng `ALGORITHM_VERSION` và ghi lý do.

---

## 9. Rủi ro và phương án dự phòng

| Rủi ro | Dấu hiệu | Phương án |
|--------|----------|-----------|
| Firmware vòng đeo chậm | Tuần 8 chưa có gói BLE thật | Tiếp tục bằng simulator; dùng ESP32 phát gói giả qua BLE để kiểm thử transport |
| BLE nhiều thiết bị không ổn định trên Pi | Mất kết nối liên tục | Giới hạn số thiết bị/Pi, tăng khoảng kết nối, gửi theo lô; phương án dự phòng Wi-Fi MQTT từ ESP32 |
| SpO2 cổ tay kém chính xác | Tỉ lệ phiên bị loại cao | Báo cáo trung thực tỉ lệ loại (PDF giới hạn 1); không nới cổng |
| Không có máy đo chuẩn để làm nhãn SQI | Tuần 10 không thu được | Bỏ `arch.sqi` khỏi FL, giữ SQI bằng luật |
| SNN không hội tụ | F1 thấp sau nhiều epoch | So sánh với MLP/1D-CNN nhỏ làm baseline; báo cáo kết quả |
| FL tốn thời gian tích hợp | Tuần 10 chưa có vòng FedAvg | Ưu tiên `arch.snn`; hai mô hình còn lại để báo cáo mô phỏng |
| Pi quá tải | CPU > 80 % | Gộp service nhẹ, huấn luyện ngoài giờ cao điểm, giảm tần số FL |
| Thành viên vắng | Việc trễ > 1 tuần | Mỗi module có người hỗ trợ (mục 2) đọc hiểu được mã |

---

## 10. Quyết định cần chốt ở tuần 1

- [ ] **Số tuần thực tế** của học kỳ, điều chỉnh lịch mục 5.
- [ ] **Giao tiếp vòng đeo – Pi:** BLE như PDF, hay Wi-Fi MQTT giai đoạn đầu rồi chuyển BLE.
- [ ] **Triển khai trên Pi:** Docker Compose `restart: always` hay systemd như PDF.
- [ ] **Framework FL:** Flower hay tự viết.
- [ ] **Mô hình SNN:** dùng snnTorch; kích thước 12 → 32 → 5 như PDF hay thử nghiệm thêm.
- [ ] **Đường gói 18 byte cũ:** giữ cho simulator hay bỏ.
- [ ] **`src/ml_inference/*` (PatchTST/Informer):** xóa hay tái sử dụng làm khung MLP trend.
- [ ] **Màn hình cục bộ:** web nhỏ trên Pi hay màn hình gắn trực tiếp.
- [ ] **Nguồn dữ liệu:** dataset IMU công khai nào; có máy đo SpO2 chuẩn và nhiệt kế chuẩn không; thủ tục phiếu đồng ý cho tình nguyện viên.
- [ ] **Ngưỡng khởi tạo** (`τ_impact = 2.5 g`, `τ_angle = 60°`, `τ_snn`, `τ_sqi`, `τ_det`): ai duyệt, ghi ở đâu.
