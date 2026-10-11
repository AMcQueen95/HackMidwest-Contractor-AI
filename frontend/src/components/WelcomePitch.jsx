import { CheckIcon } from './Icons'

const POINTS = [
  ['See the month at a glance', 'What came in, what went out, and what is left to spend.'],
  ['Find the jobs that lost money', 'Every job with its quote, its real cost, and its margin.'],
  ['Ask before you buy', 'Check a purchase against your cash, or ask your CFO in plain words.'],
]

const PREVIEW = [
  ['Money in', '$45,070', ''],
  ['Money out', '$52,900', ''],
  ['Loss', '−$7,830', 'is-bad'],
  ['Available cash', '$51,453', ''],
]

export default function WelcomePitch() {
  return (
    <section className="pitch">
      <h1>
        Know where your money went.
        <span>Toolbelt CFO reads your bank activity, invoices, and jobs, then shows what you made, what you spent, and what to fix.</span>
      </h1>

      <ul className="pitch-points">
        {POINTS.map(([title, text]) => (
          <li key={title}>
            <span className="pitch-check">
              <CheckIcon />
            </span>
            <div>
              <strong>{title}</strong>
              <p>{text}</p>
            </div>
          </li>
        ))}
      </ul>

      <figure className="pitch-preview" aria-label="Example dashboard with sample figures">
        <figcaption>
          <span className="dataset-tag">Sample figures</span>
          Ridgeline Heating &amp; Air · September 2026
        </figcaption>
        <div className="pitch-tiles">
          {PREVIEW.map(([name, value, tone]) => (
            <div key={name}>
              <span>{name}</span>
              <strong className={tone}>{value}</strong>
            </div>
          ))}
        </div>
      </figure>
    </section>
  )
}
