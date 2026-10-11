"""Plumbing: the sections a plumbing shop owner needs, calculated from the books.

Sections return the shared shape described in hvac.py. Takeaways are written by
code from the numbers.
"""

from statistics import median

import pandas as pd

from backend.app.data import Books
from backend.app.trades.common import jobs_in, label, months, needs, pct, plain, section, sorter, work_mix

KEY, NAME = "plumbing", "Plumbing"

SEGMENTS = {
    "emergency": "Emergency calls", "drain": "Drain cleaning", "repair": "Repairs", "water_heater": "Water heaters",
    "replacement": "Sewer and repipes", "fixture": "Fixture installs", "callback": "Callbacks", "other": "Other",
}
segment = sorter([  # first match wins
    ("callback", r"warrant|call ?back|return visit|redo|follow[- ]?up"),
    ("emergency", r"emergenc|after[- ]?hours|weekend|burst|flood|no water|overnight|holiday"),
    ("water_heater", r"water heater|tankless|\bwh\b"),
    ("replacement", r"sewer|repipe|re-pipe|main line (?:replace|repair)|lateral|excavat|trenchless|slab leak"),
    ("drain", r"drain|clog|rooter|snake|hydro[- ]?jet|camera|backup|back-up"),
    ("fixture", r"install|new (?:toilet|faucet|fixture|sink)"),
    ("repair", r"repair|leak|fix|replace|service call|toilet|faucet|valve|disposal|sump|shutoff|running"),
])
SERVICE = ("repair", "drain", "emergency")  # everyday service calls


def _sec(window, columns, rows):
    return {"columns": columns, "rows": rows}


def service_vs_replacement(books: Books, through: str) -> dict:
    """Revenue, profit and margin by kind of work: repairs, drains, emergencies, water heaters, sewer and repipes."""
    return work_mix(books, through, segment, SEGMENTS, "service_vs_replacement", "Service vs. replacement",
                    "Which kind of work is carrying the business?",
                    compare=(("replacement", "Replacement"), ("repair", "Repair")))


def emergency_calls(books: Books, through: str) -> dict:
    """Emergency and after-hours calls: how many, when, and whether they're priced above regular calls."""
    key, title, question = "emergency_calls", "Emergency calls", "Am I charging enough for emergency calls?"
    window = months(books, through)
    jobs = jobs_in(books, window, segment)
    service = jobs[jobs["segment"].isin(SERVICE)] if not jobs.empty else jobs
    urgent = service[service["segment"] == "emergency"] if not service.empty else service
    if urgent.empty:
        return needs(key, title, question, window, "No emergency or after-hours jobs found. Jobs need a type like "
                                                   "'Emergency' or 'After-hours' to show up here.")
    regular = service[service["segment"] != "emergency"]
    urgent_avg = urgent["quoted_revenue"].mean()
    regular_avg = regular["quoted_revenue"].mean() if not regular.empty else None
    premium = round((urgent_avg / regular_avg - 1) * 100, 1) if regular_avg else None
    rows = [{"month": label(m), "emergencies": int((urgent["month"] == m).sum()),
             "average_ticket": round(urgent.loc[urgent["month"] == m, "quoted_revenue"].mean(), 2)
             if (urgent["month"] == m).any() else None} for m in window]
    busiest = max(rows, key=lambda r: r["emergencies"])
    headline = [{"label": "Emergency calls", "value": len(urgent), "format": "count", "tone": None},
                {"label": "Share of service calls", "value": pct(len(urgent), len(service)), "format": "percent", "tone": None},
                {"label": "Emergency avg. ticket", "value": round(urgent_avg, 2), "format": "money", "tone": None},
                {"label": "Above regular calls", "value": premium, "format": "percent",
                 "tone": "bad" if premium is not None and premium < 25 else None}]
    takeaway = (f"{len(urgent)} emergency calls averaged ${urgent_avg:,.0f}, against ${regular_avg:,.0f} for regular "
                f"service calls: {premium}% more.") if regular_avg else f"{len(urgent)} emergency calls averaged ${urgent_avg:,.0f}."
    if premium is not None and premium < 25:
        takeaway += " That's a thin premium for nights, weekends and overtime. Check your after-hours fee covers them."
    takeaway += f" The busiest month was {busiest['month']} with {busiest['emergencies']} calls."
    return section(key, title, question, window, headline, _sec(window, [
        {"key": "month", "label": "Month", "format": "text"}, {"key": "emergencies", "label": "Emergencies", "format": "count"},
        {"key": "average_ticket", "label": "Avg. ticket", "format": "money"}], rows), takeaway,
        "Emergency calls are jobs whose type mentions emergency, after-hours, weekend, burst or flood.")


