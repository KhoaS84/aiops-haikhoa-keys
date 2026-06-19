# Assignment Day 3 - Data Layer Architecture

## 1. Architecture Diagram
![](diagram/1.jpg)
![](diagram/2.jpg)

## 2. Cost Estimate Model
| Tier   |   Build_Storage Cost |   Build_Kafka/Network Cost |   Build_Compute Cost |   Total_Build |   Total_Buy_Saas |
|:-------|---------------------:|---------------------------:|---------------------:|--------------:|-----------------:|
| Small  |                   25 |                        300 |                  500 |           825 |             2550 |
| Medium |                   50 |                       3000 |                 1000 |          4050 |             5100 |
| Large  |                  100 |                       6000 |                 2500 |          8600 |            10500 |

## 3. Architecture Decision Record
**ADR-001: Sử dụng Apache Kafka làm lớp đệm truyền tải telemetry**
*   *Quyết định:* Thêm Kafka vào giữa OTel Collector và Storage.
*   *Lý do:* Khắc phục tình trạng mất dữ liệu và chậm ứng dụng khi Elasticsearch bị quá tải trong các khung giờ cao điểm.
*   *Đánh đổi:* Tốn thêm ~$1,200/tháng và độ trễ tăng thêm 15-30ms, nhưng đổi lại độ tin cậy đạt 100% và hệ thống scale tốt hơn.

## 4. Reflection
*Câu hỏi*: Nếu được thuê làm Platform Engineer cho startup 50-service vừa raise Series A, bạn sẽ recommend Build tự làm open-source hay Buy dùng SaaS? Tại sao?

*Trả lời*:
Với một startup vừa gọi vốn SeriesA và quy mô khoảng 50 services, em sẽ đề xuất phương án Buy "dùng SaaS". Vì startup ở giai đoạn này cần tập trung nguồn lực kỹ sư vào việc phát triển tính năng chính để sinh lời, thay vì dành thời gian 3-6 tháng để cài đặt và vận hành hệ thống Kafka/Elasticsearch. SaaS chỉ mất 1-2 tuần để tích hợp. Mặc dù tự xây dựng rẻ hơn khi quy mô rất lớn nhưng ở mức 50 services, số tiền tiết kiệm từ hạ tầng không bù đắp được chi phí con người từ xây dựng đến vận hành. Khi hệ thống tiến tới mức hàng ngìn services, lúc đó việc chuyển dần sang việc tự build sẽ hợp lý hơn cho bài toán kinh tế. 