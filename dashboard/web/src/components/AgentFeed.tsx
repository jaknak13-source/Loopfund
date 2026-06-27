import type { Agent } from '../api'
import { confScore, relativeTime } from '../format'
import { toneForAction } from '../lib'
import { Badge, ConfidenceBar, Empty, ErrorNote, Panel } from './ui'

interface AgentFeedProps {
  agents: Agent[] | null
  error: string | null
  loading: boolean
}

export function AgentFeed({ agents, error, loading }: AgentFeedProps): React.JSX.Element {
  return (
    <Panel title="Agent activity">
      {error && !agents ? (
        <ErrorNote message={`Could not load agents: ${error}`} />
      ) : loading && !agents ? (
        <Empty>Loading…</Empty>
      ) : !agents || agents.length === 0 ? (
        <Empty>No agent activity yet.</Empty>
      ) : (
        <ul className="space-y-2">
          {agents.map((a, i) => {
            const score = confScore(a.confidence)
            return (
              <li
                key={`${a.agent}-${i}`}
                className="rounded-lg border border-border bg-panel-2/40 p-3"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium text-ink">{a.agent}</span>
                  {a.stance && <Badge tone={toneForAction(a.stance)}>{a.stance}</Badge>}
                  <span className="ml-auto font-mono text-[11px] text-muted">
                    {relativeTime(a.at)}
                  </span>
                </div>
                {a.last_topic && (
                  <p className="mt-1 text-xs text-ink/80">{a.last_topic}</p>
                )}
                {score != null && (
                  <div className="mt-2">
                    <ConfidenceBar score={score} />
                  </div>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </Panel>
  )
}
