import type { ReactNode } from 'react'
import { cn } from '../lib'
import type { BadgeTone } from '../lib'

interface PanelProps {
  title?: string
  right?: ReactNode
  children: ReactNode
  className?: string
}

export function Panel({ title, right, children, className }: PanelProps): React.JSX.Element {
  return (
    <section
      className={cn(
        'rounded-xl border border-border bg-panel shadow-sm shadow-black/20',
        className,
      )}
    >
      {(title || right) && (
        <header className="flex items-center justify-between border-b border-border px-4 py-3">
          {title && (
            <h2 className="text-xs font-semibold uppercase tracking-wider text-muted">{title}</h2>
          )}
          {right}
        </header>
      )}
      <div className="p-4">{children}</div>
    </section>
  )
}

const toneClass: Record<BadgeTone, string> = {
  neutral: 'bg-panel-2 text-muted border-border',
  pos: 'bg-pos/10 text-pos border-pos/30',
  neg: 'bg-neg/10 text-neg border-neg/30',
  accent: 'bg-accent/10 text-accent border-accent/30',
  warn: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
}

export function Badge({
  children,
  tone = 'neutral',
  className,
}: {
  children: ReactNode
  tone?: BadgeTone
  className?: string
}): React.JSX.Element {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded border px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide',
        toneClass[tone],
        className,
      )}
    >
      {children}
    </span>
  )
}

// Confidence bar with a low/high band rendered behind the point estimate.
export function ConfidenceBar({
  score,
  low,
  high,
}: {
  score: number | null
  low?: number | null
  high?: number | null
}): React.JSX.Element {
  const clamp = (v: number): number => Math.max(0, Math.min(1, v))
  const s = score == null ? null : clamp(score)
  const lo = low == null ? null : clamp(low)
  const hi = high == null ? null : clamp(high)
  return (
    <div className="flex items-center gap-2">
      <div className="relative h-2 flex-1 overflow-hidden rounded bg-panel-2">
        {lo != null && hi != null && hi >= lo && (
          <div
            className="absolute top-0 h-full bg-accent/20"
            style={{ left: `${lo * 100}%`, width: `${(hi - lo) * 100}%` }}
          />
        )}
        {s != null && (
          <div className="absolute top-0 h-full bg-accent" style={{ width: `${s * 100}%` }} />
        )}
      </div>
      <span className="w-10 text-right font-mono text-xs text-muted">
        {s == null ? '—' : s.toFixed(2)}
      </span>
    </div>
  )
}

export function ErrorNote({ message }: { message: string }): React.JSX.Element {
  return (
    <div className="rounded border border-neg/30 bg-neg/10 px-3 py-2 text-xs text-neg">
      {message}
    </div>
  )
}

export function Empty({ children }: { children: ReactNode }): React.JSX.Element {
  return <div className="py-6 text-center text-sm text-muted">{children}</div>
}
