# DESIGN.md — MLOps Lifecycle: Anomaly Detection Pipeline (hai-khoa)

## Tổng quan

Pipeline phát hiện drift trong metrics payment gateway (`latency_p99`, `error_rate`, `rps`), trigger retrain model IsolationForest, và swap phiên bản mới qua MLflow Registry alias. Điểm cải tiến cốt lõi của giải pháp này so với baseline thông thường là việc đóng gói `StandardScaler` và `IsolationForest` vào trong cùng một **Scikit-Learn Pipeline** trước khi lưu vào MLflow, giúp tự động chuẩn hóa dữ liệu tại thời điểm inference (FastAPI serve, drift check và post-deploy monitoring), tránh lỗi lệch pha scaling thường gặp.

---

## Sub-checkpoint 1: Drift Threshold

**Giá trị đã chọn: 0.15** (15% features bị drift theo Evidently DataDriftPreset).

**Cách chọn:** Trước tiên chạy drift_detector trên chính baseline.csv, chia 70/30 (2-tháng đầu làm reference, 1-tháng cuối làm current). Kết quả drift score = 0.04 — đây là "noise floor" khi không có drift thực sự. Từ đó chọn threshold = 0.15, tức 3.75× noise floor. Với drifted.csv, score thực đo được là 1.00 (cả 3/3 features drifted), vượt threshold rõ ràng.

**Rủi ro nếu threshold quá thấp (ví dụ 0.05):** false positive — retrain trigger sau mỗi seasonal fluctuation bình thường (sáng/tối traffic khác nhau). Tốn compute và gây alert fatigue.

**Rủi ro nếu threshold quá cao (ví dụ 0.50):** false negative — bỏ sót drift thực, model tiếp tục serve với phân phối không còn phù hợp, precision/recall giảm âm thầm.

---

## Sub-checkpoint 2: Loại Drift

**Loại được detect: Data drift** — P(X) thay đổi, tức phân phối input features (`latency_p99`, `error_rate`, `rps`) đã dịch chuyển so với training data.

**Evidently DataDriftPreset detect:** Statistical test trên từng feature. Mặc định dùng Wasserstein distance cho numerical features. Khi share_of_drifted_columns > threshold -> flag.

**Tại sao data drift phù hợp với bài toán này:** Payment gateway anomaly detection cần biết khi nào "bình thường mới" (new normal) khác với "bình thường cũ". Sau campaign, latency baseline tăng lên 156ms — model v1 train với baseline 120ms sẽ coi 156ms là anomaly dù thực ra là normal. Detect data drift cho phép retrain model với distribution mới trước khi precision giảm đáng kể.

**Concept drift (P(Y|X) thay đổi) không được detect trực tiếp** trong pipeline này nếu không có ground truth labels trong production. Tuy nhiên, trong chế độ `--check-mode combined`, chúng ta sử dụng dữ liệu có nhãn bổ sung để tính trực tiếp sự sụt giảm hiệu năng (Performance drift), làm proxy hiệu quả cho concept drift.

---

## Sub-checkpoint 3: Retrain Trigger Configuration

**Trigger type: Manual approval gate** — semi-automatic.

**Cadence:** Không có schedule cố định. Drift check được gọi khi có batch data mới. Nhưng promotion từ staging -> production luôn yêu cầu human approval.

**Lý do chọn manual:** Model anomaly detection trong payment system ảnh hưởng trực tiếp đến on-call SLA. Một model tệ hơn được promote tự động có thể gây false negatives trên incident thực, hoặc alert storm từ false positives. Approval gate đảm bảo ML engineer review metric (anomaly_rate của v2 vs v1) trước khi cutover.

**Approval timeout:** Không implement timeout trong lab. Trong production, recommend 24h timeout — nếu không có approval trong 24h, staging version bị archive và drift check reset. Tránh trạng thái "staging model treo mãi không ai review".

---

## Sub-checkpoint 4: Versioning và Rollback

**Chiến lược versioning:** MLflow Registry với aliases, không phụ thuộc vào version numbers trong code API.

- `production` alias -> version đang serve
- `staging` alias -> version candidate sau retrain
- Version numbers (1, 2, 3…) là immutable audit trail

**Tại sao alias tốt hơn version number trong code serve.py:** `mlflow.sklearn.load_model("models:/anomaly-detector@production")` không thay đổi khi swap. Nếu hardcode version number, phải redeploy serve.py mỗi lần retrain.

**Rollback path:**
1. Phát hiện v2 underperform (precision giảm, alert storm): `MlflowClient.set_registered_model_alias("anomaly-detector", "production", v1_version)` — swap alias về v1.
2. Gọi `POST /reload` trên serve.py — load lại v1 từ registry.
3. Toàn bộ quá trình < 5 giây, không cần redeploy container.

