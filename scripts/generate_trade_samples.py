"""A full year of books for a fictional plumbing shop and electrical contractor.

Riverside Plumbing Co. (Kansas City):
- Repairs and drain cleaning every day; emergencies spike in the January-February freeze.
- Emergency and after-hours calls priced only about 20% above regular calls.
- About 1 in 6 camera/drain jobs turns into a sewer line or repipe job within weeks.
- Water heater installs, with tank prices up about 10% from July.

Brightline Electric (Kansas City):
- Service calls, panel upgrades, EV chargers, lighting.
- Remodels and new-construction jobs billed in stages (deposit, progress, final);
  a few are still in progress at year end with work done but not billed.
- Permits on most panel, EV and remodel jobs.
- Wire and copper up about 12% from June; some open quotes were priced before that.

Run: python scripts/generate_trade_samples.py
Writes backend/app/trades/samples/plumbing/ and backend/app/trades/samples/electrical/.
"""

import csv
import json
import random
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "backend" / "app" / "trades" / "samples"
START, END = date(2025, 10, 1), date(2026, 9, 30)
NAMES = ["Miller", "Okafor", "Patel", "Nguyen", "Lindqvist", "Brooks", "Delgado", "Schultz", "Kim", "Russo",
         "Whitfield", "Tran", "Coleman", "Haddad", "Sorensen", "Bauer", "Ellison", "Moreau", "Garza", "Hughes",
         "Iverson", "Jensen", "Kowalski", "Lopez", "Mendez", "Novak", "Ortiz", "Price", "Quinn", "Reyes"]
STREETS = ["Ward Pkwy", "Main St", "Brookside Blvd", "Holmes Rd", "Wornall Rd", "State Line Rd", "Troost Ave",
           "Gillham Rd", "Oak St", "Broadway Blvd"]


