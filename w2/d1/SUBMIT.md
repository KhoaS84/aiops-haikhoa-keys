Alert Correclation Submission
Mình triển khai pipeline gồm ba lớp: Dedup -> Session Window -> Topology-aware Grouping

Mình chọn gap_sec = 120 giây vì đây là mức cân bằng giữa việc gom các alert và tránh gộp các incident không liên quan. Nếu gap quá nhỏ là 30 giây, một incident kéo dài có thể bị tách thành nhiều cluster. Nếu gap quá lớn là 600 giây thì các incident độc lập có thể bị gộp nhầm.

Mình chọn max_hop = 1 giúp giữ cluster nhỏ gọn và dễ giải thích hơn. Nếu tăng max_hop lên 2 hoặc cao hơn thì nhiều service kết nối qua hub service có thể bị gom vào cùng một cluster, dẫn tới over-correlation.

Không có alert nào hoàn toàn bị bỏ sót. Tuy nhiên alert của recommender-svc (a-0013) được tách thành một cluster riêng vì không có quan hệ topology trực tiếp với payment incident và metric thuộc nhóm resourcs, không phù hợp với chuỗi database-latency-error của incident chính.

Nếu số lượng tăng từ 20 lên 10000, điểm nghẽn cổ chai lớn nhất nằm ở bước topology grouping. Hiện tịa thuật toán phải so sánh nhiều cặp alert trong cùng session nên độ phức tạp gần O(n^2). Có thể tối ưu bằng cách index theo service hoặc metric family hoặc connected component trước khi thực hiện clustering.

EOD Checkpoint
1. Fingerprint sử dụng service|metric|severity. Nếu thêm timestamp hoặc value thì mỗi lần alert fire sẽ tạo fingerprint mới. Ví dụ hai alert payment-svc latency_p99_ms crit tại hai thời điểm khác nhau sẽ không còn được deduplicate mặc dù thực chất là cùng một loại alert.

2. Deduplicate alert là nhiều lần xuất hiện của cùng một loại alert. Corrected alert là các alert khác nhau nhưng có khả năng thuộc cùng incident, ví dụ payment-svc latency, checkout-svc downstream_payment_error, và edge-lb upstream_5xx_rate.

3. gap_sec=30 và gap_sec=600
- gap_sec=30 dễ tạo nhiều cluster hơn, có nguy cơ tách một incident dài thành nhiều phần.
- gap_sec=600 tạo ít cluster hơn nhưng có nguy cơ gộp các incident độc lập lại với nhau.

4. Alert của recommender-svc là cpu_utilization, thuộc nhóm resource và không có quan hệ topology đủ mnahj với payment incident. Vì vậy correlator giữu nó thành một cluster riêng thay vì gộp vào cluster chính.

5. Topology grounding chỉ dựa trên dependency graph nên có thể tạo false correlation khi hai service ở gần nhau trên graph nhưng trong thực tế là những sự cố độc lập. Cải thiện theo hướng là bổ sung semantic similarity hoặc root-cause scoring dựa trên metric và historical incidents.