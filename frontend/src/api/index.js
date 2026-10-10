// The only place the UI talks to the backend (FastAPI on :8000; Vite proxies /api in dev).

async function getJson(url) {
  const response = await fetch(url)
  if (!response.ok) throw new Error(`${url} failed: ${response.status}`)
  return response.json()
}

// Reads a server-sent event stream and calls onEvent with each parsed `data:` line.
async function readEvents(response, onEvent, signal) {
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail ?? `Request failed: ${response.status}`)
  }
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    if (signal?.aborted) return reader.cancel()
    const { done, value } = await reader.read()
    if (done) return
    buffer += decoder.decode(value, { stream: true })
    const blocks = buffer.split('\n\n')
    buffer = blocks.pop()
    for (const block of blocks) {
      const line = block.split('\n').find((l) => l.startsWith('data: '))
      if (line) onEvent(JSON.parse(line.slice(6)))
    }
  }
}

// GET /api/report?month=YYYY-MM
export function getReport(month) {
  return getJson(month ? `/api/report?month=${month}` : '/api/report')
}

// GET /api/report/narrative?month=  (SSE). Calls onText with each chunk, and
// onReset when the text so far should be discarded.
export async function streamNarrative(month, onText, signal, onReset) {
  const response = await fetch(`/api/report/narrative?month=${month}`, { signal })
  await readEvents(
    response,
    (event) => {
      if (event.error) throw new Error(event.error)
      if (event.reset) onReset?.()
      if (event.text) onText(event.text)
    },
    signal,
  )
}

// GET /api/affordability?amount=
export function checkAffordability(amount) {
  return getJson(`/api/affordability?amount=${amount}`)
}

// POST /api/ask (SSE). Events: session, status, text, text_reset, card, error, done.
export async function ask(question, { sessionId, month } = {}, onEvent, signal) {
  const response = await fetch('/api/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, session_id: sessionId, month }),
    signal,
  })
  await readEvents(response, onEvent, signal)
}
