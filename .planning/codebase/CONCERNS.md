# Codebase Concerns

**Analysis Date:** 2026-01-29

## Tech Debt

**Broad Exception Handling:**
- Issue: Multiple modules use bare `except Exception` without specific error logging or recovery strategies
- Files: `src/freshbooks_tools/api/rates.py:44`, `src/freshbooks_tools/api/rates.py:98`, `src/freshbooks_tools/api/invoices.py:267`, `src/freshbooks_tools/api/team.py:86`
- Impact: Exceptions are silently swallowed, making debugging difficult. API failures (network timeouts, rate limits, invalid responses) cannot be distinguished from other errors. Users receive no feedback when operations partially fail.
- Fix approach: Replace broad exception handlers with specific catches (httpx.HTTPError, ValueError, KeyError). Log actual error details. Return meaningful status indicators or raise with context.

**Silent Failures in API Response Parsing:**
- Issue: Malformed API responses are silently skipped in list operations using `continue` statements
- Files: `src/freshbooks_tools/api/time_entries.py:110-111`, `src/freshbooks_tools/api/invoices.py:145-146`, `src/freshbooks_tools/api/team.py:43`, `src/freshbooks_tools/api/rates.py:71`
- Impact: When FreshBooks API returns unexpected data shapes, entries silently disappear from results without user awareness. Partial data corruptions go undetected. Users cannot diagnose why records are missing from reports.
- Fix approach: Collect and report skipped records. Add verbose logging option. Validate response schemas with Pydantic stricter validation. Alert users when data loss occurs.

**Duplicate Value Parsing Logic:**
- Issue: Amount/value parsing is repeated across invoices.py (lines 104-123 for amount, 228-247 for invoice detail fetch, similar for paid and outstanding)
- Files: `src/freshbooks_tools/api/invoices.py` (lines 104-123, 228-247, duplicate patterns)
- Impact: Inconsistent parsing logic across code paths. Bugs in one location don't get fixed everywhere. Maintenance burden increases with each refactor.
- Fix approach: Extract to helper function `_parse_decimal_value(value)` that handles both dict and scalar formats. Reuse everywhere.

**Incomplete Rate Configuration Documentation:**
- Issue: TODO comments in generated rates file indicate developers must manually set cost rates with no guidance
- Files: `src/freshbooks_tools/cli.py:989`, `src/freshbooks_tools/cli.py:993`
- Impact: Users generate rates template but lack clear guidance on where to source cost rates. Manual data entry is error-prone and unmaintainable. No validation that entered rates are realistic.
- Fix approach: Add cost rate validation (warn if > 5x or < 0.1x billable rate). Provide instructions in generated YAML file linking to cost estimation guidelines. Add CLI command to validate rates.yaml syntax.

## Known Bugs

**Token Refresh Returns None Signal:**
- Issue: `_handle_response` in FreshBooksClient returns None as a retry signal when token refresh is needed (line 56), but this None is passed to calling code expecting a dict
- Files: `src/freshbooks_tools/api/client.py:56`, `src/freshbooks_tools/api/client.py:64-68`, `src/freshbooks_tools/api/client.py:75-78`
- Symptoms: After token expiry, first request returns None, but retry logic checks `if result is None:` which works but is fragile. Type checker sees inconsistency (returns dict[str, Any] but sometimes None).
- Trigger: Let token expire naturally (wait for expires_at to pass), then make API request
- Fix approach: Return proper error indicator (custom exception or typed response) instead of None. Separate token-refresh logic from response handling.

**Race Condition in Token Expiration Check:**
- Issue: `is_expired` property compares `datetime.now()` against stored `expires_at`, but no synchronization between check and use
- Files: `src/freshbooks_tools/config.py:32-36`, `src/freshbooks_tools/auth.py:213`
- Symptoms: Token passes `is_expired` check but fails 401 during API call if clock skew or processing delay occurs. Token refresh triggered mid-request instead of before.
- Trigger: High latency network + token expiring within milliseconds
- Workaround: Current 401 retry logic catches this, but inefficient
- Fix approach: Refresh tokens slightly before actual expiry (add buffer, e.g., 30-second grace period)

