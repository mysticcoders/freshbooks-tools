"""OAuth authentication for FreshBooks API."""

import html
import http.server
import secrets
import socketserver
import threading
import webbrowser
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
from rich.console import Console

from .config import DEFAULT_REDIRECT_URI, RELAY_LOCAL_PORT, Config, Tokens, load_tokens, save_tokens, tokens_lock
from .exceptions import AuthenticationError, NetworkError

console = Console()

AUTH_URL = "https://auth.freshbooks.com/oauth/authorize"
TOKEN_URL = "https://api.freshbooks.com/auth/oauth/token"

SCOPES = [
    "user:profile:read",
    "user:time_entries:read",
    "user:time_entries:write",
    "user:projects:read",
    "user:clients:read",
    "user:billable_items:read",
    "user:invoices:read",
    "user:payments:read",
    "user:teams:read",
    "user:expenses:read",
    "user:reports:read",
    "user:bills:read",
]


class OAuthCallbackHandler(http.server.BaseHTTPRequestHandler):
    """HTTP handler for OAuth callback."""

    authorization_code: Optional[str] = None
    error: Optional[str] = None
    expected_state: Optional[str] = None

    def do_GET(self) -> None:
        """Handle the OAuth callback GET request, rejecting a missing or mismatched state."""
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        state = params.get("state", [None])[0]
        state_ok = (
            OAuthCallbackHandler.expected_state is not None
            and state is not None
            and secrets.compare_digest(state, OAuthCallbackHandler.expected_state)
        )

        if ("code" in params or "error" in params) and not state_ok:
            OAuthCallbackHandler.error = "State mismatch: this callback didn't come from the login fb started"
            self._send_failure()
        elif "code" in params:
            OAuthCallbackHandler.authorization_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            response = b"""
            <html>
            <head><title>FreshBooks CLI - Authorization Successful</title></head>
            <body style="font-family: system-ui; text-align: center; padding: 50px;">
                <h1 style="color: #2ecc71;">Authorization Successful!</h1>
                <p>You can close this window and return to the terminal.</p>
            </body>
            </html>
            """
            self.wfile.write(response)
        elif "error" in params:
            OAuthCallbackHandler.error = params.get("error_description", params["error"])[0]
            self._send_failure()
        else:
            self.send_response(404)
            self.end_headers()

    def _send_failure(self) -> None:
        """Send the failure page, escaping the error text taken from the query string."""
        self.send_response(400)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        response = f"""
            <html>
            <head><title>FreshBooks CLI - Authorization Failed</title></head>
            <body style="font-family: system-ui; text-align: center; padding: 50px;">
                <h1 style="color: #e74c3c;">Authorization Failed</h1>
                <p>{html.escape(OAuthCallbackHandler.error or "")}</p>
            </body>
            </html>
            """.encode()
        self.wfile.write(response)

    def log_message(self, format: str, *args) -> None:
        """Suppress server logging."""
        pass


def get_authorization_url(config: Config, state: str) -> str:
    """Generate the OAuth authorization URL carrying the per-login state value."""
    params = {
        "client_id": config.client_id,
        "response_type": "code",
        "redirect_uri": config.redirect_uri,
        "scope": " ".join(SCOPES),
        "state": state,
    }
    return f"{AUTH_URL}?{urlencode(params)}"


def exchange_code_for_tokens(config: Config, code: str) -> Tokens:
    """Exchange authorization code for access and refresh tokens."""
    data = {
        "grant_type": "authorization_code",
        "client_id": config.client_id,
        "client_secret": config.client_secret,
        "code": code,
        "redirect_uri": config.redirect_uri,
    }

    try:
        with httpx.Client() as client:
            response = client.post(TOKEN_URL, data=data, timeout=30.0)
            response.raise_for_status()
            token_data = response.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            raise AuthenticationError("Authorization code invalid or expired") from e
        raise AuthenticationError(f"Token exchange failed: HTTP {e.response.status_code}") from e
    except httpx.TimeoutException as e:
        raise NetworkError("Token exchange timed out") from e
    except httpx.RequestError as e:
        raise NetworkError(f"Network error during token exchange: {e}") from e

    expires_at = None
    if "expires_in" in token_data:
        expires_at = datetime.now() + timedelta(seconds=token_data["expires_in"])

    return Tokens(
        access_token=token_data["access_token"],
        refresh_token=token_data["refresh_token"],
        token_type=token_data.get("token_type", "Bearer"),
        expires_at=expires_at,
    )


