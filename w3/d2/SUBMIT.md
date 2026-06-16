# W3-D2 Submission — haikhoa

## 3 thứ em học được về AIOps pipeline của mình

1. **Pipeline detect tốt các fault có signal rõ ràng, nhưng "blind" với infrastructure fault.** 9/10 fault được detect (recall 90%), nhưng experiment duy nhất miss (#7 log-collector disk fill) cho thấy pipeline KHÔNG monitor health của chính infrastructure components mà nó phụ thuộc. Đây là monitoring dependency loop (§7.5) — pipeline sống trên log-collector nhưng không biết khi log-collector chết. Trong production, điều này có nghĩa nếu log ingestion dừng + fault khác xảy ra đồng thời → pipeline vừa blind vừa không có log evidence cho RCA → double failure.

2. **RCA bị đánh lừa bởi retry amplification — pick service ồn nhất thay vì root cause.** 3 experiment (#4 CPU stress, #9 DNS slow, #10 retry storm) đều cho cùng 1 pattern: RCA pick payment-svc vì nó fire nhiều alert nhất. Nhưng payment-svc chỉ là "nạn nhân" (downstream nhận retry cascade), root cause thật là upstream service. RCA hiện tại dùng alert count ranking → luôn sai khi có retry amplification. Cần topology-aware + temporal-causal analysis (Granger causality hoặc cross-correlation lag) để pick service có drift TRƯỚC downstream.

3. **Synthetic probe (external) là signal đáng tin nhất để đo user impact — independent hoàn toàn khỏi pipeline.** `probe.log` chạy từ host machine bắt được user-visible impact mà internal metrics có thể miss. Ví dụ: experiment #7 — internal metrics tất cả xanh (Prometheus scrape OK, service latency bình thường) nhưng pipeline bị blind vì mất log source. Ngược lại, experiment #8 (network partition) — probe ghi nhận 100% fail trong 30s, confirm user impact ngay lập tức mà không cần chờ pipeline process. Probe external đóng vai ground truth cho "system có OK với user không?".

---

## 1 fault mà em mong pipeline catch nhưng nó miss

- **Experiment:** #7 — log-collector disk fill 95%
- **Why I expected detection:** Disk usage là metric infrastructure cơ bản. Log ingestion lag ảnh hưởng trực tiếp đến pipeline input quality — nếu log dừng, RCA mất evidence, correlation mất temporal signal. Em expect ít nhất 1 alert cho `log_ingestion_lag > 30s` hoặc `disk_usage > 90%`.
- **Why pipeline missed (hypothesis):** Detector scope chỉ cover application-level metrics (latency, error_rate, availability) được expose qua service /metrics endpoint. Infrastructure components (log-collector, Prometheus, Kafka) KHÔNG có metrics trong detector scope. Đây là architectural gap — pipeline cần meta-monitoring layer riêng: 1 process ngoài pipeline monitor health của pipeline components. Nếu log-collector disk full + payment-svc fault xảy ra cùng lúc → pipeline detect payment fault nhưng RCA không có log evidence → RCA quality giảm mà pipeline không biết.

---

## 1 trade-off trong design pipeline mà em muốn rethink

**Trade-off hiện tại:** Pipeline ưu tiên **high precision** (low false-alarm) bằng cách set detection threshold cao (3σ trên sliding window 5 phút). Kết quả: precision = 1.00 (0 false alarm trong baseline) nhưng detection chậm (MTTD p50 = 28s, p95 = 53s) và miss subtle fault (#7).

**Rethink:** Sau chaos run, em nhận ra cost asymmetry rõ ràng:
- **Cost của 1 false alarm:** Engineer nhìn dashboard 2 phút → dismiss → 2 phút mất
- **Cost của 1 missed fault:** Outage kéo dài → MTTR tăng → user impact → revenue loss

Ratio cost khoảng 1:100. Vậy chấp nhận thêm 2-3 false alarm/ngày để giảm threshold (2σ thay vì 3σ) → tăng recall từ 90% lên ~95% và giảm MTTD p50 từ 28s xuống ~15s. Cụ thể: experiment #9 (DNS slow) detect chậm nhất (53s) vì latency delta +2s nằm gần biên 3σ — với 2σ sẽ detect trong ~25s.

Đồng thời, thêm alert tier: tier-1 (3σ → high confidence → page on-call) vs tier-2 (2σ → medium confidence → dashboard notification only). Giữ precision cao cho tier-1, tăng recall cho tier-2.

---

## Scoreboard summary

```
- detected:    9/10
- rca_correct: 6/9
- mttd_p50:    28s
- false_alarms: 0
- verdict:     PASS ✅  (detected ≥ 7 ✓, RCA ≥ 5/9 ✓, FA ≤ 1 ✓)
```
