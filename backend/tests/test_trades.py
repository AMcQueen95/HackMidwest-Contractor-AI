"""Trade profiles (HVAC): job sorting, sections, the trade API and the trade analyst. No model calls."""

import json

import pytest

from backend.app import trades
from backend.app.agents import finance_tools as ft
from backend.app.agents.cfo_agent import build_cfo_agent
from backend.app.agents.trade_agent import system_prompt
from backend.app.data import load_books
from backend.tests.account_helpers import AuthTestClient as TestClient
from backend.tests.account_helpers import create_app
from backend.app.trades import hvac

SAMPLE = load_books(trades.SAMPLES["hvac"])


@pytest.mark.parametrize("job_type,expected", [
    ("Capacitor and contactor replacement", "repair"), ("Igniter replacement", "repair"),
    ("Furnace replacement", "install"), ("AC system replacement", "install"), ("Heat pump install", "install"),
    ("Ductwork replacement", "ductwork"), ("Commercial RTU replacement", "commercial"),
    ("Warranty callback - install follow-up", "callback"), ("AC tune-up - maintenance plan", "maintenance"),
    ("Service call - diagnostic", "repair"), ("residential_hvac", "other")])
def test_hvac_job_types_are_sorted_by_kind_of_work(job_type, expected):
    assert hvac.segment(job_type) == expected


def test_no_charge_unknown_jobs_count_as_callbacks():
    assert hvac.segment("Site visit", 0) == "callback"


def test_hvac_sample_sections_tell_the_story():
    sections = {s["key"]: s for s in hvac.sections(SAMPLE, "2026-09")}
    json.dumps(sections)  # plain JSON
    assert all(s["status"] == "ok" and s["takeaway"] for s in sections.values())
    head = {k: {h["label"]: h["value"] for h in s["headline"]} for k, s in sections.items()}

    mix = head["installs_vs_repairs"]
    assert mix["Repair margin"] > mix["Install margin"]  # repairs keep more of each dollar
    assert head["maintenance_plans"]["Plan customers"] == 140
    assert head["maintenance_plans"]["Earned in your slowest months"] > 40
    equipment = head["equipment_costs"]
    assert equipment["Equipment share, last 3 months"] > equipment["Before that"]  # August price increase
    assert equipment["Installs well over typical cost"] > 0
    assert head["callbacks"]["Callbacks"] > 0
    assert "Last year" in sections["slow_season"]["takeaway"]


def test_sections_say_what_is_missing_instead_of_guessing():
    sections = {s["key"]: s for s in hvac.sections(load_books(), "2026-09")}  # two-month sample, no tune-ups
    assert sections["maintenance_plans"]["status"] == "needs_data"
    assert "full year" in sections["slow_season"]["note"]


def test_trade_api_sets_trade_loads_sample_and_rejects_unknown():
    client = TestClient(create_app())
    assert client.get("/api/report").json()["trade"] is None
    assert [t["key"] for t in client.get("/api/trades").json()["trades"] if t["ready"]] == [
        "hvac", "plumbing", "electrical"]

    picked = client.post("/api/trade", json={"trade": "hvac"}).json()
    ok = [x["key"] for x in hvac.sections(load_books(), picked["month"]) if x["status"] == "ok"]
    assert picked["trade"]["key"] == "hvac" and [x["key"] for x in picked["trade_sections"]] == ok
    assert "maintenance_plans" not in ok  # two months of books, no tune-ups: hidden, not shown empty
    assert picked["business"]["name"] == "Ridgeline Heating & Air"  # books unchanged

    sample = client.post("/api/trade", json={"trade": "hvac", "load_sample": True}).json()
    assert sample["business"]["name"] == "Summit Air & Heat" and sample["is_sample"] is True
    assert client.get("/api/report").json()["suggested_questions"] == hvac.QUESTIONS

    assert client.post("/api/trade", json={"trade": "roofing"}).status_code == 422
    assert client.post("/api/trade", json={"trade": None}).json()["trade"] is None


