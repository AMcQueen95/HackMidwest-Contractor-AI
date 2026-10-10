import { useState } from 'react'
import { label, money, percent } from '../lib/format'

const COLUMNS = [
  { key: 'job_id', name: 'Job' },
  { key: 'customer', name: 'Customer' },
  { key: 'job_type', name: 'Type', format: label, wide: true },
  { key: 'quoted_revenue', name: 'Quoted price', format: money, num: true, wide: true },
  { key: 'cash_received', name: 'Paid so far', format: money, num: true, wide: true },
  { key: 'total_cost', name: 'Total cost', format: money, num: true, wide: true },
  { key: 'profit', name: 'Profit', format: money, num: true },
  { key: 'margin_percent', name: 'Margin', format: (v) => percent(v, 1), num: true },
]

// job_profitability and losing_jobs
export default function JobTable({ data, compact, emptyText = 'No finished jobs this month.' }) {
  const [sort, setSort] = useState({ key: 'profit', ascending: true })
  if (data.jobs.length === 0) return <p className="empty">{emptyText}</p>

  const columns = compact ? COLUMNS.filter((column) => !column.wide) : COLUMNS
  const jobs = [...data.jobs].sort((a, b) => {
    const order = a[sort.key] > b[sort.key] ? 1 : a[sort.key] < b[sort.key] ? -1 : 0
    return sort.ascending ? order : -order
  })
  const toggle = (key) =>
    setSort((s) => ({ key, ascending: s.key === key ? !s.ascending : true }))

  return (
    <div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              {columns.map((column) => (
                <th
                  key={column.key}
                  className={column.num ? 'num' : ''}
                  aria-sort={
                    sort.key === column.key ? (sort.ascending ? 'ascending' : 'descending') : 'none'
                  }
                >
                  <button type="button" className="sort" onClick={() => toggle(column.key)}>
                    {column.name}
                    <span aria-hidden="true">
                      {sort.key === column.key ? (sort.ascending ? ' ↑' : ' ↓') : ''}
                    </span>
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {jobs.map((job) => (
              <tr key={job.job_id} className={job.profit < 0 ? 'row-losing' : ''}>
                {columns.map((column) => (
                  <td
                    key={column.key}
                    className={`${column.num ? 'num' : ''} ${
                      column.key === 'profit' && job.profit < 0 ? 'is-bad' : ''
                    }`}
                  >
                    {column.format ? column.format(job[column.key]) : job[column.key]}
                    {column.key === 'job_id' && job.profit < 0 && (
                      <span className="pill is-bad">Lost money</span>
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!compact && (
        <p className="footnote">
          Profit here is the quoted price minus materials and labor for that job. Shared costs like
          insurance and office bills are not split across jobs.
        </p>
      )}
    </div>
  )
}
