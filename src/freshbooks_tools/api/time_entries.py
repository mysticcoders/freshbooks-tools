"""Time entries API module."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from ..models import TimeEntry
from .client import FreshBooksClient


class TimeEntriesAPI:
    """API for querying time entries."""

    def __init__(self, client: FreshBooksClient):
        self.client = client

    def list(
        self,
        identity_id: Optional[int] = None,
        started_from: Optional[datetime] = None,
        started_to: Optional[datetime] = None,
        billable: Optional[bool] = None,
        billed: Optional[bool] = None,
        client_id: Optional[int] = None,
        project_id: Optional[int] = None,
        include_team: bool = True,
        include_deleted: bool = False,
        page: int = 1,
        per_page: int = 100,
    ) -> tuple[list[TimeEntry], int]:
        """
        List time entries with optional filters.

        Args:
            identity_id: Filter by specific teammate
            started_from: Start of date range (UTC)
            started_to: End of date range (UTC)
            billable: Filter by billable status
            billed: Filter by billed status
            client_id: Filter by client
            project_id: Filter by project
            include_team: Include entries from all team members
            include_deleted: Include soft-deleted entries
            page: Page number (1-indexed)
            per_page: Results per page

        Returns:
            Tuple of (time entries list, total count)
        """
        params = {
            "page": page,
            "per_page": per_page,
        }

        if identity_id is not None:
            params["identity_id"] = identity_id

        if started_from is not None:
            params["started_from"] = started_from.strftime("%Y-%m-%dT%H:%M:%S")

        if started_to is not None:
            params["started_to"] = started_to.strftime("%Y-%m-%dT%H:%M:%S")

        if billable is not None:
            params["billable"] = str(billable).lower()

        if billed is not None:
            params["billed"] = str(billed).lower()

        if client_id is not None:
            params["client_id"] = client_id

        if project_id is not None:
            params["project_id"] = project_id

        if include_team:
            params["team"] = "true"

        if include_deleted:
            params["include_deleted"] = "true"

        url = self.client.timetracking_url("time_entries")
        response = self.client.get(url, params=params)

        entries_data = response.get("time_entries", [])
        total = response.get("meta", {}).get("total", len(entries_data))

        entries = []
        for entry_data in entries_data:
            try:
                entry = TimeEntry(
                    id=entry_data["id"],
                    identity_id=entry_data["identity_id"],
                    duration=entry_data.get("duration", 0),
                    started_at=datetime.fromisoformat(
                        entry_data["started_at"].replace("Z", "+00:00")
                    ),
                    is_logged=entry_data.get("is_logged", True),
                    client_id=entry_data.get("client_id"),
                    project_id=entry_data.get("project_id"),
                    service_id=entry_data.get("service_id"),
                    billable=entry_data.get("billable", True),
                    billed=entry_data.get("billed", False),
                    note=entry_data.get("note"),
                    active=entry_data.get("active", True),
                    internal=entry_data.get("internal", False),
                )
                entries.append(entry)
            except (KeyError, ValueError):
                continue

        return entries, total

    def list_all(
        self,
        identity_id: Optional[int] = None,
        started_from: Optional[datetime] = None,
        started_to: Optional[datetime] = None,
        billable: Optional[bool] = None,
        billed: Optional[bool] = None,
        client_id: Optional[int] = None,
        project_id: Optional[int] = None,
        include_team: bool = True,
    ) -> list[TimeEntry]:
        """
        List all time entries (paginated automatically).

        Returns all entries matching the filters.
        """
        all_entries = []
        page = 1
        per_page = 100

        while True:
            entries, total = self.list(
                identity_id=identity_id,
                started_from=started_from,
                started_to=started_to,
                billable=billable,
                billed=billed,
                client_id=client_id,
                project_id=project_id,
                include_team=include_team,
                page=page,
                per_page=per_page,
            )

            all_entries.extend(entries)

            if len(all_entries) >= total or not entries:
                break

            page += 1

        return all_entries

    def get_month_range(self, year: int, month: int) -> tuple[datetime, datetime]:
        """Get start and end datetime for a month."""
        from calendar import monthrange

        start = datetime(year, month, 1, 0, 0, 0)
        _, last_day = monthrange(year, month)
        end = datetime(year, month, last_day, 23, 59, 59)

        return start, end

    def list_by_month(
        self,
        year: int,
        month: int,
        identity_id: Optional[int] = None,
        billable: Optional[bool] = None,
        include_team: bool = True,
    ) -> list[TimeEntry]:
        """List all time entries for a specific month."""
        started_from, started_to = self.get_month_range(year, month)

        return self.list_all(
            identity_id=identity_id,
            started_from=started_from,
            started_to=started_to,
            billable=billable,
            include_team=include_team,
        )

    def delete(self, time_entry_id: int) -> bool:
        """Delete a time entry by ID."""
        url = self.client.timetracking_url(f"time_entries/{time_entry_id}")
        self.client.client.delete(url, headers=self.client.headers)
        return True

    def update(
        self,
        time_entry_id: int,
        billable: Optional[bool] = None,
        billed: Optional[bool] = None,
        note: Optional[str] = None,
    ) -> bool:
        """Update a time entry."""
        url = self.client.timetracking_url(f"time_entries/{time_entry_id}")

        payload: dict = {"time_entry": {}}

        if billable is not None:
            payload["time_entry"]["billable"] = billable
        if billed is not None:
            payload["time_entry"]["billed"] = billed
        if note is not None:
            payload["time_entry"]["note"] = note

        response = self.client.client.put(url, headers=self.client.headers, json=payload)
        response.raise_for_status()
        return True

    def create(
        self,
        started_at: datetime,
        duration_seconds: int,
        project_id: Optional[int] = None,
        client_id: Optional[int] = None,
        service_id: Optional[int] = None,
        note: Optional[str] = None,
        billable: bool = True,
    ) -> TimeEntry:
        """Create a new time entry for the authenticated user."""
        url = self.client.timetracking_url("time_entries")

        payload = {
            "time_entry": {
                "started_at": started_at.strftime("%Y-%m-%dT%H:%M:%S"),
                "duration": duration_seconds,
                "is_logged": True,
                "billable": billable,
            }
        }

        if project_id:
            payload["time_entry"]["project_id"] = project_id
        if client_id:
            payload["time_entry"]["client_id"] = client_id
        if service_id:
            payload["time_entry"]["service_id"] = service_id
        if note:
            payload["time_entry"]["note"] = note

        response = self.client.post(url, data=payload)
        entry_data = response.get("time_entry", {})

        return TimeEntry(
            id=entry_data["id"],
            identity_id=entry_data["identity_id"],
            duration=entry_data.get("duration", 0),
            started_at=datetime.fromisoformat(
                entry_data["started_at"].replace("Z", "+00:00")
            ),
            is_logged=entry_data.get("is_logged", True),
            client_id=entry_data.get("client_id"),
            project_id=entry_data.get("project_id"),
            service_id=entry_data.get("service_id"),
            billable=entry_data.get("billable", True),
            billed=entry_data.get("billed", False),
            note=entry_data.get("note"),
            active=entry_data.get("active", True),
            internal=entry_data.get("internal", False),
        )
