"""CLI entry point for FreshBooks tools."""

import csv
import json
import sys
from datetime import datetime
from decimal import Decimal
from difflib import get_close_matches
from io import StringIO
from typing import Optional

import click
from rich.console import Console

from .api.client import FreshBooksClient
from .api.expenses import ExpensesAPI
from .api.invoices import InvoicesAPI
from .api.projects import ProjectsAPI
from .api.rates import RatesAPI
from .api.reports import ReportsAPI
from .api.team import TeamAPI
from .api.time_entries import TimeEntriesAPI
from .auth import start_oauth_flow
from .config import (
    delete_tokens,
    load_account_info,
    load_config,
    load_tokens,
)
from .ui.invoice_browser import run_invoice_browser
from .ui.tables import ARAgingTable, ClientARFormatter, ExpenseTable, InvoiceTable, RevenueSummaryTable, TimeEntryRow, TimeEntryTable

console = Console()

RESOLUTION_MAP = {
    "monthly": "m",
    "quarterly": "q",
    "yearly": "y",
}


def parse_month(month_str: str) -> tuple[int, int]:
    """Parse month string in YYYY-MM format."""
    try:
        parts = month_str.split("-")
        year = int(parts[0])
        month = int(parts[1])
        if not (1 <= month <= 12):
            raise ValueError("Month must be between 1 and 12")
        return year, month
    except (IndexError, ValueError) as e:
        raise click.BadParameter(f"Invalid month format. Use YYYY-MM (e.g., 2024-01): {e}")


@click.group()
@click.version_option()
def cli():
    """FreshBooks CLI tools for time entries and invoices."""
    pass


@cli.group()
def auth():
    """Authentication commands."""
    pass


@auth.command("login")
def auth_login():
    """Start OAuth login flow.

    Requires FRESHBOOKS_REDIRECT_URI in .env for ngrok setup.
    """
    try:
        config = load_config()
        console.print("[bold]Starting FreshBooks OAuth login...[/bold]")
        console.print()

        is_default_uri = config.redirect_uri == "http://localhost:8374/callback"
        if is_default_uri:
            console.print("[yellow]Note: FreshBooks requires HTTPS for redirect URIs.[/yellow]")
            console.print()
            console.print("To authenticate, you need to use ngrok:")
            console.print("  1. Run: [cyan]ngrok http 8374[/cyan]")
            console.print("  2. Copy the https URL (e.g., https://abc123.ngrok.io)")
            console.print("  3. Add to .env: [cyan]FRESHBOOKS_REDIRECT_URI=https://abc123.ngrok.io/callback[/cyan]")
            console.print("  4. Add the same URL to your FreshBooks app in Developer Portal")
            console.print("  5. Re-run: [cyan]fb auth login[/cyan]")
            console.print()
            sys.exit(1)

        console.print("[dim]Redirect URI configured:[/dim]")
        console.print(f"[cyan]{config.redirect_uri}[/cyan]")
        console.print()
        console.print("[dim]Make sure this URI is added to your FreshBooks app in the Developer Portal.[/dim]")
        console.print()

        start_oauth_flow(config)

        with FreshBooksClient(config) as client:
            client.ensure_account_info()
            console.print("[green]Account info cached successfully![/green]")

    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Authentication failed:[/red] {e}")
        sys.exit(1)


@auth.command("status")
def auth_status():
    """Show current authentication status."""
    tokens = load_tokens()
    account_id, business_id = load_account_info()

    if tokens:
        console.print("[green]Authenticated[/green]")
        console.print(f"  Token expires: {tokens.expires_at or 'Unknown'}")
        console.print(f"  Account ID: {account_id or 'Not cached'}")
        console.print(f"  Business ID: {business_id or 'Not cached'}")

        if tokens.is_expired:
            console.print("[yellow]  Token is expired - will be refreshed on next request[/yellow]")
    else:
        console.print("[red]Not authenticated[/red]")
        console.print("Run 'fb auth login' to authenticate.")


@auth.command("logout")
def auth_logout():
    """Clear stored authentication tokens."""
    delete_tokens()
    console.print("[green]Logged out successfully.[/green]")


@cli.group()
def time():
    """Time entry commands."""
    pass


@time.command("list")
@click.option("--teammate", "-t", help="Filter by teammate name (partial match)")
@click.option("--month", "-m", help="Filter by month (YYYY-MM format)")
@click.option("--billable/--all", default=True, help="Show only billable entries (default) or all")
@click.option("--show-notes", is_flag=True, help="Show entry notes")
@click.option("--no-rates", is_flag=True, help="Hide rate columns")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def time_list(teammate: Optional[str], month: Optional[str], billable: bool, show_notes: bool, no_rates: bool, as_json: bool):
    """List time entries with optional filters."""
    try:
        config = load_config()

        if not config.tokens:
            console.print("[red]Not authenticated. Run 'fb auth login' first.[/red]")
            sys.exit(1)

        with FreshBooksClient(config) as client:
            time_api = TimeEntriesAPI(client)
            team_api = TeamAPI(client)
            rates_api = RatesAPI(client, team_api, config.rates)
            invoices_api = InvoicesAPI(client)

            identity_id = None
            if teammate:
                identity_id = team_api.find_identity_by_name(teammate)
                if identity_id is None:
                    console.print(f"[red]No teammate found matching '{teammate}'[/red]")
                    sys.exit(1)

            if month:
                year, mon = parse_month(month)
                entries = time_api.list_by_month(
                    year, mon,
                    identity_id=identity_id,
                    billable=billable if billable else None,
                )
                title = f"Time Entries - {year}-{mon:02d}"
            else:
                entries, _ = time_api.list(
                    identity_id=identity_id,
                    billable=billable if billable else None,
                    per_page=100,
                )
                title = "Time Entries"

            if teammate:
                title += f" - {teammate}"

            rows = []
            for entry in entries:
                teammate_name = team_api.get_team_member_name(entry.identity_id)
                client_name = invoices_api.get_client_name(entry.client_id) if entry.client_id else "-"
                project_name = f"Project {entry.project_id}" if entry.project_id else "-"
                service_name = rates_api.get_service_name(entry.service_id) if entry.service_id else "-"

                billable_rate = rates_api.get_billable_rate(entry.identity_id, entry.service_id) if entry.billable else None
                cost_rate = rates_api.get_cost_rate(entry.identity_id)

                rows.append(TimeEntryRow(
                    date=entry.started_at.strftime("%Y-%m-%d"),
                    teammate=teammate_name,
                    client=client_name,
                    project=project_name,
                    service=service_name,
                    hours=entry.hours,
                    billable_rate=billable_rate,
                    cost_rate=cost_rate,
                    note=entry.note or "",
                ))

            if as_json:
                total_hours = sum(r.hours for r in rows)
                total_billable = sum(r.billable_amount or Decimal("0") for r in rows)
                total_cost = sum(r.cost_amount or Decimal("0") for r in rows)
                profit = total_billable - total_cost
                margin = float(profit / total_billable * 100) if total_billable else 0.0
                output = {
                    "entries": [
                        {
                            "date": r.date,
                            "teammate": r.teammate,
                            "client": r.client,
                            "project": r.project,
                            "service": r.service,
                            "hours": float(r.hours),
                            "billable_rate": float(r.billable_rate) if r.billable_rate else None,
                            "cost_rate": float(r.cost_rate) if r.cost_rate else None,
                            "billable_amount": float(r.billable_amount) if r.billable_amount else None,
                            "cost_amount": float(r.cost_amount) if r.cost_amount else None,
                            "note": r.note or None,
                        }
                        for r in rows
                    ],
                    "totals": {
                        "hours": float(total_hours),
                        "billable": float(total_billable),
                        "cost": float(total_cost),
                        "profit": float(profit),
                        "margin": margin,
                    },
                }
                print(json.dumps(output, indent=2))
                return

            if not rows:
                console.print("[yellow]No time entries found.[/yellow]")
                return

            table = TimeEntryTable(console)
            table.print_table(rows, title=title, show_rates=not no_rates, show_notes=show_notes)

    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@time.command("summary")
