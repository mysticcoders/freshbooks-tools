# Configure cost rates

FreshBooks exposes billable rates but not cost rates (what a person costs you). `fb` reads cost rates from `rates.yaml` to compute profit and margin in time reports.

1. Generate a template listing your team:

   ```bash
   fb rates-init
   ```

2. Edit `rates.yaml` in the config directory (the command prints the path) and fill in rates:

   ```yaml
   default_cost_rate: 50.00
   members:
     9535329:
       name: "Joseph Ottinger"
       cost_rate: 75.00
   ```

3. Check a report:

   ```bash
   fb time summary -m 10
   ```

## Billable amounts show as zero

FreshBooks hides project rates from project members, so your amounts can come out as zero. Set your rate locally:

```bash
fb rates show                  # what applies now, and where it comes from
fb rates set 125               # your rate on every project
fb rates set 140 -p acme       # a rate for one project
fb rates set 110 -t "Ann"      # a teammate's rate (owners and admins)
```

These write `billable_rate` entries to `rates.yaml` under `members` or `projects`. Other settings in the file are kept, but comments are not. An LLM connected over MCP can do the same with `set_billable_rate` when you say "my rate is $125".

The full file format is in [Configuration › rates.yaml](../reference/configuration.md#ratesyaml). How `fb` chooses between rates is in [Rates](../explanation/rates.md).
