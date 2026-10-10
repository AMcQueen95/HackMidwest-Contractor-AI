# Agents

Four [Strands](https://strandsagents.com/) agents. The **CFO Advisor** answers the owner and calls three specialist agents as tools. Each specialist has its own finance tools.

| File | Agent | Tools |
| --- | --- | --- |
| `cfo_agent.py` | CFO Advisor | `expense_agent`, `job_profitability_agent`, `cash_flow_agent`, `business_profile`, `monthly_summary` |
| `expense_agent.py` | Expense | `monthly_summary`, `expense_changes`, `recurring_charges` |
| `job_profitability_agent.py` | Job Profitability | `job_profitability`, `losing_jobs`, `margin_by_job_type` |
| `cash_flow_agent.py` | Cash Flow | `cash_balance`, `receivables`, `affordability` |

`finance_tools.py` wraps the finance functions as Strands tools. `prompts.py` holds the rule every agent follows: numbers come from tools, never from the model.

## Data

The tools call PBoekhout's functions in `backend/app/finance/` (see [the finance contract](../../../docs/finance-contract.md)) and bind the active `Books`, so the model only passes a month or a dollar amount. The bundled Ridgeline sample loads by default. After a validated upload, call `finance_tools.use_books(books)` to point the agents at the new data.

## For API & UI

`backend/app/main.py` serves these. For the streamed endpoints:

```python
from backend.app.agents import ask_stream, stream_narrative, reset_caches

async for event in ask_stream("Who owes me money?", session_id=None, month="2026-09"):
    ...  # {"type": "session" | "status" | "text" | "text_reset" | "card" | "error" | "done", ...}

async for chunk in stream_narrative("2026-09"):
    ...  # report text; None means discard the text so far
```

- `status` events say which analyst the CFO consulted.
- `card` events carry `{type, data}`, where `type` is a finance function name and `data` is its result. That's the shape `DataCard` renders.
- A new chat with `month` set starts with that month's report in its history, so the owner can ask about it.
- Call `reset_caches()` after new books are loaded.

`ask()` and `financial_health_report()` are the non-streaming versions, used by the CLI. Response shapes are in `schemas.py`.

## Running

From the repository root:

```bash
bash scripts/setup_backend.sh && source .venv/bin/activate
cp backend/.env.example backend/.env     # paste your ANTHROPIC_API_KEY
python -m backend.app.cli --demo         # the five demo questions
python -m backend.app.cli "Can I afford a $15,000 equipment purchase?"
python -m backend.app.cli --report       # monthly report as JSON
python -m pytest backend/tests -q        # offline checks, no model calls
RUN_LIVE_TESTS=1 python -m pytest backend/tests/test_agents_live.py -v   # real model calls, ~90s, a few cents
```

The CFO runs on Claude Sonnet 5.5 and the three specialists on Claude Haiku 5.5, through the Anthropic API. Change models with `CFO_MODEL_ID` and `SPECIALIST_MODEL_ID` in `backend/.env`. To run on Amazon Bedrock instead, set `MODEL_PROVIDER=bedrock` and add AWS credentials.
