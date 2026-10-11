import { test, expect } from '@playwright/test'
import { prepareCompany, openCompany, password } from './helpers'

test('welcome requires sign-in and public demo cannot upload or call AI', async ({ page }) => {
  const paths = []
  page.on('request', request => paths.push(new URL(request.url()).pathname))
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Sign in to your company' })).toBeVisible()
  expect((await page.request.get('/api/plaid/status')).status()).toBe(401)
  await page.getByRole('button', { name: 'Try the demo' }).click()
  await expect(page.locator('.tile-value').nth(1)).toHaveText('$52,900')
  await expect(page.getByRole('button', { name: 'Use your own books' })).toHaveCount(0)
  await page.getByRole('button', { name: 'Ask your CFO', exact: true }).click()
  await expect(page.getByPlaceholder('Ask about your books')).toBeDisabled()
  expect(paths).not.toContain('/api/report/narrative')
  expect(paths).not.toContain('/api/ask')
  await page.getByRole('button', { name: 'Back to welcome' }).click()
  await expect(page.getByRole('heading', { name: 'Sign in to your company' })).toBeVisible()
})

test('sign up, create an empty company, switch companies, and sign out', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Create account', exact: true }).click()
  await page.getByLabel('Email', { exact: true }).fill(`signup-${crypto.randomUUID()}@example.com`)
  await page.getByLabel('Password', { exact: true }).fill(password)
  await page.getByRole('button', { name: 'Create account', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Your companies' })).toBeVisible()
  await page.getByLabel('Company name').fill('My new company')
  await page.getByRole('button', { name: 'Create company', exact: true }).click()
  await expect(page.getByText('This company has no books yet.', { exact: false })).toBeVisible()
  await expect(page.locator('.tile-value')).toHaveCount(0)
  await page.getByRole('button', { name: 'Switch company' }).click()
  await page.getByLabel('Company name').fill('Another company')
  await page.getByRole('button', { name: 'Create company', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Another company' })).toBeVisible()
  await page.getByRole('button', { name: 'Sign out', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Sign in to your company' })).toBeVisible()
  expect((await page.request.get('/api/auth/me')).status()).toBe(401)
})

test('saved books survive logout, login, and a new browser without storing tokens in localStorage', async ({ page, browser }) => {
  const account = await prepareCompany(page)
  await openCompany(page)
  await expect(page.locator('.tile-value').nth(1)).toHaveText('$52,900')
  const cookies = await page.context().cookies()
  expect(cookies.filter(cookie => ['toolbelt_access', 'toolbelt_refresh'].includes(cookie.name)).every(cookie => cookie.httpOnly)).toBeTruthy()
  await page.getByRole('button', { name: 'Sign out', exact: true }).click()
  const context = await browser.newContext()
  try {
    const other = await context.newPage()
    await other.goto('http://127.0.0.1:5173')
    await other.getByLabel('Email', { exact: true }).fill(account.email)
    await other.getByLabel('Password', { exact: true }).fill(password)
    await other.getByRole('button', { name: 'Sign in', exact: true }).click()
    await other.getByRole('button', { name: account.company.name, exact: true }).click()
    await expect(other.locator('.tile-value').nth(1)).toHaveText('$52,900')
    expect(await other.evaluate(() => Object.keys(localStorage))).toEqual(['toolbelt-theme'])
  } finally { await context.close() }
})

test('an expired request refreshes account cookies and a retry error keeps the user signed in', async ({ page }) => {
  await prepareCompany(page)
  let calls = 0
  await page.route('**/api/report', route => {
    calls += 1
    return calls === 1 ? route.fulfill({ status: 401, json: { detail: 'Please sign in again.' } })
      : route.fulfill({ status: 409, json: { detail: 'Records changed; please refresh.' } })
  })
  await openCompany(page)
  await expect(page.getByRole('alert')).toContainText('Records changed; please refresh.')
  await expect(page.getByRole('button', { name: 'Sign out', exact: true })).toBeVisible()
  expect((await page.request.get('/api/auth/me')).ok()).toBeTruthy()
  await page.unroute('**/api/report')
  await page.getByRole('button', { name: 'Try again', exact: true }).click()
  await expect(page.locator('.tile-value').nth(1)).toHaveText('$52,900')
})