def refresh_access_token(config: Config) -> Tokens:
    """Refresh the access token using the refresh token."""
    if not config.tokens or not config.tokens.refresh_token:
        raise AuthenticationError("No refresh token available")

    data = {
        "grant_type": "refresh_token",
        "client_id": config.client_id,
        "client_secret": config.client_secret,
        "refresh_token": config.tokens.refresh_token,
    }

    try:
        with httpx.Client() as client:
            response = client.post(TOKEN_URL, data=data, timeout=30.0)
            response.raise_for_status()
            token_data = response.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            raise AuthenticationError("Refresh token expired or invalid") from e
        raise AuthenticationError(f"Token refresh failed: HTTP {e.response.status_code}") from e
    except httpx.TimeoutException as e:
        raise NetworkError("Token refresh timed out") from e
    except httpx.RequestError as e:
        raise NetworkError(f"Network error during token refresh: {e}") from e

    expires_at = None
    if "expires_in" in token_data:
        expires_at = datetime.now() + timedelta(seconds=token_data["expires_in"])

    return Tokens(
        access_token=token_data["access_token"],
        refresh_token=token_data["refresh_token"],
        token_type=token_data.get("token_type", "Bearer"),
        expires_at=expires_at,
    )


def start_oauth_flow(config: Config, local_port: int = RELAY_LOCAL_PORT) -> Tokens:
    """Start the OAuth flow with a local callback server.

    Args:
        config: Application configuration
        local_port: Local port to listen on (default 8374).
                   The hosted relay always forwards to 8374; with ngrok or
                   another tunnel, this must match the port it forwards to.
    """
    import os

    OAuthCallbackHandler.authorization_code = None
    OAuthCallbackHandler.error = None
    state = secrets.token_urlsafe(32)
    OAuthCallbackHandler.expected_state = state

    port = int(os.getenv("FRESHBOOKS_LOCAL_PORT", str(local_port)))

    if config.redirect_uri == DEFAULT_REDIRECT_URI and port != RELAY_LOCAL_PORT:
        raise ValueError(
            f"The hosted relay ({DEFAULT_REDIRECT_URI}) only forwards to port {RELAY_LOCAL_PORT}, "
            f"but FRESHBOOKS_LOCAL_PORT is {port}. Unset FRESHBOOKS_LOCAL_PORT, or set "
            "FRESHBOOKS_REDIRECT_URI to a tunnel that forwards to that port."
        )

    parsed = urlparse(config.redirect_uri)
    is_ngrok = "ngrok" in parsed.netloc

    if is_ngrok:
        console.print(f"[cyan]Using ngrok redirect:[/cyan] {config.redirect_uri}")
        console.print(f"[cyan]Local server listening on port:[/cyan] {port}")
        console.print()
        console.print("[yellow]Make sure ngrok is running:[/yellow]")
        console.print(f"  ngrok http {port}")
        console.print()

    socketserver.TCPServer.allow_reuse_address = True
    server = socketserver.TCPServer(("127.0.0.1", port), OAuthCallbackHandler)
    server.timeout = 120

    server_thread = threading.Thread(target=server.handle_request)
    server_thread.start()

    auth_url = get_authorization_url(config, state)
    console.print(f"\n[bold]Opening browser for authorization...[/bold]")
    console.print(f"If the browser doesn't open, visit:\n[link={auth_url}]{auth_url}[/link]\n")
    webbrowser.open(auth_url)

    server_thread.join(timeout=120)
    server.server_close()

    if OAuthCallbackHandler.error:
        raise ValueError(f"Authorization failed: {OAuthCallbackHandler.error}")

    if not OAuthCallbackHandler.authorization_code:
        raise ValueError("Authorization timed out or was cancelled")

    console.print("[bold green]Authorization code received![/bold green]")
    console.print("Exchanging for tokens...")

    tokens = exchange_code_for_tokens(config, OAuthCallbackHandler.authorization_code)
    save_tokens(tokens)

    console.print("[bold green]Successfully authenticated![/bold green]")
    return tokens


def ensure_valid_token(config: Config) -> Tokens:
    """Ensure we have a valid access token, refreshing if needed."""
    if not config.tokens:
        raise AuthenticationError("Not authenticated. Run 'fb auth login' first.")

    if config.tokens.is_expired:
        console.print("[dim]Access token expired, refreshing...[/dim]")
        return refresh_tokens_locked(config)

    return config.tokens


def refresh_tokens_locked(config: Config) -> Tokens:
    """Refresh tokens under the inter-process lock, and save them.

    Inside the lock, re-reads tokens.json first. If another process has
    already replaced the access token this process holds, and the new one is
    still valid, uses it instead of refreshing again. Otherwise refreshes with
    the newest refresh token on disk, since FreshBooks invalidates a refresh
    token once it has been used.
    """
    stale_access_token = config.tokens.access_token if config.tokens else None
    with tokens_lock():
        current = load_tokens()
        if current and current.access_token != stale_access_token and not current.is_expired:
            config.tokens = current
            return current
        if current:
            config.tokens = current
        tokens = refresh_access_token(config)
        save_tokens(tokens)
        config.tokens = tokens
        return tokens
