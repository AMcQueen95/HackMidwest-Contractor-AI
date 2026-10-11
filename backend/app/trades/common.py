"""Shared pieces for trade sections: month windows, the section shape, job profits by kind of work."""

import re
import weakref
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import date

import pandas as pd

from backend.app.data import Books
from backend.app.finance import job_profitability


def months(books: Books, through: str, count: int = 12) -> list[str]:
    first = pd.Period(books.business["opening_balance_date"][:7], "M")
    last = pd.Period(through, "M")
    return [str(p) for p in pd.period_range(max(first, last - (count - 1)), last, freq="M")]


def label(month: str) -> str:
    return date.fromisoformat(f"{month}-01").strftime("%b %Y")


def period(window: list[str]) -> str:
    return label(window[0]) if len(window) == 1 else f"{label(window[0])} to {label(window[-1])}"


def pct(part: float, whole: float) -> float | None:
    return round(part / whole * 100, 1) if whole else None


def section(key, title, question, window, headline, table, takeaway, note=None, status="ok") -> dict:
    return {"key": key, "title": title, "question": question, "status": status, "period": period(window),
            "headline": headline, "table": table, "takeaway": takeaway, "note": note}


def needs(key, title, question, window, note) -> dict:
    return section(key, title, question, window, [], {"columns": [], "rows": []}, "", note, "needs_data")


ESTIMATED_NOTE = ("Most of these jobs are estimated from customer payments, so their types are guesses from the "
                  "payment size and job costs aren't known. Upload a jobs export from your field-service app for "
                  "real job types, costs and margins.")


def estimated(jobs) -> bool:
    """True when most jobs were estimated from bank payments rather than a jobs export."""
    if jobs is None or len(jobs) == 0:
        return False
    return jobs["job_type"].str.contains("(estimated", regex=False).mean() > 0.5


def plain(value):
    """Plain JSON types (pandas sums come back as numpy numbers)."""
    if isinstance(value, dict):
        return {k: plain(v) for k, v in value.items()}
    if isinstance(value, list):
        return [plain(v) for v in value]
    if hasattr(value, "item"):
        return value.item()
    return value


def sorter(rules: list[tuple[str, str]], free_jobs: str = "callback"):
    """A job-type sorter from (segment, regex) rules; first match wins. Unmatched
    no-charge jobs count as `free_jobs`."""
    compiled = [(name, re.compile(pattern)) for name, pattern in rules]

    def segment(job_type: str, price: float | None = None) -> str:
        text = (job_type or "").lower()
        for name, pattern in compiled:
            if pattern.search(text):
                return name
        return free_jobs if price == 0 else "other"
    return segment


_several: ContextVar[bool] = ContextVar("several_trades", default=False)


@contextmanager
def several_trades(on: bool):
    """While building sections for a company with several trades, each trade's work mix
    leaves out jobs that belong to the other trades (they'd all land under Other)."""
    token = _several.set(on)
    try:
        yield
    finally:
        _several.reset(token)


_profits: dict[tuple, tuple[weakref.ref, pd.DataFrame]] = {}


def completed_jobs(books: Books, segment) -> pd.DataFrame:
    """Every completed job with profit, end month and segment, worked out once per books and trade."""
    key = (id(books), segment)
    cached = _profits.get(key)
    if cached and cached[0]() is books:
        return cached[1]
    rows = pd.DataFrame(job_profitability(books)["jobs"])
    if not rows.empty:
        rows = rows.join(books.jobs.set_index("job_id")[["end_date", "start_date"]], on="job_id")
        rows["month"] = rows["end_date"].dt.strftime("%Y-%m")
        rows["segment"] = [segment(t, p) for t, p in zip(rows["job_type"], rows["quoted_revenue"])]
    for stale in [k for k, (ref, _) in _profits.items() if ref() is None]:
        del _profits[stale]
    _profits[key] = (weakref.ref(books), rows)
    return rows


def jobs_in(books: Books, window: list[str], segment) -> pd.DataFrame:
    rows = completed_jobs(books, segment)
    return rows if rows.empty else rows[rows["month"].isin(window)].copy()


def work_mix(books, through, segment, names, key, title, question, compare=None, note_other=True) -> dict:
    """Revenue, profit, margin and average ticket by kind of work. `compare` is two
    (segment, singular label) pairs whose margins to contrast, e.g.
    (("install", "Install"), ("repair", "Repair"))."""
    window = months(books, through)
    jobs = jobs_in(books, window, segment)
    if _several.get() and not jobs.empty:
        jobs = jobs[jobs["segment"] != "other"]
        note_other = False
    if jobs.empty:
        return needs(key, title, question, window, "No completed jobs in these months. Upload a jobs export "
                                                   "from your field-service app to see this.")
    total = jobs["quoted_revenue"].sum()
    rows = []
    for seg, name in names.items():
        part = jobs[jobs["segment"] == seg]
        if part.empty:
            continue
        revenue, profit = part["quoted_revenue"].sum(), part["profit"].sum()
        rows.append({"segment": name, "jobs": len(part), "revenue": round(revenue, 2), "share": pct(revenue, total),
                     "profit": round(profit, 2), "margin": pct(profit, revenue),
                     "average_ticket": round(revenue / len(part), 2)})
    guessed = estimated(jobs)
    if guessed:  # no job costs: margins would read as nearly 100%
        for r in rows:
            r["profit"], r["margin"] = None, None
    by = {r["segment"]: r for r in rows}
    if guessed:
        top = max(rows, key=lambda r: r["revenue"])
        takeaway = (f"{top['segment']} brought in the most revenue: ${top['revenue']:,.0f}, {top['share']}% of the "
                    f"total, averaging ${top['average_ticket']:,.0f} a job.")
    else:
        top = max(rows, key=lambda r: r["profit"])
        takeaway = f"{top['segment']} brought in the most profit: ${top['profit']:,.0f} on {top['share']}% of revenue."
    headline = []
    if compare:
        (seg_a, one_a), (seg_b, one_b) = compare
        a, b = by.get(names[seg_a]), by.get(names[seg_b])
        headline = [{"label": f"Revenue from {names[seg_a].lower()}", "value": a["share"] if a else 0,
                     "format": "percent", "tone": None},
                    {"label": f"{one_a} margin", "value": a["margin"] if a else None, "format": "percent", "tone": None},
                    {"label": f"{one_b} margin", "value": b["margin"] if b else None, "format": "percent", "tone": None}]
        if guessed:
            headline = headline[:1]
        elif a and b and a["margin"] is not None and b["margin"] is not None:
            takeaway += (f" {names[seg_b]} keep {b['margin']}% of each dollar after parts and labor; "
                         f"{names[seg_a].lower()} keep {a['margin']}%.")
    other = by.get(names.get("other", "Other"))
    note = f"{other['jobs']} jobs didn't match a known job type and are under Other." if other and note_other else None
    if guessed:
        note = ESTIMATED_NOTE
    return section(key, title, question, window, headline, {"columns": [
        {"key": "segment", "label": "Work", "format": "text"}, {"key": "jobs", "label": "Jobs", "format": "count"},
        {"key": "revenue", "label": "Revenue", "format": "money"}, {"key": "share", "label": "Share", "format": "percent"},
        {"key": "profit", "label": "Profit", "format": "money"}, {"key": "margin", "label": "Margin", "format": "percent"},
        {"key": "average_ticket", "label": "Avg. ticket", "format": "money"}], "rows": rows}, takeaway, note)