**AsyncIO Event Loop Abuse in Sync Context:**
- Issue: `account_id` and `business_id` properties use `asyncio.get_event_loop().run_until_complete()` on async methods that aren't actually async
- Files: `src/freshbooks_tools/api/client.py:128-129`, `src/freshbooks_tools/api/client.py:136-137`
- Symptoms: Creates hidden event loop in sync context. Can fail if event loop already exists. Methods marked async but don't await anything. Type hints mislead developers.
- Trigger: Call `.account_id` property before calling any async method
- Fix approach: Remove async/await from `fetch_account_info()` - it's synchronous. Use `ensure_account_info()` consistently instead.

## Security Considerations

**Credentials in Environment Variable Exposure:**
- Risk: FreshBooks client_secret stored in .env file with default 0644 permissions. If development machine is compromised, attacker gains full API access.
- Files: `.env.example` (documentation), `src/freshbooks_tools/config.py:132-149` (loading logic)
- Current mitigation: `load_env_config()` reads from .env but doesn't validate file permissions. No warning if .env has world-readable permissions.
- Recommendations: Add startup check that .env file is 0600 or 0400. Warn if credentials readable by other users. Document security requirements in README.

**OAuth Tokens Stored with 0600 Permissions But Unencrypted:**
- Risk: Access tokens that grant API access are stored in plaintext at `~/.config/freshbooks-tools/tokens.json`. Local user compromise exposes tokens.
- Files: `src/freshbooks_tools/config.py:125-129`, `src/freshbooks_tools/config.py:165-168`
- Current mitigation: File is 0600 (owner-read-only), but unencrypted. Short-lived tokens (expires_at tracked) provide some protection.
- Recommendations: Document that token file should not be backed up to cloud without encryption. Consider adding optional encryption at rest. Add token rotation reminder if token age > 90 days.

**No Input Validation on Redirected OAuth Callback:**
- Risk: OAuth callback handler accepts any `code` parameter without CSRF protection. If attacker crafts malicious OAuth link, user's browser could be tricked into authorizing.
- Files: `src/freshbooks_tools/auth.py:40-78` (OAuthCallbackHandler.do_GET)
- Current mitigation: Uses standard OAuth flow. `redirect_uri` must match app registration (FreshBooks side).
- Recommendations: Add CSRF token to authorization URL. Validate state parameter matches. Document that ngrok URL must match FreshBooks app settings exactly.

## Performance Bottlenecks

**No Caching Between CLI Commands:**
- Problem: Each CLI invocation loads fresh data from FreshBooks API. Running `fb time list && fb time summary` fetches same data twice.
- Files: All API classes (time_entries.py, invoices.py, team.py) use optional caching via `_cache` fields, but CLI doesn't reuse client across commands
- Cause: Each Click command creates new FreshBooksClient context. No session persistence between commands.
- Improvement path: Implement CLI session management. Cache frequently-accessed data (team members, services, rates) in process memory during multi-command workflows. Add `--cache-ttl` option for batch operations.

**Pagination Not Leveraged for Partial Results:**
- Problem: `list_all_*()` methods fetch all pages even when user only needs first 10 records
- Files: `src/freshbooks_tools/api/time_entries.py:115-147`, `src/freshbooks_tools/api/invoices.py:150-183`
- Cause: Caller must use `list()` with pagination instead of `list_all()` to avoid full fetch. CLI defaults to non-paginated output.
- Improvement path: Add `--limit N` option to CLI commands. Return iterator instead of full list. Make pagination the default for large result sets.

**Invoice Browser UI Loads All Invoices Synchronously:**
- Problem: `InvoiceBrowser.load_data()` fetches all clients and all invoices in single thread, blocking UI
- Files: `src/freshbooks_tools/ui/invoice_browser.py:241-260`
- Cause: No async data loading or background threads. Large accounts (1000+ invoices) freeze UI for seconds.
- Improvement path: Load clients and invoices in background worker threads. Show loading spinner. Implement lazy-load of invoice details when user selects client.

