"""Tests for open_notebook.utils.error_classifier."""

import pytest

from open_notebook.exceptions import (
    AuthenticationError,
    ConfigurationError,
    ExternalServiceError,
    NetworkError,
    RateLimitError,
)
from open_notebook.utils.error_classifier import _truncate, classify_error


# ---------------------------------------------------------------------------
# _truncate
# ---------------------------------------------------------------------------
class TestTruncate:
    def test_short_text_unchanged(self):
        assert _truncate("short", 100) == "short"

    def test_exact_length_unchanged(self):
        assert _truncate("1234567890", 10) == "1234567890"

    def test_long_text_truncated(self):
        result = _truncate("x" * 250, 200)
        assert len(result) == 203  # 200 + "..."
        assert result.endswith("...")

    def test_default_max_length_200(self):
        result = _truncate("x" * 300)
        assert len(result) == 203


# ---------------------------------------------------------------------------
# classify_error – regression for existing rules
# ---------------------------------------------------------------------------
class TestClassifyErrorRegression:
    def test_authentication_401(self):
        cls, msg = classify_error(Exception("HTTP 401 Unauthorized"))
        assert cls is AuthenticationError
        assert "API key" in msg

    def test_invalid_api_key(self):
        cls, msg = classify_error(Exception("invalid_api_key provided"))
        assert cls is AuthenticationError

    def test_rate_limit_429(self):
        cls, msg = classify_error(Exception("Error 429 Too Many Requests"))
        assert cls is RateLimitError
        assert "Rate limit" in msg

    def test_model_not_found_passthrough(self):
        exc = Exception("model not found: gpt-9")
        cls, msg = classify_error(exc)
        assert cls is ConfigurationError
        assert "gpt-9" in msg  # passed through

    def test_network_connection_refused(self):
        cls, msg = classify_error(ConnectionError("connection refused"))
        assert cls is NetworkError
        assert "network" in msg.lower()

    def test_context_length(self):
        cls, msg = classify_error(Exception("context_length_exceeded"))
        assert cls is ExternalServiceError
        assert "too large" in msg.lower()

    def test_payload_too_large(self):
        cls, msg = classify_error(Exception("413 Request Entity Too Large"))
        assert cls is ExternalServiceError
        assert "payload" in msg.lower()

    def test_service_unavailable_503(self):
        cls, msg = classify_error(Exception("503 Service Unavailable"))
        assert cls is ExternalServiceError
        assert "temporarily unavailable" in msg


# ---------------------------------------------------------------------------
# classify_error – new rules (added in bugfix/user_feedback_0529)
# ---------------------------------------------------------------------------
class TestClassifyErrorNewRules:
    def test_timeout_request_timed_out(self):
        cls, msg = classify_error(Exception("request timed out after 30s"))
        assert cls is ExternalServiceError
        assert "took too long" in msg

    def test_timeout_timed_out_waiting(self):
        cls, msg = classify_error(Exception("timed out waiting for response"))
        assert cls is ExternalServiceError
        assert "took too long" in msg

    def test_timeout_operation_timed_out(self):
        cls, msg = classify_error(Exception("operation timed out"))
        assert cls is ExternalServiceError
        assert "took too long" in msg

    def test_unsupported_passthrough(self):
        exc = Exception("this model does not support pdf input")
        cls, msg = classify_error(exc)
        assert cls is ExternalServiceError
        assert "does not support pdf input" in msg

    def test_unsupported_passthrough_case_insensitive(self):
        exc = Exception("This Model Does Not Support Vision")
        cls, msg = classify_error(exc)
        assert cls is ExternalServiceError
        assert "Does Not Support Vision" in msg

    def test_bad_request_400_passthrough(self):
        exc = Exception("400 bad request: invalid parameters")
        cls, msg = classify_error(exc)
        assert cls is ExternalServiceError
        assert "invalid parameters" in msg


# ---------------------------------------------------------------------------
# classify_error – unclassified fallback
# ---------------------------------------------------------------------------
class TestClassifyErrorUnclassified:
    def test_unclassified_error_returns_external_service(self):
        cls, msg = classify_error(Exception("some_weird_provider_error"))
        assert cls is ExternalServiceError
        assert "unexpected error" in msg

    def test_unclassified_error_includes_raw_message(self):
        cls, msg = classify_error(Exception("unknown_provider_specific_bug_xyz"))
        assert cls is ExternalServiceError
        assert "unknown_provider_specific_bug_xyz" in msg

    def test_unclassified_long_message_truncated_to_300(self):
        exc = Exception("x" * 500)
        cls, msg = classify_error(exc)
        assert cls is ExternalServiceError
        # prefix "AI provider returned an unexpected error: " (46) + _truncate(300) + "..." = up to 349
        assert len(msg) <= 350

    def test_unclassified_type_name_used_in_matching(self):
        # The classifier combines type_name + error_str for matching
        class CustomNetworkError(Exception):
            pass

        cls, msg = classify_error(CustomNetworkError("connection error"))
        assert cls is NetworkError


# ---------------------------------------------------------------------------
# classify_error – edge cases
# ---------------------------------------------------------------------------
class TestClassifyErrorEdgeCases:
    def test_empty_error_message(self):
        cls, msg = classify_error(Exception(""))
        assert cls is ExternalServiceError

    def test_first_match_wins_order_matters(self):
        # "timed out waiting" (new timeout rule) is listed before "timed out" (network rule)
        # So "timed out waiting for backend" → ExternalServiceError, not NetworkError
        exc = Exception("timed out waiting for backend")
        cls, msg = classify_error(exc)
        assert cls is ExternalServiceError
        assert "took too long" in msg

    def test_network_timed_out_still_matches_generic(self):
        # Generic "connection timed out" still matches network rule (not the specific request timeout rule)
        exc = Exception("connection timed out")
        cls, msg = classify_error(exc)
        assert cls is NetworkError
        assert "network" in msg.lower()
