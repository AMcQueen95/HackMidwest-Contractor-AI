"""Generate deterministic, fictional Ridgeline books with a reconciled demo story."""

import argparse
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

BUSINESS = {
    "name": "Ridgeline Heating & Air",
    "currency": "USD",
    "accounting_basis": "cash",
    "opening_balance": 45000,
    "opening_balance_date": "2026-08-01",
    "as_of_date": "2026-09-30",
    "labor_rate": 50,
    "tax_reserve_rate": 0.10,
}

JOBS = [
    (
        "AUG-001",
        "Prairie Medical",
        "commercial_hvac",
        "2026-08-01",
        "2026-08-05",
        "22000",
        "120",
        "completed",
    ),
    (
        "AUG-002",
        "Oakwood Apartments",
        "commercial_hvac",
        "2026-08-06",
        "2026-08-15",
        "18000",
        "100",
        "completed",
    ),
    (
        "AUG-003",
        "Cedar Homeowners",
        "residential_hvac",
        "2026-08-16",
        "2026-08-25",
        "20000",
        "80",
        "completed",
    ),
    (
        "SEP-001",
        "Westport Dental",
        "commercial_hvac",
        "2026-09-01",
        "2026-09-15",
        "12000",
        "80",
        "completed",
    ),
    (
        "SEP-002",
        "Brookside Property Mgmt",
        "plumbing",
        "2026-09-02",
        "2026-09-18",
        "9000",
        "60",
        "completed",
    ),
    (
        "SEP-003",
        "Maple Homeowners",
        "residential_hvac",
        "2026-09-01",
        "2026-09-06",
        "30000",
        "160",
        "completed",
    ),
    (
        "SEP-004",
        "Riverbend Apartments",
        "plumbing",
        "2026-09-18",
        "2026-09-22",
        "15070",
        "100",
        "completed",
    ),
]

INVOICES = [
    (
        "INV-A01",
        "AUG-001",
        "Prairie Medical",
        "2026-08-06",
        "2026-08-20",
        "22000",
        "22000",
        "2026-08-10",
    ),
    (
        "INV-A02",
        "AUG-002",
        "Oakwood Apartments",
        "2026-08-16",
        "2026-08-30",
        "18000",
        "18000",
        "2026-08-20",
    ),
    (
        "INV-A03",
        "AUG-003",
        "Cedar Homeowners",
        "2026-08-26",
        "2026-09-09",
        "20000",
        "20000",
        "2026-08-28",
    ),
    (
        "INV-S01",
        "SEP-001",
        "Westport Dental",
        "2026-09-16",
        "2026-09-20",
        "12000",
        "0",
        "",
    ),
    (
        "INV-S02",
        "SEP-002",
        "Brookside Property Mgmt",
        "2026-09-18",
        "2026-09-25",
        "9000",
        "0",
        "",
    ),
    (
        "INV-S03",
        "SEP-003",
        "Maple Homeowners",
        "2026-09-06",
        "2026-09-20",
        "30000",
        "30000",
        "2026-09-07",
    ),
    (
        "INV-S04",
        "SEP-004",
        "Riverbend Apartments",
        "2026-09-22",
        "2026-10-06",
        "15070",
        "15070",
        "2026-09-25",
    ),
]

