import { useEffect, useState } from 'react'
import type { Instruction } from '../api'
import { getInstructions, postInstruction } from '../api'
import { relativeTime } from '../format'
import { Badge, Empty, ErrorNote, Panel } from './ui'

const PLACEHOLDER =
  "e.g. 'be more defensive this month', 'don't trade this week', 'analyze NVDA'"

function intentTone(intent: string | null): 'pos' | 'neg' | 'warn' | 'accent' | 'neutral' {
  const i = (intent ?? '').toLowerCase()
  if (i.includes('no_trade') || i.includes('halt')) return 'neg'
  if (i.includes('defensive') || i.includes('cautious')) return 'warn'
  if (i.includes('aggressive') || i.includes('buy')) return 'pos'
  if (i) return 'accent'
  return 'neutral'
}

export function ChatBox(): React.JSX.Element {
  const [text, setText] = useState('')
  const [instructions, setInstructions] = useState<Instruction[]>([])
  const [error, setError] = useState<string | null>(null)
  const [sendError, setSendError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function load(): Promise<void> {
    try {
      const res = await getInstructions()
      setInstructions(res ?? [])
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  useEffect(() => {
    void load()
  }, [])

  async function send(): Promise<void> {
    const trimmed = text.trim()
    if (!trimmed) return
    setBusy(true)
    setSendError(null)
    try {
      await postInstruction(trimmed)
      setText('')
      await load()
    } catch (e) {
      setSendError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  const active = instructions.filter((i) => i.active)
  const inactive = instructions.filter((i) => !i.active)

  return (
    <Panel title="Instructions">
      <div className="space-y-3">
        {(active.length > 0 || inactive.length > 0) && (
          <div className="space-y-1.5">
            {active.map((ins) => (
              <InstructionRow key={String(ins.id)} ins={ins} />
            ))}
            {inactive.length > 0 && (
              <details className="text-xs text-muted">
                <summary className="cursor-pointer">{inactive.length} inactive</summary>
                <div className="mt-1.5 space-y-1.5">
                  {inactive.map((ins) => (
                    <InstructionRow key={String(ins.id)} ins={ins} />
                  ))}
                </div>
              </details>
            )}
          </div>
        )}

        {error && instructions.length === 0 && (
          <ErrorNote message={`Could not load instructions: ${error}`} />
        )}
        {instructions.length === 0 && !error && (
          <Empty>No standing instructions.</Empty>
        )}

        {sendError && <ErrorNote message={`Send failed: ${sendError}`} />}

        <div className="flex gap-2">
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
                e.preventDefault()
                void send()
              }
            }}
            placeholder={PLACEHOLDER}
            rows={2}
            className="min-w-0 flex-1 resize-none rounded-md border border-border bg-panel-2 px-3 py-2 text-sm text-ink outline-none placeholder:text-muted focus:border-accent/50"
          />
          <button
            onClick={() => void send()}
            disabled={busy || !text.trim()}
            className="self-end rounded-md border border-accent/40 bg-accent/15 px-4 py-2 text-sm font-medium text-accent hover:bg-accent/25 disabled:opacity-50"
          >
            {busy ? 'Sending…' : 'Send'}
          </button>
        </div>
      </div>
    </Panel>
  )
}

function InstructionRow({ ins }: { ins: Instruction }): React.JSX.Element {
  return (
    <div
      className={`flex flex-wrap items-center gap-2 rounded-md border px-3 py-2 ${
        ins.active ? 'border-border bg-panel-2/40' : 'border-border/50 bg-transparent opacity-70'
      }`}
    >
      <span className="text-sm text-ink">{ins.text}</span>
      {ins.parsed_intent && <Badge tone={intentTone(ins.parsed_intent)}>{ins.parsed_intent}</Badge>}
      <span className="ml-auto font-mono text-[11px] text-muted">
        {relativeTime(ins.received_at)}
      </span>
    </div>
  )
}
