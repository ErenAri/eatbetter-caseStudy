import asyncio
import random
from collections.abc import Awaitable, Callable
from typing import TypeVar

from app.application.errors import ApplicationError, RetryableProviderError


T = TypeVar("T")


async def run_with_bounded_retry(
    operation: Callable[[], Awaitable[T]],
    *,
    map_error: Callable[[Exception, int], ApplicationError],
    max_attempts: int,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    jitter: Callable[[float, float], float] = random.uniform,
) -> tuple[T, int]:
    retries = 0
    for attempt in range(1, min(max(max_attempts, 1), 5) + 1):
        try:
            return await operation(), retries
        except Exception as error:
            mapped = map_error(error, retries)
            if not isinstance(mapped, RetryableProviderError) or attempt >= max_attempts:
                if isinstance(mapped.details, dict):
                    mapped.details["retry_count"] = retries
                elif isinstance(mapped, RetryableProviderError):
                    mapped.details = {"retry_count": retries}
                raise mapped from None
            retries += 1
            await sleep(0.25 * (2 ** (attempt - 1)) + jitter(0, 0.1))
    raise AssertionError("unreachable")
