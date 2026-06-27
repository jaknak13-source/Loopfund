// Typed client for the loopfund FastAPI backend (base path /api).
// In production the backend serves this app on the same origin. In dev, the
// Vite dev server proxies /api -> http://localhost:8500.

export interface Confidence {
  score: number
  low: number
  high: number
  rationale: string
}

export interface LoopStatus {
  running: boolean
  interval_s: number
  cycles_run: number
  last_cycle_at: string | null
  last_error: string | null
}

export interface Health {
  status: string
  mode: 'dry' | 'live'
  model: string
  backend: string
  memory_size: number
  watchlist: string[]
  loop: LoopStatus
  can_trade_now: boolean
  cost_usd?: number
  backend_needs_key?: boolean
  key_set?: boolean
  time: string
}

export interface Position {
  asset: string
  qty: number
  avg_cost_eur: number
  ccy: string
  current_price_eur?: number | null
  current_price_native?: number | null
  value_eur?: number
  weight_pct?: number
  unrealized_eur?: number
}

export interface PortfolioSnapshot {
  cash_eur: number
  market_value_eur: number
  total_value_eur: number
  realized_pnl_eur: number
  unrealized_pnl_eur: number
  n_positions: number
}

export interface Portfolio {
  snapshot: PortfolioSnapshot
  positions: Position[]
  cash_weight_pct?: number
  invested_pct?: number
  contributed_eur?: number   // total capital put in (initial + top-ups) = cash-only baseline
  vs_cash_eur?: number       // total value minus contributed: gain/loss vs never investing
  vs_cash_pct?: number
}

export type TradeAction =
  | 'buy' | 'sell' | 'trim' | 'add' | 'hold' | 'hedge' | 'no_action'

export type BlockReason =
  | 'traded' | 'risk_veto' | 'below_floor' | 'no_structured_output'
  | 'evidence_insufficient' | 'model_no_action' | null

export interface Decision {
  id: string | number
  decision_date: string
  created_at?: string
  action: TradeAction
  asset: string | null
  target_weight: number | null
  size_eur: number | null
  reasoning: string
  key_assumptions: string[]
  known_risks: string[]
  confidence: Confidence
  contributing_reports: string[]
  risk_rebuttal: string
  mode: string
  human_override: string | null
  block_reason: BlockReason
}

export interface Trade {
  id: string | number
  decision_id: string | number
  placed_at: string
  asset: string
  side: string
  qty: number
  ccy: string
  price_native: number
  fx_rate: number
  fill_price_eur: number
  fees_eur: number
  status: string
  realized_pnl_eur: number
  unrealized_pnl_eur: number
}

export interface Report {
  id: string | number
  agent: string
  cycle_id: string | number
  created_at: string
  topic: string
  assets: string[]
  stance: string
  summary: string
  findings: string[]
  confidence: Confidence
  unverified_claims: string[]
  asset_signals?: Record<string, number>
  model_used: string
}

export type ActivityKind = 'status' | 'thinking' | 'research' | 'decision' | 'tool' | 'error'

export interface ActivityEvent {
  id: string
  ts: string
  cycle_id: string
  agent: string
  kind: ActivityKind
  title: string
  summary: string
  // reason: meta carries kind-specific fields (stance, confidence, action, etc.)
  meta: Record<string, unknown>
}

export interface AgentProgress {
  name: string
  state: 'running' | 'done' | 'error'
  stance?: string
  confidence?: number
  at: string
}

export interface CycleProgress {
  cycle_id: string
  phase: string
  current_agent: string | null
  agents: AgentProgress[]
  loop: string
}

export interface DecisionBlockers {
  blockers: Record<string, number>
  n: number
}

export interface Agent {
  agent: string
  role: string
  description: string
  dynamic: boolean
  schedule: string
  last_topic: string | null
  stance?: string
  confidence?: number
  at: string | null
}

export interface MarketQuote {
  asset: string
  price_native?: number
  ccy?: string
  fx_to_eur?: number
  price_eur: number | null
  unavailable?: boolean
}

export interface Market {
  watchlist: string[]
  quotes: MarketQuote[]
}

export interface BackendError {
  ts: string
  where: string
  type: string
  error: string
  traceback?: string
}

export interface ErrorsResponse {
  errors: BackendError[]
}

export interface MemoryItem {
  id: string | number
  created_at: string
  kind: string
  title: string
  body: string
  assets: string[]
  tags: string[]
  confidence: number | Confidence | null
  outcome: string | null
}

export interface MemoryResponse {
  size: number
  results: MemoryItem[]
}

// reason: backend settings/models/risk_limits are free-form JSON objects.
export type JsonObject = Record<string, unknown>

export interface SettingsResponse {
  settings: JsonObject
  models: JsonObject
  risk_limits: JsonObject
}

export interface SettingsUpdateResponse {
  updated: string
  value: unknown
}

