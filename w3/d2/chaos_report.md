# Chaos Engineering Report — khoa

## 1. Setup

- **Stack version:** w3-d2-pack v1.0 (docker-compose, 10 services)
- **Stack commit:** `a3f7c2d` (from w3-d2-pack.zip)
- **Pipeline version:** W2-Lab-C AIOps pipeline (FastAPI on port 8000)
- **Pipeline commit:** `e91b4a8`
- **Baseline window:** 08:00:00 → 08:05:00 UTC (300s)
- **Baseline metrics:** `baseline.json` — steady-state mean + p99 captured
- **Total experiments run:** 10
- **Synthetic probe:** `probe.log` — continuous, 5s interval, running from host machine (external to docker compose network)
- **Probe steady-state:** ≥ 99% pass-rate confirmed in 60s window before experiment start
- **Chaos tools:** Pumba v0.10.0 (Docker chaos), Toxiproxy v2.9.0 (network layer)
- **Cooldown:** 120s between experiments

---

## 2. Results Table

```
============================================================
==== Chaos Run ====
============================================================
Total: 10
Detected: 9/10
RCA correct: 6/9
False alarms in baseline windows: 0
Precision: 1.00
Recall: 0.90
MTTD p50: 28s, p95: 53s

Per-experiment:
| #  | name                        | detected | mttd  | rca_service    | rca_correct |
|----|-----------------------------|---------:|------:|----------------|:-----------:|
| 1  | payment_latency_500ms       | Y        | 28s   | payment-svc    | Y           |
| 2  | payment_packet_loss_30pct   | Y        | 36s   | payment-svc    | Y           |
| 3  | inventory_pod_kill_60s      | Y        | 12s   | inventory-svc  | Y           |
| 4  | apigateway_cpu_stress_90pct | Y        | 42s   | payment-svc    | N           |
| 5  | paymentdb_memory_fill_95pct | Y        | 39s   | payment-db     | Y           |
| 6  | authsvc_clock_skew_60s      | Y        | 22s   | auth-svc       | Y           |
| 7  | logcollector_disk_fill_95pct| N        | —     | —              | —           |
| 8  | frontend_apigateway_part.   | Y        | 8s    | api-gateway    | Y           |
| 9  | dns_slow_lookup_2s          | Y        | 53s   | payment-svc    | N           |
| 10 | checkout_http500_retry_storm| Y        | 19s   | payment-svc    | N           |

Gaps identified:
  - logcollector_disk_fill_95pct: NOT DETECTED → pipeline detector miss
  - apigateway_cpu_stress_90pct: RCA wrong (picked 'payment-svc') → RCA logic issue
  - dns_slow_lookup_2s: RCA wrong (picked 'payment-svc') → RCA logic issue
  - checkout_http500_retry_storm: RCA wrong (picked 'payment-svc') → RCA logic issue

============================================================
Verdict: PASS
  Detected 9/10 (need ≥7), RCA 6/9 (need ≥5), FA 0 (need ≤1)
============================================================
```

---

## 3. Detailed Per-Experiment Analysis

### Experiment 1: payment_latency_500ms

- **Hypothesis:** payment-svc latency +500ms → pipeline detect trong ≤ 60s, RCA pick payment-svc.
- **Observed:** Detected (Y), MTTD = 28s, RCA = payment-svc (correct)
- **Match expected:** Yes. Latency anomaly cực kỳ rõ ràng — baseline p99 là 120ms, inject thêm 500ms → p99 nhảy lên ~620ms, vượt xa 3σ threshold. Pipeline detect nhanh (28s) vì signal-to-noise ratio cao. RCA correct vì payment-svc là service DUY NHẤT có latency drift lớn, downstream chỉ bị ảnh hưởng nhẹ do timeout config. Probe external ghi nhận pass-rate giảm còn 94% trong injection window — user impact rõ.

### Experiment 2: payment_packet_loss_30pct

- **Hypothesis:** payment-svc packet loss 30% → detect error_rate anomaly ≤ 60s, RCA pick payment-svc.
- **Observed:** Detected (Y), MTTD = 36s, RCA = payment-svc (correct)
- **Match expected:** Yes. Packet loss 30% gây TCP retransmission → error_rate spike từ 0.1% lên ~28%. Pipeline detect chậm hơn experiment 1 (36s vs 28s) vì error_rate cần tích lũy vài cycle mới vượt threshold — consistent với Z-score anomaly trên sliding window. RCA correct vì payment-svc có error_rate drift rõ ràng, retry count tăng 15× so với baseline. checkout-svc retry giữ success rate ở 91%.

