import { money, shortDate } from '../lib/format'

// cash_balance
export default function CashBreakdown({ data }) {
  return (
    <dl className="ledger">
      <div>
        <dt>Starting balance, {shortDate(data.opening_balance_date)}</dt>
        <dd>{money(data.opening_balance)}</dd>
      </div>
      <div>
        <dt>Money in since then</dt>
        <dd>{money(data.cash_in)}</dd>
      </div>
      <div>
        <dt>Money out since then</dt>
        <dd>{money(-data.cash_out)}</dd>
      </div>
      <div className="ledger-total">
        <dt>In the bank, {shortDate(data.as_of_date)}</dt>
        <dd>{money(data.balance)}</dd>
      </div>
      <div>
        <dt>Set aside for taxes</dt>
        <dd>{money(-data.tax_reserve)}</dd>
      </div>
      <div className="ledger-total">
        <dt>Available to spend</dt>
        <dd>{money(data.available_cash)}</dd>
      </div>
    </dl>
  )
}
