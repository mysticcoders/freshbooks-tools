"""Projects API module."""

from __future__ import annotations

from typing import Optional

from ..models import Project
from .client import FreshBooksClient


class ProjectsAPI:
    """API for querying projects."""

    def __init__(self, client: FreshBooksClient):
        self.client = client
        self._projects_cache: Optional[list[Project]] = None
        self._services_by_project: dict[int, dict[int, str]] = {}

    def list(self, include_internal: bool = False) -> list[Project]:
        """List all projects, cached."""
        if self._projects_cache is not None:
            projects = self._projects_cache
        else:
            url = self.client.timetracking_url("projects")
            response = self.client.get(url, params={"per_page": 100})
            projects_data = response.get("projects", [])
            projects = [Project.from_api(p) for p in projects_data]
            self._projects_cache = projects

        if include_internal:
            return projects
        return [p for p in projects if not p.internal]

    def find_by_name(self, fragment: str, include_internal: bool = False) -> list[Project]:
        """Find projects matching a name fragment (case-insensitive)."""
        projects = self.list(include_internal=include_internal)
        fragment_lower = fragment.lower()
        return [p for p in projects if fragment_lower in p.title.lower()]

    def get_by_id(self, project_id: int) -> Optional[Project]:
        """Get a project by ID from cache."""
        projects = self.list(include_internal=True)
        for p in projects:
            if p.id == project_id:
                return p
        return None

    def get_with_services(self, project_id: int) -> Optional[Project]:
        """Fetch a project by ID with its associated services."""
        url = self.client.projects_url(f"project/{project_id}")
        response = self.client.get(url)
        project_data = response.get("project")
        if project_data:
            return Project.from_api(project_data)
        return None

    def service_name(self, project_id: int, service_id: int) -> Optional[str]:
        """Name of a service attached to a project (these can be missing from the business-wide service list)."""
        if project_id not in self._services_by_project:
            project = self.get_with_services(project_id)
            self._services_by_project[project_id] = {s.id: s.name for s in project.services} if project else {}
        return self._services_by_project[project_id].get(service_id)

    def clear_cache(self) -> None:
        """Clear cached project data."""
        self._projects_cache = None
        self._services_by_project = {}
