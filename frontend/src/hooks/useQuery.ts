import { useEffect, useState } from 'react'
import type { DataSource } from '../data'
import { useAppState } from '../state/AppState'

export type QueryState<T> =
  | { status: 'loading'; data: undefined; error: undefined }
  /** `refreshing`: a newer request is in flight; the data shown belongs to the previous one. */
  | { status: 'success'; data: T; error: undefined; refreshing: boolean }
  /** `data` keeps the last successful result, so a failed refresh never blanks the screen. */
  | { status: 'error'; data: T | undefined; error: Error }

export type Query<T> = (dataSource: DataSource) => Promise<T>

interface RequestKey<T> {
  query: Query<T>
  dataSource: DataSource
  revision: number
}

interface Settled<T> {
  key: RequestKey<T>
  data: T | undefined
  error: Error | undefined
}

/**
 * Loads data through the current DataSource and reloads it whenever the app
 * revision changes (after a mutation or an auto-refresh tick).
 *
 * `query` must be referentially stable: define it at module level or wrap it
 * in useCallback with the values it reads.
 *
 * - keeps the previous data while reloading (no skeleton flash);
 * - ignores responses to superseded requests;
 * - on error after a success, keeps the last data and exposes the error.
 */
export function useQuery<T>(query: Query<T>): QueryState<T> {
  const { dataSource, revision } = useAppState()
  const [settled, setSettled] = useState<Settled<T> | null>(null)

  useEffect(() => {
    const key = { query, dataSource, revision }
    let superseded = false
    query(dataSource).then(
      (data) => {
        if (!superseded) setSettled({ key, data, error: undefined })
      },
      (error: unknown) => {
        if (!superseded) setSettled((prev) => ({ key, data: prev?.data, error: toError(error) }))
      },
    )
    return () => {
      superseded = true
    }
  }, [query, dataSource, revision])

  if (!settled) return { status: 'loading', data: undefined, error: undefined }
  if (settled.error) return { status: 'error', data: settled.data, error: settled.error }
  const k = settled.key
  const refreshing = k.query !== query || k.dataSource !== dataSource || k.revision !== revision
  return { status: 'success', data: settled.data as T, error: undefined, refreshing }
}

export function toError(error: unknown): Error {
  return error instanceof Error ? error : new Error(String(error))
}
