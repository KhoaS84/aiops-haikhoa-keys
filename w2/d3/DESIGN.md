1. Kiến trúc Pipeline
Service này sử dụng FastAPI để đưa pipeline AIOps từ đang chạy thủ công trong notebook thành một HTTP API service. Endpoint chính là POST /incident, dùng để nhận một batch alert ở dạng JSON. Trước khi xử lý, dữ liệu đầu vào được kiểm tra bằng Pydantic. Mỗi alert bắt phải có các trường id, ts, service, metric, severity, value, và threshold. Nếu input thiếu field hoặc sai định dạng, FastAPI sẽ tự động trả về lỗi validation 422 thay vì làm service crash.

2. Latency Budget
Mục tiêu latency của endpoint là p99 dưới 10 giây. Ở phiên bản local hiện tại, service chưa gọi LLM bên ngoài nên thời gian xử lý chủ yếu đến từ HTTP parsing, Pydantic validation, gom alert, tính root cause đơn giản và serialize JSON response. Với batch alert nhỏ, latency sẽ thấp vì logic xử lý hiện tại khá nhẹ.

Nếu sau này nối service với pipeline của ngày thứ hai đầy đủ và có thêm LLM enrichment, phần gọi LLM sẽ chiếm thời gian lớn nhất. Lý do là LLM call phụ thuộc vào network, provider bên ngoài và thời gian inference của model. Vì vậy trong production cần có timeout, retry limit, cache response cho prompt lặp lại, và có thể skip LLM nếu RCA dựa trên graph đã có confidence cao.

Service hiện tại đã thêm middleware để đo thời gian xử lý mỗi request. Middleware này ghi log latency và trả thêm header X-Processing-Time-ms, giúp dễ quan sát thời gian xử lý khi test local.

3. Production Concern
Một vấn đề production quan trọng là fault tolerance. Service không nên trả lỗi 500 cho những input thông thường. Nếu alert thiếu field, Pydantic sẽ trả 422. Nếu danh sách alert rỗng, endpoint chủ động trả 400 với message Empty alert list. Điều này giúp APi rõ ràng hơn và tránh làm người dùng hiểu nhầm rằng hệ thống bị lỗi nội bộ.

Mộ vấn đề khác là readiness. Một service có thể đang chạy nhưng chưa chắc đã sẵn sàng nhận traffic. Vì vậy /healthz chỉ kiểm tra app còn sống, còn /readyz kiểm tra trạng thái sẵn sàng của pipeline. Trong phiên bản hiện tại, /readyz kiểm tra cấu hình cơ bản như GAP_SEC và MAX_HOP. Trong production thật, /readyz nên kiểm tra thêm service graph, incident history, database, cache hoặc model dependency.

Concurrency cũng là một concern cần chú ý. Nếu chạy một Uvicorn worker với code đồng bộ, nhiều request đồng thời có thể phải chờ nhau. Khi scale production, thể cải thiện bằng cách chạy nhiều worker, dùng async cho external call, tránh shared mutable state và cache các computaiont tốn kém.

4. FastAPI được chọn thay vì Flask hoặc BentoML vì phù hợp với bài toán này nhất. Flask đơn giản và dễ dùng cho prototype, nhưng không có validation input mạnh bằng Pydantic và không tự động tạo OpenAPI docs tốt như FastAPI. BentoML phù hợp nhất khi cần serve một ML model cụ thể, nhưng bài này không chỉ serve model mà serve cả pipeline AIOps gồm correlation, RCA, validation, health check, versioning và response formatting.

FastAPI có lợi thế là hỗ trợ type hints, Pydantic validation, async support và tự động sinh giao diện tài liệu API tại /docs. Điều này giúp việc test endpoint /incident, /healthz, /readyz, và /version dễ dàng hơn. FastAPI đủ đơn giản để làm lab nhưng vẫn gần với cách xây dựng production API service thực tế.