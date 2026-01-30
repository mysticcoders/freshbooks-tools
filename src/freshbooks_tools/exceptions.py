"""Custom exception hierarchy for FreshBooks CLI."""

from typing import Optional

import click
from rich.console import Console


class FreshBooksError(click.ClickException):
    """Base exception for all FreshBooks CLI errors."""

    exit_code = 1

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message

    def show(self, file=None) -> None:
        """Display error with Rich formatting."""
        console = Console(stderr=True)
        console.print(f"[red]Error:[/red] {self.format_message()}")

    def format_message(self) -> str:
        """Override in subclasses for custom formatting."""
        return self.message


class AuthenticationError(FreshBooksError):
    """OAuth authentication failed or token invalid."""

    def format_message(self) -> str:
        return f"{self.message}\n\nRun 'fb auth login' to re-authenticate."


class RateLimitError(FreshBooksError):
    """API rate limit exceeded."""

    def __init__(self, message: str = "Rate limit exceeded. Please try again later.", retry_after: Optional[str] = None):
        super().__init__(message)
        self.retry_after = retry_after

    def format_message(self) -> str:
        if self.retry_after:
            return f"Rate limit exceeded. Retry after {self.retry_after} seconds."
        return self.message


class NetworkError(FreshBooksError):
    """Network connectivity issue."""

    def format_message(self) -> str:
        return f"{self.message}\n\nCheck your internet connection and try again."


class APIResponseError(FreshBooksError):
    """API returned unexpected response format."""

    pass
