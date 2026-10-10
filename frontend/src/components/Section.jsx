export default function Section({ title, info, aside, children, className = '' }) {
  return (
    <section className={`card ${className}`}>
      <header className="card-header">
        <h2>
          {title}
          {info}
        </h2>
        {aside && <div className="card-aside">{aside}</div>}
      </header>
      {children}
    </section>
  )
}
