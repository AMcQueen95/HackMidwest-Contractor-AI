"""Canned Ridgeline Heating & Air numbers for building the agents.

These match the story in the README so demo questions get sensible answers
before app.finance exists. Delete this file once every function is real.
"""

_STUB = {"source": "stub"}

_MONTHS = {
    "2026-08": {"revenue": 58_240, "expenses": 49_310},
    "2026-09": {"revenue": 45_070, "expenses": 52_900},
}


def monthly_summary(month: str) -> dict:
    m = _MONTHS.get(month)
    if m is None:
        return {**_STUB, "error": f"No books for {month}", "months": sorted(_MONTHS)}
    return {**_STUB, "month": month, **m, "profit": m["revenue"] - m["expenses"]}


def expense_changes(month: str) -> dict:
    return {
        **_STUB,
        "month": month,
        "compared_to": "2026-08",
        "changes": [
            {"category": "Software", "previous": 205, "current": 567, "pct_change": 176.6},
            {"category": "Fuel", "previous": 2_140, "current": 2_890, "pct_change": 35.0},
            {"category": "Insurance", "previous": 1_850, "current": 2_330, "pct_change": 25.9},
            {"category": "Marketing", "previous": 1_200, "current": 1_640, "pct_change": 36.7},
            {"category": "Materials", "previous": 18_400, "current": 21_950, "pct_change": 19.3},
        ],
    }


def recurring_charges() -> dict:
    return {
        **_STUB,
        "charges": [
            {"vendor": "ServiceTitan", "category": "Software", "monthly": 398},
            {"vendor": "Housecall Pro", "category": "Software", "monthly": 169},
            {"vendor": "QuickBooks Online", "category": "Software", "monthly": 90},
            {"vendor": "Verizon Fleet", "category": "Phone", "monthly": 310},
        ],
        "possible_duplicates": [
            {"vendors": ["ServiceTitan", "Housecall Pro"], "reason": "Both are dispatch and scheduling apps"}
        ],
    }


_JOBS = {
    "J-1042": {"customer": "Westport Dental", "job_type": "Commercial rooftop unit",
               "quoted_price": 18_600, "materials": 13_480, "labor": 6_352, "status": "complete"},
    "J-1047": {"customer": "Hernandez residence", "job_type": "Residential furnace install",
               "quoted_price": 7_400, "materials": 3_150, "labor": 1_480, "status": "complete"},
    "J-1051": {"customer": "Brookside Property Mgmt", "job_type": "Commercial maintenance",
               "quoted_price": 8_600, "materials": 1_920, "labor": 3_040, "status": "complete"},
    "J-1055": {"customer": "Patel residence", "job_type": "Water heater replacement",
               "quoted_price": 2_850, "materials": 1_390, "labor": 640, "status": "complete"},
}


def _job_row(job_id: str, j: dict) -> dict:
    profit = j["quoted_price"] - j["materials"] - j["labor"]
    return {"job_id": job_id, **j, "profit": profit,
            "margin_pct": round(100 * profit / j["quoted_price"], 1)}


def job_profitability(job_id: str) -> dict:
    j = _JOBS.get(job_id)
    if j is None:
        return {**_STUB, "error": f"Unknown job {job_id}", "job_ids": sorted(_JOBS)}
    return {**_STUB, **_job_row(job_id, j)}


def losing_jobs() -> dict:
    rows = [_job_row(k, j) for k, j in _JOBS.items()]
    return {**_STUB, "jobs": [r for r in rows if r["profit"] < 0],
            "notes": {"J-1042": "Rooftop unit price rose $2,100 after the fixed bid was signed"}}


def margin_by_job_type() -> dict:
    rows = [_job_row(k, j) for k, j in _JOBS.items()]
    return {**_STUB, "job_types": [
        {"job_type": r["job_type"], "jobs": 1, "revenue": r["quoted_price"],
         "profit": r["profit"], "margin_pct": r["margin_pct"]} for r in rows
    ]}


def cash_balance() -> dict:
    return {**_STUB, "as_of": "2026-09-30", "cash": 23_480, "avg_monthly_expenses": 51_105}


def receivables() -> dict:
    return {
        **_STUB,
        "as_of": "2026-09-30",
        "total_outstanding": 21_000,
        "invoices": [
            {"invoice_id": "INV-2207", "customer": "Westport Dental", "amount": 12_400, "days_overdue": 34},
            {"invoice_id": "INV-2215", "customer": "Brookside Property Mgmt", "amount": 8_600, "days_overdue": 18},
        ],
    }


def affordability(amount: float) -> dict:
    cash = 23_480
    reserve = 25_552  # half a month of average expenses
    return {
        **_STUB,
        "amount": amount,
        "cash": cash,
        "reserve_target": reserve,
        "cash_after_purchase": cash - amount,
        "affordable_from_cash": cash - amount >= reserve,
        "affordable_if_receivables_collected": cash + 21_000 - amount >= reserve,
    }
