import { toIso, toMs } from '../../domain/time'
import { SAMPLE_INTERVAL_S, SESSION_START, SIM_NOW } from './generator'

/**
 * The mock backend's notion of "now" (it plays the role of the server clock;
 * the UI never reads the browser clock to judge data freshness).
 */
export type SimClock = () => string

/** Default: frozen at 10:40 UTC, so every run of the demo shows the same data. */
export const fixedClock: SimClock = () => SIM_NOW

export const REPLAY = {
  /** Replay starts at 10:30 UTC: after every scheduled demo event, before the 10:34 link loss. */
  startOffsetS: 30 * 60,
  /** …and stops at the end of the scheduled session (10:45 UTC). */
  endOffsetS: 45 * 60,
} as const

/**
 * Live replay: the simulated clock advances one sample (10 s) per 10 s of real
 * time from 10:30 UTC, then stops at 10:45 UTC. Deterministic for a given
 * elapsed time. `realNow` is injectable for tests.
 */
export function replayClock(startedAtMs: number, realNow: () => number = Date.now): SimClock {
  const stepMs = SAMPLE_INTERVAL_S * 1000
  return () => {
    const steps = Math.max(0, Math.floor((realNow() - startedAtMs) / stepMs))
    const offsetS = Math.min(REPLAY.startOffsetS + steps * SAMPLE_INTERVAL_S, REPLAY.endOffsetS)
    return toIso(toMs(SESSION_START) + offsetS * 1000)
  }
}
