# W3-D3 Submission — haikhoa

## Outage chosen

- ID: 1
- Name: AWS S3 us-east-1 2017-02-28
- Why this one: Pattern "Operator action without guardrail" là failure mode cơ bản nhất nhưng gây hậu quả lớn nhất — một lệnh gõ nhầm làm sập nửa internet. Muốn hiểu tại sao hệ thống critical nhất thế giới lại thiếu guardrail đơn giản như confirmation prompt.
- Failure mode: operator (operator action without guardrail)

## 3 thứ em học từ outage này

1. **Blast-radius guardrail quan trọng hơn mọi monitoring.** Không có monitoring nào detect kịp một lệnh xóa server chạy trong vài giây. Prevention (guardrail) >> Detection (monitoring) trong trường hợp operator error. Cụ thể: nếu tool yêu cầu confirm "sẽ remove 500 server từ 3 subsystem, proceed?" thì sự cố không xảy ra.

2. **Monitoring dependency loop là failure mode rất thực.** AWS Service Health Dashboard depend on S3 → khi S3 sập, dashboard vẫn hiện xanh. Đây chính xác là pattern mà pipeline của em cũng mắc (Experiment #7 W3-D2: log-collector disk fill → pipeline mù). Bài học: monitoring stack PHẢI có đường kiểm tra sức khỏe ĐỘC LẬP với hệ thống được monitor.

3. **Recovery time cho hệ thống chưa từng restart là unpredictable.** S3 index subsystem chưa restart toàn bộ trong nhiều năm → khi phải restart, team không biết mất bao lâu, phát hiện bottleneck mới lần đầu dưới áp lực incident. Bài học: phải diễn tập restart/recovery định kỳ (quarterly drill) — giống chaos engineering nhưng cho recovery procedure.

## 1 thứ pipeline của em sẽ vẫn miss nếu outage này xảy ra real

- Pattern: Operator action without guardrail — human executes over-broad command
- Why miss: Pipeline AIOps detect anomaly SAU KHI hệ thống đã bị ảnh hưởng (reactive). Nhưng operator error xảy ra trong vài giây — từ lúc lệnh chạy đến lúc 5 service chết chỉ mất ~10s. Pipeline cần ít nhất 1-2 metric scrape cycles (15-30s) để nhận ra anomaly. Khi đó damage đã xong. Thêm nữa, nếu operator command xóa luôn monitoring components (giống S3 dashboard depend on S3), pipeline sẽ mù hoàn toàn.
- Mitigation idea: (1) Pre-execution validation ở tầng tooling — tool phải dry-run và hiện blast radius trước khi thực thi. (2) Independent watchdog chạy trên infrastructure riêng, health-check hệ thống mỗi 5s bằng synthetic probe, alert qua kênh riêng (SMS, PagerDuty) không phụ thuộc vào stack đang monitor.

## 1 quyết định trong ADR mà em không hoàn toàn chắc

Trọng số 0.5 / 0.4 / 0.1 cho 3 signal (topology / first-drift / alert-volume) trong ADR-001 là ước lượng, chưa validate bằng dữ liệu thực. Có thể topology weight 0.5 quá cao cho hệ thống có flat topology (ít layer), hoặc first-drift weight 0.4 quá cao khi metric scrape interval lớn (30s) làm temporal resolution thấp. Cần grid search trên ≥ 20 incident scenario để tìm optimal weights — hiện mới chỉ test 10 chaos experiment. Sai weights có thể khiến RCA mới tệ hơn count-based trong edge cases.

## Cost model verdict cho stack của em

- ROI: 6.0
- Payback: 0.17 tháng (~5 ngày)
- Verdict: worth_it
