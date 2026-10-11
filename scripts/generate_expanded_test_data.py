"""Rebuild synthetic CSV upload fixtures; no credentials or network access required.

Run from the repository root with Python 3.12 or newer.
"""

import csv
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "test-data" / "expanded-finance"
D = Decimal


def money(value):
    return f"{D(str(value)):.2f}"


def write_csv(folder, name, columns, rows):
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / name).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(columns)
        writer.writerows(rows)


def ledgers(higher_cost=False):
    accounts = {name: [] for name in ("checking", "savings", "card", "cash")}
    invoices, jobs = [], []

    def add(account, month, day, description, vendor, category, amount):
        accounts[account].append((date(2026, month, day), description, vendor, category, D(str(amount))))

    customers = ["Cypress Court HOA", "Willow Market", "Ashford Library", "Brookhaven Cafe", "Meadow Works"]
    prices = {5: [7500, 5200, 12000, 3500, 2400], 6: [8500, 6000, 14000, 4500, 2800], 7: [6500, 4800, 15000, 5500, 3200]}
    types = ["Landscape maintenance", "Storefront remodel", "Accessible walkway", "Patio repair", "Irrigation service"]
    for month in (5, 6, 7):
        for index, (customer, total) in enumerate(zip(customers, prices[month]), 1):
            issued = date(2026, month, index + 2)
            job_id, invoice_id = f"CS-{month:02d}{index:02d}", f"INV-CS-{month:02d}{index:02d}"
            paid = total // 2 if index == 3 else (0 if index == 4 else total)
            paid_date = issued + timedelta(days=5) if paid else None
            invoices.append([invoice_id, job_id, customer, issued.isoformat(), (issued + timedelta(days=14)).isoformat(), money(total), money(paid), paid_date.isoformat() if paid_date and not (month == 6 and index in (1, 3)) else "", "Partially paid" if index == 3 else ("Unpaid" if index == 4 else "Paid")])
            jobs.append([job_id, customer, types[index - 1], date(2026, month, 1).isoformat(), issued.isoformat(), money(total), [38, 42, 96, 25, 18][index - 1], "Completed"])
            if paid:
                add("checking", month, paid_date.day, f"Customer payment {invoice_id}", customer, "income", paid)

        # Amounts here are cash posted, not gross wages plus a second net-wages payment.
        checking_costs = [
            (1, "Yard and office lease", "Juniper Industrial Park", "rent", 1650),
            (2, "Commercial liability policy", "Pine Shield Insurance", "insurance", 640 + (400 if higher_cost and month == 7 else 0)),
            (2, "Workers compensation premium", "Crew Cover Mutual", "insurance", 390),
            (3, "Electric and water service", "Cedar Utility District", "utilities", 245 + (month - 5) * 20),
            (3, "Business mobile and internet", "Field Signal Telecom", "utilities", 185),
            (4, "Dispatch scheduling subscription", "RouteNest", "software", 89),
            (4, "Second scheduling subscription", "CrewCalendar", "software", 59),
            (4, "Accounting subscription", "LedgerSprout", "software", 42),
            (9, "Drainage subcontractor invoice", "Stonepath Drainage", "subcontractors", 2200 + (month - 5) * 350),
            (10, "Plants gravel and landscape supplies", "Green Canopy Supply", "materials", 1750 + (month - 5) * 150),
            (12, "Net crew wages period one", "Cedar Stone Payroll", "payroll", 3500 + (month - 5) * 200 + (1300 if higher_cost and month == 7 else 0)),
            (13, "Payroll withholding tax remittance", "Payroll Tax Clearing", "payroll", 1050),
            (13, "Employer payroll taxes", "Payroll Tax Clearing", "payroll", 480),
            (15, "Monthly local search advertising", "LocalRoot Ads", "marketing", 275),
            (16, "City work permit", "Cedar City Permit Office", "permits", 125),
            (20, "Bookkeeping and legal consultation", "Clear Oak Advisors", "overhead", 320),
            (22, "Net crew wages period two", "Cedar Stone Payroll", "payroll", 3500 + (month - 5) * 200),
            (23, "Payroll withholding tax remittance two", "Payroll Tax Clearing", "payroll", 1050),
            (23, "Employer payroll taxes two", "Payroll Tax Clearing", "payroll", 480),
            (24, "State business tax payment", "State Revenue Office", "taxes", 280),
            (25, "Loan interest only", "Cedar Equipment Finance", "bank_fees", 150 - (month - 5) * 10),
            (28, "Merchant processing fee", "Checkout Grove", "bank_fees", 18),
            (28, "Service call receipt gross", "Walk-in service customers", "income", 600),
            (30 if month == 6 else 31, "Monthly bank maintenance fee", "Fictional Cedar Bank", "bank_fees", 12),
        ]
        for day, desc, vendor, category, amount in checking_costs:
            add("checking", month, day, desc, vendor, category, amount if category == "income" else -amount)
        add("checking", month, 5, "Transfer to business savings 8822", "Internal transfer", "transfer", -2500)
        add("savings", month, 5, "Transfer from business checking 5501", "Internal transfer", "transfer", 2500)
        add("checking", month, 6, "Transfer to petty cash box", "Internal transfer", "transfer", -250)
        add("cash", month, 6, "Cash box funding from checking", "Internal transfer", "transfer", 250)
        add("checking", month, 18, "Card autopay business card 7710", "Internal card payment", "transfer", -2400)
        add("card", month, 18, "Payment received from checking 5501", "Internal card payment", "transfer", 2400)
        add("checking", month, 25, "Equipment loan principal only", "Cedar Equipment Finance", "loan", -900)
        add("savings", month, 30 if month == 6 else 31, "Savings interest credited", "Fictional Cedar Bank", "income", 14 + month - 5)

        card_costs = [
            (7, "Lumber fasteners and masonry", "Timberline Trade Supply", "materials", 960 + (month - 5) * 120),
            (8, "Diesel fuel crew truck", "Trail Fuel Stop", "fuel", "86.45"),
            (8, "Diesel fuel crew truck", "Trail Fuel Stop", "fuel", "86.45"),  # two real purchases, same source
            (11, "Truck service oil and tires", "Oakbend Fleet Service", "vehicle", 440),
            (14, "Mini excavator rental", "Liftleaf Rentals", "equipment", 720),
            (17, "Tool blades and safety equipment", "Workshop Orchard", "equipment", "137.80"),
            (19, "Crew protective gear and first aid", "SafeCrew Outfitters", "overhead", "124.35"),
            (21, "Business website hosting", "Canopy Hosting", "marketing", 24),
            (26, "Card annual fee installment", "Fictional Business Card", "bank_fees", 15),
            (27, "Client meeting refreshments", "Maple Table Cafe", "overhead", "54.60"),
        ]
        for day, desc, vendor, category, amount in card_costs:
            add("card", month, day, desc, vendor, category, -D(str(amount)))
        add("cash", month, 10, "Fuel for mower cash purchase", "Trail Fuel Stop", "fuel", "-35.75")
        add("cash", month, 12, "Inspection counter cash fee", "Cedar City Permit Office", "permits", -25)
        add("cash", month, 14, "Office stationery cash purchase", "Paper Fern", "overhead", "-18.20")

    add("checking", 5, 1, "Owner startup cash contribution", "Business owner", "owner", 4000)
    add("checking", 5, 2, "Equipment loan proceeds", "Cedar Equipment Finance", "loan", 18000)
    add("checking", 5, 19, "Used commercial mower purchase", "Moss Ridge Equipment", "equipment", -4800)
    add("checking", 6, 17, "Supplier refund returned irrigation parts", "Green Canopy Supply", "materials", 230)
    add("checking", 5, 21, "Annual contractor license renewal", "Cedar City License Office", "permits", -225)
    add("checking", 6, 21, "Truck registration renewal", "State Vehicle Office", "vehicle", -135)
    add("checking", 6, 26, "Outgoing wire transfer service fee", "Fictional Cedar Bank", "bank_fees", -30)
    add("checking", 7, 17, "Customer refund service adjustment", "Willow Market", "income", -300)
    add("checking", 7, 19, "Employer crew health coverage contribution", "Crew Health Mutual", "insurance", -310)
    add("checking", 7, 23, "Employer retirement plan match", "Crew Retirement Plan", "payroll", -160)
    add("checking", 7, 27, "Disputed customer card payment chargeback", "Checkout Grove", "income", -160)
    add("checking", 7, 29, "Owner cash distribution", "Business owner", "owner", -1800)
    add("card", 7, 20, "Refund returned lumber", "Timberline Trade Supply", "materials", 120)
    add("card", 7, 22, "Personal purchase on business card", "Personal purchase", "owner", -95)
    add("card", 6, 23, "Crew safety training course", "Fieldcraft Training", "overhead", -145)
    add("card", 7, 24, "Jobsite highway tolls", "Cedar Toll Authority", "vehicle", "-18.50")
    add("card", 7, 24, "Jobsite parking meter", "Cedar City Parking", "vehicle", -12)
    add("card", 7, 25, "Material delivery freight charge", "Timberline Trade Supply", "materials", -48)
    add("card", 7, 26, "Late payment fee", "Fictional Business Card", "bank_fees", -22)
    add("cash", 6, 18, "Cash receipt small repair", "Walk-in repair customer", "income", 85)
    if higher_cost:
        add("card", 7, 29, "Emergency truck transmission repair", "Oakbend Fleet Service", "vehicle", -1450)
    jobs.extend([
        ["CS-QUOTE-01", "Fern Hollow Apartments", "Courtyard redesign", "2026-07-20", "", "18200.00", 0, "Quote"],
        ["CS-ACTIVE-01", "Copper Gate Offices", "Drainage installation", "2026-07-24", "", "9700.00", 16, "In progress"],
        ["CS-CANCEL-01", "Birch Lane Bakery", "Patio expansion", "2026-06-14", "", "4200.00", 0, "Cancelled"],
    ])
    for rows in accounts.values():
        rows.sort(key=lambda row: row[0])  # stable: preserves within-day posting order
    return accounts, invoices, jobs


