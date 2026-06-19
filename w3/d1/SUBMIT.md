# W3-D1 Submission — haikhoa

## 3 thứ em học được
1. **Cơ chế MWMBR giảm nhiễu cảnh báo**: Hiểu sâu sắc cách kết hợp Long Window (đảm bảo sự cố đủ nghiêm trọng để tiêu tốn ngân sách lỗi) và Short Window (kiểm tra sự cố vẫn đang xảy ra) giúp giảm số lần báo động giả cực kỳ ấn tượng (giảm 86.4% nhiễu so với cảnh báo tĩnh).
2. **Vai trò quan trọng của 4xx Exclusion**: Nhận ra tầm quan trọng của việc loại bỏ lỗi client-side (như 4xx) ra khỏi SLO để tránh cạn kiệt ngân sách lỗi do bot hoặc lỗi từ phía người dùng, đồng thời giữ lại mã 429 vì nó phản ánh khả năng chịu tải của hệ thống.
3. **Quy trình thiết kế SLO dựa trên Baseline thực tế**: Biết cách phân tích dữ liệu lịch sử (baseline) để đưa ra mục tiêu SLO thực tế và khả thi, thay vì đặt ra các mục tiêu "nhiều số 9" một cách cảm tính dẫn đến chi phí hạ tầng và vận hành tăng vọt vô lý.

## 1 thứ vẫn chưa rõ
- Làm thế nào để điều phối cảnh báo SLO hiệu quả trong kiến trúc microservices/topology phức tạp (ví dụ: API gọi DB, DB bị nghẽn làm API chậm kéo theo Frontend chậm. Lúc này làm sao để chỉ page đúng đội quản lý DB thay vì cả 3 đội quản lý 3 service cùng nhận cảnh báo gây nhiễu loạn).

## 1 trade-off trong SLO decision của em mà em không chắc
- Việc loại bỏ 100% các lỗi 4xx (trừ 429) khỏi chỉ số availability của API. Trade-off là nếu chúng ta deploy một phiên bản client mới bị lỗi gửi sai định dạng request hàng loạt (gây ra lỗi 400 Bad Request), hệ thống SLO sẽ không ghi nhận đây là sự cố mặc dù người dùng thực sự đang gặp lỗi nghiêm trọng và không dùng được ứng dụng.

## Validation report
- noise_reduction_pct: 86.4%
- mttd_delta_s: 60s
- false_negative: 0
- verdict: pass
