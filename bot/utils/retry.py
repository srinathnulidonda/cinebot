# bot/utils/retry.py
import asyncio
import logging
from functools import wraps

logger = logging.getLogger(__name__)

TRANSIENT_ERRORS = (
    ConnectionResetError,
    ConnectionRefusedError,
    ConnectionAbortedError,
    OSError,
    TimeoutError,
)


def db_retry(attempts: int = 3, delay: float = 2.0):
    """
    Retry decorator for async functions that touch the database.

    On transient connection errors (DB sleeping / network blip),
    waits with exponential back-off and retries the *entire* function,
    which means a fresh session + fresh connection each attempt.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_err = None
            for attempt in range(1, attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except TRANSIENT_ERRORS as exc:
                    last_err = exc
                    if attempt < attempts:
                        wait = delay * (2 ** (attempt - 1))   # 2s → 4s → 8s
                        logger.warning(
                            "⚠️ %s attempt %d/%d failed: %s — retrying in %.0fs",
                            func.__name__, attempt, attempts, exc, wait,
                        )
                        await asyncio.sleep(wait)
                    else:
                        logger.error(
                            "❌ %s failed after %d attempts: %s",
                            func.__name__, attempts, exc,
                        )
            raise last_err
        return wrapper
    return decorator