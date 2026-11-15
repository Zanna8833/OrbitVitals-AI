import type {
  ActivityKind,
  ActivitySegment,
  DataSourceInfo,
  HistoricalSession,
  ParameterId,
  QualityFlag,
  QualityReason,
  ReferenceBand,
  ReferencePoint,
  Sample,
} from '../../domain/types'
import { PARAMETERS } from '../../domain/parameters'
import { toIso, toMs } from '../../domain/time'
import { gaussian, hashSeed, mulberry32 } from './rng'
import type { ScenarioFlags } from './scenarios'

/* ------------------------------------------------------------------ */
/* Fixed simulated timeline                                            */
/* ------------------------------------------------------------------ */

export const SESSION_START = '2026-11-14T10:00:00Z'
export const SIM_NOW = '2026-11-14T10:40:00Z'
export const SAMPLE_INTERVAL_S = 10
/** Link loss time in the "offline" scenario (offset from session start, s). */
export const LINK_LOSS_OFFSET_S = 34 * 60
/** Crew C device stops reporting at this offset in the "stale" scenario. */
export const STALE_OFFSET_S = 22 * 60

export const PROTOCOL_EXERCISE = 'EX-CICLO-30'
export const PROTOCOL_OPERATIONAL = 'OPS-MANUT-45'

interface PhaseDef {
  kind: ActivityKind
  label: string
  from: number
  to: number
}

const PROTOCOLS: Record<string, PhaseDef[]> = {
  [PROTOCOL_EXERCISE]: [
    { kind: 'rest', label: 'Pre-exercise rest', from: 0, to: 300 },
    { kind: 'warmup', label: 'Warm-up', from: 300, to: 600 },
    { kind: 'exercise', label: 'Cycle ergometer, constant load', from: 600, to: 1680 },
    { kind: 'recovery', label: 'Recovery', from: 1680, to: 2700 },
  ],
  [PROTOCOL_OPERATIONAL]: [{ kind: 'operational', label: 'Scheduled maintenance', from: 0, to: 2700 }],
}

/* ------------------------------------------------------------------ */
/* Simulated crew                                                      */
/* ------------------------------------------------------------------ */

interface CrewProfile {
  id: string
  displayName: string
  protocolId: string
  rest: Record<ParameterId, number>
  peak: Record<ParameterId, number>
  noise: Record<ParameterId, number>
}

export const CREW_PROFILES: CrewProfile[] = [
  {
    id: 'crew-a',
    displayName: 'Astronaut A',
    protocolId: PROTOCOL_EXERCISE,
    rest: { heart_rate: 60, spo2: 98, resp_rate: 12, motion: 0.02 },
    peak: { heart_rate: 136, spo2: 97, resp_rate: 25, motion: 0.34 },
    noise: { heart_rate: 1.6, spo2: 0.4, resp_rate: 0.7, motion: 0.025 },
  },
  {
    id: 'crew-b',
    displayName: 'Astronaut B',
    protocolId: PROTOCOL_EXERCISE,
    rest: { heart_rate: 66, spo2: 97.6, resp_rate: 14, motion: 0.02 },
    peak: { heart_rate: 131, spo2: 97, resp_rate: 27, motion: 0.37 },
    noise: { heart_rate: 1.6, spo2: 0.4, resp_rate: 0.7, motion: 0.03 },
  },
  {
    id: 'crew-c',
    displayName: 'Astronaut C',
    protocolId: PROTOCOL_OPERATIONAL,
    rest: { heart_rate: 64, spo2: 97.8, resp_rate: 13, motion: 0.03 },
    peak: { heart_rate: 92, spo2: 97.5, resp_rate: 17, motion: 0.18 },
    noise: { heart_rate: 1.8, spo2: 0.4, resp_rate: 0.8, motion: 0.025 },
  },
]

export function getProfile(crewId: string): CrewProfile | undefined {
  return CREW_PROFILES.find((p) => p.id === crewId)
}

