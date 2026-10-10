// All finance data comes from the Python API. Same-origin requests retain the
// browser's dataset cookie through Vite's proxy or the built FastAPI app.
async function request(path, options = {}) {
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
  return response.json()
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
