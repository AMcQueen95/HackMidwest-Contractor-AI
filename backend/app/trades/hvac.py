"""HVAC: the sections an HVAC shop owner needs, calculated from the books.

Every section returns the same shape so one frontend component and one agent
tool layer can handle any trade:

    {"key", "title", "question", "status": "ok" | "needs_data", "period",
     "headline": [{"label", "value", "format", "tone"}],
     "table": {"columns": [{"key", "label", "format"}], "rows": [...]},
     "takeaway": str, "note": str | None}

Formats: money, percent, count, months, date, text. Takeaways are written by
code from the numbers, never by a model.
"""

from datetime import date
import re
from statistics import median

import pandas as pd

from backend.app.data import Books
from backend.app.finance import cash_balance, monthly_summary
from backend.app.trades.common import (estimated, jobs_in, label, months, needs, pct, period, plain, section, sorter,
                                       work_mix)

KEY, NAME = "hvac", "HVAC"

# --- Sorting jobs -------------------------------------------------------------------

SEGMENTS = {
    "callback": "Callbacks", "maintenance": "Maintenance", "install": "Installs", "commercial": "Commercial",
    "ductwork": "Ductwork", "repair": "Repairs", "other": "Other",
}
_PARTS = (r"igniter|capacitor|contactor|motor|thermostat|compressor|board|sensor|valve|fan|belt|filter|"
          r"flame|inducer|transformer|switch|fuse|breaker|drain line|pan|txv|expansion")
segment = sorter([  # first match wins
    ("callback", r"warrant|call ?back|recall|return visit|redo|follow[- ]?up"),
    ("maintenance", r"maint|tune|inspection|clean|check[- ]?up|service agreement|plan visit|\bpm\b|membership"),
    ("commercial", r"commercial|\brtu\b|rooftop"),
    ("install", r"install|change ?out|new system|system replacement|retrofit|heat pump"),
    ("ductwork", r"duct"),
    ("repair", r"repair|service call|diagnos|no heat|no cool|not (?:cooling|heating)|leak|fix|" + _PARTS),
    ("install", r"replace|upgrade|new (?:furnace|ac|unit)"),
])


# --- Shared helpers -------------------------------------------------------------------

_months, _label, _period, _pct, _section, _needs, _plain = months, label, period, pct, section, needs, plain


def _jobs(books: Books, window: list[str]) -> pd.DataFrame:
    return jobs_in(books, window, segment)


# --- Sections -----------------------------------------------------------------------------

def installs_vs_repairs(books: Books, through: str) -> dict:
    """Revenue, profit and margin by kind of work: installs, repairs, maintenance, commercial, callbacks."""
    return work_mix(books, through, segment, SEGMENTS, "installs_vs_repairs", "Installs vs. repairs",
                    "Which kind of work is carrying the business?", compare=(("install", "Install"), ("repair", "Repair")))


