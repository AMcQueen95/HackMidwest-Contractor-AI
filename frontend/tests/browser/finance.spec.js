import { test, expect } from '@playwright/test'
import fs from 'node:fs'
import { fileURLToPath } from 'node:url'

const sample = fileURLToPath(new URL('../../../backend/app/data/sample/', import.meta.url))

async function selectBooks(page, { invalid = false } = {}) {
  await page.getByRole('button', { name: 'Use your own books' }).click()
  for (const name of ['transactions.csv', 'jobs.csv', 'invoices.csv', 'business.json']) {
    let content = fs.readFileSync(`${sample}/${name}`, 'utf8')
    if (name === 'transactions.csv') content = content.replace('insurance,-1260,', 'insurance,-1500,')
    if (invalid && name === 'invoices.csv') content = 'invoice_id\n'
    await page.getByLabel(name, { exact: true }).setInputFiles({ name, mimeType: name.endsWith('.json') ? 'application/json' : 'text/csv', buffer: Buffer.from(content) })
  }
  await page.getByRole('button', { name: 'Upload books', exact: true }).click()
}

test('dashboard, month selection, and purchase checks use the live API', async ({ page }) => {
  const errors = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.goto('/')
  await expect(page.locator('.tile-value').nth(1)).toHaveText('$52,900')
  await expect(page.locator('.tile-value').nth(2)).toContainText('7,830')
  await expect(page.locator('.affordability .verdict')).toContainText('$16,447')
  await page.locator('[aria-label="Month"] button').first().click()
  await expect(page.locator('.tile-value').nth(2)).toHaveText('$15,000')
  await expect(page.locator('.tile').nth(3).locator('.tile-note')).toContainText('Sep 30')
  await page.locator('[aria-label="Month"] button').last().click()
  await expect(page.locator('.tile-value').nth(1)).toHaveText('$52,900')
  await page.getByLabel(/How much is the purchase/).fill('1000000')
  await expect(page.locator('.affordability .verdict')).toContainText('$1,001,447')
  await expect(page.getByText('AI analysis is not configured. Your financial calculations are still available.')).toBeVisible()
  await page.getByRole('button', { name: 'Ask your CFO', exact: true }).click()
  await expect(page.getByPlaceholder('Ask about your books')).toBeDisabled()
  expect(errors).toEqual([])
})

test('upload updates real calculations, isolates browsers, preserves books on failure, and resets', async ({ page, browser }) => {
  await page.goto('/')
  await expect(page.locator('.tile-value').nth(1)).toHaveText('$52,900')
  await selectBooks(page)
  await expect(page.getByRole('dialog')).not.toBeVisible()
  await expect(page.locator('.tile-value').nth(1)).toHaveText('$53,140')
  await expect(page.locator('.tile-value').nth(2)).toContainText('8,070')
  await expect(page.locator('.dataset-tag')).toHaveText('Your books')
  await expect(page.locator('.affordability .verdict')).toContainText('$16,903')

  const other = await browser.newContext()
  try {
    const otherPage = await other.newPage()
    await otherPage.goto(page.url())
    await expect(otherPage.locator('.tile-value').nth(1)).toHaveText('$52,900')
  } finally {
    await other.close()
  }

  await selectBooks(page, { invalid: true })
  await expect(page.getByRole('alert')).toContainText('invoices.csv: missing columns')
  const response = await page.request.get('/api/report')
  expect((await response.json()).monthly_summary.expenses).toBe(53140)
  await page.getByRole('button', { name: 'Cancel', exact: true }).click()
  await page.getByRole('button', { name: 'Use your own books' }).click()
  await page.getByRole('button', { name: 'Use sample books', exact: true }).click()
  await expect(page.getByRole('dialog')).not.toBeVisible()
  await expect(page.locator('.tile-value').nth(1)).toHaveText('$52,900')
  await expect(page.locator('.dataset-tag')).toHaveText('Sample data')
})

test('a failed report request shows an error and can be retried', async ({ page }) => {
  await page.route('**/api/report', (route) => route.fulfill({ status: 503, json: { detail: 'API temporarily unavailable' } }))
  await page.goto('/')
  await expect(page.getByRole('alert')).toHaveText('API temporarily unavailable')
  await page.unroute('**/api/report')
  await page.getByRole('button', { name: 'Try again' }).click()
  await expect(page.locator('.tile-value').nth(1)).toHaveText('$52,900')
})

