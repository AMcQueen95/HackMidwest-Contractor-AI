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
import UploadDialog from './components/UploadDialog'
import { monthName } from './lib/format'
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
  const [narrativeText, setNarrativeText] = useState('')
  const [narrativeDone, setNarrativeDone] = useState(false)
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
    setNarrativeText('')
    setNarrativeDone(false)
    getReport(month).then((next) => {
      if (controller.signal.aborted) return
      setReport(next)
      streamNarrative(
        next.month,
        (chunk) => setNarrativeText((text) => text + chunk),
        controller.signal,
        () => setNarrativeText(''),
      )
        .catch((error) => {
          if (error.name !== 'AbortError') {
            setNarrativeText(`The written report couldn't load: ${error.message}`)
          }
        })
        .finally(() => {
          if (!controller.signal.aborted) setNarrativeDone(true)
        })
    })
    return () => controller.abort()
  }, [month])

  const narrative = useMemo(() => parseNarrative(narrativeText), [narrativeText])

  if (!report) return null
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
        <AiCaption narrative={narrative} done={narrativeDone} onOpenChat={() => setChatOpen(true)} />

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
            <PurchaseCheck />
          </Section>
        </div>

        <p className="page-footer">
          Numbers come straight from the books. The AI explains them and never
          calculates them.
        </p>
      </main>

      <ChatWidget
        open={chatOpen}
        onOpen={() => setChatOpen(true)}
        onClose={() => setChatOpen(false)}
        narrative={narrative}
        narrativeDone={narrativeDone}
        month={report.month}
      />
      {uploadOpen && <UploadDialog onClose={() => setUploadOpen(false)} />}
    </ThemeContext.Provider>
  )
}
