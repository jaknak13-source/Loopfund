import { useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import type { JsonObject, SettingsName, SettingsResponse } from '../api'
import { getHealth, getSettings, putSettings, setApiKey } from '../api'
import { Badge, Empty, ErrorNote, Panel } from './ui'

// Safe nested getter for free-form JSON config objects.
function dig(obj: unknown, path: string[]): unknown {
  let cur: unknown = obj
  for (const key of path) {
    if (cur && typeof cur === 'object' && key in (cur as JsonObject)) {
      cur = (cur as JsonObject)[key]
    } else {
      return undefined
    }
  }
  return cur
}

function asNumber(v: unknown, fallback: number): number {
  return typeof v === 'number' && !Number.isNaN(v) ? v : fallback
}

function asString(v: unknown, fallback: string): string {
  return typeof v === 'string' ? v : fallback
}

function asBool(v: unknown, fallback: boolean): boolean {
  return typeof v === 'boolean' ? v : fallback
}

// Reads a free-form object of ticker -> weight, tolerating non-object / non-number values.
function asWeights(v: unknown): Record<string, number> {
  if (!v || typeof v !== 'object') return {}
  const out: Record<string, number> = {}
  for (const [k, val] of Object.entries(v as JsonObject)) {
    if (typeof val === 'number' && !Number.isNaN(val)) out[k] = val
  }
  return out
}

export function SettingsPanel(): React.JSX.Element {
  const [data, setData] = useState<SettingsResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [savedKey, setSavedKey] = useState<string | null>(null)
  const savedTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  async function load(): Promise<void> {
    try {
      const res = await getSettings()
      setData(res)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
    return () => {
      if (savedTimer.current) clearTimeout(savedTimer.current)
    }
  }, [])

  async function save(key: string, name: SettingsName, patch: JsonObject): Promise<void> {
    setSaving(key)
    setSaveError(null)
    try {
      await putSettings(name, patch)
      await load()
      setSavedKey(key)
      if (savedTimer.current) clearTimeout(savedTimer.current)
      savedTimer.current = setTimeout(() => setSavedKey(null), 2000)
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : String(e))
    } finally {
      setSaving(null)
    }
  }

  if (loading && !data) {
    return (
      <Panel title="Settings">
        <Empty>Loading…</Empty>
      </Panel>
    )
  }
  if (error && !data) {
    return (
      <Panel title="Settings">
        <ErrorNote message={`Could not load settings: ${error}`} />
      </Panel>
    )
  }

  const s = data?.settings
  const rl = data?.risk_limits
  const m = data?.models

  // INVESTMENT & MODE
  const mode = asString(dig(s, ['mode']), 'dry') === 'live' ? 'live' : 'dry'
  const startingCash = asNumber(dig(s, ['portfolio', 'starting_cash']), 0)
  const weeklyTopup = asNumber(dig(s, ['portfolio', 'weekly_topup']), 0)
  const volTarget = asNumber(dig(s, ['portfolio', 'vol_target']), 0.15)
  const reminderHours = asNumber(dig(s, ['decision', 'reminder_hours']), asNumber(dig(s, ['decision', 'interval_hours']), 1))
  const horizonDays = asNumber(dig(s, ['learning', 'horizon_days']), 1)
  const memMax = asNumber(dig(s, ['memory', 'max_entries']), 1000)
  const researchInterval = asNumber(dig(s, ['loops', 'research_interval_minutes']), 60)
  const idleMaxDays = asNumber(dig(s, ['loops', 'idle_max_days']), 7)

  // PASSIVE CORE
  const baselineEnabled = asBool(dig(s, ['portfolio', 'baseline', 'enabled']), false)
  const baselineStep = asNumber(dig(s, ['portfolio', 'baseline', 'deploy_step']), 0.1)
  const baselineWeights = asWeights(dig(s, ['portfolio', 'baseline', 'weights']))

  // AGENT CAPABILITIES
  const allowCode = asBool(dig(s, ['agents', 'allow_code_execution']), false)
  const allowWeb = asBool(dig(s, ['agents', 'allow_web']), false)
  const allowMeta = asBool(dig(s, ['agents', 'allow_meta']), false)
  const maxDynAgents = asNumber(dig(s, ['agents', 'max_dynamic_agents']), 0)
  const researchAttempts = asNumber(dig(s, ['agents', 'research_max_attempts']), 1)

  // RISK LIMITS
  const maxAsset = asNumber(dig(rl, ['max_single_asset_weight']), 0.25)
  const maxEtf = asNumber(dig(rl, ['max_etf_weight']), 0.5)
  const maxCrypto = asNumber(dig(rl, ['max_crypto_weight']), 0.2)
  const minCash = asNumber(dig(rl, ['min_cash_buffer']), 0.1)
  const ddSoft = asNumber(dig(rl, ['max_drawdown_soft']), 0.1)
  const ddHard = asNumber(dig(rl, ['max_drawdown_hard']), 0.2)
  const dailyLoss = asNumber(dig(rl, ['daily_loss_limit']), 0.05)
  const stopLoss = asNumber(dig(rl, ['stop_loss_pct']), 0.1)
  const kellyCap = asNumber(dig(rl, ['kelly_fraction_cap']), 0.5)
  const feeFlat = asNumber(dig(rl, ['fees', 'flat_eur']), 0)
  const feeFx = asNumber(dig(rl, ['fees', 'fx_spread_bps']), 0)

  // MODEL
  const modelName = asString(dig(m, ['default', 'model']), '')
  const modelTemp = asNumber(dig(m, ['default', 'temperature']), 0.7)
  const modelMaxTokens = asNumber(dig(m, ['default', 'max_tokens']), 2048)

  const rowProps = (key: string): { busy: boolean; saved: boolean } => ({
    busy: saving === key,
    saved: savedKey === key,
  })

  return (
    <Panel title="Settings">
      <div className="space-y-6">
        {saveError && <ErrorNote message={`Save failed: ${saveError}`} />}

        <ApiKeySection />

        <Section title="Investment & mode">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <span className="text-sm text-ink">Trading mode</span>
              {mode === 'live' ? (
                <Badge tone="neg">live — real orders</Badge>
              ) : (
                <Badge tone="neutral">dry run</Badge>
              )}
            </div>
            <div className="flex items-center gap-2">
              <ModeToggle
                {...rowProps('mode')}
                mode={mode}
                onSave={(v) => save('mode', 'settings', { mode: v })}
              />
            </div>
          </div>
          {mode === 'live' && (
            <p className="text-[11px] text-amber-400">
              Live mode places real orders. Switch back to dry to simulate only.
            </p>
          )}
          <NumberRow
            key={`startingCash-${startingCash}`}
            label="Starting cash (EUR)"
            value={startingCash}
            min={0}
            step={100}
            {...rowProps('startingCash')}
            onSave={(v) => save('startingCash', 'settings', { portfolio: { starting_cash: v } })}
          />
          <NumberRow
            key={`weeklyTopup-${weeklyTopup}`}
            label="Weekly top-up (EUR)"
            value={weeklyTopup}
            min={0}
            step={10}
            {...rowProps('weeklyTopup')}
            onSave={(v) => save('weeklyTopup', 'settings', { portfolio: { weekly_topup: v } })}
          />
          <SliderRow
            key={`vol-${volTarget}`}
            label="Volatility target"
            value={volTarget}
            min={0.05}
            max={0.4}
            step={0.01}
            {...rowProps('vol')}
            onSave={(v) => save('vol', 'settings', { portfolio: { vol_target: v } })}
          />
          <NumberRow
            key={`reminder-${reminderHours}`}
            label="Reminder interval (hours) — trade-opportunity every X, checkpoint at X/2"
            value={reminderHours}
            min={0.05}
            max={168}
            step={0.25}
            {...rowProps('reminder')}
            onSave={(v) => save('reminder', 'settings', { decision: { reminder_hours: v } })}
          />
          <NumberRow
            key={`horizon-${horizonDays}`}
            label="Learning horizon (days)"
            hint="float ok"
            value={horizonDays}
            min={0}
            step={0.05}
            {...rowProps('horizon')}
            onSave={(v) => save('horizon', 'settings', { learning: { horizon_days: v } })}
          />
          <NumberRow
            key={`memMax-${memMax}`}
            label="Memory max entries"
            value={memMax}
            min={0}
            step={100}
            {...rowProps('memMax')}
            onSave={(v) => save('memMax', 'settings', { memory: { max_entries: v } })}
          />
          <NumberRow
            key={`researchInterval-${researchInterval}`}
            label="Research interval (minutes)"
            value={researchInterval}
            min={0}
            step={5}
            {...rowProps('researchInterval')}
            onSave={(v) =>
              save('researchInterval', 'settings', { loops: { research_interval_minutes: v } })
            }
          />
          <NumberRow
            key={`idleMaxDays-${idleMaxDays}`}
            label="Idle max (days)"
            value={idleMaxDays}
            min={0}
            step={1}
            {...rowProps('idleMaxDays')}
            onSave={(v) => save('idleMaxDays', 'settings', { loops: { idle_max_days: v } })}
          />
        </Section>

        <Section title="Passive core">
          <ToggleRow
            label="Baseline enabled"
            value={baselineEnabled}
            {...rowProps('baselineEnabled')}
            onSave={(v) =>
              save('baselineEnabled', 'settings', { portfolio: { baseline: { enabled: v } } })
            }
          />
          <SliderRow
            key={`baselineStep-${baselineStep}`}
            label="Baseline deploy step"
            value={baselineStep}
            min={0}
            max={0.5}
            step={0.01}
            {...rowProps('baselineStep')}
            onSave={(v) =>
              save('baselineStep', 'settings', { portfolio: { baseline: { deploy_step: v } } })
            }
          />
          <WeightsEditor
            key={`weights-${JSON.stringify(baselineWeights)}`}
            value={baselineWeights}
            {...rowProps('baselineWeights')}
            onSave={(w) =>
              save('baselineWeights', 'settings', { portfolio: { baseline: { weights: w } } })
            }
          />
        </Section>

        <Section title="Agent capabilities">
          <ToggleRow
            label="Allow code execution"
            hint="runs model-written code"
            danger
            value={allowCode}
            {...rowProps('allowCode')}
            onSave={(v) => save('allowCode', 'settings', { agents: { allow_code_execution: v } })}
          />
          <ToggleRow
            label="Allow web access"
            value={allowWeb}
            {...rowProps('allowWeb')}
            onSave={(v) => save('allowWeb', 'settings', { agents: { allow_web: v } })}
          />
          <ToggleRow
            label="Allow meta agents"
            value={allowMeta}
            {...rowProps('allowMeta')}
            onSave={(v) => save('allowMeta', 'settings', { agents: { allow_meta: v } })}
          />
          <NumberRow
            key={`maxDynAgents-${maxDynAgents}`}
            label="Max dynamic agents"
            value={maxDynAgents}
            min={0}
            step={1}
            {...rowProps('maxDynAgents')}
            onSave={(v) => save('maxDynAgents', 'settings', { agents: { max_dynamic_agents: v } })}
          />
          <NumberRow
            key={`researchAttempts-${researchAttempts}`}
            label="Research max attempts"
            value={researchAttempts}
            min={0}
            step={1}
            {...rowProps('researchAttempts')}
            onSave={(v) =>
              save('researchAttempts', 'settings', { agents: { research_max_attempts: v } })
            }
          />
        </Section>

        <Section title="Risk limits">
          <SliderRow
            key={`maxAsset-${maxAsset}`}
            label="Max single-asset weight"
            value={maxAsset}
            min={0}
            max={1}
            step={0.01}
            {...rowProps('maxAsset')}
            onSave={(v) => save('maxAsset', 'risk_limits', { max_single_asset_weight: v })}
          />
          <SliderRow
            key={`maxEtf-${maxEtf}`}
            label="Max ETF weight"
            value={maxEtf}
            min={0}
            max={1}
            step={0.01}
            {...rowProps('maxEtf')}
            onSave={(v) => save('maxEtf', 'risk_limits', { max_etf_weight: v })}
          />
          <SliderRow
            key={`maxCrypto-${maxCrypto}`}
            label="Max crypto weight"
            value={maxCrypto}
            min={0}
            max={1}
            step={0.01}
            {...rowProps('maxCrypto')}
            onSave={(v) => save('maxCrypto', 'risk_limits', { max_crypto_weight: v })}
          />
          <SliderRow
            key={`minCash-${minCash}`}
            label="Min cash buffer"
            value={minCash}
            min={0}
            max={1}
            step={0.01}
            {...rowProps('minCash')}
            onSave={(v) => save('minCash', 'risk_limits', { min_cash_buffer: v })}
          />
          <SliderRow
            key={`ddSoft-${ddSoft}`}
            label="Max drawdown (soft)"
            value={ddSoft}
            min={0}
            max={1}
            step={0.01}
            {...rowProps('ddSoft')}
            onSave={(v) => save('ddSoft', 'risk_limits', { max_drawdown_soft: v })}
          />
          <SliderRow
            key={`ddHard-${ddHard}`}
            label="Max drawdown (hard)"
            value={ddHard}
            min={0}
            max={1}
            step={0.01}
            {...rowProps('ddHard')}
            onSave={(v) => save('ddHard', 'risk_limits', { max_drawdown_hard: v })}
          />
          <SliderRow
            key={`dailyLoss-${dailyLoss}`}
            label="Daily loss limit"
            value={dailyLoss}
            min={0}
            max={1}
            step={0.01}
            {...rowProps('dailyLoss')}
            onSave={(v) => save('dailyLoss', 'risk_limits', { daily_loss_limit: v })}
          />
          <SliderRow
            key={`stopLoss-${stopLoss}`}
            label="Stop loss"
            value={stopLoss}
            min={0}
            max={1}
            step={0.01}
            {...rowProps('stopLoss')}
            onSave={(v) => save('stopLoss', 'risk_limits', { stop_loss_pct: v })}
          />
          <SliderRow
            key={`kellyCap-${kellyCap}`}
            label="Kelly fraction cap"
            value={kellyCap}
            min={0}
            max={1}
            step={0.01}
            {...rowProps('kellyCap')}
            onSave={(v) => save('kellyCap', 'risk_limits', { kelly_fraction_cap: v })}
          />
          <NumberRow
            key={`feeFlat-${feeFlat}`}
            label="Fees: flat (EUR)"
            value={feeFlat}
            min={0}
            step={0.5}
            {...rowProps('feeFlat')}
            onSave={(v) => save('feeFlat', 'risk_limits', { fees: { flat_eur: v } })}
          />
          <NumberRow
            key={`feeFx-${feeFx}`}
            label="Fees: FX spread (bps)"
            value={feeFx}
            min={0}
            step={1}
            {...rowProps('feeFx')}
            onSave={(v) => save('feeFx', 'risk_limits', { fees: { fx_spread_bps: v } })}
          />
        </Section>

        <Section title="Model">
          <ModelRow
            key={`model-${modelName}`}
            label="Default model id"
            value={modelName}
            {...rowProps('model')}
            onSave={(v) => save('model', 'models', { default: { model: v } })}
          />
          <SliderRow
            key={`temp-${modelTemp}`}
            label="Default temperature"
            value={modelTemp}
            min={0}
            max={1}
            step={0.01}
            {...rowProps('temp')}
            onSave={(v) => save('temp', 'models', { default: { temperature: v } })}
          />
          <NumberRow
            key={`maxTokens-${modelMaxTokens}`}
            label="Default max tokens"
            value={modelMaxTokens}
            min={1}
            step={128}
            {...rowProps('maxTokens')}
            onSave={(v) => save('maxTokens', 'models', { default: { max_tokens: v } })}
          />
        </Section>

        <AdvancedSection data={data} saving={saving} savedKey={savedKey} onSave={save} />
      </div>
    </Panel>
  )
}

