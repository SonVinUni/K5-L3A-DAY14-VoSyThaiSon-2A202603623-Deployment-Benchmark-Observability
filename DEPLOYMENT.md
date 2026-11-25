# Deployment Information

## Public URL

[https://agent-production-e7e68f12.up.railway.app](https://agent-production-e7e68f12.up.railway.app)

## Platform

Railway, project `day14-agent`, môi trường `production`. Service `agent` build bằng Dockerfile trong `06-lab-complete/`. Service `Redis` chạy cùng môi trường và được kết nối qua `REDIS_URL`.

## Environment Variables

| Biến | Thiết lập |
| --- | --- |
| `PORT` | Railway cấp cho agent. Dockerfile truyền giá trị cho Uvicorn. |
| `ENVIRONMENT` | `production` |
| `REDIS_URL` | Biến tham chiếu `${{Redis.REDIS_URL}}` khi service Redis có tên `Redis`. |
| `AGENT_API_KEY` | Khóa tôi tạo và lưu trong Variables của service agent. |

## Test Commands

Chạy trong Git Bash. Khối lệnh yêu cầu nhập khóa agent và chỉ hiển thị tên phép thử cùng mã HTTP. Trên máy lab, có thể đọc khóa đã lưu từ `$HOME/AppData/Local/day14/cp6-agent-key.txt` mà không in khóa ra terminal.

```bash
BASE=https://agent-production-e7e68f12.up.railway.app
read -r -s -p 'AGENT_API_KEY: ' AGENT_API_KEY
printf '\n'

curl -sS --max-time 15 -o /dev/null -w 'GET /health -> %{http_code}\n' "$BASE/health"
curl -sS --max-time 15 -o /dev/null -w 'GET /ready -> %{http_code}\n' "$BASE/ready"
curl -sS --max-time 15 -o /dev/null -w 'POST /ask (no key) -> %{http_code}\n' \
  --json '{"question":"Hello"}' "$BASE/ask"
curl -sS --max-time 15 -o /dev/null -w 'POST /ask (with key) -> %{http_code}\n' \
  -H "X-API-Key: $AGENT_API_KEY" --json '{"question":"Hello"}' "$BASE/ask"
unset AGENT_API_KEY
```

Kết quả tôi tự kiểm tra ngày 25-11-2026:

```text
GET /health -> 200
GET /ready -> 200
POST /ask (no key) -> 401
POST /ask (with key) -> 200
```

## Screenshots

- [Dashboard](screenshots/dashboard.png) — project có service agent và Redis.
- [Deployment](screenshots/running.png) — deployment agent đang chạy và có domain công khai.
- [Kết quả HTTP](screenshots/test.png) — ảnh chụp bản hiển thị output thực tế của bốn lệnh `curl`.
