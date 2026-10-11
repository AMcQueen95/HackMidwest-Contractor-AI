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


BRIEF_RULES = """\
Keep it short: at most five bullets, each one line, with only the numbers that
matter. The CFO combines your answer with others, so skip greetings and summaries."""

ESTIMATED_JOBS = """\
If job types end in "(estimated from payment)", those jobs were inferred from bank
payments: their costs aren't tied to them. Say that once in a single line; never
list jobs with $0 costs or margins near 100%."""

STE_RULES = """\
Write in ASD-STE100 Simplified Technical English:
- Keep sentences short: no more than 20 words for an instruction and 25 words for
  a description.
- Use the active voice.
- Write one instruction in each sentence. Start instructions with a verb, for
  example "Send the invoice to Westport."
- Use simple, common words with one meaning. Do not use idioms, slang or jargon.
- Use the present tense or simple past tense. Do not use "would", "could" or "-ing"
  words as nouns.
- Use the same word for the same thing every time.
- Use articles ("the", "a") where English needs them. Write numbers as digits."""