def average_ticket(books: Books, through: str) -> dict:
    """Average invoice per service call by month, and how many calls are small tickets."""
    key, title, question = "average_ticket", "Average ticket", "Is my average service call growing?"
    window = months(books, through)
    jobs = jobs_in(books, window, segment)
    calls = jobs[jobs["segment"].isin(SERVICE)] if not jobs.empty else jobs
    if calls.empty:
        return needs(key, title, question, window, "No service calls found in these months.")
    rows = [{"month": label(m), "calls": int((calls["month"] == m).sum()),
             "average_ticket": round(calls.loc[calls["month"] == m, "quoted_revenue"].mean(), 2)
             if (calls["month"] == m).any() else None} for m in window]
    recent, earlier = calls[calls["month"].isin(window[-3:])], calls[~calls["month"].isin(window[-3:])]
    recent_avg = round(recent["quoted_revenue"].mean(), 2) if not recent.empty else None
    earlier_avg = round(earlier["quoted_revenue"].mean(), 2) if not earlier.empty else None
    small_line = float(calls["quoted_revenue"].quantile(0.25))
    small = calls[calls["quoted_revenue"] <= small_line]
    headline = [{"label": "Avg. ticket, last 3 months", "value": recent_avg, "format": "money", "tone": None},
                {"label": "Before that", "value": earlier_avg, "format": "money", "tone": None},
                {"label": "Service calls", "value": len(calls), "format": "count", "tone": None}]
    takeaway = f"Service calls averaged ${calls['quoted_revenue'].mean():,.0f} across {len(calls)} calls."
    if recent_avg and earlier_avg:
        change = pct(recent_avg - earlier_avg, earlier_avg)
        takeaway += f" The last three months averaged ${recent_avg:,.0f}, {'up' if change >= 0 else 'down'} {abs(change)}%."
    takeaway += (f" A quarter of calls were ${small_line:,.0f} or less, bringing in ${small['profit'].sum():,.0f} of "
                 f"profit. A minimum service charge lifts those.")
    return section(key, title, question, window, headline, _sec(window, [
        {"key": "month", "label": "Month", "format": "text"}, {"key": "calls", "label": "Calls", "format": "count"},
        {"key": "average_ticket", "label": "Avg. ticket", "format": "money"}], rows), takeaway,
        "Service calls are repairs, drain cleaning and emergency calls.")


def drain_conversions(books: Books, through: str) -> dict:
    """Drain and camera jobs that turned into sewer, repipe or other replacement work, and that revenue."""
    key, title, question = "drain_conversions", "Drains that became replacements", \
        "How often do drain jobs turn into bigger work?"
    window = months(books, through)
    jobs = jobs_in(books, window, segment)
    drains = jobs[jobs["segment"] == "drain"] if not jobs.empty else jobs
    if drains.empty:
        return needs(key, title, question, window, "No drain cleaning or camera jobs found in these months.")
    bigger = jobs[jobs["segment"] == "replacement"]
    rows, used = [], set()
    for _, drain in drains.sort_values("end_date").iterrows():
        follow = bigger[(bigger["customer"] == drain["customer"]) & (bigger["start_date"] >= drain["end_date"])
                        & (bigger["start_date"] <= drain["end_date"] + pd.Timedelta(days=60))
                        & (~bigger["job_id"].isin(used))]
        if not follow.empty:
            job = follow.iloc[0]
            used.add(job["job_id"])
            rows.append({"date": job["start_date"].date().isoformat(), "customer": drain["customer"],
                         "drain_job": drain["job_type"], "became": job["job_type"],
                         "days_later": int((job["start_date"] - drain["end_date"]).days),
                         "revenue": round(job["quoted_revenue"], 2)})
    camera = drains[drains["job_type"].str.contains("camera", case=False, na=False)]
    revenue = sum(r["revenue"] for r in rows)
    headline = [{"label": "Drain jobs", "value": len(drains), "format": "count", "tone": None},
                {"label": "Became replacements", "value": len(rows), "format": "count", "tone": "good" if rows else None},
                {"label": "Conversion rate", "value": pct(len(rows), len(drains)), "format": "percent", "tone": None},
                {"label": "Revenue from those", "value": round(revenue, 2), "format": "money", "tone": "good" if rows else None}]
    takeaway = (f"{len(rows)} of {len(drains)} drain jobs led to replacement work within 60 days, worth "
                f"${revenue:,.0f}.")
    if not camera.empty:
        from_camera = sum(1 for r in rows if "camera" in r["drain_job"].lower())
        takeaway += (f" {pct(from_camera, len(camera))}% of camera inspections led to a replacement, against "
                     f"{pct(len(rows) - from_camera, len(drains) - len(camera))}% of drains without one.")
    return section(key, title, question, window, headline, _sec(window, [
        {"key": "date", "label": "Date", "format": "date"}, {"key": "customer", "label": "Customer", "format": "text"},
        {"key": "became", "label": "Became", "format": "text"}, {"key": "days_later", "label": "Days later", "format": "count"},
        {"key": "revenue", "label": "Revenue", "format": "money"}], rows[-15:]), takeaway,
        "A conversion is a sewer, repipe or other replacement job for the same customer within 60 days of a drain job.")


