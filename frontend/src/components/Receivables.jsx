import { money, shortDate } from '../lib/format'

const BUCKETS = [
  ['current', 'Not due yet'],
  ['1_30', '1–30 days late'],
  ['31_60', '31–60 days late'],
  ['61_90', '61–90 days late'],
  ['90_plus', 'Over 90 days late'],
]

// receivables
export default function Receivables({ data, compact }) {
  if (data.total_outstanding === 0) {
    return <p className="empty">Nobody owes you money right now.</p>
  }
  const filled = BUCKETS.filter(([key]) => data.aging[key] > 0)
  return (
    <div className="receivables">
      <p className="lede">
        <strong>{money(data.total_outstanding)}</strong> unpaid, {money(data.overdue_total)} of it
        past due.
      </p>

      <div className="aging-bar" role="img" aria-label="Unpaid invoices by how late they are">
        {filled.map(([key, name]) => (
          <span
            key={key}
            className={`aging-${key}`}
            style={{ flexGrow: data.aging[key] }}
            title={`${name}: ${money(data.aging[key])}`}
          />
        ))}
      </div>
      <ul className="legend">
        {filled.map(([key, name]) => (
          <li key={key}>
            <span className={`swatch aging-${key}`} />
            {name} <strong>{money(data.aging[key])}</strong>
          </li>
        ))}
      </ul>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Customer</th>
              {!compact && <th>Invoice</th>}
              <th>Due</th>
              <th>Late by</th>
              <th className="num">Unpaid</th>
            </tr>
          </thead>
          <tbody>
            {data.invoices.map((invoice) => (
              <tr key={invoice.invoice_id}>
                <td>{invoice.customer}</td>
                {!compact && <td className="muted">{invoice.invoice_id}</td>}
                <td>{shortDate(invoice.due)}</td>
                <td>
                  {invoice.days_overdue > 0 ? (
                    <span className="pill is-bad">{invoice.days_overdue} days</span>
                  ) : (
                    <span className="muted">Not due</span>
                  )}
                </td>
                <td className="num">{money(invoice.outstanding)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
