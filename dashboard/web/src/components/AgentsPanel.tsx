import type { Agent } from '../api'
import { confScore, relativeTime } from '../format'
import { toneForAction } from '../lib'
import { Badge, ConfidenceBar, Empty, ErrorNote, Panel } from './ui'

interface AgentsPanelProps {
  agents: Agent[] | null
  error: string | null
  loading: boolean
}

export function AgentsPanel({ agents, error, loading }: AgentsPanelProps): React.JSX.Element {
  const list = agents ?? []
  const core = list.filter((a) => !a.dynamic)
  const custom = list.filter((a) => a.dynamic)

  return (
    <Panel
      title="Agents"
      right={
        list.length > 0 ? (
          <span className="font-mono text-[11px] text-muted">
            {core.length} core · {custom.length} custom
          </span>
        ) : undefined
      }
    >
      {error && !agents ? (
        <ErrorNote message={`Could not load agents: ${error}`} />
      ) : loading && !agents ? (
        <Empty>Loading…</Empty>
      ) : list.length === 0 ? (
        <Empty>No agents registered.</Empty>
      ) : (
        <div className="space-y-5">
          <AgentGroup label="Core agents" agents={core} />
          {custom.length > 0 && <AgentGroup label="Custom agents" agents={custom} />}
        </div>
      )}
    </Panel>
  )
}

function AgentGroup({ label, agents }: { label: string; agents: Agent[] }): React.JSX.Element | null {
  if (agents.length === 0) return null
  return (
    <div>
      <div className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-muted">
        {label}
      </div>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        {agents.map((a, i) => (
          <AgentCard key={`${a.agent}-${i}`} agent={a} />
        ))}
      </div>
    </div>
  )
}

function AgentCard({ agent: a }: { agent: Agent }): React.JSX.Element {
  const score = confScore(a.confidence)
  return (
    <article className="flex flex-col rounded-lg border border-border bg-panel-2/40 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium text-ink">{a.agent || '—'}</span>
        {a.role && <Badge tone="accent">{a.role}</Badge>}
        {a.dynamic && <Badge tone="warn">custom</Badge>}
        {a.schedule && (
          <span className="ml-auto font-mono text-[11px] text-muted">{a.schedule}</span>
        )}
      </div>

      {a.description && (
        <p className="mt-1.5 text-xs leading-relaxed text-ink/80">{a.description}</p>
      )}

      <div className="mt-3 border-t border-border/60 pt-2">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[10px] font-semibold uppercase tracking-wide text-muted">
            Last activity
          </span>
          {a.stance && <Badge tone={toneForAction(a.stance)}>{a.stance}</Badge>}
          <span className="ml-auto font-mono text-[11px] text-muted">{relativeTime(a.at)}</span>
        </div>
        {a.last_topic ? (
          <p className="mt-1 text-xs text-ink/80">{a.last_topic}</p>
        ) : (
          <p className="mt-1 text-xs italic text-muted">No activity yet.</p>
        )}
        {score != null && (
          <div className="mt-2">
            <ConfidenceBar score={score} />
          </div>
        )}
      </div>
    </article>
  )
}