def save_core(folder, higher_cost=False):
    accounts, invoices, jobs = ledgers(higher_cost)
    balances = {"checking": D(75000), "savings": D(12000), "cash": D(300)}
    for account in ("checking", "savings", "cash"):
        output = []
        for day, desc, vendor, category, amount in accounts[account]:
            balances[account] += amount
            if account == "checking":
                output.append([day.strftime("%m/%d/%Y"), desc, vendor, category, f"${abs(amount):,.2f}" if amount < 0 else "", f"${amount:,.2f}" if amount > 0 else "", money(balances[account]), "Fictional checking 5501"])
            elif account == "savings":
                output.append([day.isoformat(), desc, vendor, category, money(abs(amount)), "DEBIT" if amount < 0 else "CREDIT", money(balances[account]), "Fictional savings 8822"])
            else:
                output.append([day.isoformat(), desc, vendor, category, money(amount), money(balances[account])])
        if account == "checking":
            write_csv(folder, "business_checking.csv", ["Posted Date", "Description", "Payee", "Category", "Withdrawal", "Deposit", "Running Balance", "Account"], reversed(output))
        elif account == "savings":
            write_csv(folder, "business_savings.csv", ["Date", "Description", "Merchant", "Category", "Amount", "Direction", "Balance", "Account"], output)
        else:
            write_csv(folder, "petty_cash.csv", ["Date", "Description", "Merchant", "Category", "Amount", "Cash Balance"], output)
    write_csv(folder, "business_credit_card.csv", ["Date", "Description", "Merchant", "Category", "Charge Amount", "Account"], [[day.isoformat(), desc, vendor, category, f"({amount:.2f})" if amount > 0 else money(-amount), "Fictional card 7710"] for day, desc, vendor, category, amount in accounts["card"]])
    write_csv(folder, "customer_invoices.csv", ["Invoice Number", "Work Order", "Customer", "Issued", "Due", "Invoice Total", "Paid Amount", "Paid Date", "Status"], invoices)
    write_csv(folder, "jobs.csv", ["Job ID", "Customer", "Job Type", "Start Date", "End Date", "Quoted Price", "Labor Hours", "Status"], jobs)