class Books:
    def __init__(self, prefix: str, seed: int):
        self.rng, self.prefix = random.Random(seed), prefix
        self.jobs, self.invoices, self.txns, self.n, self.inv = [], [], [], 0, 0

    def customer(self) -> str:
        r = self.rng
        return f"{r.choice(NAMES)} residence, {r.randint(100, 9900)} {r.choice(STREETS)}"

    def cost(self, day, vendor, category, amount, job_id=""):
        self.txns.append({"date": day.isoformat(), "description": f"{vendor}" + (f" for {job_id}" if job_id else ""),
                          "vendor": vendor, "category": category, "amount": f"{-amount:.2f}", "job_id": job_id})

    def bill(self, job_id, cust, issued, amount, due_days=10, lag=None):
        """An invoice and, if paid by the end of the books, its payment."""
        self.inv += 1
        lag = lag if lag is not None else self.rng.choice([0, 0, 1, 2, 3, 5, 8, 12, 20])
        paid_on = issued + timedelta(days=lag)
        paid = paid_on <= END
        self.invoices.append({"invoice_id": f"INV-{self.prefix}{self.inv:04d}", "job_id": job_id, "customer": cust,
                              "issued": issued.isoformat(), "due": (issued + timedelta(days=due_days)).isoformat(),
                              "amount": f"{amount:.2f}", "paid_amount": f"{amount if paid else 0:.2f}",
                              "paid_date": paid_on.isoformat() if paid else ""})
        if paid:
            self.txns.append({"date": paid_on.isoformat(), "description": f"Payment INV-{self.prefix}{self.inv:04d}",
                              "vendor": cust, "category": "income", "amount": f"{amount:.2f}", "job_id": job_id})

    def job(self, title, cust, start, price, hours, costs, days=0, status="completed", bill=True, lag=None):
        end = start + timedelta(days=days)
        if start > END:
            return None
        if status == "completed" and end > END:
            status = "in_progress"
        self.n += 1
        job_id = f"{self.prefix}-{self.n:04d}"
        self.jobs.append({"job_id": job_id, "customer": cust, "job_type": title, "start_date": start.isoformat(),
                          "end_date": end.isoformat() if status == "completed" else "",
                          "quoted_price": f"{price:.2f}", "labor_hours": hours, "status": status})
        for vendor, category, amount in costs:
            self.cost(start, vendor, category, amount, job_id)
        if bill and status == "completed" and price > 0:
            self.bill(job_id, cust, end, price, lag=lag)
        return job_id

    def overhead(self, monthly: list[tuple[int, str, str, float]], payroll: float, season: dict):
        for i in range(12):
            first = date(START.year + (START.month - 1 + i) // 12, (START.month - 1 + i) % 12 + 1, 1)
            f = season[first.month]
            for day, vendor, category, amount in monthly:
                self.cost(first.replace(day=day), vendor, category, amount * (f if category == "fuel" else 1))
            for day in (1, 15):
                self.cost(first.replace(day=day), "Gusto", "payroll", payroll * (0.9 + 0.1 * f))
        for d in range(1, 15):  # payments in early October for September work
            if date(2025, 10, d).weekday() < 5:
                self.txns.append({"date": date(2025, 10, d).isoformat(), "description": "Customer payments for September work",
                                  "vendor": "Stripe", "category": "income",
                                  "amount": f"{self.rng.uniform(1800, 3000):.2f}", "job_id": ""})

    def write(self, folder: str, name: str, opening: float, labor_rate: float):
        out = ROOT / folder
        out.mkdir(parents=True, exist_ok=True)
        cols = {"transactions.csv": ["date", "description", "vendor", "category", "amount", "job_id"],
                "jobs.csv": ["job_id", "customer", "job_type", "start_date", "end_date", "quoted_price", "labor_hours",
                             "status"],
                "invoices.csv": ["invoice_id", "job_id", "customer", "issued", "due", "amount", "paid_amount",
                                 "paid_date"]}
        for file, rows in (("transactions.csv", sorted(self.txns, key=lambda r: r["date"])), ("jobs.csv", self.jobs),
                           ("invoices.csv", self.invoices)):
            with open(out / file, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=cols[file], lineterminator="\n")
                w.writeheader()
                w.writerows(rows)
        (out / "business.json").write_text(json.dumps({
            "name": name, "currency": "USD", "accounting_basis": "cash", "opening_balance": opening,
            "opening_balance_date": START.isoformat(), "as_of_date": END.isoformat(), "labor_rate": labor_rate,
            "tax_reserve_rate": 0.25}, indent=2) + "\n")
        print(f"{name}: {len(self.jobs)} jobs, {len(self.invoices)} invoices, {len(self.txns)} transactions -> {out}")


def days():
    d = START
    while d <= END:
        yield d
        d += timedelta(days=1)


# --- Riverside Plumbing Co. ---------------------------------------------------------------

def plumbing():
    b = Books("RP", 31)
    r = b.rng
    freeze = {12: 1.3, 1: 2.2, 2: 1.8}
    season = {m: 1.0 for m in range(1, 13)} | {12: 1.1, 1: 1.25, 2: 1.2, 7: 0.95, 8: 0.95}
    for day in days():
        if day.weekday() < 6:
            for _ in range(r.choices([1, 2, 3, 4], weights=[2, 4, 3, 2])[0]):
                title = r.choice(["Leak repair - kitchen sink", "Toilet repair", "Faucet replacement",
                                  "Shutoff valve replacement", "Garbage disposal repair", "Sump pump repair",
                                  "Service call - running toilet"])
                price = round(r.uniform(150, 620), -1)
                b.job(title, b.customer(), day, price, r.choice([1, 1.5, 2, 3]),
                      [("Ferguson Plumbing", "materials", round(price * r.uniform(0.12, 0.28), 2))])
            for _ in range(r.choices([0, 1, 2], weights=[3, 4, 2])[0]):
                camera = r.random() < 0.4
                price = round(r.uniform(180, 450) + (220 if camera else 0), -1)
                cust = b.customer()
                b.job("Drain cleaning with camera inspection" if camera else "Drain cleaning - main line clog", cust,
                      day, price, r.choice([1.5, 2, 2.5]), [("RIDGID Supply", "materials", round(r.uniform(15, 45), 2))])
                if camera and r.random() < 0.38:  # the camera found a broken line
                    later = day + timedelta(days=r.randint(5, 40))
                    big = round(r.uniform(6500, 14500), -2)
                    b.job(r.choice(["Sewer line replacement", "Trenchless sewer repair", "Whole-house repipe"]), cust,
                          later, big, r.choice([24, 32, 40]),
                          [("Ferguson Plumbing", "materials", round(big * r.uniform(0.22, 0.3), 2)),
                           ("KC Excavating", "subcontractors", round(big * r.uniform(0.12, 0.18), 2)),
                           ("KCMO Permits", "permits", 260.0)], days=2)
        # Emergencies: nights and weekends, many more in the freeze.
        if r.random() < 0.35 * freeze.get(day.month, 1.0):
            regular = round(r.uniform(180, 620), -1)
            price = round(regular * r.uniform(1.1, 1.3), -1)  # a thin premium for after hours
            b.job(r.choice(["Emergency - burst pipe", "After-hours drain backup", "Emergency - no water",
                            "Weekend emergency leak"]), b.customer(), day, price, r.choice([2, 3, 4]),
                  [("Ferguson Plumbing", "materials", round(price * r.uniform(0.15, 0.3), 2))])
        if day.weekday() < 5 and r.random() < 0.22:
            price = round(r.uniform(1650, 3200), -1)
            tank = r.uniform(0.38, 0.46) * (1.1 if day >= date(2026, 7, 1) else 1.0)
            b.job(r.choice(["Water heater replacement - 50 gal", "Water heater replacement - 40 gal",
                            "Tankless water heater install"]), b.customer(), day, price, r.choice([4, 5, 6]),
                  [("Ferguson Plumbing", "materials", round(price * tank, 2)), ("KCMO Permits", "permits", 95.0)])
        if day.weekday() < 5 and r.random() < 0.06:
            b.job("Warranty callback - leak at fitting", b.customer(), day, 0.0, r.choice([1, 2]),
                  [("Ferguson Plumbing", "materials", round(r.uniform(10, 60), 2))])
    b.overhead([(1, "Holmes Rd Properties", "rent", 2600), (1, "Acuity Insurance", "insurance", 1250),
                (1, "Housecall Pro", "software", 169), (5, "Intuit QuickBooks", "software", 90),
                (12, "Google Ads", "marketing", 1600), (18, "Evergy", "utilities", 380),
                (20, "Verizon Business", "utilities", 220), (3, "WEX Fleet Fuel", "fuel", 900),
                (17, "WEX Fleet Fuel", "fuel", 900), (25, "Stripe", "bank_fees", 380)], 16500, season)
    b.write("plumbing", "Riverside Plumbing Co.", 61000, 50)


# --- Brightline Electric ----------------------------------------------------------------------

def electrical():
    b = Books("BE", 47)
    r = b.rng
    copper = lambda d: 1.12 if d >= date(2026, 6, 1) else 1.0  # noqa: E731
    season = {m: 1.0 for m in range(1, 13)}
    for day in days():
        if day.weekday() >= 5:
            continue
        for _ in range(r.choices([0, 1, 2, 3], weights=[1, 4, 3, 1])[0]):
            title = r.choice(["Service call - outlets not working", "GFCI outlet install", "Breaker tripping - troubleshoot",
                              "Light switch repair", "Ceiling fan install", "Service call - flickering lights"])
            price = round(r.uniform(150, 520), -1)
            b.job(title, b.customer(), day, price, r.choice([1, 1.5, 2, 3]),
                  [("Crescent Electric Supply", "materials", round(price * r.uniform(0.1, 0.22) * copper(day), 2))])
        if r.random() < 0.28:
            price = round(r.uniform(2600, 5400), -2)
            b.job(r.choice(["Panel upgrade - 200 amp", "Main panel replacement", "Subpanel install"]), b.customer(),
                  day, price, r.choice([8, 10, 12]),
                  [("Crescent Electric Supply", "materials", round(price * r.uniform(0.3, 0.38) * copper(day), 2)),
                   ("KCMO Permits", "permits", 185.0)], days=1)
        if r.random() < 0.22:
            price = round(r.uniform(950, 2300), -1)
            b.job(r.choice(["EV charger install - Level 2", "Tesla wall connector install"]), b.customer(), day, price,
                  r.choice([4, 5, 6]),
                  [("Crescent Electric Supply", "materials", round(price * r.uniform(0.25, 0.33) * copper(day), 2)),
                   ("KCMO Permits", "permits", 95.0)])
        if r.random() < 0.15:
            price = round(r.uniform(450, 1600), -1)
            b.job(r.choice(["Recessed lighting install", "LED lighting retrofit", "Landscape lighting"]), b.customer(),
                  day, price, r.choice([3, 4, 6]),
                  [("Crescent Electric Supply", "materials", round(price * r.uniform(0.3, 0.4), 2))])
        forced = day in (date(2026, 8, 18), date(2026, 9, 8))  # make sure some are mid-job at year end
        if forced or r.random() < 0.06:  # big jobs, billed in stages
            construction = forced or r.random() < 0.4
            price = round(r.uniform(22000, 46000) if construction else r.uniform(6500, 18000), -2)
            span = r.randint(30, 75) if construction else r.randint(10, 30)
            cust = r.choice(["Waldo Office Partners", "River Market Lofts LLC", "Plaza Dental Suite",
                             "Northland Retail Center"]) if construction else b.customer()
            title = r.choice(["New construction rough-in and trim", "Tenant finish - commercial suite"]) if construction \
                else r.choice(["Kitchen remodel wiring", "Basement finish - electrical", "Whole-house rewire"])
            share = r.uniform(0.34, 0.42) * copper(day)
            end = day + timedelta(days=span)
            done = end <= END
            progress = 1.0 if done else max(0.2, (END - day).days / span)
            job_id = b.job(title, cust, day, price, round((80 if construction else 40) * progress), [], days=span,
                           status="completed" if done else "in_progress", bill=False)
            # Materials and permits as the work happens.
            for step in range(4):
                when = day + timedelta(days=int(span * step / 4))
                if when <= END:
                    b.cost(when, "Crescent Electric Supply", "materials", round(price * share / 4, 2), job_id)
            b.cost(day, "KCMO Permits", "permits", 450.0 if construction else 240.0, job_id)
            # Billing: 30% deposit, 40% at rough-in, 30% at the end.
            b.bill(job_id, cust, day, round(price * 0.3, 2), due_days=15, lag=r.choice([2, 5, 10]))
            mid = day + timedelta(days=span // 2 + r.randint(5, 20))  # progress bills often go out late
            if mid <= END:
                b.bill(job_id, cust, mid, round(price * 0.4, 2), due_days=30, lag=r.choice([10, 20, 30]))
            if done:
                b.bill(job_id, cust, end, round(price - round(price * 0.3, 2) - round(price * 0.4, 2), 2),
                       due_days=30, lag=r.choice([15, 25, 40]))
        if day >= date(2026, 7, 15) and r.random() < 0.08:  # open quotes, some priced before copper rose
            quoted_on = day - timedelta(days=r.randint(0, 75))
            b.job(r.choice(["Whole-house rewire", "Kitchen remodel wiring", "Tenant finish - commercial suite"]),
                  b.customer(), quoted_on, round(r.uniform(7000, 26000), -2), 0, [], status="quoted", bill=False)
        if r.random() < 0.05:
            b.job("Callback - breaker issue after panel upgrade", b.customer(), day, 0.0, r.choice([1, 2]),
                  [("Crescent Electric Supply", "materials", round(r.uniform(20, 90), 2))])
    b.overhead([(1, "Holmes Rd Properties", "rent", 2900), (1, "Acuity Insurance", "insurance", 1600),
                (1, "ServiceTitan", "software", 398), (5, "Intuit QuickBooks", "software", 90),
                (12, "Google Ads", "marketing", 1400), (18, "Evergy", "utilities", 360),
                (20, "Verizon Business", "utilities", 240), (3, "WEX Fleet Fuel", "fuel", 850),
                (17, "WEX Fleet Fuel", "fuel", 850), (8, "Sunbelt Rentals", "equipment", 650),
                (25, "Stripe", "bank_fees", 420)], 14500, season)
    b.write("electrical", "Brightline Electric", 88000, 62)


if __name__ == "__main__":
    plumbing()
    electrical()
