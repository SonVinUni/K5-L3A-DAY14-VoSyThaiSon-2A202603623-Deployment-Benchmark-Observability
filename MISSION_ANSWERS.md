# Day 14 Lab — Mission Answers

## Part 1 — Localhost vs Production

### Exercise 1.1 — Anti-patterns

1. `develop/app.py:17–18` đặt khóa mẫu và chuỗi kết nối PostgreSQL có mật khẩu ngay trong mã nguồn. Nếu làm tương tự với credential thật, người có quyền đọc repo hoặc lịch sử Git có thể lấy được chúng.
2. `develop/app.py:21–22` đặt `DEBUG` và `MAX_TOKENS` thành hằng số, nên muốn thay các giá trị này theo môi trường phải sửa mã.
3. `develop/app.py:33–38` dùng `print()` cho log request và response, đồng thời in cả giá trị khóa ở dòng 34. Log thu thập tập trung có thể làm lộ khóa thật và nội dung người dùng.
4. Bản develop chỉ khai báo `GET /` và `POST /ask` (dòng 25 và 30). Thiếu probe riêng để hạ tầng theo dõi tiến trình và quyết định khi nào chuyển traffic vào app.
5. `develop/app.py:51–53` bind `localhost`, cố định cổng 8000 và bật reload. Container cần nhận kết nối từ bên ngoài tiến trình, và nền tảng có thể cấp cổng động qua biến `PORT`.
6. Bản develop chưa có logic startup/shutdown của ứng dụng để chuyển trạng thái sẵn sàng hoặc dọn tài nguyên khi tiến trình dừng.

### Exercise 1.2 — Chạy bản develop

- Gọi `POST /ask?question=Hello` trên cổng 8000.
- Tôi chạy lệnh từ Git Bash qua Ubuntu WSL 2 với Python 3.14.4. Kết quả là `HTTP/1.1 200 OK`, `content-type: application/json`.

```json
{"answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."}
```

Câu trả lời trên là chuỗi mẫu của mock. Uvicorn phục vụ request ở `localhost:8000`. Nội dung `answer` có thể khác giữa các lần gọi vì mock chọn ngẫu nhiên.

### Exercise 1.3 — So sánh

| Hạng mục | Develop | Production | Vì sao quan trọng |
| --- | --- | --- | --- |
| Cấu hình | Các giá trị gắn trong `app.py` | `production/config.py` đọc `PORT`, `DEBUG`, `OPENAI_API_KEY` và các cấu hình khác từ môi trường | Có thể dùng cùng mã nguồn ở nhiều môi trường và giữ credential khỏi lịch sử Git. |
| Health và readiness | Thiếu endpoint riêng | `production/app.py:135–157` thêm `/health` và `/ready` | Liveness cho biết app còn phản hồi. Readiness cho biết app có thể nhận traffic và trả 503 khi chưa sẵn sàng. |
| Logging | `print()` và có dòng in khóa | Log request/response theo sự kiện và độ dài nội dung, có timestamp và mức log | Dễ lọc sự kiện khi vận hành và giảm thông tin nhạy cảm ghi vào log. |
| Shutdown | Thiếu hook vòng đời của app | `production/app.py:39–65` dùng FastAPI lifespan cho startup và shutdown | Ứng dụng có điểm thực hiện cleanup khi server dừng. Uvicorn điều phối việc dừng và chờ các request đang chạy. |
| Mạng và reload | `localhost:8000`, luôn reload | `production/config.py:17–19` và `production/app.py:194–199` dùng `HOST`, `PORT`, `DEBUG`, mặc định bind `0.0.0.0` và tắt reload | Hạ tầng container có thể chuyển request đến app, đồng thời cổng và chế độ chạy cấu hình được. |

## Part 2 — Docker

### Exercise 2.1 — Dockerfile cơ bản

1. Base image là `python:3.11`, đã có Python và pip.
2. `WORKDIR /app` đặt thư mục làm việc trong image và khi chạy container.
3. Copy `requirements.txt` và cài package trước khi copy mã ứng dụng. Khi chỉ sửa `app.py`, BuildKit có thể tái sử dụng layer cài dependencies.
4. `CMD` đặt lệnh hoặc tham số mặc định và có thể bị thay bằng tham số sau tên image trong `docker run`. `ENTRYPOINT` đặt chương trình chính. Khi khai báo cả hai ở dạng exec, `CMD` cung cấp tham số mặc định cho `ENTRYPOINT`.

### Exercise 2.2 — Chạy container develop

- Tôi kiểm tra từ Git Bash: `POST /ask?question=Hello` qua cổng 8000 của container trả `HTTP/1.1 200 OK`, `content-type: application/json` và JSON có trường `answer`.

```json
{"answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic."}
```

