from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

from openai import APITimeoutError, OpenAI, RateLimitError

from backend.app.settings import Settings

T = TypeVar("T")


def create_openai_client(settings: Settings) -> OpenAI:
    return OpenAI(
        api_key=settings.openai_api_key,
        timeout=settings.openai_timeout_seconds,
        max_retries=0,
    )


def with_retry(operation: Callable[[], T], settings: Settings, op_name: str) -> T:
    attempts = max(1, settings.openai_max_retries + 1)
    delay = 0.5
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return operation()
        except (APITimeoutError, RateLimitError) as exc:
            last_error = exc
            if attempt == attempts:
                break
            time.sleep(delay)
            delay *= 2
        except Exception:
            raise
    raise RuntimeError(f"{op_name} failed after {attempts} attempts: {last_error}")