def main():
    save_core(ROOT / "01-upload-together")
    save_core(ROOT / "02-higher-cost-scenario", higher_cost=True)
    accounts, _, _ = ledgers()
    overlap = accounts["checking"][4:16] + accounts["card"][:6]
    write_csv(ROOT / "03-duplicate-check", "overlapping_accounting_export.csv", ["Date", "Description", "Merchant", "Category", "Amount"], [[day.isoformat(), desc, vendor, category, money(amount)] for day, desc, vendor, category, amount in overlap])
    errors = ROOT / "04-error-checks"
    write_csv(errors, "crew_roster.csv", ["Crew ID", "Display Name", "Skill", "Shift"], [["TEST-C01", "Fictional Crew One", "Irrigation", "Morning"], ["TEST-C02", "Fictional Crew Two", "Carpentry", "Afternoon"]])
    headers = ["Date", "Description", "Merchant", "Category", "Amount"]
    bad = [["not-a-date", "Unreadable date", "Test vendor", "fuel", "-40.00"], ["2026-06-12", "Unreadable amount", "Test vendor", "materials", "unknown"], ["2026-06-13", "Zero dollar row", "Test vendor", "bank_fees", "0.00"]]
    write_csv(errors, "unreadable_dates_and_amounts.csv", headers, bad)
    write_csv(errors, "partial_bad_rows.csv", headers, [["2026-06-10", "Test service payment", "Test customer", "income", "500.00"], ["2026-06-11", "Test fuel purchase", "Test fuel stop", "fuel", "-85.25"], *bad])
    (errors / "empty.csv").write_bytes(b"")
    reference = ROOT / "05-reference-only-do-not-upload-with-core"
    # Payroll deductions + net wages = gross; bank files already contain net and tax remittances.
    write_csv(reference, "payroll_breakdown.csv", ["Pay Date", "Crew ID", "Gross Wages", "Federal Withholding", "State Withholding", "Employee Social Security", "Employee Medicare", "Net Wages", "Employer Payroll Taxes", "Included In Checking Export"], [["2026-07-12", "TEST-C01", "2480.00", "300.00", "68.68", "153.76", "35.96", "1921.60", "250.00", "Yes"], ["2026-07-12", "TEST-C02", "2470.00", "241.50", "61.15", "153.14", "35.81", "1978.40", "230.00", "Yes"]])
    write_csv(reference, "unpaid_vendor_bills.csv", ["Vendor Bill ID", "Vendor", "Bill Date", "Due Date", "Amount Owed", "Paid Amount", "Purpose"], [["VB-TEST-01", "Green Canopy Supply", "2026-07-25", "2026-08-24", "1680.00", "0.00", "Materials not yet paid - payable not customer receivable"], ["VB-TEST-02", "Stonepath Drainage", "2026-07-28", "2026-08-12", "2500.00", "0.00", "Subcontractor payable not yet paid"]])
    write_csv(reference, "equipment_and_loan_register.csv", ["Record Type", "Asset or Loan", "Original Amount", "Opening Principal", "Principal Repaid", "Remaining Principal", "Notes"], [["Asset", "Used commercial mower", "4800.00", "", "", "", "Cash purchase included in May checking; depreciation not modeled"], ["Loan", "Cedar equipment loan", "18000.00", "0.00", "2700.00", "15300.00", "Principal excluded from profit; interest separately posted"]])
    write_csv(reference, "inventory_movements.csv", ["Date", "SKU", "Item", "Quantity Change", "Unit Cost", "Reason"], [["2026-07-10", "TEST-MULCH", "Bagged mulch", 50, "6.20", "Purchased; paid amount already included in materials"], ["2026-07-16", "TEST-MULCH", "Bagged mulch", -18, "6.20", "Used on job; noncash movement, do not count a second expense"]])
    print(f"Created {len(list(ROOT.rglob('*.csv')))} synthetic CSV files in {ROOT}")


if __name__ == "__main__":
    main()
