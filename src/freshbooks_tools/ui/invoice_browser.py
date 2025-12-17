"""Interactive invoice browser using Textual."""

from decimal import Decimal
from typing import Optional

from rich.text import Text
from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import (
    DataTable,
    Footer,
    Header,
    Label,
    ListItem,
    ListView,
    Static,
)

from ..api.client import FreshBooksClient
from ..api.invoices import InvoicesAPI
from ..config import Config
from ..models import Client, Invoice


class StatusBadge(Static):
    """Colored status badge widget."""

    STATUS_COLORS = {
        "paid": "green",
        "partial": "yellow",
        "viewed": "cyan",
        "sent": "blue",
        "draft": "white on dark_blue",
        "overdue": "white on red",
        "failed": "white on red",
        "disputed": "white on dark_red",
    }

    def __init__(self, status: str, **kwargs):
        super().__init__(**kwargs)
        self.status = status

    def render(self) -> Text:
        """Render the status badge."""
        color = self.STATUS_COLORS.get(self.status.lower(), "white")
        return Text(f" {self.status.upper()} ", style=f"bold {color}")


class ClientListItem(ListItem):
    """List item for a client."""

    def __init__(self, client: Client, invoice_count: int = 0, **kwargs):
        super().__init__(**kwargs)
        self.client = client
        self.invoice_count = invoice_count

    def compose(self) -> ComposeResult:
        """Compose the client list item."""
        yield Label(f"{self.client.display_name} ({self.invoice_count})")


