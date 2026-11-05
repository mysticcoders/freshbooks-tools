"""MCP server: exposes FreshBooks time tracking and accounting to an LLM client over stdio."""

from __future__ import annotations

from collections import defaultdict
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Iterator, Optional

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from .api.client import FreshBooksClient
from .api.expenses import ExpensesAPI
from .api.invoices import InvoicesAPI
from .api.projects import ProjectsAPI
from .api.rates import RatesAPI
from .api.reports import ReportsAPI
from .api.team import TeamAPI
from .api.time_entries import TimeEntriesAPI
from .config import load_aliases, load_config, save_aliases
from .exceptions import FreshBooksError

INSTRUCTIONS = """\
FreshBooks for the logged-in user: time tracking, projects, invoices, expenses and reports.

Logging time (e.g. "log 2 hours to acme today"):
1. Call time_habits. It returns today's date, the user's aliases and default alias, and each
   project they have logged time to recently, with the services they use there (most-used first).
2. Find the project the user means: match their words against aliases, project titles and clients.
   If two projects fit equally well, ask the user which one.
3. If the user did not name a service, use that project's usual_service from time_habits.
   If the project has no history, call list_projects and ask which service to use.
4. Call add_time_entry with the project id and service id. Omit date for today; otherwise YYYY-MM-DD.
5. Tell the user what was filed: project, service, hours, date.

If the user says they always log a project the same way, offer set_alias so next time
`add_time_entry` can take just the alias, or no project at all if it is the default.
Business questions (owners and admins): list_invoices (pass client for "what does X owe"),
unbilled_time ("what can we invoice?"), accounts_receivable_aging, profit_and_loss, list_expenses,
list_time_entries with everyone=true. If a tool reports insufficient_scope or 403, explain that
the user's FreshBooks role or login may not allow it; they may need `fb auth logout` then `fb auth login`.

Money values are strings to keep exact decimals.
"""

READ = ToolAnnotations(read_only_hint=True, open_world_hint=True)
WRITE = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=True)

server = MCPServer("freshbooks", instructions=INSTRUCTIONS, log_level="WARNING")


@contextmanager
def _client() -> Iterator[FreshBooksClient]:
    try:
        config = load_config()
    except ValueError as e:
        raise ToolError(str(e)) from e
    if not config.tokens:
        raise ToolError("Not logged in to FreshBooks. The user needs to run `fb auth login` in a terminal.")
    try:
        with FreshBooksClient(config) as client:
            yield client
    except FreshBooksError as e:
        raise ToolError(f"FreshBooks API error: {e}") from e  # e.g. a missing OAuth scope; the LLM should see why


def _parse_date(value: Optional[str], name: str) -> Optional[datetime]:
    if value is None:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError as e:
        raise ToolError(f"{name} must be YYYY-MM-DD, got {value!r}") from e


def _one(matches: list, kind: str, text: str, label) -> Any:
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise ToolError(f"No {kind} matches {text!r}. Call list_projects to see projects and their services.")
    raise ToolError(f"{len(matches)} {kind}s match {text!r}: " + "; ".join(label(m) for m in matches) + ". Ask the user which one.")


