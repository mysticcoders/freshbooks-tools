"""Configuration management for FreshBooks CLI tools."""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Optional

import yaml
from dotenv import load_dotenv
from platformdirs import user_config_dir

APP_NAME = "freshbooks-tools"
CONFIG_DIR = Path(user_config_dir(APP_NAME))
TOKENS_FILE = CONFIG_DIR / "tokens.json"
RATES_FILE = CONFIG_DIR / "rates.yaml"


@dataclass
class Tokens:
    """OAuth tokens with expiration tracking."""

    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)

    @property
    def is_expired(self) -> bool:
        """Check if access token is expired."""
        if self.expires_at is None:
            return False
        return datetime.now() >= self.expires_at

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "token_type": self.token_type,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Tokens":
        """Create from dictionary."""
        expires_at = None
        if data.get("expires_at"):
            expires_at = datetime.fromisoformat(data["expires_at"])
        created_at = datetime.now()
        if data.get("created_at"):
            created_at = datetime.fromisoformat(data["created_at"])
        return cls(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            token_type=data.get("token_type", "Bearer"),
            expires_at=expires_at,
            created_at=created_at,
        )


@dataclass
class RatesConfig:
    """Configuration for cost and billable rates.

    Rates can be keyed by email OR identity_id (as string).
    """

    cost_rates: dict[str, Decimal] = field(default_factory=dict)
    billable_rates: dict[str, Decimal] = field(default_factory=dict)
    default_cost_rate: Optional[Decimal] = None
    default_billable_rate: Optional[Decimal] = None
    members: dict[int, dict] = field(default_factory=dict)

    def get_cost_rate(self, email: str) -> Optional[Decimal]:
        """Get cost rate for a team member by email."""
        return self.cost_rates.get(email, self.default_cost_rate)

    def get_cost_rate_by_id(self, identity_id: int) -> Optional[Decimal]:
        """Get cost rate for a team member by identity_id."""
        if identity_id in self.members:
            return self.members[identity_id].get("cost_rate")
        str_id = str(identity_id)
        if str_id in self.cost_rates:
            return self.cost_rates[str_id]
        return self.default_cost_rate

    def get_billable_rate(self, email: str) -> Optional[Decimal]:
        """Get billable rate for a team member by email."""
        return self.billable_rates.get(email, self.default_billable_rate)

    def get_billable_rate_by_id(self, identity_id: int) -> Optional[Decimal]:
        """Get billable rate override for a team member by identity_id."""
        if identity_id in self.members:
            return self.members[identity_id].get("billable_rate")
        str_id = str(identity_id)
        if str_id in self.billable_rates:
            return self.billable_rates[str_id]
        return None


@dataclass
class Config:
    """Application configuration."""

    client_id: str
    client_secret: str
    redirect_uri: str = "http://localhost:8374/callback"
    tokens: Optional[Tokens] = None
    rates: RatesConfig = field(default_factory=RatesConfig)
    account_id: Optional[str] = None
    business_id: Optional[int] = None


def ensure_config_dir() -> None:
    """Ensure the configuration directory exists."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_env_config() -> tuple[str, str, str]:
    """Load client credentials and redirect URI from .env file."""
    load_dotenv()

    client_id = os.getenv("FRESHBOOKS_CLIENT_ID")
    client_secret = os.getenv("FRESHBOOKS_CLIENT_SECRET")
    redirect_uri = os.getenv("FRESHBOOKS_REDIRECT_URI", "http://localhost:8374/callback")

    if not client_id or not client_secret:
        raise ValueError(
            "Missing FRESHBOOKS_CLIENT_ID or FRESHBOOKS_CLIENT_SECRET in .env file"
        )

    return client_id, client_secret, redirect_uri


def load_tokens() -> Optional[Tokens]:
    """Load stored tokens from config directory."""
    if not TOKENS_FILE.exists():
        return None

    try:
        with open(TOKENS_FILE) as f:
            data = json.load(f)
        return Tokens.from_dict(data)
    except (json.JSONDecodeError, KeyError):
        return None


def save_tokens(tokens: Tokens) -> None:
    """Save tokens to config directory."""
    ensure_config_dir()
    with open(TOKENS_FILE, "w") as f:
        json.dump(tokens.to_dict(), f, indent=2)


def delete_tokens() -> None:
    """Remove stored tokens."""
    if TOKENS_FILE.exists():
        TOKENS_FILE.unlink()


def load_rates_config() -> RatesConfig:
    """Load rates configuration from YAML file.

    The YAML file can have the following structure:
    ```yaml
    default_cost_rate: 50.00
    default_billable_rate: 150.00

    # Rates by email
    cost_rates:
      "john@example.com": 50.00
    billable_rates:
      "john@example.com": 150.00

    # Rates by identity_id with names for reference
    members:
      340305:
        name: "Andrew Lombardi"
        cost_rate: 100.00
        billable_rate: 288.00
      9535329:
        name: "Joseph Ottinger"
        cost_rate: 75.00
    ```
    """
    if not RATES_FILE.exists():
        return RatesConfig()

    try:
        with open(RATES_FILE) as f:
            data = yaml.safe_load(f) or {}

        cost_rates = {}
        for key, rate in data.get("cost_rates", {}).items():
            cost_rates[str(key)] = Decimal(str(rate))

        billable_rates = {}
        for key, rate in data.get("billable_rates", {}).items():
            billable_rates[str(key)] = Decimal(str(rate))

        default_cost = None
        if data.get("default_cost_rate"):
            default_cost = Decimal(str(data["default_cost_rate"]))

        default_billable = None
        if data.get("default_billable_rate"):
            default_billable = Decimal(str(data["default_billable_rate"]))

        members = {}
        for identity_id, member_data in data.get("members", {}).items():
            member_info = {}
            if member_data.get("name"):
                member_info["name"] = member_data["name"]
            if member_data.get("cost_rate"):
                member_info["cost_rate"] = Decimal(str(member_data["cost_rate"]))
            if member_data.get("billable_rate"):
                member_info["billable_rate"] = Decimal(str(member_data["billable_rate"]))
            members[int(identity_id)] = member_info

        return RatesConfig(
            cost_rates=cost_rates,
            billable_rates=billable_rates,
            default_cost_rate=default_cost,
            default_billable_rate=default_billable,
            members=members,
        )
    except (yaml.YAMLError, KeyError):
        return RatesConfig()


def load_config() -> Config:
    """Load complete application configuration."""
    client_id, client_secret, redirect_uri = load_env_config()
    tokens = load_tokens()
    rates = load_rates_config()

    return Config(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        tokens=tokens,
        rates=rates,
    )


def save_account_info(account_id: str, business_id: int) -> None:
    """Save account and business IDs to config."""
    ensure_config_dir()
    account_file = CONFIG_DIR / "account.json"
    with open(account_file, "w") as f:
        json.dump({"account_id": account_id, "business_id": business_id}, f, indent=2)


def load_account_info() -> tuple[Optional[str], Optional[int]]:
    """Load saved account and business IDs."""
    account_file = CONFIG_DIR / "account.json"
    if not account_file.exists():
        return None, None

    try:
        with open(account_file) as f:
            data = json.load(f)
        return data.get("account_id"), data.get("business_id")
    except (json.JSONDecodeError, KeyError):
        return None, None
