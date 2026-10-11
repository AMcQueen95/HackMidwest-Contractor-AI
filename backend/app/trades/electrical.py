"""Electrical: the sections an electrical contractor needs, calculated from the books.

Sections return the shared shape described in hvac.py. Takeaways are written by
code from the numbers. Big jobs include ones still in progress, read straight
from the books (job costs to date and invoices so far).
"""

import re
from statistics import median

import pandas as pd

from backend.app.data import Books
from backend.app.trades.common import (ESTIMATED_NOTE, estimated, jobs_in, label, months, needs, pct, plain, section,
                                       sorter, work_mix)

KEY, NAME = "electrical", "Electrical"
BIG_JOB = 5000  # dollars; big jobs are usually billed in stages

SEGMENTS = {
    "service": "Service calls", "panel": "Panel upgrades", "ev": "EV chargers", "lighting": "Lighting",
    "remodel": "Remodels and rewires", "construction": "New construction", "callback": "Callbacks", "other": "Other",
}
segment = sorter([  # first match wins
    ("callback", r"warrant|call ?back|return visit|redo|follow[- ]?up"),
    ("ev", r"\bev\b|electric vehicle|level 2|tesla|charger|wall connector"),
    ("panel", r"panel|service upgrade|\d+ ?amp|meter base|subpanel|breaker box"),
    ("construction", r"new construction|rough[- ]?in|tenant (?:finish|build)|commercial (?:build|suite)"),
    ("remodel", r"remodel|rewire|kitchen|basement|addition|renovat"),
    ("lighting", r"light(?:ing)? (?:install|retrofit)|recessed|can lights|\bled\b|landscape light"),
    ("service", r"repair|service call|troubleshoot|outlet|switch|gfci|breaker|fix|fan|install|flicker"),
])


def _table(columns, rows):
    return {"columns": columns, "rows": rows}


def _big_jobs(books: Books) -> pd.DataFrame:
    """Every big job (completed or in progress) with costs to date, billed and collected so far."""
    jobs = books.jobs[books.jobs["status"].isin(["completed", "in_progress"])].copy()
    jobs = jobs[jobs["_quoted_price_cents"] >= BIG_JOB * 100]
    if jobs.empty:
        return jobs
    tx = books.transactions[books.transactions["job_id"] != ""]
    costs = (-tx[tx["_amount_cents"] < 0].groupby("job_id")["_amount_cents"].sum()) / 100
    paid = tx[tx["_amount_cents"] > 0].groupby("job_id")["_amount_cents"].sum() / 100
    billed = books.invoices.groupby("job_id")["_amount_cents"].sum() / 100
    jobs["quote"] = jobs["_quoted_price_cents"] / 100
    jobs["materials"] = jobs["job_id"].map(costs).fillna(0.0)
    jobs["labor"] = jobs["_estimated_labor_cents"].astype(float) / 100
    jobs["cost_to_date"] = jobs["materials"] + jobs["labor"]
    jobs["billed"] = jobs["job_id"].map(billed).fillna(0.0)
    jobs["collected"] = jobs["job_id"].map(paid).fillna(0.0)
    jobs["cost_share"] = jobs["cost_to_date"] / jobs["quote"] * 100
    return jobs


def kinds_of_work(books: Books, through: str) -> dict:
    """Revenue, profit and margin by kind of work: service calls, panels, EV chargers, lighting, remodels, construction."""
    return work_mix(books, through, segment, SEGMENTS, "kinds_of_work", "Kinds of work",
                    "Which kind of work is carrying the business?",
                    compare=(("panel", "Panel upgrade"), ("service", "Service call")))


