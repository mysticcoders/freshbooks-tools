"""Team members and staff API module."""

from decimal import Decimal
from typing import Optional

from ..models import Staff, TeamMember
from .client import FreshBooksClient


class TeamAPI:
    """API for querying team members and staff."""

    def __init__(self, client: FreshBooksClient):
        self.client = client
        self._team_cache: Optional[dict[int, TeamMember]] = None
        self._staff_cache: Optional[dict[int, Staff]] = None
        self._project_members_cache: Optional[dict[int, dict]] = None

    def list_team_members(self) -> list[TeamMember]:
        """List all team members from auth API."""
        _, business_id = self.client.ensure_account_info()
        url = f"{self.client.BASE_AUTH_URL}/businesses/{business_id}/team_members"

        response = self.client.get(url)
        members_data = response.get("team_members", [])

        members = []
        for member_data in members_data:
            try:
                member = TeamMember(
                    uuid=member_data["uuid"],
                    first_name=member_data.get("first_name"),
                    middle_name=member_data.get("middle_name"),
                    last_name=member_data.get("last_name"),
                    email=member_data.get("email"),
                    job_title=member_data.get("job_title"),
                    business_id=member_data.get("business_id", business_id),
                    business_role_name=member_data.get("business_role_name"),
                    active=member_data.get("active", True),
                    identity_id=member_data.get("identity_id"),
                )
                members.append(member)
            except (KeyError, ValueError):
                continue

        return members

    def list_project_members(self) -> dict[int, dict]:
        """List all members from project groups (contractors).

        Returns dict mapping identity_id to member info dict with:
        - first_name, last_name, email, company, active, role
        """
        if self._project_members_cache is not None:
            return self._project_members_cache

        members_by_id: dict[int, dict] = {}

        url = self.client.timetracking_url("projects")
        response = self.client.get(url, params={"per_page": 100})
        projects = response.get("projects", [])

        for project in projects:
            project_id = project.get("id")
            if not project_id:
                continue

            try:
                detail_url = self.client.timetracking_url(f"projects/{project_id}")
                detail = self.client.get(detail_url)
                project_data = detail.get("project", {})
                group = project_data.get("group", {})
                members = group.get("members", [])

                for m in members:
                    identity_id = m.get("identity_id")
                    if identity_id and identity_id not in members_by_id:
                        members_by_id[identity_id] = {
                            "first_name": m.get("first_name"),
                            "last_name": m.get("last_name"),
                            "email": m.get("email"),
                            "company": m.get("company"),
                            "active": m.get("active", True),
                            "role": m.get("role"),
                        }
            except Exception:
                continue

        self._project_members_cache = members_by_id
        return members_by_id

    def list_staff(self) -> list[Staff]:
        """List all staff from accounting API (deprecated but has rates)."""
        url = self.client.accounting_url("users/staffs")

        response = self.client.get(url)
        staff_response = response.get("response", {}).get("result", {})
        staff_data = staff_response.get("staffs", [])

        staff_list = []
        for s in staff_data:
            try:
                rate = None
                if s.get("rate"):
                    rate = Decimal(str(s["rate"]))

                staff = Staff(
                    id=s["id"],
                    userid=s.get("userid"),
                    fname=s.get("fname"),
                    lname=s.get("lname"),
                    email=s.get("email"),
                    rate=rate,
                    display_name=s.get("display_name"),
                )
                staff_list.append(staff)
            except (KeyError, ValueError):
                continue

        return staff_list

    def get_team_by_identity_id(self) -> dict[int, TeamMember]:
        """Get team members indexed by identity_id."""
        if self._team_cache is not None:
            return self._team_cache

        members = self.list_team_members()
        self._team_cache = {}

        for member in members:
            if member.identity_id:
                self._team_cache[member.identity_id] = member

        return self._team_cache

    def get_staff_by_id(self) -> dict[int, Staff]:
        """Get staff indexed by id (which matches identity_id)."""
        if self._staff_cache is not None:
            return self._staff_cache

        staff_list = self.list_staff()
        self._staff_cache = {}

        for staff in staff_list:
            self._staff_cache[staff.id] = staff

        return self._staff_cache

    def get_team_member_name(self, identity_id: int) -> str:
        """Get display name for a team member by identity_id."""
        team = self.get_team_by_identity_id()

        if identity_id in team:
            return team[identity_id].display_name

        staff = self.get_staff_by_id()
        if identity_id in staff:
            return staff[identity_id].name

        project_members = self.list_project_members()
        if identity_id in project_members:
            m = project_members[identity_id]
            name = f"{m.get('first_name', '')} {m.get('last_name', '')}".strip()
            return name or m.get("email") or f"Unknown ({identity_id})"

        return f"Unknown ({identity_id})"

    def get_team_member_email(self, identity_id: int) -> Optional[str]:
        """Get email for a team member by identity_id."""
        team = self.get_team_by_identity_id()

        if identity_id in team:
            return team[identity_id].email

        staff = self.get_staff_by_id()
        if identity_id in staff:
            return staff[identity_id].email

        project_members = self.list_project_members()
        if identity_id in project_members:
            return project_members[identity_id].get("email")

        return None

    def find_identity_by_name(self, name: str) -> Optional[int]:
        """Find identity_id by name (case-insensitive partial match)."""
        name_lower = name.lower()

        team = self.get_team_by_identity_id()
        for identity_id, member in team.items():
            if name_lower in member.display_name.lower():
                return identity_id

        staff = self.get_staff_by_id()
        for staff_id, s in staff.items():
            if name_lower in s.name.lower():
                return staff_id

        project_members = self.list_project_members()
        for identity_id, m in project_members.items():
            full_name = f"{m.get('first_name', '')} {m.get('last_name', '')}".strip().lower()
            if name_lower in full_name:
                return identity_id
            if m.get("email") and name_lower in m["email"].lower():
                return identity_id

        return None

    def get_all_members(self) -> dict[int, dict]:
        """Get all team members/contractors from all sources.

        Returns dict mapping identity_id to info dict.
        """
        all_members: dict[int, dict] = {}

        team = self.get_team_by_identity_id()
        for identity_id, member in team.items():
            all_members[identity_id] = {
                "first_name": member.first_name,
                "last_name": member.last_name,
                "email": member.email,
                "company": None,
                "active": member.active,
                "role": member.business_role_name,
                "source": "team_members",
            }

        staff = self.get_staff_by_id()
        for staff_id, s in staff.items():
            if staff_id not in all_members:
                all_members[staff_id] = {
                    "first_name": s.fname,
                    "last_name": s.lname,
                    "email": s.email,
                    "company": None,
                    "active": True,
                    "role": "staff",
                    "rate": s.rate,
                    "source": "staff",
                }

        project_members = self.list_project_members()
        for identity_id, m in project_members.items():
            if identity_id not in all_members:
                all_members[identity_id] = {
                    **m,
                    "source": "project_members",
                }

        return all_members

    def clear_cache(self) -> None:
        """Clear cached team data."""
        self._team_cache = None
        self._staff_cache = None
        self._project_members_cache = None