def equipment_costs(books: Books, through: str) -> dict:
    """Equipment and parts as a share of install prices by month, and installs that cost well over typical."""
    key, title, question = "equipment_costs", "Equipment costs", "Are equipment prices eating into install profit?"
    months = _months(books, through)
    jobs = _jobs(books, months)
    installs = jobs[jobs["segment"].isin(["install", "commercial"]) & (jobs["quoted_revenue"] > 0)] \
        if not jobs.empty else jobs
    if installs.empty or installs["direct_expenses"].sum() == 0:
        return _needs(key, title, question, months, "No installs with equipment costs tied to them. This needs "
                                                    "jobs plus purchases linked to those jobs.")
    installs = installs.assign(cost_share=installs["direct_expenses"] / installs["quoted_revenue"] * 100)
    typical = median(installs["cost_share"])
    rows = []
    for month in months:
        part = installs[installs["month"] == month]
        if not part.empty:
            rows.append({"month": _label(month), "installs": len(part),
                         "equipment_share": round(part["cost_share"].mean(), 1),
                         "equipment": round(part["direct_expenses"].sum(), 2)})
    recent = installs[installs["month"].isin(months[-3:])]
    earlier = installs[~installs["month"].isin(months[-3:])]
    over = installs[installs["cost_share"] >= typical + 8].sort_values("cost_share", ascending=False)
    lost = ((over["cost_share"] - typical) / 100 * over["quoted_revenue"]).sum()
    recent_share = round(recent["cost_share"].mean(), 1) if not recent.empty else None
    earlier_share = round(earlier["cost_share"].mean(), 1) if not earlier.empty else None
    headline = [{"label": "Equipment share, last 3 months", "value": recent_share, "format": "percent",
                 "tone": "bad" if recent_share and earlier_share and recent_share > earlier_share + 2 else None},
                {"label": "Before that", "value": earlier_share, "format": "percent", "tone": None},
                {"label": "Installs well over typical cost", "value": len(over), "format": "count",
                 "tone": "bad" if len(over) else "good"}]
    takeaway = (f"Equipment and parts usually take {typical:.1f}% of an install's price.")
    if recent_share and earlier_share:
        change = recent_share - earlier_share
        takeaway += (f" Over the last three months that was {recent_share}%, "
                     f"{'up' if change > 0 else 'down'} {abs(change):.1f} points from before.")
    if len(over):
        takeaway += (f" {len(over)} installs cost 8+ points more than typical, about ${lost:,.0f} of margin, "
                     f"often a sign the bid used old equipment prices.")
    note = "Costs are the purchases tied to each job: equipment, parts and permits."
    return _section(key, title, question, months, headline, {"columns": [
        {"key": "month", "label": "Month", "format": "text"}, {"key": "installs", "label": "Installs", "format": "count"},
        {"key": "equipment_share", "label": "Equipment share", "format": "percent"},
        {"key": "equipment", "label": "Equipment spend", "format": "money"}], "rows": rows}, takeaway, note)


def slow_season(books: Books, through: str) -> dict:
    """Money in and out by month, cash available, and whether it covers the coming slow months."""
    key, title, question = "slow_season", "Slow-season outlook", "Do I have enough cash to get through the slow months?"
    months = _months(books, through)
    summaries = [monthly_summary(books, m) for m in months]
    rows = [{"month": _label(m), "revenue": s["revenue"], "expenses": s["expenses"], "profit": s["profit"]}
            for m, s in zip(months, summaries)]
    cash = cash_balance(books)
    available = cash["available_cash"]
    recent = [s["expenses"] for s in summaries[-3:]]
    burn = sum(recent) / len(recent) if recent else 0
    runway = round(available / burn, 1) if burn else None
    headline = [{"label": "Cash available", "value": available, "format": "money", "tone": None},
                {"label": "Months of expenses covered", "value": runway, "format": "months",
                 "tone": "bad" if runway is not None and runway < 2 else None}]
    if len(months) < 12:
        return _section(key, title, question, months, headline, {"columns": _season_columns(), "rows": rows},
                        f"Cash covers about {runway} months of recent expenses." if runway else "",
                        "A full year of books shows which months are slow and what they cost. "
                        f"These books cover {len(months)} months.", "ok")

    # Last year's money-losing months tell us what the same months will cost this year.
    losing = {m[5:]: -s["profit"] for m, s in zip(months, summaries) if s["profit"] < 0}
    as_of = date.fromisoformat(books.business["as_of_date"])
    upcoming = []
    for ahead in range(1, 7):
        month = (pd.Period(as_of.strftime("%Y-%m"), "M") + ahead)
        if str(month)[5:] in losing:
            upcoming.append((str(month), losing[str(month)[5:]]))
        elif upcoming:
            break  # only the next unbroken slow stretch
    needed = round(sum(cost for _, cost in upcoming), 2)
    headline.insert(1, {"label": "Last year's loss in the coming slow months", "value": needed, "format": "money",
                        "tone": "bad" if needed > available else None})
    slowest = sorted(zip(months, summaries), key=lambda x: x[1]["revenue"])[:3]
    if upcoming:
        stretch = ", ".join(_label(m)[:3] for m, _ in upcoming)
        takeaway = (f"Last year, {stretch} lost ${needed:,.0f} combined. You have ${available:,.0f} available, "
                    + ("enough to cover that." if available >= needed else
                       f"${needed - available:,.0f} short of covering it."))
    else:
        takeaway = "None of the next six months lost money last year."
    takeaway += f" Your slowest months by revenue were {', '.join(_label(m)[:3] for m, _ in slowest)}."
    return _section(key, title, question, months, headline, {"columns": _season_columns(), "rows": rows}, takeaway,
                    "Based on last year's same months. A different year can be busier or slower.")


