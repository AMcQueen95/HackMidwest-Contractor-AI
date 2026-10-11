# Cedar & Stone upload test pack

All companies, customers, vendors, crew IDs, and account labels are fictional. This is a new landscaping and light remodeling business, **Cedar & Stone Property Services**, with records from **May 1 through July 31, 2026**. It differs from the earlier Ridgeline samples. Amounts are USD.

Start with `01-upload-together`. The other folders are separate scenarios, not additional books to upload all at once.

## First upload: six files together

1. Download and unzip `cedar-stone-test-files.zip`. On a Mac, double-click the ZIP in Finder.
2. With your backend and frontend running, open your frontend at `http://localhost:5174` in your browser.
3. Sign in and create a **new company** named `Cedar & Stone Property Services`. Keep this test separate from your existing company and sample Plaid bank.
4. On **Add your financial records**, click **Choose files**, open `01-upload-together`, and select all **six CSV files**. On a Mac, press Command+A inside that folder. Select CSVs, not the ZIP or the whole folder.
5. Click **Read 6 files**. This uses the configured AI service, so it can take time and incur normal provider usage. If the app says the AI service is unavailable, check the server's configuration before retrying.
6. On **Check what we read**, expect four transaction exports, one customer invoice list, and one jobs export. The credit card has **positive charges and negative payments/refunds**; the checking export has separate withdrawal and deposit columns. Verify money direction and recognized file types before saving.
7. Enter hourly labor cost **52** and tax reserve percentage **25** if requested. These files include cash balances, so a manual starting balance should not be needed. If the app asks for one, check whether the bank balance columns were recognized. Leave a manual balance unset for the benchmark below.
8. Click **Save and open my dashboard**. Review July, then select June and May. Compare the numbers below. Sign out and back in to check that the company's records persist.

| File | What it tests |
| --- | --- |
| `business_checking.csv` | Newest-first bank statement, separate money-in/out columns, currency symbols, running balances, customer receipts, payroll, operating payments, refunds, chargeback, loans and owner transactions |
| `business_savings.csv` | Unsigned amounts plus CREDIT/DEBIT direction, internal transfers, earned interest, separate account balance |
| `business_credit_card.csv` | Positive charges, parenthesized negative refunds/payments, repeated purchases, merchant categories, equipment, fuel, vehicle repairs, freight, tolls and parking |
| `petty_cash.csv` | Signed cash transactions, bank-to-cash transfers, fuel, inspection fees, stationery and a small cash customer receipt |
| `customer_invoices.csv` | 15 fully paid, partially paid or unpaid customer invoices, due dates, job references and two missing payment dates that should match bank deposits |
| `jobs.csv` | 18 work orders: 15 completed, one quote, one in progress and one cancelled; prices, work types and labor hours |

## Expected baseline results

These numbers were checked through the real CSV converter, books loader and finance calculations using explicit column mappings and the supplied `Category` hints. **The live AI identification/categorization and signed-in browser upload were not run for this pack.** If the live import differs, inspect its mapping, warnings and categories before assuming the finance arithmetic is wrong.

| Month | Received money / revenue | Expenses | Profit |
| --- | ---: | ---: | ---: |
| May 2026 | $21,714.00 | $26,242.60 | -$4,528.60 |
| June 2026 | $25,230.00 | $22,557.60 | $2,672.40 |
| July 2026 | $22,736.00 | $24,308.10 | -$1,572.10 |

- **142 business transactions**, **15 invoices**, **18 jobs** after import.
- **25 transactions excluded from profit**: 18 transfers, three owner transactions, four loan transactions. Notices about excluding these are expected.
- **Cash balance: $102,603.15**, the combined closing balances of checking, savings and petty cash. This includes loan proceeds and owner cash movements. Credit card debt is not included in this cash total.
- **Unpaid customer invoices: $34,000.00**, all overdue on July 31: $13,000 in 1–30 days, $11,500 in 31–60 days, $9,500 in 61–90 days.
- **Two invoice payment dates matched** from customer deposits.
- There are two identical fuel purchases on the same day in each month's card export. Both should remain: they are separate purchases within the same source, not overlapping exports.
- July is a full month and should be selected by default. May includes a one-time $4,800 mower purchase, so its loss is intentional. June is profitable and July is a loss.

Detailed category totals, warnings and scenarios are in `expected-results.json`.

## What kinds of charges are covered?

The dataset covers every currently supported category: income plus materials, payroll, subcontractors, fuel, vehicle, equipment, insurance, rent, utilities, software, marketing, permits, bank fees, taxes and overhead. Transfers, owner transactions and loan principal are also present to test their exclusion from profit.

