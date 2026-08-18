import asyncio
import random
from collections.abc import Awaitable, Callable
from typing import TypeVar

from .errors import RetryableProviderError

T = TypeVar("T")


async def with_retry(
    operation: Callable[[], Awaitable[T]],
    *,
    max_attempts: int = 3,
    base_delay_seconds: float = 0.05,
) -> tuple[T, int]:
    retries = 0
    for attempt in range(max_attempts):
        try:
            return await operation(), retries
        except RetryableProviderError:
            if attempt == max_attempts - 1:
                raise
            retries += 1
            delay = base_delay_seconds * (2**attempt) + random.uniform(0, base_delay_seconds)
            await asyncio.sleep(delay)
    raise AssertionError("unreachable")
