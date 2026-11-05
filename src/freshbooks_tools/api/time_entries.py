"""Time entries API module."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from rich.console import Console

from ..models import TimeEntry
from .client import FreshBooksClient

console = Console(stderr=True)


class TimeEntriesAPI:
    """API for querying time entries."""

    def __init__(self, client: FreshBooksClient):
        self.client = client

    def _parse_entries(self, entries_data: list[dict]) -> tuple[list[TimeEntry], int]:
        """Parse time entries, returning (entries, skipped_count)."""
        entries = []
        skipped = 0

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
            except (KeyError, ValueError, TypeError):
                skipped += 1

        return entries, skipped

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

        entries, skipped = self._parse_entries(entries_data)

        if skipped > 0:
            console.print(
                f"[yellow]Warning: Skipped {skipped} malformed time "
                f"{'entry' if skipped == 1 else 'entries'}[/yellow]"
            )

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
        duration_seconds: Optional[int] = None,
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
        if duration_seconds is not None:
            payload["time_entry"]["duration"] = duration_seconds

        self.client.put(url, data=payload)
        return True

    def find_mergeable(
        self,
        identity_id: int,
        day: datetime,
        project_id: int,
        service_id: Optional[int],
        billable: bool,
    ) -> Optional[TimeEntry]:
        """The user's most recent unbilled entry on that day with the same project, service and billable flag."""
        entries = self.list_all(
            identity_id=identity_id,
            project_id=project_id,
            started_from=day.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1),
            started_to=day.replace(hour=23, minute=59, second=59, microsecond=0) + timedelta(days=1),
        )
        matches = [
            e for e in entries
            if e.started_at.date() == day.date() and e.identity_id == identity_id
            and e.project_id == project_id and e.service_id == service_id
            and e.billable == billable and not e.billed
        ]
        return max(matches, key=lambda e: (e.started_at, e.id), default=None)

    def add_or_extend(
        self,
        identity_id: int,
        started_at: datetime,
        duration_seconds: int,
        project_id: int,
        client_id: Optional[int],
        service_id: Optional[int],
        note: Optional[str],
        billable: bool,
        new_entry: bool = False,
    ) -> tuple[TimeEntry, Optional[Decimal]]:
        """Add hours to a matching entry from the same day, or create one.

        Returns (entry, hours before) where hours before is None when a new entry was created.
        """
        existing = None if new_entry else self.find_mergeable(identity_id, started_at, project_id, service_id, billable)
        if existing is None:
            entry = self.create(
                started_at=started_at, duration_seconds=duration_seconds, project_id=project_id,
                client_id=client_id, service_id=service_id, note=note, billable=billable,
            )
            return entry, None

        before = existing.hours
        merged_note = existing.note
        if note:
            merged_note = f"{existing.note}; {note}" if existing.note else note
        self.update(existing.id, duration_seconds=existing.duration + duration_seconds,
                    note=merged_note if merged_note != existing.note else None)
        return existing.model_copy(update={"duration": existing.duration + duration_seconds, "note": merged_note}), before

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
