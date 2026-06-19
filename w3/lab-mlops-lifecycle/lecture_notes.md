# Giáo Trình: MLOps Lifecycle & Automation

> [!NOTE]
> Tài liệu học tập và thực hành quy trình MLOps khép kín: Giám sát drift, tự động tái huấn luyện và cơ chế rollback bảo vệ hệ thống.

---

# PHẦN I: LÝ THUYẾT VẬN HÀNH

## 1. So Sánh Mô Hình Vận Hành Mô Hình (Model Operations)

| Tiêu chí | 🕰️ Vận hành Tĩnh (Static MLOps) | 🌀 Chu kỳ Tự động (Dynamic MLOps) |
| :--- | :--- | :--- |
| **Giám sát hiệu năng** | Kiểm tra thủ công định kỳ / Ad-hoc | Tự động quét và cảnh báo Drift (Combined Mode) |
| **Tái huấn luyện** | ML Engineer train thủ công khi có sự cố | Kích hoạt tự động khi drift vượt ngưỡng |
| **Phục vụ & Deploy** | Thay thế file model trực tiếp, restart API | Blue-Green swap qua MLflow registry alias, reload API |
| **Rollback sự cố** | Khó khăn, mất thời gian phục hồi container | Tự động Rollback tức thì (< 5s) khi model mới suy giảm |
| **Rủi ro vận hành** | Cao (dễ mất mát doanh thu khi model decay) | Thấp (chốt chặn an toàn bảo vệ SLA) |

---

## 2. Chu Trình MLOps Lifecycle (MAPE-ML)

```mermaid
graph TD
    classDef default fill:#1f2937,stroke:#4b5563,stroke-width:1px,color:#f3f4f6,font-family:sans-serif;
    classDef success fill:#10b981,stroke:#059669,stroke-width:2px,color:#ffffff,font-weight:bold;
    classDef danger fill:#ef4444,stroke:#dc2626,stroke-width:2px,color:#ffffff,font-weight:bold;
    
    A["🔍 1. MONITOR<br/>Quét Data/Perf Drift"]:::default -->|Drift > Threshold| B["🧠 2. DECIDE & RETRAIN<br/>Huấn luyện mô hình v2"]:::default
    B -->|Sliding Window| C["🧪 3. SANITY CHECK<br/>Kiểm thử holdout"]:::default
    C -->|Pass| D["⚡ 4. DEPLOY STAGING<br/>Gán alias @staging"]:::default
    D -->|Kỹ sư duyệt| E["📈 5. SWAP PRODUCTION<br/>Promote @production & Reload"]:::default
    E -->|24 chu kỳ| F["🚨 POST-DEPLOY MONITOR<br/>Kiểm tra độ chính xác v2"]:::default
    
    F -->|Đạt chuẩn| G["🎉 STABLE<br/>Mô hình v2 ổn định"]:::success
    F -->|Precision < 0.65| H["🔄 AUTO-ROLLBACK<br/>Khôi phục v1 & Archive v2"]:::danger
```

### Chi tiết các bước vận hành trong chu trình:

1. **🔍 1. MONITOR (Quét Drift Kết Hợp)**
   * **Mô tả**: Định kỳ thu thập dữ liệu giao dịch thực tế (`current_df`) để đối chiếu với tập dữ liệu huấn luyện chuẩn ban đầu (`reference_df`).
   * **Kỹ thuật**: `drift_detector.py` thực hiện hai phép đo song song:
     * *Data Drift*: Dùng khoảng cách Wasserstein (Wasserstein Distance) của Evidently AI để kiểm tra sự lệch phân phối của 3 đặc trưng đầu vào (`latency_p99`, `error_rate`, `rps`).
     * *Performance Drift*: Đánh giá trực tiếp hiệu năng của mô hình hiện tại (v1) trên tập dữ liệu mới có nhãn.
   * **Ngưỡng vi phạm**: Nếu `drift_score > 0.15` (lệch phân phối) hoặc `precision < 0.70` (suy giảm hiệu năng), cảnh báo được kích hoạt để chuyển sang bước tiếp theo.

