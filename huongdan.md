# Hướng dẫn Vận hành & Cấu trúc mã nguồn Closed-Loop Auto-Remediation

Tài liệu này hướng dẫn chi tiết cấu trúc mã nguồn đã chỉnh sửa, các bước triển khai cũng như các lệnh Terminal để chạy thực nghiệm và nghiệm thu 6 kịch bản Chaos Test của hệ thống Closed-Loop Auto-Remediation.

---

## 📂 1. Cấu trúc thư mục dự án `ronki-orchestrator`

Thư mục bài nộp [ronki-orchestrator](file:///C:/Users/ASUS/OneDrive/Obsidian%20Vault/XBrain-Phase2/W3%20-%20Reliability%20Engineering%20&%20Postmortem/D4/lab-closed-loop/ronki-orchestrator) được xây dựng hoàn chỉnh và đóng gói độc lập bao gồm các tệp tin và cấu trúc như sau:

* **[closed_loop.py](file:///C:/Users/ASUS/OneDrive/Obsidian%20Vault/XBrain-Phase2/W3%20-%20Reliability%20Engineering%20&%20Postmortem/D4/lab-closed-loop/ronki-orchestrator/closed_loop.py)**: Mã nguồn chính của orchestrator điều hành hệ thống Closed-loop Auto-remediation.
* **[config.yaml](file:///C:/Users/ASUS/OneDrive/Obsidian%20Vault/XBrain-Phase2/W3%20-%20Reliability%20Engineering%20&%20Postmortem/D4/lab-closed-loop/ronki-orchestrator/config.yaml)**: Tệp cấu hình chứa các quy định ánh xạ cảnh báo (alert) sang runbook, whitelist registry, blast-radius limit và circuit-breaker limit.
* **[DESIGN.md](file:///C:/Users/ASUS/OneDrive/Obsidian%20Vault/XBrain-Phase2/W3%20-%20Reliability%20Engineering%20&%20Postmortem/D4/lab-closed-loop/ronki-orchestrator/DESIGN.md)**: Bản thiết kế giải pháp và phòng vệ kiến trúc (architecture defense).
* **[SUBMIT.md](file:///C:/Users/ASUS/OneDrive/Obsidian%20Vault/XBrain-Phase2/W3%20-%20Reliability%20Engineering%20&%20Postmortem/D4/lab-closed-loop/ronki-orchestrator/SUBMIT.md)**: Kết quả nghiệm thu thực tế với 6 kịch bản test.
* **`engine/`**: Thư mục chứa các module bổ trợ được kế thừa từ data-pack:
  * `logger.py`: Xuất log theo cấu trúc JSON phục vụ phân tích log.
  * `metrics.py`: Khởi tạo Prometheus client để xuất số liệu hoạt động.
  * `safety.py`: Các logic kiểm tra giới hạn Blast Radius và Circuit Breaker.
  * `verify.py`: Gọi Prometheus API và thực hiện xác thực độ trễ (verify) dựa trên ngưỡng baseline.
* **`runbooks/`**: Các script thực thi hành động khôi phục:
  * `restart_service.sh`: Khởi động lại docker container của dịch vụ.
  * `clear_cache.sh`: Xoá bộ nhớ cache.
  * `scale_replicas.sh`: Thay đổi số lượng replica dịch vụ.
  * `multi_step_deploy.sh`: Script đặc biệt dùng cho triển khai đa bước (Transactional Multi-step).

---

## 🛠️ 2. Các phần mã nguồn được thiết kế & chỉnh sửa

### 1️⃣ Điều phối chính `closed_loop.py`
Mã nguồn này được viết mới hoàn toàn để xử lý 5 trạm kiểm soát (checkpoints) và tích hợp các tính năng mở rộng chịu tải (stress extensions):
* **Concurrency & Mutex (Scenario 5)**: Sử dụng bản đồ Lock (`threading.Lock`) được phân chia theo từng tên dịch vụ (`service`). Khi có nhiều luồng cảnh báo đồng thời, các dịch vụ khác nhau chạy song song không block nhau, nhưng các cảnh báo trùng lặp trên cùng một dịch vụ sẽ bị block ngay lập tức và ghi nhận log `SERVICE_LOCK_BUSY`.
* **Decision Validation / Hallucination Defense (Scenario 6)**: Trước khi thực hiện bất kỳ hành động nào, orchestrator kiểm tra xem câu lệnh/runbook khớp với Whitelist Registry trong `config.yaml` hay không. Nếu không khớp, chặn đứng hành động và log ra `DECISION_VALIDATION_FAILED`.
* **Transactional Multi-step & Reverse Rollback (Scenario 4)**: Định nghĩa tiến trình chạy lần lượt theo chuỗi bước (ví dụ: `Step A -> Step B -> Step C`). Nếu một bước bất kỳ thất bại (`TRANSACTIONAL_STEP_FAIL`), orchestrator lập tức thực hiện rollback các bước đã hoàn thành trước đó theo thứ tự đảo ngược (ví dụ: `Rollback B -> Rollback A`) rồi log ra `TRANSACTIONAL_ROLLBACK_COMPLETE`.
* **Verify & Auto-rollback (Scenario 1 & 2)**: Sau khi thực hiện action thực tế, hệ thống tiến hành gọi API Prometheus để lấy số liệu thực tế p99 latency của dịch vụ trong khoảng thời gian nhất định và đối chiếu với baseline JSON. Nếu verify thất bại, tiến hành chạy runbook rollback tự động.
* **Circuit Breaker (Scenario 3)**: Khi phát hiện 3 lần verify thất bại liên tiếp, cầu chì sẽ nhảy (`is_open()`), ghi nhận log `CIRCUIT_BREAKER_HALT` và đóng băng toàn bộ tiến trình quét alert cho tới khi được khởi động lại thủ công.

### 2️⃣ Cấu hình hệ thống `config.yaml`
Tệp cấu hình được thiết kế tỉ mỉ để quản lý toàn bộ các kịch bản hành động, cấu hình ngưỡng và whitelist chạy runbook.

---

## 💻 3. Hướng dẫn các lệnh chạy trong Terminal

Để thực nghiệm 6 kịch bản, bạn hãy mở **3 cửa sổ Terminal** riêng biệt và thực hiện lần lượt các bước sau:

### 🖥️ Terminal 1: Docker Stack & Load Generator
**Bước 1: Khởi động các container Docker của hệ thống**
```bash
# Khởi chạy docker compose stack
bash data-pack/scripts/start_stack.sh
```

**Bước 2: Chạy Python Load Generator liên tục**
*Để Prometheus có dữ liệu tính toán latency thực tế một cách chuẩn xác, bạn cần tạo luồng request liên tục (5 req/s cho mỗi container):*
```bash
python -c "import urllib.request, time, threading; urls=['http://localhost:8080/', 'http://localhost:8081/', 'http://localhost:8082/', 'http://localhost:8083/', 'http://localhost:8084/']; [threading.Thread(target=lambda u: [ (urllib.request.urlopen(u).read(), time.sleep(0.2)) for _ in iter(int, 1) ], daemon=True).start() for u in urls]; time.sleep(999999)"
```

---

### 🖥️ Terminal 2: Khởi chạy Orchestrator
**Bước 1: Cài đặt các thư viện Python cần thiết (nếu chưa cài)**
```bash
uv pip install requests pyyaml prometheus_client
```

**Bước 2: Di chuyển vào thư mục bài nộp và khởi động orchestrator**
```bash
cd ronki-orchestrator
uv run python closed_loop.py --config config.yaml
```

---

### 🖥️ Terminal 3: Thực hiện Chaos Tests (Kích hoạt 6 kịch bản lỗi)
Bạn sử dụng `curl` để POST trực tiếp cảnh báo giả lập vào Alertmanager API, kích hoạt phản hồi tự động từ Orchestrator:

#### 1️⃣ Kịch bản 1: Phục hồi thành công (Latency trên `payment-svc`)
```bash
# Gửi cảnh báo HighLatency trên payment-svc
curl -H "Content-Type: application/json" -d '[{"labels":{"alertname":"HighLatency","service":"payment-svc","severity":"warning","uniq":"scen-1"}}]' http://localhost:9093/api/v2/alerts
```
* **Kết quả mong đợi**: Cảnh báo được bắt $\rightarrow$ Orchestrator restart container `ronki-payment-svc` $\rightarrow$ Verify thành công (do latency thực tế khoảng 248ms < threshold baseline 500ms) $\rightarrow$ Log ra `ACTION_SUCCESS`.

#### 2️⃣ Kịch bản 2 & 3: Rollback tự động & Ngắt cầu chì (Circuit Breaker)
*Để tạo kịch bản verify luôn thất bại, bạn sửa giá trị `"latency_p99_max_ms": 500` thành `"latency_p99_max_ms": 1` trong tệp `data-pack/data/baseline.json`.*

Sau khi sửa tệp baseline, khởi động lại Orchestrator ở **Terminal 2**, sau đó chạy liên tiếp 3 lệnh sau ở **Terminal 3**:
```bash
# Cảnh báo 1: Lỗi verify -> rollback
curl -H "Content-Type: application/json" -d '[{"labels":{"alertname":"HighLatency","service":"payment-svc","severity":"warning","uniq":"cb-1"}}]' http://localhost:9093/api/v2/alerts

# Cảnh báo 2: Lỗi verify -> rollback
curl -H "Content-Type: application/json" -d '[{"labels":{"alertname":"HighLatency","service":"inventory-svc","severity":"warning","uniq":"cb-2"}}]' http://localhost:9093/api/v2/alerts

# Cảnh báo 3: Lỗi verify -> rollback -> SẬP CẦU CHÌ
curl -H "Content-Type: application/json" -d '[{"labels":{"alertname":"HighLatency","service":"checkout-svc","severity":"warning","uniq":"cb-3"}}]' http://localhost:9093/api/v2/alerts
```
* **Kết quả mong đợi**: Ở Terminal 2, Orchestrator sẽ báo lỗi Verify cho cả 3 alert và kích hoạt Rollback cho từng dịch vụ tương ứng. Sau lần thứ 3, xuất hiện log `CIRCUIT_BREAKER_HALT`. Toàn bộ hoạt động quét cảnh báo bị đóng băng.
* *Khôi phục lại baseline:* Đổi lại ngưỡng `1` thành `500` trong `baseline.json` và restart Orchestrator ở Terminal 2 để tiếp tục các bài test khác.

#### 3️⃣ Kịch bản 4: Triển khai đa bước & Rollback ngược thứ tự (`api-gateway`)
```bash
# Gửi cảnh báo MultiStepDeploy
curl -H "Content-Type: application/json" -d '[{"labels":{"alertname":"MultiStepDeploy","service":"api-gateway","severity":"warning","uniq":"scen-4"}}]' http://localhost:9093/api/v2/alerts
```
*Để phá huỷ Step C bắt buộc lỗi xảy ra, bạn hãy mở thêm Terminal phụ hoặc dùng Terminal 3 gõ lệnh dừng container api-gateway ngay khi Terminal 2 đang thực hiện Step B (khoảng 2 giây sau lệnh curl):*
```bash
docker stop ronki-api-gateway
```
* **Kết quả mong đợi**: Orchestrator cố chạy Step C nhưng thất bại vì container đã tắt $\rightarrow$ ghi nhận `TRANSACTIONAL_STEP_FAIL` $\rightarrow$ Tiến hành rollback ngược thứ tự: Rollback B $\rightarrow$ Rollback A $\rightarrow$ Log ra `TRANSACTIONAL_ROLLBACK_COMPLETE`.
* *Khôi phục lại stack:* Chạy lệnh dưới đây để start lại container:
  ```bash
  docker start ronki-api-gateway
  ```

#### 4️⃣ Kịch bản 5: Xử lý alert đồng thời (Concurrency / Locks)
```bash
# Gửi đồng thời hai alert của payment-svc và inventory-svc
curl -H "Content-Type: application/json" -d '[{"labels":{"alertname":"HighLatency","service":"payment-svc","severity":"warning","uniq":"concur-1"}}, {"labels":{"alertname":"HighLatency","service":"inventory-svc","severity":"warning","uniq":"concur-2"}}]' http://localhost:9093/api/v2/alerts

# Gửi ngay lập tức một alert trùng lặp tiếp theo của payment-svc (sau 2-3s)
curl -H "Content-Type: application/json" -d '[{"labels":{"alertname":"HighLatency","service":"payment-svc","severity":"warning","uniq":"concur-3"}}]' http://localhost:9093/api/v2/alerts
```
* **Kết quả mong đợi**: Luồng xử lý cho `payment-svc` và `inventory-svc` sẽ chạy song song không block nhau. Alert gửi sau của `payment-svc` (alert thứ 3) sẽ bị khoá dịch vụ chặn lại và log ra `SERVICE_LOCK_BUSY`.

#### 5️⃣ Kịch bản 6: Chống LLM Hallucination (Validation)
```bash
# Gửi alert trỏ tới runbook không có trong whitelist registry
curl -H "Content-Type: application/json" -d '[{"labels":{"alertname":"TestHallucination","service":"payment-svc","severity":"warning","uniq":"scen-6"}}]' http://localhost:9093/api/v2/alerts
```
* **Kết quả mong đợi**: Orchestrator phát hiện `TestHallucination` ánh xạ tới runbook lạ không có trong whitelist registry $\rightarrow$ lập tức chặn đứng tiến trình và xuất ra log lỗi `DECISION_VALIDATION_FAILED` chứa đầy đủ thông tin sự kiện cảnh báo.