@click.option("--month", "-m", required=True, help="Month to summarize (YYYY-MM format)")
@click.option("--by-teammate", is_flag=True, help="Group by teammate")
@click.option("--by-client", is_flag=True, help="Group by client")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def time_summary(month: str, by_teammate: bool, by_client: bool, as_json: bool):
    """Show time entry summary for a month."""
    try:
        config = load_config()

        if not config.tokens:
            console.print("[red]Not authenticated. Run 'fb auth login' first.[/red]")
            sys.exit(1)

        year, mon = parse_month(month)

        with FreshBooksClient(config) as client:
            time_api = TimeEntriesAPI(client)
            team_api = TeamAPI(client)
            rates_api = RatesAPI(client, team_api, config.rates)
            invoices_api = InvoicesAPI(client)

            entries = time_api.list_by_month(year, mon)

            if not entries:
                if as_json:
                    print(json.dumps({"month": month, "total_hours": 0, "total_billable": 0, "total_cost": 0, "profit": 0, "margin": 0, "groups": {}}))
                else:
                    console.print(f"[yellow]No time entries found for {year}-{mon:02d}.[/yellow]")
                return

            if as_json:
                _print_time_summary_json(entries, month, by_teammate, by_client, team_api, rates_api, invoices_api)
                return

            if by_teammate:
                groups: dict[str, list] = {}
                for entry in entries:
                    name = team_api.get_team_member_name(entry.identity_id)
                    if name not in groups:
                        groups[name] = []
                    groups[name].append(entry)

                console.print(f"\n[bold]Time Summary by Teammate - {year}-{mon:02d}[/bold]\n")

                for name, group_entries in sorted(groups.items()):
                    total_hours = sum(e.hours for e in group_entries)
                    total_billable = Decimal("0")
                    total_cost = Decimal("0")

                    for entry in group_entries:
                        if entry.billable:
                            rate = rates_api.get_billable_rate(entry.identity_id, entry.service_id)
                            if rate:
                                total_billable += entry.hours * rate
                        cost_rate = rates_api.get_cost_rate(entry.identity_id)
                        if cost_rate:
                            total_cost += entry.hours * cost_rate

                    console.print(f"[green]{name}[/green]")
                    console.print(f"  Hours: [magenta]{total_hours:.2f}[/magenta]")
                    console.print(f"  Billable: [green]${total_billable:.2f}[/green]")
                    console.print(f"  Cost: [red]${total_cost:.2f}[/red]")
                    profit = total_billable - total_cost
                    console.print(f"  Profit: [{'green' if profit >= 0 else 'red'}]${profit:.2f}[/{'green' if profit >= 0 else 'red'}]")
                    console.print()

            elif by_client:
                groups: dict[str, list] = {}
                for entry in entries:
                    name = invoices_api.get_client_name(entry.client_id) if entry.client_id else "No Client"
                    if name not in groups:
                        groups[name] = []
                    groups[name].append(entry)

                console.print(f"\n[bold]Time Summary by Client - {year}-{mon:02d}[/bold]\n")

                for name, group_entries in sorted(groups.items()):
                    total_hours = sum(e.hours for e in group_entries)
                    total_billable = Decimal("0")

                    for entry in group_entries:
                        if entry.billable:
                            rate = rates_api.get_billable_rate(entry.identity_id, entry.service_id)
                            if rate:
                                total_billable += entry.hours * rate

                    console.print(f"[yellow]{name}[/yellow]")
                    console.print(f"  Hours: [magenta]{total_hours:.2f}[/magenta]")
                    console.print(f"  Billable: [green]${total_billable:.2f}[/green]")
                    console.print()

            else:
                total_hours = sum(e.hours for e in entries)
                total_billable = Decimal("0")
                total_cost = Decimal("0")

                for entry in entries:
                    if entry.billable:
                        rate = rates_api.get_billable_rate(entry.identity_id, entry.service_id)
                        if rate:
                            total_billable += entry.hours * rate
                    cost_rate = rates_api.get_cost_rate(entry.identity_id)
                    if cost_rate:
                        total_cost += entry.hours * cost_rate

                console.print(f"\n[bold]Time Summary - {year}-{mon:02d}[/bold]\n")
                console.print(f"Total Entries: {len(entries)}")
                console.print(f"Total Hours: [magenta]{total_hours:.2f}[/magenta]")
                console.print(f"Total Billable: [green]${total_billable:.2f}[/green]")
                console.print(f"Total Cost: [red]${total_cost:.2f}[/red]")
                profit = total_billable - total_cost
                margin = (profit / total_billable * 100) if total_billable else Decimal("0")
                console.print(f"Profit: [{'green' if profit >= 0 else 'red'}]${profit:.2f}[/{'green' if profit >= 0 else 'red'}]")
                console.print(f"Margin: [{'green' if margin >= 0 else 'red'}]{margin:.1f}%[/{'green' if margin >= 0 else 'red'}]")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


