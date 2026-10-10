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
  await expect(page.getByText('AI explanations are not connected yet. Your report and purchase checks use live financial calculations.')).toBeVisible()
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
