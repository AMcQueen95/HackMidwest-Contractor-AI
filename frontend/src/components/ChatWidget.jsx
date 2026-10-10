import { useMemo } from 'react'
import { getSampleConversation } from '../api'
import { SUGGESTED_QUESTIONS } from '../api/mock/chat'
import { monthName } from '../lib/format'
import DataCard from './DataCard'
import { ChatIcon, CheckIcon, CloseIcon, SendIcon } from './Icons'

// The report narrative is the conversation's first message, matching how the
// API will seed each session's history.
function NarrativeMessage({ narrative, done, month }) {
  if (!narrative.summary) {
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

function Message({ message }) {
  if (message.role === 'user') return <div className="message message-user">{message.text}</div>
  return (
    <div className="message message-assistant">
      {message.statuses?.map((status) => (
        <p key={status} className="message-status">
          <CheckIcon /> {status}
        </p>
      ))}
      {message.text.split('\n\n').map((paragraph) => (
        <p key={paragraph}>{paragraph}</p>
      ))}
      {message.cards?.map((card) => (
        <DataCard key={card.type} {...card} />
      ))}
    </div>
  )
}

export default function ChatWidget({ open, onOpen, onClose, narrative, narrativeDone, month }) {
  const sample = useMemo(getSampleConversation, [])

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
        <button type="button" className="button button-quiet" disabled>
          New conversation
        </button>
        <button type="button" className="icon-button" aria-label="Close chat" onClick={onClose}>
          <CloseIcon />
        </button>
      </header>

      <div className="chat-messages">
        <NarrativeMessage narrative={narrative} done={narrativeDone} month={month} />
        <p className="chat-divider">Example conversation</p>
        {sample.map((message, index) => (
          <Message key={index} message={message} />
        ))}
      </div>

      <footer className="chat-footer">
        <div className="chips">
          {SUGGESTED_QUESTIONS.map((question) => (
            <button key={question} type="button" className="chip" disabled>
              {question}
            </button>
          ))}
        </div>
        <div className="chat-input">
          <input type="text" placeholder="Chat isn't connected yet" disabled />
          <button type="button" className="icon-button" aria-label="Send" disabled>
            <SendIcon />
          </button>
        </div>
      </footer>
    </aside>
  )
}
