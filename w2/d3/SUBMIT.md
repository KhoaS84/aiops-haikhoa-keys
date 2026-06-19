1. Mục tiêu latency budget của endpoint là p99 dưới 10 giây. Ở phiên bản hiện tại, service đang chạy local và dùng pipeline đơn giản, chưa gọi LLM provider bên ngoài. Vì vậy latency chủ yếu đến từ việc parse HTTP request, validate input bằng Pydantic, gom alert thành cluster, tính root cause đơn giản và serialize JSON response. Với batch alert nhỏ, các bước này thường rất nhanh.

Nếu nối với pipeline production đầy đủ có LLM enrichment, phase chiếm thời gian nhiều nhất sẽ là LLM call. Lý do là LLM call phụ thuộc vào network, provider bên ngoài và thời gian model inference. Để kiểm soát latency, hệ thống nên có timeout, retry limit, cache kết quả cho prompt lặp lại và bỏ qua LLM khi graph-based RCA đã có confidence đủ cao.

2. Với 5 alert, phần lớn latency là fixed cost như HTTP overhead, request validation, gọi function và format response. Logic correlation/RCA gần như không đáng kể vì số lượng alert rất nhỏ.

Với 500 alert, endpoint phải validate nhiều object hơn, duyệt qua nhiều alert hơn, gom service, đếm số lượng alert theo service và sort timestamp. Vì vậy latency sẽ tăng theo số lượng alert. Trong implementation hiện tại, độ phức tạp gần như tuyến tính vì pipeline chủ yếu loop qua danh sách alert. Tuy nhiên nếu nối với pipeline graph-based đầy đủ, một số bước như topology traversal, shortest path hoặc RCA trên graph có thể tốn thời gian hơn nếu không cache hoặc optimize.

3. Nếu LLM provider bị down, endpoint không nên bị treo vô hạn hoặc làm toàn bộ incident pipeline thất bại. Mọi outbound call tới LLM cần có timeout và retry limit. Nếu LLM call fail, hệ thống nên fallback sang graph-only RCA hoặc rule-based RCA.

Trong fallback mode, response vẫn nên trả về root cause candidate, confidence, reasoning và recommended actions dựa trên pipeline không dùng LLM. Reasoning nên ghi rõ rằng LLM enrichment đã bị skip hoặc không khả dụng. Ngoài ra có thể dùng feature flag như AIOPS_USE_LLM=false để tắt LLM khi provider đang lỗi. Cách này giúp hệ thống vẫn hỗ trợ incident triage ngay cả khi dependency bên ngoài gặp sự cố.

4. /healthz là liveness check. Nó trả lời câu hỏi: “Process của service còn sống không?”. Trong bài này, /healthz trả về {"status":"ok"} nếu FastAPI app đang chạy.

/readyz là readiness check. Nó trả lời câu hỏi: “Service đã sẵn sàng nhận traffic thật chưa?”. Một service có thể còn sống nhưng chưa sẵn sàng nếu chưa load service graph, incident history, config hoặc model dependency. Trong bản hiện tại, /readyz kiểm tra app và pipeline config. Trong production, /readyz nên kiểm tra thêm graph, history, cache, database hoặc model service.

Khi deploy, /healthz thường dùng để quyết định container/process có cần restart không. /readyz dùng để quyết định instance này đã được route traffic vào hay chưa.

5. Nếu chạy một Uvicorn worker và pipeline code là synchronous, 4 request đồng thời có thể chưa scale tốt. Với request nhỏ, service local vẫn có thể xử lý ổn vì logic hiện tại nhẹ. Nhưng nếu một request có nhiều alert hoặc có gọi LLM bên ngoài, các request khác có thể phải chờ lâu hơn.

Bottleneck đầu tiên nhiều khả năng là LLM call nếu bật LLM enrichment. Nếu không dùng LLM, bottleneck có thể là validation và computation khi batch alert lớn. Để cải thiện concurrency, có thể chạy nhiều Uvicorn workers, dùng async cho external call, cache computation lặp lại và thiết kế service stateless để tránh race condition với shared state.