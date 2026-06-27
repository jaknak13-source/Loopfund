import { useState } from 'react'
import type { BlockReason, Decision } from '../api'
import { eur, pct, shortTime } from '../format'
import { toneForAction } from '../lib'
import { Badge, ConfidenceBar, Empty, ErrorNote, Panel } from './ui'

// Human label for the structured why-no-trade reason.
const BLOCK_LABELS: Record<string, string> = {
  risk_veto: 'blocked: risk veto',
  below_floor: 'blocked: low conviction',
  no_structured_output: 'blocked: no model output',
  evidence_insufficient: 'blocked: thin evidence',
  model_no_action: 'chose no action',
}

function blockLabel(reason: BlockReason): string | null {
  if (!reason || reason === 'traded') return null
  return BLOCK_LABELS[reason] ?? `blocked: ${reason}`
}

interface DecisionLogProps {
  decisions: Decision[] | null
  error: string | null
  loading: boolean
}

export function DecisionLog({ decisions, error, loading }: DecisionLogProps): React.JSX.Element {
  return (
    <Panel title="Decision log">
      {error && !decisions ? (
        <ErrorNote message={`Could not load decisions: ${error}`} />
      ) : loading && !decisions ? (
        <Empty>Loading…</Empty>
      ) : !decisions || decisions.length === 0 ? (
        <Empty>No decisions yet. Run a cycle to generate one.</Empty>
      ) : (
        <div className="max-h-[640px] space-y-3 overflow-y-auto pr-1">
          {decisions.map((d) => (
            <DecisionCard key={String(d.id)} decision={d} />
          ))}
        </div>
      )}
    </Panel>
  )
}

function DecisionCard({ decision: d }: { decision: Decision }): React.JSX.Element {
  const [open, setOpen] = useState(false)
  const conf = d.confidence ?? null
  const assumptions = d.key_assumptions ?? []
  const risks = d.known_risks ?? []

  return (
    <article className="rounded-lg border border-border bg-panel-2/40 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={toneForAction(d.action)}>{d.action || 'n/a'}</Badge>
        <span className="font-medium text-ink">{d.asset || '—'}</span>
        {blockLabel(d.block_reason) && <Badge tone="warn">{blockLabel(d.block_reason)}</Badge>}
        {d.mode && <Badge tone={d.mode === 'live' ? 'neg' : 'neutral'}>{d.mode}</Badge>}
        <span className="ml-auto font-mono text-[11px] text-muted">
          {shortTime(d.created_at ?? d.decision_date)}
        </span>
      </div>

      <div className="mt-2 flex flex-wrap gap-x-6 gap-y-1 font-mono text-xs text-muted">
        {d.target_weight != null && <span>target weight {pct(d.target_weight)}</span>}
        {d.size_eur != null && <span>size {eur(d.size_eur)}</span>}
      </div>

      {conf && (
        <div className="mt-2">
          <ConfidenceBar score={conf.score} low={conf.low} high={conf.high} />
          {conf.rationale && (
            <p className="mt-1 text-[11px] italic text-muted">{conf.rationale}</p>
          )}
        </div>
      )}

      {d.reasoning && <p className="mt-2 text-sm leading-relaxed text-ink/90">{d.reasoning}</p>}

      {(assumptions.length > 0 || risks.length > 0) && (
        <div className="mt-2 grid grid-cols-1 gap-3 sm:grid-cols-2">
          {assumptions.length > 0 && (
            <Bullets label="Key assumptions" items={assumptions} />
          )}
          {risks.length > 0 && <Bullets label="Known risks" items={risks} tone="warn" />}
        </div>
      )}

      {d.risk_rebuttal && (
        <div className="mt-2">
          <button
            onClick={() => setOpen((v) => !v)}
            className="text-xs font-medium text-accent hover:underline"
          >
            {open ? 'Hide' : 'Show'} risk rebuttal
          </button>
          {open && (
            <p className="mt-1 rounded border border-border bg-bg/60 p-2 text-xs leading-relaxed text-ink/80">
              {d.risk_rebuttal}
            </p>
          )}
        </div>
      )}
    </article>
  )
}

function Bullets({
  label,
  items,
  tone = 'neutral',
}: {
  label: string
  items: string[]
  tone?: 'neutral' | 'warn'
}): React.JSX.Element {
  return (
    <div>
      <div
        className={`mb-1 text-[10px] font-semibold uppercase tracking-wide ${
          tone === 'warn' ? 'text-amber-400' : 'text-muted'
        }`}
      >
        {label}
      </div>
      <ul className="space-y-0.5 text-xs text-ink/80">
        {items.map((it, i) => (
          <li key={i} className="flex gap-1.5">
            <span className="text-muted">·</span>
            <span>{it}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
