import { label, money } from '../lib/format'
import { AlertIcon } from './Icons'

// recurring_charges
export default function RecurringCharges({ data, compact }) {
  const charges = compact ? data.charges.slice(0, 5) : data.charges
  return (
    <div>
      {data.potential_duplicate_groups.map((group) => (
        <div key={group.vendors.join()} className="callout">
          <AlertIcon />
          <div>
            <strong>
              {group.vendors.join(' and ')}: {money(group.monthly_total)} this month
            </strong>
            <p>
              You paid more than one {label(group.category).toLowerCase()} vendor. Check whether
              they do the same job. They may not.
            </p>
          </div>
        </div>
      ))}

      {data.charges.length === 0 ? (
        <p className="empty">No bills have repeated month to month yet.</p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Paid to</th>
                <th>For</th>
                <th className="num">This month</th>
                {!compact && <th className="num">Monthly average</th>}
              </tr>
            </thead>
            <tbody>
              {charges.map((charge) => (
                <tr key={charge.vendor}>
                  <td>{charge.vendor}</td>
                  <td className="muted">{label(charge.category)}</td>
                  <td className="num">{money(charge.latest_monthly_amount)}</td>
                  {!compact && <td className="num">{money(charge.average_monthly_amount)}</td>}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {compact && data.charges.length > charges.length && (
        <p className="footnote">And {data.charges.length - charges.length} more in the report.</p>
      )}
    </div>
  )
}