function ApiKeySection(): React.JSX.Element {
  const [key, setKey] = useState('')
  const [status, setStatus] = useState<'unknown' | 'set' | 'unset'>('unknown')
  const [backend, setBackend] = useState('')
  const [needsKey, setNeedsKey] = useState(true)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)

  useEffect(() => {
    getHealth()
      .then((h) => {
        setBackend(h.backend || '')
        setNeedsKey(h.backend_needs_key !== false)
        setStatus(h.key_set ? 'set' : 'unset')
      })
      .catch(() => setStatus('unknown'))
  }, [])

  async function save(): Promise<void> {
    const k = key.trim()
    if (!k) return
    setBusy(true)
    setMsg(null)
    try {
      const r = await setApiKey(k)
      setStatus('set')
      setKey('')
      setMsg(`Saved (${r.masked}). The fund uses it immediately.`)
    } catch (e) {
      setMsg(e instanceof Error ? e.message : 'failed to save key')
    } finally {
      setBusy(false)
    }
  }

  const label = backend ? `API key — ${backend}` : 'Model API key'
  if (!needsKey) {
    return (
      <Section title={label}>
        <div className="text-sm text-muted">
          The active backend <span className="font-mono text-ink">{backend || 'local'}</span> runs
          locally and needs no API key. Switch the backend in <span className="text-ink">Models</span>{' '}
          (or config/models.yaml) to use a cloud provider.
        </div>
      </Section>
    )
  }
  return (
    <Section title={label}>
      <div className="space-y-2">
        <div className="flex items-center gap-2 text-sm">
          <span className="text-muted">Key for {backend || 'active backend'}:</span>
          {status === 'set' ? (
            <Badge tone="pos">configured</Badge>
          ) : status === 'unset' ? (
            <Badge tone="warn">not set</Badge>
          ) : null}
        </div>
        <div className="flex gap-2">
          <input
            type="password"
            value={key}
            onChange={(e) => setKey(e.target.value)}
            placeholder="paste your API key…"
            className="flex-1 rounded border border-border bg-panel-2 px-3 py-1.5 font-mono text-sm text-ink"
          />
          <button
            onClick={save}
            disabled={busy || !key.trim()}
            className="rounded bg-accent px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
          >
            {busy ? 'Saving…' : 'Save'}
          </button>
        </div>
        {msg && <div className="text-xs text-muted">{msg}</div>}
        <div className="text-xs text-muted">
          Stored server-side in .env (git-ignored), applied immediately, survives restart. Never displayed back.
        </div>
      </div>
    </Section>
  )
}