def test_cfo_gets_the_trade_analyst_only_when_a_trade_is_set():
    assert "trade_agent" not in build_cfo_agent().tool_names
    with trades.use_trade("hvac"):
        cfo = build_cfo_agent()
        assert "trade_agent" in cfo.tool_names
        assert "seasonal" in cfo.system_prompt


def test_trade_section_tool_reads_the_active_trade(monkeypatch):
    monkeypatch.setattr(ft, "get_books", lambda: SAMPLE)
    assert "error" in ft.trade_section("slow_season")  # no trade set
    with trades.use_trade("hvac"):
        assert ft.trade_section("callbacks", "2026-09")["key"] == "callbacks"
        assert "Unknown section" in ft.trade_section("roofs")["error"]
    prompt = system_prompt(hvac)
    assert all(build.__name__ in prompt for build in hvac.SECTIONS)


# --- Plumbing and electrical -------------------------------------------------------------

from backend.app.trades import electrical, plumbing  # noqa: E402


@pytest.mark.parametrize("trade,job_type,expected", [
    (plumbing, "Emergency - burst pipe", "emergency"), (plumbing, "After-hours drain backup", "emergency"),
    (plumbing, "Drain cleaning with camera inspection", "drain"), (plumbing, "Sewer line replacement", "replacement"),
    (plumbing, "Water heater replacement - 50 gal", "water_heater"), (plumbing, "Faucet replacement", "repair"),
    (electrical, "Panel upgrade - 200 amp", "panel"), (electrical, "EV charger install - Level 2", "ev"),
    (electrical, "New construction rough-in and trim", "construction"), (electrical, "Kitchen remodel wiring", "remodel"),
    (electrical, "Recessed lighting install", "lighting"), (electrical, "GFCI outlet install", "service"),
    (electrical, "Callback - breaker issue after panel upgrade", "callback")])
def test_plumbing_and_electrical_job_types(trade, job_type, expected):
    assert trade.segment(job_type) == expected


def head(sections):
    return {s["key"]: {h["label"]: h["value"] for h in s["headline"]} for s in sections}


def test_plumbing_sample_sections_tell_the_story():
    sections = plumbing.sections(load_books(trades.SAMPLES["plumbing"]), "2026-09")
    json.dumps(sections)
    assert all(s["status"] == "ok" and s["takeaway"] for s in sections)
    h = head(sections)
    assert 0 < h["emergency_calls"]["Above regular calls"] < 25  # a thin after-hours premium
    assert h["drain_conversions"]["Became replacements"] > 0
    heaters = h["water_heaters"]
    assert heaters["Heater share of price, last 3 months"] > heaters["Before that"]  # tank prices up from July


def test_electrical_sample_sections_tell_the_story():
    sections = electrical.sections(load_books(trades.SAMPLES["electrical"]), "2026-09")
    json.dumps(sections)
    assert all(s["status"] == "ok" and s["takeaway"] for s in sections)
    h = head(sections)
    assert h["big_jobs"]["In progress"] > 0
    assert h["unbilled_work"]["Estimated unbilled work"] > 0
    materials = h["material_prices"]
    assert materials["Material share, last 3 months"] > materials["Before that"]  # copper up from June
    assert materials["Open quotes"] > 0
    assert h["permits"]["Permits and inspections"] > 0


@pytest.mark.parametrize("key", ["plumbing", "electrical"])
def test_each_trade_loads_its_sample_and_gets_its_analyst(key):
    client = TestClient(create_app())
    report = client.post("/api/trade", json={"trade": key, "load_sample": True}).json()
    assert report["trade"]["key"] == key and len(report["trade_sections"]) == 5
    assert report["suggested_questions"] == trades.get(key).QUESTIONS
    with trades.use_trade(key):
        cfo = build_cfo_agent()
        assert "trade_agent" in cfo.tool_names
        assert all(b.__doc__ in cfo.system_prompt for b in trades.get(key).SECTIONS)  # routing per trade
        assert all(b.__name__ in system_prompt(trades.get(key)) for b in trades.get(key).SECTIONS)


