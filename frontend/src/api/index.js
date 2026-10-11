// All finance data comes from the Python API. Same-origin requests retain the
// browser's HTTP-only account cookies through Vite's proxy or the built FastAPI app.
let workspace = { demo: false, companyId: null }
let refreshRequest = null
export function setWorkspace(next) { workspace = next }

export function refreshAccount() {
  if (!refreshRequest) refreshRequest = request('/api/auth/refresh', { method: 'POST' })
    .finally(() => { refreshRequest = null })
  return refreshRequest
}

async function requestResponse(path, options = {}, retried = false) {
  let response
  try {
    response = await fetch(path, { credentials: 'same-origin', ...options,
      headers: { ...(workspace.companyId ? { 'X-Company-ID': workspace.companyId } : {}), ...options.headers },
    })
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new Error('Could not reach the backend. Check that the API is running and try again.')
  }
  if (!response.ok) {
    if (response.status === 401 && retried) window.dispatchEvent(new Event('toolbelt-signed-out'))
    if (response.status === 401 && !path.startsWith('/api/auth/') && !retried && !workspace.demo) {
      try {
        await refreshAccount()
      } catch (error) {
        if (error.status === 401) window.dispatchEvent(new Event('toolbelt-signed-out'))
        throw error
      }
      return requestResponse(path, options, true)
    }
    const body = await response.json().catch(() => ({}))
    const detail = Array.isArray(body.detail)
      ? body.detail.map((item) => item.msg).join('; ')
      : body.detail
    const error = new Error(detail || `Request failed (${response.status}). Please try again.`)
    error.status = response.status
    throw error
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
  return request(`/api/${workspace.demo ? 'demo/' : ''}report${query}`, { signal })
}

export function checkAffordability(amount, signal) {
  return request(`/api/${workspace.demo ? 'demo/' : ''}affordability?${new URLSearchParams({ amount })}`, { signal })
}

export function importRecords(files, { details = {}, dryRun = false } = {}) {
  const body = new FormData()
  for (const file of files) body.append('files', file, file.name)
  for (const [key, value] of Object.entries(details)) {
    if (value != null && value !== '') body.append(key, String(value))
  }
  if (dryRun) body.append('dry_run', 'true')
  return request('/api/import', { method: 'POST', body })
}

export function resetBooks() {
  return request('/api/reset', { method: 'POST' })
}

export const getImportSources = () => request('/api/import/sources')
export const getPlaidStatus = () => request('/api/plaid/status')
export const createPlaidLinkToken = () => request('/api/plaid/link-token', { method: 'POST' })
export const connectSampleBank = () => request('/api/plaid/sandbox', { method: 'POST' })
export function exchangePlaidToken(publicToken) {
  return request('/api/plaid/exchange', { method: 'POST',
    headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ public_token: publicToken }) })
}

export const getAuthConfig = () => request('/api/auth/config')
export const getAccount = () => request('/api/auth/me')
export const signOut = () => request('/api/auth/logout', { method: 'POST' })
export function accountAction(action, body) {
  return request(`/api/auth/${action}`, { method: 'POST',
    headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
}
export function createCompany(name) {
  return request('/api/companies', { method: 'POST',
    headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name }) })
}

// Kinds of work (onboarding). GET /api/trades lists them; POST /api/trade saves the company's choice.
export async function getTrades() {
  return (await request('/api/trades')).trades
}
export function saveTrades({ trades, other }) {
  return request('/api/trade', { method: 'POST',
    headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ trades, other }) })
}
