"""
Cost guard (tiêu chí 8).

Yêu cầu:
  • Cộng dồn chi phí LLM (tính theo token) vào Redis
  • Tổng chi phí vượt DAILY_BUDGET_USD (hoặc MONTHLY_BUDGET_USD) → HTTP 402
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import ROUND_DOWN

from fastapi import HTTPException

from .config import settings
from .redis_client import r

# Integer nano-USD avoid rounding drift when several workers update the same budget.
NANO_USD_PER_DOLLAR = 1_000_000_000
INPUT_TOKEN_COST = 150
OUTPUT_TOKEN_COST = 600

reserve_budget = r.register_script("""
local used = tonumber(redis.call('GET', KEYS[1]) or '0')
local amount = tonumber(ARGV[1])
if used + amount > tonumber(ARGV[2]) then
    return 0
end
redis.call('INCRBY', KEYS[1], amount)
redis.call('EXPIREAT', KEYS[1], ARGV[3])
return 1
""")

refund_budget = r.register_script("""
if redis.call('EXISTS', KEYS[1]) == 1 then
    redis.call('DECRBY', KEYS[1], ARGV[1])
end
""")


@dataclass(frozen=True)
class Reservation:
    key: str
    amount: int


def check_budget(input_tokens: int, max_output_tokens: int) -> Reservation:
    """Reserve enough budget for a response before calling the model."""
    now = datetime.now(timezone.utc)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if settings.daily_budget_usd is not None:
        key = f"agent:cost:daily:{now:%Y-%m-%d}"
        end = start_of_day + timedelta(days=1)
        budget = settings.daily_budget_usd
    else:
        key = f"agent:cost:monthly:{now:%Y-%m}"
        end = (start_of_day.replace(day=1) + timedelta(days=32)).replace(day=1)
        budget = settings.monthly_budget_usd

    amount = input_tokens * INPUT_TOKEN_COST + max_output_tokens * OUTPUT_TOKEN_COST
    limit = int((budget * NANO_USD_PER_DOLLAR).to_integral_value(rounding=ROUND_DOWN))
    # Keep the previous period available briefly for requests finishing after midnight.
    expires = int((end + timedelta(days=1)).timestamp())
    if not reserve_budget(keys=[key], args=[amount, limit, expires]):
        raise HTTPException(status_code=402, detail="LLM budget exceeded")
    return Reservation(key, amount)


def record_cost(reservation: Reservation, input_tokens: int, output_tokens: int) -> None:
    actual = input_tokens * INPUT_TOKEN_COST + output_tokens * OUTPUT_TOKEN_COST
    if actual != reservation.amount:
        refund_budget(keys=[reservation.key], args=[reservation.amount - actual])
