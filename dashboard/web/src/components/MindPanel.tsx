import { useMemo, useState } from 'react'
import type { ActivityEvent, ActivityKind, CycleProgress, DecisionBlockers } from '../api'
import { relativeTime } from '../format'
import { cn, toneForAction } from '../lib'
import type { BadgeTone } from '../lib'
import { Badge, ConfidenceBar, Empty, ErrorNote, Panel } from './ui'

interface MindPanelProps {
  activity: ActivityEvent[] | null
  activityError: string | null
  progress: CycleProgress | null
  blockers: DecisionBlockers | null
  loading: boolean
}

const KINDS: ReadonlyArray<{ id: ActivityKind | 'all'; label: string }> = [
  { id: 'all', label: 'All' },
  { id: 'thinking', label: 'Thinking' },
  { id: 'decision', label: 'Decisions' },
  { id: 'research', label: 'Research' },
  { id: 'status', label: 'Status' },
  { id: 'error', label: 'Errors' },
]

const KIND_TONE: Record<ActivityKind, BadgeTone> = {
  thinking: 'accent',
  decision: 'pos',
  research: 'neutral',
  status: 'neutral',
  tool: 'neutral',
  error: 'neg',
}

const BLOCK_LABELS: Record<string, string> = {
  traded: 'traded',
  risk_veto: 'risk veto',
  below_floor: 'low conviction',
  no_structured_output: 'no model output',
  evidence_insufficient: 'thin evidence',
  model_no_action: 'chose no action',
}

export function MindPanel({
  activity,
  activityError,
  progress,
  blockers,
  loading,
}: MindPanelProps): React.JSX.Element {
  const [kind, setKind] = useState<ActivityKind | 'all'>('all')
  const [agent, setAgent] = useState<string>('')
  const [query, setQuery] = useState<string>('')

  const agentsInFeed = useMemo(() => {
    const s = new Set<string>()
    for (const e of activity ?? []) s.add(e.agent)
    return Array.from(s).sort()
  }, [activity])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return (activity ?? []).filter((e) => {
      if (kind !== 'all' && e.kind !== kind) return false
      if (agent && e.agent !== agent) return false
      if (q && !`${e.agent} ${e.title} ${e.summary}`.toLowerCase().includes(q)) return false
      return true
    })
  }, [activity, kind, agent, query])

  return (
    <div className="space-y-4">
      <CycleProgressStrip progress={progress} blockers={blockers} />

      <Panel
        title="Mind — live thinking, research & decisions"
        right={
          <div className="flex items-center gap-2">
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="search…"
              className="w-40 rounded border border-border bg-bg px-2 py-1 text-xs text-ink placeholder:text-muted focus:border-accent focus:outline-none"
            />
            <select
              value={agent}
              onChange={(e) => setAgent(e.target.value)}
              className="rounded border border-border bg-bg px-2 py-1 text-xs text-ink focus:border-accent focus:outline-none"
            >
              <option value="">all agents</option>
              {agentsInFeed.map((a) => (
                <option key={a} value={a}>
                  {a}
                </option>
              ))}
            </select>
          </div>
        }
      >
        <div className="mb-3 flex flex-wrap gap-1">
          {KINDS.map((k) => (
            <button
              key={k.id}
              onClick={() => setKind(k.id)}
              className={cn(
                'rounded-full border px-2.5 py-1 text-[11px] font-medium transition',
                kind === k.id
                  ? 'border-accent/40 bg-accent/10 text-accent'
                  : 'border-border bg-panel-2 text-muted hover:text-ink',
              )}
            >
              {k.label}
            </button>
          ))}
        </div>

        {activityError && !activity ? (
          <ErrorNote message={`Could not load activity: ${activityError}`} />
        ) : loading && !activity ? (
          <Empty>Loading…</Empty>
        ) : filtered.length === 0 ? (
          <Empty>No activity matches. Agents write here as they run.</Empty>
        ) : (
          <div className="max-h-[640px] space-y-1.5 overflow-y-auto pr-1">
            {filtered.map((e) => (
              <ActivityRow key={e.id} event={e} />
            ))}
          </div>
        )}
      </Panel>
    </div>
  )
}