def big_jobs(books: Books, through: str) -> dict:
    """Big jobs, finished and in progress: quote vs. costs so far, billed and collected."""
    key, title, question = "big_jobs", "Big jobs: budget vs. actual", "Are my big jobs staying on budget?"
    window = months(books, through)
    jobs = _big_jobs(books)
    if jobs.empty:
        return needs(key, title, question, window, f"No jobs over ${BIG_JOB:,} found.")
    if estimated(jobs):
        return needs(key, title, question, window, ESTIMATED_NOTE)
    done = jobs[jobs["status"] == "completed"]
    typical = median(done["cost_share"]) if not done.empty else None
    open_jobs = jobs[jobs["status"] == "in_progress"]
    recent = jobs[(jobs["status"] == "in_progress") | (jobs["end_date"].dt.strftime("%Y-%m").isin(window))]
    rows = [{"job": r.job_id, "customer": r.customer, "type": r.job_type,
             "status": "In progress" if r.status == "in_progress" else "Done", "quote": round(r.quote, 2),
             "cost_to_date": round(r.cost_to_date, 2), "cost_share": round(r.cost_share, 1),
             "billed": round(r.billed, 2)} for r in recent.sort_values("start_date", ascending=False).itertuples()]
    over = done[done["cost_share"] >= (typical or 0) + 10] if typical is not None else done.iloc[0:0]
    headline = [{"label": "Big jobs", "value": len(recent), "format": "count", "tone": None},
                {"label": "In progress", "value": len(open_jobs), "format": "count", "tone": None},
                {"label": "Typical cost, % of quote", "value": round(typical, 1) if typical else None,
                 "format": "percent", "tone": None},
                {"label": "Finished well over typical", "value": len(over), "format": "count",
                 "tone": "bad" if len(over) else "good"}]
    takeaway = (f"Finished big jobs usually cost {typical:.0f}% of the quote in materials, permits and labor."
                if typical else "No finished big jobs yet to compare against.")
    if len(over):
        takeaway += f" {len(over)} finished 10+ points over that, worth checking before the next similar bid."
    if not open_jobs.empty:
        takeaway += (f" {len(open_jobs)} jobs worth ${open_jobs['quote'].sum():,.0f} are in progress with "
                     f"${open_jobs['cost_to_date'].sum():,.0f} spent so far.")
    return section(key, title, question, window, headline, _table([
        {"key": "job", "label": "Job", "format": "text"}, {"key": "customer", "label": "Customer", "format": "text"},
        {"key": "status", "label": "Status", "format": "text"}, {"key": "quote", "label": "Quote", "format": "money"},
        {"key": "cost_to_date", "label": "Cost so far", "format": "money"},
        {"key": "cost_share", "label": "% of quote", "format": "percent"},
        {"key": "billed", "label": "Billed", "format": "money"}], rows[:15]), takeaway,
        f"Big jobs are over ${BIG_JOB:,}. Labor is estimated from hours times your labor rate.")


def unbilled_work(books: Books, through: str) -> dict:
    """Work done on in-progress jobs that hasn't been invoiced yet (an estimate from costs so far)."""
    key, title, question = "unbilled_work", "Unbilled work", "How much work haven't I billed yet?"
    window = months(books, through)
    jobs = _big_jobs(books)
    if jobs.empty or not (jobs["status"] == "in_progress").any():
        return needs(key, title, question, window, "No big jobs in progress, so nothing is waiting to be billed.")
    done = jobs[jobs["status"] == "completed"]
    typical = median(done["cost_share"]) / 100 if not done.empty else 0.6
    rows, total = [], 0.0
    for r in jobs[jobs["status"] == "in_progress"].itertuples():
        complete = min(1.0, r.cost_to_date / (r.quote * typical)) if typical else 0.0
        earned = complete * r.quote
        unbilled = max(0.0, earned - r.billed)
        total += unbilled
        rows.append({"job": r.job_id, "customer": r.customer, "quote": round(r.quote, 2),
                     "percent_complete": round(complete * 100, 1), "earned": round(earned, 2),
                     "billed": round(r.billed, 2), "unbilled": round(unbilled, 2)})
    rows.sort(key=lambda r: r["unbilled"], reverse=True)
    headline = [{"label": "Estimated unbilled work", "value": round(total, 2), "format": "money",
                 "tone": "bad" if total > 0 else "good"},
                {"label": "Jobs in progress", "value": len(rows), "format": "count", "tone": None}]
    top = rows[0]
    takeaway = (f"About ${total:,.0f} of work on {len(rows)} jobs in progress looks done but not billed."
                + (f" The biggest is {top['customer']} ({top['job']}): about {top['percent_complete']:.0f}% done, "
                   f"${top['billed']:,.0f} billed of ${top['earned']:,.0f} earned." if top["unbilled"] else ""))
    if total:
        takeaway += " Sending progress invoices now gets that cash in sooner."
    return section(key, title, question, window, headline, _table([
        {"key": "job", "label": "Job", "format": "text"}, {"key": "customer", "label": "Customer", "format": "text"},
        {"key": "quote", "label": "Quote", "format": "money"},
        {"key": "percent_complete", "label": "% done (est.)", "format": "percent"},
        {"key": "earned", "label": "Earned", "format": "money"}, {"key": "billed", "label": "Billed", "format": "money"},
        {"key": "unbilled", "label": "Unbilled", "format": "money"}], rows), takeaway,
        "Percent done is estimated by comparing costs so far with what finished big jobs typically cost. "
        "It's a guide for when to bill, not an exact figure.")


