import { SparkIcon } from './Icons'

export default function AiCaption({ narrative, done, onOpenChat }) {
  const waiting = !narrative.summary
  return (
    <div className="caption" aria-live="polite" aria-busy={!done}>
      <span className="caption-icon">
        <SparkIcon />
      </span>
      <div className="caption-body">
        <div className="caption-label">Your CFO's read</div>
        {waiting ? (
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
      <button type="button" className="button button-quiet" onClick={onOpenChat} disabled={waiting}>
        See issues and next steps
      </button>
    </div>
  )
}