@server.tool(annotations=READ)
def time_habits(days: int = 90) -> dict:
    """Today's date, aliases, and the projects and services the user has logged time to in the last `days` days.

    Use this first when the user asks to log time: each project lists its services by hours,
    and `usual_service` is the one to use when the user doesn't name a service.
    """
    with _client() as client:
        projects_api = ProjectsAPI(client)
        invoices_api = InvoicesAPI(client)
        me = client.current_identity_id()
        since = datetime.now() - timedelta(days=days)
        entries = TimeEntriesAPI(client).list_all(identity_id=me, started_from=since)  # identity filter requires team=true (the default)

        hours: dict[int, dict[Optional[int], float]] = defaultdict(lambda: defaultdict(float))
        last: dict[int, date] = {}
        for e in entries:
            if not e.project_id:
                continue
            hours[e.project_id][e.service_id] += float(e.hours)
            last[e.project_id] = max(last.get(e.project_id, e.started_at.date()), e.started_at.date())

        projects = []
        for project_id, by_service in hours.items():
            project = projects_api.get_by_id(project_id)
            services = [
                {"service_id": sid, "service": (projects_api.service_name(project_id, sid) if sid else None), "hours": round(h, 2)}
                for sid, h in sorted(by_service.items(), key=lambda kv: -kv[1])
            ]
            projects.append({
                "project_id": project_id,
                "project": project.title if project else f"Project {project_id}",
                "client": invoices_api.get_client_name(project.client_id) if project and project.client_id else None,
                "hours": round(sum(by_service.values()), 2),
                "last_logged": last[project_id].isoformat(),
                "usual_service": services[0],
                "services": services,
            })

        aliases = load_aliases()
        return {
            "today": date.today().isoformat(),
            "days": days,
            "default_alias": aliases["default"],
            "aliases": aliases["aliases"],
            "projects": sorted(projects, key=lambda p: -p["hours"]),
        }


@server.tool(annotations=READ)
def list_projects() -> dict:
    """All active projects with their client and services (ids included)."""
    with _client() as client:
        projects_api = ProjectsAPI(client)
        invoices_api = InvoicesAPI(client)
        return {"projects": [
            {
                "project_id": p.id,
                "project": p.title,
                "client": invoices_api.get_client_name(p.client_id) if p.client_id else None,
                "services": [{"service_id": s.id, "service": s.name} for s in projects_api.project_services(p.id)],
            }
            for p in sorted(projects_api.list(), key=lambda p: p.title.lower())
        ]}


@server.tool(annotations=READ)
def list_aliases() -> dict:
    """Saved aliases (name -> project and service) and the default alias."""
    return load_aliases()


@server.tool(annotations=WRITE)
def add_time_entry(
    hours: float,
    project: Optional[str] = None,
    service: Optional[str] = None,
    date: Optional[str] = None,
    note: Optional[str] = None,
    billable: bool = True,
) -> dict:
    """File a time entry for the logged-in user.

    project: an alias, project id, or project name fragment; omit to use the default alias.
    service: a service id or name fragment; omit to use the alias's service (if any).
    date: YYYY-MM-DD; omit for today.
    """
    if hours <= 0 or hours > 24:
        raise ToolError("hours must be more than 0 and at most 24")
    entry_date = (_parse_date(date, "date") or datetime.now()).replace(hour=9, minute=0, second=0, microsecond=0)

    with _client() as client:
        projects_api = ProjectsAPI(client)
        aliases = load_aliases()
        name = project or aliases["default"]
        if not name:
            raise ToolError("No project given and no default alias. Call time_habits or list_projects to pick one.")

        alias = aliases["aliases"].get(name)
        service_id = service_name = None
        if alias:
            selected = projects_api.get_by_id(alias["project_id"])
            if not selected:
                raise ToolError(f"Alias {name!r} points to project {alias['project_id']}, which no longer exists.")
            service_id, service_name = alias.get("service_id"), alias.get("service")
        else:
            selected = _one(projects_api.match_projects(name), "project", name, lambda p: f"{p.title} (id {p.id})")

        if service:
            svc = _one(projects_api.match_services(selected.id, service), "service", service, lambda s: f"{s.name} (id {s.id})")
            service_id, service_name = svc.id, svc.name

        entry = TimeEntriesAPI(client).create(
            started_at=entry_date,
            duration_seconds=int(hours * 3600),
            project_id=selected.id,
            client_id=selected.client_id,
            service_id=service_id,
            note=note,
            billable=billable,
        )
        return {
            "entry_id": entry.id,
            "date": entry_date.date().isoformat(),
            "hours": hours,
            "project": selected.title,
            "service": service_name,
            "note": note,
            "billable": billable,
        }