2. **🧠 2. DECIDE & RETRAIN (Tái huấn luyện mô hình v2)**
   * **Mô tả**: Tự động gom dữ liệu để xây dựng lại mô hình phù hợp với thực tế vận hành mới.
   * **Kỹ thuật**: Sử dụng chiến lược *Sliding Window* bằng cách gộp dữ liệu lịch sử (`baseline.csv` - 4320 dòng) và dữ liệu lệch mới (`drifted.csv` - 1008 dòng) thành tập huấn luyện mới 5328 dòng.
   * **Tránh lỗi chuẩn hóa**: Đóng gói `StandardScaler` và `IsolationForest` vào trong một Scikit-Learn `Pipeline` để đảm bảo đồng bộ hóa tiền xử lý. Lưu vết toàn bộ tham số, metrics, artifact mô hình và scaler lên MLflow Tracking Server.

3. **🧪 3. SANITY CHECK (Kiểm thử Holdout)**
   * **Mô tả**: Chạy kiểm thử độc lập trước khi đẩy mô hình lên registry nhằm ngăn ngừa hiện tượng thoái hóa hiệu năng (model regression).
   * **Kỹ thuật**: Đánh giá pipeline v2 trực tiếp trên tập dữ liệu kiểm chứng độc lập `data/holdout.csv` (lưu giữ các pattern cũ).
   * **Điều kiện vượt qua**: Độ chính xác (Precision) của v2 trên tập holdout bắt buộc phải lớn hơn hoặc bằng v1.

4. **⚡ 4. DEPLOY STAGING (Đăng ký mô hình thử nghiệm)**
   * **Mô tả**: Đăng ký phiên bản mới vào MLflow Model Registry.
   * **Kỹ thuật**: Gán alias `@staging` cho phiên bản v2 vừa tạo. Việc này giúp tách biệt phiên bản thử nghiệm với phiên bản phục vụ khách hàng thực tế (`@production`), cho phép kiểm tra cô lập mô hình mới mà không gây ảnh hưởng đến hệ thống đang chạy.

5. **📈 5. SWAP PRODUCTION & RELOAD (Cắt chuyển không downtime)**
   * **Mô tả**: Đưa mô hình v2 vào hoạt động chính thức và cập nhật API server.
   * **Kỹ thuật**: ML Engineer thực hiện duyệt cổng thủ công thông qua console. Khi được duyệt:
     * MLflow Registry sẽ thực hiện đổi thẻ alias `@production` từ v1 sang v2 một cách nguyên tử (atomic).
     * Script gửi request `POST /reload` đến FastAPI serve API. API server ngay lập tức tải lại pipeline v2 từ registry vào RAM, chuyển đổi mô hình phục vụ thực tế trong thời gian thực với **0 downtime**.

6. **🔄 6. POST-DEPLOY MONITOR & AUTO-ROLLBACK (Cầu chì tự động)**
   * **Mô tả**: Giám sát hiệu năng của mô hình v2 sau khi được deploy lên production trong 24 chu kỳ hoạt động.
   * **Kỹ thuật**: Chạy đánh giá độ chính xác của v2 trên tập dữ liệu kiểm thử thực tế `data/post_deploy_eval.csv`.
   * **Cơ chế Rollback**: Nếu phát hiện lỗi nghiêm trọng (mô phỏng bằng lỗi tiền xử lý/bypass scaler làm precision tụt xuống dưới `0.65` tại Cycle 01):
     * Cầu chì tự động kích hoạt: đổi thẻ alias của v2 thành `@archived`, khôi phục alias `@production` về v1.
     * Gọi lệnh `/reload` để API server lập tức chuyển về phục vụ bằng v1 ổn định.
     * Ghi nhận sự kiện `auto_rollback_v2_to_v1` vào audit log `outputs/audit_log.jsonl` để báo cáo on-call.

---

## 3. Chốt Chặn An Toàn (Safety Gates)

> [!IMPORTANT]
> **Nguyên tắc**: Tự động hóa không được phép gây ra hỗn loạn (chaos). Chu trình MLOps phải tuân thủ 4 chốt chặn an toàn sau:

### 📊 1. Ngưỡng Drift Khoa Học (Drift Threshold Noise Floor)
* **Mục tiêu**: Loại bỏ cảnh báo giả (false alarm) do nhiễu dữ liệu tự nhiên hoặc biến động theo mùa.
* **Cơ chế**: Đo lường drift score trên chính dữ liệu bình thường (`baseline.csv`) chia 70/30 để tìm mức nhiễu nền (**noise floor = 0.04**). Thiết lập threshold = **0.15** (gấp 3.75 lần noise floor) giúp đảm bảo độ nhạy và độ chính xác của bộ cảnh báo.

