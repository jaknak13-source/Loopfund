import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import type { Portfolio } from '../api'
import { eur, num, signClass } from '../format'
import { Empty, ErrorNote, Panel } from './ui'

interface PortfolioPanelProps {
  portfolio: Portfolio | null
  error: string | null
  loading: boolean
}

const SLICE_COLORS = ['#3b82f6', '#22c55e', '#f59e0b', '#a855f7', '#06b6d4', '#ef4444', '#84cc16']

export function PortfolioPanel({
  portfolio,
  error,
  loading,
}: PortfolioPanelProps): React.JSX.Element {
  const snap = portfolio?.snapshot
  const positions = portfolio?.positions ?? []

  const allocation = positions
    .map((p) => ({
      name: p.asset,
      value: Math.abs((p.qty ?? 0) * (p.avg_cost_eur ?? 0)),
    }))
    .filter((d) => d.value > 0)
  if (snap?.cash_eur && snap.cash_eur > 0) {
    allocation.push({ name: 'Cash', value: snap.cash_eur })
  }

  return (
    <Panel title="Portfolio">
      {error && !portfolio ? (
        <ErrorNote message={`Could not load portfolio: ${error}`} />
      ) : loading && !portfolio ? (
        <Empty>Loading…</Empty>
      ) : (
        <div className="space-y-4">
          <div className="flex flex-wrap items-end gap-x-8 gap-y-3">
            <div>
              <div className="text-xs uppercase tracking-wide text-muted">Total value</div>
              <div className="font-mono text-3xl font-semibold text-ink">
                {eur(snap?.total_value_eur)}
              </div>
            </div>
            <Metric label="Cash" value={eur(snap?.cash_eur)} />
            <Metric label="Market value" value={eur(snap?.market_value_eur)} />
            <Metric
              label="Realized P&L"
              value={eur(snap?.realized_pnl_eur)}
              className={signClass(snap?.realized_pnl_eur)}
            />
            <Metric
              label="Unrealized P&L"
              value={eur(snap?.unrealized_pnl_eur)}
              className={signClass(snap?.unrealized_pnl_eur)}
            />
            {portfolio?.contributed_eur != null && (
              <Metric
                label="Contributed (cash-only)"
                value={eur(portfolio.contributed_eur)}
              />
            )}
            {portfolio?.vs_cash_eur != null && (
              <Metric
                label="vs holding cash"
                value={`${eur(portfolio.vs_cash_eur)}${
                  portfolio.vs_cash_pct != null ? ` (${portfolio.vs_cash_pct > 0 ? '+' : ''}${portfolio.vs_cash_pct.toFixed(2)}%)` : ''
                }`}
                className={signClass(portfolio.vs_cash_eur)}
              />
            )}
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <div className="lg:col-span-2">
              {positions.length === 0 ? (
                <Empty>No open positions.</Empty>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-[11px] uppercase tracking-wide text-muted">
                        <th className="pb-2 font-medium">Asset</th>
                        <th className="pb-2 text-right font-medium">% Portfolio</th>
                        <th className="pb-2 text-right font-medium">Qty</th>
                        <th className="pb-2 text-right font-medium">Avg cost €</th>
                        <th className="pb-2 text-right font-medium">Now €</th>
                        <th className="pb-2 text-right font-medium">uPnL €</th>
                      </tr>
                    </thead>
                    <tbody>
                      {positions.map((p, i) => (
                        <tr key={`${p.asset}-${i}`} className="border-t border-border/60">
                          <td className="py-2 font-medium text-ink">{p.asset}</td>
                          <td className="py-2 text-right font-mono font-semibold text-ink">
                            {p.weight_pct != null ? `${p.weight_pct.toFixed(1)}%` : '—'}
                          </td>
                          <td className="py-2 text-right font-mono text-ink">{num(p.qty)}</td>
                          <td className="py-2 text-right font-mono text-muted">{eur(p.avg_cost_eur)}</td>
                          <td className="py-2 text-right font-mono text-ink">
                            {p.current_price_eur != null ? eur(p.current_price_eur) : '—'}
                          </td>
                          <td className={`py-2 text-right font-mono ${signClass(p.unrealized_eur ?? 0)}`}>
                            {p.unrealized_eur != null ? eur(p.unrealized_eur) : '—'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {allocation.length > 0 && (
              <div className="h-44">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={allocation}
                      dataKey="value"
                      nameKey="name"
                      innerRadius={40}
                      outerRadius={70}
                      paddingAngle={2}
                      stroke="none"
                    >
                      {allocation.map((_, i) => (
                        <Cell key={i} fill={SLICE_COLORS[i % SLICE_COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{
                        background: '#11151c',
                        border: '1px solid #232a36',
                        borderRadius: 8,
                        fontSize: 12,
                      }}
                      formatter={(v, n) => [eur(Number(v)), String(n)]}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        </div>
      )}
    </Panel>
  )
}

function Metric({
  label,
  value,
  className,
}: {
  label: string
  value: string
  className?: string
}): React.JSX.Element {
  return (
    <div>
      <div className="text-xs uppercase tracking-wide text-muted">{label}</div>
      <div className={`font-mono text-lg ${className ?? 'text-ink'}`}>{value}</div>
    </div>
  )
}
