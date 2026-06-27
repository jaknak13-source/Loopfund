import { useCallback, useState } from 'react'
import {
  getActivity,
  getAgents,
  getCalibration,
  getCycleProgress,
  getDecisionBlockers,
  getDecisions,
  getErrors,
  getHealth,
  getMarket,
  getPortfolio,
} from './api'
import { AgentsPanel } from './components/AgentsPanel'
import { CalibrationPanel } from './components/CalibrationPanel'
import { ChatBox } from './components/ChatBox'
import { DecisionLog } from './components/DecisionLog'
import { Header } from './components/Header'
import { HealthPanel } from './components/HealthPanel'
import { MarketPanel } from './components/MarketPanel'
import { MemoryBrowser } from './components/MemoryBrowser'
import { MindPanel } from './components/MindPanel'
import { PortfolioPanel } from './components/PortfolioPanel'
import { SettingsPanel } from './components/SettingsPanel'
import { usePolling } from './hooks/usePolling'
import { cn } from './lib'

const FAST_POLL = 10_000 // health + portfolio
const SLOW_POLL = 30_000 // decisions + market
const CALIBRATION_POLL = 15_000 // performance & learning
const AGENTS_POLL = 15_000
const ERRORS_POLL = 15_000
const MIND_POLL = 3_000 // near-real-time thinking/research feed

type TabId = 'overview' | 'mind' | 'agents' | 'market' | 'memory' | 'settings' | 'health'

const TABS: ReadonlyArray<{ id: TabId; label: string }> = [
  { id: 'overview', label: 'Overview' },
  { id: 'mind', label: 'Mind' },
  { id: 'agents', label: 'Agents' },
  { id: 'market', label: 'Market' },
  { id: 'memory', label: 'Memory' },
  { id: 'settings', label: 'Settings' },
  { id: 'health', label: 'Health' },
]

function App(): React.JSX.Element {
  const [tab, setTab] = useState<TabId>('overview')
  // Bumping this key forces the slower feeds to refetch after a manual cycle run.
  const [refreshKey, setRefreshKey] = useState(0)

  const health = usePolling(getHealth, FAST_POLL)
  const portfolio = usePolling(getPortfolio, FAST_POLL)
  const decisions = usePolling(() => getDecisions(30), SLOW_POLL, [refreshKey])
  const agents = usePolling(getAgents, AGENTS_POLL, [refreshKey])
  const calibration = usePolling(getCalibration, CALIBRATION_POLL, [refreshKey])
  const market = usePolling(getMarket, SLOW_POLL)
  const errors = usePolling(() => getErrors(50), ERRORS_POLL, [refreshKey])
  // Mind tab: poll fast only while the tab is open to keep it near-real-time.
  const mindActive = tab === 'mind'
  const activity = usePolling(() => getActivity({ limit: 150 }), mindActive ? MIND_POLL : 0)
  const progress = usePolling(getCycleProgress, mindActive ? MIND_POLL : 0)
  const blockers = usePolling(getDecisionBlockers, mindActive ? MIND_POLL * 3 : 0)

  const onAfterAction = useCallback((): void => {
    setRefreshKey((k) => k + 1)
    void health.refetch()
    void portfolio.refetch()
  }, [health, portfolio])

  return (
    <div className="flex min-h-full flex-col bg-bg">
      <Header health={health.data} healthError={health.error} onAfterAction={onAfterAction} />

      <nav className="sticky top-[57px] z-10 border-b border-border bg-bg/90 backdrop-blur">
        <div className="mx-auto flex max-w-7xl gap-1 overflow-x-auto px-5">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={cn(
                'relative whitespace-nowrap px-3 py-2.5 text-sm font-medium transition',
                tab === t.id ? 'text-ink' : 'text-muted hover:text-ink',
              )}
            >
              {t.label}
              {tab === t.id && (
                <span className="absolute inset-x-2 -bottom-px h-0.5 rounded-full bg-accent" />
              )}
            </button>
          ))}
        </div>
      </nav>

      <main className="mx-auto w-full max-w-7xl flex-1 space-y-4 px-5 py-5">
        {tab === 'overview' && (
          <>
            <PortfolioPanel
              portfolio={portfolio.data}
              error={portfolio.error}
              loading={portfolio.loading}
            />
            <DecisionLog
              decisions={decisions.data}
              error={decisions.error}
              loading={decisions.loading}
            />
            <CalibrationPanel
              calibration={calibration.data}
              error={calibration.error}
              loading={calibration.loading}
            />
          </>
        )}

        {tab === 'mind' && (
          <MindPanel
            activity={activity.data}
            activityError={activity.error}
            progress={progress.data}
            blockers={blockers.data}
            loading={activity.loading}
          />
        )}

        {tab === 'agents' && (
          <AgentsPanel agents={agents.data} error={agents.error} loading={agents.loading} />
        )}

        {tab === 'market' && (
          <MarketPanel market={market.data} error={market.error} loading={market.loading} />
        )}

        {tab === 'memory' && <MemoryBrowser />}

        {tab === 'settings' && <SettingsPanel />}

        {tab === 'health' && (
          <HealthPanel
            health={health.data}
            healthError={health.error}
            errors={errors.data}
            errorsError={errors.error}
            loading={errors.loading}
          />
        )}
      </main>

      <div className="sticky bottom-0 z-10 border-t border-border bg-bg/90 backdrop-blur">
        <div className="mx-auto w-full max-w-7xl px-5 py-4">
          <ChatBox />
        </div>
      </div>
    </div>
  )
}

export default App
