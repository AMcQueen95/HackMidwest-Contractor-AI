import { useState } from 'react'
import { money, monthName, percent, shortDate } from '../lib/format'
import CashBreakdown from './CashBreakdown'
import InfoTip from './InfoTip'

// "Up 18% vs August", colored by whether that direction is good news.
function Change({ current, previous, previousMonth, upIsGood, asDollars }) {
  if (previous == null) return <p className="tile-note">No earlier month to compare</p>
  const diff = current - previous
  if (diff === 0) return <p className="tile-note">Same as {monthName(previousMonth)}</p>
  const up = diff > 0
  const amount = asDollars
    ? money(Math.abs(diff))
    : previous === 0
      ? money(Math.abs(diff))
      : percent(Math.abs((diff / previous) * 100))
  return (
    <p className={`tile-note ${up === upIsGood ? 'is-good' : 'is-bad'}`}>
      <span aria-hidden="true">{up ? '▲' : '▼'}</span> {up ? 'Up' : 'Down'} {amount}
      <span className="tile-note-rest"> vs {monthName(previousMonth)}</span>
    </p>
  )
}

export default function HeadlineTiles({ report }) {
  const [cashOpen, setCashOpen] = useState(false)
  const { monthly_summary: now, previous_summary: before, cash_balance: cash, receivables } = report
  const compare = { previousMonth: before?.month }

  return (
    <div className="tiles">
      <div className="tile">
        <h3>
          Money in
          <InfoTip term="Revenue (cash received)">
            Payments that actually arrived this month. Work you billed but haven't been paid for
            is not counted yet.
          </InfoTip>
        </h3>
        <p className="tile-value">{money(now.revenue)}</p>
        <Change {...compare} current={now.revenue} previous={before?.revenue} upIsGood />
      </div>

      <div className="tile">
        <h3>
          Money out
          <InfoTip term="Expenses">
            Everything paid out this month: payroll, materials, fuel, insurance, software, and
            other bills.
          </InfoTip>
        </h3>
        <p className="tile-value">{money(now.expenses)}</p>
        <Change {...compare} current={now.expenses} previous={before?.expenses} upIsGood={false} />
      </div>

      <div className="tile">
        <h3>
          {now.profit < 0 ? 'Loss' : 'Profit'}
          <InfoTip term="Net profit (cash basis)">Money in minus money out for the month.</InfoTip>
        </h3>
        <p className={`tile-value ${now.profit < 0 ? 'is-bad' : ''}`}>{money(now.profit)}</p>
        <Change
          {...compare}
          current={now.profit}
          previous={before?.profit}
          upIsGood
          asDollars
        />
      </div>

      <div className="tile">
        <h3>
          Available cash
          <InfoTip term="Available cash">
            What's in the bank today, minus the amount set aside for taxes.
          </InfoTip>
        </h3>
        <p className="tile-value">{money(cash.available_cash)}</p>
        <p className="tile-note">
          As of {shortDate(cash.as_of_date)} ·{' '}
          <button
            type="button"
            className="link"
            aria-expanded={cashOpen}
            onClick={() => setCashOpen((open) => !open)}
          >
            {cashOpen ? 'Hide breakdown' : 'See breakdown'}
          </button>
        </p>
        {cashOpen && <CashBreakdown data={cash} />}
      </div>

      <div className="tile">
        <h3>
          Owed to you
          <InfoTip term="Accounts receivable">
            Invoices you've sent that customers haven't paid yet.
          </InfoTip>
        </h3>
        <p className="tile-value">{money(receivables.total_outstanding)}</p>
        <p className={`tile-note ${receivables.overdue_total > 0 ? 'is-bad' : ''}`}>
          {receivables.overdue_total > 0
            ? `${money(receivables.overdue_total)} is past due`
            : 'Nothing past due'}
          <span className="tile-note-rest"> · as of {shortDate(receivables.as_of_date)}</span>
        </p>
      </div>
    </div>
  )
}