// Model responses are controlled here; reports/uploads still use the actual API.
async function enableAi(page) {
  await page.route(/\/api\/report(?:\?.*)?$/, async (route) => {
    const response = await route.fetch()
    const report = await response.json()
    await route.fulfill({ response, json: { ...report, agent_status: { available: true, message: '' } } })
  })
}

function events(items) {
  return items.map((event) => `data: ${JSON.stringify(event)}\n\n`).join('')
}

test('AI narrative and chat retain live books and reset after upload', async ({ page }) => {
  const errors = []
  page.on('pageerror', (error) => errors.push(error.message))
  await enableAi(page)
  await page.route('**/api/report/narrative?*', async (route) => {
    const report = await (await page.request.get('/api/report')).json()
    await route.fulfill({ contentType: 'text/event-stream', body: events([
      { text: 'A preamble.' }, { reset: true },
      { text: `Expenses are $${report.monthly_summary.expenses.toLocaleString('en-US')}.\n\nIssues\n- Review insurance.\n\nRecommendations\n- Check your policy.` },
      { done: true },
    ]) })
  })
  const requests = []
  await page.route('**/api/ask', async (route) => {
    const request = route.request().postDataJSON()
    requests.push(request)
    const report = await (await page.request.get('/api/report')).json()
    await route.fulfill({ contentType: 'text/event-stream', body: events([
      { type: 'session', session_id: request.session_id || `chat-${requests.length}` },
      { type: 'text', text: 'Let me look.' }, { type: 'text_reset' },
      { type: 'status', text: 'Consulted the expense analyst' },
      { type: 'text', text: `Your expenses are $${report.monthly_summary.expenses.toLocaleString('en-US')}.` },
      { type: 'card', card: { type: 'receivables', data: report.receivables } },
      { type: 'done' },
    ]) })
  })
  await page.goto('/')
  await expect(page.locator('.caption-body')).toContainText('Expenses are $52,900.')
  await expect(page.locator('.caption-body')).not.toContainText('A preamble')
  await page.getByRole('button', { name: 'Ask your CFO', exact: true }).click()
  const input = page.getByPlaceholder('Ask about your books')
  await input.fill('How much did I spend?')
  await page.getByRole('button', { name: 'Send', exact: true }).click()
  await expect(page.locator('.message-assistant').last()).toContainText('Your expenses are $52,900.')
  await expect(page.locator('.message-assistant').last()).not.toContainText('Let me look')
  await expect(page.locator('.data-card')).toContainText('Who owes you')
  await input.fill('What about insurance?')
  await page.getByRole('button', { name: 'Send', exact: true }).click()
  await expect(page.locator('.data-card')).toHaveCount(2)
  expect(requests[0].session_id).toBeNull()
  expect(requests[1].session_id).toBe('chat-1')
  await page.getByRole('button', { name: 'Close chat' }).click()
  await selectBooks(page)
  await expect(page.locator('.caption-body')).toContainText('Expenses are $53,140.')
  await page.getByRole('button', { name: 'Ask your CFO', exact: true }).click()
  await expect(page.locator('.data-card')).toHaveCount(0)
  await input.fill('How much did I spend now?')
  await page.getByRole('button', { name: 'Send', exact: true }).click()
  await expect(page.locator('.message-assistant').last()).toContainText('Your expenses are $53,140.')
  expect(requests[2].session_id).toBeNull()
  expect(errors).toEqual([])
})

test('model errors finish loading and keep the finance report usable', async ({ page }) => {
  await enableAi(page)
  await page.route('**/api/report/narrative?*', (route) => route.fulfill({
    contentType: 'text/event-stream', body: events([{ error: 'Model unavailable' }, { done: true }]),
  }))
  await page.route('**/api/ask', (route) => route.fulfill({ contentType: 'text/event-stream', body: events([
    { type: 'error', message: 'Model unavailable' }, { type: 'done' },
  ]) }))
  await page.goto('/')
  await expect(page.locator('.caption-body')).toContainText('The written report could not load: Model unavailable')
  await expect(page.locator('.tile-value').nth(1)).toHaveText('$52,900')
  await page.getByRole('button', { name: 'Ask your CFO', exact: true }).click()
  await page.getByPlaceholder('Ask about your books').fill('Why did profit drop?')
  await page.getByRole('button', { name: 'Send', exact: true }).click()
  await expect(page.locator('.message-assistant').last()).toContainText('Model unavailable')
  await expect(page.getByPlaceholder('Ask about your books')).toBeEnabled()
  await expect(page.locator('.chat .skeleton')).toHaveCount(0)
})
