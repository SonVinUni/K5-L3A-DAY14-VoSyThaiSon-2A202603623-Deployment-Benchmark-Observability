# Benchmark & Observability Report — Day 14

**Họ tên:** Vo Sy Thai Son

**Ngày chạy:** 25-11-2026 (GMT+7)
**Môi trường tôi dùng:** Windows, Ubuntu WSL 2, Python 3.11.18, Intel Core i5-12500H; WSL nhận 16 CPU logic và khoảng 7,65 GiB RAM.

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---|---|
| p95 latency `/ask` | ≤ 500 ms | Ngưỡng mặc định của `load_test.py`. Giới hạn thời gian phản hồi cho phần lớn request. |
| Error rate `/ask` | ≤ 2% | Ngưỡng mặc định của `load_test.py`. Tính cả phản hồi khác 200 và lỗi kết nối. |
| Accuracy trên golden dataset | ≥ 85% | Ngưỡng quality gate cho CI theo Exercise 7.3. Bản sửa còn phải đạt 100% và không có regression ở CP7. |

---

## 2. Benchmark hiệu năng (develop, `load_test.py`)

### 2.1 Concurrency vs latency (agent v2)

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---|---|---|---|---|---|
| 1 | 4.01 | 188.4 | 220.6 | 1702.7 | 0.67% | PASS |
| 10 | 35.67 | 187.2 | 222.2 | 1696.0 | 1.33% | PASS |
| 50 | 108.25 | 198.0 | 258.3 | 1708.7 | 0.33% | PASS |
| 100 | 54.74 | 397.9 | 4238.9 | 4534.3 | 0.00% | FAIL |

Tôi thấy RPS tăng đến 108.25 ở concurrency 50, rồi giảm còn 54.74 ở mức 100. Ở mức 100, p95 tăng lên 4238.9 ms. Một lượt chạy cho thấy độ trễ tăng, nhưng chưa đủ để xác định nút thắt.

Mỗi lượt có 300 request, `MOCK_SLOW_RATE=0.03` và `MOCK_ERROR_RATE=0.01`. Percentile chỉ tính trên phản hồi `200`. Error rate tính trên mọi request.

### 2.2 Tail latency

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|
| 0 | 189.4 | 218.1 | 221.3 |
| 0.03 (mặc định) | 225.4 | 219.7 | 1703.2 |
| 0.1 | 326.7 | 1683.2 | 1706.7 |

Ở concurrency 20, tôi thấy khi 3% request bị làm chậm, trung bình chỉ tăng 36.0 ms còn p99 tăng 1481.9 ms. Khi tỷ lệ lên 10%, p95 cũng tăng mạnh. Tôi dùng p95 cho SLO và theo dõi thêm p99 để thấy nhóm request chậm nhất.

### 2.3 Metrics của agent

Tôi kiểm tra ba loại metric sau:

- Counter `http_requests_total` đếm request theo method, route và mã HTTP.
- Gauge `agent_in_flight_requests` cho biết số request đang xử lý.
- Histogram `agent_question_length_chars` cho biết phân bố độ dài câu hỏi.

Sau một lần gọi `/ask` thành công trên v2 mới khởi động, scrape trả `http_requests_total{method="POST",route="/ask",status="200"} 1.0`, `agent_in_flight_requests 0.0` và `agent_question_length_chars_count 1.0`.

Tôi giữ label theo route template như `/ask`, và gộp URL lạ vào `unmatched`. Dùng URL thô làm label sẽ tăng số time series và bộ nhớ của Prometheus.

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

Tôi so sánh các lượt eval với `MOCK_ERROR_RATE=0` và `MOCK_SLOW_RATE=0` để lỗi và độ trễ ngẫu nhiên của mock không ảnh hưởng phép đo chất lượng.

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | 4.3% (1/23) | 91.3% (21/23) | 100.0% (23/23) |
| Avg tokens / câu | 58.1 | 109.3 | 114.4 |
| Tổng cost (USD) | 0.000418 | 0.000764 | 0.000797 |
| Cost / câu đúng (USD) | 0.00041775 | 0.00003639 | 0.00003465 |
| Latency p95 (ms) | 188.0 | 206.8 | 210.6 |
| Quality gate | FAIL (≥ 85%) | PASS (≥ 85%, so với v1) | PASS (100%, so với v2 ban đầu) |

**Những câu v2 trả lời sai ban đầu và cách bạn sửa:**

| ID | Keyword bị thiếu | Bạn đã sửa gì |
|---|---|---|
| `security-02` | `token`, `hết hạn`, `chữ ký` | Tôi thêm mục `jwt`, giải thích token, claims, chữ ký và hạn dùng so với API key. |
| `scaling-03` | `cpu`, `memory`, `custom metrics` | Tôi thêm mục `hpa`/`kubernetes`, giải thích các metric HPA dùng để điều chỉnh số replica. |

V2 dùng nhiều token hơn vì có thêm ngữ cảnh. Tôi thấy tổng chi phí mô phỏng tăng, nhưng chi phí trên mỗi câu đúng giảm từ 0.00041775 USD xuống 0.00003639 USD. Sau khi bổ sung JWT và HPA, v2 đúng 23/23 và giữ nguyên các câu đã đúng. Tôi chạy lại từ Git Bash và nhận cùng kết quả 23/23, 0 regression.