# --- Jobs estimated from bank payments (bank connection without a jobs export) -----------

from datetime import date as _date  # noqa: E402

from backend.app.integrations.records import BusinessFacts, Records, Transaction, assemble  # noqa: E402


def _bank_only_books(trade):
    txs = [Transaction(date=_date(2026, 9, d), amount=amount, description=desc, vendor=vendor, category=cat)
           for d, amount, desc, vendor, cat in [
               (2, 9500, "ACH CREDIT MILLER RESIDENCE", "Miller Residence", "income"),
               (3, 350, "ZELLE FROM PATEL RESIDENCE", "Patel Residence", "income"),
               (4, 149, "ACH CREDIT OKAFOR HOME", "Okafor Home", "income"),
               (5, 2400, "STRIPE TRANSFER ST-1", "Stripe", "income"),  # bundles customers: not a job
               (6, -4200, "FERGUSON ENT", "Ferguson", "materials")]]
    return assemble(Records(transactions=txs, closing_balance=20000), BusinessFacts(),
                    trades.get(trade).estimate_job_type if trade else None)


def test_named_payments_become_estimated_jobs_and_payouts_dont():
    books, warnings, summary = _bank_only_books("hvac")
    assert summary["estimated_jobs"] == 3
    types = sorted(books.jobs["job_type"])
    assert types == ["Repair (estimated from payment)", "System install (estimated from payment)",
                     "Tune-up (estimated from payment)"]
    assert any("estimated from customer payments" in w and "1 payouts" in w for w in warnings)


def test_estimated_jobs_show_revenue_mix_without_fake_margins():
    books, _, _ = _bank_only_books("hvac")
    sections = {s["key"]: s for s in hvac.sections(books, "2026-09")}
    mix = sections["installs_vs_repairs"]
    assert all(r["margin"] is None for r in mix["table"]["rows"])
    assert "estimated from customer payments" in mix["note"]
    assert sections["callbacks"]["status"] == "needs_data"  # free visits never hit the bank
    assert sections["equipment_costs"]["status"] == "needs_data"


def test_jobs_export_turns_estimation_off():
    books, _, summary = assemble(Records(
        transactions=[Transaction(date=_date(2026, 9, 2), amount=900, description="ACH CREDIT ANN", vendor="Ann",
                                  category="income")],
        jobs=[__import__("backend.app.integrations.records", fromlist=["Job"]).Job(
            "J1", "Ann", "AC repair", _date(2026, 9, 1), _date(2026, 9, 1), 900)]), BusinessFacts(),
        hvac.estimate_job_type)
    assert summary["estimated_jobs"] == 0 and list(books.jobs["job_id"]) == ["J1"]


# --- Hiring ----------------------------------------------------------------------------------

from backend.app.finance import hire_capacity  # noqa: E402


def test_hire_capacity_from_a_full_year_of_books():
    result = hire_capacity(SAMPLE, monthly_cost=5200)
    assert "full year" in result["basis"]
    afford = result["affordable_from_profit"]
    assert afford["monthly_cost"] == result["average_monthly_profit"] > 0
    assert afford["hourly_full_time"] == round(afford["monthly_wages"] / (40 * 52 / 12), 2)
    hire = result["proposed_hire"]
    assert hire["covered_by_current_profit"] is True
    assert hire["extra_revenue_to_keep_profit"] == round(5200 / (result["margin_after_job_costs_percent"] / 100), 0) \
        or abs(hire["extra_revenue_to_keep_profit"] - 5200 / (result["margin_after_job_costs_percent"] / 100)) < 25
    assert hire["extra_jobs_per_month"] > 0 and hire["months_spare_cash_covers"] > 0


def test_hire_agent_tool_converts_pay_to_monthly_cost(monkeypatch):
    monkeypatch.setattr(ft, "get_books", lambda: SAMPLE)
    result = ft.hire_affordability(hourly_rate=25)
    assert result["proposed_hire"]["monthly_cost"] == round(25 * 40 * 52 / 12 * 1.2, 2)


