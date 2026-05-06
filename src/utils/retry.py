"""
Retry utilities with exponential backoff and rate limiting.
"""
import time
import random
import functools
import logging
from typing import Callable, TypeVar, Any, Optional

logger = logging.getLogger(__name__)

# ── Gemini error classification ─────────────────────────────────────────────

_GEMINI_TRANSIENT = (
    "503", "500", "unavailable", "overloaded", "internal",
    "deadline", "timeout", "temporarily", "service_unavailable",
    "try again later", "resource temporarily", "backend error",
    "server error",
)

_GEMINI_QUOTA = (
    "429", "resource_exhausted", "quota", "credits exhausted",
    "rate limit", "ratelimitexceeded", "daily limit",
)


def is_gemini_transient(err: Exception) -> bool:
    """Return True if this is a temporary/transient Gemini error worth retrying."""
    s = str(err).lower()
    return any(k in s for k in _GEMINI_TRANSIENT)


def is_gemini_quota(err: Exception) -> bool:
    """Return True if this is a quota/credits-exhausted error (try next model)."""
    s = str(err).lower()
    return any(k in s for k in _GEMINI_QUOTA)


def gemini_generate_with_retry(
    client,
    model: str,
    contents,
    config: Optional[dict] = None,
    max_transient_retries: int = 3,
    base_delay: float = 5.0,
    max_delay: float = 60.0,
):
    """
    Call client.models.generate_content with automatic retry for transient errors.

    Behaviour:
    - Transient error (503, overloaded, …): retry same model with exponential
      backoff + jitter, up to max_transient_retries times, then re-raise.
    - Quota/credits error (429, resource_exhausted, …): raise immediately so
      the caller can move to the next model.
    - Any other error: raise immediately (non-retryable).

    Args:
        client:               google.genai.Client instance
        model:                model name string, e.g. "gemini-2.0-flash"
        contents:             prompt string or list
        config:               optional dict passed as `config=` kwarg
        max_transient_retries: how many extra attempts on transient errors
        base_delay:           initial backoff in seconds
        max_delay:            cap on backoff in seconds

    Returns:
        The raw response object from generate_content.

    Raises:
        The last exception when all retries are exhausted or error is not
        retryable.
    """
    last_err: Optional[Exception] = None
    for attempt in range(max_transient_retries + 1):
        try:
            kwargs: dict = {"model": model, "contents": contents}
            if config:
                kwargs["config"] = config
            return client.models.generate_content(**kwargs)
        except Exception as e:
            last_err = e
            if is_gemini_quota(e):
                # Quota exhausted — no point retrying same model
                raise
            if is_gemini_transient(e):
                if attempt < max_transient_retries:
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    jitter = random.uniform(0, delay * 0.25)
                    wait = delay + jitter
                    logger.warning(
                        f"[Gemini] {model} transient error "
                        f"(attempt {attempt + 1}/{max_transient_retries + 1}): "
                        f"{str(e)[:100]}. Retrying in {wait:.1f}s…"
                    )
                    time.sleep(wait)
                    continue
                # All transient retries exhausted
                logger.error(
                    f"[Gemini] {model} still failing after "
                    f"{max_transient_retries + 1} attempts. Giving up on this model."
                )
                raise
            # Non-retryable (400 bad request, 404 not found, …) — raise immediately
            raise
    raise last_err  # unreachable, but satisfies type checkers

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
