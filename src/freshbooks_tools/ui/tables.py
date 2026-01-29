"""Rich table formatters for CLI output."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ..models import AccountAgingReport, Invoice, TimeEntry


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
