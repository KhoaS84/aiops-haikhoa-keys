# Nộp bài

## Ảnh chụp
- Biểu đồ time series + điểm bất thường: assets/phase2_template_count.png

## Kết quả
- HDFS (200k dòng): 25 templates; top-10 ở results/top_templates.csv
- BGL (200k dòng): 108 templates
- Tuning `drain_sim_th`: results/drain_sim_th_tuning.csv
- Log analyzer HDFS: top-5 = 1(23.26%), 5(22.46%), 3(22.44%), 4(22.44%), 2(7.82%)
- Log analyzer BGL: top-5 = 18(48.46%), 79(13.01%), 1(11.31%), 70(9.18%), 99(3.76%)
- HDFS (label): precision=0.0259, recall=0.7037

## Nhận xét
- Drain3 ổn định, gom nhóm tốt; template rõ ràng với tham số `*`.
- Insight chính từ nhóm DataNode/FSNamesystem, phản ánh thao tác I/O và quản lý block.
- Metric cho biết mức độ; log cho biết nguyên nhân; kết hợp giúp khoanh vùng root cause nhanh hơn.

## Viết tay
- Ảnh/scan: assets/cau1-2.jpg, assets/cau3-4.jpg, assets/cau5.jpg