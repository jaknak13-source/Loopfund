import type { Calibration, CalibrationAgent, CalibrationSource } from '../api'
import { pct } from '../format'
import { Badge, Empty, ErrorNote, Panel } from './ui'

interface CalibrationPanelProps {
  calibration: Calibration | null
  error: string | null
  loading: boolean
}

// Hit-rate color thresholds: >=0.55 good, <=0.45 bad, else neutral.
function hitRateClass(rate: number | null): string {
  if (rate == null) return 'text-muted'
  if (rate >= 0.55) return 'text-pos'
  if (rate <= 0.45) return 'text-neg'
  return 'text-ink'
}

// Small sample sizes are unreliable, so they render muted.
const SMALL_N = 10

export function CalibrationPanel({
  calibration,
  error,
  loading,
}: CalibrationPanelProps): React.JSX.Element {
  const horizon = calibration?.horizon_days ?? 0
  const benchmark = calibration?.benchmark
  const agentEntries = Object.entries(calibration?.agents ?? {}).sort(
    ([, a], [, b]) => (b.n ?? 0) - (a.n ?? 0),
  )
  const priorEntries = Object.entries(calibration?.learned_priors ?? {})
  const sources = calibration?.top_sources ?? []
  const pending = calibration?.pending_observations ?? 0

  return (
    <Panel title="Performance & Learning">
      {error && !calibration ? (
        <ErrorNote message={`Could not load calibration: ${error}`} />
      ) : loading && !calibration ? (
        <Empty>Loading…</Empty>
      ) : (
        <div className="space-y-5">
          <BenchmarkBlock benchmark={benchmark} />

          <Section title="Agent reliability">
            {agentEntries.length === 0 ? (
              <Empty>{`No matured observations yet — needs ${horizon}d`}</Empty>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-[11px] uppercase tracking-wide text-muted">
                      <th className="pb-2 font-medium">Agent</th>
                      <th className="pb-2 text-right font-medium">Hit rate</th>
                      <th className="pb-2 text-right font-medium">Samples</th>
                    </tr>
                  </thead>
                  <tbody>
                    {agentEntries.map(([name, a]) => (
                      <AgentRow key={name} name={name} agent={a} />
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Section>

          {priorEntries.length > 0 && (
            <Section title="Learned priors">
              <div className="space-y-2">
                {priorEntries.map(([name, value]) => (
                  <PriorBar key={name} name={name} value={value} />
                ))}
              </div>
            </Section>
          )}

          <Section title="Top news sources">
            {sources.length === 0 ? (
              <Empty>No source outcomes yet.</Empty>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-[11px] uppercase tracking-wide text-muted">
                      <th className="pb-2 font-medium">Domain</th>
                      <th className="pb-2 text-right font-medium">Hit rate</th>
                      <th className="pb-2 text-right font-medium">Samples</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sources.map((s, i) => (
                      <SourceRow key={`${s.domain}-${i}`} source={s} />
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Section>

          <div className="border-t border-border/60 pt-3 text-xs text-muted">
            {`Pending observations: ${pending} (mature in ${horizon}d)`}
          </div>
        </div>
      )}
    </Panel>
  )
}

function BenchmarkBlock({
  benchmark,
}: {
  benchmark: Calibration['benchmark'] | undefined
}): React.JSX.Element {
  if (!benchmark?.available) {
    return (
      <div className="rounded-lg border border-border bg-panel-2 px-4 py-3 text-sm text-muted">
        Benchmark starts after first cycle
      </div>
    )
  }

  const beating = benchmark.beating_sp500 === true

  return (
    <div className="rounded-lg border border-border bg-panel-2 px-4 py-3">
      <div className="flex items-center justify-between">
        <span className="text-xs uppercase tracking-wide text-muted">vs. S&amp;P 500</span>
        <Badge tone={beating ? 'pos' : 'neg'}>{beating ? 'Beating SP500' : 'Trailing SP500'}</Badge>
      </div>
      <div className="mt-3 flex flex-wrap items-end gap-x-8 gap-y-3">
        <ReturnMetric label="Strategy" value={benchmark.strategy_return} large />
        <ReturnMetric label="S&P 500" value={benchmark.sp500_return} large />
        <ReturnMetric label="Excess" value={benchmark.excess_return} />
      </div>
      {benchmark.since && (
        <div className="mt-2 text-[11px] text-muted">{`Since ${benchmark.since}`}</div>
      )}
    </div>
  )
}

function returnClass(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value) || value === 0) return 'text-ink'
  return value > 0 ? 'text-pos' : 'text-neg'
}

function ReturnMetric({
  label,
  value,
  large = false,
}: {
  label: string
  value: number | null | undefined
  large?: boolean
}): React.JSX.Element {
  return (
    <div>
      <div className="text-xs uppercase tracking-wide text-muted">{label}</div>
      <div className={`font-mono ${large ? 'text-2xl font-semibold' : 'text-lg'} ${returnClass(value)}`}>
        {pct(value)}
      </div>
    </div>
  )
}

function Section({
  title,
  children,
}: {
  title: string
  children: React.ReactNode
}): React.JSX.Element {
  return (
    <div className="space-y-2">
      <h3 className="text-[11px] font-semibold uppercase tracking-wide text-muted">{title}</h3>
      {children}
    </div>
  )
}

function AgentRow({ name, agent }: { name: string; agent: CalibrationAgent }): React.JSX.Element {
  const n = agent.n ?? 0
  const small = n < SMALL_N
  return (
    <tr className="border-t border-border/60">
      <td className="py-2 font-medium text-ink">{name}</td>
      <td className={`py-2 text-right font-mono ${hitRateClass(agent.hit_rate)}`}>
        {pct(agent.hit_rate)}
      </td>
      <td className={`py-2 text-right font-mono ${small ? 'text-muted/60' : 'text-muted'}`}>{n}</td>
    </tr>
  )
}

function SourceRow({ source }: { source: CalibrationSource }): React.JSX.Element {
  const n = source.n ?? 0
  const small = n < SMALL_N
  return (
    <tr className="border-t border-border/60">
      <td className="py-2 font-medium text-ink">{source.domain}</td>
      <td className={`py-2 text-right font-mono ${hitRateClass(source.hit_rate)}`}>
        {pct(source.hit_rate)}
      </td>
      <td className={`py-2 text-right font-mono ${small ? 'text-muted/60' : 'text-muted'}`}>{n}</td>
    </tr>
  )
}

// Learned priors range ~0.2–2.0 with 1.0 = baseline. Bar scaled against a 2.0 max.
const PRIOR_MAX = 2.0

function PriorBar({ name, value }: { name: string; value: number }): React.JSX.Element {
  const safe = Number.isFinite(value) ? value : 0
  const widthPct = Math.max(0, Math.min(1, safe / PRIOR_MAX)) * 100
  const tone = safe >= 1 ? 'bg-pos' : 'bg-neg'
  return (
    <div className="flex items-center gap-2">
      <span className="w-28 shrink-0 truncate text-xs text-ink">{name}</span>
      <div className="relative h-2 flex-1 overflow-hidden rounded bg-panel-2">
        {/* baseline marker at 1.0 */}
        <div className="absolute top-0 h-full w-px bg-border" style={{ left: `${(1 / PRIOR_MAX) * 100}%` }} />
        <div className={`absolute top-0 h-full ${tone}`} style={{ width: `${widthPct}%` }} />
      </div>
      <span className="w-10 text-right font-mono text-xs text-muted">{safe.toFixed(2)}</span>
    </div>
  )
}
