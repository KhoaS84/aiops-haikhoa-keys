# DESIGN.md — Ronki Closed-Loop Orchestrator

## 1. Decision engine: Rule-based hay LLM-based?

**Chọn: Rule-based.**

Lý do:
- Stack Ronki có các alert được định nghĩa rõ ràng (`HighLatency`, `HighErrorRate`, `InstanceDown`, `MultiStepDeploy`) và mỗi loại map 1-1 với một runbook đã được ops team kiểm chứng.
- Rule-based cung cấp **latency quyết định cực nhanh (< 1ms)** và **deterministic** (đảm bảo tính nhất quán: cùng một alert luôn trigger cùng một runbook), loại bỏ hoàn toàn rủi ro hallucination (ảo tưởng) của LLM trong môi trường production nhạy cảm.

Trade-offs:

| Tiêu chí | Rule-based | LLM-based |
|---|---|---|
| Latency quyết định | < 1ms | 200–800ms (API round-trip) |
| Determinism (Tính nhất quán) | 100% (Tuyệt đối) | Phụ thuộc temperature, prompt |
| Mở rộng alert mới | Cần cập nhật map thủ công | Tự suy luận nếu prompt đủ tốt |
| Chi phí | Không | Có phí API |
| Fallback khi offline | Không cần | Cần rule-based làm fallback |

---

## 2. Blast-radius config

Cấu hình blast radius được định nghĩa trong `config.yaml`:
```yaml
blast_radius:
  max_actions_per_minute: 10
  max_restarts_per_service_per_hour: 5
```

Lý do chọn giá trị:
- `max_actions_per_minute: 10` — Cho phép hệ thống xử lý nhanh các sự cố đồng thời ở quy mô lớn hoặc chạy song song nhiều bước tự động hóa mà không bị nghẽn (đặc biệt khi thực hiện test concurrency).
- `max_restarts_per_service_per_hour: 5` — Ngăn chặn hành vi loop vô hạn (restart liên tục một dịch vụ bị lỗi nghiêm trọng như cấu hình sai, OOM liên tục, lỗi code). Sau 5 lần restart trong 1 giờ không thành công, hệ thống sẽ log `BLAST_RADIUS_EXCEEDED` và dừng tự động hóa để chuyển tiếp cho kỹ sư on-call xử lý thủ công.

---

## 3. Verify step

**Metric kiểm tra:** p99 latency (ms) và trạng thái sống sót (`up`).

**Ngưỡng (Threshold):**
- `latency_p99_max_ms: 500` — Dựa theo `baseline.json`, p99 latency ở trạng thái bình thường của dịch vụ chậm nhất (`checkout-svc`) là ~230ms. Đặt ngưỡng 500ms (khoảng 2x baseline) giúp lọc nhiễu tốt (tránh false positive) nhưng phát hiện ngay khi dịch vụ bị trễ nặng.
- `up_required: 1` — Đảm bảo dịch vụ hoàn toàn online và phản hồi được trước khi đo đạc latency.

**Timeout và Polling:**
- `verify_timeout_seconds: 60` — Thời gian đủ để container khởi động lại và metric Prometheus được cập nhật ổn định qua các scrape cycle (scrape interval là 10s).
- `verify_poll_interval_seconds: 10` — Trùng khớp với scrape interval của Prometheus để lấy dữ liệu mới nhất mà không gây quá tải API.
- `verify_min_samples: 3` — Yêu cầu tối thiểu 3 mẫu liên tiếp đạt chuẩn nhằm ngăn chặn false positive (do một request may mắn phản hồi nhanh trước khi container ổn định).

---

## 4. Circuit breaker reset

**Reset mode: manual (thủ công).**

Lý do:
- Khi circuit breaker chuyển sang `LOCKED` (mở cầu chì sau 3 consecutive failures), hệ thống đang ở trạng thái lỗi rất nghiêm trọng (đã chạy tự động phục hồi và rollback 3 lần đều thất bại).
- Tự động reset cầu chì có thể dẫn đến loop thảm họa (ví dụ: cạn kiệt kết nối database, thundering herd làm sập các dịch vụ lân cận).
- Việc bắt buộc kỹ sư can thiệp thủ công (tìm nguyên nhân gốc, sửa chữa và khởi động lại orchestrator) đảm bảo an toàn tối đa cho hệ thống production.

---

## 5. Mutex strategy (Concurrency/Locks)

Để xử lý các sự cố đồng thời mà không bị xung đột, orchestrator sử dụng cấu trúc lock theo từng dịch vụ:
- Mỗi dịch vụ được gán một `threading.Lock` trong một dictionary được bảo vệ bởi một meta-lock.
- Khi alert đến, orchestrator sử dụng `svc_lock.acquire(blocking=False)`.
- Nếu khóa đã được giữ (dịch vụ đang có runbook chạy), orchestrator sẽ log `SERVICE_LOCK_BUSY` và bỏ qua alert trùng lặp đó ngay lập tức thay vì xếp hàng chờ. Việc này tránh chạy đè runbook lên một dịch vụ đang trong tiến trình phục hồi.
- Các dịch vụ khác nhau có các khóa khác nhau nên các luồng (thread) xử lý hoàn toàn song song mà không block lẫn nhau.

---

## 6. Rollback chain ordering (Multi-step transactional deploy)

Với các quy trình triển khai đa bước (Step A $\rightarrow$ B $\rightarrow$ C):
- Orchestrator lưu trữ lịch sử các bước đã thực hiện thành công vào một danh sách (`completed`).
- Nếu có bất kỳ bước nào thất bại (ví dụ: Step C lỗi), orchestrator sẽ kích hoạt rollback theo thứ tự ngược lại (LIFO - Last In First Out): chỉ rollback các bước đã hoàn thành (ví dụ: Rollback B rồi tới Rollback A), và không đụng vào bước chưa chạy.
- Nguyên tắc reverse-order này tương tự cơ chế rollback transaction của database, đảm bảo hệ thống quay trở lại trạng thái ban đầu một cách an toàn mà không bị mâu thuẫn phụ thuộc.

---

## 7. Decision validation policy (LLM Hallucination Defense)

Để ngăn chặn các quyết định không an toàn hoặc ảo tưởng (hallucination) từ LLM (trả về tên runbook không tồn tại):
- Orchestrator duy trì một whitelist registry chứa toàn bộ các đường dẫn runbook được cho phép (`runbook_registry` trong file `config.yaml`).
- Trước khi thực thi bất cứ lệnh nào (kể cả dry-run), orchestrator đối chiếu tên runbook nhận được với registry.
- Nếu không khớp, orchestrator ngay lập tức ngắt tiến trình, ghi nhận lỗi `DECISION_VALIDATION_FAILED` chứa đầy đủ chi tiết sự việc, và leo thang (escalate) mà không chạy bất kỳ subprocess nào, giữ nguyên an toàn cho hệ thống.