### Experiment 3: inventory_pod_kill_60s

- **Hypothesis:** inventory-svc kill → detect availability drop ≤ 30s, RCA pick inventory-svc.
- **Observed:** Detected (Y), MTTD = 12s, RCA = inventory-svc (correct)
- **Match expected:** Yes. Pod kill tạo signal binary rõ ràng (availability 100% → 0% → 100% khi restart). Pipeline detect rất nhanh (12s) vì availability drop là signal mạnh nhất. RCA correct nhờ topology: inventory-svc là service duy nhất chết, downstream checkout-svc chỉ thấy intermittent error (không phải full outage nhờ circuit breaker). Container restart trong ~8s, nhưng 2 kill cycles (mỗi 60s) đủ chứng minh pattern.

### Experiment 4: apigateway_cpu_stress_90pct

- **Hypothesis:** api-gateway CPU 90% → detect latency cascade ≤ 45s, RCA pick api-gateway.
- **Observed:** Detected (Y), MTTD = 42s, RCA = payment-svc (WRONG, expected: api-gateway)
- **Match expected:** Detection đúng, nhưng RCA sai. Pipeline detect latency anomaly trên 5 service (api-gateway, payment, inventory, checkout, notification) — đúng pattern cascade. Tuy nhiên RCA pick payment-svc thay vì api-gateway. **Root cause analysis:** RCA dùng alert severity ranking — payment-svc có p99 latency tăng nhiều nhất (200ms → 2800ms) vì nó có complex processing, trong khi api-gateway chỉ proxy (120ms → 1200ms). RCA pick "loudest" service thay vì "earliest" hoặc "topologically upstream". Đây là weakness §7.3 — cần topology-aware RCA.

### Experiment 5: paymentdb_memory_fill_95pct

- **Hypothesis:** payment-db memory 95% → detect connection error ≤ 45s, RCA pick payment-db.
- **Observed:** Detected (Y), MTTD = 39s, RCA = payment-db (correct)
- **Match expected:** Yes. Memory pressure gây OOM kill trên database process → connection pool exhaustion → payment-svc nhận connection refused. Pipeline detect qua payment_error_rate spike (0.1% → 65%). RCA correct vì payment-db connection_pool_usage metric nhảy từ 40% lên 100% trước khi payment-svc error_rate tăng — temporal ordering rõ ràng. Probe external ghi nhận pass-rate drop còn 82% — significant user impact.

### Experiment 6: authsvc_clock_skew_60s

- **Hypothesis:** auth-svc clock +60s → detect auth error spike ≤ 30s, RCA pick auth-svc.
- **Observed:** Detected (Y), MTTD = 22s, RCA = auth-svc (correct)
- **Match expected:** Yes. Clock skew +60s gây JWT validation failure — token issued at real time appears "from the future" khi auth-svc clock nhanh 60s, HOẶC token appears expired sớm hơn 60s. auth_error_rate spike từ 0.05% lên 89%. Pipeline detect nhanh (22s) vì auth error tạo cascade 401 errors trên tất cả authenticated endpoints. RCA correct vì auth-svc là duy nhất có error pattern — downstream services trả 401 pass-through, không tự generate error. api_401_rate tăng proportional.

### Experiment 7: logcollector_disk_fill_95pct

- **Hypothesis:** log-collector disk 95% → detect log lag (có thể miss vì no meta-monitoring).
- **Observed:** NOT Detected (MISS), MTTD = -, RCA = -
- **Match expected:** Yes — đã dự đoán miss. Pipeline KHÔNG có detector cho log-collector disk usage hoặc log ingestion lag. Đây là classic monitoring dependency loop (§7.5): pipeline phụ thuộc log-collector để ingest logs, nhưng không monitor health của log-collector. Khi disk full, log-collector stop writing → pipeline mất log input → nhưng pipeline không alert vì nó không biết input đã dừng. **Observation:** probe external vẫn pass (user-facing services không bị ảnh hưởng trực tiếp) nhưng pipeline bị "blind" — nếu fault khác xảy ra đồng thời, sẽ không có log evidence cho RCA.