class InvoiceDetail(Static):
    """Widget showing invoice details."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._invoice: Optional[Invoice] = None

    def set_invoice(self, invoice: Optional[Invoice]) -> None:
        """Set the invoice to display."""
        self._invoice = invoice
        self.refresh()

    def render(self) -> Text:
        """Render the invoice details."""
        if not self._invoice:
            return Text("Select an invoice to view details", style="dim")

        inv = self._invoice
        lines = []

        lines.append(Text(f"Invoice #{inv.invoice_number or inv.id}", style="bold cyan"))
        lines.append(Text(""))
        lines.append(Text(f"Client: {inv.client_name}", style="green"))
        lines.append(Text(f"Status: {inv.display_status}", style=self._get_status_style(inv.display_status)))
        lines.append(Text(f"Created: {inv.create_date}"))
        lines.append(Text(f"Due: {inv.due_date or 'N/A'}"))
        lines.append(Text(f"Currency: {inv.currency_code}"))
        lines.append(Text(""))

        lines.append(Text("─" * 40))
        lines.append(Text(""))

        amount = inv.amount or Decimal("0")
        paid = inv.paid or Decimal("0")
        outstanding = inv.outstanding or Decimal("0")

        lines.append(Text(f"Amount:      ${amount:>10.2f}", style="bold"))
        lines.append(Text(f"Paid:        ${paid:>10.2f}", style="green"))
        lines.append(Text(f"Outstanding: ${outstanding:>10.2f}", style="yellow" if outstanding > 0 else "dim"))

        if inv.payments:
            lines.append(Text(""))
            lines.append(Text("Payments:", style="bold"))
            for payment in inv.payments:
                gateway = f" ({payment.gateway})" if payment.gateway else ""
                lines.append(Text(f"  • {payment.date}: ${payment.amount:.2f}{gateway}", style="green"))

        if inv.lines:
            lines.append(Text(""))
            lines.append(Text("Line Items:", style="bold"))
            for line in inv.lines[:5]:
                desc = line.description or line.name or "Item"
                desc = desc[:30] + "..." if len(desc) > 30 else desc
                amt = f"${line.amount:.2f}" if line.amount else "-"
                lines.append(Text(f"  • {desc}: {amt}"))
            if len(inv.lines) > 5:
                lines.append(Text(f"  ... and {len(inv.lines) - 5} more items", style="dim"))

        result = Text()
        for i, line in enumerate(lines):
            result.append(line)
            if i < len(lines) - 1:
                result.append("\n")

        return result

    def _get_status_style(self, status: str) -> str:
        """Get style for status."""
        styles = {
            "paid": "green",
            "partial": "yellow",
            "viewed": "cyan",
            "sent": "blue",
            "draft": "dim",
            "overdue": "red",
            "failed": "red",
            "disputed": "red",
        }
        return styles.get(status.lower(), "white")


class InvoiceBrowserApp(App):
    """Interactive invoice browser TUI application."""

    CSS = """
    Screen {
        layout: horizontal;
    }

    #client-panel {
        width: 30%;
        min-width: 25;
        border: solid green;
        padding: 1;
    }

    #invoice-panel {
        width: 40%;
        border: solid cyan;
    }

    #detail-panel {
        width: 30%;
        border: solid yellow;
        padding: 1;
    }

    #client-list {
        height: 100%;
    }

    #invoice-table {
        height: 100%;
    }

    .panel-title {
        text-align: center;
        text-style: bold;
        background: $surface;
        padding: 1;
    }

    DataTable {
        height: 100%;
    }

    DataTable > .datatable--cursor {
        background: $accent;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("escape", "quit", "Quit"),
    ]

    def __init__(self, config: Config, **kwargs):
        super().__init__(**kwargs)
        self.config = config
        self._client: Optional[FreshBooksClient] = None
        self._invoices_api: Optional[InvoicesAPI] = None
        self._clients: list[Client] = []
        self._invoices: list[Invoice] = []
        self._client_invoices: dict[int, list[Invoice]] = {}
        self._selected_client: Optional[Client] = None

    def compose(self) -> ComposeResult:
        """Compose the app layout."""
        yield Header()

        with Horizontal():
            with Vertical(id="client-panel"):
                yield Static("Clients", classes="panel-title")
                yield ListView(id="client-list")

            with Vertical(id="invoice-panel"):
                yield Static("Invoices", classes="panel-title")
                yield DataTable(id="invoice-table")

            with Vertical(id="detail-panel"):
                yield Static("Details", classes="panel-title")
                yield InvoiceDetail(id="invoice-detail")

        yield Footer()

    def on_mount(self) -> None:
        """Initialize the app on mount."""
        self.title = "FreshBooks Invoice Browser"
        self.sub_title = "Loading..."

        invoice_table = self.query_one("#invoice-table", DataTable)
        invoice_table.add_columns("Invoice #", "Date", "Status", "Amount", "Outstanding")
        invoice_table.cursor_type = "row"

        self.load_data()

    def load_data(self) -> None:
        """Load clients and invoices from API."""
        try:
            self._client = FreshBooksClient(self.config)
            self._invoices_api = InvoicesAPI(self._client)

            self._clients = self._invoices_api.list_clients()
            self._invoices = self._invoices_api.list_all_invoices(include_payments=True)

            self._client_invoices = {}
            for inv in self._invoices:
                if inv.customerid not in self._client_invoices:
                    self._client_invoices[inv.customerid] = []
                self._client_invoices[inv.customerid].append(inv)

            self._populate_client_list()
            self.sub_title = f"{len(self._clients)} clients, {len(self._invoices)} invoices"

        except Exception as e:
            self.sub_title = f"Error: {e}"

    def _populate_client_list(self) -> None:
        """Populate the client list."""
        client_list = self.query_one("#client-list", ListView)
        client_list.clear()

        sorted_clients = sorted(
            self._clients,
            key=lambda c: len(self._client_invoices.get(c.id, [])),
            reverse=True,
        )

        for client in sorted_clients:
            invoice_count = len(self._client_invoices.get(client.id, []))
            if invoice_count > 0:
                client_list.append(ClientListItem(client, invoice_count))

    def _populate_invoice_table(self, client: Client) -> None:
        """Populate the invoice table for a client."""
        invoice_table = self.query_one("#invoice-table", DataTable)
        invoice_table.clear()

        invoices = self._client_invoices.get(client.id, [])
        invoices = sorted(invoices, key=lambda i: i.create_date, reverse=True)

        for inv in invoices:
            status_colors = {
                "paid": "green",
                "partial": "yellow",
                "viewed": "cyan",
                "sent": "blue",
                "draft": "dim",
                "overdue": "red",
            }
            status_style = status_colors.get(inv.display_status.lower(), "white")
            status_text = Text(inv.display_status, style=status_style)

            amount = inv.amount or Decimal("0")
            outstanding = inv.outstanding or Decimal("0")
            outstanding_style = "yellow" if outstanding > 0 else "dim"

            invoice_table.add_row(
                inv.invoice_number or str(inv.id),
                inv.create_date,
                status_text,
                f"${amount:.2f}",
                Text(f"${outstanding:.2f}", style=outstanding_style),
                key=str(inv.id),
            )

        self._invoices = invoices

    @on(ListView.Selected, "#client-list")
    def on_client_selected(self, event: ListView.Selected) -> None:
        """Handle client selection."""
        if isinstance(event.item, ClientListItem):
            self._selected_client = event.item.client
            self._populate_invoice_table(event.item.client)

            detail = self.query_one("#invoice-detail", InvoiceDetail)
            detail.set_invoice(None)

    @on(DataTable.RowSelected, "#invoice-table")
    def on_invoice_selected(self, event: DataTable.RowSelected) -> None:
        """Handle invoice selection."""
        if event.row_key and self._invoices:
            invoice_id = int(str(event.row_key.value))
            invoice = next((i for i in self._invoices if i.id == invoice_id), None)

            if invoice:
                detail = self.query_one("#invoice-detail", InvoiceDetail)
                detail.set_invoice(invoice)

    def action_refresh(self) -> None:
        """Refresh data from API."""
        self.sub_title = "Refreshing..."
        self.load_data()

    def action_quit(self) -> None:
        """Quit the application."""
        if self._client:
            self._client.close()
        self.exit()


def run_invoice_browser(config: Config) -> None:
    """Run the invoice browser app."""
    app = InvoiceBrowserApp(config)
    app.run()
