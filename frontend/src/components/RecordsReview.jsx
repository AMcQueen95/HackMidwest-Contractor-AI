import { useState } from 'react'
import { importRecords } from '../api'
import { describeCounts, money, shortDate } from '../lib/format'
import { parseNumber, requireText } from '../lib/validate'
import { AlertIcon, CheckIcon } from './Icons'
import OnboardingShell from './OnboardingShell'

const KINDS = {
  transactions: 'Bank or card activity',
  invoices: 'Invoices',
  jobs: 'Jobs',
}

const SKIPPED_FILE = /: not a transactions, invoices or jobs file/

const FIELDS = {
  business_name: { label: 'Business name', hint: 'Shown at the top of your dashboard.' },
  opening_balance: {
    label: 'Bank balance at the start of these records',
    hint: 'None of your files included a balance, so cash can\'t be worked out without it.',
    prefix: '$',
    rule: { label: 'your starting bank balance', min: -10000000, max: 100000000, example: '45,000' },
  },
  labor_rate: {
    label: 'What an hour of labor costs you',
    hint: 'Your jobs list hours worked. This turns hours into a cost for each job.',
    prefix: '$',
    suffix: 'per hour',
    rule: { label: 'your hourly labor cost', min: 1, max: 1000, example: '50' },
  },
  tax_reserve_rate: {
    label: 'Share of profit to set aside for taxes',
    hint: 'Held back from available cash. Your accountant can tell you the right figure.',
    suffix: '%',
    rule: { label: 'a percentage', min: 0, max: 60, example: '25' },
  },
}

function neededFields(result, known) {
  const facts = known?.facts ?? {}
  const confirmedBefore = (known?.sources?.length ?? 0) > 0
  const needed = ['business_name']
  if (result.summary.bank_balance_now == null && facts.opening_balance == null) needed.push('opening_balance')
  if (result.summary.jobs > 0 && !(facts.labor_rate > 0)) needed.push('labor_rate')
  if (!confirmedBefore) needed.push('tax_reserve_rate')
  return needed
}

function check(key, text) {
  if (key === 'business_name') return requireText(text, { label: 'your business name', max: 120 })
  return parseNumber(text, FIELDS[key].rule)
}

function FileResult({ file }) {
  const recognised = file.kind in KINDS
  return (
    <li className={recognised ? '' : 'is-skipped'}>
      <span className={`file-state ${recognised ? 'is-good' : 'is-bad'}`}>{recognised ? <CheckIcon /> : <AlertIcon />}</span>
      <div>
        <strong>{file.name}</strong>
        <p>
          {recognised
            ? `${KINDS[file.kind]}: ${describeCounts(file).toLowerCase()}`
            : 'Not recognised as financial records, so it will be skipped'}
        </p>
        {recognised && file.source && <p className="muted">{file.source}</p>}
        {file.notes && (
          <details className="file-notes">
            <summary>How this file was read</summary>
            <p>{file.notes}</p>
          </details>
        )}
      </div>
    </li>
  )
}

function Summary({ summary }) {
  const [start, end] = summary.date_range
  return (
    <dl className="review-summary" aria-label="Records this company will have">
      <div><dt>Transactions</dt><dd>{summary.transactions.toLocaleString('en-US')}</dd></div>
      <div><dt>Invoices</dt><dd>{summary.invoices.toLocaleString('en-US')}</dd></div>
      <div><dt>Jobs</dt><dd>{summary.jobs.toLocaleString('en-US')}</dd></div>
      <div><dt>Covers</dt><dd>{shortDate(start)} to {shortDate(end)}</dd></div>
    </dl>
  )
}

function Warnings({ warnings }) {
  if (!warnings.length) return null
  return (
    <div className="review-block">
      <h2>Things to know</h2>
      <ul className="review-warnings">
        {warnings.map((warning) => (
          <li key={warning}><AlertIcon /> <span>{warning}</span></li>
        ))}
      </ul>
    </div>
  )
}

function BankReview({ company, result, account, onAddMore, onDone }) {
  return (
    <OnboardingShell step={3} width="medium" account={account}>
      <section className="setup-card">
        <p className="setup-kicker">{company.name}</p>
        <h1>Bank connected</h1>
        <p className="setup-lede">
          {result.bank.transactions.toLocaleString('en-US')} transactions were read and saved to this company.
        </p>
        <ul className="file-results">
          {result.bank.accounts.map((account) => (
            <li key={`${account.name}-${account.mask}`}>
              <span className="file-state is-good"><CheckIcon /></span>
              <div>
                <strong>{account.name}{account.mask ? ` ····${account.mask}` : ''}</strong>
                <p>
                  {account.subtype || account.type}
                  {account.current_balance != null ? `, current balance ${money(account.current_balance)}` : ''}
                </p>
              </div>
            </li>
          ))}
        </ul>
        <Summary summary={result.summary} />
        <Warnings warnings={result.warnings.filter((warning) => !SKIPPED_FILE.test(warning))} />
        <p className="setup-note">
          <AlertIcon /> Banks don't hold your invoices or jobs. Add those exports to see who owes you and which jobs made money.
        </p>
        <div className="setup-actions">
          <button type="button" className="button" onClick={onAddMore}>Add invoice or job exports</button>
          <button type="button" className="button button-primary button-large" onClick={onDone}>Open my dashboard</button>
        </div>
      </section>
    </OnboardingShell>
  )
}

