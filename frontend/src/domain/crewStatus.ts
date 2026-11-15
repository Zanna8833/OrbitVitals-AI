import type { ParameterId, QualityFlag, TimeSeries } from './types'
import { computeFreshness } from './freshness'
import { findGaps } from './observations'
import { formatAge, formatClock, formatDuration, formatUtc, toMs } from './time'

/**
 * Plain-language status for the CREW view. Deliberately non-clinical: it only
 * says whether data is flowing and whether a sensor signal looks disturbed,
 * and never asks for action during the activity.
 */

/** Visual level, rendered with the quality glyph shapes (shape + text, never colour alone). */
export type StatusLevel = QualityFlag

export interface CollectionStatus {
  level: StatusLevel
  headline: string
  detail: string
}

export function describeCollection(
  lastReceivedAt: string | null,
  nowIso: string,
  expectedIntervalS: number,
  linkOffline: boolean,
): CollectionStatus {
  if (linkOffline) {
    return {
      level: 'poor',
      headline: 'Transmission to ground paused',
      detail: lastReceivedAt
        ? `Last successful transmission at ${formatUtc(lastReceivedAt, false)}. It resumes when the link is restored (assumed behaviour).`
        : 'No successful transmission.',
    }
  }
  const freshness = computeFreshness(lastReceivedAt, nowIso, expectedIntervalS)
  if (lastReceivedAt && freshness === 'current') {
    return {
      level: 'good',
      headline: 'Data collection active',
      detail: `Last sent to ground: ${formatUtc(lastReceivedAt)} (${formatAge(lastReceivedAt, nowIso)}).`,
    }
  }
  if (lastReceivedAt && freshness === 'delayed') {
    return {
      level: 'uncertain',
      headline: 'Data transmission delayed',
      detail: `Last sent: ${formatUtc(lastReceivedAt)} (${formatAge(lastReceivedAt, nowIso)}). No action needed.`,
    }
  }
  return {
    level: lastReceivedAt ? 'poor' : 'missing',
    headline: 'The device is not sending data',
    detail: lastReceivedAt
      ? `Last data received at ${formatUtc(lastReceivedAt, false)} (${formatAge(lastReceivedAt, nowIso)}). The ground team can see this interruption.`
      : 'No data received. The ground team can see this interruption.',
  }
}

export const SENSOR_RULES = {
  /** "Right now" for the crew = the last 2 minutes. */
  recentWindowMs: 2 * 60 * 1000,
  /** More than this many poor/missing samples in the recent window → "disturbed right now". */
  maxRecentBadSamples: 2,
  /** An earlier disturbed interval is mentioned only if it had more than this many poor samples. */
  minEarlierPoorSamples: 3,
  /** Earlier gaps shorter than this many samples are not worth mentioning to the crew. */
  minEarlierGapSamples: 3,
} as const

export interface SensorStatus {
  deviceId: string
  deviceLabel: string
  placement: string
  parameters: ParameterId[]
  level: StatusLevel
  text: string
  /** A quiet, one-line note about an earlier problem that has since resolved; null if none. */
  earlierNote: string | null
  /**
   * The signal itself was disturbed (poor-quality samples now or earlier), as
   * opposed to data simply not being received. Only this suggests checking placement.
   */
  signalDisturbed: boolean
}

/** One status per physical device (series sharing the same deviceId). */
export function describeSensors(series: TimeSeries[], nowIso: string): SensorStatus[] {
  const byDevice = new Map<string, TimeSeries[]>()
  for (const s of series) byDevice.set(s.source.deviceId, [...(byDevice.get(s.source.deviceId) ?? []), s])
  return [...byDevice.values()].map((list) => describeDevice(list, nowIso))
}

function describeDevice(list: TimeSeries[], nowIso: string): SensorStatus {
  const source = list[0].source
  const recentFrom = toMs(nowIso) - SENSOR_RULES.recentWindowMs
  const recent = list.flatMap((s) => s.samples.filter((x) => toMs(x.t) >= recentFrom))
  const recentBad = recent.filter((x) => x.quality === 'poor' || x.quality === 'missing').length

  let level: StatusLevel
  let text: string
  if (!recent.length) {
    level = 'missing'
    text = 'No data in the last 2 minutes'
  } else if (recentBad > SENSOR_RULES.maxRecentBadSamples) {
    level = 'poor'
    text = 'Signal disturbed right now'
  } else {
    level = 'good'
    text = 'Signal regular'
  }

  const poorSamples = list.reduce((n, s) => n + s.samples.filter((x) => x.quality === 'poor').length, 0)

  return {
    deviceId: source.deviceId,
    deviceLabel: source.deviceLabel,
    placement: source.placement,
    parameters: list.map((s) => s.parameter),
    level,
    text,
    earlierNote: level === 'good' ? earlierProblemNote(list) : null,
    signalDisturbed: level === 'poor' || poorSamples > SENSOR_RULES.minEarlierPoorSamples,
  }
}

function earlierProblemNote(list: TimeSeries[]): string | null {
  const poor = list.flatMap((s) => s.samples.filter((x) => x.quality === 'poor'))
  if (poor.length > SENSOR_RULES.minEarlierPoorSamples) {
    return `Signal disturbed between ${formatClock(poor[0].t, false)} and ${formatClock(poor[poor.length - 1].t, false)} UTC. No action needed during the activity.`
  }
  for (const s of list) {
    const gap = findGaps(s.samples, s.source.samplingIntervalS).find((g) => g.missingSamples >= SENSOR_RULES.minEarlierGapSamples)
    if (gap) {
      const duration = formatDuration(gap.missingSamples * s.source.samplingIntervalS * 1000)
      return `Data not received for a short period at ${formatClock(gap.start, false)} UTC (${duration}). No action needed.`
    }
  }
  return null
}
