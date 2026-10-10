import { label, money } from '../lib/format'

// monthly_summary
export default function MonthlySummary({ data }) {
  const categories = Object.entries(data.expenses_by_category).sort((a, b) => b[1] - a[1])
  return (
    <div>
      <dl className="ledger">
        <div>
          <dt>Money in</dt>
          <dd>{money(data.revenue)}</dd>
        </div>
        <div>
          <dt>Money out</dt>
          <dd>{money(-data.expenses)}</dd>
        </div>
        <div className="ledger-total">
          <dt>{data.profit < 0 ? 'Loss' : 'Profit'}</dt>
          <dd className={data.profit < 0 ? 'is-bad' : ''}>{money(data.profit)}</dd>
        </div>
      </dl>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Where the money went</th>
              <th className="num">Amount</th>
            </tr>
          </thead>
          <tbody>
            {categories.map(([category, amount]) => (
              <tr key={category}>
                <td>{label(category)}</td>
                <td className="num">{money(amount)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