**Decimal Conversion Inefficiency:**
- Problem: Converting decimal values through string intermediate: `Decimal(str(value))` done repeatedly
- Files: `src/freshbooks_tools/api/invoices.py` (lines 86-88, 97, 107, etc.)
- Cause: Defensive coding against mixed int/dict/string API responses, but expensive
- Improvement path: Validate API response schema once, then use direct conversion. Use Pydantic BaseModel to parse and validate in one pass.

## Fragile Areas

**Team Member Identity Resolution:**
- Files: `src/freshbooks_tools/api/team.py` (full file)
- Why fragile: Multiple lookup methods (`find_identity_by_name()`, `get_team_member_by_id()`, `get_team_member_email()`) that can all return None. No null-safety enforced.
- Safe modification: Always check return values for None before use. Consider making lookups throw exceptions instead of returning None so failures are obvious.
- Test coverage: CLI accepts teammate names via `--teammate` flag but doesn't validate match exists before passing to API. Should test ambiguous names and partial matches.

**Invoice Status Display Inconsistency:**
- Files: `src/freshbooks_tools/models/schemas.py` (status field definitions), `src/freshbooks_tools/ui/invoice_browser.py` (status colors), `src/freshbooks_tools/api/invoices.py` (status parsing)
- Why fragile: `status` (numeric), `v3_status` (string), `display_status` (computed) can be out of sync. StatusBadge uses hardcoded color map that might not cover all API values.
- Safe modification: Test with all known invoice statuses from FreshBooks API. Add defensive fallback color in StatusBadge. Validate status enum values.
- Test coverage: No tests for invoice status rendering. Unknown status values silently use "white" color.

**Rate Resolution Priority Complex:**
- Files: `src/freshbooks_tools/api/rates.py:118-157` (get_billable_rate method)
- Why fragile: 6-level priority chain (config override → service rate → team member rate → staff rate → email-based rate → default). Difficult to debug which rate actually got used.
- Safe modification: Add detailed logging showing which rate source was used. Consider allowing user override of priority order via config file.
- Test coverage: No tests verifying rate priority precedence. Changes to precedence order risk breaking rate calculations silently.

**OAuth Server Timeout Hard-Coded:**
- Files: `src/freshbooks_tools/auth.py:179` (server.timeout = 120)
- Why fragile: 120-second timeout means browser must complete OAuth within 2 minutes or login fails silently. Network issues or slow FreshBooks auth server could cause apparent hang.
- Safe modification: Make timeout configurable. Show countdown to user. Provide retry mechanism.
- Test coverage: Cannot easily test timeout behavior without live OAuth flow.

## Scaling Limits

**Single-Page API Queries Limited to 100 Items:**
- Current capacity: `per_page=100` (hardcoded in most methods)
- Limit: Accounts with 100+ team members, 100+ open invoices per month hit pagination boundaries
- Scaling path: Make `per_page` configurable. Implement efficient cursor-based pagination. Add batch fetch methods for multi-page operations.

**In-Memory Invoice Storage:**
- Current capacity: All invoices loaded into `_invoices` list in InvoiceBrowser
- Limit: Accounts with 10,000+ invoices will consume significant memory and slow sorting/filtering
- Scaling path: Implement lazy-loading in DataTable. Store only metadata in memory, fetch details on-demand. Add filtering/search at API level.

**Rate Cache Not Invalidated:**
- Current capacity: `_services_cache` and `_team_member_rates_cache` in RatesAPI persist for lifetime of process
- Limit: Long-running processes (if ever made a daemon) serve stale rate data after updates
- Scaling path: Add cache TTL. Implement cache invalidation events. Provide manual refresh command.

## Dependencies at Risk

