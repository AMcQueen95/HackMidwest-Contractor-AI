"""A full year of books for a fictional HVAC shop: Summit Air & Heat, Kansas City.

Built to exercise the HVAC sections, so it has what a real HVAC shop's year has:
- Seasons: busy in summer (cooling) and winter (heating), slow in spring and fall.
- Installs, repairs, ductwork and a few commercial rooftop units.
- About 140 maintenance-plan customers with spring AC and fall furnace tune-ups.
- Callbacks: return visits after some installs, at no charge.
- Equipment prices up about 9% from August, so some summer and fall installs
  were bid on old prices.

Run: python scripts/generate_hvac_sample.py
Writes backend/app/trades/samples/hvac/.
"""

import csv
import json
import random
from datetime import date, timedelta
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "backend" / "app" / "trades" / "samples" / "hvac"
START, END = date(2025, 10, 1), date(2026, 9, 30)
LABOR_RATE = 55
rng = random.Random(2026)

SEASON = {1: 1.15, 2: 1.0, 3: 0.6, 4: 0.55, 5: 0.85, 6: 1.25, 7: 1.45, 8: 1.3, 9: 0.85, 10: 0.6, 11: 0.8, 12: 1.1}
FIRST = ["Miller", "Okafor", "Patel", "Nguyen", "Lindqvist", "Brooks", "Delgado", "Schultz", "Kim", "Russo",
         "Whitfield", "Tran", "Coleman", "Haddad", "Sorensen", "Bauer", "Ellison", "Moreau", "Abernathy", "Garza",
         "Hughes", "Iverson", "Jensen", "Kowalski", "Lopez", "Mendez", "Novak", "Ortiz", "Price", "Quinn"]
STREETS = ["Ward Pkwy", "Main St", "Brookside Blvd", "Holmes Rd", "Wornall Rd", "State Line Rd", "Troost Ave",
           "Gillham Rd", "Oak St", "Broadway Blvd"]
COMMERCIAL = ["Westport Dental Group", "Crown Center Retail", "Plaza Fitness", "River Market Deli", "Waldo Vet Clinic"]


def customer() -> str:
    return f"{rng.choice(FIRST)} residence, {rng.randint(100, 9900)} {rng.choice(STREETS)}"


plan_members = [customer() for _ in range(140)]
jobs, invoices, txns = [], [], []
n = 0


def add_job(kind, title, cust, start, price, hours, cost_lines, pay_lag=None):
    """Record a job, its costs (tagged to the job), its invoice and payment."""
    global n
    n += 1
    job_id = f"SA-{n:04d}"
    end = start + timedelta(days={"install": 2, "commercial": 4, "ductwork": 2}.get(kind, 0))
    if end > END:
        return None
    jobs.append({"job_id": job_id, "customer": cust, "job_type": title, "start_date": start.isoformat(),
                 "end_date": end.isoformat(), "quoted_price": f"{price:.2f}", "labor_hours": hours,
                 "status": "completed"})
    for vendor, category, amount in cost_lines:
        txns.append({"date": start.isoformat(), "description": f"{vendor} for {job_id}", "vendor": vendor,
                     "category": category, "amount": f"{-amount:.2f}", "job_id": job_id})
    if price <= 0:
        return job_id
    commercial = kind == "commercial"
    due = end + timedelta(days=30 if commercial else 10)
    lag = pay_lag if pay_lag is not None else rng.choice([0, 0, 1, 2, 3, 5, 7, 12, 18])
    paid_on = end + timedelta(days=lag)
    paid = paid_on <= END
    invoices.append({"invoice_id": f"INV-{n:04d}", "job_id": job_id, "customer": cust, "issued": end.isoformat(),
                     "due": due.isoformat(), "amount": f"{price:.2f}", "paid_amount": f"{price if paid else 0:.2f}",
                     "paid_date": paid_on.isoformat() if paid else ""})
    if paid:
        txns.append({"date": paid_on.isoformat(), "description": f"Payment INV-{n:04d}", "vendor": cust,
                     "category": "income", "amount": f"{price:.2f}", "job_id": job_id})
    return job_id


def price_bump(day: date) -> float:
    return 1.09 if day >= date(2026, 8, 1) else 1.0


