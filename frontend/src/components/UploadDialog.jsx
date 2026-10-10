import { useEffect, useRef } from 'react'
import { AlertIcon, CheckIcon, CloseIcon } from './Icons'

// Display only until POST /api/upload exists. The error shown is an example of
// the 422 validation response, worded like the loader's messages.
const FILES = [
  { name: 'transactions.csv', about: 'Every payment in and out', ok: true },
  { name: 'jobs.csv', about: 'Each job, its quote, and hours worked', ok: true },
  {
    name: 'invoices.csv',
    about: 'What you billed and what has been paid',
    error: 'Missing columns: paid_amount, paid_date',
  },
  { name: 'business.json', about: 'Business name, opening balance, labor rate', ok: true },
]

export default function UploadDialog({ onClose }) {
  const ref = useRef(null)

  useEffect(() => {
    // Strict mode runs effects twice in dev, and showModal throws if already open.
    if (!ref.current.open) ref.current.showModal()
  }, [])

  return (
    <dialog ref={ref} className="dialog" onClose={onClose}>
      <header className="dialog-header">
        <h2>Use your own books</h2>
        <button type="button" className="icon-button" aria-label="Close" onClick={onClose}>
          <CloseIcon />
        </button>
      </header>
      <p className="dialog-intro">
        Add all four files together. They replace the sample data for everyone using this app.
      </p>

      <ul className="file-list">
        {FILES.map((file) => (
          <li key={file.name} className={file.error ? 'has-error' : ''}>
            <span className={`file-state ${file.error ? 'is-bad' : 'is-good'}`}>
              {file.error ? <AlertIcon /> : <CheckIcon />}
            </span>
            <div>
              <strong>{file.name}</strong>
              <p>{file.error ?? file.about}</p>
            </div>
          </li>
        ))}
      </ul>

      <p className="dialog-note">
        This is a preview of the upload step with an example error. Uploading isn't connected yet.
      </p>
      <footer className="dialog-footer">
        <button type="button" className="button" onClick={onClose}>
          Keep sample data
        </button>
        <button type="button" className="button button-primary" disabled>
          Upload books
        </button>
      </footer>
    </dialog>
  )
}
