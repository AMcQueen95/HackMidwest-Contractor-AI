# Data and finance handoff

This component supplies sample books, validation, and deterministic calculations
for Aidan's agent tools and Tyler's API. It does not require model credentials or
an API server. All exported finance functions return JSON-friendly dictionaries.

## Run from the repository root

```bash
bash scripts/setup_backend.sh
source .venv/bin/activate
python -m pytest backend/tests -q
python scripts/demo_finance.py
```

The demo prints results from all nine functions as strict JSON. To supply your own
books, pass `--books /path/to/books`; use `--month YYYY-MM` or `--purchase 15000`
to change the reporting month or purchase amount.

The bundled fictional files are generated deterministically:

```bash
python scripts/generate_sample_data.py --output /tmp/ridgeline-books
python scripts/demo_finance.py --books /tmp/ridgeline-books
```

Omitting `--output` regenerates the bundled sample files. Do not run that command
against a directory containing books you want to preserve.

## Agent and API integration

```python
from backend.app.data import load_books
from backend.app.finance import monthly_summary, affordability

books = load_books()  # default bundled sample, or load_books(directory)
summary = monthly_summary(books, "2026-09")
purchase = affordability(books, 15000)
```

Keep `Books` internal to the application. Bind it in agent tool wrappers and pass
only question parameters such as `month` or `amount` to those tools. Let the model
explain returned figures; do not ask it to calculate figures missing from results.

| Function | Arguments after `books` | Principal result fields |
| --- | --- | --- |
| `monthly_summary` | `month` | `revenue`, `expenses`, `profit`, `expenses_by_category`, `basis`, `period_complete` |
| `expense_changes` | `month`, optional `previous_month` | `changes`: category, previous/current amount, change, change percent |
| `recurring_charges` | optional `month` | `charges`, `potential_duplicate_groups` |
| `job_profitability` | optional completion `month` | `jobs`: quoted revenue, cash received, direct/labor costs, profit, margin percent |
| `losing_jobs` | optional completion `month` | same job fields, restricted to negative profit |
| `margin_by_job_type` | optional completion `month` | `job_types`: counts, totals, weighted margin percent |
| `cash_balance` | none | `balance`, `cash_in`, `cash_out`, `tax_reserve`, `available_cash` |
| `receivables` | none | `total_outstanding`, `overdue_total`, `aging`, `customers`, `invoices` |
| `affordability` | `amount`, optional `reserve_months=1`, `reserve_month` | `can_afford_now`, `shortfall`, reserve amounts, `collection_scenario` |

Months must be `YYYY-MM` and cannot follow the snapshot's as-of date. Percentage
changes and job margins are `null` when the denominator is zero. Money is returned
in USD dollars as ordinary numbers; internal sums use integer cents. Negative
expense transactions become positive expense totals. Percentages are rounded to
two decimal places; estimated labor and tax holds round half cents up.

## Input contract

Load a directory containing `transactions.csv`, `jobs.csv`, `invoices.csv`, and
`business.json`. CSV columns match the README. Job IDs must be unique and must
exist when referenced by invoices or transactions. Empty transaction `job_id`
means an unallocated business transaction. Completed jobs need an end date.
Supported statuses are `completed`, `in_progress`, `quoted`, and `cancelled`.

`business.json` requires `name`, `currency: "USD"`, `accounting_basis: "cash"`,
`opening_balance`, `opening_balance_date`, `as_of_date`, `labor_rate`, and
`tax_reserve_rate`. The opening balance is the balance at the beginning of
`opening_balance_date`, before transactions on that date. Actual transaction
dates must fall within that date and the as-of date, inclusive.

Dates must be ISO `YYYY-MM-DD`. Monetary input must be finite and use at most two
decimal places. Quotes, invoice balances, paid amounts, hours, and the labor rate
cannot be negative. Payments cannot exceed an invoice amount and need a payment
date. Unpaid invoices leave `paid_date` blank. Future due dates are allowed;
future posted transactions and payments are not. Files must be UTF-8, at most
10 MiB each, with complete rows and unique header names. Additional CSV columns
are ignored. One input numeric value is limited to an absolute value of 1 trillion.

For upload integration, gather all four named files and call
`load_books_from_uploads({filename: bytes_or_text, ...})`. It validates a complete
new snapshot before returning `Books`. Replace the current dataset only after
success; catch `BooksValidationError` to return an appropriate API validation
error. The function neither changes an existing dataset nor stores uploaded
files. The [live dashboard API](live-dashboard.md) implements browser-session
isolation and this upload route.

## Accounting and interpretation

- Monthly revenue is cash received, expenses are cash spent, and profit is their
  difference. Inputs should be operating transactions; owner transfers and loan
  proceeds are not modeled as financing flows. Unpaid invoices never get added
  to cash revenue until their payment is posted to transactions.
- Invoice `paid_amount` is the cumulative payment at the snapshot date;
  `paid_date` is the most recent payment date. Receivables use the snapshot date,
  not reconstructed historical balances. Record actual collections once in
  transactions as well; the loader does not infer payments or reconcile invoice
  paid totals with the cash ledger, which can cover a shorter period.
- Job profit uses quoted price, not recognized accounting revenue. It subtracts
  negative transactions tagged to the job and estimated labor (`hours × rate`).
  If any negative tagged `labor` or `payroll` transactions exist, their sum replaces
  the estimate. When allocating payroll, move/tag existing entries rather than
  posting them a second time. Unallocated overhead is excluded, so these margins
  do not sum to business cash profit. `cost_history_complete` means the ledger
  window covers the job's start; it does not prove every cost has been recorded.
- Recurring bills require the same vendor/category in at least two months,
  including the reporting month. Multiple software vendors produce a review
  candidate, not a claim of duplicate services.
- The tax hold is a configurable planning estimate: the tax reserve rate times
  positive net cash income since the opening date. It is not a tax calculation.
- Purchase policy keeps a tax hold plus `reserve_months` of observed expenses.
  It defaults to the last complete calendar month so partial-month expenses
  cannot silently reduce the cushion. Without a complete month with recorded
  expenses, `can_afford_now` is `null` and status is `insufficient_expense_history`.
  Setting `reserve_months=0` explicitly disables the operating-expense cushion.
- The collection scenario assumes every outstanding invoice is collected with
  no new expenses, recomputes the tax hold, and applies the same purchase policy.
  It is conditional, not a forecast or a guarantee of collection.

## Verified sample answers

| Result | Value |
| --- | --- |
| August cash receipts / expenses / profit | $60,000 / $45,000 / $15,000 |
| September cash receipts / expenses / profit | $45,070 / $52,900 / −$7,830 |
| Westport quoted job margin | −$1,232 |
| Unpaid invoices | Westport $12,000; Brookside $9,000 |
| Fuel / insurance / software increase | 35% / 26% / 176.01% |
| Cash balance / tax hold / available cash | $52,170 / $717 / $51,453 |
| $15,000 purchase today, keeping one month of expenses | Fails; $16,447 short of policy |
| After collecting all $21,000, then buying | Passes; $55,353 after purchase and tax hold, versus $52,900 reserve |

The HTML artifact's figures were illustrative. These values reconcile to the
bundled files and are asserted by tests. Aidan can call August and September
`monthly_summary` to explain the $22,830 decline: $14,930 less cash received plus
$7,900 more spending. Collecting receivables improves cash; it does not fix the
Westport job margin.
