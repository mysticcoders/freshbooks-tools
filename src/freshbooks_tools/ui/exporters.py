"""CSV export utilities for financial reports."""

import csv
from datetime import datetime
from decimal import Decimal
from io import StringIO
from typing import TYPE_CHECKING, Optional

from ..models import AccountAgingReport

if TYPE_CHECKING:
    from ..models import ProfitLossReport


def generate_csv_filename(report_type: str) -> str:
    """
    Generate timestamp-based filename for CSV export.

    Args:
        report_type: Type of report (e.g., 'ar_aging', 'client_ar', 'revenue_summary')

    Returns:
        Filename with timestamp (e.g., 'ar_aging_20260129T143045.csv')
    """
    timestamp = datetime.now().strftime('%Y%m%dT%H%M%S')
    return f"{report_type}_{timestamp}.csv"


def export_ar_aging_csv(report: AccountAgingReport, output: Optional[str]) -> str:
    """
    Export AR aging report to CSV.

    Args:
        report: AccountAgingReport to export
        output: Optional output file path (auto-generates if None)

    Returns:
        Path to the exported CSV file
    """
    filepath = output or generate_csv_filename('ar_aging')

    buffer = StringIO()
    writer = csv.writer(buffer)

    # Write header
    writer.writerow([
        "Client",
        "0-30 Days",
        "31-60 Days",
        "61-90 Days",
        "91+ Days",
        "Total",
        "Currency"
    ])

    # Write client rows
    for account in report.accounts:
        client_name = account.get("organization") or account.get("fname", "") + " " + account.get("lname", "")
        client_name = client_name.strip() or "Unknown Client"

        current = _get_bucket_amount(account, "0-30")
        days_30 = _get_bucket_amount(account, "31-60")
        days_60 = _get_bucket_amount(account, "61-90")
        days_90_plus = _get_bucket_amount(account, "91+")
        total = _get_account_total(account)

        writer.writerow([
            client_name,
            f"{current:.2f}",
            f"{days_30:.2f}",
            f"{days_60:.2f}",
            f"{days_90_plus:.2f}",
            f"{total:.2f}",
            report.currency_code
        ])

    # Write total row
    writer.writerow([
        "TOTAL",
        f"{report.totals.current.amount:.2f}",
        f"{report.totals.days_30.amount:.2f}",
        f"{report.totals.days_60.amount:.2f}",
        f"{report.totals.days_90_plus.amount:.2f}",
        f"{report.totals.total.amount:.2f}",
        report.currency_code
    ])

    # Write to file
    with open(filepath, "w", newline='') as f:
        f.write(buffer.getvalue())

    return filepath


def export_client_ar_csv(client_name: str, account: dict, currency: str, output: Optional[str]) -> str:
    """
    Export client-specific AR to CSV.

    Args:
        client_name: Name of the client
        account: Account data dictionary
        currency: Currency code
        output: Optional output file path (auto-generates if None)

    Returns:
        Path to the exported CSV file
    """
    filepath = output or generate_csv_filename('client_ar')

    buffer = StringIO()
    writer = csv.writer(buffer)

    # Write header
    writer.writerow([
        "Client",
        "0-30 Days",
        "31-60 Days",
        "61-90 Days",
        "91+ Days",
        "Total",
        "Currency"
    ])

    # Write client row
    current = _get_bucket_amount(account, "0-30")
    days_30 = _get_bucket_amount(account, "31-60")
    days_60 = _get_bucket_amount(account, "61-90")
    days_90_plus = _get_bucket_amount(account, "91+")
    total = _get_account_total(account)

    writer.writerow([
        client_name,
        f"{current:.2f}",
        f"{days_30:.2f}",
        f"{days_60:.2f}",
        f"{days_90_plus:.2f}",
        f"{total:.2f}",
        currency
    ])

    # Write to file
    with open(filepath, "w", newline='') as f:
        f.write(buffer.getvalue())

    return filepath


def export_revenue_csv(report: "ProfitLossReport", ar_balance: Decimal, currency: str, output: Optional[str]) -> str:
    """
    Export revenue summary report to CSV.

    Args:
        report: ProfitLossReport to export
        ar_balance: Current AR balance for DSO calculation
        currency: Currency code
        output: Optional output file path (auto-generates if None)

    Returns:
        Path to the exported CSV file
    """
    from ..api.reports import calculate_dso, get_days_in_period

    filepath = output or generate_csv_filename('revenue_summary')

    buffer = StringIO()
    writer = csv.writer(buffer)

    # Write header
    writer.writerow([
        "Period",
        "Revenue",
        "DSO (days)",
        "Currency"
    ])

    # Write period rows
    for period in report.income:
        # Format period label
        start = datetime.strptime(period.start_date, "%Y-%m-%d")
        if report.resolution == "m":
            period_label = start.strftime("%b %Y")
        elif report.resolution == "q":
            quarter = (start.month - 1) // 3 + 1
            period_label = f"Q{quarter} {start.year}"
        elif report.resolution == "y":
            period_label = str(start.year)
        else:
            period_label = f"{period.start_date} - {period.end_date}"

        # Calculate DSO
        days = get_days_in_period(start.year, start.month, report.resolution)
        dso = calculate_dso(ar_balance, period.total.amount, days)
        dso_str = f"{dso:.1f}" if dso is not None else "N/A"

        writer.writerow([
            period_label,
            f"{period.total.amount:.2f}",
            dso_str,
            currency
        ])

    # Write to file
    with open(filepath, "w", newline='') as f:
        f.write(buffer.getvalue())

    return filepath


def _get_account_total(account: dict) -> Decimal:
    """Get total outstanding for an account."""
    if "total" in account:
        total_data = account["total"]
        if isinstance(total_data, dict) and "amount" in total_data:
            return Decimal(str(total_data["amount"]))
        return Decimal(str(total_data))
    return Decimal("0")


def _get_bucket_amount(account: dict, bucket_key: str) -> Decimal:
    """Get amount for a specific aging bucket from account data."""
    if bucket_key in account:
        bucket_data = account[bucket_key]
        if isinstance(bucket_data, dict) and "amount" in bucket_data:
            return Decimal(str(bucket_data["amount"]))
        return Decimal(str(bucket_data))
    return Decimal("0")
