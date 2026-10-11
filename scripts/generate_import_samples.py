"""Messy, realistic exports for testing the any-CSV import (test-data/imports/).

Each file mimics a real export format with its quirks: newest-first rows and a
running balance (Chase), charges as positive numbers (Amex), title lines and a
totals row (QuickBooks), split debit/credit columns (credit union), and one file
that isn't financial at all. The books tell one story: Ridgeline Heating & Air,
August-September 2026, with two invoices unpaid.

Run: python scripts/generate_import_samples.py
"""

import csv
import random
from datetime import date, timedelta
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "test-data" / "imports"
rng = random.Random(11)

# Invoices: (number, customer, issued, total, paid, job)
INVOICES = [
    ("1041", "Miller Residence", date(2026, 8, 4), 8400.00, True, "J-101"),
    ("1042", "Okafor Home", date(2026, 8, 7), 640.00, True, "J-102"),
    ("1043", "Crown Center Retail", date(2026, 8, 12), 6200.00, True, "J-103"),
    ("1044", "Patel Residence", date(2026, 8, 19), 2350.00, True, "J-104"),
    ("1045", "Lindqvist Home", date(2026, 8, 26), 495.00, True, "J-105"),
    ("1046", "Nguyen Residence", date(2026, 9, 3), 9100.00, True, "J-106"),
    ("1047", "Westport Dental Group", date(2026, 9, 10), 12000.00, False, "J-107"),
    ("1048", "Okafor Home", date(2026, 9, 15), 780.00, True, "J-108"),
    ("1049", "Brookside Property Mgmt", date(2026, 9, 18), 9000.00, False, "J-109"),
    ("1050", "Patel Residence", date(2026, 9, 24), 1950.00, True, "J-110"),
]
JOB_TYPES = {"J-101": "AC install", "J-102": "AC repair", "J-103": "Commercial service", "J-104": "Water heater install",
             "J-105": "Furnace repair", "J-106": "AC install", "J-107": "Commercial RTU install", "J-108": "AC repair",
             "J-109": "Ductwork", "J-110": "Water heater install"}
HOURS = {"J-101": 18, "J-102": 3, "J-103": 26, "J-104": 7, "J-105": 3, "J-106": 20, "J-107": 96, "J-108": 4,
         "J-109": 40, "J-110": 6}


def write(name, rows, header=None, preamble=(), footer=()):
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / name, "w", newline="") as f:
        for line in preamble:
            f.write(line + "\n")
        w = csv.writer(f)
        if header:
            w.writerow(header)
        w.writerows(rows)
        for line in footer:
            w.writerow(line)


# --- Chase business checking: newest first, deposits positive, running balance ---
checking = []
for num, customer, issued, total, paid, _ in INVOICES:
    if paid:
        checking.append((issued + timedelta(days=rng.randint(2, 9)), f"ONLINE PAYMENT FROM {customer.upper()} INV {num}",
                         total, "ACH_CREDIT"))
for month in (8, 9):
    checking += [
        (date(2026, month, 1), "HOLMES RD PROPERTIES RENT", -2400.00, "ACH_DEBIT"),
        (date(2026, month, 1), "ACUITY INSURANCE PREMIUM", -(1000.00 if month == 8 else 1260.00), "ACH_DEBIT"),
        (date(2026, month, 1), "HOUSECALL PRO SUBSCRIPTION", -169.00, "DEBIT_CARD"),
        (date(2026, month, 15), "GUSTO PAYROLL 0815" if month == 8 else "GUSTO PAYROLL 0915", -6500.00, "ACH_DEBIT"),
        (date(2026, month, 30 if month == 9 else 31), "GUSTO PAYROLL MONTH END", -(6500.00 if month == 8 else 7000.00),
         "ACH_DEBIT"),
        (date(2026, month, 12), "GOOGLE *ADS4411", -(1000.00 if month == 8 else 1500.00), "DEBIT_CARD"),
        (date(2026, month, 18), "EVERGY KS ELECTRIC", -(412.37 if month == 8 else 398.15), "ACH_DEBIT"),
        (date(2026, month, 22), "PAYMENT TO CHASE CARD ENDING 4421", -2600.00, "LOAN_PMT"),
        (date(2026, month, 28), "ONLINE TRANSFER TO SAV XXXX9012", -3000.00, "ACCT_XFER"),
    ]
checking.append((date(2026, 9, 1), "SERVICETITAN INC", -398.00, "DEBIT_CARD"))
for _ in range(28):  # card payments from service calls, paid out by Stripe
    day = date(2026, rng.choice([8, 9]), rng.randint(2, 29))
    checking.append((day, "STRIPE TRANSFER ST-" + str(rng.randint(100000, 999999)), round(rng.uniform(280, 950), 2),
                     "ACH_CREDIT"))
