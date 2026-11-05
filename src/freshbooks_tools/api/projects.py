"""Projects API module."""

from __future__ import annotations

from typing import Optional

from ..models import Project, Service
from .client import FreshBooksClient


class ProjectsAPI:
    """API for querying projects.

    Lookups go through the client's on-disk cache. A project or service that isn't
    found triggers one refetch per run, in case it was added since the cache was filled.
    """

    def __init__(self, client: FreshBooksClient):
        self.client = client
        self._projects_cache: Optional[list[Project]] = None
        self._refreshed: set = set()  # project ids, and "list", refetched this run

    def list(self, include_internal: bool = False, refresh: bool = False) -> list[Project]:
        """List all projects, cached."""
        if self._projects_cache is None or refresh:
            url = self.client.timetracking_url("projects")
            response = self.client.get_cached(url, params={"per_page": 100}, refresh=refresh)
            self._projects_cache = [Project.from_api(p) for p in response.get("projects", [])]
            if refresh:
                self._refreshed.add("list")

        if include_internal:
            return self._projects_cache
        return [p for p in self._projects_cache if not p.internal]

    def _refresh_list_once(self) -> bool:
        if "list" in self._refreshed:
            return False
        self.list(refresh=True)
        return True

    def find_by_name(self, fragment: str, include_internal: bool = False) -> list[Project]:
        """Find projects matching a name fragment (case-insensitive)."""
        def find():
            return [p for p in self.list(include_internal=include_internal) if fragment.lower() in p.title.lower()]
        return find() or (self._refresh_list_once() and find()) or []

    def get_by_id(self, project_id: int) -> Optional[Project]:
        """Get a project by ID."""
        def find():
            return next((p for p in self.list(include_internal=True) if p.id == project_id), None)
        return find() or (self._refresh_list_once() and find()) or None

    def get_with_services(self, project_id: int, refresh: bool = False) -> Optional[Project]:
        """Fetch a project by ID with its associated services."""
        url = self.client.projects_url(f"project/{project_id}")
        response = self.client.get_cached(url, refresh=refresh)
        if refresh:
            self._refreshed.add(project_id)
        project_data = response.get("project")
        if project_data:
            return Project.from_api(project_data)
        return None

    def project_services(self, project_id: int, refresh: bool = False) -> list[Service]:
        """A project's services."""
        project = self.get_with_services(project_id, refresh=refresh)
        return project.services if project else []

    def refresh_once(self, project_id: int) -> Optional[list[Service]]:
        """Refetch a project's services unless already fetched this run; None if already fetched."""
        if project_id in self._refreshed:
            return None
        return self.project_services(project_id, refresh=True)

    def service_name(self, project_id: int, service_id: int) -> Optional[str]:
        """Name of a service attached to a project (these can be missing from the business-wide service list)."""
        names = {s.id: s.name for s in self.project_services(project_id)}
        if service_id not in names and (fresh := self.refresh_once(project_id)) is not None:
            names = {s.id: s.name for s in fresh}
        return names.get(service_id)

    def match_projects(self, text: str) -> list[Project]:
        """Projects matching an exact id or a case-insensitive name fragment."""
        if text.isdigit() and (by_id := self.get_by_id(int(text))):
            return [by_id]
        return self.find_by_name(text)

    def match_services(self, project_id: int, text: str) -> list[Service]:
        """A project's services matching an exact id or a name fragment; refetches once on no match."""
        def find(services):
            if text.isdigit() and (by_id := [s for s in services if s.id == int(text)]):
                return by_id
            return [s for s in services if text.lower() in s.name.lower()]

        matches = find(self.project_services(project_id))
        if not matches and (fresh := self.refresh_once(project_id)) is not None:
            matches = find(fresh)
        return matches

    def clear_cache(self) -> None:
        """Clear in-memory project data."""
        self._projects_cache = None
        self._refreshed = set()
