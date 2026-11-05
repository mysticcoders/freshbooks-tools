# Run reports and exports

Every command takes `--json` for structured output. All options are in the [CLI reference](../reference/cli.md).

## Receivables

```bash
fb reports ar-aging                       # outstanding invoices by age bucket
fb reports ar-aging --export csv          # writes a CSV in the current directory
fb reports client-ar --client-name "Acme" # what one client owes
fb reports client-ar --client-id 12345 --detail
```

## Revenue and expenses

```bash
fb reports revenue --start-date 2026-01-01 --end-date 2026-03-31
fb reports revenue --resolution quarterly --start-date 2026-01-01 --end-date 2026-12-31
fb reports expense-summary --start-date 2026-01-01 --end-date 2026-03-31 --export csv
fb expenses list --start-date 2026-10-01
```

## Time

```bash
fb time list -m 10                        # October this year; -m 2025-10 for another year
fb time summary -m 10 --by-teammate
fb time unbilled --by-client
fb time export -m 10 --output timesheet.csv
```

## Invoices

```bash
fb invoices list --status overdue
fb invoices show INV-0001
fb invoices browse                        # interactive browser
```

The profit and cost columns in time reports need cost rates, which FreshBooks doesn't provide; see [Configure cost rates](configure-cost-rates.md).
