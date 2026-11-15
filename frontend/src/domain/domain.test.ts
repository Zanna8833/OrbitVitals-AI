import { describe, expect, it } from 'vitest'
import { computeFreshness } from './freshness'
import { compareWithBand, countQuality, expectedSampleCount, findGaps, goodQualityPct, statsOf } from './observations'
import type { ReferenceBand, Sample } from './types'
import { formatAge, formatUtc } from './time'

const s = (t: string, value: number | null, quality: Sample['quality'] = 'good'): Sample => ({ t, value, quality })

describe('freshness (display thresholds, not clinical)', () => {
  const now = '2026-11-14T10:40:00Z'
  it('classifies by age of the last sample', () => {
    expect(computeFreshness('2026-11-14T10:39:50Z', now, 10)).toBe('current')
    expect(computeFreshness('2026-11-14T10:38:30Z', now, 10)).toBe('delayed')
    expect(computeFreshness('2026-11-14T10:22:00Z', now, 10)).toBe('stale')
    expect(computeFreshness(null, now, 10)).toBe('none')
  })
})

describe('findGaps', () => {
  it('detects explicit missing samples and timeline holes', () => {
    const samples = [
      s('2026-11-14T10:00:00Z', 1),
      s('2026-11-14T10:00:10Z', null, 'missing'),
      s('2026-11-14T10:00:20Z', null, 'missing'),
      s('2026-11-14T10:00:30Z', 1),
      // hole: 10:00:40 and 10:00:50 never received
      s('2026-11-14T10:01:00Z', 1),
    ]
    const gaps = findGaps(samples, 10)
    expect(gaps).toHaveLength(2)
    expect(gaps[0]).toMatchObject({ start: '2026-11-14T10:00:10Z', end: '2026-11-14T10:00:20Z', missingSamples: 2 })
    expect(gaps[1]).toMatchObject({ start: '2026-11-14T10:00:40Z', end: '2026-11-14T10:00:50Z', missingSamples: 2 })
  })
  it('reports a trailing gap up to the range end', () => {
    const gaps = findGaps([s('2026-11-14T10:00:00Z', 1)], 10, '2026-11-14T10:05:00Z')
    expect(gaps).toHaveLength(1)
    expect(gaps[0].missingSamples).toBe(30)
  })
  it('returns no gaps for a complete series', () => {
    expect(findGaps([s('2026-11-14T10:00:00Z', 1), s('2026-11-14T10:00:10Z', 2)], 10)).toEqual([])
  })
})

describe('quality and statistics', () => {
  it('counts quality flags', () => {
    const q = countQuality([s('2026-11-14T10:00:00Z', 1), s('2026-11-14T10:00:10Z', 2, 'uncertain'), s('2026-11-14T10:00:20Z', null, 'missing')])
    expect(q.counts).toEqual({ good: 1, uncertain: 1, poor: 0, missing: 1 })
  })
  it('computes the share of good-quality samples', () => {
    expect(goodQualityPct([s('2026-11-14T10:00:00Z', 1), s('2026-11-14T10:00:10Z', 2, 'poor')])).toBe(50)
    expect(goodQualityPct([])).toBeNull()
  })
  it('counts expected samples with both window ends included', () => {
    expect(expectedSampleCount('2026-11-14T10:00:00Z', '2026-11-14T10:01:00Z', 10)).toBe(7)
  })
  it('computes median for even and odd sizes', () => {
    expect(statsOf([3, 1, 2])?.median).toBe(2)
    expect(statsOf([4, 1, 2, 3])?.median).toBe(2.5)
    expect(statsOf([])).toBeNull()
  })
  it('compares only good samples with the personal band', () => {
    const band: ReferenceBand = {
      crewId: 'x',
      parameter: 'heart_rate',
      protocolId: 'p',
      basis: '',
      sessions: [],
      points: [
        { offsetS: 0, low: 60, median: 70, high: 80 },
        { offsetS: 600, low: 60, median: 70, high: 80 },
      ],
    }
    const r = compareWithBand(
      [s('2026-11-14T10:01:00Z', 90), s('2026-11-14T10:02:00Z', 50), s('2026-11-14T10:03:00Z', 99, 'poor'), s('2026-11-14T10:04:00Z', 70)],
      band,
      '2026-11-14T10:00:00Z',
    )
    expect(r).toEqual({ compared: 3, above: 1, below: 1 })
  })
})

describe('time formatting', () => {
  it('always formats in UTC', () => {
    expect(formatUtc('2026-11-14T10:15:20Z')).toBe('10:15:20 UTC')
    expect(formatAge('2026-11-14T10:22:00Z', '2026-11-14T10:40:00Z')).toBe('18 min ago')
  })
})
