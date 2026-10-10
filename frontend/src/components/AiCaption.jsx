import { SparkIcon } from './Icons'

export default function AiCaption({ narrative, done, onOpenChat, available = true, error, message }) {
  if (!available) {
    return (
      <div className="caption">
        <span className="caption-icon"><SparkIcon /></span>
        <div className="caption-body">
          <div className="caption-label">AI analysis</div>
          <p>{message || 'AI analysis is not configured. Your financial calculations are still available.'}</p>
        </div>
      </div>
    )
  }
  const waiting = !narrative.summary
  return (
    <div className="caption" aria-live="polite" aria-busy={!done}>
      <span className="caption-icon">
        <SparkIcon />
      </span>
      <div className="caption-body">
        <div className="caption-label">Your CFO's read</div>
        {error ? <p role="alert" className="is-bad">The written report could not load: {error}</p> : waiting && done ? (
          <p>The AI returned no summary. You can still ask a question in chat.</p>
        ) : waiting ? (
          <div className="skeleton" aria-label="Writing summary">
            <span />
            <span />
          </div>
        ) : (
          <p>
            {narrative.summary}
            {!done && narrative.issues.length === 0 && <span className="cursor" />}
          </p>
        )}
      </div>
      <button type="button" className="button button-quiet" onClick={onOpenChat} disabled={waiting && !done}>
        See issues and next steps
      </button>
    </div>
  )
}
