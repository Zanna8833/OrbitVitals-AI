import type { QualityFlag, ReferenceBand, Sample } from './types'
import { toIso, toMs } from './time'

/**
 * Pure functions that derive OBSERVED facts from samples. They describe the
 * data; they never interpret it physiologically.
 */

export interface QualityCounts {
  total: number
  counts: Record<QualityFlag, number>
}

export function countQuality(samples: Sample[]): QualityCounts {
  const counts: Record<QualityFlag, number> = { good: 0, uncertain: 0, poor: 0, missing: 0 }
  for (const s of samples) counts[s.quality]++
  return { total: samples.length, counts }
}

export function samplesInWindow(samples: Sample[], startIso: string, endIso: string): Sample[] {
  const a = toMs(startIso)
  const b = toMs(endIso)
  return samples.filter((s) => {
    const t = toMs(s.t)
    return t >= a && t <= b
  })
}

/** Samples expected in [start, end] (both inclusive) at a fixed sampling interval. */
export function expectedSampleCount(startIso: string, endIso: string, samplingIntervalS: number): number {
  return Math.floor((toMs(endIso) - toMs(startIso)) / 1000 / samplingIntervalS) + 1
}

export interface Gap {
  start: string
  end: string
  /** Number of expected samples not received or not valid. */
  missingSamples: number
}

/**
 * Finds intervals without a valid value: explicit "missing" samples and holes
 * in the timeline larger than 1.5 sampling intervals.
 */
export function findGaps(samples: Sample[], samplingIntervalS: number, rangeEndIso?: string): Gap[] {
  const step = samplingIntervalS * 1000
  const gaps: Gap[] = []
  let open: { start: number; last: number; n: number } | null = null
  const close = () => {
    if (open) gaps.push({ start: toIso(open.start), end: toIso(open.last), missingSamples: open.n })
    open = null
  }
  let prevT: number | null = null
  for (const s of samples) {
    const t = toMs(s.t)
    if (prevT !== null && t - prevT > step * 1.5) {
      const n = Math.round((t - prevT) / step) - 1
      if (open) {
        open.last = t - step
        open.n += n
      } else {
        open = { start: prevT + step, last: t - step, n }
      }
    }
    if (s.value === null || s.quality === 'missing') {
      if (open) {
        open.last = t
        open.n++
      } else open = { start: t, last: t, n: 1 }
    } else close()
    prevT = t
  }
  if (rangeEndIso && prevT !== null) {
    const end = toMs(rangeEndIso)
    if (end - prevT > step * 1.5) {
      const n = Math.floor((end - prevT) / step)
      if (open) {
        open.last = end
        open.n += n
      } else open = { start: prevT + step, last: end, n }
    }
  }
  close()
  return gaps
}

export interface ValueStats {
  n: number
  min: number
  median: number
  max: number
}

export function statsOf(values: number[]): ValueStats | null {
  if (!values.length) return null
  const v = [...values].sort((a, b) => a - b)
  const mid = Math.floor(v.length / 2)
  const median = v.length % 2 ? v[mid] : (v[mid - 1] + v[mid]) / 2
  return { n: v.length, min: v[0], median, max: v[v.length - 1] }
}

/** Share (0–100) of samples flagged "good"; null when there are no samples. */
export function goodQualityPct(samples: Sample[]): number | null {
  if (!samples.length) return null
  return (samples.filter((s) => s.quality === 'good').length / samples.length) * 100
}

export function goodValues(samples: Sample[]): number[] {
  return samples.filter((s) => s.quality === 'good' && s.value !== null).map((s) => s.value as number)
}

/** Reference value at a given time, by linear interpolation over the protocol offset. */
export function referenceAt(band: ReferenceBand, sessionStartIso: string, tIso: string) {
  const off = (toMs(tIso) - toMs(sessionStartIso)) / 1000
  const pts = band.points
  if (!pts.length) return null
  if (off <= pts[0].offsetS) return pts[0]
  for (let i = 1; i < pts.length; i++) {
    if (off <= pts[i].offsetS) {
      const a = pts[i - 1]
      const b = pts[i]
      const k = (off - a.offsetS) / (b.offsetS - a.offsetS)
      return {
        offsetS: off,
        low: a.low + (b.low - a.low) * k,
        median: a.median + (b.median - a.median) * k,
        high: a.high + (b.high - a.high) * k,
      }
    }
  }
  return pts[pts.length - 1]
}

export interface BandComparison {
  compared: number
  above: number
  below: number
}

/** Counts good-quality samples above/below the personal historical band. */
export function compareWithBand(samples: Sample[], band: ReferenceBand, sessionStartIso: string): BandComparison {
  let compared = 0
  let above = 0
  let below = 0
  for (const s of samples) {
    if (s.quality !== 'good' || s.value === null) continue
    const r = referenceAt(band, sessionStartIso, s.t)
    if (!r) continue
    compared++
    if (s.value > r.high) above++
    else if (s.value < r.low) below++
  }
  return { compared, above, below }
}
