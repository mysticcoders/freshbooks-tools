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

    def clear_cache(self) -> None:
        """Clear cached project data."""
        self._projects_cache = None
