"""Pydantic models for FreshBooks API responses."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class Timer(BaseModel):
    """Timer state for a time entry."""

    id: Optional[int] = None
    is_running: bool = False


class TimeEntry(BaseModel):
    """A time entry record."""

    id: int
    identity_id: int
    duration: int  # seconds
    started_at: datetime
    is_logged: bool = True
    client_id: Optional[int] = None
    project_id: Optional[int] = None
    service_id: Optional[int] = None
    billable: bool = True
    billed: bool = False
    note: Optional[str] = None
    active: bool = True
    internal: bool = False
    timer: Optional[Timer] = None

    @property
    def hours(self) -> Decimal:
        """Duration in hours."""
        return Decimal(self.duration) / Decimal(3600)


class InvoiceLine(BaseModel):
    """A line item on an invoice."""

    lineid: Optional[int] = None
    name: Optional[str] = None
    description: Optional[str] = None
    qty: Decimal = Decimal("1")
    unit_cost: Optional[Decimal] = Field(default=None, alias="unit_cost")
    amount: Optional[Decimal] = Field(default=None, alias="amount")
    type: int = 0


class Payment(BaseModel):
    """A payment record."""

    id: int = Field(alias="paymentid")
    invoiceid: int
    amount: Decimal
    date: str
    type: Optional[str] = None
    note: Optional[str] = None
    gateway: Optional[str] = None
    from_credit: Optional[bool] = None
    updated: Optional[str] = None

    class Config:
        populate_by_name = True


class Invoice(BaseModel):
    """An invoice record."""

    id: int = Field(alias="invoiceid")
    invoice_number: Optional[str] = None
    customerid: int
    create_date: str
    due_date: Optional[str] = None
    currency_code: str = "USD"
    status: int  # legacy numeric status
    v3_status: Optional[str] = None
    amount: Optional[Decimal] = Field(default=None, alias="amount")
    paid: Optional[Decimal] = None
    outstanding: Optional[Decimal] = None
    discount_value: Optional[Decimal] = None
    fname: Optional[str] = None
    lname: Optional[str] = None
    organization: Optional[str] = None
    lines: list[InvoiceLine] = []
    payments: list[Payment] = []

    class Config:
        populate_by_name = True

    @property
    def display_status(self) -> str:
        """Human-readable status."""
        if self.v3_status:
            return self.v3_status.title()
        status_map = {
            0: "Disputed",
            1: "Draft",
            2: "Sent",
            3: "Viewed",
            4: "Paid",
            5: "Auto Paid",
            6: "Retry",
            7: "Failed",
            8: "Partial",
        }
        return status_map.get(self.status, "Unknown")

    @property
    def client_name(self) -> str:
        """Combined client name."""
        parts = []
        if self.organization:
            parts.append(self.organization)
        elif self.fname or self.lname:
            parts.append(f"{self.fname or ''} {self.lname or ''}".strip())
        return " ".join(parts) or "Unknown"


class Client(BaseModel):
    """A client record."""

    id: int = Field(alias="userid")
    fname: Optional[str] = None
    lname: Optional[str] = None
    organization: Optional[str] = None
    email: Optional[str] = None
    currency_code: str = "USD"

    class Config:
        populate_by_name = True

    @property
    def display_name(self) -> str:
        """Combined display name."""
        if self.organization:
            return self.organization
        return f"{self.fname or ''} {self.lname or ''}".strip() or "Unknown"


class TeamMember(BaseModel):
    """A team member from the auth API."""

    uuid: str
    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    job_title: Optional[str] = None
    business_id: int
    business_role_name: Optional[str] = None
    active: bool = True
    identity_id: Optional[int] = None

    @property
    def display_name(self) -> str:
        """Combined display name."""
        parts = [self.first_name, self.middle_name, self.last_name]
        return " ".join(p for p in parts if p) or self.email or "Unknown"


class Staff(BaseModel):
    """A staff member from the accounting API (deprecated but has rates)."""

    id: int
    userid: Optional[int] = None
    fname: Optional[str] = None
    lname: Optional[str] = None
    email: Optional[str] = None
    rate: Optional[Decimal] = None
    display_name: Optional[str] = None

    @property
    def name(self) -> str:
        """Combined name."""
        if self.display_name:
            return self.display_name
        return f"{self.fname or ''} {self.lname or ''}".strip() or self.email or "Unknown"


class ServiceRate(BaseModel):
    """Rate for a service."""

    rate: Decimal


class Service(BaseModel):
    """A service that can be tracked against."""

    id: int
    business_id: int
    name: str
    billable: bool = True
    project_default: bool = False
    vis_state: int = 0


class BusinessMembership(BaseModel):
    """User's membership in a business."""

    id: int
    role: str
    business: dict


class UserIdentity(BaseModel):
    """Current user identity."""

    id: int = Field(alias="identity_id")
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: str
    business_memberships: list[BusinessMembership] = []

    class Config:
        populate_by_name = True

    @property
    def display_name(self) -> str:
        """Combined display name."""
        return f"{self.first_name or ''} {self.last_name or ''}".strip() or self.email


class Project(BaseModel):
    """A project from the timetracking API."""

    id: int
    title: str
    client_id: Optional[int] = None
    active: bool = True
    complete: bool = False
    billable: bool = True
    internal: bool = False

    @classmethod
    def from_api(cls, data: dict) -> "Project":
        """Create a Project from API response data."""
        return cls(
            id=data["id"],
            title=data.get("title", ""),
            client_id=data.get("client_id"),
            active=data.get("active", True),
            complete=data.get("complete", False),
            billable=data.get("billable", True),
            internal=data.get("internal", False),
        )


class AmountWithCurrency(BaseModel):
    """Currency amount as returned by FreshBooks API."""

    amount: Decimal
    code: str


class AgingBucket(BaseModel):
    """AR aging bucket totals."""

    current: AmountWithCurrency = Field(alias="0-30")
    days_30: AmountWithCurrency = Field(alias="31-60")
    days_60: AmountWithCurrency = Field(alias="61-90")
    days_90_plus: AmountWithCurrency = Field(alias="91+")
    total: AmountWithCurrency

    class Config:
        populate_by_name = True


class AccountAgingReport(BaseModel):
    """AR aging report response from FreshBooks API."""

    end_date: str
    company_name: str
    currency_code: str
    totals: AgingBucket
    accounts: list[dict]
    download_token: Optional[str] = None
