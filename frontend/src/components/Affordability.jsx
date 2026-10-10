import { money } from '../lib/format'
import { AlertIcon, CheckIcon } from './Icons'

function verdict(data) {
  if (data.status !== 'evaluated') {
    return { tone: 'neutral', text: "There isn't a full month of expenses yet to judge this against." }
  }
  if (data.can_afford_now) {
    return {
      tone: 'good',
      text: `Yes. You'd still have ${money(data.available_after_purchase)} available, which covers one month of expenses.`,
    }
  }
  return {
    tone: 'bad',
    text: `Not yet. You'd be ${money(data.shortfall)} short of keeping one month of expenses in reserve.`,
  }
}

function scenarioText(data) {
  const scenario = data.collection_scenario
  if (data.status !== 'evaluated' || scenario.collections <= 0 || data.can_afford_now) return null
  const owed = money(scenario.collections)
  if (scenario.can_afford) {
    return `If customers pay the ${owed} they owe you, you can afford it and keep the reserve.`
  }
  const gap = money(data.reserve_required - scenario.available_after_purchase)
  return `Even if customers pay the ${owed} they owe you, you'd still be ${gap} short.`
}

// affordability
export default function Affordability({ data }) {
  const { tone, text } = verdict(data)
  const scenario = scenarioText(data)
  return (
    <div className="affordability">
      <p className={`verdict is-${tone}`}>
        {tone === 'good' ? <CheckIcon /> : <AlertIcon />}
        <span>{text}</span>
      </p>
      <dl className="ledger">
        <div>
          <dt>Available cash</dt>
          <dd>{money(data.available_cash)}</dd>
        </div>
        <div>
          <dt>Purchase</dt>
          <dd>{money(-data.purchase_amount)}</dd>
        </div>
        <div className="ledger-total">
          <dt>Left after buying</dt>
          <dd>{money(data.available_after_purchase)}</dd>
        </div>
        <div>
          <dt>Reserve to keep (one month of expenses)</dt>
          <dd>{money(data.reserve_required)}</dd>
        </div>
      </dl>
      {scenario && <p className="scenario">{scenario}</p>}
    </div>
  )
}