### Exercise 2.3 — Multi-stage build

Stage `builder` dùng `python:3.11-slim`, cài công cụ build và đưa các package Python vào `/root/.local`. Stage `runtime` cũng dùng base slim, copy package đã cài sang `/home/appuser/.local` và thêm mã ứng dụng. Image cuối bỏ được các layer `gcc` và `libpq-dev` của builder và chạy dưới user `appuser`.

| Image | `DISK USAGE` từ `docker images` | Byte từ `docker image inspect` | `CONTENT SIZE` từ `docker images` |
| --- | ---: | ---: | ---: |
| `my-agent:develop` | 1.67 GB | 1,667,780,185 | 426 MB |
| `my-agent:advanced` | 240 MB | 239,815,398 | 57.4 MB |

Trong lần tôi đo lại, `DISK USAGE` giảm **85.62%**, tính theo `(1,667,780,185 − 239,815,398) / 1,667,780,185 × 100%`. Theo cột `CONTENT SIZE`, mức giảm khoảng **86.5%** (số Docker đã làm tròn). Lần đo đầu ngay sau khi build hiển thị 57.4 MB cho `DISK USAGE` của production; hai lần đo sau hiển thị 240 MB với cùng image ID `23774c2f04d4`. `CONTENT SIZE` vẫn là 57.4 MB.

### Exercise 2.4 — Docker Compose stack

```text
Client → Nginx :80 → agent :8000
                     ├── Redis :6379
                     └── Qdrant :6333
```

Compose đặt bốn service trên mạng `internal`. Agent chờ Redis và Qdrant healthy, còn Nginx chuyển request đến upstream `agent:8000`. Compose cung cấp `REDIS_URL` và `QDRANT_URL` cho agent. Hai mũi tên từ agent thể hiện cấu hình kết nối của stack. Các handler mock trong `main.py` của bài này chưa truy vấn hai service đó.

- Khi tôi chạy stack `k5-day14-docker`, Compose khởi động agent, Redis, Qdrant và Nginx. Qua Nginx, `GET /health` và `POST /ask` đều trả `200 OK` với header `Server: nginx`; `/health` trả `status: ok` và `/ask` trả JSON có trường `answer`. Tôi dùng `docker compose down` để dừng cả bốn container.

## Part 3 — Cloud Deployment

### Exercise 3.1 — Railway

