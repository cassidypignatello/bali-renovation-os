"""
Resilience patterns for external API integration.

Provides circuit breaker, retry logic, and timeout handling
for OpenAI, Apify, and other external services.
"""

import asyncio
import time
from collections import defaultdict
from functools import wraps
from typing import Any, Callable

from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import get_settings

settings = get_settings()


class CircuitBreaker:
    """
    Circuit breaker for external service calls.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Service failing, requests fail fast
    - HALF_OPEN: Testing if service recovered

    Transitions:
    - CLOSED → OPEN: After {failure_threshold} failures
    - OPEN → HALF_OPEN: After {timeout} seconds
    - HALF_OPEN → CLOSED: After successful call
    - HALF_OPEN → OPEN: On any failure
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        timeout: int = 60,
        expected_exception: type[Exception] = Exception,
    ):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            timeout: Seconds to wait before half-open attempt
            expected_exception: Exception type to track
        """
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.expected_exception = expected_exception

        self._failure_count = 0
        self._last_failure_time = 0
        self._state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    def call(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """
        Execute function with circuit breaker protection.

        Args:
            func: Function to call
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Function result

        Raises:
            CircuitBreakerError: If circuit is open
            Exception: Original exception if circuit allows call
        """
        if self._state == "OPEN":
            if time.time() - self._last_failure_time > self.timeout:
                self._state = "HALF_OPEN"
                self._failure_count = 0
            else:
                raise CircuitBreakerError(
                    f"Circuit breaker is OPEN. Last failure: {self._last_failure_time}"
                )

        try:
            result = func(*args, **kwargs)
            if self._state == "HALF_OPEN":
                self._state = "CLOSED"
                self._failure_count = 0
            return result

        except self.expected_exception as e:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._failure_count >= self.failure_threshold:
                self._state = "OPEN"

            raise e

    async def call_async(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """
        Execute async function with circuit breaker protection.

        Args:
            func: Async function to call
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Function result

        Raises:
            CircuitBreakerError: If circuit is open
            Exception: Original exception if circuit allows call
        """
        if self._state == "OPEN":
            if time.time() - self._last_failure_time > self.timeout:
                self._state = "HALF_OPEN"
                self._failure_count = 0
            else:
                raise CircuitBreakerError(
                    f"Circuit breaker is OPEN. Last failure: {self._last_failure_time}"
                )

        try:
            result = await func(*args, **kwargs)
            if self._state == "HALF_OPEN":
                self._state = "CLOSED"
                self._failure_count = 0
            return result

        except self.expected_exception as e:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._failure_count >= self.failure_threshold:
                self._state = "OPEN"

            raise e

    @property
    def state(self) -> str:
        """Get current circuit breaker state."""
        return self._state


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open."""

    pass


# Global circuit breakers for external services
_circuit_breakers: dict[str, CircuitBreaker] = defaultdict(
    lambda: CircuitBreaker(failure_threshold=5, timeout=60)
)


def with_circuit_breaker(service_name: str):
    """
    Decorator to add circuit breaker protection to async functions.

    Usage:
        @with_circuit_breaker("openai")
        async def generate_bom(...):
            ...

    Args:
        service_name: Unique identifier for the service
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            circuit_breaker = _circuit_breakers[service_name]
            return await circuit_breaker.call_async(func, *args, **kwargs)

        return wrapper

    return decorator


def with_retry(
    max_attempts: int = 3,
    min_wait: int = 1,
    max_wait: int = 10,
    exceptions: tuple[type[Exception], ...] = (Exception,),
):
    """
    Decorator to add exponential backoff retry logic to async functions.

    Usage:
        @with_retry(max_attempts=3, min_wait=1, max_wait=10)
        async def scrape_prices(...):
            ...

    Args:
        max_attempts: Maximum number of retry attempts
        min_wait: Minimum wait time in seconds
        max_wait: Maximum wait time in seconds
        exceptions: Tuple of exception types to retry on
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(max_attempts),
                wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
                retry=retry_if_exception_type(exceptions),
                reraise=True,
            ):
                with attempt:
                    return await func(*args, **kwargs)

        return wrapper

    return decorator


async def with_timeout(coro: Any, timeout: float) -> Any:
    """
    Execute coroutine with timeout.

    Args:
        coro: Coroutine to execute
        timeout: Timeout in seconds

    Returns:
        Coroutine result

    Raises:
        asyncio.TimeoutError: If timeout exceeded
    """
    return await asyncio.wait_for(coro, timeout=timeout)


# Service-specific retry configurations
OPENAI_RETRY_CONFIG = {
    "max_attempts": 3,
    "min_wait": 2,
    "max_wait": 10,
    "exceptions": (Exception,),  # Catch all for OpenAI API errors
}

APIFY_RETRY_CONFIG = {
    "max_attempts": 3,
    "min_wait": 1,
    "max_wait": 8,
    "exceptions": (Exception,),  # Catch all for Apify API errors
}

SUPABASE_RETRY_CONFIG = {
    "max_attempts": 3,
    "min_wait": 1,
    "max_wait": 5,
    "exceptions": (Exception,),  # Catch all for database errors
}
