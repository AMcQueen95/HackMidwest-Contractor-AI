// Plain-English labels carry the accounting term here, for whoever wants it.
export default function InfoTip({ term, children }) {
  return (
    <span className="infotip">
      <button type="button" className="infotip-button" aria-label={`What is this? ${term}`}>
        i
      </button>
      <span className="infotip-bubble" role="tooltip">
        <strong>{term}</strong>
        {children}
      </span>
    </span>
  )
}