### 🛡️ 2. Chọn Lựa Dữ Liệu Tái Huấn Luyện (Sliding Window Strategy)
* **Mục tiêu**: Ngăn chặn mô hình bị thiên lệch (overfitting) vào phân phối mới mà quên đi các đặc trưng lịch sử của hệ thống.
* **Cơ chế**: Concat dữ liệu cũ (`baseline.csv`) và dữ liệu mới (`drifted.csv`) để tạo sliding window huấn luyện. Nếu chỉ train trên cửa sổ drift (7 ngày), độ chính xác trên tập holdout lịch sử sẽ giảm mạnh (~18%).

### 📢 3. Cổng Duyệt Phê Duyệt Thủ Công (Approval Gate)
* **Mục tiêu**: Đảm bảo quyền kiểm soát tối cao của con người trước khi đưa mô hình mới ra thị trường.
* **Cơ chế**: Model v2 được đăng ký ở trạng thái `staging` và chỉ được promote lên `production` sau khi ML Engineer phê duyệt thủ công `[y/N]` trên console.

### 🚨 4. Tự Động Rollback Tức Thì (Post-Deploy Auto-Rollback)
* **Mục tiêu**: Bảo vệ SLA hệ thống khi mô hình mới phát sinh lỗi nghiêm trọng sau khi triển khai (ví dụ: lỗi trích xuất dữ liệu, lệch phân phối bất ngờ).
* **Cơ chế**: Đo lường precision của mô hình liên tục trong 24 chu kỳ đầu. Nếu rơi xuống dưới **0.65**, hệ thống tự động swap ngược alias registry về v1, reload API server và chuyển v2 sang trạng thái `@archived`.

---

## 4. Kỹ Thuật Nâng Cao

> [!WARNING]
> MLOps thực chiến yêu cầu giải quyết triệt để vấn đề đồng bộ hóa tiền xử lý (pre-processing synchronization) và bảo vệ trước hiện tượng mù đặc trưng (drift misclassification):

* **Đóng gói Pipeline (StandardScaler + IsolationForest)**: Lưu trữ mô hình thô và scaler riêng biệt là một phản mẫu (anti-pattern) phổ biến dẫn đến lỗi lệch pha chuẩn hóa tại API server. Giải pháp là đóng gói cả scaler và mô hình vào chung một `sklearn.pipeline.Pipeline` trước khi serialize lên MLflow.
* **Giám sát Kết Hợp (Combined Drift Mode)**: 
  * *Data Drift* ($P(X)$ thay đổi) được phát hiện nhanh qua các kiểm định thống kê của Evidently (Wasserstein distance).
  * *Concept Drift* ($P(Y|X)$ thay đổi) chỉ có thể phát hiện qua sự sụt giảm hiệu năng (precision/recall) trên dữ liệu thực tế có nhãn.
  * Việc chạy `--check-mode combined` giúp chốt chặn cả hai hiện tượng này, ngăn chặn "bẫy phân loại sai" khi dữ liệu đầu vào có vẻ bình thường nhưng nhãn thực tế đã bị dịch chuyển.

---
---

# PHẦN II: THỰC HÀNH LAB "MLOPS LIFECYCLE"

