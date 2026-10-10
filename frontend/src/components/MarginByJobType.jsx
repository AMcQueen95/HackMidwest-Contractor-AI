import { label, money, percent } from '../lib/format'

// margin_by_job_type
export default function MarginByJobType({ data }) {
  if (data.job_types.length === 0) return <p className="empty">No finished jobs this month.</p>
  return (
    <div className="job-types">
      {data.job_types.map((type) => {
        const losing = type.profit < 0
        const width = Math.min(100, Math.abs(type.margin_percent ?? 0))
        return (
          <div key={type.job_type} className="job-type">
            <div className="job-type-name">{label(type.job_type)}</div>
            <div className={`job-type-margin ${losing ? 'is-bad' : ''}`}>
              {percent(losing ? Math.abs(type.margin_percent) : type.margin_percent)}
              <span> of the quoted price {losing ? 'lost' : 'kept as profit'}</span>
            </div>
            <div className="meter">
              <span className={losing ? 'is-bad' : 'is-good'} style={{ width: `${width}%` }} />
            </div>
            <div className="job-type-detail">
              {money(type.profit)} {losing ? 'lost' : 'profit'} on {type.job_count}{' '}
              {type.job_count === 1 ? 'job' : 'jobs'}
            </div>
          </div>
        )
      })}
    </div>
  )
}
