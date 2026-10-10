import { useEffect, useState } from 'react'
import { checkAffordability } from '../api'
import Affordability from './Affordability'

export default function PurchaseCheck({ datasetRevision }) {
  const [input, setInput] = useState('15,000')
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const amount = Number(input.replace(/[^0-9.]/g, ''))

  useEffect(() => {
    setResult(null)
    setError('')
    setLoading(false)
    if (!(amount > 0)) {
      return
    }
    const controller = new AbortController()
    setLoading(true)
    const timeout = setTimeout(() => {
      checkAffordability(amount, controller.signal)
        .then((data) => { if (!controller.signal.aborted) setResult(data) })
        .catch((error) => { if (!controller.signal.aborted) setError(error.message) })
        .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    }, 200)
    return () => {
      clearTimeout(timeout)
      controller.abort()
    }
  }, [amount, datasetRevision])

  const tidy = () => {
    if (amount > 0) setInput(amount.toLocaleString('en-US'))
  }

  return (
    <div>
      <label className="amount-field">
        <span>How much is the purchase?</span>
        <span className="amount-input">
          <span aria-hidden="true">$</span>
          <input
            type="text"
            inputMode="decimal"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onBlur={tidy}
          />
        </span>
      </label>
      {error ? <p role="alert" className="is-bad">{error}</p>
        : result ? <Affordability data={result} />
          : <p className="empty" role="status">{loading ? 'Checking your books…' : 'Enter an amount to check.'}</p>}
    </div>
  )
}
