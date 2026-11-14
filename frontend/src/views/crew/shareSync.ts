import { useCallback, useEffect, useRef, useState } from 'react'
import type { MissionStatus } from '../../domain/types'
import { useAppState } from '../../state/AppState'
import { enqueueShare, localPersistenceAvailable, queuedShares, removeQueuedShare } from '../../state/crewLocal'

const flushing = new Set<string>()

/**
 * Share with the medical team, with the demo's offline queue:
 * - link up → send now;
 * - link down (mock only) → save on this device, send automatically when the
 *   simulated link returns while the crew screen is open. An entry is removed
 *   only after the data source acknowledges it.
 */
export function useShare(crewId: string, mission: MissionStatus) {
  const { dataSource, notifyChanged } = useAppState()
  const offline = mission.link.state === 'offline'
  const canQueue = dataSource.kind === 'mock'
  const [queued, setQueued] = useState(() => queuedShares().filter((q) => q.crewId === crewId).length)
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const current = useRef(crewId)
  useEffect(() => {
    current.current = crewId
  }, [crewId])

  const recount = useCallback(() => setQueued(queuedShares().filter((q) => q.crewId === crewId).length), [crewId])
  useEffect(() => {
    recount()
    setNotice('')
  }, [recount])

  // Reconnection: deliver what was queued.
  useEffect(() => {
    if (offline || flushing.has(crewId)) return
    const entries = queuedShares().filter((q) => q.crewId === crewId)
    if (!entries.length) return
    flushing.add(crewId)
    let cancelled = false
    void (async () => {
      let sent = 0
      for (const entry of entries) {
        try {
          await dataSource.shareWithMedicalTeam(crewId, entry.note)
          removeQueuedShare(entry.id)
          sent++
        } catch {
          if (!cancelled && current.current === crewId) setNotice('A queued report could not be delivered. It stays saved on this device.')
          break
        }
      }
      flushing.delete(crewId)
      if (sent) notifyChanged()
      if (!cancelled && current.current === crewId) {
        recount()
        if (sent) setNotice(`${sent} queued report${sent === 1 ? '' : 's'} delivered to the medical team (simulated).`)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [crewId, offline, dataSource, notifyChanged, recount])

  const share = useCallback(
    async (note: string): Promise<'sent' | 'queued' | 'failed'> => {
      setError(null)
      if (offline) {
        if (!canQueue) {
          setError('Offline queuing needs secure storage from the backend; not available yet.')
          return 'failed'
        }
        enqueueShare(crewId, note, mission.now)
        recount()
        setNotice(
          localPersistenceAvailable()
            ? 'Saved on this device. It will be sent when the ground link returns.'
            : 'Held in this page only (storage unavailable). Keep the page open until the link returns.',
        )
        return 'queued'
      }
      setBusy(true)
      try {
        await dataSource.shareWithMedicalTeam(crewId, note)
        notifyChanged()
        setNotice('Shared with the medical team (simulated delivery).')
        return 'sent'
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Unexpected error')
        return 'failed'
      } finally {
        setBusy(false)
      }
    },
    [offline, canQueue, crewId, mission.now, dataSource, notifyChanged, recount],
  )

  return { share, queued, notice, busy, error, offline, canQueue }
}