@server.tool(annotations=WRITE)
def set_alias(name: str, project: str, service: Optional[str] = None, make_default: bool = False) -> dict:
    """Save an alias for a project (and optionally a service) so add_time_entry can use the short name.

    project: project id or name fragment. service: service id or name fragment.
    make_default: also use this alias when add_time_entry gets no project.
    """
    with _client() as client:
        projects_api = ProjectsAPI(client)
        selected = _one(projects_api.match_projects(project), "project", project, lambda p: f"{p.title} (id {p.id})")
        svc = _one(projects_api.match_services(selected.id, service), "service", service, lambda s: f"{s.name} (id {s.id})") if service else None

    aliases = load_aliases()
    aliases["aliases"][name] = {
        "project_id": selected.id,
        "project": selected.title,
        "service_id": svc.id if svc else None,
        "service": svc.name if svc else None,
    }
    if make_default:
        aliases["default"] = name
    save_aliases(aliases)
    return {"alias": name, **aliases["aliases"][name], "default": aliases["default"] == name}


@server.tool(annotations=READ)
def list_time_entries(start_date: str, end_date: Optional[str] = None, everyone: bool = False) -> dict:
    """Time entries from start_date to end_date (YYYY-MM-DD, end defaults to today).

    The user's own entries unless everyone=True; seeing the team's needs an owner or admin role.
    """
    start = _parse_date(start_date, "start_date")
    end = (_parse_date(end_date, "end_date") or datetime.now()).replace(hour=23, minute=59, second=59)
    with _client() as client:
        projects_api = ProjectsAPI(client)
        team_api = TeamAPI(client)
        entries = TimeEntriesAPI(client).list_all(
            identity_id=None if everyone else client.current_identity_id(),
            started_from=start, started_to=end,
        )
        rows = []
        for e in sorted(entries, key=lambda e: e.started_at):
            project = projects_api.get_by_id(e.project_id) if e.project_id else None
            rows.append({
                "entry_id": e.id,
                "date": e.started_at.date().isoformat(),
                "teammate": team_api.get_team_member_name(e.identity_id),
                "project": project.title if project else None,
                "service": projects_api.service_name(e.project_id, e.service_id) if e.project_id and e.service_id else None,
                "hours": float(e.hours),
                "billable": e.billable,
                "billed": e.billed,
                "note": e.note,
            })
        return {"entries": rows, "total_hours": round(sum(r["hours"] for r in rows), 2)}


@server.tool(annotations=READ)
def list_invoices(
    client: Optional[str] = None,
    status: Optional[str] = None,
    date_min: Optional[str] = None,
    date_max: Optional[str] = None,
    limit: int = 50,
) -> dict:
    """Invoices, newest first, with amount, paid and outstanding.

    client: client name fragment or id. status: draft, sent, viewed, paid, partial, overdue...
    Dates YYYY-MM-DD. For "what does X owe", pass client; outstanding_in_results sums the returned invoices,
    so raise limit if total is larger than the number returned.
    """
    with _client() as fb:
        invoices_api = InvoicesAPI(fb)
        customer_id = None
        if client:
            clients = invoices_api.list_clients()
            matches = [c for c in clients if str(c.id) == client] or [c for c in clients if client.lower() in c.display_name.lower()]
            customer_id = _one(matches, "client", client, lambda c: f"{c.display_name} (id {c.id})").id
        invoices, total = invoices_api.list_invoices(
            customer_id=customer_id, status=status, date_min=date_min, date_max=date_max, per_page=min(limit, 100))
        return {
            "total": total,
            "outstanding_in_results": str(sum((i.outstanding or 0) for i in invoices[:limit])),
            "invoices": [{**i.model_dump(mode="json", exclude={"lines", "payments"}), "client": i.client_name, "status_name": i.display_status}
                         for i in invoices[:limit]],
        }