Service `agent` trong project Railway `day14-agent` build từ `06-lab-complete/Dockerfile` theo `06-lab-complete/railway.toml`. Dịch vụ `Redis` chạy trong cùng môi trường. Agent nhận `REDIS_URL` qua biến tham chiếu từ Redis và nhận `AGENT_API_KEY` qua biến bí mật. URL công khai là [agent-production-e7e68f12.up.railway.app](https://agent-production-e7e68f12.up.railway.app). Kết quả chạy thực tế là `GET /health → 200`, `GET /ready → 200`, `POST /ask` thiếu key → `401` và key hợp lệ → `200`. Xem [DEPLOYMENT.md](DEPLOYMENT.md).

### Exercise 3.2 — So sánh Railway và Render

| Hạng mục | Railway của bài nộp | Render Blueprint mẫu |
| --- | --- | --- |
| Build và chạy | `railway.toml` đặt `builder = "DOCKERFILE"`. Dockerfile chứa lệnh Uvicorn và đọc `PORT`. | `03-cloud-deployment/render/render.yaml` chọn Python, cài dependency qua `buildCommand` và khởi động qua `startCommand`. |
| Health check | `healthcheckPath = "/health"` trong phần `[deploy]`. | `healthCheckPath: /health` trên mục `type: web`. |
| Redis | Tạo dịch vụ Redis trong cùng project Railway và tham chiếu `REDIS_URL` từ agent. | Blueprint mẫu khai báo thêm dịch vụ Redis trong `services`. Một Blueprint dùng cho agent Part 6 cần nối biến kết nối Redis vào web service. |
| Secrets | Đặt `AGENT_API_KEY` trong variables của service. | Blueprint cho phép nhập giá trị qua Dashboard với `sync: false` hoặc dùng `generateValue: true`. |

### Exercise 3.3 — Cloud Run pipeline

1. Cloud Build cài dependency và chạy `pytest` trong container Python.
2. Sau bước test, pipeline build Docker image và gắn hai tag theo commit và `latest`.
3. Pipeline push các tag lên registry, rồi dùng `gcloud run deploy` triển khai image gắn tag commit lên `asia-southeast1`.
4. `service.yaml` minh họa khai báo cổng, tài nguyên, số instance, concurrency, probe và tham chiếu Secret Manager cho service Cloud Run.

## Part 4 — API Security

### Exercise 4.1 — API key

`verify_api_key` trong `04-api-gateway/develop/app.py` đọc header `X-API-Key`. Endpoint `/ask` gọi dependency này trước khi gọi mock LLM. Thiếu header trả 401, giá trị sai trả 403. Bản mẫu đọc `AGENT_API_KEY` khi import app, nên để đổi khóa cần cập nhật biến môi trường, khởi động lại tiến trình và cập nhật các client.

Kết quả `curl -i` tôi chạy trên localhost:

```http
HTTP/1.1 401 Unauthorized
content-type: application/json

{"detail":"Missing API key. Include header: X-API-Key: <your-key>"}
```

```http
HTTP/1.1 200 OK
content-type: application/json

{"question":"Hello","answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic."}
```

Khi kiểm tra thêm, khóa sai trả `403 Forbidden` và `{"detail":"Invalid API key."}`.

### Exercise 4.2 — JWT

`POST /auth/token` xác thực tài khoản mẫu và cấp JWT ký bằng HS256 có `sub`, `role`, `iat` và `exp`. `/ask` nhận `Authorization: Bearer <token>` và kiểm tra chữ ký cùng hạn dùng. Token có hạn 60 phút. Lần gọi `/ask` đầu tiên bằng JWT hợp lệ trả `200 OK`, JSON có `question`, `answer` và `usage.requests_remaining` bằng `9`. Giá trị token đã được giữ ngoài output.

### Exercise 4.3 — Rate limiting

App dùng sliding window 60 giây và lưu timestamp từng request trong `deque` theo người dùng. Khi nhận request mới, nó loại timestamp đã ra khỏi cửa sổ và so số request còn lại với ngưỡng. Tài khoản thường có giới hạn 10 request/phút, tài khoản role `admin` có giới hạn 100 request/phút. Mỗi tiến trình giữ state riêng trong bộ nhớ.

Tôi gọi `/ask` 10 lần bằng JWT của tài khoản mẫu và cả 10 lần đều trả `200`. Lần thứ 11 trả:

```http
HTTP/1.1 429 Too Many Requests
x-ratelimit-limit: 10
x-ratelimit-remaining: 0
retry-after: 59
content-type: application/json

{"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":59}}
```

### Exercise 4.4 — Cost guard

`production/cost_guard.py` minh họa ngân sách trong RAM, với ngưỡng `$1/ngày` mỗi người dùng và `$10/ngày` toàn ứng dụng. `/ask` kiểm tra ngân sách trước khi gọi mock LLM rồi ghi nhận usage dựa trên số token ước tính. Khi người dùng hết ngân sách, app trả `402`. Khi đạt ngưỡng toàn ứng dụng, mẫu trả `503`.

Với bài toán `$10/tháng` mỗi người dùng, lưu tổng chi phí theo khóa Redis `budget:{user_id}:{YYYY-MM}` và dùng UTC để thống nhất thời điểm sang tháng. Trước khi gọi LLM, kiểm tra tổng đã dùng cộng chi phí dự kiến và giữ chỗ số tiền đó trong cùng một thao tác nguyên tử. Nếu tổng vượt ngưỡng, trả `402`. Khi có usage thực tế, đối soát phần đã giữ. Khóa tháng mới bắt đầu từ 0 và khóa cũ có thể hết hạn sau khi sang tháng. Rate limit khống chế số lượt gọi trong thời gian ngắn, còn cost guard khống chế ngân sách ngay cả khi mỗi lượt gọi có chi phí khác nhau.

## Part 5 — Scaling & Reliability

### Exercise 5.1 — Liveness và readiness

`GET /health` cho biết tiến trình còn phản hồi và cung cấp trạng thái cơ bản. `GET /ready` cho biết instance có thể nhận traffic. Trong mẫu develop, cờ `_is_ready` được bật sau startup và `/ready` trả 503 khi cờ tắt. Trong stack production đang dùng Redis, `/ready` gọi `PING` và trả 503 nếu mất kết nối. `/health` vẫn trả 200 với trạng thái `degraded` trong trường hợp đó.

### Exercise 5.2 — Graceful shutdown

Khi nhận `SIGTERM`, Uvicorn ngừng nhận kết nối mới, đợi các request đang xử lý và chạy phần shutdown của FastAPI lifespan. Mẫu develop theo dõi request đang xử lý trong middleware và có timeout shutdown 30 giây. Khi tôi gửi `SIGTERM` lúc `POST /ask?question=Long%20task` đang chạy, request vẫn trả `200 OK`. Tiến trình ghi `Graceful shutdown initiated` và `Shutdown complete`, rồi thoát với mã 0.

### Exercise 5.3 — Session dùng Redis

Các tiến trình có bộ nhớ riêng. Nếu giữ lịch sử trong một `dict` của tiến trình, agent B sẽ không thấy tin nhắn trước đó do agent A xử lý. Mẫu production đọc và ghi session bằng khóa `session:{session_id}` trong Redis, với TTL 3.600 giây và tối đa 20 tin nhắn. Mỗi lần gọi gửi lại `session_id` để một instance bất kỳ lấy cùng lịch sử. Mẫu có thể fallback sang RAM nếu lúc khởi động không kết nối được Redis. Tính liên tục giữa các instance được kiểm tra với Redis đang chạy.

### Exercise 5.4 — Nginx và ba instance

Tôi chạy Compose với project `k5-day14-scaling` và `--scale agent=3`; cả ba agent và Redis đều healthy. Khi kiểm tra qua Nginx cổng 8080, `/health` trả `200`, `storage: redis`, `redis_connected: true`; `/ready` trả `200` và `ready: true`. Hai request đi qua hai upstream khác nhau theo header `X-Served-By`. Nginx nhận request ở cổng 8080 và chuyển đến agent ở cổng 8000 trong mạng Compose.

### Exercise 5.5 — Kiểm tra lịch sử phiên

`test_stateless.py` gửi 5 câu hỏi cùng `session_id`, rồi gọi `/chat/{session_id}/history`. Khi tôi chạy lại qua WSL, request lần lượt đi qua các instance `edc23e → 6d6c11 → be19a0 → edc23e → 6d6c11`. Redis trả đủ **10 tin nhắn**: 5 câu hỏi và 5 câu trả lời. Bài kiểm tra này xác nhận session được giữ khi request chuyển giữa ba instance. Script gửi request tuần tự; tôi chưa kiểm tra trường hợp dừng một instance.

## Part 6 — Final Project

Agent trong `06-lab-complete/` dùng cấu hình từ biến môi trường, API key tự đặt cho `/ask` và mock LLM. `/health` chỉ báo tiến trình còn sống. `/ready` kiểm tra Redis và trả 503 khi Redis gián đoạn. Redis chia sẻ sliding window giữa các worker và giữ state sau khi restart agent. Cost guard giữ chỗ ngân sách nguyên tử trước khi gọi mock, rồi đối soát số token ước tính theo phản hồi. Mặc định giới hạn tổng của agent là `$10/tháng` theo UTC. Đặt `DAILY_BUDGET_USD` để dùng giới hạn ngày. Uvicorn điều phối graceful shutdown và FastAPI đóng kết nối Redis khi dừng.

Tôi chạy bộ chấm đầy đủ trong WSL 2 với Python 3.11.18 và Docker Desktop. Script báo image **273 MB**. Request đang chạy vẫn trả `200` khi tiến trình nhận `SIGTERM`; `docker stop` mất **0.5 giây** và thoát mã 0.

```text
📋 Checklist Deliverable
   ✅ Dockerfile (multi-stage, < 500 MB)
   ✅ docker-compose.yml (agent + redis)
   ✅ .dockerignore
   ✅ Health check endpoint (GET /health)
   ✅ Readiness endpoint (GET /ready)
   ✅ API Key authentication
   ✅ Rate limiting
   ✅ Cost guard
   ✅ Config từ environment variables
   ✅ Structured logging
   ✅ Graceful shutdown
   ✅ Public URL ready (Railway / Render config)
----------------------------------------------------------------
Result: 12/12 tiêu chí đạt · 41/41 checks passed
🎉 PASS 12/12 — PRODUCTION READY! Deploy nào!
```

## AI log

- CP1–CP4: Tôi dùng Codex và Claude để rà đề, giải thích các mẫu code và kiểm tra một số kết quả. Tôi tự chạy Uvicorn, `curl`, Docker Compose và các lệnh kiểm tra; kết quả chi tiết nằm ở từng phần phía trên.
- CP5: Tôi dùng Codex hỗ trợ hoàn thiện cấu hình, endpoint, Redis, logging, Docker và Railway theo checklist. Tôi tự chạy bộ chấm trong WSL 2; kết quả là 12/12 tiêu chí và 41/41 checks.
- CP6: Tôi dùng Codex để đối chiếu cấu hình Railway, Render và Cloud Run. Tôi đăng nhập Railway, đồng ý triển khai lên Trial và tự kiểm tra URL công khai: `200 / 200 / 401 / 200`.
- CP7: Tôi dùng Codex hỗ trợ histogram, benchmark và eval; hai mục JWT và HPA được bổ sung vào kho tri thức. Tôi tự chạy quality gate, đạt 23/23 và không regression.
- CP8: Tôi dùng Codex hỗ trợ chạy Locust, đối chiếu trace và kiểm tra alert. Sau khi sửa đường dẫn package và chạy lại Locust với `--no-deps`, tôi lưu kết quả CSV, log và ảnh trong repo; số liệu được trình bày ở `BENCHMARK_REPORT.md`.
