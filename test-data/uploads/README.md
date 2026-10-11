# Upload test files

Each numbered folder contains the four files accepted by `POST /api/upload`.
These are synthetic demo books based on the repository sample, not real company records.

The dashboard no longer has a four-file picker; its **Add records** step takes CSV exports
(see `test-data/imports`) or a bank connection. Send these sets to the endpoint directly,
all four files from ONE folder with their exact filenames:
transactions.csv, jobs.csv, invoices.csv, and business.json.
The browser tests seed companies the same way. Where a section below says "upload",
it means through that endpoint.

## 1. 01-baseline: valid sample books

Upload these first. The badge becomes **Your books** because this is an upload,
even though the values match the built-in sample.

September 2026:
- Received: $45,070
- Expenses: $52,900
- Profit: -$7,830
- A $15,000 purchase fails the reserve requirement.

Select August 2026: profit should be $15,000.

## 2. 02-higher-insurance: valid changed books

Upload these next. September insurance has already been changed from -1260 to
-1500; you do not need to edit anything.

September 2026:
- Received: $45,070
- Expenses: $53,140
- Profit: -$8,070
- Shortfall for a $15,000 purchase: $16,903

This verifies that uploads change both the dashboard and purchase calculator.

## 3. 03-invalid-invoices: intentional validation failure

Upload these after folder 02. invoices.csv intentionally has missing columns.
The other three files match folder 02.

Expected:
- A validation error mentioning invoices.csv and missing columns.
- The upload dialog stays open.
- After closing it, expenses remain $53,140 and profit remains -$8,070.

## Reset and session check

Open the upload dialog and choose **Use sample books**. September expenses
return to $52,900 and the badge becomes **Sample data**.

After uploading folder 02, opening the app in a new private/incognito browser
window should still show sample expenses of $52,900 in that separate session.

Uploaded books are temporary. Restarting the backend restores sample data;
sessions can also expire after an hour of inactivity.
