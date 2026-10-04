import time
from collections import defaultdict
from app.core.config import settings
from app.core.exceptions import AppException

# Sliding window request timestamps per key
_rate_limit_store: dict[str, list[float]] = defaultdict(list)


def check_rate_limit(key: str, limit: int | None = None, window_seconds: int = 60) -> None:
    max_limit = limit if limit is not None else settings.RATE_LIMIT_LOGIN_PER_MINUTE
    now = time.time()
    cutoff = now - window_seconds

    # Filter out timestamps outside window
    timestamps = _rate_limit_store[key]
    valid_timestamps = [ts for ts in timestamps if ts > cutoff]
    _rate_limit_store[key] = valid_timestamps

    if len(valid_timestamps) >= max_limit:
        raise AppException(
            code="RATE_LIMIT_EXCEEDED",
            message=f"Rate limit exceeded. Maximum {max_limit} requests allowed per {window_seconds} seconds.",
            status_code=429,
        )

    _rate_limit_store[key].append(now)


def reset_rate_limit_store() -> None:
    """Utility to clear rate limit store for testing."""
    _rate_limit_store.clear()
