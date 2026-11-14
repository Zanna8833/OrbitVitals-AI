import { useCallback, useState } from 'react'
import type { DataSource } from '../data'
import { useAppState } from '../state/AppState'

export interface Mutation<A extends unknown[]> {
  /** Runs the action; resolves to true on success, false on failure (the error is kept in `error`). */
  run: (...args: A) => Promise<boolean>
  busy: boolean
  error: string | null
}

/**
 * Runs a write through the current DataSource, tracks busy/error state and
 * notifies the app so every query reloads. `action` must be referentially stable.
 */
export function useMutation<A extends unknown[]>(action: (dataSource: DataSource, ...args: A) => Promise<unknown>): Mutation<A> {
  const { dataSource, notifyChanged } = useAppState()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const run = useCallback(
    async (...args: A) => {
      setBusy(true)
      setError(null)
      try {
        await action(dataSource, ...args)
        notifyChanged()
        return true
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unexpected error')
        return false
      } finally {
        setBusy(false)
      }
    },
    [action, dataSource, notifyChanged],
  )

  return { run, busy, error }
}
