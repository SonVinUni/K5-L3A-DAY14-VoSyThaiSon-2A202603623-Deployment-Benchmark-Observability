"""
API Key authentication (tiêu chí 6).

Yêu cầu:
  • Client gửi header  X-API-Key: <key>
  • Key phải trùng biến môi trường AGENT_API_KEY
  • Thiếu hoặc sai key → HTTP 401 (không phải 403 hay 422)
"""
from secrets import compare_digest
from typing import Annotated

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from .config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(key: Annotated[str | None, Security(api_key_header)]) -> str:
    if not key or not settings.agent_api_key or not compare_digest(
        key.encode(), settings.agent_api_key.encode()
    ):
        raise HTTPException(status_code=401, detail="Missing or invalid API key")
    return key
