# W3-D1 Design Document — SLO, Error Budget, Burn-Rate Alerting

## 1. SLI choice cho frontend
Chúng ta lựa chọn chỉ số SLI kết hợp cho frontend: `count(dom_ready_ms < 3000 AND js_error == false AND network_error == false) / count(all)`. 
- **Lý do loại bỏ Page Load Time đơn lẻ**: Page Load Time đo lường toàn bộ thời gian tải trang bao gồm cả các tài nguyên bên thứ ba (quảng cáo, tracker, chatbot). Các tài nguyên này có thể tải rất chậm nhưng không làm ảnh hưởng đến trải nghiệm tương tác cốt lõi của người dùng.
- **Lý do loại bỏ JS Error Rate / Network Error Rate đơn lẻ**: Mỗi chỉ số này chỉ phản ánh một phần nhỏ lỗi kỹ thuật. JS Error Rate bỏ qua tình trạng CDN nghẽn mạng làm chậm trang; Network Error Rate bỏ qua lỗi logic client-side render; trong khi đó người dùng cần giao diện phản hồi nhanh và chạy được tính năng.
- **Tại sao chọn DOM Ready < 3000ms**: DOM Ready phản ánh thời điểm trình duyệt dựng xong khung HTML/JS chính để người dùng bắt đầu tương tác. Kết hợp với việc kiểm tra không có lỗi JS và Network giúp đảm bảo trang web tải nhanh và hoạt động không lỗi.

## 2. SLO target cho api
Chúng ta chọn SLO target cho API là **99.9%** (tương đương với ngân sách downtime 43 phút/tháng).
- **Phân tích chi phí (infra & ops)**: Theo baseline hiện tại từ `baseline.json`, tỷ lệ fail bình thường (bao gồm cả sự cố) là `0.35%` (success rate `97.63%` bao gồm 2% lỗi 4xx bị loại trừ). Tỷ lệ lỗi baseline thuần túy khi không có sự cố là `0.15%` (99.85% availability).
- **Tại sao không chọn 99.99%**: Để đạt 99.99% (chỉ cho phép 4.3 phút downtime/tháng), hệ thống bắt buộc phải có kiến trúc Multi-AZ tự động failover trong vài giây, active-active database replication, và quy trình deploy không downtime hoàn toàn (Blue-Green/Canary). Chi phí vận hành infra và nhân sự SRE sẽ tăng gấp 3-10 lần, vượt quá yêu cầu của một trang e-commerce quy mô trung bình.
- **Tại sao không chọn 99%**: SLO 99% cho phép tới 7 giờ 18 phút downtime/tháng. Mức này quá lỏng lẻo, khiến đội ngũ vận hành lơ là trước các sự cố kéo dài nhiều giờ, gây mất mát doanh thu lớn và làm giảm uy tín nghiêm trọng đối với khách hàng. Do đó, 99.9% là điểm cân bằng tối ưu giữa chi phí infra và trải nghiệm khách hàng.

## 3. Latency threshold p99
Chúng ta thiết lập latency threshold cho API là **500 ms** trong `slo_spec.yaml`.
- **Phân tích phân phối Latency (từ dữ liệu thực tế access_log.jsonl)**:
  - **p50 (Median)**: 45 ms
  - **p90**: 86 ms
  - **p95**: 104 ms
  - **p99 (Real tail pain)**: 156 ms
  - **p99.9 (Extreme tail)**: 394 ms
- **Lý do chọn 500 ms**: Dưới điều kiện hoạt động bình thường, 99% các request có phản hồi nhanh hơn 156 ms, và thậm chí 99.9% request vẫn nhanh hơn 394 ms. Do đó, mốc 500 ms là hoàn toàn an toàn và nằm ngoài phạm vi biến động tự nhiên của hệ thống. Nếu latency p99 vượt quá 500 ms, đó chắc chắn là tín hiệu của sự cố nghẽn database hoặc quá tải tài nguyên hệ thống, giúp kích hoạt cảnh báo chính xác mà không gây ra nhiễu (false positive).

## 4. 4xx exclusion
Chúng ta loại trừ các mã lỗi 4xx (ngoại trừ 429) ra khỏi cách tính toán SLO error count.
- **Tại sao loại trừ**: Lỗi 4xx (400 Bad Request, 401 Unauthorized, 403 Forbidden, 404 Not Found) phản ánh lỗi từ phía client (nhập sai dữ liệu, sai token, hoặc do các công cụ quét bot/scraper tự động tạo traffic ảo). Hệ thống server vẫn hoạt động bình thường và trả về đúng response định nghĩa.
- **Dẫn chứng số liệu từ access_log.jsonl**: 
  - Tỷ lệ lỗi 4xx phân bổ đồng đều khoảng **2%** trên mọi endpoint chính:
    - `/api/orders`: 2.02%
    - `/api/cart`: 2.04%
    - `/api/user`: 1.98%
    - `/api/checkout`: 2.01%
    - `/api/products`: 2.02%
  - Tổng traffic có tới **2.01%** là mã lỗi 4xx (41,712 lỗi trên tổng số 2,073,780 request). Nếu gộp 4xx vào lỗi hệ thống, SLO thực tế thu được sẽ tụt xuống dưới 98% ngay lập tức kể cả khi hệ thống chạy hoàn hảo. Điều này gây cạn kiệt error budget liên tục và làm vô hiệu hóa SLO. Mã 429 vẫn giữ lại vì nó thể hiện hệ thống chủ động từ chối phục vụ người dùng do chính sách giới hạn tải.

## 5. MWMBR tuning
Chúng ta sử dụng bộ tham số mặc định từ Google SRE Workbook:
- **Tier 1 (Urgent page)**: Cửa sổ 1h/5m, burn rate $\ge 14.4$ (tiêu thụ 2% budget).
- **Tier 2 (Page)**: Cửa sổ 6h/30m, burn rate $\ge 6$ (tiêu thụ 5% budget).
- **Tier 3 (Ticket)**: Cửa sổ 3d/6h, burn rate $\ge 1$ (tiêu thụ 10% budget).

- **Hiệu quả đánh giá từ `validation_report.json`**:
  - **Giảm nhiễu (Noise reduction)**: Đạt **86.4%**. Static baseline (cảnh báo tĩnh lỗi > 0.5% trong 5 phút) phát ra tới 22 cảnh báo (chủ yếu là nhiễu do spike ngắn hạn), trong khi MWMBR chỉ phát ra đúng 3 cảnh báo thực tế diễn ra.
  - **Độ nhạy (False Negatives - FN)**: Bằng **0**, tức phát hiện đầy đủ toàn bộ các sự cố thật của tầng API.
  - **Thời gian phát hiện chậm trễ (MTTD delta)**: Chỉ **60 giây**. Việc áp dụng thêm short window (5m/30m) giúp cảnh báo kích hoạt nhanh và tự động tắt (recover) chỉ trong 5 phút sau khi hết sự cố mà không bị treo hàng giờ như single long-window. Kết quả này chứng minh cấu hình mặc định là tối ưu và không cần thay đổi thêm.
