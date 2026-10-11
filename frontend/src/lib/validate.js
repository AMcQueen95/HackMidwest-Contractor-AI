const NUMBER = /^-?\d+(\.\d+)?$/

export function parseNumber(text, { label, min, max, example }) {
  const cleaned = String(text ?? '').trim().replace(/[$,%\s]/g, '').replace(/^\((.*)\)$/, '-$1')
  if (cleaned === '') return { error: `Enter ${label}.` }
  if (!NUMBER.test(cleaned)) return { error: `Use numbers only, like ${example}.` }
  const value = Number(cleaned)
  if (!Number.isFinite(value)) return { error: `Use numbers only, like ${example}.` }
  if (min != null && value < min) return { error: `This can't be less than ${min.toLocaleString('en-US')}.` }
  if (max != null && value > max) return { error: `This can't be more than ${max.toLocaleString('en-US')}.` }
  return { value }
}

export function requireText(text, { label, max }) {
  const value = String(text ?? '').trim()
  if (!value) return { error: `Enter ${label}.` }
  if (value.length > max) return { error: `Keep this under ${max} characters.` }
  return { value }
}
