"""What the test bank account in Plaid's sandbox contains: an HVAC shop's checking
account and credit card. Used once by create_plaid_sandbox_bank.py; the app never
reads this file. Plaid amounts: positive = money out. Dates roll forward so the
latest activity lands on the day the account is created.
"""

import random
from datetime import date, timedelta

CUSTOMERS = ["MILLER RESIDENCE", "WESTPORT DENTAL GRP", "BROOKSIDE PROPERTY MGMT", "OKAFOR HOME",
             "PATEL RESIDENCE", "CROWN CENTER RETAIL", "LINDQVIST HOME", "NGUYEN RESIDENCE"]


def _tx(day: date, amount: float, description: str) -> dict:
    return {"date_transacted": day.isoformat(), "date_posted": day.isoformat(),
            "amount": round(amount, 2), "description": description, "currency": "USD"}


def contractor_config(end: date = date(2026, 10, 9), months: int = 3, seed: int = 7) -> dict:
    rng = random.Random(seed)
    start = (end.replace(day=1) - timedelta(days=1)).replace(day=1)
    for _ in range(months - 1):
        start = (start - timedelta(days=1)).replace(day=1)
    checking, card = [], []
    day = start
    while day <= end:
        m, d = day.month, day.day
        if d == 1:
            checking += [_tx(day, 2400, "HOLMES RD PROPERTIES RENT"),
                         _tx(day, 1280 if m < 9 else 1610, "ACUITY INSURANCE PREMIUM"),
                         _tx(day, 169, "HOUSECALL PRO SUBSCRIPTION")]
            if m >= 9:
                checking.append(_tx(day, 398, "SERVICETITAN INC SUBSCRIPTION"))
        if d in (1, 15):
            checking.append(_tx(day, 6800 + rng.randint(-200, 200), "GUSTO PAYROLL NET PAY"))
            checking.append(_tx(day, 1400 + rng.randint(-80, 80), "GUSTO PAYROLL TAXES"))
        if d == 5:
            checking.append(_tx(day, 90, "INTUIT QUICKBOOKS ONLINE"))
        if d == 12:
            checking.append(_tx(day, 950 + (450 if m >= 9 else 0) + rng.randint(-50, 50), "GOOGLE ADS 4411"))
        if d == 18:
            checking += [_tx(day, 380 + rng.randint(-40, 60), "EVERGY KS ELECTRIC"),
                         _tx(day, 210, "VERIZON WIRELESS")]
        if d == 20:
            checking.append(_tx(day, 4200 + rng.randint(-600, 600), "PAYMENT TO CHASE CARD ENDING 4421"))
        if d == 28:
            checking.append(_tx(day, 3000, "ONLINE TRANSFER TO SAV XXXX9012 OWNER DRAW"))
        if day.weekday() < 5 and rng.random() < 0.85:  # customer payments most weekdays
            amount = rng.choice([rng.randint(280, 950), rng.randint(800, 1800), rng.randint(1800, 2600),
                                 rng.randint(7200, 9600) if rng.random() < 0.35 else rng.randint(900, 2000)])
            label = rng.choice(["MOBILE CHECK DEPOSIT", "STRIPE TRANSFER", f"ACH CREDIT {rng.choice(CUSTOMERS)}"])
            checking.append(_tx(day, -amount, label))
        if day.weekday() < 5 and rng.random() < 0.25:  # supply house runs
            vendor = rng.choice(["JOHNSTONE SUPPLY KC", "FERGUSON ENT #2231", "HVAC SUPPLY CO"])
            checking.append(_tx(day, rng.randint(350, 2400) * (1.3 if m >= 9 else 1), vendor))
        if day.weekday() < 6 and rng.random() < 0.45:  # card: fuel, hardware, meals
            pick = rng.random()
            if pick < 0.5:
                card.append(_tx(day, rng.randint(70, 140) * (1.35 if m >= 9 else 1),
                                rng.choice(["QT 0145 KANSAS CITY MO", "CASEYS #3381", "SHELL OIL 5741"])))
            elif pick < 0.8:
                card.append(_tx(day, rng.randint(40, 480), rng.choice(["THE HOME DEPOT PRO #2207", "LOWES #01542"])))
            else:
                card.append(_tx(day, rng.randint(14, 60), rng.choice(["JACKS STACK BBQ", "CHICK-FIL-A #0921"])))
        day += timedelta(days=1)
    card.append(_tx(start + timedelta(days=20), -4200, "PAYMENT THANK YOU"))
    return {
        "roll_dates_forward": True,
        "override_accounts": [
            {"type": "depository", "subtype": "checking", "starting_balance": 41250.0, "currency": "USD",
             "transactions": checking},
            {"type": "credit", "subtype": "credit card", "starting_balance": 1830.0, "currency": "USD",
             "transactions": card},
        ],
    }