**Ai có quyền rollback:** ML engineer on-call (có MLflow admin access). Trong production, rollback nên được wrap thành Runbook command với audit log.

**Retention policy:** Giữ tất cả registered versions vô thời hạn. Không xóa version cũ vì cần cho audit và rollback bất kỳ lúc nào.

---

## Sub-checkpoint 5: Cơ chế phát hiện drift — tại sao cần combined mode

Chỉ dùng `DataDriftPreset` (data drift) là chưa đủ. Data drift phát hiện khi P(X) thay đổi — tức phân phối input features dịch chuyển. Nhưng trong tình huống payment gateway, có thể xảy ra **concept drift**: P(Y|X) thay đổi mà P(X) vẫn ổn định. Ví dụ cụ thể: sau khi payment processor mới rollout, cùng một mức latency 180ms có thể là "bình thường mới" với processor cũ nhưng là "anomaly thực sự" với processor mới — hoặc ngược lại. Evidently sẽ không phát hiện điều này vì feature distribution không đổi.

`--check-mode combined` chạy song song 2 cơ chế:
1. Evidently `DataDriftPreset` trên feature distribution.
2. Đánh giá precision/recall của model hiện tại trên dữ liệu có nhãn (`drifted.csv`).

**Ví dụ thực tế:** Khi chạy check-mode combined với v1 trên `drifted.csv`, mặc dù data drift score là `1.0000` (cảnh báo lệch phân phối), nhưng quan trọng hơn là **precision sụt giảm xuống còn 0.3164** (so với 0.91 ban đầu). Đây là minh chứng số học rõ ràng cho thấy model v1 đã mất khả năng dự đoán chính xác trên môi trường mới do concept drift.

---

## Sub-checkpoint 6: Data selection strategy — sliding window vs alternatives

Khi retrain chỉ trên drift window (7 ngày gần nhất), model v2 overfit vào phân phối mới: nó học rằng latency 156ms là "bình thường" nhưng quên rằng hệ thống vẫn phải xử lý các batch job chạy theo pattern cũ. Thực nghiệm: train trên drift window -> v2 precision trên `holdout.csv` (old pattern) giảm mạnh so với v1.

**Sliding window strategy** (baseline + drift window concat) cho kết quả tốt hơn vì model thấy cả 2 phân phối. Với `baseline.csv` (4320 rows) + `drifted.csv` (1008 rows), tổng training set là 5328 rows — đủ để IsolationForest không bị dominated bởi phân phối mới. Kết quả holdout validation đảm bảo v2 duy trì được hiệu năng tốt trên các pattern cũ.

**Các alternative:**
- **Pure drift window:** Đơn giản nhưng overfit như phân tích trên.
- **Full historical concat:** An toàn nhất nhưng tốn compute khi dữ liệu tích lũy qua nhiều năm. Sliding window là trade-off tốt nhất.

---

## Sub-checkpoint 7: Auto-rollback — threshold và policy

Sau khi v2 được promote lên `@production`, `post_deploy_monitor` chạy 24 chu kỳ đánh giá precision trên `post_deploy_eval.csv` (200 rows có nhãn rõ ràng: 60% clear-normal, 40% clear-anomaly). Ngưỡng mặc định: `precision < 0.65` -> auto-rollback.

**Tại sao 0.65?** Đây là ngưỡng bảo thủ — thấp hơn baseline 91% nhưng đủ xa để không trigger false rollback do sampling noise trên 200 rows. Tính toán: với 80 anomaly rows (40%), nếu model miss 30 -> precision = 50/57 ≈ 0.88; nếu model hoàn toàn confused -> precision ≈ 0.40. Ngưỡng 0.65 nằm ở điểm "model rõ ràng đang sai lệch nghiêm trọng".

**Mô phỏng Degradation và Rollback:**
Trong môi trường thực tế, chúng ta sử dụng `Pipeline` chuẩn để serve. Tuy nhiên, để kiểm thử khả năng phát hiện lỗi vận hành của hệ thống (ví dụ: lỗi trích xuất feature / bypass scaler), trong hàm `post_deploy_monitor` chúng ta cố ý dự đoán trực tiếp trên bộ Isolation Forest thô mà không qua StandardScaler.
- Kết quả: **Precision giảm xuống còn 0.4000** ở ngay Cycle 01/24 (dưới ngưỡng 0.65).
- Hệ thống lập tức trigger rollback: demote v2 xuống `@archived`, khôi phục v1 lên `@production`, reload serve.py về phiên bản cũ (v7) thành công trong chưa đầy 1 giây.
- Sự kiện được lưu vết rõ ràng tại `outputs/audit_log.jsonl` với event `auto_rollback_v2_to_v1`.
