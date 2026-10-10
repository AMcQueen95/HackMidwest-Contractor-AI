// The only place the UI talks to the backend. Everything here returns mock
// data for now; each function names the real endpoint it will call.
import books from './mock/books.json'
import { mockAffordability } from './mock/affordability'
import { NARRATIVES } from './mock/narrative'
import { sampleConversation } from './mock/chat'

const MONTHS = Object.keys(books).sort()

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

// GET /api/report?month=YYYY-MM
export async function getReport(month) {
  const selected = MONTHS.includes(month) ? month : MONTHS[MONTHS.length - 1]
  const previous = MONTHS[MONTHS.indexOf(selected) - 1]
  return {
    ...books[selected],
    month: selected,
    months: MONTHS,
    is_sample: true,
    previous_summary: previous ? books[previous].monthly_summary : null,
    narrative: null,
  }
}

// GET /api/report/narrative?month=  (SSE). Calls onText with each chunk.
export async function streamNarrative(month, onText, signal) {
  const words = NARRATIVES[month].split(/(?<=\s)/)
  await sleep(900)
  for (const word of words) {
    if (signal?.aborted) return
    onText(word)
    await sleep(22)
  }
}

// GET /api/affordability?amount=
export async function checkAffordability(amount) {
  return mockAffordability(books[MONTHS[MONTHS.length - 1]], amount)
}

// Stands in for POST /api/ask until the agents are connected.
export function getSampleConversation() {
  return sampleConversation(books[MONTHS[MONTHS.length - 1]])
}
