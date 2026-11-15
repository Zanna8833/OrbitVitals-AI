import { useEffect, useState } from 'react'
import { config } from '../config'

/** Whether the team's cognition battery is installed next to the app (npm run cognition). null while checking. */
export function useCognitionAvailable(): boolean | null {
  const [ok, setOk] = useState<boolean | null>(null)
  useEffect(() => {
    let alive = true
    // A missing build would return OrbitVitals itself (single-page fallback): check it is the battery.
    fetch(config.cognitionUrl)
      .then(async (r) => alive && setOk(r.ok && (await r.text()).includes('Cognition Battery')))
      .catch(() => alive && setOk(false))
    return () => {
      alive = false
    }
  }, [])
  return ok
}