def water_heaters(books: Books, through: str) -> dict:
    """Water heater jobs: count, revenue, margin, and the heater's share of the price by month."""
    key, title, question = "water_heaters", "Water heaters", "Are water heater jobs still paying well?"
    window = months(books, through)
    jobs = jobs_in(books, window, segment)
    heaters = jobs[(jobs["segment"] == "water_heater") & (jobs["quoted_revenue"] > 0)] if not jobs.empty else jobs
    if heaters.empty:
        return needs(key, title, question, window, "No water heater jobs found in these months.")
    heaters = heaters.assign(part_share=heaters["direct_expenses"] / heaters["quoted_revenue"] * 100)
    rows = [{"month": label(m), "jobs": int((heaters["month"] == m).sum()),
             "part_share": round(heaters.loc[heaters["month"] == m, "part_share"].mean(), 1)
             if (heaters["month"] == m).any() else None,
             "margin": pct(heaters.loc[heaters["month"] == m, "profit"].sum(),
                           heaters.loc[heaters["month"] == m, "quoted_revenue"].sum())} for m in window]
    recent = heaters[heaters["month"].isin(window[-3:])]
    earlier = heaters[~heaters["month"].isin(window[-3:])]
    r_share = round(recent["part_share"].mean(), 1) if not recent.empty else None
    e_share = round(earlier["part_share"].mean(), 1) if not earlier.empty else None
    tankless = heaters["job_type"].str.contains("tankless", case=False, na=False).sum()
    headline = [{"label": "Water heater jobs", "value": len(heaters), "format": "count", "tone": None},
                {"label": "Margin", "value": pct(heaters["profit"].sum(), heaters["quoted_revenue"].sum()),
                 "format": "percent", "tone": None},
                {"label": "Heater share of price, last 3 months", "value": r_share, "format": "percent",
                 "tone": "bad" if r_share and e_share and r_share > e_share + 2 else None},
                {"label": "Before that", "value": e_share, "format": "percent", "tone": None}]
    takeaway = (f"{len(heaters)} water heater jobs brought in ${heaters['quoted_revenue'].sum():,.0f} at a "
                f"{headline[1]['value']}% margin, {tankless} of them tankless.")
    if r_share and e_share:
        takeaway += (f" The heater itself took {r_share}% of the price over the last three months, against {e_share}% "
                     f"before{': time to update your water heater prices' if r_share > e_share + 2 else ''}.")
    return section(key, title, question, window, headline, _sec(window, [
        {"key": "month", "label": "Month", "format": "text"}, {"key": "jobs", "label": "Jobs", "format": "count"},
        {"key": "part_share", "label": "Heater share", "format": "percent"},
        {"key": "margin", "label": "Margin", "format": "percent"}], rows), takeaway,
        "Heater share is the parts and permits tied to each job as a share of its price.")


SECTIONS = [service_vs_replacement, emergency_calls, average_ticket, drain_conversions, water_heaters]


def sections(books: Books, through: str) -> list[dict]:
    return [plain(build(books, through)) for build in SECTIONS]


_plain = plain

ADVICE = """\
This business is a plumbing contractor. Things that matter in plumbing:
- Service calls (repairs, drains) are the steady base; an average ticket that
  creeps up matters more than a few big jobs. A minimum service charge and
  flat-rate pricing protect small calls.
- Emergency and after-hours calls should carry a clear premium; they cost overtime
  and disrupt the schedule. Freezes bring emergency spikes in winter.
- Camera inspections on drain calls find broken lines and lead to sewer and repipe
  work, the biggest tickets in the business.
- Water heater prices move with manufacturer increases; flat prices need updating
  when tank costs rise."""

QUESTIONS = ["Am I charging enough for emergency calls?", "Is my average ticket growing?",
             "How often do drain jobs turn into bigger work?", "Are water heater jobs still paying well?",
             "Is service or replacement work more profitable?"]

CATEGORY_HINTS = ("Plumbing purchases: pipe, fittings, valves, fixtures, water heaters, drain and camera equipment "
                  "from supply houses (Ferguson, Winnelson, Hajoca, RIDGID) are materials; excavation crews are "
                  "subcontractors.")