Examples include net crew wages, employee payroll tax remittances, employer payroll taxes, retirement match, workers' compensation, liability and health contributions, repairs, registration, tolls, parking, rentals, tool purchases, safety gear, freight, electricity, water, phone, internet, advertising, hosting, overlapping scheduling subscriptions, accounting software, training, bookkeeping/legal fees, refreshments, permit/license fees, merchant fees, wire fees, card late fees, customer refunds/chargebacks and supplier refunds.

## Scenario 2: higher July costs

Create a second company, `Cedar & Stone — Higher Costs`, and upload all six CSVs from `02-higher-cost-scenario`. Use the same labor cost and tax reserve percentage. Compare with the baseline company.

- July insurance increases by **$400**, crew wages by **$1,300**, and an emergency truck repair adds **$1,450** on the card.
- July expenses become **$27,458.10**, an increase of **$3,150**.
- July profit becomes **-$4,722.10**. Revenue stays **$22,736.00**.
- Combined cash becomes **$100,903.15**, down **$1,700**. The additional card repair has not yet been paid from checking, so it does not reduce the bank balances yet.
- May, June and unpaid invoices stay the same.

Alternatively, uploading these six files to the baseline company replaces sources with the same filenames. This changes that company's scenario. Use separate companies if you want both visible. Do not rename these files and then combine both full sets: that would mix duplicate account balance snapshots.

## Scenario 3: overlapping exports

After saving the baseline, use **Add more records** and upload just `03-duplicate-check/overlapping_accounting_export.csv`.

This repeats 18 existing bank/card transactions with the same date, amount and description under a new source filename. Expect a warning that **18 transactions were skipped**. Revenue, expenses, profit, cash balance and the 142-transaction count should remain unchanged. It has no balance column, so it does not add another bank balance snapshot.

## Scenario 4: errors and partial reads

Test these individually. Use a separate company named `Import Error Tests` for `partial_bad_rows.csv`.

| File | Expected behavior |
| --- | --- |
| `empty.csv` | The file picker reports that it is empty and does not add it to the selection. |
| `crew_roster.csv` | Should be recognized as nonfinancial and skipped with a warning. Uploaded alone to an empty company, it cannot create books. Its AI classification still needs live testing. |
| `unreadable_dates_and_amounts.csv` | With a transaction mapping, all three rows are skipped. A new company cannot save books with no valid business transactions. On a company that already has books, a skipped new source can leave the existing books intact. |
| `partial_bad_rows.csv` | Two valid rows plus an invalid date, unreadable amount and zero-dollar row. Expect a three-row warning and two imported transactions. Enter starting cash **45000** if requested. June revenue is **$500**, expenses **$85.25**, profit **$414.75**, resulting cash **$45,414.75**. This is a partial June period ending June 11. |

For a rejected upload, return to the dashboard and confirm the saved company's figures remain intact. A preview should not change the saved dashboard until you save. The partial-row file intentionally demonstrates that valid rows can be accepted with warnings; not every malformed row rejects the whole file.

## Reference records: do not upload with the main six

`05-reference-only-do-not-upload-with-core` includes payroll deductions, unpaid vendor bills, an equipment/loan register and inventory movements. These are useful examples for future importer work. The current importer supports transaction exports, customer invoices and jobs; it does not model accounts payable, an inventory ledger, depreciation or a complete payroll register.

Payroll payments and equipment purchases are already in the main statements. Uploading their reference breakdowns as another ledger can double-count expenses. Unpaid vendor bills must not become customer receivables. Inventory usage and depreciation are noncash accounting entries, not additional bank payments. These files are not part of the validated dashboard benchmark.

## Current accounting limits to look for

- The current headline calculation adds positive business amounts to revenue and negative amounts to expenses. Supplier refunds therefore appear in received money; customer refunds and chargebacks appear in expenses. Category totals retain their categories. This pack documents that behavior rather than representing formal financial statements.
- Card charges affect expenses before their checking autopay. Autopay is an excluded transfer. Cash is anchored to bank/cash balances; this is not a complete liabilities ledger.
- Imported transactions currently lack job-level cost allocation. Jobs have labor hours and a labor rate, but the app cannot attribute these statement material purchases to particular jobs. Do not expect complete job margins or add estimated job labor to posted payroll a second time.
- The benchmark's derived starting balance is **$106,031.45**. It is calculated backwards from closing cash after profit exclusions; it is not the raw May 1 combined account balance of $87,300. Entering $87,300 as an override changes the cash result, because the prototype does not carry excluded cash movements in its profit ledger.

## Regenerate and validate

From the repository root:

```bash
python3 scripts/generate_expanded_test_data.py
.venv/bin/python -m scripts.validate_expanded_test_data
```

Validation runs offline. It checks all category coverage, money direction, per-row cash balances, invoice/job counts and statuses, receivables, payment matching, scenario differences, duplicate behavior, invalid rows and payroll arithmetic. It rewrites `expected-results.json`. The ZIP is a separate snapshot; rebuild it after changing the CSVs or documentation.
