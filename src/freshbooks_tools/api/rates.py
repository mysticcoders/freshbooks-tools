"""Rate resolution module for billable and cost rates."""

from decimal import Decimal
from typing import Optional

from ..config import RatesConfig
from ..models import Service, ServiceRate
from .client import FreshBooksClient
from .team import TeamAPI


class RatesAPI:
    """API for resolving billable and cost rates."""

    def __init__(self, client: FreshBooksClient, team_api: TeamAPI, rates_config: RatesConfig):
        self.client = client
        self.team_api = team_api
        self.rates_config = rates_config
        self._services_cache: Optional[dict[int, Service]] = None
        self._service_rates_cache: dict[int, Optional[Decimal]] = {}
        self._team_member_rates_cache: Optional[dict[int, Decimal]] = None

    def get_team_member_rates(self) -> dict[int, Decimal]:
        """Get billable rates for all team members from API.

        Returns dict mapping identity_id to billable rate.
        """
        if self._team_member_rates_cache is not None:
            return self._team_member_rates_cache

        url = self.client.timetracking_url("team_member_rates")
        try:
            response = self.client.get(url)
            rates_data = response.get("team_member_rates", [])

            self._team_member_rates_cache = {}
            for r in rates_data:
                identity_id = r.get("identity_id")
                rate = r.get("rate")
                if identity_id and rate:
                    self._team_member_rates_cache[identity_id] = Decimal(str(rate))

            return self._team_member_rates_cache
        except Exception:
            self._team_member_rates_cache = {}
            return self._team_member_rates_cache

    def get_team_member_billable_rate(self, identity_id: int) -> Optional[Decimal]:
        """Get billable rate for a specific team member from API."""
        rates = self.get_team_member_rates()
        return rates.get(identity_id)

    def list_services(self) -> list[Service]:
        """List all services."""
        url = self.client.comments_url("services")
        response = self.client.get(url)
        services_data = response.get("services", [])

        services = []
        for s in services_data:
            try:
                service = Service(
                    id=s["id"],
                    business_id=s["business_id"],
                    name=s["name"],
                    billable=s.get("billable", True),
                    project_default=s.get("project_default", False),
                    vis_state=s.get("vis_state", 0),
                )
                services.append(service)
            except (KeyError, ValueError):
                continue

        return services

    def get_services_by_id(self) -> dict[int, Service]:
        """Get services indexed by ID."""
        if self._services_cache is not None:
            return self._services_cache

        services = self.list_services()
        self._services_cache = {s.id: s for s in services}
        return self._services_cache

    def get_service_rate(self, service_id: int) -> Optional[Decimal]:
        """Get the billable rate for a service."""
        if service_id in self._service_rates_cache:
            return self._service_rates_cache[service_id]

        url = self.client.comments_url(f"service/{service_id}/rate")
        try:
            response = self.client.get(url)
            rate_data = response.get("service_rate", {})
            if rate_data.get("rate"):
                rate = Decimal(str(rate_data["rate"]))
                self._service_rates_cache[service_id] = rate
                return rate
        except Exception:
            pass

        self._service_rates_cache[service_id] = None
        return None

    def get_service_name(self, service_id: int) -> str:
        """Get the name of a service."""
        services = self.get_services_by_id()
        if service_id in services:
            return services[service_id].name
        return f"Service {service_id}"

    def get_staff_rate(self, identity_id: int) -> Optional[Decimal]:
        """Get the rate from staff record (deprecated API)."""
        staff = self.team_api.get_staff_by_id()
        if identity_id in staff:
            return staff[identity_id].rate
        return None

    def get_billable_rate(
        self,
        identity_id: int,
        service_id: Optional[int] = None,
    ) -> Optional[Decimal]:
        """
        Get the billable rate for a time entry.

        Priority:
        1. Config file override by identity_id (for manual overrides)
        2. Service rate (if service_id provided and rate > 0)
        3. Team member rate from API (team_member_rates endpoint)
        4. Staff rate (deprecated endpoint)
        5. Config file billable rate by email
        6. Default billable rate from config
        """
        config_override = self.rates_config.get_billable_rate_by_id(identity_id)
        if config_override is not None and config_override > 0:
            return config_override

        if service_id:
            service_rate = self.get_service_rate(service_id)
            if service_rate is not None and service_rate > 0:
                return service_rate

        team_rate = self.get_team_member_billable_rate(identity_id)
        if team_rate is not None and team_rate > 0:
            return team_rate

        staff_rate = self.get_staff_rate(identity_id)
        if staff_rate is not None and staff_rate > 0:
            return staff_rate

        email = self.team_api.get_team_member_email(identity_id)
        if email:
            config_rate = self.rates_config.get_billable_rate(email)
            if config_rate is not None and config_rate > 0:
                return config_rate

        return self.rates_config.default_billable_rate

    def get_cost_rate(self, identity_id: int) -> Optional[Decimal]:
        """
        Get the cost rate for a team member.

        Cost rates are not exposed in the FreshBooks API, so we rely on config file.
        Checks by identity_id first, then by email.
        """
        config_rate = self.rates_config.get_cost_rate_by_id(identity_id)
        if config_rate is not None:
            return config_rate

        email = self.team_api.get_team_member_email(identity_id)
        if email:
            config_rate = self.rates_config.get_cost_rate(email)
            if config_rate is not None:
                return config_rate

        return self.rates_config.default_cost_rate

    def clear_cache(self) -> None:
        """Clear cached rate data."""
        self._services_cache = None
        self._service_rates_cache.clear()
        self._team_member_rates_cache = None