function Section({ title, children }: { title: string; children: ReactNode }): React.JSX.Element {
  return (
    <div className="space-y-3">
      <h3 className="text-[11px] font-semibold uppercase tracking-wider text-muted">{title}</h3>
      {children}
    </div>
  )
}

function SavedTick({ saved }: { saved: boolean }): React.JSX.Element | null {
  if (!saved) return null
  return <span className="text-[11px] font-medium text-pos">saved</span>
}

function NumberRow({
  label,
  hint,
  value,
  min,
  max,
  step,
  busy,
  saved,
  onSave,
}: {
  label: string
  hint?: string
  value: number
  min?: number
  max?: number
  step: number
  busy: boolean
  saved: boolean
  onSave: (v: number) => void
}): React.JSX.Element {
  const [v, setV] = useState(value)
  return (
    <div className="flex items-center gap-3">
      <label className="flex-1 text-sm text-ink">
        {label}
        {hint && <span className="ml-2 text-[11px] text-muted">({hint})</span>}
      </label>
      <SavedTick saved={saved} />
      <input
        type="number"
        min={min}
        max={max}
        step={step}
        value={v}
        onChange={(e) => setV(Number(e.target.value))}
        className="w-28 rounded-md border border-border bg-panel-2 px-2 py-1 text-right font-mono text-sm text-ink outline-none focus:border-accent/50"
      />
      <SaveButton busy={busy} disabled={v === value} onClick={() => onSave(v)} />
    </div>
  )
}

