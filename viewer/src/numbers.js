// Choose precision for a whole column, so filtering and sorting never change it.
export function columnNumberFormat(magnitude, integers = false) {
  if (integers) return { minimumFractionDigits: 0, maximumFractionDigits: 0 }
  if (magnitude > 0 && (magnitude < 1e-6 || magnitude >= 1e12))
    return { notation: 'scientific', minimumFractionDigits: 2, maximumFractionDigits: 2 }
  const digits = magnitude > 0 && magnitude < 0.01
    ? Math.min(8, Math.ceil(-Math.log10(magnitude)) + 2)
    : 2
  return { minimumFractionDigits: digits, maximumFractionDigits: digits }
}

export function formatNumber(value, options) {
  if (value == null || !Number.isFinite(value)) return '—'
  const threshold = 0.5 * 10 ** -options.maximumFractionDigits
  // Don't suggest a small recorded nonzero value is exactly zero.
  if (value !== 0 && Math.abs(value) < threshold && options.notation !== 'scientific')
    return `${value < 0 ? '>−' : '<'}${(2 * threshold).toLocaleString('en-GB', options)}`
  return (Object.is(value, -0) ? 0 : value).toLocaleString('en-GB', options)
}
