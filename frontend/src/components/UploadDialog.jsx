import { useEffect, useRef, useState } from 'react'
import { resetBooks, uploadBooks } from '../api'
import { CheckIcon, CloseIcon, UploadIcon } from './Icons'

const FILES = [
  { name: 'transactions.csv', about: 'Every payment in and out' },
  { name: 'jobs.csv', about: 'Each job, its quote, and hours worked' },
  { name: 'invoices.csv', about: 'What you billed and what has been paid' },
  { name: 'business.json', about: 'Business settings and reporting dates' },
]

export default function UploadDialog({ onClose, onUploaded, isSample }) {
  const ref = useRef(null)
  const [files, setFiles] = useState({})
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const ready = FILES.every(({ name }) => files[name])

  useEffect(() => {
    if (!ref.current.open) ref.current.showModal()
  }, [])

  const choose = (name, event) => {
    const file = event.target.files[0]
    setError('')
    if (file && (file.name !== name || file.size > 10 * 1024 * 1024)) {
      setError(file.name !== name ? `Choose a file named ${name}.` : `${name} exceeds the 10 MiB size limit.`)
      event.target.value = ''
      setFiles((current) => ({ ...current, [name]: undefined }))
      return
    }
    setFiles((current) => ({ ...current, [name]: file }))
  }

  const submit = async (event) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      await uploadBooks(files)
      onUploaded()
    } catch (error) {
      setError(error.message)
    } finally {
      setBusy(false)
    }
  }

  const reset = async () => {
    setBusy(true)
    setError('')
    try {
      await resetBooks()
      onUploaded()
    } catch (error) {
      setError(error.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <dialog ref={ref} className="dialog" onClose={onClose} onCancel={(event) => {
      if (busy) event.preventDefault()
    }}>
      <form onSubmit={submit}>
        <header className="dialog-header">
          <h2>Use your own books</h2>
          <button type="button" className="icon-button" aria-label="Close" onClick={onClose} disabled={busy}>
            <CloseIcon />
          </button>
        </header>
        <p className="dialog-intro">
          Add all four files together. They replace the books for this browser session after validation succeeds.
        </p>
        <ul className="file-list">
          {FILES.map((file) => (
            <li key={file.name}>
              <span className="file-state">{files[file.name] ? <CheckIcon /> : <UploadIcon />}</span>
              <label className="file-choice">
                <strong>{file.name}</strong>
                <span>{file.about}</span>
                <input type="file" aria-label={file.name} accept={file.name.endsWith('.json') ? '.json' : '.csv'}
                  onChange={(event) => choose(file.name, event)} disabled={busy} />
              </label>
            </li>
          ))}
        </ul>
        {error && <p role="alert" className="is-bad upload-error">{error} Your current books have been kept.</p>}
        <p className="dialog-note">Validated books are saved to this company. Invalid uploads preserve your current books.</p>
        <footer className="dialog-footer">
          {!isSample && <button type="button" className="button" onClick={reset} disabled={busy}>Clear company books</button>}
          <button type="button" className="button" onClick={onClose} disabled={busy}>Cancel</button>
          <button type="submit" className="button button-primary" disabled={!ready || busy}>
            {busy ? 'Updating books…' : 'Upload books'}
          </button>
        </footer>
      </form>
    </dialog>
  )
}
