import { useEffect, useState } from 'react'
import { getTrades, saveTrades } from '../api'
import OnboardingShell from './OnboardingShell'

const FALLBACK = [
  { key: 'hvac', name: 'HVAC' },
  { key: 'plumbing', name: 'Plumbing' },
  { key: 'electrical', name: 'Electrical' },
]

const ABOUT = {
  hvac: 'Heating, cooling, installs, repairs and maintenance plans',
  plumbing: 'Repairs, drains, water heaters, sewer and repipes',
  electrical: 'Service calls, panels, EV chargers, remodels and new construction',
}

// Onboarding step 3: what kinds of work the company does. Picks the report
// sections, the trade analyst and the advice the CFO gives.
export default function TradeStep({ company, initial, account, onBack, onDone }) {
  const [options, setOptions] = useState(FALLBACK)
  const [chosen, setChosen] = useState(new Set(initial?.trades ?? []))
  const [otherOn, setOtherOn] = useState(Boolean(initial?.other))
  const [other, setOther] = useState(initial?.other ?? '')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    getTrades()
      .then((list) => setOptions(list.filter((trade) => trade.ready)))
      .catch(() => {}) // the built-in list still works
  }, [])

  const toggle = (key) =>
    setChosen((current) => {
      const next = new Set(current)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })

  const ready = chosen.size > 0 || (otherOn && other.trim())

  async function submit(event) {
    event.preventDefault()
    if (!ready) return
    setBusy(true)
    setError('')
    try {
      await saveTrades({ trades: [...chosen], other: otherOn ? other.trim() : null })
      onDone()
    } catch (failure) {
      setError(failure.message)
      setBusy(false)
    }
  }

  return (
    <OnboardingShell step={2} account={account} onBack={busy ? undefined : onBack} backLabel="Switch company">
      <section className="setup-card">
        <p className="setup-kicker">{company?.name}</p>
        <h1>What kind of work do you do?</h1>
        <p className="setup-lede">Choose all that apply. Your CFO uses this to show the numbers that matter for your trade.</p>
        {error && <p role="alert" className="form-alert is-bad">{error}</p>}
        <form className="setup-form" onSubmit={submit}>
          <fieldset className="trade-choices">
            <legend className="visually-hidden">Kinds of work</legend>
            {options.map((trade) => (
              <label key={trade.key} className={`trade-choice ${chosen.has(trade.key) ? 'is-selected' : ''}`}>
                <input
                  id={`trade-${trade.key}`}
                  type="checkbox"
                  checked={chosen.has(trade.key)}
                  onChange={() => toggle(trade.key)}
                />
                <span>
                  <strong>{trade.name}</strong>
                  {ABOUT[trade.key] && <small>{ABOUT[trade.key]}</small>}
                </span>
              </label>
            ))}
            <label className={`trade-choice ${otherOn ? 'is-selected' : ''}`}>
              <input id="trade-other" type="checkbox" checked={otherOn} onChange={() => setOtherOn((on) => !on)} />
              <span>
                <strong>Other</strong>
                <small>Landscaping, roofing, remodeling or anything else</small>
              </span>
            </label>
          </fieldset>
          {otherOn && (
            <div className="field">
              <label htmlFor="trade-other-text">Describe your work</label>
              <input
                id="trade-other-text"
                value={other}
                onChange={(e) => setOther(e.target.value)}
                maxLength={200}
                placeholder="Landscaping and snow removal"
                autoFocus
              />
            </div>
          )}
          <button className="button button-primary button-large" disabled={busy || !ready}>
            {busy ? 'Saving…' : 'Continue'}
          </button>
        </form>
      </section>
    </OnboardingShell>
  )
}