function SliderRow({
  label,
  hint,
  value,
  min,
  max,
  step,
  busy,
  saved,
  onSave,
}: {
  label: string
  hint?: string
  value: number
  min: number
  max: number
  step: number
  busy: boolean
  saved: boolean
  onSave: (v: number) => void
}): React.JSX.Element {
  const [v, setV] = useState(value)
  return (
    <div>
      <div className="flex items-center justify-between">
        <label className="text-sm text-ink">
          {label}
          {hint && <span className="ml-2 text-[11px] text-muted">({hint})</span>}
        </label>
        <div className="flex items-center gap-2">
          <SavedTick saved={saved} />
          <span className="font-mono text-sm text-ink">{v.toFixed(2)}</span>
        </div>
      </div>
      <div className="mt-1.5 flex items-center gap-3">
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={v}
          onChange={(e) => setV(Number(e.target.value))}
          className="flex-1 accent-accent"
        />
        <SaveButton busy={busy} disabled={v === value} onClick={() => onSave(v)} />
      </div>
    </div>
  )
}

function ModelRow({
  label,
  value,
  busy,
  saved,
  onSave,
}: {
  label: string
  value: string
  busy: boolean
  saved: boolean
  onSave: (v: string) => void
}): React.JSX.Element {
  const [v, setV] = useState(value)
  return (
    <div className="flex items-center gap-3">
      <label className="text-sm text-ink">{label}</label>
      <SavedTick saved={saved} />
      <input
        type="text"
        value={v}
        onChange={(e) => setV(e.target.value)}
        placeholder="e.g. qwen2.5:7b"
        className="min-w-0 flex-1 rounded-md border border-border bg-panel-2 px-2 py-1 font-mono text-sm text-ink outline-none placeholder:text-muted focus:border-accent/50"
      />
      <SaveButton busy={busy} disabled={v === value} onClick={() => onSave(v)} />
    </div>
  )
}

