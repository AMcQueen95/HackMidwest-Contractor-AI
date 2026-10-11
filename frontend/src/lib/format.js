const whole = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 })

// $45,070 and −$7,830. Whole dollars everywhere except chart axes.
export function money(value) {
  if (value == null) return '—'
  const rounded = Math.round(value)
  return `${rounded < 0 ? '−' : ''}$${whole.format(Math.abs(rounded))}`
}

// $45k, for chart axes only.
export function moneyShort(value) {
  const abs = Math.abs(value)
  if (abs < 1000) return money(value)
  const k = abs / 1000
  return `${value < 0 ? '−' : ''}$${Number.isInteger(k) ? k : k.toFixed(1)}k`
}

export function percent(value, digits = 0) {
  if (value == null) return '—'
  return `${value < 0 ? '−' : ''}${Math.abs(value).toFixed(digits)}%`
}

export function monthName(month, style = 'long') {
  const [year, m] = month.split('-').map(Number)
  return new Date(year, m - 1, 1).toLocaleString('en-US', { month: style })
}

export function monthLabel(month) {
  return `${monthName(month, 'short')} ${month.slice(0, 4)}`
}

export function shortDate(iso) {
  const [year, m, d] = iso.split('-').map(Number)
  return new Date(year, m - 1, d).toLocaleString('en-US', { month: 'short', day: 'numeric' })
}

const JOB_TYPES = {
  commercial_hvac: 'Commercial HVAC',
  residential_hvac: 'Residential HVAC',
  plumbing: 'Plumbing',
}

// Falls back to title-casing so uploaded books with other values still read well.
export function label(key) {
  return JOB_TYPES[key] ?? key.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase())
}

// Round axis ticks (0, $10k, $20k, $30k) that reach past the largest value.
export function niceTicks(max, count = 3) {
  if (!(max > 0)) return [0]
  const raw = max / count
  const magnitude = 10 ** Math.floor(Math.log10(raw))
  const step = [1, 2, 5, 10].find((m) => m * magnitude >= raw) * magnitude
  const ticks = []
  for (let tick = 0; tick < max + step; tick += step) ticks.push(tick)
  return ticks
}

export function describeCounts({ transactions = 0, invoices = 0, jobs = 0 }) {
  const parts = [
    [transactions, 'transaction'],
    [invoices, 'invoice'],
    [jobs, 'job'],
  ].filter(([count]) => count > 0).map(([count, noun]) => `${count.toLocaleString('en-US')} ${noun}${count === 1 ? '' : 's'}`)
  return parts.length ? parts.join(', ') : 'No records'
}