def _season_columns():
    return [{"key": "month", "label": "Month", "format": "text"}, {"key": "revenue", "label": "Money in", "format": "money"},
            {"key": "expenses", "label": "Money out", "format": "money"}, {"key": "profit", "label": "Profit", "format": "money"}]


def maintenance_plans(books: Books, through: str) -> dict:
    """Maintenance-plan customers, visits, revenue, how much lands in slow months, and lapsing customers."""
    key, title, question = "maintenance_plans", "Maintenance plans", "How much steady income do maintenance plans bring?"
    months = _months(books, through)
    jobs = _jobs(books, months)
    visits = jobs[jobs["segment"] == "maintenance"] if not jobs.empty else jobs
    if visits.empty:
        return _needs(key, title, question, months, "No maintenance or tune-up visits found. If you sell plans, "
                                                    "upload your jobs export so visits show up.")
    total = jobs["quoted_revenue"].sum()
    revenue = visits["quoted_revenue"].sum()
    customers = visits["customer"].nunique()
    as_of = pd.Timestamp(books.business["as_of_date"])
    last_visit = visits.groupby("customer")["end_date"].max()
    lapsing = last_visit[last_visit < as_of - pd.Timedelta(days=300)]
    by_month = {m: 0.0 for m in months}
    for m, value in visits.groupby("month")["quoted_revenue"].sum().items():
        by_month[m] = value
    revenue_by_month = {m: monthly_summary(books, m)["revenue"] for m in months}
    slow = sorted(months, key=lambda m: revenue_by_month[m])[:4]
    in_slow = sum(by_month[m] for m in slow)
    rows = [{"month": _label(m), "visits": int((visits["month"] == m).sum()), "revenue": round(by_month[m], 2)}
            for m in months]
    seasons_known = len(months) >= 8  # "slowest months" means little with only a few months of books
    headline = [{"label": "Plan customers", "value": customers, "format": "count", "tone": None},
                {"label": "Share of revenue", "value": _pct(revenue, total), "format": "percent", "tone": None}]
    if seasons_known:
        headline.append({"label": "Earned in your slowest months", "value": _pct(in_slow, revenue),
                         "format": "percent", "tone": "good"})
    headline.append({"label": "No visit in 10+ months", "value": len(lapsing), "format": "count",
                     "tone": "bad" if len(lapsing) else None})
    takeaway = (f"{customers} customers had {len(visits)} maintenance visits worth ${revenue:,.0f}, "
                f"{_pct(revenue, total)}% of job revenue.")
    if seasons_known:
        takeaway += (f" {_pct(in_slow, revenue)}% of it came in your four slowest months, which is when you "
                     f"need it most.")
    if len(lapsing):
        takeaway += f" {len(lapsing)} customers haven't had a visit in over 10 months: worth a call to renew."
    note = "Maintenance visits are jobs whose type mentions maintenance, tune-ups, inspections or plans."
    if estimated(jobs):
        note = ("These visits are payments of $200 or less, assumed to be tune-ups. A jobs export shows real "
                "plan visits.")
    return _section(key, title, question, months, headline, {"columns": [
        {"key": "month", "label": "Month", "format": "text"}, {"key": "visits", "label": "Visits", "format": "count"},
        {"key": "revenue", "label": "Revenue", "format": "money"}], "rows": rows}, takeaway, note)