function ModeToggle({
  mode,
  busy,
  saved,
  onSave,
}: {
  mode: 'dry' | 'live'
  busy: boolean
  saved: boolean
  onSave: (v: 'dry' | 'live') => void
}): React.JSX.Element {
  const next = mode === 'live' ? 'dry' : 'live'
  return (
    <div className="flex items-center gap-2">
      <SavedTick saved={saved} />
      <button
        onClick={() => onSave(next)}
        disabled={busy}
        className="rounded-md border border-border bg-panel-2 px-2.5 py-1 text-xs font-medium text-ink hover:bg-border disabled:opacity-40"
      >
        {busy ? '…' : `Switch to ${next}`}
      </button>
    </div>
  )
}

function ToggleRow({
  label,
  hint,
  danger,
  value,
  busy,
  saved,
  onSave,
}: {
  label: string
  hint?: string
  danger?: boolean
  value: boolean
  busy: boolean
  saved: boolean
  onSave: (v: boolean) => void
}): React.JSX.Element {
  return (
    <div className="flex items-center gap-3">
      <label className="flex-1 text-sm text-ink">
        {label}
        {hint && (
          <span className={danger ? 'ml-2 text-[11px] text-amber-400' : 'ml-2 text-[11px] text-muted'}>
            ({hint})
          </span>
        )}
      </label>
      <SavedTick saved={saved} />
      <Badge tone={value ? 'accent' : 'neutral'}>{value ? 'on' : 'off'}</Badge>
      <button
        onClick={() => onSave(!value)}
        disabled={busy}
        className="rounded-md border border-border bg-panel-2 px-2.5 py-1 text-xs font-medium text-ink hover:bg-border disabled:opacity-40"
      >
        {busy ? '…' : value ? 'Turn off' : 'Turn on'}
      </button>
    </div>
  )
}

