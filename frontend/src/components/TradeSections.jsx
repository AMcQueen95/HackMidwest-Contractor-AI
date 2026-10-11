import { money, percent, shortDate } from '../lib/format'
import Section from './Section'

// Every trade section (backend/app/trades) has the same shape: headline numbers,
// a table, a takeaway written in code, and a note, or a "needs data" note instead.
const FORMATS = {
  money,
  percent: (v) => percent(v, 1),
  count: (v) => (v == null ? '—' : v.toLocaleString('en-US')),
  months: (v) => (v == null ? '—' : `${v} months`),
  date: (v) => (v ? shortDate(v) : '—'),
  text: (v) => v ?? '',
}
const show = (value, format) => (FORMATS[format] ?? FORMATS.text)(value)

export function TradeSectionBody({ section, compact = false }) {
  if (section.status === 'needs_data') return <p className="empty">{section.note}</p>
  const { headline, table, takeaway, note } = section
  return (
    <div className="trade-section">
      {headline.length > 0 && (
        <div className="tiles trade-tiles">
          {headline.map((item) => (
            <div className="tile" key={item.label}>
              <h3>{item.label}</h3>
              <p className={`tile-value ${item.tone ? `is-${item.tone}` : ''}`}>{show(item.value, item.format)}</p>
            </div>
          ))}
        </div>
      )}
      {takeaway && <p className="trade-takeaway">{takeaway}</p>}
      {!compact && table.rows.length > 0 && (
        <details className="trade-details">
          <summary>Show the numbers</summary>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  {table.columns.map((column) => (
                    <th key={column.key} className={column.format === 'text' ? '' : 'num'}>
                      {column.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {table.rows.map((row, index) => (
                  <tr key={index}>
                    {table.columns.map((column) => (
                      <td key={column.key} className={column.format === 'text' ? '' : 'num'}>
                        {show(row[column.key], column.format)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}
      {note && !compact && <p className="trade-note">{note}</p>}
    </div>
  )
}

// All trade sections in one flowing layout: cards pack into columns whatever their
// count or height, and the column count follows the screen width.
// One card per trade section, for the dashboard board. The trade's name sits in
// the corner so cards from several trades can mix in one layout.
export function tradeCards(sections = []) {
  return sections
    .filter((section) => section.status !== 'needs_data')
    .map((section) => (
      <Section
        key={`${section.trade}:${section.key}`}
        title={section.title}
        aside={section.trade_name ? `${section.trade_name} · ${section.period}` : section.period}
      >
        <TradeSectionBody section={section} />
      </Section>
    ))
}
