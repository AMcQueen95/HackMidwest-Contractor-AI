import { money, monthName } from '../lib/format'
import Affordability from './Affordability'
import CashBreakdown from './CashBreakdown'
import ExpenseChanges from './ExpenseChanges'
import JobTable from './JobTable'
import MarginByJobType from './MarginByJobType'
import MonthlySummary from './MonthlySummary'
import Receivables from './Receivables'
import RecurringCharges from './RecurringCharges'
import { TradeSectionBody } from './TradeSections'

// One entry per finance function. `card` events from POST /api/ask carry
// {type, data}, where type is the function name.
const CARDS = {
  monthly_summary: { title: (d) => `${monthName(d.month)} at a glance`, Body: MonthlySummary },
  expense_changes: { title: () => 'What changed in your costs', Body: ExpenseChanges },
  recurring_charges: { title: () => 'Bills that repeat', Body: RecurringCharges },
  job_profitability: { title: () => 'Profit by job', Body: JobTable },
  losing_jobs: {
    title: () => 'Jobs that lost money',
    Body: (props) => <JobTable {...props} emptyText="No jobs lost money." />,
  },
  margin_by_job_type: { title: () => 'Profit by type of work', Body: MarginByJobType },
  cash_balance: { title: () => 'Cash on hand', Body: CashBreakdown },
  receivables: { title: () => 'Who owes you', Body: Receivables },
  affordability: { title: (d) => `Can you afford ${money(d.purchase_amount)}?`, Body: Affordability },
}

export default function DataCard({ type, data }) {
  if (type?.startsWith('trade:')) {
    return (
      <div className="data-card">
        <h4>{data.title}</h4>
        <TradeSectionBody section={data} compact />
      </div>
    )
  }
  const card = CARDS[type]
  if (!card) return null
  return (
    <div className="data-card">
      <h4>{card.title(data)}</h4>
      <card.Body data={data} compact />
    </div>
  )
}
