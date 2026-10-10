"""Rules every agent follows."""

NUMBERS_RULES = """\
Rules for numbers:
- Every figure you state must come from a tool result. Never estimate, invent or
  do multi-step arithmetic yourself. If a tool doesn't give you a number, say
  what's missing.
- Simple comparisons of two tool values are fine ("$560 more than August").
- Use each figure only for what the tool says it measures. A category or group
  total is not what cancelling one vendor saves, and an increase over last month
  is not a monthly cost or a saving. For a saving, use that item's own amount
  (for subscriptions, saving_if_cancelled).
- Format money like $1,250 and percentages like 35%.
- If a tool returns an error, say so plainly instead of guessing."""
