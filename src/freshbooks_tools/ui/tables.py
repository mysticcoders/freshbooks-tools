"""Rich table formatters for CLI output."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from difflib import get_close_matches
from typing import TYPE_CHECKING, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ..models import AccountAgingReport, Expense, Invoice, TimeEntry

if TYPE_CHECKING:
    from ..models import ProfitLossReport


@dataclass
class TimeEntryRow:
    """Processed time entry row for display."""

    date: str
    teammate: str
    client: str
    project: str
    service: str
    hours: Decimal
    billable_rate: Optional[Decimal]
    cost_rate: Optional[Decimal]
    note: str

    @property
    def billable_amount(self) -> Optional[Decimal]:
        """Calculate billable amount."""
        if self.billable_rate is None:
            return None
        return self.hours * self.billable_rate

    @property
    def cost_amount(self) -> Optional[Decimal]:
        """Calculate cost amount."""
        if self.cost_rate is None:
            return None
        return self.hours * self.cost_rate


class TimeEntryTable:
    """Rich table formatter for time entries."""

    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()

    def create_table(
        self,
        rows: list[TimeEntryRow],
        title: Optional[str] = None,
        show_rates: bool = True,
        show_notes: bool = False,
    ) -> Table:
        """Create a Rich table from time entry rows."""
        table = Table(title=title, show_footer=True)

        table.add_column("Date", style="cyan", no_wrap=True)
        table.add_column("Teammate", style="green")
        table.add_column("Client", style="yellow")
        table.add_column("Project", style="blue")
        table.add_column("Hours", justify="right", style="magenta")

        if show_rates:
            table.add_column("Bill Rate", justify="right")
            table.add_column("Cost Rate", justify="right")
            table.add_column("Billable $", justify="right", style="green")
            table.add_column("Cost $", justify="right", style="red")

        if show_notes:
            table.add_column("Note", max_width=30)

        total_hours = Decimal("0")
        total_billable = Decimal("0")
        total_cost = Decimal("0")

        for row in rows:
            total_hours += row.hours

            cells = [
                row.date,
                row.teammate,
                row.client,
                row.project,
                f"{row.hours:.2f}",
            ]

            if show_rates:
                billable_rate_str = f"${row.billable_rate:.2f}" if row.billable_rate else "-"
                cost_rate_str = f"${row.cost_rate:.2f}" if row.cost_rate else "-"

                billable_amt = row.billable_amount
                cost_amt = row.cost_amount

                billable_str = f"${billable_amt:.2f}" if billable_amt else "-"
                cost_str = f"${cost_amt:.2f}" if cost_amt else "-"

                if billable_amt:
                    total_billable += billable_amt
                if cost_amt:
                    total_cost += cost_amt

                cells.extend([billable_rate_str, cost_rate_str, billable_str, cost_str])

            if show_notes:
                note = row.note[:27] + "..." if len(row.note) > 30 else row.note
                cells.append(note)

            table.add_row(*cells)

        footer_cells = ["", "", "", "TOTAL", f"{total_hours:.2f}"]
        if show_rates:
            profit = total_billable - total_cost
            margin = (profit / total_billable * 100) if total_billable else Decimal("0")

            footer_cells.extend([
                "",
                "",
                f"[bold green]${total_billable:.2f}[/bold green]",
                f"[bold red]${total_cost:.2f}[/bold red]",
            ])

        if show_notes:
            footer_cells.append("")

        table.columns[0].footer = ""
        table.columns[1].footer = ""
        table.columns[2].footer = ""
        table.columns[3].footer = Text("TOTAL", style="bold")
        table.columns[4].footer = Text(f"{total_hours:.2f}", style="bold magenta")

        if show_rates:
            table.columns[5].footer = ""
            table.columns[6].footer = ""
            table.columns[7].footer = Text(f"${total_billable:.2f}", style="bold green")
            table.columns[8].footer = Text(f"${total_cost:.2f}", style="bold red")

        return table

    def print_table(
        self,
        rows: list[TimeEntryRow],
        title: Optional[str] = None,
        show_rates: bool = True,
        show_notes: bool = False,
    ) -> None:
        """Print the time entries table."""
        table = self.create_table(rows, title, show_rates, show_notes)
        self.console.print(table)

        if show_rates and rows:
            total_hours = sum(r.hours for r in rows)
            total_billable = sum(r.billable_amount or Decimal("0") for r in rows)
            total_cost = sum(r.cost_amount or Decimal("0") for r in rows)
            profit = total_billable - total_cost
            margin = (profit / total_billable * 100) if total_billable else Decimal("0")

            self.console.print()
            self.console.print(f"[bold]Summary:[/bold]")
            self.console.print(f"  Total Hours: [magenta]{total_hours:.2f}[/magenta]")
            self.console.print(f"  Total Billable: [green]${total_billable:.2f}[/green]")
            self.console.print(f"  Total Cost: [red]${total_cost:.2f}[/red]")
            self.console.print(f"  Profit: [{'green' if profit >= 0 else 'red'}]${profit:.2f}[/{'green' if profit >= 0 else 'red'}]")
            self.console.print(f"  Margin: [{'green' if margin >= 0 else 'red'}]{margin:.1f}%[/{'green' if margin >= 0 else 'red'}]")


class InvoiceTable:
    """Rich table formatter for invoices."""

    STATUS_COLORS = {
        "paid": "green",
        "partial": "yellow",
        "viewed": "cyan",
        "sent": "blue",
        "draft": "dim",
        "overdue": "red",
        "failed": "red",
        "disputed": "red",
    }

    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()

    def get_status_style(self, status: str) -> str:
        """Get Rich style for invoice status."""
        return self.STATUS_COLORS.get(status.lower(), "white")

    def create_table(
        self,
        invoices: list[Invoice],
        title: Optional[str] = None,
    ) -> Table:
        """Create a Rich table from invoices."""
        table = Table(title=title, show_footer=True)

        table.add_column("Invoice #", style="cyan", no_wrap=True)
        table.add_column("Client", style="green")
        table.add_column("Date", style="dim")
        table.add_column("Due", style="dim")
        table.add_column("Status", justify="center")
        table.add_column("Amount", justify="right")
        table.add_column("Paid", justify="right", style="green")
        table.add_column("Outstanding", justify="right", style="yellow")

        total_amount = Decimal("0")
        total_paid = Decimal("0")
        total_outstanding = Decimal("0")

        for inv in invoices:
            status_style = self.get_status_style(inv.display_status)
            status_text = Text(inv.display_status, style=status_style)

            amount = inv.amount or Decimal("0")
            paid = inv.paid or Decimal("0")
            outstanding = inv.outstanding or Decimal("0")

            total_amount += amount
            total_paid += paid
            total_outstanding += outstanding

            table.add_row(
                inv.invoice_number or str(inv.id),
                inv.client_name,
                inv.create_date,
                inv.due_date or "-",
                status_text,
                f"${amount:.2f}",
                f"${paid:.2f}",
                f"${outstanding:.2f}",
            )

        table.columns[0].footer = ""
        table.columns[1].footer = ""
        table.columns[2].footer = ""
        table.columns[3].footer = ""
        table.columns[4].footer = Text("TOTAL", style="bold")
        table.columns[5].footer = Text(f"${total_amount:.2f}", style="bold")
        table.columns[6].footer = Text(f"${total_paid:.2f}", style="bold green")
        table.columns[7].footer = Text(f"${total_outstanding:.2f}", style="bold yellow")

        return table

    def print_table(
        self,
        invoices: list[Invoice],
        title: Optional[str] = None,
    ) -> None:
        """Print the invoices table."""
        table = self.create_table(invoices, title)
        self.console.print(table)

    def print_invoice_detail(self, invoice: Invoice) -> None:
        """Print detailed invoice information."""
        status_style = self.get_status_style(invoice.display_status)

        self.console.print()
        self.console.print(f"[bold]Invoice {invoice.invoice_number or invoice.id}[/bold]")
        self.console.print(f"  Client: [green]{invoice.client_name}[/green]")
        self.console.print(f"  Status: [{status_style}]{invoice.display_status}[/{status_style}]")
        self.console.print(f"  Created: {invoice.create_date}")
        self.console.print(f"  Due: {invoice.due_date or 'N/A'}")
        self.console.print(f"  Currency: {invoice.currency_code}")
        self.console.print()

        if invoice.lines:
            lines_table = Table(title="Line Items")
            lines_table.add_column("Description")
            lines_table.add_column("Qty", justify="right")
            lines_table.add_column("Unit Cost", justify="right")
            lines_table.add_column("Amount", justify="right")

            for line in invoice.lines:
                desc = line.description or line.name or "-"
                lines_table.add_row(
                    desc[:50] + "..." if len(desc) > 50 else desc,
                    f"{line.qty:.2f}",
                    f"${line.unit_cost:.2f}" if line.unit_cost else "-",
                    f"${line.amount:.2f}" if line.amount else "-",
                )

            self.console.print(lines_table)
            self.console.print()

        self.console.print(f"  [bold]Amount:[/bold] ${invoice.amount or 0:.2f}")
        self.console.print(f"  [bold green]Paid:[/bold green] ${invoice.paid or 0:.2f}")
        self.console.print(f"  [bold yellow]Outstanding:[/bold yellow] ${invoice.outstanding or 0:.2f}")

        if invoice.payments:
            self.console.print()
            self.console.print("[bold]Payments:[/bold]")
            for payment in invoice.payments:
                gateway = f" via {payment.gateway}" if payment.gateway else ""
                self.console.print(f"  • {payment.date}: [green]${payment.amount:.2f}[/green]{gateway}")


class ExpenseTable:
    """Rich table formatter for expenses."""

    STATUS_COLORS = {
        "internal": "dim",
        "outstanding": "yellow",
        "invoiced": "blue",
        "recouped": "green",
    }

    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()

    def get_status_style(self, status: str) -> str:
        """Get Rich style for expense status."""
        return self.STATUS_COLORS.get(status.lower(), "white")

    def create_table(
        self,
        expenses: list[Expense],
        get_category_name: callable,
        title: Optional[str] = None,
    ) -> Table:
        """Create a Rich table from expenses."""
        table = Table(title=title, show_footer=True)

        table.add_column("Date", style="cyan", no_wrap=True)
        table.add_column("Vendor", style="yellow")
        table.add_column("Category", style="blue")
        table.add_column("Amount", justify="right", style="green")
        table.add_column("Status", justify="center")
        table.add_column("Notes", max_width=30)

        total_amount = Decimal("0")

        for exp in expenses:
            status_style = self.get_status_style(exp.display_status)
            status_text = Text(exp.display_status, style=status_style)

            amount = exp.total_amount
            total_amount += amount

            vendor = exp.vendor or "-"
            category = get_category_name(exp.categoryid) if exp.categoryid else "-"
            notes = exp.notes or ""
            if len(notes) > 27:
                notes = notes[:27] + "..."

            table.add_row(
                exp.date,
                vendor,
                category,
                f"${amount:.2f}",
                status_text,
                notes,
            )

        table.columns[0].footer = ""
        table.columns[1].footer = ""
        table.columns[2].footer = ""
        table.columns[3].footer = Text(f"${total_amount:.2f}", style="bold green")
        table.columns[4].footer = Text("TOTAL", style="bold")
        table.columns[5].footer = ""

        return table

    def print_table(
        self,
        expenses: list[Expense],
        get_category_name: callable,
        title: Optional[str] = None,
    ) -> None:
        """Print the expenses table."""
        table = self.create_table(expenses, get_category_name, title)
        self.console.print(table)

    def print_expense_detail(self, expense: Expense, get_category_name: callable) -> None:
        """Print detailed expense information."""
        status_style = self.get_status_style(expense.display_status)

        self.console.print()
        self.console.print(f"[bold]Expense {expense.id}[/bold]")
        self.console.print(f"  Date: [cyan]{expense.date}[/cyan]")
        self.console.print(f"  Vendor: [yellow]{expense.vendor or 'N/A'}[/yellow]")

        category = get_category_name(expense.categoryid) if expense.categoryid else "N/A"
        self.console.print(f"  Category: [blue]{category}[/blue]")
        self.console.print(f"  Status: [{status_style}]{expense.display_status}[/{status_style}]")
        self.console.print(f"  Currency: {expense.currency_code}")
        self.console.print()

        self.console.print(f"  [bold]Base Amount:[/bold] ${expense.amount:.2f}")
        if expense.taxAmount1:
            tax_name = expense.taxName1 or "Tax 1"
            self.console.print(f"  [dim]{tax_name}:[/dim] ${expense.taxAmount1:.2f}")
        if expense.taxAmount2:
            tax_name = expense.taxName2 or "Tax 2"
            self.console.print(f"  [dim]{tax_name}:[/dim] ${expense.taxAmount2:.2f}")
        self.console.print(f"  [bold green]Total:[/bold green] ${expense.total_amount:.2f}")

        if expense.notes:
            self.console.print()
            self.console.print(f"  [bold]Notes:[/bold]")
            self.console.print(f"    {expense.notes}")

        if expense.invoiceid:
            self.console.print()
            self.console.print(f"  [bold]Attached to Invoice:[/bold] {expense.invoiceid}")


class ARAgingTable:
    """Rich table formatter for AR aging reports."""

    AGING_COLORS = {
        "current": "green",
        "days_30": "yellow",
        "days_60": "rgb(255,165,0)",
        "days_90_plus": "red",
    }

    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()

    def _format_amount_with_color(self, amount: Decimal, bucket: str, currency_code: str) -> Text:
        """Format currency amount with color based on aging bucket."""
        color = self.AGING_COLORS.get(bucket, "white")
        sign = "-" if amount < 0 else ""
        formatted = f"{sign}${abs(amount):,.2f}"
        text = Text(formatted, style=color)

        age_labels = {
            "current": "",
            "days_30": " (overdue)",
            "days_60": " (60+ days)",
            "days_90_plus": " (90+ days)",
        }
        label = age_labels.get(bucket, "")
        if label:
            text.append(label, style="dim")

        return text

    def _count_invoices(self, report: AccountAgingReport) -> int:
        """Count total invoices across all accounts."""
        count = 0
        for account in report.accounts:
            if "invoices" in account:
                count += len(account["invoices"])
            else:
                count += 1
        return count

    def _print_summary_panel(self, report: AccountAgingReport, position: str) -> None:
        """Print summary panel at top or bottom of report."""
        grid = Table.grid(padding=(0, 2))
        grid.add_column(style="bold")
        grid.add_column(justify="right")

        total_amount = report.totals.total.amount
        client_count = len(report.accounts)
        invoice_count = self._count_invoices(report)

        grid.add_row("Total Outstanding:", f"${total_amount:,.2f}")
        grid.add_row("Clients:", str(client_count))
        grid.add_row("Invoices:", str(invoice_count))
        grid.add_row("", "")
        grid.add_row("By Aging Bucket:", "")
        grid.add_row(
            "  0-30 days:",
            self._format_amount_with_color(report.totals.current.amount, "current", report.currency_code)
        )
        grid.add_row(
            "  31-60 days:",
            self._format_amount_with_color(report.totals.days_30.amount, "days_30", report.currency_code)
        )
        grid.add_row(
            "  61-90 days:",
            self._format_amount_with_color(report.totals.days_60.amount, "days_60", report.currency_code)
        )
        grid.add_row(
            "  91+ days:",
            self._format_amount_with_color(report.totals.days_90_plus.amount, "days_90_plus", report.currency_code)
        )

        title = "Summary" if position == "top" else "Totals"
        panel = Panel(grid, title=title, expand=False)
        self.console.print(panel)

    def _get_account_total(self, account: dict) -> Decimal:
        """Get total outstanding for an account."""
        if "total" in account:
            total_data = account["total"]
            if isinstance(total_data, dict) and "amount" in total_data:
                return Decimal(str(total_data["amount"]))
            return Decimal(str(total_data))
        return Decimal("0")

    def _get_bucket_amount(self, account: dict, bucket_key: str) -> Decimal:
        """Get amount for a specific aging bucket from account data."""
        if bucket_key in account:
            bucket_data = account[bucket_key]
            if isinstance(bucket_data, dict) and "amount" in bucket_data:
                return Decimal(str(bucket_data["amount"]))
            return Decimal(str(bucket_data))
        return Decimal("0")

    def _print_client_table(self, report: AccountAgingReport) -> None:
        """Print the main client table with aging data."""
        table = Table(title=f"AR Aging - {report.company_name}")

        table.add_column("Client / Invoice", style="cyan")
        table.add_column("0-30", justify="right")
        table.add_column("31-60", justify="right")
        table.add_column("61-90", justify="right")
        table.add_column("91+", justify="right")
        table.add_column("Total", justify="right", style="bold")

        sorted_accounts = sorted(
            report.accounts,
            key=lambda a: self._get_account_total(a),
            reverse=True
        )

        for account in sorted_accounts:
            client_name = account.get("organization") or account.get("fname", "") + " " + account.get("lname", "")
            client_name = client_name.strip() or "Unknown Client"

            current = self._get_bucket_amount(account, "0-30")
            days_30 = self._get_bucket_amount(account, "31-60")
            days_60 = self._get_bucket_amount(account, "61-90")
            days_90_plus = self._get_bucket_amount(account, "91+")
            total = self._get_account_total(account)

            table.add_row(
                Text(client_name, style="bold"),
                self._format_amount_with_color(current, "current", report.currency_code) if current else Text("-", style="dim"),
                self._format_amount_with_color(days_30, "days_30", report.currency_code) if days_30 else Text("-", style="dim"),
                self._format_amount_with_color(days_60, "days_60", report.currency_code) if days_60 else Text("-", style="dim"),
                self._format_amount_with_color(days_90_plus, "days_90_plus", report.currency_code) if days_90_plus else Text("-", style="dim"),
                Text(f"${total:,.2f}", style="bold"),
            )

            if "invoices" in account:
                for inv in account["invoices"]:
                    inv_label = inv.get("invoice_number") or inv.get("invoiceid") or "Invoice"
                    due_date = inv.get("due_date", "")
                    inv_display = f"  {inv_label}"
                    if due_date:
                        inv_display += f" (due {due_date})"

                    inv_current = self._get_bucket_amount(inv, "0-30")
                    inv_days_30 = self._get_bucket_amount(inv, "31-60")
                    inv_days_60 = self._get_bucket_amount(inv, "61-90")
                    inv_days_90_plus = self._get_bucket_amount(inv, "91+")
                    inv_total = self._get_bucket_amount(inv, "total") if "total" in inv else (inv_current + inv_days_30 + inv_days_60 + inv_days_90_plus)

                    table.add_row(
                        Text(inv_display, style="dim"),
                        self._format_amount_with_color(inv_current, "current", report.currency_code) if inv_current else Text("-", style="dim"),
                        self._format_amount_with_color(inv_days_30, "days_30", report.currency_code) if inv_days_30 else Text("-", style="dim"),
                        self._format_amount_with_color(inv_days_60, "days_60", report.currency_code) if inv_days_60 else Text("-", style="dim"),
                        self._format_amount_with_color(inv_days_90_plus, "days_90_plus", report.currency_code) if inv_days_90_plus else Text("-", style="dim"),
                        Text(f"${inv_total:,.2f}", style="dim"),
                    )

            table.add_section()

        self.console.print(table)

    def print_report(self, report: AccountAgingReport) -> None:
        """Print the full AR aging report."""
        if not report.accounts:
            self.console.print("[yellow]No outstanding accounts found.[/yellow]")
            return

        self.console.print()
        self._print_summary_panel(report, "top")
        self.console.print()
        self._print_client_table(report)
        self.console.print()
        self._print_summary_panel(report, "bottom")
        self.console.print()
        self.console.print(f"[dim]Report date: {report.end_date}[/dim]")
        self.console.print(f"[dim]Currency: {report.currency_code}[/dim]")


class ClientARFormatter:
    """Rich formatter for client-specific AR output."""

    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
        self.AGING_COLORS = ARAgingTable.AGING_COLORS

    def find_client_by_id(self, accounts: list[dict], client_id: int) -> Optional[dict]:
        """Find client in accounts array by userid field."""
        for account in accounts:
            if account.get("userid") == client_id:
                return account
        return None

    def find_client_by_name(self, accounts: list[dict], search_name: str) -> tuple[Optional[dict], Optional[str]]:
        """Find client by fuzzy name match."""
        name_to_account = {}
        for account in accounts:
            client_name = self.get_client_name_from_account(account)
            name_to_account[client_name] = account

        matches = get_close_matches(search_name, name_to_account.keys(), n=1, cutoff=0.6)

        if matches:
            matched_name = matches[0]
            return name_to_account[matched_name], matched_name

        return None, None

    def get_client_name_from_account(self, account: dict) -> str:
        """Extract name from organization or fname/lname."""
        if account.get("organization"):
            return account["organization"]
        fname = account.get("fname", "")
        lname = account.get("lname", "")
        name = f"{fname} {lname}".strip()
        return name if name else "Unknown Client"

    def _get_bucket_amount(self, account: dict, bucket_key: str) -> Decimal:
        """Get amount for a specific aging bucket from account data."""
        if bucket_key in account:
            bucket_data = account[bucket_key]
            if isinstance(bucket_data, dict) and "amount" in bucket_data:
                return Decimal(str(bucket_data["amount"]))
            return Decimal(str(bucket_data))
        return Decimal("0")

    def get_worst_bucket(self, account: dict) -> str:
        """Return bucket key for oldest non-zero balance."""
        buckets_order = [
            ("91+", "days_90_plus"),
            ("61-90", "days_60"),
            ("31-60", "days_30"),
            ("0-30", "current"),
        ]

        for bucket_key, color_key in buckets_order:
            amount = self._get_bucket_amount(account, bucket_key)
            if amount > 0:
                return color_key

        return "current"

    def print_compact(self, client_name: str, total: Decimal, worst_bucket: str, currency: str) -> None:
        """Print one-liner with colored amount using ARAgingTable.AGING_COLORS."""
        color = self.AGING_COLORS.get(worst_bucket, "white")

        text = Text.assemble(
            (f"{client_name}: ", "bold"),
            (f"${total:,.2f}", color),
            (f" outstanding ({currency})", "")
        )

        self.console.print(text)

    def print_detail(self, client_name: str, account: dict, currency: str) -> None:
        """Show total + bucket breakdown."""
        total = self._get_bucket_amount(account, "total")
        if "total" not in account and isinstance(account.get("total"), dict):
            total = Decimal(str(account.get("total", {}).get("amount", 0)))

        self.console.print(f"[bold]{client_name}[/bold]")
        self.console.print(f"Total Outstanding: ${total:,.2f} {currency}")
        self.console.print()
        self.console.print("By Aging Bucket:")

        buckets = [
            ("  0-30 days", "0-30", "current"),
            ("  31-60 days", "31-60", "days_30"),
            ("  61-90 days", "61-90", "days_60"),
            ("  91+ days", "91+", "days_90_plus"),
        ]

        for label, key, color_key in buckets:
            amount = self._get_bucket_amount(account, key)
            color = self.AGING_COLORS[color_key]
            amount_text = Text(f"${amount:,.2f}", style=color)
            self.console.print(f"{label}: ", end="")
            self.console.print(amount_text)


class RevenueSummaryTable:
    """Rich table formatter for revenue summary reports with DSO."""

    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()

    def _format_period_label(self, start_date: str, end_date: str, resolution: str) -> str:
        """Format period label based on resolution."""
        start = datetime.strptime(start_date, "%Y-%m-%d")

        if resolution == "m":
            return start.strftime("%b %Y")
        elif resolution == "q":
            quarter = (start.month - 1) // 3 + 1
            return f"Q{quarter} {start.year}"
        elif resolution == "y":
            return str(start.year)
        else:
            return f"{start_date} - {end_date}"

    def _format_dso(self, dso: Optional[Decimal]) -> Text:
        """Format DSO value with color coding."""
        if dso is None:
            return Text("N/A", style="dim")

        if dso < 30:
            style = "green"
        elif dso < 45:
            style = "yellow"
        elif dso < 60:
            style = "rgb(255,165,0)"
        else:
            style = "red"

        return Text(f"{dso:.1f}", style=style)

    def print_report(
        self,
        report: "ProfitLossReport",
        ar_balance: Decimal,
        currency: str
    ) -> None:
        """
        Print revenue summary table with DSO.

        Args:
            report: ProfitLossReport with income periods
            ar_balance: Current AR balance for DSO calculation
            currency: Currency code for display
        """
        from ..api.reports import calculate_dso, get_days_in_period

        if not report.income:
            self.console.print("[yellow]No revenue data found for the specified period.[/yellow]")
            return

        table = Table(title=f"Revenue Summary ({currency})")
        table.add_column("Period", style="cyan")
        table.add_column("Revenue", justify="right", style="green")
        table.add_column("DSO (days)", justify="right")

        total_revenue = Decimal("0")

        for period in report.income:
            period_label = self._format_period_label(
                period.start_date, period.end_date, report.resolution
            )

            revenue = period.total.amount
            total_revenue += revenue

            start = datetime.strptime(period.start_date, "%Y-%m-%d")
            days = get_days_in_period(start.year, start.month, report.resolution)
            dso = calculate_dso(ar_balance, revenue, days)

            table.add_row(
                period_label,
                f"${revenue:,.2f}",
                self._format_dso(dso),
            )

        table.add_section()
        table.add_row(
            Text("TOTAL", style="bold"),
            Text(f"${total_revenue:,.2f}", style="bold green"),
            Text("", style="dim"),
        )

        self.console.print()
        self.console.print(table)
        self.console.print()

        self.console.print(f"[dim]Report period: {report.start_date} to {report.end_date}[/dim]")
        self.console.print(f"[dim]Current AR Balance: ${ar_balance:,.2f}[/dim]")
        self.console.print(f"[dim]Currency: {currency}[/dim]")
