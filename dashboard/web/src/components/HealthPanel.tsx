import { useState } from 'react'
import type { BackendError, ErrorsResponse, Health } from '../api'
import { relativeTime, shortTime } from '../format'
import { Badge, Empty, ErrorNote, Panel } from './ui'

interface HealthPanelProps {
  health: Health | null
  healthError: string | null
  errors: ErrorsResponse | null
  errorsError: string | null
  loading: boolean
}

export function HealthPanel({
  health,
  healthError,
  errors,
  errorsError,
  loading,
}: HealthPanelProps): React.JSX.Element {
  const loop = health?.loop
  const lastError = loop?.last_error ?? null
  const errorList = errors?.errors ?? []

  return (
    <div className="space-y-4">
      <Panel title="System status">
        {healthError && !health ? (
          <ErrorNote message={`Could not load health: ${healthError}`} />
        ) : loading && !health ? (
          <Empty>Loading…</Empty>
        ) : (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={health?.status === 'ok' ? 'pos' : 'warn'}>
                {health?.status ?? 'unknown'}
              </Badge>
              {health?.mode && (
                <Badge tone={health.mode === 'live' ? 'neg' : 'pos'}>
                  {health.mode === 'live' ? 'LIVE' : 'DRY'}
                </Badge>
              )}
              <Badge tone={health?.can_trade_now ? 'pos' : 'neutral'}>
                {health?.can_trade_now ? 'can trade now' : 'trading idle'}
              </Badge>
              {health?.model && (
                <span className="ml-auto font-mono text-xs text-muted">{health.model}</span>
              )}
            </div>

            <div className="grid grid-cols-2 gap-4 sm:grid-cols-5">
              <Stat label="Memory size" value={String(health?.memory_size ?? '—')} />
              <Stat
                label="Loop"
                value={loop?.running ? 'running' : 'stopped'}
                tone={loop?.running ? 'pos' : 'muted'}
              />
              <Stat label="Cycles run" value={String(loop?.cycles_run ?? '—')} />
              <Stat label="Last cycle" value={relativeTime(loop?.last_cycle_at)} />
              <Stat
                label="Qwen spend"
                value={health?.cost_usd != null ? `$${health.cost_usd.toFixed(4)}` : '—'}
              />
            </div>

            {lastError && (
              <div>
                <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-muted">
                  Last loop error
                </div>
                <ErrorNote message={lastError} />
              </div>
            )}
          </div>
        )}
      </Panel>

      <Panel
        title="Recent errors"
        right={
          errorList.length > 0 ? (
            <span className="font-mono text-[11px] text-muted">{errorList.length}</span>
          ) : undefined
        }
      >
        {errorsError && !errors ? (
          <ErrorNote message={`Could not load errors: ${errorsError}`} />
        ) : loading && !errors ? (
          <Empty>Loading…</Empty>
        ) : errorList.length === 0 ? (
          <div className="py-6 text-center text-sm text-pos">No errors logged.</div>
        ) : (
          <ul className="space-y-2">
            {errorList.map((e, i) => (
              <ErrorRow key={`${e.ts}-${i}`} error={e} />
            ))}
          </ul>
        )}
      </Panel>
    </div>
  )
}

function Stat({
  label,
  value,
  tone = 'ink',
}: {
  label: string
  value: string
  tone?: 'ink' | 'pos' | 'muted'
}): React.JSX.Element {
  const valueClass = tone === 'pos' ? 'text-pos' : tone === 'muted' ? 'text-muted' : 'text-ink'
  return (
    <div>
      <div className="text-[11px] uppercase tracking-wide text-muted">{label}</div>
      <div className={`font-mono text-lg ${valueClass}`}>{value}</div>
    </div>
  )
}

function ErrorRow({ error: e }: { error: BackendError }): React.JSX.Element {
  const [open, setOpen] = useState(false)
  return (
    <li className="rounded-lg border border-border bg-panel-2/40 p-3">
      <div className="flex flex-wrap items-center gap-2">
        {e.type && <Badge tone="neg">{e.type}</Badge>}
        {e.where && <span className="font-mono text-[11px] text-muted">{e.where}</span>}
        <span className="ml-auto font-mono text-[11px] text-muted">{shortTime(e.ts)}</span>
      </div>
      <p className="mt-1.5 text-xs leading-relaxed text-neg">{e.error || '—'}</p>
      {e.traceback && (
        <div className="mt-2">
          <button
            onClick={() => setOpen((v) => !v)}
            className="text-xs font-medium text-accent hover:underline"
          >
            {open ? 'Hide' : 'Show'} traceback
          </button>
          {open && (
            <pre className="mt-1 overflow-x-auto rounded border border-border bg-bg/60 p-2 font-mono text-[11px] leading-relaxed text-ink/80">
              {e.traceback}
            </pre>
          )}
        </div>
      )}
    </li>
  )
}
