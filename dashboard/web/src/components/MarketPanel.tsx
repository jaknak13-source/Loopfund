import type { Market } from '../api'
import { eur, num } from '../format'
import { Badge, Empty, ErrorNote, Panel } from './ui'

interface MarketPanelProps {
  market: Market | null
  error: string | null
  loading: boolean
}

export function MarketPanel({ market, error, loading }: MarketPanelProps): React.JSX.Element {
  const quotes = market?.quotes ?? []
  const watchlistSize = market?.watchlist?.length ?? 0

  return (
    <Panel
      title="Market"
      right={
        market ? (
          <span className="font-mono text-[11px] text-muted">{watchlistSize} watched</span>
        ) : undefined
      }
    >
      {error && !market ? (
        <ErrorNote message={`Could not load market: ${error}`} />
      ) : loading && !market ? (
        <Empty>Loading…</Empty>
      ) : quotes.length === 0 ? (
        <Empty>No quotes available.</Empty>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-[11px] uppercase tracking-wide text-muted">
                <th className="pb-2 font-medium">Asset</th>
                <th className="pb-2 text-right font-medium">Price (EUR)</th>
                <th className="pb-2 text-right font-medium">Native</th>
                <th className="pb-2 text-right font-medium">Ccy</th>
                <th className="pb-2 text-right font-medium">FX → EUR</th>
              </tr>
            </thead>
            <tbody>
              {quotes.map((q, i) => {
                const muted = q.unavailable === true
                const rowClass = muted ? 'opacity-50' : ''
                return (
                  <tr
                    key={`${q.asset}-${i}`}
                    className={`border-t border-border/60 ${rowClass}`}
                  >
                    <td className="py-2 font-medium text-ink">
                      {q.asset || '—'}
                      {muted && (
                        <Badge tone="neutral" className="ml-2">
                          n/a
                        </Badge>
                      )}
                    </td>
                    <td className="py-2 text-right font-mono text-ink">{eur(q.price_eur)}</td>
                    <td className="py-2 text-right font-mono text-muted">
                      {q.price_native != null ? num(q.price_native) : '—'}
                    </td>
                    <td className="py-2 text-right font-mono text-muted">{q.ccy ?? '—'}</td>
                    <td className="py-2 text-right font-mono text-muted">
                      {q.fx_to_eur != null ? num(q.fx_to_eur, 4) : '—'}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  )
}
