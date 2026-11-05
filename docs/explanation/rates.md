# Rates

Time reports show a billable rate (what you charge) and a cost rate (what the work costs you). Together they give profit and margin.

## Billable rate

For each time entry, `fb` uses the first of these that's set and above zero:

1. A billable rate for that person's identity id in `rates.yaml`, either `billable_rate` under `members` or a `billable_rates` entry keyed by the id: your manual override.
2. The rate of the entry's service in FreshBooks.
3. The person's team member rate in FreshBooks.
4. The person's staff rate (an older FreshBooks API).
5. A `billable_rates` entry for the person's email in `rates.yaml`.
6. `default_billable_rate` in `rates.yaml`.

Non-billable entries have no billable rate.

## Cost rate

FreshBooks doesn't expose cost rates, so they come only from `rates.yaml`:

1. `cost_rate` for the identity id under `members`, or a `cost_rates` entry keyed by the identity id.
2. `default_cost_rate`.
3. A `cost_rates` entry for the person's email. This is only reached when no `default_cost_rate` is set, so if you use a default, key rates by identity id rather than email.

## Staleness

FreshBooks rates are cached for up to 24 hours (see [Lookups and caching](lookups-and-caching.md)). After changing a rate in FreshBooks, run `fb cache clear` if you need reports to reflect it right away. Changes to `rates.yaml` apply immediately.
