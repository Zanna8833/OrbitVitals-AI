import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { config } from '../config'
import { createDataSource, DEFAULT_SCENARIO_ID, type DataSource } from '../data'
import { startPolling } from './poller'

export interface AutoRefresh {
  /** Seconds between reloads; 0 means auto-refresh is disabled by configuration. */
  intervalS: number
  paused: boolean
  setPaused: (paused: boolean) => void
}

interface AppState {
  scenarioId: string
  setScenarioId: (id: string) => void
  /** Mock only: the simulated clock advances in real time (see data/mock/clock.ts). */
  replay: boolean
  setReplay: (replay: boolean) => void
  dataSource: DataSource
  /** Incremented after every mutation and every auto-refresh tick: queries reload when it changes. */
  revision: number
  notifyChanged: () => void
  autoRefresh: AutoRefresh
}

const Ctx = createContext<AppState | null>(null)

export function AppStateProvider({ children, refreshIntervalS = config.refreshIntervalS }: { children: ReactNode; refreshIntervalS?: number }) {
  const [scenarioId, setScenarioIdRaw] = useState(DEFAULT_SCENARIO_ID)
  const [revision, setRevision] = useState(0)
  const [paused, setPaused] = useState(false)
  const [replay, setReplayRaw] = useState(false)
  // A new data source (and, in replay, a clock restarting at 10:30) for each scenario or mode.
  const dataSource = useMemo(() => createDataSource(scenarioId, { replay }), [scenarioId, replay])
  const notifyChanged = useCallback(() => setRevision((r) => r + 1), [])
  const setScenarioId = useCallback((id: string) => {
    setScenarioIdRaw(id)
    setRevision((r) => r + 1)
  }, [])
  const setReplay = useCallback((on: boolean) => {
    setReplayRaw(on)
    setRevision((r) => r + 1)
  }, [])

  useEffect(() => {
    if (paused || refreshIntervalS <= 0) return
    return startPolling(refreshIntervalS * 1000, notifyChanged, document)
  }, [paused, refreshIntervalS, notifyChanged])

  const value = useMemo(
    () => ({
      scenarioId,
      setScenarioId,
      replay,
      setReplay,
      dataSource,
      revision,
      notifyChanged,
      autoRefresh: { intervalS: refreshIntervalS, paused, setPaused },
    }),
    [scenarioId, setScenarioId, replay, setReplay, dataSource, revision, notifyChanged, refreshIntervalS, paused],
  )
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

// The hook belongs with its provider.
// eslint-disable-next-line react-refresh/only-export-components
export function useAppState(): AppState {
  const v = useContext(Ctx)
  if (!v) throw new Error('useAppState must be used inside AppStateProvider')
  return v
}