export default function RecordsReview({ company, review, files, known, account, onBack, onAddMore, onDone }) {
  const { result } = review
  const needed = review.kind === 'files' ? neededFields(result, known) : []
  const [values, setValues] = useState({ business_name: known?.sources?.length ? known.facts.name : company.name })
  const [touched, setTouched] = useState({})
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  if (review.kind === 'bank') return <BankReview company={company} result={result} account={account} onAddMore={onAddMore} onDone={onDone} />

  const usable = result.files.some((file) => file.kind in KINDS)
  const skipped = result.files.filter((file) => !(file.kind in KINDS)).map((file) => `${file.name}:`)
  const asked = [
    needed.includes('opening_balance') && 'Starting cash balance unknown',
    needed.includes('labor_rate') && 'Jobs have labor hours but no labor rate',
  ].filter(Boolean)
  const warnings = result.warnings.filter((warning) =>
    ![...skipped, ...asked].some((prefix) => warning.startsWith(prefix)))
  const checks = Object.fromEntries(needed.map((key) => [key, check(key, values[key])]))
  const valid = needed.every((key) => !checks[key].error)

  async function save(event) {
    event.preventDefault()
    setTouched(Object.fromEntries(needed.map((key) => [key, true])))
    if (!valid || !usable) return
    setSaving(true)
    setError('')
    try {
      const details = Object.fromEntries(needed.map((key) => [key, checks[key].value]))
      if (details.tax_reserve_rate != null) details.tax_reserve_rate = details.tax_reserve_rate / 100
      await importRecords(files, { details })
      onDone()
    } catch (failure) {
      setError(failure.message)
      setSaving(false)
    }
  }

  return (
    <OnboardingShell step={3} width="medium" account={account} onBack={saving ? undefined : onBack}>
      <form className="setup-card" onSubmit={save} noValidate>
        <p className="setup-kicker">{company.name}</p>
        <h1>Check what we read</h1>
        <p className="setup-lede">Nothing has been saved yet. Confirm below to add these records to your company.</p>

        <ul className="file-results">
          {result.files.map((file) => <FileResult key={file.name} file={file} />)}
        </ul>

        {usable && <Summary summary={result.summary} />}
        <Warnings warnings={warnings} />

        {usable && (
          <div className="review-block">
            <h2>Details your files couldn't tell us</h2>
            <div className="review-fields">
              {needed.map((key) => {
                const field = FIELDS[key]
                const problem = touched[key] ? checks[key].error : ''
                return (
                  <div key={key} className={`field ${problem ? 'has-error' : ''}`}>
                    <label htmlFor={`detail-${key}`}>{field.label}</label>
                    <div className="field-input">
                      {field.prefix && <span aria-hidden="true">{field.prefix}</span>}
                      <input
                        id={`detail-${key}`}
                        type="text"
                        inputMode={field.rule ? 'decimal' : 'text'}
                        value={values[key] ?? ''}
                        aria-invalid={Boolean(problem)}
                        aria-describedby={`detail-${key}-hint`}
                        disabled={saving}
                        onChange={(event) => setValues({ ...values, [key]: event.target.value })}
                        onBlur={() => setTouched({ ...touched, [key]: true })}
                      />
                      {field.suffix && <span aria-hidden="true">{field.suffix}</span>}
                    </div>
                    <p id={`detail-${key}-hint`} className={problem ? 'field-error' : 'field-hint'} role={problem ? 'alert' : undefined}>
                      {problem || field.hint}
                    </p>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {!usable && (
          <p role="alert" className="form-alert is-bad">
            None of these files could be read as bank activity, invoices, or jobs. Go back and choose different files.
          </p>
        )}
        {error && <p role="alert" className="form-alert is-bad">{error} Nothing was saved.</p>}

        {saving ? (
          <div className="working" role="status">
            <div className="working-bar"><span /></div>
            <p>Saving your records and building your dashboard. This usually takes under a minute.</p>
          </div>
        ) : (
          <div className="setup-actions">
            <button type="submit" className="button button-primary button-large" disabled={!usable}>
              Save and open my dashboard
            </button>
          </div>
        )}
      </form>
    </OnboardingShell>
  )
}