@server.tool(annotations=READ)
def unbilled_time(start_date: Optional[str] = None) -> dict:
    """Billable time not yet invoiced, for the whole team, by client and project, with hours and amounts.

    Answers "what can we invoice?". start_date (YYYY-MM-DD) limits how far back to look.
    Amounts use the same billable rates as the CLI reports; needs a role that can see the team's time.
    """
    with _client() as fb:
        projects_api = ProjectsAPI(fb)
        invoices_api = InvoicesAPI(fb)
        team_api = TeamAPI(fb)
        rates_api = RatesAPI(fb, team_api, load_config().rates)
        entries = TimeEntriesAPI(fb).list_all(started_from=_parse_date(start_date, "start_date"), billable=True, billed=False)

        groups: dict[tuple, dict] = {}
        for e in entries:
            key = (e.client_id, e.project_id)
            g = groups.setdefault(key, {"hours": 0.0, "amount": Decimal("0"), "unpriced_hours": 0.0})
            g["hours"] += float(e.hours)
            rate = rates_api.get_billable_rate(e.identity_id, e.service_id)
            if rate:
                g["amount"] += e.hours * rate
            else:
                g["unpriced_hours"] += float(e.hours)

        rows = []
        for (client_id, project_id), g in groups.items():
            project = projects_api.get_by_id(project_id) if project_id else None
            rows.append({
                "client": invoices_api.get_client_name(client_id) if client_id else None,
                "project": project.title if project else None,
                "hours": round(g["hours"], 2),
                "amount": str(g["amount"].quantize(Decimal("0.01"))),
                "hours_without_rate": round(g["unpriced_hours"], 2),
            })
        rows.sort(key=lambda r: -Decimal(r["amount"]))
        return {
            "total_hours": round(sum(r["hours"] for r in rows), 2),
            "total_amount": str(sum((Decimal(r["amount"]) for r in rows), Decimal("0"))),
            "by_client_and_project": rows,
        }


@server.tool(annotations=READ)
def get_invoice(invoice_id: int) -> dict:
    """One invoice with its lines and payments."""
    with _client() as client:
        invoice = InvoicesAPI(client).get_invoice(invoice_id)
        if not invoice:
            raise ToolError(f"No invoice with id {invoice_id}.")
        return invoice.model_dump(mode="json")


@server.tool(annotations=READ)
def list_expenses(date_min: Optional[str] = None, date_max: Optional[str] = None, vendor: Optional[str] = None, limit: int = 50) -> dict:
    """Expenses, optionally filtered by date range (YYYY-MM-DD) and vendor."""
    with _client() as client:
        expenses, total = ExpensesAPI(client).list(date_min=date_min, date_max=date_max, vendor=vendor, per_page=min(limit, 100))
        return {"total": total, "expenses": [e.model_dump(mode="json") for e in expenses[:limit]]}


@server.tool(annotations=READ)
def accounts_receivable_aging(end_date: Optional[str] = None) -> dict:
    """Outstanding receivables by client and age bucket, as of end_date (YYYY-MM-DD, default today)."""
    with _client() as client:
        return ReportsAPI(client).get_ar_aging(end_date=end_date).model_dump(mode="json")


@server.tool(annotations=READ)
def profit_and_loss(start_date: str, end_date: str) -> dict:
    """Profit and loss report by month between two dates (YYYY-MM-DD)."""
    with _client() as client:
        return ReportsAPI(client).get_profit_and_loss(start_date=start_date, end_date=end_date).model_dump(mode="json")


@server.tool(annotations=READ)
def list_team() -> dict:
    """Team members and contractors with identity ids and emails."""
    with _client() as client:
        members = TeamAPI(client).get_all_members()
        return {"members": [
            {"identity_id": i, "name": f"{m.get('first_name') or ''} {m.get('last_name') or ''}".strip(),
             "email": m.get("email"), "role": m.get("role"), "active": m.get("active", True)}
            for i, m in members.items()
        ]}


def run() -> None:
    server.run("stdio")
