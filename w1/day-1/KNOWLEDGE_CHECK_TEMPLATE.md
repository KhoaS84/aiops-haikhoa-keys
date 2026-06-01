# Knowledge Check - Viết Tay Trên Giấy

**Hướng dẫn:** Viết tay trả lời các câu hỏi dưới đây trên giấy A4, sau đó chụp ảnh rõ và nộp kèm file SUBMIT.md

---

## Câu 1: Giải Thích Skewness

**Viết tay trả lời:**

1. Skewness là gì?
   - Định nghĩa từ ngôn ngữ thống kê
   - Công thức tính hoặc công thức ngắn gọn
   - Phân loại: skew trái (negative skew), skew phải (positive skew), no skew

2. Data bị skew (trong bài tập này skew=35.75) thì 3σ sai ở đâu?
   - 3σ giả định gì về phân bố dữ liệu
   - Khi dữ liệu lệch, điểm dữ liệu ở tail bên ngoài 3σ nhưng không phải anomaly thực sự
   - Ví dụ cụ thể từ rogue_agent_key_updown.csv

3. Hai cách xử lý khi gặp dữ liệu lệch:
   - Cách 1: IQR (cách được dùng trong bài)
   - Cách 2: Transformation (log transform, Box-Cox, v.v.)
   - Viết công thức và giải thích tại sao hiệu quả hơn 3σ

---

## Câu 2: So Sánh 3σ vs EWMA vs STL

**Viết tay tạo bảng so sánh:**

| Phương pháp | 3σ | EWMA | STL |
|---|---|---|---|
| Detect loại anomaly nào? |  |  |  |
| Ưu điểm |  |  |  |
| Nhược điểm / Fail ở đâu? |  |  |  |
| Dùng khi nào (use case)? |  |  |  |
| Yêu cầu tuning parameter? |  |  |  |

**Gợi ý viết:**
- 3σ: phát hiện point anomaly, giả định phân bố chuẩn, không điều chỉnh xu hướng
- EWMA: phát hiện sudden changes, smooth time series, dùng khi data có trend
- STL: phát hiện seasonal/trend anomaly, tách biệt thành seasonal+trend+residual, dùng khi có mùa vụ rõ

---

## Câu 3: Isolation Forest - Path Length

**Viết tay giải thích:**

1. Ý tưởng chủ yếu: "path length ngắn = anomaly"
   - Cây quyết định (decision tree) trong IF hoạt động như thế nào
   - Tại sao anomaly bị cô lập nhanh hơn (path ngắn)
   - Tại sao normal point cần path dài hơn

2. Vẽ sơ đồ nhỏ (tree diagram):
   - Ví dụ: 1D data với 1 point anomaly
   - Vẽ 2-3 lần split, chỉ ra cách anomaly bị isolate ở early split

3. Tại sao cần feature engineering trước khi feed vào IF?
   - Trong bài: 11 features được tạo ra thay vì chỉ dùng "value"
   - Feature engineering cung cấp gì cho IF? (context, temporal patterns, volatility info)
   - Nếu không có feature engineering, IF chỉ dùng "value" → kết quả thế nào?

---

## Câu 4: Univariate vs Multivariate

**Scenario:** Memory leak detection
- Memory usage tăng từ từ, nhưng không vượt threshold
- CPU usage bình thường
- Network traffic bình thường

**Viết tay giải thích:**

1. **Univariate approach** (chỉ dùng memory):
   - Kết quả: Miss (bỏ qua) vì memory chưa vượt threshold
   - Tại sao?

2. **Multivariate approach** (dùng memory + CPU + network + ...):
   - Kết quả: Catch (phát hiện được)
   - Tại sao? Giải thích mối liên hệ giữa các đặc trưng
   - Ví dụ: memory tăng + file descriptor tăng = memory leak

3. Kết luận: khi nào dùng univariate, khi nào dùng multivariate?

---

## Câu 5: Precision vs Recall trong AIOps

**Viết tay:**

1. Định nghĩa:
   - Precision = ? (công thức)
   - Recall = ? (công thức)

2. Bảng Confusion Matrix:
   ```
   |           | Predicted Positive | Predicted Negative |
   |-----------|---|---|
   | Actual Positive |  TP |  FN |
   | Actual Negative |  FP |  TN |
   ```

3. **Trong AIOps, tại sao ưu tiên Recall?**
   - False Negative (bỏ qua sự cố) = chi phí cao (system down, user impact)
   - False Positive (cảnh báo giả) = chi phí thấp hơn (on-call engineer check)
   - Ví dụ: database outage vs disk space warning

4. **Trade-off khi tune threshold:**
   - Khi tăng threshold → Precision tăng, Recall giảm
   - Khi giảm threshold → Precision giảm, Recall tăng
   - Vẽ biểu đồ PR curve hoặc ROC curve (nếu vẽ được)
   - Điểm tối ưu nằm ở đâu trong AIOps context?

5. **Kết luận từ bài tập:**
   - Contamination=0.2 cho Recall=9.25%, Precision=4.83%
   - Tại sao chọn điểm này thay vì contamination nhỏ hơn (recall thấp hơn)?

---

## Hướng Dẫn Nộp Bài

1. Viết tay trên giấy A4 (hoặc nhiều trang nếu cần)
2. Viết rõ ràng, dễ đọc
3. Có thể vẽ sơ đồ, biểu đồ, bảng
4. Chụp ảnh từng trang (màu hoặc đen trắng)
5. Dán ảnh vào file Word/PDF, hoặc tạo thư mục `knowledge_check_images/`
6. Nộp kèm SUBMIT.md

---

## Tệp Nộp

Cấu trúc thư mục cuối cùng:
```
w1/day-1/
  ├── assignment.ipynb
  ├── SUBMIT.md
  ├── KNOWLEDGE_CHECK_TEMPLATE.md (file này)
  ├── knowledge_check_images/
  │   ├── Q1_skewness.jpg
  │   ├── Q2_comparison.jpg
  │   ├── Q3_isolation_forest.jpg
  │   ├── Q4_univariate_vs_multivariate.jpg
  │   └── Q5_precision_recall.jpg
  └── models/
      └── isolation_forest_cont0.2.pkl
```

---

**Ghi chú:** Ngày nộp: 1 tháng 6 năm 2026