function CycleProgressStrip({
  progress,
  blockers,
}: {
  progress: CycleProgress | null
  blockers: DecisionBlockers | null
}): React.JSX.Element {
  return (
    <Panel
      title="Current cycle"
      right={
        progress?.current_agent ? (
          <span className="flex items-center gap-1.5 text-xs text-accent">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />
            {progress.current_agent} working…
          </span>
        ) : (
          <span className="text-xs text-muted">{progress?.loop ?? 'idle'}</span>
        )
      }
    >
      {!progress || progress.agents.length === 0 ? (
        <Empty>No cycle yet — researching between decision reminders.</Empty>
      ) : (
        <div className="flex flex-wrap gap-1.5">
          {progress.agents.map((a) => (
            <span
              key={a.name}
              title={a.stance ? `${a.stance} (${a.confidence?.toFixed(2) ?? '—'})` : a.state}
              className={cn(
                'inline-flex items-center gap-1.5 rounded border px-2 py-1 text-[11px]',
                a.state === 'running'
                  ? 'border-accent/40 bg-accent/10 text-accent'
                  : a.state === 'error'
                    ? 'border-neg/30 bg-neg/10 text-neg'
                    : 'border-border bg-panel-2 text-ink/80',
              )}
            >
              {a.state === 'running' && (
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />
              )}
              {a.name}
              {a.stance && a.state === 'done' && (
                <span className={cn('font-mono', a.stance === 'bullish' ? 'text-pos' : a.stance === 'bearish' ? 'text-neg' : 'text-muted')}>
                  {a.stance[0].toUpperCase()}
                </span>
              )}
            </span>
          ))}
        </div>
      )}

      {blockers && blockers.n > 0 && (
        <div className="mt-3 border-t border-border pt-3">
          <div className="mb-1.5 text-[10px] font-semibold uppercase tracking-wide text-muted">
            Why trades fire / don&apos;t (last {blockers.n})
          </div>
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(blockers.blockers)
              .sort((a, b) => b[1] - a[1])
              .map(([reason, n]) => (
                <Badge key={reason} tone={reason === 'traded' ? 'pos' : 'warn'}>
                  {BLOCK_LABELS[reason] ?? reason} · {n}
                </Badge>
              ))}
          </div>
        </div>
      )}
    </Panel>
  )
}

function ActivityRow({ event: e }: { event: ActivityEvent }): React.JSX.Element {
  const [open, setOpen] = useState(false)
  const conf = typeof e.meta.confidence === 'number' ? e.meta.confidence : null
  const stance = typeof e.meta.stance === 'string' ? e.meta.stance : null
  const hasDetail = Boolean(e.summary)

  return (
    <article className="rounded-lg border border-border bg-panel-2/40 px-3 py-2">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={KIND_TONE[e.kind]}>{e.kind}</Badge>
        <span className="font-mono text-xs text-muted">{e.agent}</span>
        {stance && <Badge tone={toneForAction(stance)}>{stance}</Badge>}
        <span className="text-sm text-ink/90">{e.title}</span>
        <span className="ml-auto font-mono text-[10px] text-muted">{relativeTime(e.ts)}</span>
      </div>

      {conf != null && (
        <div className="mt-1.5">
          <ConfidenceBar score={conf} />
        </div>
      )}

      {hasDetail && (
        <>
          <button
            onClick={() => setOpen((v) => !v)}
            className="mt-1 text-[11px] font-medium text-accent hover:underline"
          >
            {open ? 'Hide' : 'Show'} detail
          </button>
          {open && (
            <p className="mt-1 whitespace-pre-wrap rounded border border-border bg-bg/60 p-2 text-xs leading-relaxed text-ink/80">
              {e.summary}
            </p>
          )}
        </>
      )}
    </article>
  )
}