export function sourceFor(crewId: string, parameter: ParameterId): DataSourceInfo {
  const suffix = crewId.slice(-1).toUpperCase()
  const common = {
    samplingIntervalS: SAMPLE_INTERVAL_S,
    qualityMethod:
      'Quality flag reported with the reading by the acquisition chain.',
    firmware: 'sim-0.1',
    simulated: true,
  }
  if (parameter === 'spo2') {
    return {
      ...common,
      deviceId: `SIM-PPG-${suffix}`,
      deviceLabel: 'Pulse oximeter',
      sensorType: 'Photoplethysmography (PPG)',
      placement: 'Finger',
      processing: 'Value aggregated over 10 s windows',
    }
  }
  return {
    ...common,
    deviceId: `SIM-CHEST-${suffix}`,
    deviceLabel: 'Chest strap',
    sensorType:
      parameter === 'heart_rate'
        ? 'Single-lead ECG'
        : parameter === 'resp_rate'
          ? 'Respiratory plethysmography'
          : 'Triaxial accelerometer',
    placement: 'Chest',
    processing:
      parameter === 'motion'
        ? 'Acceleration RMS over 10 s windows'
        : 'Value aggregated over 10 s windows',
  }
}

/* ------------------------------------------------------------------ */
/* Signal shapes                                                       */
/* ------------------------------------------------------------------ */

/** Relative intensity 0..1 of the protocol at a given offset (s). */
function intensity(protocolId: string, off: number): number {
  if (protocolId === PROTOCOL_OPERATIONAL) {
    return 0.35 + 0.15 * Math.sin(off / 380) + 0.08 * Math.sin(off / 97)
  }
  if (off < 300) return 0
  if (off < 600) return (0.4 * (off - 300)) / 300
  const atEnd = 0.4 + 0.6 * (1 - Math.exp(-(1680 - 600) / 95))
  if (off < 1680) return 0.4 + 0.6 * (1 - Math.exp(-(off - 600) / 95))
  return 0.07 + (atEnd - 0.07) * Math.exp(-(off - 1680) / 120)
}

function smoothBump(off: number, from: number, to: number): number {
  if (off < from || off > to) return 0
  return Math.pow(Math.sin((Math.PI * (off - from)) / (to - from)), 0.7)
}

function round(parameter: ParameterId, v: number): number {
  const d = PARAMETERS[parameter].decimals
  const k = Math.pow(10, d)
  return Math.round(v * k) / k
}

interface GenerateOptions {
  profile: CrewProfile
  parameter: ParameterId
  seedKey: string
  /** Inclusive upper bound for the offset (s). */
  untilOffsetS: number
  flags: ScenarioFlags
  /** Per-session variation applied to historical sessions. */
  dayShift?: { rest: number; peak: number }
}

/** Generates one parameter for one crew member over the protocol. Pure and deterministic. */
export function generateSamples(o: GenerateOptions): Sample[] {
  const { profile, parameter, flags } = o
  const rand = mulberry32(hashSeed(o.seedKey))
  const rest = profile.rest[parameter] + (o.dayShift?.rest ?? 0)
  const peak = profile.peak[parameter] + (o.dayShift?.peak ?? 0)
  const startMs = toMs(SESSION_START)
  const out: Sample[] = []

  for (let off = 0; off <= o.untilOffsetS; off += SAMPLE_INTERVAL_S) {
    const t = toIso(startMs + off * 1000)
    let value = rest + (peak - rest) * intensity(profile.protocolId, off) + profile.noise[parameter] * gaussian(rand)
    let quality: QualityFlag = 'good'
    let reasons: QualityReason[] | undefined

    // Rare, isolated motion-related flags during exercise: realistic background noise.
    if (parameter !== 'motion' && off >= 600 && off < 1680 && rand() < 0.012) {
      quality = 'uncertain'
      reasons = ['motion']
    }

    // Scenario 5 — Crew A heart rate above personal range (good quality).
    if (flags.reviewEvent && profile.id === 'crew-a') {
      if (parameter === 'heart_rate') value += 21 * smoothBump(off, 840, 1210)
      if (parameter === 'resp_rate') value += 1.5 * smoothBump(off, 840, 1210)
    }

    // Scenario 2 — Crew B motion artifact on SpO₂ + respiratory-rate gap.
    if (flags.uncertainQuality && profile.id === 'crew-b') {
      const inArtifact = off >= 1080 && off <= 1380
      if (parameter === 'motion' && inArtifact) value += 0.32 + 0.08 * gaussian(rand)
      if (parameter === 'spo2' && inArtifact) {
        const r = rand()
        if (r < 0.12) {
          out.push({ t, value: null, quality: 'missing', reasons: ['not_received'] })
          continue
        }
        value -= 2 + 7 * rand()
        quality = r < 0.6 ? 'uncertain' : 'poor'
        reasons = quality === 'poor' ? ['motion', 'contact'] : ['motion']
      }
      if (parameter === 'resp_rate' && off >= 1440 && off <= 1560) {
        out.push({ t, value: null, quality: 'missing', reasons: ['not_received'] })
        continue
      }
    }

    if (parameter === 'spo2') value = Math.min(100, value)
    if (parameter === 'motion') value = Math.max(0, value)
    const s: Sample = { t, value: round(parameter, value), quality }
    if (reasons) s.reasons = reasons
    out.push(s)
  }
  return out
}