def callbacks(books: Books, through: str) -> dict:
    """Return and warranty visits, what they cost, and how soon after installs they happened."""
    key, title, question = "callbacks", "Callbacks", "How much are return visits costing me?"
    months = _months(books, through)
    jobs = _jobs(books, months)
    if jobs.empty:
        return _needs(key, title, question, months, "No completed jobs in these months.")
    if estimated(jobs):
        return _needs(key, title, question, months, "Callbacks are usually free, so they don't show up in bank "
                                                    "payments. Upload a jobs export from your field-service app "
                                                    "to track them.")
    backs = jobs[jobs["segment"] == "callback"].sort_values("end_date")
    installs = jobs[jobs["segment"].isin(["install", "commercial"])]
    if backs.empty:
        return _section(key, title, question, months,
                        [{"label": "Callbacks", "value": 0, "format": "count", "tone": "good"}],
                        {"columns": [], "rows": []}, "No callbacks or warranty visits found in these months.",
                        "Callbacks are jobs marked warranty, callback or follow-up, or done at no charge.")
    rows = []
    for _, back in backs.iterrows():
        earlier = installs[(installs["customer"] == back["customer"]) & (installs["end_date"] <= back["end_date"])
                           & (installs["end_date"] >= back["end_date"] - pd.Timedelta(days=60))]
        install = earlier.sort_values("end_date").iloc[-1] if not earlier.empty else None
        rows.append({"date": back["end_date"].date().isoformat(), "customer": back["customer"],
                     "after": install["job_type"] if install is not None else "",
                     "days_after": int((back["end_date"] - install["end_date"]).days) if install is not None else None,
                     "cost": round(back["total_cost"], 2)})
    cost = backs["total_cost"].sum()
    rate = _pct(len(backs), len(installs))
    headline = [{"label": "Callbacks", "value": len(backs), "format": "count", "tone": None},
                {"label": "Cost in labor and parts", "value": round(cost, 2), "format": "money", "tone": "bad"},
                {"label": "Per 100 installs", "value": rate, "format": "count", "tone": None}]
    tied = [r for r in rows if r["days_after"] is not None]
    takeaway = (f"{len(backs)} return visits cost ${cost:,.0f} in unpaid labor and parts."
                + (f" {len(tied)} came within 60 days of an install, on average {round(sum(r['days_after'] for r in tied) / len(tied))} days after."
                   if tied else ""))
    return _section(key, title, question, months, headline, {"columns": [
        {"key": "date", "label": "Date", "format": "date"}, {"key": "customer", "label": "Customer", "format": "text"},
        {"key": "after", "label": "After", "format": "text"}, {"key": "days_after", "label": "Days after", "format": "count"},
        {"key": "cost", "label": "Cost", "format": "money"}], "rows": rows[-15:]}, takeaway,
        "Callbacks are jobs marked warranty, callback or follow-up, or done at no charge.")


_BUSINESS = re.compile(r"\b(llc|inc|corp|co\b|group|dental|clinic|retail|center|properties|property|mgmt|"
                       r"management|partners|school|church|office|restaurant|deli|hotel|apartments|lofts|suite)\b", re.I)


def estimate_job_type(amount: float, customer: str) -> str:
    """A job type from a customer payment's size, when there's no jobs export."""
    if amount >= 10000 and _BUSINESS.search(customer):
        return "Commercial install"
    if amount >= 5000:
        return "System install"
    if amount <= 200:
        return "Tune-up"
    return "Repair"


SECTIONS = [installs_vs_repairs, slow_season, maintenance_plans, equipment_costs, callbacks]


def sections(books: Books, through: str) -> list[dict]:
    return [_plain(build(books, through)) for build in SECTIONS]


# --- What the agents know about HVAC ---------------------------------------------------------

ADVICE = """\
This business is an HVAC contractor. Things that matter in HVAC:
- It's seasonal: cooling peaks in summer, heating in winter, and spring and fall are
  slow. A slow month isn't automatically a problem; compare it with the same month
  last year when the books go back that far.
- Installs bring big revenue but carry equipment costs; repairs and maintenance
  usually keep more of each dollar. Equipment prices can rise after a bid, so fixed
  bids need a price-increase clause or a short expiry.
- Maintenance plans smooth out slow seasons: tune-ups fill spring and fall, and plan
  customers call you first for repairs and replacements.
- Callbacks after installs are unpaid labor and a quality signal worth tracking.
- Cash should be set aside in peak months to cover the slow ones."""

QUESTIONS = ["Will I make it through the slow season?", "Are installs or repairs more profitable?",
             "Are equipment costs hurting my install margins?", "How are my maintenance plans doing?",
             "What are callbacks costing me?"]

CATEGORY_HINTS = ("HVAC purchases: condensers, furnaces, heat pumps, coils, refrigerant, filters, thermostats, "
                  "sheet metal and duct from supply houses (Johnstone, Ferguson, Carrier, Lennox, Trane "
                  "distributors) are materials.")