def permits(books: Books, through: str) -> dict:
    """Permit and inspection spending by month and by kind of work, as a share of job prices."""
    key, title, question = "permits", "Permits and inspections", "What are permits costing me?"
    window = months(books, through)
    tx = books.transactions
    permit_tx = tx[(tx["category"].str.lower() == "permits") & (tx["_amount_cents"] < 0)]
    permit_tx = permit_tx[permit_tx["date"].dt.strftime("%Y-%m").isin(window)]
    if permit_tx.empty:
        return needs(key, title, question, window, "No permit or inspection spending found in these months.")
    by_month = (-permit_tx.groupby(permit_tx["date"].dt.strftime("%Y-%m"))["_amount_cents"].sum() / 100).to_dict()
    jobs = jobs_in(books, window, segment)
    per_job = (-permit_tx[permit_tx["job_id"] != ""].groupby("job_id")["_amount_cents"].sum() / 100)
    by_kind = []
    if not jobs.empty:
        jobs = jobs.assign(permit=jobs["job_id"].map(per_job).fillna(0.0))
        for seg, name in SEGMENTS.items():
            part = jobs[(jobs["segment"] == seg) & (jobs["permit"] > 0)]
            if not part.empty:
                by_kind.append({"work": name, "jobs": len(part), "average_permit": round(part["permit"].mean(), 2),
                                "share_of_price": pct(part["permit"].sum(), part["quoted_revenue"].sum())})
    total = -permit_tx["_amount_cents"].sum() / 100
    revenue = jobs["quoted_revenue"].sum() if not jobs.empty else 0
    headline = [{"label": "Permits and inspections", "value": round(total, 2), "format": "money", "tone": None},
                {"label": "Share of job revenue", "value": pct(total, revenue), "format": "percent", "tone": None},
                {"label": "Permitted jobs", "value": int((per_job > 0).sum()), "format": "count", "tone": None}]
    heaviest = max(by_kind, key=lambda r: r["share_of_price"] or 0) if by_kind else None
    takeaway = f"Permits and inspections cost ${total:,.0f}, {pct(total, revenue)}% of job revenue."
    if heaviest:
        takeaway += (f" They weigh most on {heaviest['work']}: ${heaviest['average_permit']:,.0f} a job, "
                     f"{heaviest['share_of_price']}% of the price. Make sure those quotes include the permit.")
    return section(key, title, question, window, headline, _table([
        {"key": "work", "label": "Work", "format": "text"}, {"key": "jobs", "label": "Jobs", "format": "count"},
        {"key": "average_permit", "label": "Avg. permit", "format": "money"},
        {"key": "share_of_price", "label": "Share of price", "format": "percent"}], by_kind), takeaway,
        "Permits are transactions categorized as permits; per-job figures use those tied to a job.")


