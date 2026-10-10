import { useEffect, useState } from 'react'
import { checkAffordability } from '../api'
import Affordability from './Affordability'

export default function PurchaseCheck() {
  const [input, setInput] = useState('15,000')
  const [result, setResult] = useState(null)
  const amount = Number(input.replace(/[^0-9.]/g, ''))

  useEffect(() => {
    if (!(amount > 0)) {
      setResult(null)
      return
    }
    let stale = false
    checkAffordability(amount).then((data) => {
      if (!stale) setResult(data)
    })
    return () => {
      stale = true
    }
  }, [amount])

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
      {result ? <Affordability data={result} /> : <p className="empty">Enter an amount to check.</p>}
    </div>
  )
}
