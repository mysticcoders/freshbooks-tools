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

The full file format is in [Configuration › rates.yaml](../reference/configuration.md#ratesyaml). How `fb` chooses between rates is in [Rates](../explanation/rates.md).
