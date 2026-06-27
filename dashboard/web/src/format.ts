// Small formatting helpers. All tolerant of null/undefined so the UI never crashes.

export function eur(value: number | null | undefined, fractionDigits = 2): string {
  if (value == null || Number.isNaN(value)) return '—'
  return new Intl.NumberFormat('en-IE', {
    style: 'currency',
    currency: 'EUR',
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  }).format(value)
}

export function num(value: number | null | undefined, fractionDigits = 4): string {
  if (value == null || Number.isNaN(value)) return '—'
  return new Intl.NumberFormat('en-US', {
    minimumFractionDigits: 0,
    maximumFractionDigits: fractionDigits,
  }).format(value)
}

export function pct(value: number | null | undefined, fractionDigits = 1): string {
  if (value == null || Number.isNaN(value)) return '—'
  return `${(value * 100).toFixed(fractionDigits)}%`
}

export function signClass(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value) || value === 0) return 'text-ink'
  return value > 0 ? 'text-pos' : 'text-neg'
}

export function relativeTime(iso: string | null | undefined): string {
  if (!iso) return 'never'
  const t = Date.parse(iso)
  if (Number.isNaN(t)) return iso
  const diff = Date.now() - t
  const s = Math.round(diff / 1000)
  if (s < 0) return 'just now'
  if (s < 60) return `${s}s ago`
  const m = Math.round(s / 60)
  if (m < 60) return `${m}m ago`
  const h = Math.round(m / 60)
  if (h < 24) return `${h}h ago`
  const d = Math.round(h / 24)
  return `${d}d ago`
}

export function shortTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  const t = Date.parse(iso)
  if (Number.isNaN(t)) return iso
  return new Date(t).toLocaleString('en-GB', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

// confidence can arrive as a bare number or a {score,...} object
export function confScore(c: number | { score?: number } | null | undefined): number | null {
  if (c == null) return null
  if (typeof c === 'number') return c
  if (typeof c.score === 'number') return c.score
  return null
}
