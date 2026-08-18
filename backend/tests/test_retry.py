import pytest

from app.application.errors import PermanentProviderError, RetryableProviderError
from app.application.retry import with_retry


@pytest.mark.asyncio
async def test_transient_failures_retry_then_succeed():
    calls = 0

    async def operation():
        nonlocal calls
        calls += 1
        if calls < 3:
            raise RetryableProviderError("temporary")
        return "ok"

    value, retries = await with_retry(operation, max_attempts=3, base_delay_seconds=0)
    assert value == "ok"
    assert retries == 2


@pytest.mark.asyncio
async def test_deterministic_failure_is_not_retried():
    calls = 0

    async def operation():
        nonlocal calls
        calls += 1
        raise PermanentProviderError("bad input")

    with pytest.raises(PermanentProviderError):
        await with_retry(operation, max_attempts=3, base_delay_seconds=0)
    assert calls == 1