// Editable ticker -> weight map. Sends the full map on save so removals propagate.
function WeightsEditor({
  value,
  busy,
  saved,
  onSave,
}: {
  value: Record<string, number>
  busy: boolean
  saved: boolean
  onSave: (w: Record<string, number>) => void
}): React.JSX.Element {
  const [rows, setRows] = useState<Array<{ ticker: string; weight: string }>>(() =>
    Object.entries(value).map(([ticker, weight]) => ({ ticker, weight: String(weight) })),
  )

  function update(idx: number, field: 'ticker' | 'weight', val: string): void {
    setRows((prev) => prev.map((r, i) => (i === idx ? { ...r, [field]: val } : r)))
  }
  function remove(idx: number): void {
    setRows((prev) => prev.filter((_, i) => i !== idx))
  }
  function add(): void {
    setRows((prev) => [...prev, { ticker: '', weight: '0' }])
  }
  function handleSave(): void {
    const out: Record<string, number> = {}
    for (const r of rows) {
      const t = r.ticker.trim()
      if (!t) continue
      const w = Number(r.weight)
      if (Number.isNaN(w)) continue
      out[t] = w
    }
    onSave(out)
  }

  return (
    <div className="rounded-md border border-border bg-panel-2/40 p-3">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-sm text-ink">Baseline weights (ticker → weight)</span>
        <div className="flex items-center gap-2">
          <SavedTick saved={saved} />
          <button
            onClick={add}
            className="rounded-md border border-border bg-panel-2 px-2.5 py-1 text-xs font-medium text-ink hover:bg-border"
          >
            Add
          </button>
        </div>
      </div>
      {rows.length === 0 ? (
        <p className="py-2 text-xs text-muted">No tickers. Use Add to create one.</p>
      ) : (
        <div className="space-y-2">
          {rows.map((r, idx) => (
            <div key={idx} className="flex items-center gap-2">
              <input
                type="text"
                value={r.ticker}
                placeholder="TICKER"
                onChange={(e) => update(idx, 'ticker', e.target.value)}
                className="min-w-0 flex-1 rounded-md border border-border bg-panel-2 px-2 py-1 font-mono text-sm uppercase text-ink outline-none placeholder:text-muted focus:border-accent/50"
              />
              <input
                type="number"
                step={0.01}
                value={r.weight}
                onChange={(e) => update(idx, 'weight', e.target.value)}
                className="w-24 rounded-md border border-border bg-panel-2 px-2 py-1 text-right font-mono text-sm text-ink outline-none focus:border-accent/50"
              />
              <button
                onClick={() => remove(idx)}
                className="rounded-md border border-border bg-panel-2 px-2 py-1 text-xs text-muted hover:bg-border hover:text-ink"
              >
                Remove
              </button>
            </div>
          ))}
        </div>
      )}
      <div className="mt-3 flex justify-end">
        <SaveButton busy={busy} disabled={false} onClick={handleSave} />
      </div>
    </div>
  )
}