def _print_time_summary_json(entries, month, by_teammate, by_client, team_api, rates_api, invoices_api):
    """Build and print JSON output for time summary."""
    total_hours = float(sum(e.hours for e in entries))
    total_billable = Decimal("0")
    total_cost = Decimal("0")

    for entry in entries:
        if entry.billable:
            rate = rates_api.get_billable_rate(entry.identity_id, entry.service_id)
            if rate:
                total_billable += entry.hours * rate
        cost_rate = rates_api.get_cost_rate(entry.identity_id)
        if cost_rate:
            total_cost += entry.hours * cost_rate

    profit = total_billable - total_cost
    margin = float(profit / total_billable * 100) if total_billable else 0.0

    groups = {}
    if by_teammate or by_client:
        group_map: dict[str, list] = {}
        for entry in entries:
            if by_teammate:
                key = team_api.get_team_member_name(entry.identity_id)
            else:
                key = invoices_api.get_client_name(entry.client_id) if entry.client_id else "No Client"
            group_map.setdefault(key, []).append(entry)

        for name, group_entries in sorted(group_map.items()):
            g_hours = float(sum(e.hours for e in group_entries))
            g_billable = Decimal("0")
            g_cost = Decimal("0")
            for entry in group_entries:
                if entry.billable:
                    rate = rates_api.get_billable_rate(entry.identity_id, entry.service_id)
                    if rate:
                        g_billable += entry.hours * rate
                cr = rates_api.get_cost_rate(entry.identity_id)
                if cr:
                    g_cost += entry.hours * cr
            g_profit = g_billable - g_cost
            groups[name] = {
                "hours": g_hours,
                "billable": float(g_billable),
                "cost": float(g_cost),
                "profit": float(g_profit),
            }

    output = {
        "month": month,
        "total_hours": total_hours,
        "total_billable": float(total_billable),
        "total_cost": float(total_cost),
        "profit": float(profit),
        "margin": margin,
        "groups": groups,
    }
    print(json.dumps(output, indent=2))


@time.command("export")
@click.option("--month", "-m", required=True, help="Month to export (YYYY-MM format)")
@click.option("--format", "-f", "fmt", type=click.Choice(["csv"]), default="csv", help="Export format")
@click.option("--output", "-o", help="Output file (default: stdout)")
def time_export(month: str, fmt: str, output: Optional[str]):
    """Export time entries to CSV."""
    try:
        config = load_config()

        if not config.tokens:
            console.print("[red]Not authenticated. Run 'fb auth login' first.[/red]", err=True)
            sys.exit(1)

        year, mon = parse_month(month)

        with FreshBooksClient(config) as client:
            time_api = TimeEntriesAPI(client)
            team_api = TeamAPI(client)
            rates_api = RatesAPI(client, team_api, config.rates)
            invoices_api = InvoicesAPI(client)

            entries = time_api.list_by_month(year, mon)

            if not entries:
                console.print(f"[yellow]No time entries found for {year}-{mon:02d}.[/yellow]", err=True)
                return

            buffer = StringIO()
            writer = csv.writer(buffer)
            writer.writerow([
                "Date", "Teammate", "Client", "Project", "Service",
                "Hours", "Billable Rate", "Cost Rate", "Billable Amount", "Cost Amount", "Note"
            ])

            for entry in entries:
                teammate_name = team_api.get_team_member_name(entry.identity_id)
                client_name = invoices_api.get_client_name(entry.client_id) if entry.client_id else ""
                project_name = f"Project {entry.project_id}" if entry.project_id else ""
                service_name = rates_api.get_service_name(entry.service_id) if entry.service_id else ""

                billable_rate = rates_api.get_billable_rate(entry.identity_id, entry.service_id) if entry.billable else None
                cost_rate = rates_api.get_cost_rate(entry.identity_id)

                billable_amount = entry.hours * billable_rate if billable_rate else None
                cost_amount = entry.hours * cost_rate if cost_rate else None

                writer.writerow([
                    entry.started_at.strftime("%Y-%m-%d"),
                    teammate_name,
                    client_name,
                    project_name,
                    service_name,
                    f"{entry.hours:.2f}",
                    f"{billable_rate:.2f}" if billable_rate else "",
                    f"{cost_rate:.2f}" if cost_rate else "",
                    f"{billable_amount:.2f}" if billable_amount else "",
                    f"{cost_amount:.2f}" if cost_amount else "",
                    entry.note or "",
                ])

            if output:
                with open(output, "w") as f:
                    f.write(buffer.getvalue())
                console.print(f"[green]Exported to {output}[/green]", err=True)
            else:
                print(buffer.getvalue())

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}", err=True)
        sys.exit(1)