export type SettingsName = 'settings' | 'models' | 'risk_limits'

export interface Instruction {
  id: string | number
  received_at: string
  text: string
  parsed_intent: string | null
  active: boolean
}

export interface CalibrationBenchmark {
  available: boolean
  since?: string
  strategy_return?: number
  sp500_return?: number
  excess_return?: number
  beating_sp500?: boolean
}

export interface CalibrationAgent {
  n: number
  hit_rate: number | null
}

export interface CalibrationSource {
  domain: string
  n: number
  hit_rate: number | null
}

export interface Calibration {
  benchmark: CalibrationBenchmark
  horizon_days: number
  agents: Record<string, CalibrationAgent>
  top_sources: CalibrationSource[]
  pending_observations: number
  learned_priors: Record<string, number>
}

export interface CycleResult {
  decision?: Decision | null
  portfolio?: Portfolio | null
  // reason: cycle result carries additional engine-defined fields we don't render.
  [key: string]: unknown
}

const BASE = '/api'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`
    try {
      const body = (await res.json()) as { detail?: string }
      if (body?.detail) detail = body.detail
    } catch {
      // ignore non-JSON error bodies
    }
    throw new Error(detail)
  }
  return (await res.json()) as T
}

export function getHealth(): Promise<Health> {
  return request<Health>('/health')
}

export function getPortfolio(): Promise<Portfolio> {
  return request<Portfolio>('/portfolio')
}

export function getDecisions(limit = 30): Promise<Decision[]> {
  return request<Decision[]>(`/decisions?limit=${limit}`)
}

export function getTrades(limit = 50): Promise<Trade[]> {
  return request<Trade[]>(`/trades?limit=${limit}`)
}

export function getReports(limit = 50): Promise<Report[]> {
  return request<Report[]>(`/reports?limit=${limit}`)
}

export function getAgents(): Promise<Agent[]> {
  return request<Agent[]>('/agents')
}

export function getMarket(): Promise<Market> {
  return request<Market>('/market')
}

export function getErrors(limit = 50): Promise<ErrorsResponse> {
  return request<ErrorsResponse>(`/errors?limit=${limit}`)
}

export function searchMemory(q: string, k = 8, kind = ''): Promise<MemoryResponse> {
  const params = new URLSearchParams()
  if (q) params.set('q', q)
  params.set('k', String(k))
  if (kind) params.set('kind', kind)
  return request<MemoryResponse>(`/memory?${params.toString()}`)
}

export function getSettings(): Promise<SettingsResponse> {
  return request<SettingsResponse>('/settings')
}

export function putSettings(
  name: SettingsName,
  patch: JsonObject,
): Promise<SettingsUpdateResponse> {
  return request<SettingsUpdateResponse>('/settings', {
    method: 'PUT',
    body: JSON.stringify({ name, patch }),
  })
}

export function getInstructions(): Promise<Instruction[]> {
  return request<Instruction[]>('/instructions')
}

export function postInstruction(text: string): Promise<Instruction> {
  return request<Instruction>('/instructions', {
    method: 'POST',
    body: JSON.stringify({ text }),
  })
}

export function runCycle(): Promise<CycleResult> {
  return request<CycleResult>('/cycle/run', { method: 'POST' })
}

export function setApiKey(key: string, baseUrl?: string): Promise<{ set: boolean; masked: string }> {
  return request<{ set: boolean; masked: string }>('/apikey', {
    method: 'POST',
    body: JSON.stringify({ key, base_url: baseUrl || null }),
  })
}

export function getCalibration(): Promise<Calibration> {
  return request<Calibration>('/calibration')
}

export interface ActivityFilter {
  agent?: string
  kind?: string
  q?: string
  limit?: number
}

export function getActivity(filter: ActivityFilter = {}): Promise<ActivityEvent[]> {
  const params = new URLSearchParams()
  if (filter.agent) params.set('agent', filter.agent)
  if (filter.kind) params.set('kind', filter.kind)
  if (filter.q) params.set('q', filter.q)
  params.set('limit', String(filter.limit ?? 120))
  return request<ActivityEvent[]>(`/activity?${params.toString()}`)
}

export function getCycleProgress(): Promise<CycleProgress> {
  return request<CycleProgress>('/cycle/progress')
}

export function getDecisionBlockers(): Promise<DecisionBlockers> {
  return request<DecisionBlockers>('/decisions/blockers')
}

export function getLoopStatus(): Promise<LoopStatus> {
  return request<LoopStatus>('/loop/status')
}

export function startLoop(intervalSeconds?: number): Promise<LoopStatus> {
  const body =
    intervalSeconds != null ? JSON.stringify({ interval_seconds: intervalSeconds }) : '{}'
  return request<LoopStatus>('/loop/start', { method: 'POST', body })
}

export function stopLoop(): Promise<LoopStatus> {
  return request<LoopStatus>('/loop/stop', { method: 'POST' })
}