/** Last offset (s) for which the ground segment has data at `nowIso`, given the scenario. */
export function receivedUntilOffset(crewId: string, flags: ScenarioFlags, nowIso: string = SIM_NOW): number {
  let until = (toMs(nowIso) - toMs(SESSION_START)) / 1000
  if (flags.linkOffline) until = Math.min(until, LINK_LOSS_OFFSET_S)
  if (flags.staleData && crewId === 'crew-c') until = Math.min(until, STALE_OFFSET_S)
  return until
}

export function activitiesFor(crewId: string): ActivitySegment[] {
  const profile = getProfile(crewId)
  if (!profile) return []
  const startMs = toMs(SESSION_START)
  return PROTOCOLS[profile.protocolId].map((p) => ({
    start: toIso(startMs + p.from * 1000),
    end: toIso(startMs + p.to * 1000),
    kind: p.kind,
    label: p.label,
    protocolId: profile.protocolId,
    scheduled: true,
  }))
}

/* ------------------------------------------------------------------ */
/* Personal history (5 previous simulated sessions, same protocol)     */
/* ------------------------------------------------------------------ */

const HISTORY_DATES = ['2026-11-04', '2026-11-06', '2026-11-08', '2026-11-10', '2026-11-12']
const NO_FLAGS: ScenarioFlags = { reviewEvent: false, uncertainQuality: false, staleData: false, linkOffline: false }

function percentile(sorted: number[], p: number): number {
  if (!sorted.length) return NaN
  const idx = (sorted.length - 1) * p
  const lo = Math.floor(idx)
  const hi = Math.ceil(idx)
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (idx - lo)
}

export function buildReferenceBand(crewId: string, parameter: ParameterId): ReferenceBand | null {
  const profile = getProfile(crewId)
  if (!profile) return null
  const duration = 2700
  const scale = Math.abs(profile.peak[parameter] - profile.rest[parameter])
  const sessions = HISTORY_DATES.map((date, i) => {
    const r = mulberry32(hashSeed(`${crewId}-${parameter}-day-${i}`))
    const samples = generateSamples({
      profile,
      parameter,
      seedKey: `${crewId}-${parameter}-hist-${i}`,
      untilOffsetS: duration,
      flags: NO_FLAGS,
      dayShift: { rest: gaussian(r) * profile.noise[parameter] * 0.8, peak: gaussian(r) * scale * 0.035 },
    })
    return { date, samples }
  })

  const mainPhase = PROTOCOLS[profile.protocolId].find((p) => p.kind === 'exercise' || p.kind === 'operational')!
  const historical: HistoricalSession[] = sessions.map(({ date, samples }) => {
    const main = samples
      .filter((s, k) => s.quality === 'good' && s.value !== null && k * SAMPLE_INTERVAL_S >= mainPhase.from && k * SAMPLE_INTERVAL_S < mainPhase.to)
      .map((s) => s.value as number)
      .sort((a, b) => a - b)
    const good = samples.filter((s) => s.quality === 'good').length
    return {
      id: `${crewId}-${parameter}-${date}`,
      date: `${date}T10:00:00Z`,
      protocolId: profile.protocolId,
      mainPhaseMedian: round(parameter, percentile(main, 0.5)),
      goodQualityPct: Math.round((good / samples.length) * 1000) / 10,
    }
  })

  const points: ReferencePoint[] = []
  const bin = 60
  for (let off = 0; off <= duration; off += bin) {
    const vals: number[] = []
    for (const { samples } of sessions) {
      for (let k = 0; k < samples.length; k++) {
        const o = k * SAMPLE_INTERVAL_S
        const s = samples[k]
        if (o >= off - bin / 2 && o < off + bin / 2 && s.quality === 'good' && s.value !== null) vals.push(s.value)
      }
    }
    vals.sort((a, b) => a - b)
    if (vals.length) points.push({ offsetS: off, low: percentile(vals, 0.1), median: percentile(vals, 0.5), high: percentile(vals, 0.9) })
  }

  return {
    crewId,
    parameter,
    protocolId: profile.protocolId,
    basis: `P10–P90 of good-quality samples from ${sessions.length} previous sessions of the same protocol (${profile.protocolId}), aligned on time from protocol start, 60 s windows. Reference data set.`,
    sessions: historical,
    points,
  }
}