// Raw JSON editors so any field is reachable even without a dedicated control.
function AdvancedSection({
  data,
  saving,
  savedKey,
  onSave,
}: {
  data: SettingsResponse | null
  saving: string | null
  savedKey: string | null
  onSave: (key: string, name: SettingsName, patch: JsonObject) => void
}): React.JSX.Element {
  const [open, setOpen] = useState(false)
  return (
    <div className="space-y-3">
      <button
        onClick={() => setOpen((o) => !o)}
        className="text-[11px] font-semibold uppercase tracking-wider text-muted hover:text-ink"
      >
        {open ? '▾' : '▸'} Advanced (raw JSON)
      </button>
      {open && (
        <div className="space-y-4">
          <RawEditor
            name="settings"
            obj={data?.settings}
            busy={saving === 'raw-settings'}
            saved={savedKey === 'raw-settings'}
            onSave={(patch) => onSave('raw-settings', 'settings', patch)}
          />
          <RawEditor
            name="models"
            obj={data?.models}
            busy={saving === 'raw-models'}
            saved={savedKey === 'raw-models'}
            onSave={(patch) => onSave('raw-models', 'models', patch)}
          />
          <RawEditor
            name="risk_limits"
            obj={data?.risk_limits}
            busy={saving === 'raw-risk_limits'}
            saved={savedKey === 'raw-risk_limits'}
            onSave={(patch) => onSave('raw-risk_limits', 'risk_limits', patch)}
          />
        </div>
      )}
    </div>
  )
}

function RawEditor({
  name,
  obj,
  busy,
  saved,
  onSave,
}: {
  name: SettingsName
  obj: JsonObject | undefined
  busy: boolean
  saved: boolean
  onSave: (patch: JsonObject) => void
}): React.JSX.Element {
  const initial = JSON.stringify(obj ?? {}, null, 2)
  const [text, setText] = useState(initial)
  const [parseError, setParseError] = useState<string | null>(null)

  function handleSave(): void {
    let parsed: unknown
    try {
      parsed = JSON.parse(text)
    } catch (e) {
      setParseError(e instanceof Error ? e.message : 'Invalid JSON')
      return
    }
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      setParseError('Top-level value must be a JSON object')
      return
    }
    setParseError(null)
    onSave(parsed as JsonObject)
  }

  return (
    <div className="rounded-md border border-border bg-panel-2/40 p-3">
      <div className="mb-2 flex items-center justify-between">
        <span className="font-mono text-sm text-ink">{name}</span>
        <div className="flex items-center gap-2">
          <SavedTick saved={saved} />
          <SaveButton busy={busy} disabled={false} onClick={handleSave} label="Save raw" />
        </div>
      </div>
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        spellCheck={false}
        rows={Math.min(20, Math.max(6, text.split('\n').length))}
        className="w-full rounded-md border border-border bg-panel px-2 py-1.5 font-mono text-xs text-ink outline-none focus:border-accent/50"
      />
      {parseError && <p className="mt-2 text-[11px] text-neg">JSON error: {parseError}</p>}
    </div>
  )
}

function SaveButton({
  busy,
  disabled,
  onClick,
  label = 'Save',
}: {
  busy: boolean
  disabled: boolean
  onClick: () => void
  label?: string
}): React.JSX.Element {
  return (
    <button
      onClick={onClick}
      disabled={busy || disabled}
      className="rounded-md border border-border bg-panel-2 px-2.5 py-1 text-xs font-medium text-ink hover:bg-border disabled:opacity-40"
    >
      {busy ? '…' : label}
    </button>
  )
}
