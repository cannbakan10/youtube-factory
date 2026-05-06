"""
Unit tests for Gemini retry/fallback helpers in src/utils/retry.py
"""
import pytest
from src.utils.retry import is_gemini_transient, is_gemini_quota


# ── is_gemini_transient ──────────────────────────────────────────────────────

@pytest.mark.parametrize("msg", [
    "503 Service Unavailable",
    "500 Internal Server Error",
    "The model is currently overloaded",
    "Deadline exceeded",
    "Request timeout",
    "Service temporarily unavailable",
    "Backend error",
    "Please try again later",
    "resource temporarily unavailable",
])
def test_transient_detected(msg):
    assert is_gemini_transient(Exception(msg)), f"Should be transient: {msg!r}"


@pytest.mark.parametrize("msg", [
    "400 INVALID_ARGUMENT",
    "404 NOT_FOUND: models/gemini-1.5-flash not found",
    "API key not valid",
    "Permission denied",
])
def test_transient_not_detected_for_non_transient(msg):
    assert not is_gemini_transient(Exception(msg)), f"Should NOT be transient: {msg!r}"


# ── is_gemini_quota ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("msg", [
    "429 Too Many Requests",
    "RESOURCE_EXHAUSTED: quota exceeded",
    "Gemini credits exhausted",
    "Daily limit reached",
    "rateLimitExceeded",
    "rate limit",
])
def test_quota_detected(msg):
    assert is_gemini_quota(Exception(msg)), f"Should be quota: {msg!r}"


@pytest.mark.parametrize("msg", [
    "503 Service Unavailable",
    "400 INVALID_ARGUMENT",
    "404 NOT_FOUND",
])
def test_quota_not_detected_for_non_quota(msg):
    assert not is_gemini_quota(Exception(msg)), f"Should NOT be quota: {msg!r}"


# ── mutual exclusivity for common cases ─────────────────────────────────────

def test_503_is_transient_not_quota():
    e = Exception("503 UNAVAILABLE")
    assert is_gemini_transient(e)
    assert not is_gemini_quota(e)


def test_429_is_quota_not_transient():
    e = Exception("429 RESOURCE_EXHAUSTED quota exceeded")
    assert is_gemini_quota(e)
    assert not is_gemini_transient(e)
