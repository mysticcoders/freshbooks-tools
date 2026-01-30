"""Unit tests for FreshBooksClient error handling."""

import re
from unittest.mock import patch

import httpx
import pytest

from freshbooks_tools.api.client import FreshBooksClient
from freshbooks_tools.exceptions import (
    APIResponseError,
    AuthenticationError,
    NetworkError,
    RateLimitError,
)


class TestErrorHandling:
    """Tests for FreshBooksClient error response mapping."""

    def test_401_raises_authentication_error(self, httpx_mock, mock_config):
        """Verify 401 response raises AuthenticationError with re-auth hint."""
        httpx_mock.add_response(
            url=re.compile(r".*"),
            status_code=401,
            json={"error": "Unauthorized"},
        )
        httpx_mock.add_response(
            url=re.compile(r".*/auth/oauth/token.*"),
            status_code=401,
            json={"error": "invalid_grant"},
        )

        with FreshBooksClient(mock_config) as client:
            client._account_id = "ABC123"
            client._business_id = 98765

            with pytest.raises(AuthenticationError) as exc_info:
                client.get("https://api.freshbooks.com/test/endpoint")

            assert "re-authenticate" in exc_info.value.format_message().lower()

    def test_429_raises_rate_limit_error(self, httpx_mock, mock_config):
        """Verify 429 response raises RateLimitError with retry_after."""
        httpx_mock.add_response(
            url=re.compile(r".*"),
            status_code=429,
            headers={"Retry-After": "60"},
        )

        with FreshBooksClient(mock_config) as client:
            client._account_id = "ABC123"
            client._business_id = 98765

            with pytest.raises(RateLimitError) as exc_info:
                client.get("https://api.freshbooks.com/test/endpoint")

            assert exc_info.value.retry_after == "60"

    def test_network_error_raises_network_error(self, httpx_mock, mock_config):
        """Verify connection failure raises NetworkError with connectivity hint."""
        httpx_mock.add_exception(
            httpx.ConnectError("Connection refused")
        )

        with FreshBooksClient(mock_config) as client:
            client._account_id = "ABC123"
            client._business_id = 98765

            with pytest.raises(NetworkError) as exc_info:
                client.get("https://api.freshbooks.com/test/endpoint")

            assert "connection" in exc_info.value.format_message().lower()

    def test_500_raises_api_response_error(self, httpx_mock, mock_config):
        """Verify 500 response raises APIResponseError."""
        httpx_mock.add_response(
            url=re.compile(r".*"),
            status_code=500,
            text="Internal Server Error",
        )

        with FreshBooksClient(mock_config) as client:
            client._account_id = "ABC123"
            client._business_id = 98765

            with pytest.raises(APIResponseError) as exc_info:
                client.get("https://api.freshbooks.com/test/endpoint")

            assert "500" in str(exc_info.value)

    def test_timeout_raises_network_error(self, httpx_mock, mock_config):
        """Verify timeout raises NetworkError."""
        httpx_mock.add_exception(
            httpx.TimeoutException("Request timed out")
        )

        with FreshBooksClient(mock_config) as client:
            client._account_id = "ABC123"
            client._business_id = 98765

            with pytest.raises(NetworkError) as exc_info:
                client.get("https://api.freshbooks.com/test/endpoint")

            assert "timed out" in str(exc_info.value).lower()