**Quality gate trong CI.** Nếu đưa bước eval vào CI, tôi sẽ khởi động v2 với `MOCK_ERROR_RATE=0`, đợi `/health`, rồi chạy `python eval/run_eval.py --url http://127.0.0.1:8000 --min-accuracy 0.85 --baseline <baseline.json>`. Tôi sẽ đặt job làm required status check để chặn merge nếu accuracy dưới 85% hoặc có regression.

---

## 4. Observability stack (production)

### 4.1 Grafana và ảnh minh chứng

- [Grafana khi có tải](screenshots/grafana-dashboard.png)
- [Trace chậm](screenshots/jaeger-slow-trace.png) và [trace lỗi](screenshots/jaeger-error-trace.png)
- [Hai alert cùng firing](screenshots/prometheus-alert-firing.png)

Ở lượt quan sát Grafana, tôi thấy 63.0 request/giây, 1.01% lỗi, p95 là 292.22 ms và 18 request đang xử lý. Đó là bốn tín hiệu traffic, errors, latency và saturation. Truy vấn Prometheus lúc 17:37:16 cho p95 khoảng 292.84 ms và trung bình 230.20 ms. Biểu đồ p99 gần 1.8 giây cho thấy vài request chậm kéo dài hơn nhiều.

Hai agent nhận khoảng 31.45 và 31.40 request/giây. Input khoảng 4594 token/giây, cao hơn output khoảng 2440 token/giây vì v2 đưa cả câu hỏi và tài liệu truy xuất vào prompt. Khi tôi kiểm tra `/metrics` qua cổng Nginx 8080, kết quả là `404`. Prometheus scrape trực tiếp từng agent qua mạng Docker.

### 4.2 Thí nghiệm "phá hệ thống"

| Thay đổi | Alert firing | Thời gian tới lần đầu thấy firing | Tín hiệu |
| --- | --- | ---: | --- |
| A · `MOCK_ERROR_RATE=0.2` | `AgentHighErrorRate` | 86.2 giây | Error rate khoảng 21.7%, vượt 5%. |
| B · `MOCK_SLOW_RATE=0.3` | `AgentHighLatencyP95` | 140.5 giây | p95 khoảng 1.89 giây, vượt 1 giây. |

Tôi áp dụng A và B cùng lúc, giữ Locust ở 30 user và theo dõi API Prometheus. Thời gian tính từ lúc bắt đầu đổi cấu hình tới lần đầu API báo `firing`. Hai rule có `for` lần lượt là 1 phút và 2 phút. `promtool test rules` trả `SUCCESS`.

Nếu triển khai nhầm agent v1, tôi sẽ kiểm tra phiên bản qua `agent_info` và chạy eval trên golden dataset. Các alert hạ tầng có thể vẫn xanh trong khi độ chính xác giảm.

### 4.3 Đối chiếu trace với log

**Trace chậm.** `423cecc093d8493537f28efee74743d6` kéo dài **1669.30 ms**. Span `chat mock-llm-small` mất **1652.81 ms**, khoảng **99.0%** tổng thời gian. Retrieval chỉ mất 14.74 ms. Tôi dùng `trace_id` để tìm đúng request có event `llm_call`.

```json
{"ts":"2026-11-25T10:38:31.397967+00:00","level":"INFO","service":"observable-agent","instance":"e519caf0446b","event":"llm_call","trace_id":"423cecc093d8493537f28efee74743d6","span_id":"bc5f586506ff1d90","request_id":"8a45df54d3da","model":"mock-llm-small","agent_version":"v2","input_tokens":74,"output_tokens":37,"cost_usd":3.3e-05,"llm_ms":1652.7}
```

**Trace lỗi.** `005975b7c273d5f6f2fdfb8e695a0f72` kéo dài **91.80 ms** và trả `503`. Span `chat mock-llm-small` mất 73.61 ms, có event `exception` báo upstream mock không sẵn sàng. Log `llm_error` có cùng `trace_id`.

```json
{"ts":"2026-11-25T10:38:32.370824+00:00","level":"INFO","service":"observable-agent","instance":"e519caf0446b","event":"llm_error","trace_id":"005975b7c273d5f6f2fdfb8e695a0f72","span_id":"211a369f2e399d2b","request_id":"4496ec4cf97d","error":"Upstream LLM error: 503 Service Unavailable (mock)"}
```

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | 59.94 | 190 | 230 | 1700 | 66 / 7167 (0.92%) |
| 3 | 59.83 | 190 | 220 | 1700 | 61 / 7152 (0.85%) |

Tôi lấy dòng `POST /ask` trong hai file CSV. Mỗi lượt chạy 100 user trong hai phút, tăng 10 user/giây. Tôi dùng `--no-deps` cho Locust để Compose giữ đúng số replica đã đặt.

Tăng từ 1 lên 3 replica giảm p95 10 ms và p99 vẫn là 1700 ms. RPS gần như giữ nguyên. Ở tải này, thời gian chờ mock LLM và nhịp nghỉ giữa request của Locust có thể giải thích vì sao scale ít tác động. Trace chậm cho thấy riêng span gọi LLM chiếm khoảng 99% thời gian request.

---

## 6. Kết luận

1. Tôi xem p95 và p99 cùng nhau vì một ít request chậm có thể bị trung bình che mất.
2. Tôi dùng eval để đo chất lượng và chi phí trên mỗi câu đúng.
3. Tôi dùng metric để thấy lỗi đang tăng, rồi đối chiếu `trace_id` với log để tìm bước gây lỗi.

Nếu đưa agent lên production, tôi sẽ thêm tỷ lệ 5xx và 504 tại reverse proxy để thấy cả lỗi xảy ra trước khi request tới agent.