@time.command("add")
@click.option("--hours", "-h", required=True, type=float, help="Hours worked")
@click.option("--date", "-d", default=None, help="Date (YYYY-MM-DD), defaults to today")
@click.option("--project", "-p", required=True, help="Project name or fragment")
@click.option("--service", "-s", help="Service/category name or fragment")
@click.option("--note", "-n", help="Note/comment")
@click.option("--billable/--not-billable", default=True, help="Mark as billable")
def time_add(hours: float, date: Optional[str], project: str,
             service: Optional[str], note: Optional[str], billable: bool):
    """Add a new time entry."""
    try:
        config = load_config()

        if not config.tokens:
            console.print("[red]Not authenticated. Run 'fb auth login' first.[/red]")
            sys.exit(1)

        if date:
            try:
                entry_date = datetime.strptime(date, "%Y-%m-%d")
            except ValueError:
                console.print("[red]Invalid date format. Use YYYY-MM-DD.[/red]")
                sys.exit(1)
        else:
            entry_date = datetime.now()

        entry_date = entry_date.replace(hour=9, minute=0, second=0, microsecond=0)

        duration_seconds = int(hours * 3600)

        with FreshBooksClient(config) as client:
            projects_api = ProjectsAPI(client)
            team_api = TeamAPI(client)
            rates_api = RatesAPI(client, team_api, config.rates)
            time_api = TimeEntriesAPI(client)

            matching_projects = projects_api.find_by_name(project)

            if not matching_projects:
                all_projects = projects_api.list()
                console.print(f"[red]No projects found matching '{project}'[/red]")
                if all_projects:
                    console.print("\n[yellow]Available projects:[/yellow]")
                    for p in all_projects[:10]:
                        console.print(f"  - {p.title}")
                    if len(all_projects) > 10:
                        console.print(f"  ... and {len(all_projects) - 10} more")
                sys.exit(1)
            elif len(matching_projects) == 1:
                selected_project = matching_projects[0]
            else:
                console.print(f"[yellow]Multiple projects match '{project}':[/yellow]")
                for i, p in enumerate(matching_projects, 1):
                    console.print(f"  {i}. {p.title}")

                choice = click.prompt(
                    f"Select project [1-{len(matching_projects)}]",
                    type=click.IntRange(1, len(matching_projects))
                )
                selected_project = matching_projects[choice - 1]

            service_id = None
            service_name = None
            if service:
                project_with_services = projects_api.get_with_services(selected_project.id)
                services = project_with_services.services if project_with_services else []
                service_lower = service.lower()
                matching_services = [s for s in services if service_lower in s.name.lower()]

                if not matching_services:
                    console.print(f"[red]No services found matching '{service}' for project '{selected_project.title}'[/red]")
                    if services:
                        console.print("\n[yellow]Available services for this project:[/yellow]")
                        for s in services:
                            console.print(f"  - {s.name}")
                    else:
                        console.print("[yellow]This project has no services configured.[/yellow]")
                    sys.exit(1)
                elif len(matching_services) == 1:
                    service_id = matching_services[0].id
                    service_name = matching_services[0].name
                else:
                    console.print(f"[yellow]Multiple services match '{service}':[/yellow]")
                    for i, s in enumerate(matching_services, 1):
                        console.print(f"  {i}. {s.name}")

                    choice = click.prompt(
                        f"Select service [1-{len(matching_services)}]",
                        type=click.IntRange(1, len(matching_services))
                    )
                    service_id = matching_services[choice - 1].id
                    service_name = matching_services[choice - 1].name

            entry = time_api.create(
                started_at=entry_date,
                duration_seconds=duration_seconds,
                project_id=selected_project.id,
                client_id=selected_project.client_id,
                service_id=service_id,
                note=note,
                billable=billable,
            )

            msg = f"Added {hours:.2f} hours to \"{selected_project.title}\""
            if service_name:
                msg += f" ({service_name})"
            console.print(f"[green]{msg}[/green]")

            if note:
                console.print(f"[dim]Note: {note}[/dim]")
            console.print(f"[dim]Date: {entry_date.strftime('%Y-%m-%d')}[/dim]")
            console.print(f"[dim]Entry ID: {entry.id}[/dim]")

    except click.Abort:
        console.print("\n[yellow]Cancelled.[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@time.command("unbilled")
@click.option("--by-client", is_flag=True, help="Group by client")
@click.option("--by-project", is_flag=True, help="Group by project")
@click.option("--by-teammate", is_flag=True, help="Group by teammate")
@click.option("--before", "before_date", help="Only entries before date (YYYY-MM-DD)")
@click.option("--after", "after_date", help="Only entries after date (YYYY-MM-DD)")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def time_unbilled(by_client: bool, by_project: bool, by_teammate: bool,
                  before_date: Optional[str], after_date: Optional[str], as_json: bool):
    """Show unbilled billable time entries."""
    try:
        config = load_config()

        if not config.tokens:
            console.print("[red]Not authenticated. Run 'fb auth login' first.[/red]")
            sys.exit(1)

        started_from = None
        started_to = None

        if before_date:
            try:
                started_to = datetime.strptime(before_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            except ValueError:
                console.print("[red]Invalid date format for --before. Use YYYY-MM-DD.[/red]")
                sys.exit(1)

        if after_date:
            try:
                started_from = datetime.strptime(after_date, "%Y-%m-%d")
            except ValueError:
                console.print("[red]Invalid date format for --after. Use YYYY-MM-DD.[/red]")
                sys.exit(1)

        with FreshBooksClient(config) as client:
            time_api = TimeEntriesAPI(client)
            team_api = TeamAPI(client)
            rates_api = RatesAPI(client, team_api, config.rates)
            invoices_api = InvoicesAPI(client)
            projects_api = ProjectsAPI(client)

            entries = time_api.list_all(
                billed=False,
                billable=True,
                started_from=started_from,
                started_to=started_to,
            )

            if not entries:
                if as_json:
                    print(json.dumps({"entries": [], "total_hours": 0, "total_amount": 0}))
                else:
                    console.print("[yellow]No unbilled time entries found.[/yellow]")
                return

            total_hours = sum(float(e.hours) for e in entries)
            total_amount = Decimal("0")

            for e in entries:
                rate = rates_api.get_billable_rate(e.identity_id, e.service_id)
                if rate:
                    total_amount += e.hours * rate

            if as_json:
                groups = {}
                for e in entries:
                    if by_teammate:
                        key = team_api.get_team_member_name(e.identity_id)
                    elif by_project:
                        proj = projects_api.get_by_id(e.project_id) if e.project_id else None
                        key = proj.title if proj else "No Project"
                    else:
                        key = invoices_api.get_client_name(e.client_id) if e.client_id else "No Client"

                    if key not in groups:
                        groups[key] = {"hours": 0, "amount": 0}
                    groups[key]["hours"] += float(e.hours)
                    rate = rates_api.get_billable_rate(e.identity_id, e.service_id)
                    if rate:
                        groups[key]["amount"] += float(e.hours * rate)

                output = {
                    "total_hours": total_hours,
                    "total_amount": float(total_amount),
                    "groups": groups,
                }
                print(json.dumps(output, indent=2))
                return

            if by_project:
                groups: dict[str, list] = {}
                for e in entries:
                    proj = projects_api.get_by_id(e.project_id) if e.project_id else None
                    key = proj.title if proj else "No Project"
                    groups.setdefault(key, []).append(e)
                group_label = "Project"
            elif by_teammate:
                groups: dict[str, list] = {}
                for e in entries:
                    key = team_api.get_team_member_name(e.identity_id)
                    groups.setdefault(key, []).append(e)
                group_label = "Teammate"
            else:
                groups: dict[str, list] = {}
                for e in entries:
                    key = invoices_api.get_client_name(e.client_id) if e.client_id else "No Client"
                    groups.setdefault(key, []).append(e)
                group_label = "Client"

            console.print(f"\n[bold]Unbilled Time by {group_label}[/bold]\n")

            for name, group_entries in sorted(groups.items()):
                group_hours = sum(float(e.hours) for e in group_entries)
                group_amount = Decimal("0")
                for e in group_entries:
                    rate = rates_api.get_billable_rate(e.identity_id, e.service_id)
                    if rate:
                        group_amount += e.hours * rate

                console.print(f"[cyan]{name}[/cyan]")
                console.print(f"  Hours: [magenta]{group_hours:.2f}[/magenta]")
                console.print(f"  Amount: [green]${group_amount:,.2f}[/green]")
                console.print()

            console.print("[bold]" + "-" * 40 + "[/bold]")
            console.print(f"[bold]Total Hours:[/bold] [magenta]{total_hours:.2f}[/magenta]")
            console.print(f"[bold]Total Unbilled:[/bold] [green]${total_amount:,.2f}[/green]")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@cli.group()
def invoices():
    """Invoice commands."""
    pass


@invoices.command("browse")
def invoices_browse():
    """Launch interactive invoice browser."""
    try:
        config = load_config()

        if not config.tokens:
            console.print("[red]Not authenticated. Run 'fb auth login' first.[/red]")
            sys.exit(1)

        run_invoice_browser(config)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@invoices.command("list")
@click.option("--client", "-c", help="Filter by client name (partial match)")
@click.option("--status", "-s", type=click.Choice(["draft", "sent", "viewed", "paid", "partial", "overdue"]), help="Filter by status")
@click.option("--limit", "-l", default=50, help="Maximum number of invoices to show")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def invoices_list(client: Optional[str], status: Optional[str], limit: int, as_json: bool):
    """List invoices (non-interactive)."""
    try:
        config = load_config()

        if not config.tokens:
            console.print("[red]Not authenticated. Run 'fb auth login' first.[/red]")
            sys.exit(1)

        with FreshBooksClient(config) as fb_client:
            invoices_api = InvoicesAPI(fb_client)

            customer_id = None
            if client:
                clients = invoices_api.list_clients()
                matching = [c for c in clients if client.lower() in c.display_name.lower()]
                if not matching:
                    console.print(f"[red]No client found matching '{client}'[/red]")
                    sys.exit(1)
                if len(matching) > 1:
                    console.print(f"[yellow]Multiple clients match '{client}':[/yellow]")
                    for c in matching:
                        console.print(f"  - {c.display_name}")
                    sys.exit(1)
                customer_id = matching[0].id

            all_invoices = invoices_api.list_all_invoices(
                customer_id=customer_id,
                status=status,
            )

            all_invoices = sorted(all_invoices, key=lambda i: i.create_date, reverse=True)[:limit]

            if as_json:
                total_amount = sum(i.amount or Decimal("0") for i in all_invoices)
                total_paid = sum(i.paid or Decimal("0") for i in all_invoices)
                total_outstanding = sum(i.outstanding or Decimal("0") for i in all_invoices)
                output = {
                    "invoices": [
                        {
                            "id": inv.id,
                            "invoice_number": inv.invoice_number,
                            "client": inv.client_name,
                            "create_date": inv.create_date,
                            "due_date": inv.due_date,
                            "status": inv.display_status,
                            "currency": inv.currency_code,
                            "amount": float(inv.amount) if inv.amount else None,
                            "paid": float(inv.paid) if inv.paid else None,
                            "outstanding": float(inv.outstanding) if inv.outstanding else None,
                        }
                        for inv in all_invoices
                    ],
                    "totals": {
                        "amount": float(total_amount),
                        "paid": float(total_paid),
                        "outstanding": float(total_outstanding),
                    },
                }
                print(json.dumps(output, indent=2))
                return

            if not all_invoices:
                console.print("[yellow]No invoices found.[/yellow]")
                return

            title = "Invoices"
            if client:
                title += f" - {client}"
            if status:
                title += f" ({status})"

            table = InvoiceTable(console)
            table.print_table(all_invoices, title=title)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@invoices.command("show")
@click.argument("invoice_number")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def invoices_show(invoice_number: str, as_json: bool):
    """Show details for a specific invoice."""
    try:
        config = load_config()

        if not config.tokens:
            console.print("[red]Not authenticated. Run 'fb auth login' first.[/red]")
            sys.exit(1)

        with FreshBooksClient(config) as fb_client:
            invoices_api = InvoicesAPI(fb_client)

            all_invoices = invoices_api.list_all_invoices(include_lines=True, include_payments=True)

            invoice = None
            for inv in all_invoices:
                if inv.invoice_number == invoice_number or str(inv.id) == invoice_number:
                    invoice = inv
                    break

            if not invoice:
                if as_json:
                    print(json.dumps({"error": f"Invoice '{invoice_number}' not found"}))
                else:
                    console.print(f"[red]Invoice '{invoice_number}' not found.[/red]")
                sys.exit(1)

            if as_json:
                output = {
                    "invoice": {
                        "id": invoice.id,
                        "invoice_number": invoice.invoice_number,
                        "client": invoice.client_name,
                        "create_date": invoice.create_date,
                        "due_date": invoice.due_date,
                        "status": invoice.display_status,
                        "currency": invoice.currency_code,
                        "amount": float(invoice.amount) if invoice.amount else None,
                        "paid": float(invoice.paid) if invoice.paid else None,
                        "outstanding": float(invoice.outstanding) if invoice.outstanding else None,
                        "discount": float(invoice.discount_value) if invoice.discount_value else None,
                        "lines": [
                            {
                                "name": line.name,
                                "description": line.description,
                                "qty": float(line.qty) if line.qty else None,
                                "unit_cost": float(line.unit_cost) if line.unit_cost else None,
                                "amount": float(line.amount) if line.amount else None,
                                "type": line.type,
                            }
                            for line in (invoice.lines or [])
                        ],
                        "payments": [
                            {
                                "id": p.id,
                                "amount": float(p.amount) if p.amount else None,
                                "date": p.date,
                                "type": p.type,
                                "note": p.note,
                                "gateway": p.gateway,
                            }
                            for p in (invoice.payments or [])
                        ],
                    }
                }
                print(json.dumps(output, indent=2))
                return

            table = InvoiceTable(console)
            table.print_invoice_detail(invoice)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@cli.group()
def reports():
    """Financial reporting commands."""
    pass


@reports.command("ar-aging")
@click.option("--start-date", help="Filter invoices created after this date (YYYY-MM-DD)")
@click.option("--end-date", help="Report date (YYYY-MM-DD), defaults to today")
@click.option("--currency", help="Filter by currency code (e.g., USD, CAD)")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@click.option("--export", type=click.Choice(["csv"]), help="Export format")
@click.option("--output", "-o", help="Output file path (default: auto-generated)")
def reports_ar_aging(start_date: Optional[str], end_date: Optional[str], currency: Optional[str], as_json: bool, export: Optional[str], output: Optional[str]):
    """Generate accounts receivable aging report."""
    try:
        config = load_config()
        if not config.tokens:
            console.print("[red]Not authenticated. Run: fb auth login[/red]")
            sys.exit(1)

        with FreshBooksClient(config) as client:
            reports_api = ReportsAPI(client)
            report = reports_api.get_ar_aging(
                start_date=start_date,
                end_date=end_date,
                currency_code=currency
            )

            if export == "csv":
                from .ui.exporters import export_ar_aging_csv
                filepath = export_ar_aging_csv(report, output)
                console.print(f"[green]Exported to {filepath}[/green]", err=True)
                return

            if as_json:
                import json
                output = json.dumps(
                    report.model_dump(),
                    default=str,
                    indent=2
                )
                click.echo(output)
            else:
                table = ARAgingTable(console)
                table.print_report(report)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@reports.command("client-ar")
@click.option("--client-id", type=int, help="Client ID for exact lookup")
@click.option("--client-name", help="Client name for fuzzy lookup")
@click.option("--detail", is_flag=True, help="Show bucket breakdown instead of compact output")
@click.option("--currency", help="Filter by currency code (e.g., USD, CAD)")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@click.option("--export", type=click.Choice(["csv"]), help="Export format")
@click.option("--output", "-o", help="Output file path (default: auto-generated)")
def reports_client_ar(client_id: Optional[int], client_name: Optional[str], detail: bool, currency: Optional[str], as_json: bool, export: Optional[str], output: Optional[str]):
    """Query outstanding balance for a specific client by ID or name."""
    try:
        config = load_config()
        if not config.tokens:
            console.print("[red]Not authenticated. Run: fb auth login[/red]")
            sys.exit(1)

        if not client_id and not client_name:
            console.print("[red]Error: Must specify either --client-id or --client-name[/red]")
            sys.exit(1)

        if client_id and client_name:
            console.print("[yellow]Note: Using --client-id, ignoring --client-name[/yellow]")
            client_name = None

        with FreshBooksClient(config) as client:
            reports_api = ReportsAPI(client)
            invoices_api = InvoicesAPI(client)

            report = reports_api.get_ar_aging(currency_code=currency)

            formatter = ClientARFormatter(console)

            account = None
            matched_name = None
            matched_id = None

            if client_id:
                account = formatter.find_client_by_id(report.accounts, client_id)
                if account:
                    matched_name = formatter.get_client_name_from_account(account)
                    matched_id = client_id
            else:
                account, matched_name = formatter.find_client_by_name(report.accounts, client_name)
                if account:
                    matched_id = account.get("userid")

            if not account:
                all_clients = invoices_api.list_clients()

                if client_id:
                    for c in all_clients:
                        if c.id == client_id:
                            matched_name = c.display_name
                            matched_id = c.id
                            break
                else:
                    client_names = [c.display_name for c in all_clients]
                    matches = get_close_matches(client_name, client_names, n=1, cutoff=0.6)
                    if matches:
                        matched = next(c for c in all_clients if c.display_name == matches[0])
                        matched_name = matched.display_name
                        matched_id = matched.id

            if not matched_name:
                if as_json:
                    import json
                    print(json.dumps({"error": "Client not found"}))
                else:
                    console.print("[red]Error: Client not found[/red]")
                sys.exit(1)

            if export == "csv":
                from .ui.exporters import export_client_ar_csv
                if not account:
                    # Create zero-balance account dict
                    account = {
                        "0-30": 0,
                        "31-60": 0,
                        "61-90": 0,
                        "91+": 0,
                        "total": 0,
                    }
                filepath = export_client_ar_csv(matched_name, account, report.currency_code, output)
                console.print(f"[green]Exported to {filepath}[/green]", err=True)
                return

            if not account:
                if as_json:
                    import json
                    output = {
                        "client_name": matched_name,
                        "client_id": matched_id,
                        "total": 0.0,
                        "currency": report.currency_code,
                        "has_outstanding": False,
                    }
                    print(json.dumps(output, indent=2))
                else:
                    console.print(f"Matched: {matched_name} (ID: {matched_id})")
                    console.print(f"$0.00 outstanding ({report.currency_code})")
            else:
                total = account.get("total", {}).get("amount", 0) if isinstance(account.get("total"), dict) else account.get("total", 0)
                total_decimal = Decimal(str(total))
                worst_bucket = formatter.get_worst_bucket(account)

                if as_json:
                    import json
                    output = {
                        "client_name": matched_name,
                        "client_id": matched_id,
                        "total": float(total_decimal),
                        "currency": report.currency_code,
                        "has_outstanding": True,
                    }

                    if detail:
                        buckets = {}
                        for bucket_key in ["0-30", "31-60", "61-90", "91+"]:
                            amount = formatter._get_bucket_amount(account, bucket_key)
                            buckets[bucket_key] = float(amount)
                        output["buckets"] = buckets

                    print(json.dumps(output, indent=2))
                else:
                    console.print(f"Matched: {matched_name} (ID: {matched_id})")
                    if detail:
                        formatter.print_detail(matched_name, account, report.currency_code)
                    else:
                        formatter.print_compact(matched_name, total_decimal, worst_bucket, report.currency_code)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@reports.command("revenue")
@click.option("--start-date", required=True, help="Report start date (YYYY-MM-DD)")
@click.option("--end-date", required=True, help="Report end date (YYYY-MM-DD)")
@click.option(
    "--resolution",
    type=click.Choice(["monthly", "quarterly", "yearly"]),
    default="monthly",
    help="Period grouping resolution"
)
@click.option("--currency", help="Filter by currency code (e.g., USD, CAD)")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@click.option("--export", type=click.Choice(["csv"]), help="Export format")
@click.option("--output", "-o", help="Output file path (default: auto-generated)")
def reports_revenue(
    start_date: str,
    end_date: str,
    resolution: str,
    currency: Optional[str],
    as_json: bool,
    export: Optional[str],
    output: Optional[str]
):
    """Generate revenue summary report with DSO metric."""
    try:
        config = load_config()
        if not config.tokens:
            console.print("[red]Not authenticated. Run: fb auth login[/red]")
            sys.exit(1)

        with FreshBooksClient(config) as client:
            reports_api = ReportsAPI(client)

            api_resolution = RESOLUTION_MAP[resolution]
            pl_report = reports_api.get_profit_and_loss(
                start_date=start_date,
                end_date=end_date,
                resolution=api_resolution,
                currency_code=currency,
            )

            ar_report = reports_api.get_ar_aging(
                end_date=end_date,
                currency_code=currency,
            )
            ar_balance = ar_report.totals.total.amount
            report_currency = currency or ar_report.currency_code

            if export == "csv":
                from .ui.exporters import export_revenue_csv
                filepath = export_revenue_csv(pl_report, ar_balance, report_currency, output)
                console.print(f"[green]Exported to {filepath}[/green]", err=True)
                return

            if as_json:
                import json
                from .api.reports import calculate_dso, get_days_in_period

                periods_output = []
                for period in pl_report.income:
                    start = datetime.strptime(period.start_date, "%Y-%m-%d")
                    days = get_days_in_period(start.year, start.month, api_resolution)
                    dso = calculate_dso(ar_balance, period.total.amount, days)

                    periods_output.append({
                        "start_date": period.start_date,
                        "end_date": period.end_date,
                        "revenue": float(period.total.amount),
                        "dso": float(dso) if dso else None,
                    })

                output = {
                    "periods": periods_output,
                    "total_revenue": float(sum(p.total.amount for p in pl_report.income)),
                    "ar_balance": float(ar_balance),
                    "currency": report_currency,
                    "resolution": resolution,
                }
                click.echo(json.dumps(output, indent=2))
            else:
                table = RevenueSummaryTable(console)
                table.print_report(pl_report, ar_balance, report_currency)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@cli.group()
def expenses():
    """Expense commands."""
    pass


@expenses.command("list")
@click.option("--start-date", help="Start date (YYYY-MM-DD)")
@click.option("--end-date", help="End date (YYYY-MM-DD)")
@click.option("--category", help="Filter by category name (partial match)")
@click.option("--vendor", help="Filter by vendor name (partial match)")
@click.option("--status", type=click.Choice(["internal", "outstanding", "invoiced", "recouped"]), help="Filter by status")
@click.option("--limit", "-l", default=100, help="Maximum number to show")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def expenses_list(start_date: Optional[str], end_date: Optional[str], category: Optional[str], vendor: Optional[str], status: Optional[str], limit: int, as_json: bool):
    """List expenses with optional filters."""
    STATUS_MAP = {
        "internal": 0,
        "outstanding": 1,
        "invoiced": 2,
        "recouped": 4,
    }

    try:
        config = load_config()

        if not config.tokens:
            console.print("[red]Not authenticated. Run 'fb auth login' first.[/red]")
            sys.exit(1)

        with FreshBooksClient(config) as client:
            expenses_api = ExpensesAPI(client)

            category_id = None
            if category:
                all_categories = expenses_api.list_categories()
                category_lower = category.lower()
                matching = [c for c in all_categories if category_lower in c.name.lower()]

                if not matching:
                    console.print(f"[red]No category found matching '{category}'[/red]")
                    console.print("\n[yellow]Available categories:[/yellow]")
                    for c in all_categories[:15]:
                        console.print(f"  - {c.name}")
                    if len(all_categories) > 15:
                        console.print(f"  ... and {len(all_categories) - 15} more")
                    sys.exit(1)
                elif len(matching) > 1:
                    console.print(f"[yellow]Multiple categories match '{category}':[/yellow]")
                    for c in matching:
                        console.print(f"  - {c.name}")
                    sys.exit(1)
                else:
                    category_id = matching[0].id

            status_code = STATUS_MAP.get(status) if status else None

            all_expenses = expenses_api.list_all(
                date_min=start_date,
                date_max=end_date,
                categoryid=category_id,
                vendor=vendor,
                status=status_code,
            )

            all_expenses = sorted(all_expenses, key=lambda e: e.date, reverse=True)[:limit]

            if as_json:
                total_amount = sum(e.total_amount for e in all_expenses)
                output = {
                    "expenses": [
                        {
                            "id": exp.id,
                            "date": exp.date,
                            "vendor": exp.vendor,
                            "category": expenses_api.get_category_name(exp.categoryid) if exp.categoryid else None,
                            "category_id": exp.categoryid,
                            "status": exp.display_status,
                            "currency": exp.currency_code,
                            "amount": float(exp.amount),
                            "tax1": float(exp.taxAmount1) if exp.taxAmount1 else None,
                            "tax2": float(exp.taxAmount2) if exp.taxAmount2 else None,
                            "total_amount": float(exp.total_amount),
                            "notes": exp.notes,
                            "invoice_id": exp.invoiceid,
                        }
                        for exp in all_expenses
                    ],
                    "total_amount": float(total_amount),
                    "count": len(all_expenses),
                }
                print(json.dumps(output, indent=2))
                return

            if not all_expenses:
                console.print("[yellow]No expenses found.[/yellow]")
                return

            title = "Expenses"
            if category:
                title += f" - {category}"
            if status:
                title += f" ({status})"

            expense_table = ExpenseTable(console)
            expense_table.print_table(all_expenses, expenses_api.get_category_name, title=title)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@expenses.command("show")
@click.argument("expense_id", type=int)
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def expenses_show(expense_id: int, as_json: bool):
    """Show details for a specific expense."""
    try:
        config = load_config()

        if not config.tokens:
            console.print("[red]Not authenticated. Run 'fb auth login' first.[/red]")
            sys.exit(1)

        with FreshBooksClient(config) as client:
            expenses_api = ExpensesAPI(client)

            expense = expenses_api.get(expense_id)

            if not expense:
                if as_json:
                    print(json.dumps({"error": f"Expense {expense_id} not found"}))
                else:
                    console.print(f"[red]Expense {expense_id} not found.[/red]")
                sys.exit(1)

            if as_json:
                output = {
                    "expense": {
                        "id": expense.id,
                        "date": expense.date,
                        "vendor": expense.vendor,
                        "category": expenses_api.get_category_name(expense.categoryid) if expense.categoryid else None,
                        "category_id": expense.categoryid,
                        "status": expense.display_status,
                        "currency": expense.currency_code,
                        "amount": float(expense.amount),
                        "tax1_name": expense.taxName1,
                        "tax1_amount": float(expense.taxAmount1) if expense.taxAmount1 else None,
                        "tax2_name": expense.taxName2,
                        "tax2_amount": float(expense.taxAmount2) if expense.taxAmount2 else None,
                        "total_amount": float(expense.total_amount),
                        "notes": expense.notes,
                        "invoice_id": expense.invoiceid,
                        "client_id": expense.clientid,
                        "project_id": expense.projectid,
                        "staff_id": expense.staffid,
                    }
                }
                print(json.dumps(output, indent=2))
                return

            expense_table = ExpenseTable(console)
            expense_table.print_expense_detail(expense, expenses_api.get_category_name)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@cli.command("rates-init")
@click.option("--output", "-o", help="Output file path (default: ~/.config/freshbooks-tools/rates.yaml)")
def rates_init(output: Optional[str]):
    """Generate a rates.yaml template with all team members."""
    from .config import CONFIG_DIR, RATES_FILE, ensure_config_dir

    try:
        config = load_config()

        if not config.tokens:
            console.print("[red]Not authenticated. Run 'fb auth login' first.[/red]")
            sys.exit(1)

        with FreshBooksClient(config) as client:
            team_api = TeamAPI(client)
            rates_api = RatesAPI(client, team_api, config.rates)

            console.print("[dim]Fetching team members and rates...[/dim]")
            all_members = team_api.get_all_members()
            api_rates = rates_api.get_team_member_rates()

            lines = [
                "# FreshBooks Team Member Rates Configuration",
                "# Generated by: fb rates-init",
                "#",
                "# Cost rates are what you pay your team members.",
                "# Billable rates are what you charge clients (pulled from API if not overridden here).",
                "#",
                "# You can set a default rate that applies to all members without a specific rate:",
                "# default_cost_rate: 50.00",
                "# default_billable_rate: 150.00",
                "",
                "# Team members by identity_id:",
                "members:",
            ]

            for identity_id, m in sorted(all_members.items(), key=lambda x: f"{x[1].get('first_name', '')} {x[1].get('last_name', '')}"):
                name = f"{m.get('first_name', '')} {m.get('last_name', '')}".strip() or "Unknown"
                email = m.get("email") or "unknown"
                api_rate = api_rates.get(identity_id)

                lines.append(f"  {identity_id}:")
                lines.append(f"    name: \"{name}\"")
                lines.append(f"    email: \"{email}\"")
                lines.append(f"    cost_rate: 0.00  # TODO: Set actual cost rate")
                if api_rate:
                    lines.append(f"    # billable_rate: {api_rate}  # From API - uncomment to override")
                else:
                    lines.append(f"    billable_rate: 0.00  # TODO: Set billable rate")
                lines.append("")

            content = "\n".join(lines)

            output_path = output or str(RATES_FILE)
            if output_path == str(RATES_FILE):
                ensure_config_dir()

            with open(output_path, "w") as f:
                f.write(content)

            console.print(f"\n[green]Rates template generated:[/green] {output_path}")
            console.print(f"\nFound {len(all_members)} team members.")
            console.print("\n[yellow]Next steps:[/yellow]")
            console.print("  1. Edit the file to add cost rates for each team member")
            console.print("  2. Optionally override billable rates if needed")
            console.print("  3. Run 'fb time list' or 'fb time summary' to see the rates applied")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@cli.command("team")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def team_list(as_json: bool):
    """List team members and contractors."""
    try:
        config = load_config()

        if not config.tokens:
            console.print("[red]Not authenticated. Run 'fb auth login' first.[/red]")
            sys.exit(1)

        with FreshBooksClient(config) as client:
            team_api = TeamAPI(client)
            rates_api = RatesAPI(client, team_api, config.rates)

            all_members = team_api.get_all_members()

            if as_json:
                members_list = []
                for identity_id, m in sorted(all_members.items(), key=lambda x: f"{x[1].get('first_name', '')} {x[1].get('last_name', '')}"):
                    name = f"{m.get('first_name', '')} {m.get('last_name', '')}".strip() or "Unknown"
                    billable_rate = rates_api.get_billable_rate(identity_id)
                    cost_rate = rates_api.get_cost_rate(identity_id)
                    members_list.append({
                        "identity_id": identity_id,
                        "name": name,
                        "email": m.get("email"),
                        "company": m.get("company"),
                        "role": m.get("role") or "contractor",
                        "active": m.get("active", True),
                        "billable_rate": float(billable_rate) if billable_rate else None,
                        "cost_rate": float(cost_rate) if cost_rate else None,
                    })
                print(json.dumps({"members": members_list}, indent=2))
                return

            console.print("\n[dim]Fetching team members from projects...[/dim]")

            console.print(f"\n[bold]Team Members & Contractors ({len(all_members)} total)[/bold]\n")

            for identity_id, m in sorted(all_members.items(), key=lambda x: f"{x[1].get('first_name', '')} {x[1].get('last_name', '')}"):
                name = f"{m.get('first_name', '')} {m.get('last_name', '')}".strip() or "Unknown"
                status = "[green]Active[/green]" if m.get("active", True) else "[red]Inactive[/red]"

                console.print(f"  [bold]{name}[/bold]")
                console.print(f"    Email: {m.get('email') or 'N/A'}")
                if m.get("company"):
                    console.print(f"    Company: {m.get('company')}")
                console.print(f"    Role: {m.get('role') or 'contractor'}")
                console.print(f"    Identity ID: {identity_id}")
                console.print(f"    Status: {status}")

                billable_rate = rates_api.get_billable_rate(identity_id)
                if billable_rate:
                    console.print(f"    Billable Rate: [green]${billable_rate:.2f}/hr[/green]")
                else:
                    console.print(f"    Billable Rate: [dim]Not set[/dim]")

                cost_rate = rates_api.get_cost_rate(identity_id)
                if cost_rate:
                    console.print(f"    Cost Rate: [yellow]${cost_rate:.2f}/hr[/yellow]")
                else:
                    console.print(f"    Cost Rate: [dim]Not configured[/dim]")

                console.print()

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


if __name__ == "__main__":
    cli()