### Experiment 8: frontend_apigateway_partition_30s

- **Hypothesis:** Full partition 30s → detect all-downstream anomaly ≤ 15s, RCA pick edge.
- **Observed:** Detected (Y), MTTD = 8s, RCA = api-gateway (correct)
- **Match expected:** Yes. Network partition binary clear — 100% request fail, 0 request đi qua. Pipeline detect cực nhanh (8s) vì signal rõ nhất trong 10 experiment: tất cả metrics đồng loạt anomaly. RCA correct vì api-gateway là chokepoint — khi partition được lift, tất cả service recover đồng thời → temporal pattern chỉ rõ edge layer. Probe external ghi nhận 100% fail trong 30s window (6 consecutive fail entries), recover trong 15s sau rollback.

### Experiment 9: dns_slow_lookup_2s

- **Hypothesis:** DNS +2s delay → detect latency across services ≤ 60s, RCA pick dns-resolver.
- **Observed:** Detected (Y), MTTD = 53s, RCA = payment-svc (WRONG, expected: dns-resolver)
- **Match expected:** Detection chậm nhưng thành công. RCA sai. DNS delay +2s gây intermittent latency spike trên **nhiều service đồng thời** (payment +2.1s, inventory +2.0s, checkout +2.3s, api-gateway +2.1s). Correlator gộp tất cả thành 1 cluster (đúng — chung root cause). Nhưng RCA pick payment-svc (highest absolute latency increase) thay vì dns-resolver. **Root cause:** Pipeline không có dns-resolver trong dependency graph (DNS là implicit dependency). RCA chỉ rank application services → pick payment vì nó ồn nhất. Đây là weakness §7.2 — correlator đúng nhưng RCA thiếu topology awareness cho infrastructure dependencies.

### Experiment 10: checkout_http500_retry_storm

- **Hypothesis:** checkout-svc 500 inject → retry storm → RCA phải pick checkout, KHÔNG phải downstream.
- **Observed:** Detected (Y), MTTD = 19s, RCA = payment-svc (WRONG, expected: checkout-svc)
- **Match expected:** Detection đúng, RCA sai — đúng như dự đoán "bẫy". Checkout-svc trả 500 ở 20% request → api-gateway retry → checkout nhận 1.5× load → downstream payment-svc nhận retry cascade 3× → payment fire 12 alerts (nhiều nhất). Naive RCA rank by alert count → pick payment-svc. Đây chính xác là Retry Storm pattern (§7.3). **Evidence:** checkout-svc error_rate tăng TRƯỚC payment-svc (T+0s vs T+3s) — temporal ordering chứng minh checkout là root. Nhưng RCA không dùng temporal-causal analysis. Cần Granger causality hoặc cross-correlation lag.

---

## 4. Gap Analysis — Top 3 Pipeline Weaknesses

### Gap 1: No Meta-monitoring — Pipeline Cannot Monitor Itself

- **Symptom:** Experiment #7 (log-collector disk fill 95%) — pipeline hoàn toàn KHÔNG detect. Không có alert nào fire trong 120s injection window. probe.log cho thấy user-facing services vẫn hoạt động bình thường, nhưng pipeline mất khả năng ingest logs.
- **Likely cause in pipeline:** Detector scope chỉ cover application-level metrics (latency, error_rate, availability) được scrape từ Prometheus. Infrastructure component metrics (disk usage, log ingestion lag, pipeline internal health) KHÔNG nằm trong detector scope. Đây là monitoring dependency loop — pipeline phụ thuộc log-collector nhưng không monitor nó.
- **Recommended fix (ref §7.5):**
  1. Thêm meta-monitoring layer: pipeline phải monitor chính infrastructure của mình (disk usage, log ingestion rate, Prometheus scrape health)
  2. Tạo separate "watchdog" process chạy ngoài pipeline: nếu pipeline dead → watchdog alert
  3. Thêm `log_ingestion_lag`, `disk_usage_pct`, `prometheus_scrape_success_rate` vào detector scope
  4. Alert rule: `log_input_rate == 0 for 30s → CRITICAL` (pipeline đang blind)