def material_prices(books: Books, through: str) -> dict:
    """Wire, copper and other materials as a share of job prices by month, and open quotes that may be underpriced."""
    key, title, question = "material_prices", "Material price watch", "Are material prices eating my margins?"
    window = months(books, through)
    jobs = jobs_in(books, window, segment)
    if not jobs.empty:  # paid jobs with materials; free callbacks have no price to compare against
        jobs = jobs[(jobs["direct_expenses"] > 0) & (jobs["quoted_revenue"] > 0)]
    if jobs.empty:
        return needs(key, title, question, window, "No jobs with material costs tied to them.")
    jobs = jobs.assign(share=jobs["direct_expenses"] / jobs["quoted_revenue"] * 100)
    rows = [{"month": label(m), "jobs": int((jobs["month"] == m).sum()),
             "material_share": round(jobs.loc[jobs["month"] == m, "share"].mean(), 1)
             if (jobs["month"] == m).any() else None} for m in window]
    recent, earlier = jobs[jobs["month"].isin(window[-3:])], jobs[~jobs["month"].isin(window[-3:])]
    r_share = round(recent["share"].mean(), 1) if not recent.empty else None
    e_share = round(earlier["share"].mean(), 1) if not earlier.empty else None
    quotes = books.jobs[books.jobs["status"] == "quoted"]
    quoted_value = quotes["_quoted_price_cents"].sum() / 100
    rising = bool(r_share and e_share and r_share > e_share + 1.5)
    headline = [{"label": "Material share, last 3 months", "value": r_share, "format": "percent",
                 "tone": "bad" if rising else None},
                {"label": "Before that", "value": e_share, "format": "percent", "tone": None},
                {"label": "Open quotes", "value": round(quoted_value, 2), "format": "money",
                 "tone": "bad" if rising and quoted_value else None}]
    takeaway = (f"Materials took {r_share}% of job prices over the last three months, against {e_share}% before."
                if r_share and e_share else f"Materials take about {jobs['share'].mean():.1f}% of job prices.")
    if rising and len(quotes):
        takeaway += (f" {len(quotes)} open quotes worth ${quoted_value:,.0f} may have been priced on older material "
                     f"costs. Recheck them before the customer says yes.")
    return section(key, title, question, window, headline, _table([
        {"key": "month", "label": "Month", "format": "text"}, {"key": "jobs", "label": "Jobs", "format": "count"},
        {"key": "material_share", "label": "Material share", "format": "percent"}], rows), takeaway,
        "Material share is the purchases tied to each finished job as a share of its price.")


_BUSINESS = re.compile(r"\b(llc|inc|corp|co\b|group|dental|clinic|retail|center|properties|property|mgmt|"
                       r"management|partners|school|church|office|restaurant|deli|hotel|apartments|lofts|suite)\b", re.I)


def estimate_job_type(amount: float, customer: str) -> str:
    """A job type from a customer payment's size, when there's no jobs export."""
    if amount >= 15000 and _BUSINESS.search(customer):
        return "New construction"
    if amount >= 6000:
        return "Remodel or rewire"
    if amount >= 2400:
        return "Panel upgrade"
    return "Service call"


SECTIONS = [kinds_of_work, big_jobs, unbilled_work, permits, material_prices]


def sections(books: Books, through: str) -> list[dict]:
    return [plain(build(books, through)) for build in SECTIONS]


_plain = plain

ADVICE = """\
This business is an electrical contractor. Things that matter in electrical work:
- Big jobs (remodels, rewires, new construction) are billed in stages: deposit,
  progress and final. Work done but not yet billed is cash the business has earned
  but can't use; progress invoices should go out on time.
- Wire and copper prices swing; quotes should expire quickly or carry a material
  price clause, and open quotes need rechecking when prices rise.
- Permits and inspections are a real cost on panels, EV chargers and remodels and
  belong in the quote.
- Panel upgrades and EV chargers are strong, repeatable work; licensed labor is
  expensive, so hours over estimate hurt."""

QUESTIONS = ["How much work haven't I billed yet?", "Are my big jobs staying on budget?",
             "Are material prices eating my margins?", "What are permits costing me?",
             "Which kind of work is most profitable?"]

CATEGORY_HINTS = ("Electrical purchases: wire, conduit, panels, breakers, fixtures and devices from electrical "
                  "supply houses (Crescent, Graybar, CED, Border States) are materials; lift and equipment "
                  "rentals (Sunbelt, United Rentals) are equipment.")
