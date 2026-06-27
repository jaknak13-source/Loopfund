import { useState } from 'react'
import type { MemoryItem } from '../api'
import { searchMemory } from '../api'
import { relativeTime } from '../format'
import { Badge, Empty, ErrorNote, Panel } from './ui'

export function MemoryBrowser(): React.JSX.Element {
  const [q, setQ] = useState('')
  const [kind, setKind] = useState('')
  const [results, setResults] = useState<MemoryItem[] | null>(null)
  const [size, setSize] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function runSearch(): Promise<void> {
    setBusy(true)
    setError(null)
    try {
      const res = await searchMemory(q, 8, kind)
      setResults(res.results ?? [])
      setSize(res.size ?? null)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Panel
      title="Memory"
      right={size != null ? <span className="font-mono text-[11px] text-muted">{size} entries</span> : undefined}
    >
      <form
        onSubmit={(e) => {
          e.preventDefault()
          void runSearch()
        }}
        className="flex flex-wrap gap-2"
      >
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search memory…"
          className="min-w-0 flex-1 rounded-md border border-border bg-panel-2 px-3 py-1.5 text-sm text-ink outline-none placeholder:text-muted focus:border-accent/50"
        />
        <input
          value={kind}
          onChange={(e) => setKind(e.target.value)}
          placeholder="kind"
          className="w-24 rounded-md border border-border bg-panel-2 px-3 py-1.5 text-sm text-ink outline-none placeholder:text-muted focus:border-accent/50"
        />
        <button
          type="submit"
          disabled={busy}
          className="rounded-md border border-accent/40 bg-accent/15 px-3 py-1.5 text-sm font-medium text-accent hover:bg-accent/25 disabled:opacity-50"
        >
          {busy ? 'Searching…' : 'Search'}
        </button>
      </form>

      <div className="mt-3 max-h-80 space-y-2 overflow-y-auto pr-1">
        {error ? (
          <ErrorNote message={`Search failed: ${error}`} />
        ) : results == null ? (
          <Empty>Search the fund's memory by keyword or kind.</Empty>
        ) : results.length === 0 ? (
          <Empty>No matches.</Empty>
        ) : (
          results.map((m) => (
            <article key={String(m.id)} className="rounded-lg border border-border bg-panel-2/40 p-3">
              <div className="flex flex-wrap items-center gap-2">
                {m.kind && <Badge tone="accent">{m.kind}</Badge>}
                <span className="font-medium text-ink">{m.title || '(untitled)'}</span>
                {m.outcome && <Badge tone="neutral">{m.outcome}</Badge>}
                <span className="ml-auto font-mono text-[11px] text-muted">
                  {relativeTime(m.created_at)}
                </span>
              </div>
              {m.body && (
                <p className="mt-1 line-clamp-3 text-xs leading-relaxed text-ink/80">{m.body}</p>
              )}
              {(m.assets?.length ?? 0) > 0 && (
                <div className="mt-1.5 flex flex-wrap gap-1">
                  {m.assets.map((a) => (
                    <span key={a} className="rounded bg-bg/60 px-1.5 py-0.5 font-mono text-[10px] text-muted">
                      {a}
                    </span>
                  ))}
                </div>
              )}
            </article>
          ))
        )}
      </div>
    </Panel>
  )
}
