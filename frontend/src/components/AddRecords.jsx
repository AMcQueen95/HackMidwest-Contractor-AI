import { useEffect, useRef, useState } from 'react'
import {
  connectSampleBank,
  createPlaidLinkToken,
  exchangePlaidToken,
  getImportSources,
  getPlaidStatus,
  importRecords,
} from '../api'
import { describeCounts } from '../lib/format'
import { openPlaidLink } from '../lib/plaid'
import { AlertIcon, CloseIcon, UploadIcon } from './Icons'
import OnboardingShell from './OnboardingShell'
import RecordsReview from './RecordsReview'

const MAX_FILES = 20
const MAX_BYTES = 10 * 1024 * 1024

function fileProblem(file) {
  if (!/\.csv$/i.test(file.name)) return `${file.name} is not a CSV file.`
  if (file.size === 0) return `${file.name} is empty.`
  if (file.size > MAX_BYTES) return `${file.name} is larger than 10 MB.`
  return ''
}

const WAITING = {
  files: 'Reading your files. This usually takes under a minute.',
  bank: 'Connecting to your bank and reading its activity. This usually takes under a minute.',
  sample: 'Connecting the sample bank and reading its activity. This usually takes under a minute.',
}

export default function AddRecords({ company, aiStatus, hasBooks, account, onBack, backLabel, onDone }) {
  const [files, setFiles] = useState([])
  const [dragging, setDragging] = useState(false)
  const [working, setWorking] = useState('')
  const [error, setError] = useState('')
  const [plaid, setPlaid] = useState(null)
  const [known, setKnown] = useState(null)
  const [review, setReview] = useState(null)
  const [round, setRound] = useState(0)
  const picker = useRef(null)

  useEffect(() => {
    let live = true
    getPlaidStatus().then((status) => { if (live) setPlaid(status) }).catch(() => { if (live) setPlaid({ configured: false }) })
    getImportSources().then((sources) => { if (live) setKnown(sources) }).catch(() => { if (live) setKnown({ sources: [], facts: {} }) })
    return () => { live = false }
  }, [round])

  const aiReady = aiStatus?.available ?? false
  const added = (known?.sources ?? []).filter((source) => source.transactions + source.invoices + source.jobs > 0)
  const busy = Boolean(working)

  function addFiles(list) {
    const incoming = [...list]
    const problem = incoming.map(fileProblem).find(Boolean)
    const merged = [...files]
    for (const file of incoming) {
      if (fileProblem(file)) continue
      const at = merged.findIndex((existing) => existing.name === file.name)
      if (at >= 0) merged[at] = file
      else merged.push(file)
    }
    if (merged.length > MAX_FILES) {
      setError(`Add up to ${MAX_FILES} files at a time.`)
      setFiles(merged.slice(0, MAX_FILES))
      return
    }
    setError(problem)
    setFiles(merged)
  }

  async function run(kind, work) {
    setWorking(kind)
    setError('')
    try {
      const result = await work()
      if (result) setReview(result)
    } catch (failure) {
      setError(failure.message)
    } finally {
      setWorking('')
    }
  }

  const readFiles = () => run('files', async () => ({
    kind: 'files',
    result: await importRecords(files, { details: { business_name: company.name }, dryRun: true }),
  }))

  const connectBank = () => run('bank', async () => {
    const { link_token: token } = await createPlaidLinkToken()
    const publicToken = await openPlaidLink(token)
    if (!publicToken) return null
    return { kind: 'bank', result: await exchangePlaidToken(publicToken) }
  })

  const useSampleBank = () => run('sample', async () => ({ kind: 'bank', result: await connectSampleBank() }))

  if (review) {
    return (
      <RecordsReview
        company={company}
        review={review}
        account={account}
        files={files}
        known={known}
        onBack={review.kind === 'bank' ? undefined : () => setReview(null)}
        onAddMore={() => { setReview(null); setFiles([]); setRound(round + 1) }}
        onDone={onDone}
      />
    )
  }

  return (
    <OnboardingShell step={2} width="medium" account={account} onBack={busy ? undefined : onBack} backLabel={backLabel}>
      <section className="setup-card">
        <p className="setup-kicker">{company.name}</p>
        <h1>{hasBooks ? 'Add more records' : 'Add your financial records'}</h1>
        <p className="setup-lede">
          {hasBooks
            ? 'New records are combined with what this company already has. Duplicates are skipped.'
            : 'Toolbelt CFO needs your records to calculate anything. Connect a bank, upload exports, or do both.'}
        </p>

        {!aiReady && (
          <p role="alert" className="form-alert is-bad">
            Reading records needs the AI service, which isn't available right now. {aiStatus?.message}
          </p>
        )}
        {error && <p role="alert" className="form-alert is-bad">{error}</p>}

        {busy ? (
          <div className="working" role="status">
            <div className="working-bar"><span /></div>
            <p>{WAITING[working]}</p>
          </div>
        ) : (
          <div className="record-options">
            <div className="record-option">
              <h2>Connect a bank</h2>
              <p>Pull checking, savings, and card activity directly. You sign in on Plaid's screen; Toolbelt CFO never sees your bank password.</p>
              {plaid && !plaid.configured && <p className="field-hint">Bank connections aren't set up on this server yet.</p>}
              {plaid?.environment === 'sandbox' && plaid.configured && (
                <p className="field-hint">Test mode: the bank window lists Plaid's practice banks, not real ones.</p>
              )}
              <div className="record-actions">
                <button type="button" className="button button-primary" onClick={connectBank} disabled={!aiReady || !plaid?.configured}>
                  Connect a bank
                </button>
                {plaid?.environment === 'sandbox' && (
                  <button type="button" className="button" onClick={useSampleBank} disabled={!aiReady || !plaid.configured}>
                    Use the sample contractor bank
                  </button>
                )}
              </div>
              {plaid?.banks_connected > 0 && <p className="field-hint">{plaid.banks_connected} bank connection saved for this company.</p>}
            </div>

            <div className="record-divider" aria-hidden="true"><span>or</span></div>

            <div className="record-option">
              <h2>Upload CSV exports</h2>
              <p>Bank and card statements, invoice lists, and job exports, in whatever layout your bank or apps produce. Add as many as you have.</p>
              <div
                className={`dropzone ${dragging ? 'is-dragging' : ''}`}
                onDragOver={(event) => { event.preventDefault(); setDragging(true) }}
                onDragLeave={() => setDragging(false)}
                onDrop={(event) => { event.preventDefault(); setDragging(false); addFiles(event.dataTransfer.files) }}
              >
                <UploadIcon />
                <p>Drop CSV files here</p>
                <button type="button" className="button" onClick={() => picker.current.click()}>Choose files</button>
                <input ref={picker} type="file" accept=".csv,text/csv" multiple hidden aria-label="CSV files"
                  onChange={(event) => { addFiles(event.target.files); event.target.value = '' }} />
              </div>
              {files.length > 0 && (
                <ul className="chosen-files">
                  {files.map((file) => (
                    <li key={file.name}>
                      <span>{file.name}</span>
                      <span className="muted">{Math.max(1, Math.round(file.size / 1024)).toLocaleString('en-US')} KB</span>
                      <button type="button" className="icon-button" aria-label={`Remove ${file.name}`}
                        onClick={() => setFiles(files.filter((other) => other !== file))}>
                        <CloseIcon />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              <div className="record-actions">
                <button type="button" className="button button-primary" onClick={readFiles} disabled={!aiReady || files.length === 0}>
                  {files.length > 1 ? `Read ${files.length} files` : 'Read my file'}
                </button>
              </div>
            </div>
          </div>
        )}

        {added.length > 0 && !busy && (
          <div className="known-sources">
            <h2>Already added</h2>
            <ul>
              {added.map((source) => (
                <li key={source.name}>
                  <span>{source.name.startsWith('bank:') ? 'Connected bank' : source.name}</span>
                  <span className="muted">{describeCounts(source)}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        <p className="setup-note">
          <AlertIcon /> Nothing is saved from uploaded files until you review and confirm on the next step.
        </p>
      </section>
    </OnboardingShell>
  )
}