TRANSACTIONS = [
    (
        "2026-08-10",
        "Invoice INV-A01 payment",
        "Prairie Medical",
        "income",
        "22000",
        "AUG-001",
    ),
    (
        "2026-08-20",
        "Invoice INV-A02 payment",
        "Oakwood Apartments",
        "income",
        "18000",
        "AUG-002",
    ),
    (
        "2026-08-28",
        "Invoice INV-A03 payment",
        "Cedar Homeowners",
        "income",
        "20000",
        "AUG-003",
    ),
    ("2026-08-03", "HVAC materials", "HVAC Supply", "materials", "-4000", "AUG-001"),
    ("2026-08-08", "HVAC materials", "HVAC Supply", "materials", "-3500", "AUG-002"),
    (
        "2026-08-18",
        "Residential HVAC materials",
        "HVAC Supply",
        "materials",
        "-2500",
        "AUG-003",
    ),
    ("2026-08-15", "Payroll first half", "Ridgeline Payroll", "payroll", "-12000", ""),
    ("2026-08-31", "Payroll second half", "Ridgeline Payroll", "payroll", "-12000", ""),
    ("2026-08-31", "Fleet fuel", "Fleet Fuel", "fuel", "-2000", ""),
    ("2026-08-01", "Business insurance", "Shop Insurer", "insurance", "-1000", ""),
    ("2026-08-01", "Dispatch subscription", "Housecall Pro", "software", "-169", ""),
    ("2026-08-01", "Email subscription", "Workspace", "software", "-36.43", ""),
    ("2026-08-10", "Local advertising", "Local Ads", "marketing", "-1000", ""),
    (
        "2026-08-31",
        "Shop rent utilities and overhead",
        "Shop Operations",
        "overhead",
        "-6794.57",
        "",
    ),
    (
        "2026-09-07",
        "Invoice INV-S03 payment",
        "Maple Homeowners",
        "income",
        "30000",
        "SEP-003",
    ),
    (
        "2026-09-25",
        "Invoice INV-S04 payment",
        "Riverbend Apartments",
        "income",
        "15070",
        "SEP-004",
    ),
    (
        "2026-09-04",
        "Rooftop unit after supplier price increase",
        "HVAC Supply",
        "materials",
        "-9232",
        "SEP-001",
    ),
    (
        "2026-09-07",
        "Plumbing materials",
        "Plumbing Supply",
        "materials",
        "-2500",
        "SEP-002",
    ),
    (
        "2026-09-02",
        "Residential HVAC materials",
        "HVAC Supply",
        "materials",
        "-1600",
        "SEP-003",
    ),
    (
        "2026-09-19",
        "Plumbing materials",
        "Plumbing Supply",
        "materials",
        "-668",
        "SEP-004",
    ),
    ("2026-09-15", "Payroll first half", "Ridgeline Payroll", "payroll", "-13000", ""),
    ("2026-09-30", "Payroll second half", "Ridgeline Payroll", "payroll", "-13000", ""),
    ("2026-09-30", "Fleet fuel", "Fleet Fuel", "fuel", "-2700", ""),
    ("2026-09-01", "Insurance at renewal", "Shop Insurer", "insurance", "-1260", ""),
    ("2026-09-01", "Dispatch subscription", "Housecall Pro", "software", "-169", ""),
    (
        "2026-09-01",
        "Second dispatch subscription",
        "ServiceTitan",
        "software",
        "-398",
        "",
    ),
    ("2026-09-10", "Local advertising", "Local Ads", "marketing", "-1500", ""),
    (
        "2026-09-30",
        "Shop rent utilities and overhead",
        "Shop Operations",
        "overhead",
        "-6873",
        "",
    ),
]


def generate(directory: Path):
    directory.mkdir(parents=True, exist_ok=True)
    datasets = {
        "transactions.csv": (
            ("date", "description", "vendor", "category", "amount", "job_id"),
            sorted(TRANSACTIONS, key=lambda row: row[0]),
        ),
        "jobs.csv": (
            (
                "job_id",
                "customer",
                "job_type",
                "start_date",
                "end_date",
                "quoted_price",
                "labor_hours",
                "status",
            ),
            JOBS,
        ),
        "invoices.csv": (
            (
                "invoice_id",
                "job_id",
                "customer",
                "issued",
                "due",
                "amount",
                "paid_amount",
                "paid_date",
            ),
            INVOICES,
        ),
    }
    for name, (header, rows) in datasets.items():
        with (directory / name).open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream, lineterminator="\n")
            writer.writerow(header)
            writer.writerows(rows)
    (directory / "business.json").write_text(
        json.dumps(BUSINESS, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "backend/app/data/sample")
    args = parser.parse_args()
    generate(args.output)
    print(f"Generated fictional books in {args.output}")