## 1. Mô Tả Lab
Học viên lập trình giải pháp trong thư mục **`hai-khoa/`** bao gồm:
- Huấn luyện pipeline chuẩn hóa và phát hiện bất thường ([pipeline.py](file:///C:/Users/ASUS/OneDrive/Obsidian%20Vault/XBrain-Phase2/W3%20-%20Reliability%20Engineering%20&%20Postmortem/D4/lab-mlops-lifecycle/hai-khoa/pipeline.py)).
- API Gateway phục vụ mô hình FastAPI ([serve.py](file:///C:/Users/ASUS/OneDrive/Obsidian%20Vault/XBrain-Phase2/W3%20-%20Reliability%20Engineering%20&%20Postmortem/D4/lab-mlops-lifecycle/hai-khoa/serve.py)).
- Bộ giám sát sai lệch dữ liệu ([drift_detector.py](file:///C:/Users/ASUS/OneDrive/Obsidian%20Vault/XBrain-Phase2/W3%20-%20Reliability%20Engineering%20&%20Postmortem/D4/lab-mlops-lifecycle/hai-khoa/drift_detector.py)).
- Bộ điều phối tái huấn luyện và rollback ([retrain.py](file:///C:/Users/ASUS/OneDrive/Obsidian%20Vault/XBrain-Phase2/W3%20-%20Reliability%20Engineering%20&%20Postmortem/D4/lab-mlops-lifecycle/hai-khoa/retrain.py)).

---

## 2. 3 Kịch Bản Stress Test & Nghiệm Thu

| Stress Test | 🎯 Mô tả kịch bản | 📥 Đầu vào kích hoạt | 📤 Đầu ra kỳ vọng |
| :--- | :--- | :--- | :--- |
| **1. Drift Misclassification** | Kiểm tra drift kết hợp để không bỏ sót concept drift. | `--check-mode combined` trên `drifted.csv` | In cả `Drift score` (1.0000) và `Perf precision` (0.3164). Flag degraded = True. |
| **2. Sliding Window Selection** | Kiểm tra độ chính xác của v2 trên tập holdout để chống overfit. | `--holdout data/holdout.csv` trong `retrain.py` | In dòng `Holdout validation — v2 precision: X.XXXX`. Precision v2 phải $\ge$ v1. |
| **3. Post-Deploy Rollback** | Giám sát v2 sau promote. Phát hiện sự cố và rollback về v1. | `--post-deploy-eval data/post_deploy_eval.csv` | Lỗi ở Cycle 01/24 (precision = 0.40) $\rightarrow$ in dòng `Rollback complete. v1 restored...`, cập nhật audit log. |

---

## 3. Lệnh Chạy Terminal

### Terminal 1: Khởi động Stack Docker & API Server
```bash
# 1) Khởi động MLflow, Postgres, Prometheus, Grafana
docker compose -f data-pack/configs/docker-compose.yml up -d

# 2) Tạo môi trường Python và cài đặt thư viện
uv venv
uv pip install --link-mode=copy 'mlflow==2.13.2' 'evidently==0.4.40' 'setuptools<70' scikit-learn pandas numpy fastapi uvicorn prometheus_client requests

# 3) Huấn luyện và đăng ký phiên bản v1
$env:MLFLOW_TRACKING_URI="http://localhost:5000"
uv run python hai-khoa/pipeline.py --data data-pack/data/baseline.csv

# 4) Khởi chạy FastAPI API Server phục vụ mô hình
uv run python hai-khoa/serve.py
```

### Terminal 2: Chạy kiểm thử API Server
```powershell
# Gửi request dự đoán thử
Invoke-RestMethod -Method Post -Uri http://localhost:8000/predict -ContentType "application/json" -Body '{"features": [[120.0, 0.8, 450.0]]}'
```

### Terminal 3: Chạy Retrain Orchestrator (Kích hoạt Tái huấn luyện & Rollback)
```bash
# Khởi chạy quy trình điều phối và rollback tự động
$env:MLFLOW_TRACKING_URI="http://localhost:5000"
uv run python hai-khoa/retrain.py `
  --reference data-pack/data/baseline.csv `
  --current data-pack/data/drifted.csv `
  --holdout data-pack/data/holdout.csv `
  --post-deploy-eval data-pack/data/post_deploy_eval.csv `
  --serve-url http://localhost:8000 `
  --auto-approve
```

### 4. Kết quả ghi nhận tại Console khi rollback kích hoạt:
Khi `retrain.py` kích hoạt Stress 3, tại màn hình Console sẽ xuất hiện luồng log tự động rollback sau:
```text
[retrain] Drift score    : 1.0000
[retrain] Drift detected : True
[retrain] Drift confirmed. Building sliding-window training set (baseline + drift)...
[retrain] New model anomaly rate: 0.0300 on 5328 rows
[retrain] Registered anomaly-detector v8 -> alias 'staging'
[retrain] Auto-approve mode - skipping human gate.
[retrain] Promoted v8 -> alias 'production'
[retrain] serve.py reloaded -> now serving v8
[post_deploy_monitor] Starting 24-cycle post-deploy evaluation of v8...
[post_deploy_monitor] Cycle 01/24 — precision: 0.4000  recall: 1.0000
[post_deploy_monitor] Precision 0.4000 < threshold 0.65 — triggering AUTO-ROLLBACK.
[retrain] serve.py reloaded -> now serving v7
[post_deploy_monitor] Rollback complete. v7 restored to @production. v8 -> @archived.
```
Lúc này, file [audit_log.jsonl](file:///C:/Users/ASUS/OneDrive/Obsidian%20Vault/XBrain-Phase2/W3%20-%20Reliability%20Engineering%20&%20Postmortem/D4/lab-mlops-lifecycle/outputs/audit_log.jsonl) sẽ ghi nhận sự kiện `auto_rollback_v2_to_v1` để phục vụ audit.
