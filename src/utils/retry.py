"""
Retry utilities with exponential backoff and rate limiting.
"""
import time
import functools
import logging
from typing import Callable, TypeVar, Any

logger = logging.getLogger(__name__)

T = TypeVar('T')


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exceptions: tuple = (Exception,),
    on_retry: Callable[[Exception, int], None] = None
):
    """
    Decorator for retrying functions with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay between retries (seconds)
        max_delay: Maximum delay between retries (seconds)
        exceptions: Tuple of exceptions to catch and retry
        on_retry: Optional callback function(exception, attempt) called on each retry

    Usage:
        @retry_with_backoff(max_retries=3, base_delay=1.0)
        def api_call():
            return requests.get(url)
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt == max_retries:
                        logger.error(f"[Retry] {func.__name__} failed after {max_retries + 1} attempts: {e}")
                        raise

                    # Exponential backoff: delay = base_delay * 2^attempt
                    delay = min(base_delay * (2 ** attempt), max_delay)

                    logger.warning(
                        f"[Retry] {func.__name__} attempt {attempt + 1}/{max_retries + 1} failed: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )

                    if on_retry:
                        on_retry(e, attempt + 1)

                    time.sleep(delay)

            # Should never reach here, but just in case
            if last_exception:
                raise last_exception

        return wrapper
    return decorator


class RateLimiter:
    """
    Simple rate limiter using token bucket algorithm.

    Usage:
        limiter = RateLimiter(calls_per_minute=60)

        for item in items:
            limiter.wait()  # Blocks if rate limit exceeded
            api_call(item)
    """

    def __init__(self, calls_per_minute: int = 60, calls_per_second: float = None):
        """
        Args:
            calls_per_minute: Maximum calls allowed per minute
            calls_per_second: Override with calls per second (takes precedence)
        """
        if calls_per_second:
            self.min_interval = 1.0 / calls_per_second
        else:
            self.min_interval = 60.0 / calls_per_minute

        self.last_call_time = 0.0
        self._call_count = 0

    def wait(self):
        """Wait if necessary to respect rate limit."""
        now = time.time()
        elapsed = now - self.last_call_time

        if elapsed < self.min_interval:
            sleep_time = self.min_interval - elapsed
            logger.debug(f"[RateLimiter] Sleeping {sleep_time:.2f}s to respect rate limit")
            time.sleep(sleep_time)

        self.last_call_time = time.time()
        self._call_count += 1

    def reset(self):
        """Reset the rate limiter state."""
        self.last_call_time = 0.0
        self._call_count = 0

    @property
    def call_count(self) -> int:
        """Number of calls made since creation or last reset."""
        return self._call_count


# Pre-configured rate limiters for common APIs
class APIRateLimiters:
    """Pre-configured rate limiters for external APIs."""

    # ElevenLabs: ~100 requests/min on paid plans, be conservative
    elevenlabs = RateLimiter(calls_per_minute=30)

    # Pexels: 200 requests/hour = ~3.3/min, be safe
    pexels = RateLimiter(calls_per_minute=3)

    # Pixabay: 100 requests/min
    pixabay = RateLimiter(calls_per_minute=50)

    # Gemini: 60 requests/min on free tier
    gemini = RateLimiter(calls_per_minute=30)

    # Tavily: Depends on plan, be conservative
    tavily = RateLimiter(calls_per_minute=20)
