export function cn(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(' ')
}

export type BadgeTone = 'neutral' | 'pos' | 'neg' | 'accent' | 'warn'

// Maps an action / stance string to a badge tone.
export function toneForAction(action: string | null | undefined): BadgeTone {
  const a = (action ?? '').toLowerCase()
  if (a.includes('buy') || a.includes('bull') || a.includes('long') || a.includes('add'))
    return 'pos'
  if (a.includes('sell') || a.includes('bear') || a.includes('short') || a.includes('reduce'))
    return 'neg'
  if (a.includes('hold') || a.includes('neutral') || a.includes('wait')) return 'neutral'
  return 'accent'
}