# --- Onboarding: several kinds of work ------------------------------------------------------

def _new_company_client():
    """A signed-in client whose company has no books yet, like right after onboarding step 2."""
    app = create_app()
    client = TestClient(app)
    provider = app.state.accounts
    user = provider.tokens[client.headers["Authorization"].split()[1]]
    client.headers["X-Company-ID"] = provider.company(user, "New Shop")["id"]
    return client


def test_new_company_must_answer_the_trade_question_first():
    client = _new_company_client()
    report = client.get("/api/report").json()
    assert report["has_books"] is False and report["trade_setup"]["done"] is False

    saved = client.post("/api/trade", json={"trades": [], "other": None})
    assert saved.status_code == 422  # pick something or describe it

    saved = client.post("/api/trade", json={"trades": ["hvac", "plumbing"], "other": "Snow removal"}).json()
    assert saved["has_books"] is False
    assert saved["trade_setup"] == {"trades": ["hvac", "plumbing"], "other": "Snow removal", "done": True,
                                    "names": ["HVAC", "Plumbing"]}
    assert client.get("/api/report").json()["trade_setup"]["done"] is True  # saved with the company


def test_other_only_counts_as_answered():
    client = _new_company_client()
    saved = client.post("/api/trade", json={"trades": [], "other": "Landscaping"}).json()
    assert saved["trade_setup"]["done"] is True and saved["trade_sections"] == []


def test_several_trades_show_each_trades_sections_and_questions():
    client = TestClient(create_app())
    report = client.post("/api/trade", json={"trades": ["plumbing", "hvac"]}).json()
    # The two-month sample's jobs are just "plumbing", so no plumbing section can be worked out: none shown.
    assert {s["trade"] for s in report["trade_sections"]} == {"hvac"}
    assert all(s["status"] == "ok" for s in report["trade_sections"])
    assert report["trade"]["name"] == "HVAC and Plumbing"
    assert set(report["suggested_questions"]) & set(hvac.QUESTIONS) and \
        set(report["suggested_questions"]) & set(plumbing.QUESTIONS)


def test_cfo_gets_every_trade_and_the_owners_own_words():
    with trades.use_trade(["hvac", "electrical"], "Generator installs"):
        cfo = build_cfo_agent()
        assert "trade_agent" in cfo.tool_names
        assert hvac.ADVICE in cfo.system_prompt and electrical.ADVICE in cfo.system_prompt
        assert "Generator installs" in cfo.system_prompt


def test_work_mix_skips_other_trades_jobs_when_several_are_chosen():
    books = load_books(trades.SAMPLES["plumbing"])  # plumbing jobs mostly look like "Other" to HVAC
    from backend.app.trades import common
    alone = hvac.installs_vs_repairs(books, "2026-09")
    with common.several_trades(True):
        together = hvac.installs_vs_repairs(books, "2026-09")
    assert any(r["segment"] == "Other" for r in alone["table"]["rows"])
    assert not any(r["segment"] == "Other" for r in together["table"]["rows"])


def test_clearing_books_keeps_the_kinds_of_work():
    client = TestClient(create_app())
    client.post("/api/trade", json={"trades": ["electrical"], "other": "Generators"})
    client.post("/api/reset")
    report = client.get("/api/report").json()
    assert report["has_books"] is False
    assert report["trade_setup"]["trades"] == ["electrical"] and report["trade_setup"]["done"] is True



def test_bank_only_books_hide_sections_that_need_a_jobs_export():
    books, _, _ = _bank_only_books("hvac")
    from backend.app.trades.routes import trade_payload
    from backend.app.trades.store import trades as store
    store.set("bank-only-test", ["hvac"])
    shown = {s["key"] for s in trade_payload(books, "2026-09", "bank-only-test")["trade_sections"]}
    assert "installs_vs_repairs" in shown
    assert not shown & {"equipment_costs", "callbacks"}  # can't come from bank payments
