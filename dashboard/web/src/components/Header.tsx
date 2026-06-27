import { useState } from 'react'
import type { Health } from '../api'
import { runCycle, startLoop, stopLoop } from '../api'
import { relativeTime } from '../format'
import { Badge } from './ui'

interface HeaderProps {
  health: Health | null
  healthError: string | null
  onAfterAction: () => void
}

export function Header({ health, healthError, onAfterAction }: HeaderProps): React.JSX.Element {
  const [cycleBusy, setCycleBusy] = useState(false)
  const [loopBusy, setLoopBusy] = useState(false)
  const [intervalMin, setIntervalMin] = useState(60)
  const [actionError, setActionError] = useState<string | null>(null)

  const running = health?.loop.running ?? false
  const mode = health?.mode

  async function handleRunCycle(): Promise<void> {
    setCycleBusy(true)
    setActionError(null)
    try {
      await runCycle()
      onAfterAction()
    } catch (e) {
      setActionError(e instanceof Error ? e.message : String(e))
    } finally {
      setCycleBusy(false)
    }
  }

  async function handleStart(): Promise<void> {
    setLoopBusy(true)
    setActionError(null)
    try {
      await startLoop(Math.max(1, Math.round(intervalMin)) * 60)
      onAfterAction()
    } catch (e) {
      setActionError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoopBusy(false)
    }
  }

  async function handleStop(): Promise<void> {
    setLoopBusy(true)
    setActionError(null)
    try {
      await stopLoop()
      onAfterAction()
    } catch (e) {
      setActionError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoopBusy(false)
    }
  }

  return (
    <header className="sticky top-0 z-20 border-b border-border bg-bg/90 backdrop-blur">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-4 gap-y-2 px-5 py-3">
        <div className="flex items-center gap-3">
          <div className="h-6 w-6 rounded bg-gradient-to-br from-accent to-pos" />
          <h1 className="text-base font-semibold tracking-tight text-ink">loopfund</h1>
        </div>

        {mode && (
          <Badge tone={mode === 'live' ? 'neg' : 'pos'}>{mode === 'live' ? 'LIVE' : 'DRY'}</Badge>
        )}

        {health?.model && (
          <span className="font-mono text-xs text-muted">{health.model}</span>
        )}

        <div className="flex items-center gap-1.5 text-xs text-muted">
          <span
            className={`h-2 w-2 rounded-full ${running ? 'bg-pos animate-pulse' : 'bg-muted/50'}`}
          />
          {running ? `loop running · ${health?.loop.cycles_run ?? 0} cycles` : 'loop stopped'}
        </div>

        {healthError && (
          <span className="text-xs text-neg">backend offline ({healthError})</span>
        )}

        <div className="ml-auto flex flex-wrap items-center gap-2">
          {health?.loop.last_cycle_at && (
            <span className="hidden font-mono text-[11px] text-muted sm:inline">
              last cycle {relativeTime(health.loop.last_cycle_at)}
            </span>
          )}
          <button
            onClick={() => void handleRunCycle()}
            disabled={cycleBusy}
            className="inline-flex items-center gap-2 rounded-md border border-accent/40 bg-accent/15 px-3 py-1.5 text-sm font-medium text-accent transition hover:bg-accent/25 disabled:opacity-50"
          >
            {cycleBusy && (
              <span className="h-3 w-3 animate-spin rounded-full border-2 border-accent border-t-transparent" />
            )}
            Run one cycle
          </button>

          <div className="flex items-center gap-1 rounded-md border border-border bg-panel px-2 py-1">
            <input
              type="number"
              min={1}
              value={intervalMin}
              onChange={(e) => setIntervalMin(Number(e.target.value))}
              className="w-12 bg-transparent text-right font-mono text-sm text-ink outline-none"
            />
            <span className="text-[11px] text-muted">min</span>
            {running ? (
              <button
                onClick={() => void handleStop()}
                disabled={loopBusy}
                className="ml-1 rounded bg-neg/20 px-2 py-0.5 text-xs font-medium text-neg hover:bg-neg/30 disabled:opacity-50"
              >
                Stop
              </button>
            ) : (
              <button
                onClick={() => void handleStart()}
                disabled={loopBusy}
                className="ml-1 rounded bg-pos/20 px-2 py-0.5 text-xs font-medium text-pos hover:bg-pos/30 disabled:opacity-50"
              >
                Start
              </button>
            )}
          </div>
        </div>
      </div>
      {actionError && (
        <div className="mx-auto max-w-7xl px-5 pb-2">
          <span className="text-xs text-neg">{actionError}</span>
        </div>
      )}
    </header>
  )
}
