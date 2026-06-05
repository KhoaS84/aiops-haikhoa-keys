# Detection Approach — DESIGN.md

## Approach tôi dùng
Phương pháp phát hiện bất thường động dựa trên **Dynamic Thresholds
sử dụng thuật toán Rolling Z-Score kết hợp Heuristics Log Matching**.

## Tại sao chọn approach này
Trong môi trường streaming thực tế, hệ thống không tĩnh mà có tính
chu kỳ (ví dụ lưu lượng RPS thay đổi theo thời gian). Việc đặt cấu hình
tĩnh (hardcoded thresholds) sẽ dễ dẫn đến tình trạng báo động giả
(False Alarms) khi tải hệ thống tự nhiên tăng cao. Z-Score giúp hệ
thống tự học ngưỡng dựa trên độ lệch chuẩn động, phù hợp để triển khai
trực tiếp trên dữ liệu stream mà không cần biết cấu hình phần cứng hay
hành vi tải trước đó.

## Cách hoạt động
1. **Giai đoạn học (Warm-up)**: Trong 30 tick đầu tiên (khi hệ thống
chắc chắn chạy bình thường), pipeline lưu trữ các chỉ số để tính toán
giá trị trung bình (μ) và độ lệch chuẩn (σ).
2. **Giai đoạn giám sát**:
    * Với mỗi payload, pipeline tính toán khoảng cách lệch chuẩn Z-
score của từng chỉ số.
    * Nếu chỉ số vượt ngưỡng 5σ (Z > 5.0), một sự cố bất thường được
xác định.
    * Để phân loại sự cố, pipeline phân tích chỉ số bị lệch kết hợp
quét từ khóa đặc trưng trong Logs nhằm phân loại chính xác thành
`memory_leak`, `traffic_spike`, hoặc `dependency_timeout`.

## Parameters tôi chọn
* **WARMUP_PERIOD = 30 ticks**: Đủ để ghi nhận chu kỳ ngắn ban đầu mà
không làm chậm trễ quá trình giám sát.
* **Ngưỡng Z-Score = 5.0**: Đảm bảo loại bỏ hoàn toàn các điểm nhiễu
ngẫu nhiên (chỉ kích hoạt khi biến động cực kỳ dữ dội), triệt tiêu
False Alarms.
* **Standard Deviation Floor (MIN_STD)**: Tránh lỗi chia cho 0 đối
với các metrics có biến động ban đầu bằng 0 (như tỷ lệ lỗi upstream).

## Cải thiện nếu có thêm thời gian
* Áp dụng thuật toán gom cụm log (Log Clustering như Drain) để tự
động phát hiện các log lỗi mới mà không cần hardcode từ khóa.
* Sử dụng cửa sổ trượt (Sliding Window) cập nhật liên tục baseline
thay vì chỉ tính 1 lần ở đầu.
──────
### Bước 4: Hướng dẫn chạy kiểm thử trên Github Workspace của bạn

1. Cài đặt môi trường:
uv venv
# Kích hoạt venv (trên Windows: .venv\Scripts\activate, trên
Linux/macOS: source .venv/bin/activate)
uv pip install -r requirements.txt

2. Khởi chạy HTTP Server (chạy trước):
python pipeline.py

3. Khởi chạy Stream Generator (chạy song song ở Terminal thứ hai):
python stream_generator.py --birthday <NGÀY-SINH-CỦA-BẠN> --target
http://localhost:8000/ingest