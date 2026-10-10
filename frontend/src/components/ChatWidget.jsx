import { useEffect, useRef, useState } from 'react'
import { ask } from '../api'
import { SUGGESTED_QUESTIONS } from '../api/mock/chat'
import { monthName } from '../lib/format'
import DataCard from './DataCard'
import { ChatIcon, CheckIcon, CloseIcon, SendIcon } from './Icons'

// The report narrative is the conversation's first message, matching how the
// API will seed each session's history.
function NarrativeMessage({ narrative, done, month, error }) {
  if (error) return <div className="message message-assistant"><p className="message-error">The written report could not load: {error}</p></div>
  if (!narrative.summary) {
    if (done) return <div className="message message-assistant"><p>Ask a question about your books to get started.</p></div>
    return (
      <div className="message message-assistant">
        <div className="skeleton" aria-label="Writing">
          <span />
          <span />
        </div>
      </div>
    )
  }
  return (
    <div className="message message-assistant">
      <p className="message-kicker">{monthName(month)} report</p>
      <p>{narrative.summary}</p>
      {narrative.issues.length > 0 && (
        <>
          <h4>Issues</h4>
          <ul>
            {narrative.issues.map((issue) => (
              <li key={issue}>{issue}</li>
            ))}
          </ul>
        </>
      )}
      {narrative.recommendations.length > 0 && (
        <>
          <h4>Recommendations</h4>
          <ul>
            {narrative.recommendations.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </>
      )}
      {!done && <span className="cursor" />}
    </div>
  )
}

// Paragraphs are separated by blank lines; lines starting with "- " are list items.
function Paragraph({ text }) {
  const lines = text.split('\n').filter(Boolean)
  const items = lines.filter((line) => line.startsWith('- '))
  if (items.length === 0) return <p>{text}</p>
  const intro = lines.filter((line) => !line.startsWith('- '))
  return (
    <>
      {intro.length > 0 && <p>{intro.join(' ')}</p>}
      <ul>
        {items.map((item) => (
          <li key={item}>{item.slice(2)}</li>
        ))}
      </ul>
    </>
  )
}

function Message({ message }) {
  if (message.role === 'user') return <div className="message message-user">{message.text}</div>
  const waiting = message.pending && !message.text
  return (
    <div className="message message-assistant">
      {message.statuses?.map((status) => (
        <p key={status} className="message-status">
          <CheckIcon /> {status}
        </p>
      ))}
      {waiting && (
        <div className="skeleton" aria-label="Thinking">
          <span />
          <span />
        </div>
      )}
      {message.text
        .trim()
        .split(/\n\s*\n/)
        .filter(Boolean)
        .map((paragraph) => (
          <Paragraph key={paragraph} text={paragraph} />
        ))}
      {message.error && <p className="message-error">{message.error}</p>}
      {message.cards?.map((card) => (
        <DataCard key={card.type} {...card} />
      ))}
      {message.pending && message.text && <span className="cursor" />}
    </div>
  )
}

export default function ChatWidget({ open, onOpen, onClose, narrative, narrativeDone, narrativeError,
  month, datasetRevision, available = true, unavailableMessage }) {
  const [messages, setMessages] = useState([])
  const [sessionId, setSessionId] = useState(null)
  const [input, setInput] = useState('')
  const busy = messages.at(-1)?.pending ?? false
  const scroller = useRef(null)
  const controller = useRef(null)

  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight })
  }, [messages])

  // A new month means a new report, so start a fresh conversation seeded with it.
  useEffect(() => {
    reset()
    return () => controller.current?.abort()
  }, [month, datasetRevision])

  function reset() {
    controller.current?.abort()
    setMessages([])
    setSessionId(null)
    setInput('')
  }

  function updateLast(change) {
    setMessages((list) => list.length ? [...list.slice(0, -1), change(list.at(-1))] : list)
  }

  async function send(question) {
    question = question.trim()
    if (!question || busy || !available) return
    setInput('')
    setMessages((list) => [
      ...list,
      { role: 'user', text: question },
      { role: 'assistant', text: '', statuses: [], cards: [], pending: true },
    ])
    const requestController = new AbortController()
    controller.current = requestController
    const onEvent = (event) => {
      if (requestController.signal.aborted) return
      if (event.type === 'session') setSessionId(event.session_id)
      if (event.type === 'status') updateLast((m) => ({ ...m, statuses: [...m.statuses, event.text] }))
      if (event.type === 'text') updateLast((m) => ({ ...m, text: m.text + event.text }))
      if (event.type === 'text_reset') updateLast((m) => ({ ...m, text: '' }))
      if (event.type === 'card') updateLast((m) => ({ ...m, cards: [...m.cards, event.card] }))
      if (event.type === 'error') updateLast((m) => ({ ...m, error: event.message }))
    }
    try {
      await ask(question, { sessionId, month }, onEvent, requestController.signal)
    } catch (error) {
      if (!requestController.signal.aborted) updateLast((m) => ({ ...m, error: error.message }))
    }
    if (!requestController.signal.aborted) updateLast((m) => ({ ...m, pending: false }))
  }

  if (!open) {
    return (
      <button type="button" className="chat-bubble" onClick={onOpen}>
        <ChatIcon />
        Ask your CFO
      </button>
    )
  }

  return (
    <aside className="chat" aria-label="Ask your CFO">
      <header className="chat-header">
        <h2>Ask your CFO</h2>
        <button
          type="button"
          className="button button-quiet"
          onClick={reset}
          disabled={messages.length === 0}
        >
          New conversation
        </button>
        <button type="button" className="icon-button" aria-label="Close chat" onClick={onClose}>
          <CloseIcon />
        </button>
      </header>

      <div className="chat-messages" ref={scroller}>
        {available ? <NarrativeMessage narrative={narrative} done={narrativeDone} month={month} error={narrativeError} />
          : <p>{unavailableMessage || 'AI analysis is not configured. Your financial calculations are still available.'}</p>}
        {messages.map((message, index) => (
          <Message key={index} message={message} />
        ))}
      </div>

      <footer className="chat-footer">
        <div className="chips">
          {SUGGESTED_QUESTIONS.map((question) => (
            <button
              key={question}
              type="button"
              className="chip"
              onClick={() => send(question)}
              disabled={busy || !available}
            >
              {question}
            </button>
          ))}
        </div>
        <form
          className="chat-input"
          onSubmit={(event) => {
            event.preventDefault()
            send(input)
          }}
        >
          <input
            id="chat-question"
            type="text"
            placeholder="Ask about your books"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            disabled={busy || !available}
          />
          <button type="submit" className="icon-button" aria-label="Send" disabled={busy || !available || !input.trim()}>
            <SendIcon />
          </button>
        </form>
      </footer>
    </aside>
  )
}
