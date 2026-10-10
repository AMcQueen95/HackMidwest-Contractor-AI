// All finance data comes from the Python API. Same-origin requests retain the
// browser's dataset cookie through Vite's proxy or the built FastAPI app.
async function requestResponse(path, options = {}) {
  let response
  try {
    response = await fetch(path, { credentials: 'same-origin', ...options })
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new Error('Could not reach the backend. Check that the API is running and try again.')
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    const detail = Array.isArray(body.detail)
      ? body.detail.map((item) => item.msg).join('; ')
      : body.detail
    throw new Error(detail || `Request failed (${response.status}). Please try again.`)
  }
  return response
}

async function request(path, options) {
  return (await requestResponse(path, options)).json()
}

async function readEvents(response, onEvent, signal) {
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let completed = false
  const dispatch = (block) => {
    const data = block.split(/\r?\n/).filter((line) => line.startsWith('data:'))
      .map((line) => line.slice(5).trimStart()).join('\n')
    if (!data) return
    const event = JSON.parse(data)
    if (event.done || event.type === 'done') completed = true
    onEvent(event)
  }
  try {
    while (true) {
      if (signal?.aborted) throw new DOMException('Request aborted', 'AbortError')
      const { done, value } = await reader.read()
      buffer += done ? decoder.decode() : decoder.decode(value, { stream: true })
      const blocks = buffer.split(/\r?\n\r?\n/)
      buffer = blocks.pop()
      blocks.forEach(dispatch)
      if (done) {
        if (buffer.trim()) dispatch(buffer)
        if (!completed) throw new Error('The AI response ended early. Please try again.')
        return
      }
    }
  } finally {
    await reader.cancel().catch(() => {})
    reader.releaseLock()
  }
}

export async function streamNarrative(month, onText, signal, onReset) {
  const response = await requestResponse(`/api/report/narrative?${new URLSearchParams({ month })}`, { signal })
  await readEvents(response, (event) => {
    if (event.error) throw new Error(event.error)
    if (event.reset) onReset?.()
    if (event.text) onText(event.text)
  }, signal)
}

export async function ask(question, { sessionId, month } = {}, onEvent, signal) {
  const response = await requestResponse('/api/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, session_id: sessionId, month }),
    signal,
  })
  await readEvents(response, onEvent, signal)
}

export function getReport(month, signal) {
  const query = month == null ? '' : `?${new URLSearchParams({ month })}`
  return request(`/api/report${query}`, { signal })
}

export function checkAffordability(amount, signal) {
  return request(`/api/affordability?${new URLSearchParams({ amount })}`, { signal })
}

export function uploadBooks(files) {
  const body = new FormData()
  for (const file of Object.values(files)) body.append('files', file, file.name)
  return request('/api/upload', { method: 'POST', body })
}

export function resetBooks() {
  return request('/api/reset', { method: 'POST' })
}
