import { useCallback, useEffect, useRef, useState } from 'react'

export interface AsyncState<T> {
  data: T | null
  error: string | null
  loading: boolean
  refetch: () => Promise<void>
}

// Fetches `fn` immediately and re-fetches every `intervalMs` (0 = no polling).
// Keeps the last good data on error so the UI never blanks out mid-session.
export function usePolling<T>(
  fn: () => Promise<T>,
  intervalMs: number,
  deps: ReadonlyArray<unknown> = [],
): AsyncState<T> {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState<boolean>(true)
  const fnRef = useRef(fn)
  const mounted = useRef(true)

  useEffect(() => {
    fnRef.current = fn
  }, [fn])

  const refetch = useCallback(async (): Promise<void> => {
    try {
      const result = await fnRef.current()
      if (!mounted.current) return
      setData(result)
      setError(null)
    } catch (e) {
      if (!mounted.current) return
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      if (mounted.current) setLoading(false)
    }
  }, [])

  useEffect(() => {
    mounted.current = true
    void refetch()
    let id = 0
    if (intervalMs > 0) {
      id = window.setInterval(() => void refetch(), intervalMs)
    }
    return () => {
      mounted.current = false
      if (id) window.clearInterval(id)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [intervalMs, refetch, ...deps])

  return { data, error, loading, refetch }
}
