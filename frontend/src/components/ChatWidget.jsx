import { ChatIcon, CloseIcon, SendIcon } from './Icons'

// Agent chat will be connected separately. Do not show sample financial claims
// alongside a live report that may contain different uploaded books.
export default function ChatWidget({ open, onOpen, onClose }) {
  if (!open) {
    return (
      <button type="button" className="chat-bubble" onClick={onOpen}>
        <ChatIcon /> Ask your CFO
      </button>
    )
  }
  return (
    <aside className="chat" aria-label="Ask your CFO">
      <header className="chat-header">
        <h2>Ask your CFO</h2>
        <button type="button" className="icon-button" aria-label="Close chat" onClick={onClose}><CloseIcon /></button>
      </header>
      <div className="chat-messages">
        <div className="message message-assistant">
          <p>AI chat is not connected yet. Your report and purchase checks already use your live books.</p>
        </div>
      </div>
      <footer className="chat-footer">
        <div className="chat-input">
          <input type="text" placeholder="Chat isn't connected yet" disabled />
          <button type="button" className="icon-button" aria-label="Send" disabled><SendIcon /></button>
        </div>
      </footer>
    </aside>
  )
}