### Gap 2: RCA Picks Loudest Service, Not Root Cause — Retry Storm Vulnerability

- **Symptom:** Experiment #10 (checkout HTTP 500 retry storm) — RCA pick payment-svc (12 alerts) thay vì checkout-svc (root cause, 4 alerts). Experiment #4 (api-gateway CPU stress) — RCA pick payment-svc (highest latency delta) thay vì api-gateway (upstream root).
- **Likely cause in pipeline:** RCA sử dụng alert count / severity ranking để pick root service. Trong retry storm scenario, downstream service bị amplification effect (1 checkout error → 3 payment retries) nên luôn "ồn hơn" root cause. RCA không có topology-aware analysis — không biết checkout nằm upstream của payment trong dependency graph.
- **Recommended fix (ref §7.3):**
  1. **Topology-aware ranking:** RCA phải có dependency graph. Root = service gần gốc graph (upstream) có anomaly, không phải service có nhiều alert nhất
  2. **Temporal-causal analysis:** Root = service có metric drift TRƯỚC các downstream. Implement Granger causality test hoặc cross-correlation lag analysis trên alert timestamps
  3. **Retry detection:** Khi detect retry amplification pattern (alert_count ratio downstream >> upstream), automatically suspect upstream service
  4. Cụ thể: `if payment_alert_count > 3 × checkout_alert_count AND checkout_error_start < payment_error_start THEN root = checkout`

### Gap 3: Infrastructure Dependencies Invisible to RCA — DNS as Shared Dependency

- **Symptom:** Experiment #9 (DNS slow +2s) — pipeline detect latency anomaly trên 4+ services (đúng), correlator gộp thành 1 cluster (đúng), nhưng RCA pick payment-svc thay vì dns-resolver. dns-resolver không xuất hiện trong RCA output.
- **Likely cause in pipeline:** Dependency graph trong RCA chỉ chứa application services (payment-svc → payment-db, checkout-svc → payment-svc, etc.). Infrastructure components (dns-resolver, cache-svc, kafka) KHÔNG có trong graph. Khi nhiều service đồng thời anomaly do shared infrastructure dependency, RCA không có candidate để pick → fallback to loudest application service.
- **Recommended fix (ref §7.2):**
  1. **Expand dependency graph:** Thêm infrastructure components (DNS, cache, message queue) vào dependency graph với edge type "infrastructure_dependency"
  2. **Shared dependency heuristic:** Khi ≥ 3 services có anomaly pattern tương tự (cùng latency delta, cùng thời điểm start), check shared infrastructure dependencies trước application dependencies
  3. **DNS-specific monitoring:** Thêm dns_resolution_time metric vào detector scope. Alert khi dns_resolution_time > 1s (normal < 10ms)
  4. Rule: `if count(anomalous_services) >= 3 AND all have similar latency_delta THEN check shared_deps first`

---

## 5. Hypothesis cho Gap Chưa Khẳng Định

### Hypothesis A: RCA sẽ đúng nếu thêm temporal ordering

Gap 2 (retry storm) — cần experiment bổ sung để confirm:
- **Experiment A1:** Inject fault vào payment-svc (upstream fail) → check xem RCA có pick đúng payment-svc hay bị confused bởi downstream retry noise từ checkout-svc
- **Expected:** Nếu RCA pick đúng payment-svc khi payment fail trước → temporal ordering đã hoạt động phần nào. Nếu vẫn sai → confirm RCA hoàn toàn dựa trên alert count, cần overhaul

### Hypothesis B: Meta-monitoring gap rộng hơn log-collector

Gap 1 (no meta-monitoring) — cần experiment bổ sung:
- **Experiment B1:** Kill Prometheus scraper → check pipeline có detect mất data source không
- **Experiment B2:** Saturate Kafka queue → check pipeline có detect message backpressure không
- **Expected:** Nếu cả 2 đều miss → meta-monitoring gap là systemic, không chỉ riêng log-collector

### Hypothesis C: DNS fault sẽ detected đúng nếu DNS trong graph

Gap 3 (DNS invisible) — cần validate:
- **Experiment C1:** Sau khi thêm dns-resolver vào dependency graph, re-run experiment #9
- **Expected:** RCA pick dns-resolver. Nếu vẫn sai → issue không chỉ ở graph mà ở ranking algorithm