for _ in range(9):
    day = date(2026, rng.choice([8, 9]), rng.randint(2, 28))
    vendor = rng.choice(["JOHNSTONE SUPPLY KC", "FERGUSON ENT #2231", "HVAC SUPPLY CO 0098"])
    checking.append((day, f"{vendor} PURCHASE", -round(rng.uniform(600, 2800) * (1.4 if day.month == 9 else 1), 2),
                     "DEBIT_CARD"))
checking.sort(key=lambda r: r[0])
balance, rows = 38500.00, []
for day, desc, amount, kind in checking:
    balance = round(balance + amount, 2)
    rows.append(("DEBIT" if amount < 0 else "CREDIT", day.strftime("%m/%d/%Y"), desc, f"{amount:.2f}", kind,
                 f"{balance:.2f}", ""))
write("Chase4421_Activity_20261001.CSV", list(reversed(rows)),
      ["Details", "Posting Date", "Description", "Amount", "Type", "Balance", "Check or Slip #"])

# --- Amex business card: charges positive, payments negative ---
card = []
for _ in range(30):
    day = date(2026, rng.choice([8, 9]), rng.randint(1, 30))
    pick = rng.random()
    if pick < 0.45:
        card.append((day, rng.choice(["QT 0145 KANSAS CITY MO", "CASEYS GEN STORE 3381"]),
                     round(rng.uniform(70, 140) * (1.35 if day.month == 9 else 1), 2)))
    elif pick < 0.8:
        card.append((day, rng.choice(["THE HOME DEPOT PRO #2207", "LOWES #01542"]), round(rng.uniform(40, 480), 2)))
    else:
        card.append((day, rng.choice(["JACK STACK BBQ - FREIGHT", "KC PERMITS OFFICE"]), round(rng.uniform(25, 450), 2)))
card += [(date(2026, 8, 24), "AUTOPAY PAYMENT - THANK YOU", -2600.00), (date(2026, 9, 24), "AUTOPAY PAYMENT - THANK YOU", -2600.00)]
card.sort(key=lambda r: r[0])
write("amex_activity.csv", [(d.strftime("%m/%d/%Y"), desc, "R. GARCIA", "-41007", f"{amt:.2f}") for d, desc, amt in card],
      ["Date", "Description", "Card Member", "Account #", "Amount"])

# --- QuickBooks Online "Invoice List" report: title lines, money formatting, total row ---
qb = []
for num, customer, issued, total, paid, _ in INVOICES:
    qb.append((issued.strftime("%m/%d/%Y"), "Invoice", num, customer, (issued + timedelta(days=15)).strftime("%m/%d/%Y"),
               f"{total:,.2f}", "0.00" if paid else f"{total:,.2f}"))
write("Ridgeline Heating & Air_Invoice List.csv", qb,
      ["Date", "Transaction type", "Num", "Customer full name", "Due date", "Amount", "Open balance"],
      preamble=["Ridgeline Heating & Air", "Invoice List", "All Dates", ""],
      footer=[("TOTAL", "", "", "", "", f"{sum(i[3] for i in INVOICES):,.2f}", "21,000.00")])

# --- Jobber jobs export ---
jobs = []
for num, customer, issued, total, paid, job in INVOICES:
    jobs.append((job.replace("J-", ""), customer, JOB_TYPES[job], (issued - timedelta(days=3)).strftime("%b %d, %Y"),
                 issued.strftime("%b %d, %Y"), f"${total:,.2f}", HOURS[job], "Archived" if paid else "Requires invoicing"))
write("jobs_export_2026-10-01.csv", jobs,
      ["Job #", "Client name", "Title", "Start date", "Completed date", "Total ($)", "Labor hours", "Job status"])

# --- A credit union savings account with split debit/credit columns ---
write("FirstCU_savings.csv", [
    ("2026-08-28", "TRANSFER FROM CHECKING 4421", "", "3000.00", "15200.00"),
    ("2026-09-28", "TRANSFER FROM CHECKING 4421", "", "3000.00", "18213.40"),
    ("2026-09-30", "DIVIDEND", "", "13.40", "18213.40"),
], ["Date", "Memo", "Debit", "Credit", "Running Balance"])

# --- Not financial ---
write("crew_contacts.csv", [("Ray Garcia", "Owner", "816-555-0142"), ("Dee Morales", "Lead tech", "816-555-0187")],
      ["Name", "Role", "Phone"])
print(f"wrote {len(list(OUT.glob('*.csv'))) + len(list(OUT.glob('*.CSV')))} files to {OUT}")
