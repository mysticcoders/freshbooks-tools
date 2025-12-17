"""FreshBooks API client with automatic token management."""

from typing import Any, Optional

import httpx
from rich.console import Console

from ..auth import ensure_valid_token, refresh_access_token
from ..config import Config, load_account_info, save_account_info, save_tokens

console = Console()


class FreshBooksClient:
    """HTTP client for FreshBooks API with automatic token refresh."""

    BASE_AUTH_URL = "https://api.freshbooks.com/auth/api/v1"
    BASE_ACCOUNTING_URL = "https://api.freshbooks.com/accounting/account"
    BASE_TIMETRACKING_URL = "https://api.freshbooks.com/timetracking/business"
    BASE_COMMENTS_URL = "https://api.freshbooks.com/comments/business"

    def __init__(self, config: Config):
        self.config = config
        self._client: Optional[httpx.Client] = None
        self._account_id: Optional[str] = None
        self._business_id: Optional[int] = None

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

    def _handle_response(self, response: httpx.Response, retry_on_401: bool = True) -> dict[str, Any]:
        """Handle API response with automatic token refresh on 401."""
        if response.status_code == 401 and retry_on_401:
            console.print("[dim]Token expired, refreshing...[/dim]")
            tokens = refresh_access_token(self.config)
            save_tokens(tokens)
            self.config.tokens = tokens
            return None  # Signal to retry

        response.raise_for_status()
        return response.json()

    def get(self, url: str, params: Optional[dict] = None, retry_on_401: bool = True) -> dict[str, Any]:
        """Make authenticated GET request."""
        response = self.client.get(url, headers=self.headers, params=params)
        result = self._handle_response(response, retry_on_401)

        if result is None:
            response = self.client.get(url, headers=self.headers, params=params)
            result = self._handle_response(response, retry_on_401=False)

        return result

    def post(self, url: str, data: Optional[dict] = None, retry_on_401: bool = True) -> dict[str, Any]:
        """Make authenticated POST request."""
        response = self.client.post(url, headers=self.headers, json=data)
        result = self._handle_response(response, retry_on_401)

        if result is None:
            response = self.client.post(url, headers=self.headers, json=data)
            result = self._handle_response(response, retry_on_401=False)

        return result

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

    def comments_url(self, path: str) -> str:
        """Build comments/services API URL."""
        _, business_id = self.ensure_account_info()
        return f"{self.BASE_COMMENTS_URL}/{business_id}/{path}"

    def auth_url(self, path: str) -> str:
        """Build auth API URL."""
        return f"{self.BASE_AUTH_URL}/{path}"
