"""FreshBooks API client with automatic token management."""

import time
from typing import Any, Optional
from urllib.parse import urlencode

import httpx
from rich.console import Console

from ..auth import ensure_valid_token, refresh_access_token
from ..config import Config, load_account_info, load_lookup_cache, save_account_info, save_lookup_cache, save_tokens
from ..exceptions import AuthenticationError, RateLimitError, NetworkError, APIResponseError

console = Console(stderr=True)  # stdout carries data (JSON output, MCP protocol)

# shortcut: one TTL for every lookup (names, rates); per-endpoint TTLs if rates change often
LOOKUP_TTL_SECONDS = 24 * 3600


class FreshBooksClient:
    """HTTP client for FreshBooks API with automatic token refresh."""

    BASE_AUTH_URL = "https://api.freshbooks.com/auth/api/v1"
    BASE_ACCOUNTING_URL = "https://api.freshbooks.com/accounting/account"
    BASE_TIMETRACKING_URL = "https://api.freshbooks.com/timetracking/business"
    BASE_PROJECTS_URL = "https://api.freshbooks.com/projects/business"
    BASE_COMMENTS_URL = "https://api.freshbooks.com/comments/business"

    def __init__(self, config: Config):
        self.config = config
        self._client: Optional[httpx.Client] = None
        self._account_id: Optional[str] = None
        self._business_id: Optional[int] = None
        self._lookup_cache: Optional[dict] = None

        saved_account, saved_business = load_account_info()
        self._account_id = saved_account
        self._business_id = saved_business

    @property
    def client(self) -> httpx.Client:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.Client(timeout=30.0)
        return self._client

    @property
    def headers(self) -> dict[str, str]:
        """Get authorization headers."""
        tokens = ensure_valid_token(self.config)
        return {
            "Authorization": f"Bearer {tokens.access_token}",
            "Api-Version": "alpha",
            "Content-Type": "application/json",
        }

    def _handle_response(self, response: httpx.Response) -> dict[str, Any]:
        """Handle API response with proper error mapping."""
        try:
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("API authentication failed") from e
            elif e.response.status_code == 429:
                retry_after = e.response.headers.get("Retry-After")
                raise RateLimitError(retry_after=retry_after) from e
            else:
                raise APIResponseError(f"API error {e.response.status_code}: {e.response.text[:1000]}") from e

    def _make_request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Make HTTP request with network error handling."""
        try:
            if method == "GET":
                return self.client.get(url, headers=self.headers, **kwargs)
            else:
                return self.client.post(url, headers=self.headers, **kwargs)
        except httpx.TimeoutException as e:
            raise NetworkError("Request timed out") from e
        except httpx.ConnectError as e:
            raise NetworkError("Connection failed: unable to reach FreshBooks API") from e
        except httpx.RequestError as e:
            raise NetworkError(f"Network error: {e}") from e

    def get(self, url: str, params: Optional[dict] = None) -> dict[str, Any]:
        """Make authenticated GET request with automatic token refresh on 401."""
        try:
            response = self._make_request("GET", url, params=params)
            return self._handle_response(response)
        except AuthenticationError:
            console.print("[dim]Token expired, refreshing...[/dim]")
            tokens = refresh_access_token(self.config)
            save_tokens(tokens)
            self.config.tokens = tokens
            response = self._make_request("GET", url, params=params)
            return self._handle_response(response)

    def get_cached(self, url: str, params: Optional[dict] = None, refresh: bool = False) -> dict[str, Any]:
        """GET a lookup through the on-disk cache; fetched when missing, older than a day, or refresh=True."""
        key = url + ("?" + urlencode(sorted(params.items())) if params else "")
        if self._lookup_cache is None:
            self._lookup_cache = load_lookup_cache()
        entry = self._lookup_cache.get(key)
        if refresh or entry is None or time.time() - entry["at"] > LOOKUP_TTL_SECONDS:
            entry = {"at": time.time(), "data": self.get(url, params=params)}
            self._lookup_cache[key] = entry
            save_lookup_cache(self._lookup_cache)
        return entry["data"]

    def current_identity_id(self) -> int:
        """Identity id of the logged-in user."""
        return self.get_cached(f"{self.BASE_AUTH_URL}/users/me")["response"]["id"]

    def post(self, url: str, data: Optional[dict] = None) -> dict[str, Any]:
        """Make authenticated POST request with automatic token refresh on 401."""
        try:
            response = self._make_request("POST", url, json=data)
            return self._handle_response(response)
        except AuthenticationError:
            console.print("[dim]Token expired, refreshing...[/dim]")
            tokens = refresh_access_token(self.config)
            save_tokens(tokens)
            self.config.tokens = tokens
            response = self._make_request("POST", url, json=data)
            return self._handle_response(response)

    def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            self._client.close()
            self._client = None

    def __enter__(self) -> "FreshBooksClient":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    async def get_current_user(self) -> dict[str, Any]:
        """Get current user identity and business memberships."""
        url = f"{self.BASE_AUTH_URL}/users/me"
        params = {"include": "business_memberships"}
        return self.get(url, params)

    async def fetch_account_info(self) -> tuple[str, int]:
        """Fetch and cache account_id and business_id."""
        if self._account_id and self._business_id:
            return self._account_id, self._business_id

        response = self.get(f"{self.BASE_AUTH_URL}/users/me")
        user_response = response.get("response", {})

        memberships = user_response.get("business_memberships", [])
        if not memberships:
            raise ValueError("No business memberships found for this user")

        membership = memberships[0]
        business = membership.get("business", {})
        self._account_id = business.get("account_id")
        self._business_id = business.get("id")

        if not self._account_id or not self._business_id:
            raise ValueError("Could not determine account_id or business_id")

        save_account_info(self._account_id, self._business_id)
        return self._account_id, self._business_id

    @property
    def account_id(self) -> str:
        """Get account ID, fetching if necessary."""
        if not self._account_id:
            import asyncio
            asyncio.get_event_loop().run_until_complete(self.fetch_account_info())
        return self._account_id

    @property
    def business_id(self) -> int:
        """Get business ID, fetching if necessary."""
        if not self._business_id:
            import asyncio
            asyncio.get_event_loop().run_until_complete(self.fetch_account_info())
        return self._business_id

    def ensure_account_info(self) -> tuple[str, int]:
        """Ensure account info is loaded synchronously."""
        if not self._account_id or not self._business_id:
            response = self.get(f"{self.BASE_AUTH_URL}/users/me")
            user_response = response.get("response", {})

            memberships = user_response.get("business_memberships", [])
            if not memberships:
                raise ValueError("No business memberships found for this user")

            membership = memberships[0]
            business = membership.get("business", {})
            self._account_id = business.get("account_id")
            self._business_id = business.get("id")

            if not self._account_id or not self._business_id:
                raise ValueError("Could not determine account_id or business_id")

            save_account_info(self._account_id, self._business_id)

        return self._account_id, self._business_id

    def accounting_url(self, path: str) -> str:
        """Build accounting API URL."""
        account_id, _ = self.ensure_account_info()
        return f"{self.BASE_ACCOUNTING_URL}/{account_id}/{path}"

    def timetracking_url(self, path: str) -> str:
        """Build time tracking API URL."""
        _, business_id = self.ensure_account_info()
        return f"{self.BASE_TIMETRACKING_URL}/{business_id}/{path}"

    def projects_url(self, path: str) -> str:
        """Build projects API URL (includes services in response)."""
        _, business_id = self.ensure_account_info()
        return f"{self.BASE_PROJECTS_URL}/{business_id}/{path}"

    def comments_url(self, path: str) -> str:
        """Build comments/services API URL."""
        _, business_id = self.ensure_account_info()
        return f"{self.BASE_COMMENTS_URL}/{business_id}/{path}"

    def auth_url(self, path: str) -> str:
        """Build auth API URL."""
        return f"{self.BASE_AUTH_URL}/{path}"

    def reports_url(self, endpoint: str, use_business_id: bool = False) -> str:
        """
        Build reports endpoint URL.

        Args:
            endpoint: Report path (e.g., 'accounts_aging', 'profit_and_loss')
            use_business_id: If True, use /businesses/{id} pattern
                            If False, use /account/{id}/reports/accounting pattern

        Returns:
            Full URL for the report endpoint
        """
        account_id, business_id = self.ensure_account_info()
        if use_business_id:
            return f"https://api.freshbooks.com/accounting/businesses/{business_id}/reports/{endpoint}"
        return f"https://api.freshbooks.com/accounting/account/{account_id}/reports/accounting/{endpoint}"
