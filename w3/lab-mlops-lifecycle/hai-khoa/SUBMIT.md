# SUBMIT.md — Reflection: MLOps Lifecycle Lab (hai-khoa)

## Câu 1: Drift threshold bạn chọn là bao nhiêu và tại sao? Bạn có validate threshold đó với dữ liệu thực tế không?

Threshold được chọn là **0.15** (tức 15% số lượng features bị lệch phân phối). Ngưỡng này được kiểm chứng (validate) thông qua việc phân tách dữ liệu `baseline.csv` theo tỷ lệ 70/30 (20 ngày đầu làm reference, 10 ngày cuối làm current) để giả lập hoạt động bình thường. Kết quả đo được mức drift nền (noise floor) chỉ là **0.04**. Do đó, chọn threshold 0.15 (gấp 3.75 lần noise floor) là an toàn để tránh cảnh báo giả do biến động tự nhiên (seasonal variation). Khi kiểm tra trên dữ liệu `drifted.csv`, drift score đo được là **1.0000** (cả 3 feature đều lệch phân phối vượt trội), hoàn toàn kích hoạt cảnh báo chính xác.

---

## Câu 2: Điều gì xảy ra nếu model v2 sau retrain lại tệ hơn v1 trong production? Pipeline của bạn xử lý trường hợp này như thế nào?

Hệ thống có hai cơ chế phòng thủ độc lập:
1. **Cổng duyệt thủ công (Approval Gate):** ML Engineer có thể so sánh anomaly rate của v2 và v1 trên holdout. Nếu v2 thể hiện chỉ số bất thường hoặc bị suy giảm hiệu năng nghiêm trọng (ví dụ: precision trên holdout bị tụt), engineer có quyền từ chối promote, giữ v2 ở trạng thái `staging`.
2. **Tự động Rollback (Auto-Rollback):** Nếu v2 đã được promote nhưng gặp lỗi trích xuất đặc trưng hoặc suy giảm hiệu năng thực tế (mô phỏng bằng cách chạy không qua StandardScaler trong giám sát), precision của v2 sẽ tụt xuống dưới **0.65** (thực tế đo được là **0.4000** ở Cycle 01). Hệ thống sẽ ngay lập tức tự động đổi alias `production` từ v8 về v7, reload API serve.py, và đưa v8 vào trạng thái `@archived`.

---

## Câu 3: Sự khác biệt giữa data drift và concept drift? Thư viện Evidently phát hiện loại nào trong lab này?

- **Data Drift:** Là sự thay đổi phân phối xác suất của dữ liệu đầu vào, tức $P(X)$ thay đổi trong khi mối quan hệ giữa đầu vào và nhãn $P(Y|X)$ giữ nguyên. Ví dụ: latency trung bình tăng từ 120ms lên 156ms do có thêm tích hợp bên thứ ba.
- **Concept Drift:** Là sự thay đổi trong mối quan hệ giữa dữ liệu đầu vào và nhãn mục tiêu, tức $P(Y|X)$ thay đổi. Ví dụ: cùng mức latency 200ms trước đây là bất thường (anomaly) nhưng sau khi nâng cấp hệ thống thì mức 200ms lại là bình thường (normal).

Thư viện **Evidently AI** với preset `DataDriftPreset` trong lab này được sử dụng để phát hiện **Data Drift** thông qua các kiểm định thống kê (Wasserstein distance cho các feature liên tục). Concept drift/Performance drift được phát hiện gián tiếp qua chế độ `combined` bằng cách tính toán trực tiếp precision/recall trên dữ liệu thực tế có nhãn.

---

## Câu 4: Tại sao blue-green swap quan trọng hơn việc ghi đè trực tiếp file model?

Việc ghi đè trực tiếp file model (`.pkl`) tạo ra nguy cơ:
- **Race condition:** Gây lỗi đọc file (corrupted read) hoặc crash ứng dụng serve.py nếu có request truy cập đúng lúc file đang bị ghi đè.
- **Downtime:** Ứng dụng phải restart để load file mới.
- **Khó Rollback:** Không giữ lại phiên bản cũ hoạt động ổn định, rollback thủ công rất chậm và rủi ro.

**Blue-Green swap** thông qua MLflow Model Registry alias giải quyết triệt để:
- Tránh race condition vì model mới được swap atomically thông qua alias tag trên registry.
- Không có downtime. API serve.py chỉ tải lại model mới khi nhận lệnh `/reload`, các in-flight request cũ vẫn hoàn thành an toàn trên phiên bản cũ.
- Rollback tức thời chỉ mất chưa đầy 1 giây bằng cách trỏ lại alias về phiên bản trước đó và gửi request `/reload`.

---

## Câu 5: Nếu bạn phải tự động hóa hoàn toàn cổng duyệt (không cần con người), bạn sẽ sử dụng metric nào và ngưỡng bao nhiêu?

Để tự động hóa hoàn toàn cổng duyệt một cách an toàn, tôi sẽ áp dụng đồng thời 3 điều kiện kiểm thử trên tập dữ liệu Holdout (`holdout.csv`):
1. **Hiệu năng mô hình v2 không bị suy giảm (Precision & Recall):** Precision của mô hình v2 trên tập holdout phải $\ge$ Precision của v1 trên cùng tập đó và $\ge 0.85$.
2. **Độ lệch Anomaly Rate (tỷ lệ dự đoán bất thường) nằm trong tầm kiểm soát:**
   $$\text{abs}(\text{anomaly\_rate}_{v2} - \text{anomaly\_rate}_{v1}) < 0.05$$
   để đảm bảo mô hình mới không dự đoán quá nhạy (alert storm) hoặc quá bảo thủ.
3. **Mô hình không bị thoái hóa (Degenerate):** Tỷ lệ bất thường dự đoán của v2 phải nằm trong khoảng hợp lý $[0.01, 0.10]$.

Nếu v2 thỏa mãn cả 3 điều kiện trên, hệ thống sẽ tự động promote lên `production`. Ngược lại, hệ thống sẽ từ chối tự động promote và tạo một ticket cảnh báo khẩn cấp (high-priority alert) để ML Engineer vào kiểm tra thủ công.