**Textual TUI Framework Unstable:**
- Risk: `textual>=0.89` dependency rapidly evolving (moved from 0.85 to 0.89). Breaking changes in widget APIs possible.
- Impact: Invoice browser could break on routine dependency updates. No version pinning provides protection.
- Migration plan: Pin textual to specific version (e.g., `textual==0.89.x`). Add CI tests that upgrade dependencies weekly to catch breakage early. Consider fallback to CLI-only mode if TUI breaks.

**No HTTP Timeout Configuration:**
- Risk: `httpx.Client(timeout=30.0)` hardcoded. FreshBooks API occasionally slow, causing timeouts on large data fetches.
- Impact: Commands intermittently fail with timeout on large invoice/timesheet exports. Retry logic doesn't help if timeout is too short.
- Migration plan: Make timeout configurable via environment variable. Implement exponential backoff for timeout retries.

## Missing Critical Features

**No Offline Mode or Local Caching:**
- Problem: Every CLI command requires API call. Network outage makes tool unusable.
- Blocks: Generating reports during travel or when API down
- Recommendation: Cache team member list, rates config, and last-fetched data locally. Add `--offline` flag to use cached data. Add cache staleness warnings.

**No Batch Operations:**
- Problem: Cannot update multiple time entries or invoices in single API call
- Blocks: Bulk invoice status updates, bulk time entry corrections
- Recommendation: Implement batch endpoints. Add CLI commands for bulk import/export via CSV.

**No Data Validation Before API Submission:**
- Problem: Rate configuration has no schema validation. Typos in cost_rate values not caught until calculation time.
- Blocks: Early error detection, preventing bad data from reaching calculations
- Recommendation: Add Pydantic validators to RatesConfig. Validate values on load. Warn if rates seem unrealistic (e.g., cost > billable for same person).

## Test Coverage Gaps

**No Unit Tests for Core APIs:**
- What's not tested: All API classes (TimeEntriesAPI, InvoicesAPI, TeamAPI, RatesAPI) lack unit tests. Parser methods untested.
- Files: `src/freshbooks_tools/api/` (all files)
- Risk: Refactoring or schema changes to API parsing have no safety net. Silent failures in response parsing (continue statements) cannot be caught by tests.
- Priority: High - Core functionality relies on these APIs

**No Integration Tests with Mock FreshBooks API:**
- What's not tested: End-to-end CLI commands with realistic API responses
- Files: `src/freshbooks_tools/cli.py` (all commands)
- Risk: Changes to CLI logic cannot be validated against actual FreshBooks response shapes. Breaking changes to API response parsing undetected.
- Priority: High - CLI is main user interface

**No Tests for OAuth Flow:**
- What's not tested: Token refresh logic, 401 retry, callback handler, browser opening
- Files: `src/freshbooks_tools/auth.py` (all)
- Risk: Authentication can silently fail. Token refresh could be broken without detection. OAuth callback handler could fail on unusual inputs.
- Priority: Medium - Users hit this path regularly

**No Tests for Invoice Browser UI:**
- What's not tested: Client list population, invoice table rendering, status colors, detail panel updates
- Files: `src/freshbooks_tools/ui/invoice_browser.py` (all)
- Risk: UI layout could break without detection. Status color mapping could be inconsistent. Click handling could fail on edge cases (empty data, single client, etc.)
- Priority: Medium - Visual component, hard to debug without tests

**No Tests for Rate Resolution Logic:**
- What's not tested: Billable rate precedence chain, cost rate fallback behavior, cache behavior
- Files: `src/freshbooks_tools/api/rates.py` (especially get_billable_rate, get_cost_rate)
- Risk: Rate calculations could silently use wrong priority. Cache invalidation could be missed. Changes to rate lookup could silently break profit calculations.
- Priority: High - Business logic that affects financial reporting

**Test File is Empty:**
- What's not tested: Everything
- Files: `tests/__init__.py` (empty, no actual test files)
- Risk: Complete absence of test coverage. No CI/CD can enforce code quality.
- Priority: Critical - Need test infrastructure before adding more features

---

*Concerns audit: 2026-01-29*
