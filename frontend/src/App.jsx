import { useEffect, useMemo, useState } from 'react'
import { getReport, streamNarrative } from './api'
import { parseNarrative } from './api/mock/narrative'
import AiCaption from './components/AiCaption'
import ChatWidget from './components/ChatWidget'
import ExpenseChanges from './components/ExpenseChanges'
import Header from './components/Header'
import HeadlineTiles from './components/HeadlineTiles'
import InfoTip from './components/InfoTip'
import JobTable from './components/JobTable'
import MarginByJobType from './components/MarginByJobType'
import PurchaseCheck from './components/PurchaseCheck'
import Receivables from './components/Receivables'
import RecurringCharges from './components/RecurringCharges'
import Section from './components/Section'
import TradeSections from './components/TradeSections'
import UploadDialog from './components/UploadDialog'
import { monthName, shortDate } from './lib/format'
import { ThemeContext } from './lib/theme'

const THEME_KEY = 'toolbelt-theme'

// Always light on a first visit; only an explicit choice in the gear menu sticks.
function savedTheme() {
  try {
    return localStorage.getItem(THEME_KEY) === 'dark' ? 'dark' : 'light'
  } catch {
    return 'light'
  }
}

export default function App() {
  const [theme, setTheme] = useState(savedTheme)
  const [month, setMonth] = useState(null)
  const [report, setReport] = useState(null)
  const [refresh, setRefresh] = useState(0)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [narrativeText, setNarrativeText] = useState('')
  const [narrativeDone, setNarrativeDone] = useState(false)
  const [narrativeError, setNarrativeError] = useState('')
  const [chatOpen, setChatOpen] = useState(false)
  const [uploadOpen, setUploadOpen] = useState(false)

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    try {
      localStorage.setItem(THEME_KEY, theme)
    } catch {
      // Private windows can block storage; the theme still applies for this visit.
    }
  }, [theme])

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setError('')
    getReport(month, controller.signal)
      .then((next) => {
        if (!controller.signal.aborted) setReport(next)
      })
      .catch((error) => {
        if (!controller.signal.aborted) setError(error.message)
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
  }, [month, refresh])

  const aiAvailable = report?.agent_status?.available ?? false
  useEffect(() => {
    const controller = new AbortController()
    setNarrativeText('')
    setNarrativeError('')
    setNarrativeDone(!aiAvailable)
    if (report && aiAvailable) {
      streamNarrative(report.month,
        (chunk) => { if (!controller.signal.aborted) setNarrativeText((text) => text + chunk) },
        controller.signal,
        () => { if (!controller.signal.aborted) setNarrativeText('') },
      ).catch((error) => {
        if (!controller.signal.aborted) setNarrativeError(error.message)
      }).finally(() => {
        if (!controller.signal.aborted) setNarrativeDone(true)
      })
    }
    return () => controller.abort()
  }, [report, aiAvailable])

  const narrative = useMemo(() => parseNarrative(narrativeText), [narrativeText])

  const uploaded = () => {
    setUploadOpen(false)
    setReport(null)
    setMonth(null)
    setRefresh((value) => value + 1)
  }

  if (error || !report || loading) {
    return (
      <main className="page">
        <h1>Toolbelt CFO</h1>
        {error ? (
          <>
            <p role="alert" className="is-bad">{error}</p>
            <button className="button" onClick={() => setRefresh((value) => value + 1)}>Try again</button>
          </>
        ) : <p role="status">Loading your books…</p>}
      </main>
    )
  }
  const name = monthName(report.month)

  return (
    <ThemeContext.Provider value={theme}>
      <Header
        report={report}
        month={report.month}
        onMonth={setMonth}
        theme={theme}
        onTheme={setTheme}
        onUpload={() => setUploadOpen(true)}
      />

      <main className="page">
        <h1>
          {name} {report.month.slice(0, 4)}
          <span>How {report.business.name} did</span>
        </h1>

        <HeadlineTiles report={report} />
        {!report.monthly_summary.period_complete && (
          <p className="footnote">Partial reporting month: recorded transactions through {shortDate(report.monthly_summary.period_end)}.</p>
        )}
        <AiCaption available={aiAvailable} narrative={narrative} done={narrativeDone}
          error={narrativeError} message={report.agent_status?.message} onOpenChat={() => setChatOpen(true)} />

        <div className="grid-2">
          <Section
            title="Who owes you"
            info={
              <InfoTip term="Receivables aging">
                Unpaid invoices grouped by how far past the due date they are.
              </InfoTip>
            }
          >
            <Receivables data={report.receivables} />
          </Section>
          <Section
            title="What changed in your costs"
            info={
              <InfoTip term="Expense variance">
                Spending in each category compared with the month before, biggest increase first.
              </InfoTip>
            }
          >
            <ExpenseChanges data={report.expense_changes} />
          </Section>
        </div>

        <Section
          title="Profit by job"
          info={
            <InfoTip term="Job profitability and gross margin">
              Quoted price minus that job's materials and labor. Margin is the share of the quote
              left over.
            </InfoTip>
          }
          aside={`Jobs finished in ${name}`}
        >
          <MarginByJobType data={report.margin_by_job_type} />
          <JobTable data={report.job_profitability} />
        </Section>

        <div className="grid-2">
          <Section
            title="Bills that repeat"
            info={
              <InfoTip term="Recurring charges">
                Vendors you paid in more than one month, such as subscriptions, insurance, and
                payroll.
              </InfoTip>
            }
          >
            <RecurringCharges data={report.recurring_charges} />
          </Section>
          <Section
            title="Can you afford it?"
            info={
              <InfoTip term="Affordability check">
                Compares available cash after a purchase with a reserve of one month of expenses.
              </InfoTip>
            }
          >
            <PurchaseCheck datasetRevision={report.dataset_revision} />
          </Section>
        </div>

        <TradeSections trade={report.trade} sections={report.trade_sections} />

        <p className="page-footer">
          Figures are calculated from your books. AI analysis is available when configured.
        </p>
      </main>

      <ChatWidget
        key={`${report.dataset_revision}:${report.month}`}
        open={chatOpen}
        onOpen={() => setChatOpen(true)}
        onClose={() => setChatOpen(false)}
        narrative={narrative}
        narrativeDone={narrativeDone}
        narrativeError={narrativeError}
        month={report.month}
        suggestions={report.suggested_questions?.length ? report.suggested_questions : undefined}
        datasetRevision={report.dataset_revision}
        available={aiAvailable}
        unavailableMessage={report.agent_status?.message}
      />
      {uploadOpen && <UploadDialog isSample={report.is_sample} onUploaded={uploaded} onClose={() => setUploadOpen(false)} />}
    </ThemeContext.Provider>
  )
}
