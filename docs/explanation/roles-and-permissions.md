# Roles and permissions

Two separate things decide what `fb` can show you.

## OAuth scopes: what `fb` may ask for

Your FreshBooks app lists scopes, and `fb auth login` requests them (see [Configuration › OAuth scopes](../reference/configuration.md#oauth-scopes)). A scope missing from the app or the token causes `insufficient_scope` errors whatever your role. The error names the scope it needed.

A token keeps the scopes it was issued with. After a scope is added to the app or to `fb`, log out and in again.

## Your FreshBooks role: what you may see

FreshBooks then applies your role in the business. Owners and admins see the business's invoices, payments, reports, expenses and everyone's time. Team members and contractors typically see less, often their own time and the projects they're on. When FreshBooks refuses something, the CLI prints the error and the MCP tools return it to the LLM, so you see the reason rather than an empty result.

So the same `fb` setup serves both:

- **Someone logging their own time** uses `fb time add`, `fb time habits`, aliases, and the time tools over MCP.
- **An owner or admin** also uses the invoice, receivables, unbilled-time, revenue and expense commands. See [Answer business questions](../how-to/answer-business-questions.md).

Each person logs in as themselves; `fb` never shares tokens between people.

## One business at a time

`fb` works with the first business on your FreshBooks login. If you belong to several businesses, for example your own and a client's, that's the one you'll see. Which business it uses is saved in `account.json` in the config directory.
