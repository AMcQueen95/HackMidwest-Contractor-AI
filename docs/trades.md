# Trade profiles

The app changes with the owner's trade: its own report sections, a trade analyst
agent, trade advice in every agent's prompt, suggested chat questions, and trade
vocabulary when categorizing imports. HVAC, plumbing and electrical are built,
each with a year-long sample business.

## For onboarding (Tyler)

| Endpoint | Does |
| --- | --- |
| `GET /api/trades` | Trades and whether each is ready: `[{key, name, ready, has_sample, questions}]` |
| `POST /api/trade` | `{"trade": "hvac"}` sets this browser's trade and returns the report with its sections. Add `"load_sample": true` to also load that trade's sample business. `{"trade": null}` clears it. |
| `GET /api/trade` | The browser's current trade |

Every report (`/api/report`, uploads, imports) now includes `trade`, `trade_sections` and `suggested_questions`. The report page renders `trade_sections` with `TradeSections.jsx`, and the chat uses `suggested_questions` for its chips. The trade is kept per browser and survives new uploads and imports.

## HVAC sections (`backend/app/trades/hvac.py`)

Each covers up to 12 months ending at the report month.

| Section | Shows |
| --- | --- |
| Installs vs. repairs | Revenue, profit, margin and average ticket by kind of work |
| Slow-season outlook | Money in and out by month, cash available, and whether it covers last year's losses in the coming slow months (needs a year of books for the outlook) |
| Maintenance plans | Plan customers and visits, share of revenue, how much lands in the slowest months, customers with no visit in 10+ months |
| Equipment costs | Equipment and parts as a share of install prices by month, and installs that cost 8+ points over typical |
| Callbacks | Warranty and return visits, their cost, and how soon after an install they came |

Jobs are sorted into installs, repairs, maintenance, commercial, ductwork, callbacks and other by keyword rules on the job type ("Igniter replacement" is a repair, "Furnace replacement" an install). Unmatched types show up under Other with a note. Each section returns the same shape (`headline`, `table`, `takeaway`, `note`, `status`), and takeaways are written by code from the numbers. When the books can't support a section, it says what's missing.

## Plumbing sections (`backend/app/trades/plumbing.py`)

| Section | Shows |
| --- | --- |
| Service vs. replacement | Revenue, profit and margin for repairs, drains, emergencies, water heaters, sewer and repipes |
| Emergency calls | How many, when (winter freeze spikes), and how much more they're priced than regular calls |
| Average ticket | Average service call by month, and how much profit comes from the smallest quarter of calls |
| Drains that became replacements | Drain and camera jobs followed by sewer, repipe or other replacement work within 60 days, and that revenue |
| Water heaters | Count, margin, and the heater's share of the price by month |

## Electrical sections (`backend/app/trades/electrical.py`)

| Section | Shows |
| --- | --- |
| Kinds of work | Revenue, profit and margin for service calls, panels, EV chargers, lighting, remodels, new construction |
| Big jobs: budget vs. actual | Jobs over $5,000, finished and in progress: quote vs. costs so far, billed |
| Unbilled work | An estimate of work done on in-progress jobs that hasn't been invoiced |
| Permits and inspections | Permit spending, share of job revenue, and which kinds of work carry the most |
| Material price watch | Materials as a share of job prices by month, and open quotes that may be priced on older costs |

Shared pieces (month windows, the section shape, job profits by kind of work, the work-mix section) are in `backend/app/trades/common.py`.

## Agents

When a trade is set, the CFO gets the trade's advice and the list of what its trade analyst covers (built from the section docstrings, so routing follows the trade), plus a fourth analyst (`trade_agent`: the HVAC, plumbing or electrical analyst) whose one tool, `trade_section`, reads any of the trade's sections. Its chat answers can include the sections as cards. The import categorizer gets the trade's vocabulary.

## Sample businesses

- `python scripts/generate_hvac_sample.py`: Summit Air & Heat. Seasons, about 900 jobs, 140 maintenance-plan customers, callbacks after installs, a 9% equipment price increase from August.
- `python scripts/generate_trade_samples.py`: Riverside Plumbing Co. (winter emergency spikes priced only about 20% above regular calls, drain jobs that become sewer replacements, water heater prices up from July) and Brightline Electric (big jobs billed in stages with two in progress, permits, copper up 12% from June, open quotes priced before it).

## Adding a trade

Create `backend/app/trades/<trade>.py` with `KEY`, `NAME`, `SECTIONS` (functions taking `books, through_month` and returning the section shape, each with a one-line docstring), `sections()`, `ADVICE`, `QUESTIONS` and `CATEGORY_HINTS`, then add it to `TRADES` in `backend/app/trades/__init__.py`. Optionally add a sample business to `SAMPLES`.