day = START
while day <= END:
    f, m = SEASON[day.month], day.month
    if day.weekday() < 6:
        # Repairs: steady, more in peak season.
        for _ in range(rng.choices([0, 1, 2, 3], weights=[2, 4, 3, 1 + 2 * f])[0]):
            title = rng.choice(["AC repair - not cooling", "Furnace repair - no heat", "Service call - diagnostic",
                                "Refrigerant leak repair", "Capacitor and contactor replacement",
                                "Thermostat repair"] if m in (5, 6, 7, 8, 9) else
                               ["Furnace repair - no heat", "Service call - diagnostic", "Igniter replacement",
                                "Blower motor repair", "Thermostat repair", "AC repair - not cooling"])
            price = round(rng.uniform(165, 950), -1)
            add_job("repair", title, customer(), day, price, rng.choice([1.5, 2, 2.5, 3, 4]),
                    [("Johnstone Supply", "materials", round(price * rng.uniform(0.1, 0.25), 2))])
        # Installs: peak season, bid with equipment around half the price.
        if rng.random() < 0.18 * f + 0.05:
            heat = m in (11, 12, 1, 2)
            title = rng.choice(["Furnace replacement", "Gas furnace and coil install"] if heat else
                               ["AC system replacement", "Heat pump install", "AC and furnace changeout"])
            price = round(rng.uniform(6800, 14500), -2)
            equipment_share = rng.uniform(0.44, 0.52) * price_bump(day)
            install = add_job("install", title, customer(), day, price, rng.choice([10, 12, 14, 16]),
                              [("Ferguson HVAC", "materials", round(price * equipment_share, 2)),
                               ("KCMO Permits", "permits", 185.0)])
            if install and rng.random() < 0.12:  # callback a couple of weeks later, no charge
                back = day + timedelta(days=rng.randint(7, 25))
                if back <= END:
                    add_job("callback", "Warranty callback - install follow-up", jobs[-1]["customer"], back, 0.0,
                            rng.choice([2, 3, 4]), [("Johnstone Supply", "materials", round(rng.uniform(40, 220), 2))])
        if rng.random() < 0.03 * f:
            price = round(rng.uniform(2600, 6200), -2)
            add_job("ductwork", "Ductwork replacement", customer(), day, price, rng.choice([16, 20, 24]),
                    [("Johnstone Supply", "materials", round(price * rng.uniform(0.3, 0.38), 2))])
        if rng.random() < 0.035:
            price = round(rng.uniform(12000, 22000), -2)
            add_job("commercial", "Commercial RTU replacement", rng.choice(COMMERCIAL), day, price,
                    rng.choice([40, 48, 60]),
                    [("Ferguson HVAC", "materials", round(price * rng.uniform(0.5, 0.58) * price_bump(day), 2)),
                     ("Midwest Crane & Rigging", "equipment", 1100.0), ("KCMO Permits", "permits", 450.0)],
                    pay_lag=rng.choice([20, 28, 35, 45]))
    day += timedelta(days=1)

# Maintenance plans: spring AC tune-ups (Mar-May) and fall furnace tune-ups (Sep-Nov).
for member in plan_members:
    for months, title in (((3, 4, 5), "AC tune-up - maintenance plan"), ((10, 11), "Furnace tune-up - maintenance plan"),
                          ((9,), "Furnace tune-up - maintenance plan")):
        if title.startswith("Furnace") and months == (9,) and rng.random() > 0.25:
            continue
        year = 2026 if months[0] < 10 else 2025
        visit = date(year, rng.choice(months), rng.randint(1, 27))
        if START <= visit <= END and not (months == (10, 11) and rng.random() < 0.25):
            add_job("maintenance", title, member, visit, 149.0, 1.5,
                    [("Johnstone Supply", "materials", round(rng.uniform(12, 28), 2))])

# Payments in early October for September work (before these books start).
for d in range(1, 15):
    if date(2025, 10, d).weekday() < 5:
        txns.append({"date": date(2025, 10, d).isoformat(), "description": "Customer payments for September work",
                     "vendor": "Stripe", "category": "income", "amount": f"{rng.uniform(2600, 4200):.2f}", "job_id": ""})

# Overhead.
for i in range(12):
    month_start = date(START.year + (START.month - 1 + i) // 12, (START.month - 1 + i) % 12 + 1, 1)
    f = SEASON[month_start.month]

    def pay(day_of_month, vendor, category, amount, description=None):
        d = month_start.replace(day=min(day_of_month, 28))
        txns.append({"date": d.isoformat(), "description": description or vendor, "vendor": vendor,
                     "category": category, "amount": f"{-amount:.2f}", "job_id": ""})

    pay(1, "Holmes Rd Properties", "rent", 3200)
    pay(1, "Acuity Insurance", "insurance", 1450 if month_start < date(2026, 7, 1) else 1720)
    pay(1, "ServiceTitan", "software", 398)
    pay(5, "Intuit QuickBooks", "software", 90)
    pay(1, "Gusto", "payroll", 19500 + 4000 * max(0, f - 1), "Payroll")
    pay(15, "Gusto", "payroll", 19500 + 4000 * max(0, f - 1), "Payroll")
    pay(12, "Google Ads", "marketing", 2400 if f < 0.9 else 1500)
    pay(18, "Evergy", "utilities", 420 + rng.randint(-40, 60))
    pay(20, "Verizon Business", "utilities", 260)
    pay(25, "Stripe", "bank_fees", round(450 * f + rng.randint(-40, 40), 2), "Card processing fees")
    for week in (3, 10, 17, 24):
        pay(week, "WEX Fleet Fuel", "fuel", round(620 * (0.7 + 0.3 * f), 2), "Fleet fuel")
    if i in (2, 7):
        pay(22, "Firestone Complete Auto", "vehicle", 1350, "Van service and tires")

OUT.mkdir(parents=True, exist_ok=True)
columns = {"transactions.csv": ["date", "description", "vendor", "category", "amount", "job_id"],
           "jobs.csv": ["job_id", "customer", "job_type", "start_date", "end_date", "quoted_price", "labor_hours",
                        "status"],
           "invoices.csv": ["invoice_id", "job_id", "customer", "issued", "due", "amount", "paid_amount", "paid_date"]}
for name, rows in (("transactions.csv", sorted(txns, key=lambda r: r["date"])), ("jobs.csv", jobs),
                   ("invoices.csv", invoices)):
    with open(OUT / name, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns[name], lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
(OUT / "business.json").write_text(json.dumps({
    "name": "Summit Air & Heat", "currency": "USD", "accounting_basis": "cash", "opening_balance": 92000,
    "opening_balance_date": START.isoformat(), "as_of_date": END.isoformat(), "labor_rate": LABOR_RATE,
    "tax_reserve_rate": 0.25}, indent=2) + "\n")
print(f"{len(jobs)} jobs, {len(invoices)} invoices, {len(txns)} transactions -> {OUT}")
