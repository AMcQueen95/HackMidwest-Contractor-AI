import { useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { label, money, moneyShort, monthName, niceTicks, percent } from '../lib/format'
import { useChartColors } from '../lib/theme'

function ChangeTooltip({ active, payload, months }) {
  if (!active || !payload?.length) return null
  const row = payload[0].payload
  return (
    <div className="chart-tooltip">
      <strong>{label(row.category)}</strong>
      <div>
        {months.previous}: {money(row.previous)}
      </div>
      <div>
        {months.current}: {money(row.current)}
      </div>
      <div className="muted">
        {row.change >= 0 ? 'Up' : 'Down'} {money(Math.abs(row.change))}
        {row.change_percent != null && ` (${percent(Math.abs(row.change_percent), 1)})`}
      </div>
    </div>
  )
}

const signed = (value) => (value == null ? '' : `${value > 0 ? '+' : ''}${percent(value)}`)

// expense_changes
export default function ExpenseChanges({ data, compact }) {
  const [view, setView] = useState('chart')
  const colors = useChartColors()
  const months = { previous: monthName(data.previous_month), current: monthName(data.month) }
  const ticks = niceTicks(Math.max(...data.changes.flatMap((row) => [row.previous, row.current])))

  if (!data.previous_period_complete) {
    return (
      <div>
        <p className="empty">No earlier month to compare. Here's what {months.current} cost.</p>
        <div className="table-wrap">
          <table>
            <tbody>
              {data.changes.map((row) => (
                <tr key={row.category}>
                  <td>{label(row.category)}</td>
                  <td className="num">{money(row.current)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    )
  }

  return (
    <div>
      <div className="chart-controls">
        <ul className="legend">
          <li>
            <span className="swatch" style={{ background: colors.previous }} />
            {months.previous}
          </li>
          <li>
            <span className="swatch" style={{ background: colors.current }} />
            {months.current}
          </li>
        </ul>
        <div className="segmented segmented-small" role="group" aria-label="View">
          {['chart', 'table'].map((v) => (
            <button
              key={v}
              type="button"
              className={v === view ? 'is-active' : ''}
              aria-pressed={v === view}
              onClick={() => setView(v)}
            >
              {v === 'chart' ? 'Chart' : 'Table'}
            </button>
          ))}
        </div>
      </div>

      {view === 'chart' ? (
        <ResponsiveContainer width="100%" height={data.changes.length * (compact ? 36 : 44) + 30}>
          <BarChart
            data={data.changes}
            layout="vertical"
            margin={{ top: 0, right: 52, bottom: 0, left: 0 }}
            barGap={2}
            barCategoryGap="22%"
          >
            <CartesianGrid horizontal={false} stroke={colors.grid} />
            <XAxis
              type="number"
              ticks={ticks}
              domain={[0, ticks[ticks.length - 1]]}
              tickFormatter={moneyShort}
              tick={{ fill: colors.text, fontSize: 12 }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              type="category"
              dataKey="category"
              tickFormatter={label}
              tick={{ fill: colors.text, fontSize: 13 }}
              axisLine={false}
              tickLine={false}
              width={78}
            />
            <Tooltip
              content={<ChangeTooltip months={months} />}
              cursor={{ fill: colors.grid, opacity: 0.5 }}
            />
            <Bar
              dataKey="previous"
              name={months.previous}
              fill={colors.previous}
              radius={[0, 4, 4, 0]}
              isAnimationActive={false}
            />
            <Bar
              dataKey="current"
              name={months.current}
              fill={colors.current}
              radius={[0, 4, 4, 0]}
              isAnimationActive={false}
            >
              <LabelList
                dataKey="change_percent"
                position="right"
                formatter={signed}
                fill={colors.text}
                fontSize={12}
                fontWeight={600}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Category</th>
                <th className="num">{months.previous}</th>
                <th className="num">{months.current}</th>
                <th className="num">Change</th>
              </tr>
            </thead>
            <tbody>
              {data.changes.map((row) => (
                <tr key={row.category}>
                  <td>{label(row.category)}</td>
                  <td className="num">{money(row.previous)}</td>
                  <td className="num">{money(row.current)}</td>
                  <td className="num">
                    {money(row.change)}{' '}
                    <span className="muted">({percent(row.change_percent, 1)})</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
