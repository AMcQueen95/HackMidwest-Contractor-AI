import { test, expect } from '@playwright/test'
import { prepareCompany, openCompany, companyReport, uploadBooks } from './helpers'

test.beforeEach(async ({ page }) => { await prepareCompany(page) })

// Model responses are controlled here; reports/uploads still use the actual API.
async function enableAi(page) {
  await page.route(/\/api\/report(?:\?.*)?$/, async (route) => {
    const response = await route.fetch()
    const report = await response.json()
    await route.fulfill({ response, json: { ...report, agent_status: { available: true, message: '' } } })
  })
}

async function quietNarrative(page) {
  await page.route('**/api/report/narrative?*', (route) => route.fulfill({
    contentType: 'text/event-stream', body: events([{ done: true }]) }))
}

async function replaceBooks(page) {
  expect((await uploadBooks(page, { insurance: '-1500' })).ok()).toBeTruthy()
  await page.reload()
  await page.getByRole('button', { name: page.company.name, exact: true }).click()
}

test('dashboard, month selection, and purchase checks use the live API', async ({ page }) => {
  const errors = []
  page.on('pageerror', (error) => errors.push(error.message))
  await openCompany(page)
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

test('new books update real calculations, isolate browsers, survive a failed upload, and can be cleared', async ({ page, browser }) => {
  await openCompany(page)
  await expect(page.locator('.tile-value').nth(1)).toHaveText('$52,900')
  await replaceBooks(page)
  await expect(page.locator('.tile-value').nth(1)).toHaveText('$53,140')
  await expect(page.locator('.tile-value').nth(2)).toContainText('8,070')
  await expect(page.locator('.dataset-tag')).toHaveText('Your books')
  await expect(page.locator('.affordability .verdict')).toContainText('$16,903')

  const other = await browser.newContext()
  try {
    const otherPage = await other.newPage()
    await otherPage.goto(page.url())
    await otherPage.getByRole('button', { name: 'Try the demo' }).click()
    await expect(otherPage.locator('.tile-value').nth(1)).toHaveText('$52,900')
  } finally {
    await other.close()
  }

  const rejected = await uploadBooks(page, { invalid: true })
  expect(rejected.status()).toBe(422)
  expect((await rejected.json()).detail).toContain('invoices.csv: missing columns')
  const response = await companyReport(page)
  expect((await response.json()).monthly_summary.expenses).toBe(53140)

  await page.getByRole('button', { name: 'Settings' }).click()
  await page.getByRole('button', { name: 'Clear company books', exact: true }).click()
  await page.getByRole('button', { name: 'Keep records', exact: true }).click()
  await expect(page.locator('.tile-value').nth(1)).toHaveText('$53,140')
  await page.getByRole('button', { name: 'Clear company books', exact: true }).click()
  await page.getByRole('button', { name: 'Yes, clear them', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Add your financial records' })).toBeVisible()
})

const csv = (name) => ({ name, mimeType: 'text/csv', buffer: Buffer.from('Date,Description,Amount\n09/02/2026,Deposit,100\n') })

test('CSV exports are reviewed, missing details are validated, and nothing saves before confirming', async ({ page }) => {
  await prepareCompany(page, { seed: false })
  await enableAi(page)
  await quietNarrative(page)
  await page.route('**/api/plaid/status', (route) => route.fulfill({ json: { configured: true, environment: 'sandbox', banks_connected: 0 } }))
  const posts = []
  await page.route('**/api/import', async (route) => {
    const body = route.request().postData()
    const field = (name) => body.match(new RegExp(`name="${name}"\\r\\n\\r\\n([^\\r]*)`))?.[1]
    const dryRun = field('dry_run') === 'true'
    posts.push({ dryRun, name: field('business_name'), balance: field('opening_balance'), labor: field('labor_rate'), tax: field('tax_reserve_rate') })
    if (!dryRun) expect((await uploadBooks(page)).ok()).toBeTruthy()
    await route.fulfill({ json: {
      applied: !dryRun,
      files: [
        { name: 'bank.csv', kind: 'transactions', source: 'Bank export', rows: 1, transactions: 1, invoices: 0, jobs: 0, notes: 'Signed amounts.' },
        { name: 'jobs.csv', kind: 'jobs', source: 'Jobs export', rows: 1, transactions: 0, invoices: 0, jobs: 1, notes: '' },
        { name: 'crew.csv', kind: 'unknown', source: '', rows: 2, transactions: 0, invoices: 0, jobs: 0, notes: 'A contact list.' },
      ],
      warnings: ['crew.csv: not a transactions, invoices or jobs file, so it was skipped.',
        "Starting cash balance unknown, so it's set to $0.", 'Left out 2 transfer transactions.'],
      summary: { transactions: 1, invoices: 0, jobs: 1, date_range: ['2026-09-02', '2026-09-30'], bank_balance_now: null },
      sources: [],
    } })
  })

  await openCompany(page)
  await expect(page.getByRole('heading', { name: 'Add your financial records' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Read my file', exact: true })).toBeDisabled()
  await page.getByLabel('CSV files').setInputFiles([{ ...csv('notes.txt'), mimeType: 'text/plain' }])
  await expect(page.getByRole('alert')).toContainText('notes.txt is not a CSV file.')
  await page.getByLabel('CSV files').setInputFiles([csv('bank.csv'), csv('jobs.csv'), csv('crew.csv')])
  await page.getByRole('button', { name: 'Read 3 files', exact: true }).click()

  await expect(page.getByRole('heading', { name: 'Check what we read' })).toBeVisible()
  await expect(page.locator('.file-results li')).toHaveCount(3)
  await expect(page.locator('.file-results li.is-skipped')).toContainText('crew.csv')
  await expect(page.locator('.review-warnings li')).toHaveCount(1)
  await expect(page.getByLabel('Business name')).toHaveValue('Browser company')
  expect(posts).toEqual([{ dryRun: true, name: 'Browser company', balance: undefined, labor: undefined, tax: undefined }])
  expect((await (await companyReport(page)).json()).has_books).toBe(false)

  await page.getByLabel('Bank balance at the start of these records').fill('adninwainwadnwa')
  await page.getByLabel('What an hour of labor costs you').fill('-5')
  await page.getByRole('button', { name: 'Save and open my dashboard' }).click()
  await expect(page.locator('.field-error')).toHaveText([
    'Use numbers only, like 45,000.', "This can't be less than 1.", 'Enter a percentage.'])
  expect(posts).toHaveLength(1)

  await page.getByLabel('Bank balance at the start of these records').fill('$45,000')
  await page.getByLabel('What an hour of labor costs you').fill('50')
  await page.getByLabel('Share of profit to set aside for taxes').fill('25%')
  await expect(page.locator('.field-error')).toHaveCount(0)
  await page.getByRole('button', { name: 'Save and open my dashboard' }).click()
  await expect(page.locator('.tile-value').nth(1)).toHaveText('$52,900')
  expect(posts[1]).toEqual({ dryRun: false, name: 'Browser company', balance: '45000', labor: '50', tax: '0.25' })

  await page.getByRole('button', { name: 'Add records' }).click()
  await expect(page.getByRole('heading', { name: 'Add more records' })).toBeVisible()
  await page.getByRole('button', { name: 'Back to dashboard' }).click()
  await expect(page.locator('.tile-value').nth(1)).toHaveText('$52,900')
})

test('the sample bank connects through the API and reports what was saved', async ({ page }) => {
  await prepareCompany(page, { seed: false })
  await enableAi(page)
  await quietNarrative(page)
  await page.route('**/api/plaid/status', (route) => route.fulfill({ json: { configured: true, environment: 'sandbox', banks_connected: 0 } }))
  await page.route('**/api/plaid/sandbox', async (route) => {
    expect((await uploadBooks(page)).ok()).toBeTruthy()
    await route.fulfill({ json: {
      applied: true, warnings: ['Left out 2 transfer transactions.'],
      summary: { transactions: 28, invoices: 0, jobs: 0, date_range: ['2026-08-01', '2026-09-30'], bank_balance_now: 41250 },
      sources: [], bank: { item_id: 'sandbox', transactions: 28, accounts: [
        { name: 'Checking', type: 'depository', subtype: 'checking', mask: '4979', current_balance: 41250 }] },
    } })
  })
  await openCompany(page)
  await page.getByRole('button', { name: 'Use the sample contractor bank', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Bank connected' })).toBeVisible()
  await expect(page.locator('.file-results li')).toContainText('Checking ····4979')
  await expect(page.locator('.file-results li')).toContainText('$41,250')
  await page.getByRole('button', { name: 'Open my dashboard', exact: true }).click()
  await expect(page.locator('.tile-value').nth(1)).toHaveText('$52,900')
})

test('a failed report request shows an error and can be retried', async ({ page }) => {
  await page.route('**/api/report', (route) => route.fulfill({ status: 503, json: { detail: 'API temporarily unavailable' } }))
  await openCompany(page)
  await expect(page.getByRole('alert')).toHaveText('API temporarily unavailable')
  await page.unroute('**/api/report')
  await page.getByRole('button', { name: 'Try again' }).click()
  await expect(page.locator('.tile-value').nth(1)).toHaveText('$52,900')
})

function events(items) {
  return items.map((event) => `data: ${JSON.stringify(event)}\n\n`).join('')
}

test('AI narrative and chat retain live books and reset after upload', async ({ page }) => {
  const errors = []
  page.on('pageerror', (error) => errors.push(error.message))
  await enableAi(page)
  await page.route('**/api/report/narrative?*', async (route) => {
    const report = await (await companyReport(page)).json()
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
    const report = await (await companyReport(page)).json()
    await route.fulfill({ contentType: 'text/event-stream', body: events([
      { type: 'session', session_id: request.session_id || `chat-${requests.length}` },
      { type: 'text', text: 'Let me look.' }, { type: 'text_reset' },
      { type: 'status', text: 'Consulted the expense analyst' },
      { type: 'text', text: `Your expenses are $${report.monthly_summary.expenses.toLocaleString('en-US')}.` },
      { type: 'card', card: { type: 'receivables', data: report.receivables } },
      { type: 'done' },
    ]) })
  })
  await openCompany(page)
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
  await replaceBooks(page)
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
  await openCompany(page)
  await expect(page.locator('.caption-body')).toContainText('The written report could not load: Model unavailable')
  await expect(page.locator('.tile-value').nth(1)).toHaveText('$52,900')
  await page.getByRole('button', { name: 'Ask your CFO', exact: true }).click()
  await page.getByPlaceholder('Ask about your books').fill('Why did profit drop?')
  await page.getByRole('button', { name: 'Send', exact: true }).click()
  await expect(page.locator('.message-assistant').last()).toContainText('Model unavailable')
  await expect(page.getByPlaceholder('Ask about your books')).toBeEnabled()
  await expect(page.locator('.chat .skeleton')).toHaveCount(0)
})
