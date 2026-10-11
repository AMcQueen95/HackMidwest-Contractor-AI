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
    assert picked["trade"]["key"] == "hvac" and len(picked["trade_sections"]) == 5
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
