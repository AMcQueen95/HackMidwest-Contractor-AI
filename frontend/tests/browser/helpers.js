import fs from 'node:fs'
import { fileURLToPath } from 'node:url'
import { expect } from '@playwright/test'

const sample = fileURLToPath(new URL('../../../backend/app/data/sample/', import.meta.url))
export const password = 'browser-passphrase-123'

export async function prepareCompany(page, { seed = true } = {}) {
  const email = `browser-${crypto.randomUUID()}@example.com`
  const signup = await page.request.post('/api/auth/signup', { data: { email, password } })
  expect(signup.ok()).toBeTruthy()
  const created = await page.request.post('/api/companies', { data: { name: 'Browser company' } })
  expect(created.ok()).toBeTruthy()
  const { company } = await created.json()
  page.company = company
  page.email = email
  if (seed) {
    const multipart = {}
    for (const name of ['transactions.csv', 'jobs.csv', 'invoices.csv', 'business.json']) {
      multipart[`file-${name}`] = { name, mimeType: name.endsWith('.json') ? 'application/json' : 'text/csv', buffer: fs.readFileSync(`${sample}/${name}`) }
    }
    // The canonical uploader expects repeated "files" fields.
    const body = new FormData()
    for (const value of Object.values(multipart)) body.append('files', new Blob([value.buffer], { type: value.mimeType }), value.name)
    const request = new Request('http://unused', { method: 'POST', body })
    const upload = await page.request.post('/api/upload', {
      headers: { 'X-Company-ID': company.id, 'Content-Type': request.headers.get('content-type') },
      data: Buffer.from(await request.arrayBuffer()),
    })
    expect(upload.ok()).toBeTruthy()
  }
  return { email, password, company }
}

export async function openCompany(page) {
  await page.goto('/')
  await page.getByRole('button', { name: page.company.name, exact: true }).click()
}

export const companyReport = (page) => page.request.get('/api/report', { headers: { 'X-Company-ID': page.company.id } })
