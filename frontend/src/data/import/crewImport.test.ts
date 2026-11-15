import { describe, expect, it } from 'vitest'
import { indicatorOf, parseMeasurementsCsv, parseProfileJson } from './crewImport'

describe('profile JSON', () => {
  it('reads aliases and defaults the mission start', () => {
    const p = parseProfileJson('{"crew_id":"crew-b","name":"Mission Specialist","role":"FE-1"}')
    expect(p).toMatchObject({ crewId: 'crew-b', displayName: 'Mission Specialist', role: 'FE-1', missionStartDate: '2026-10-31' })
  })
  it('rejects invalid JSON and arrays with a readable message', () => {
    expect(() => parseProfileJson('{oops')).toThrow(/not valid JSON/)
    expect(() => parseProfileJson('[]')).toThrow(/JSON object/)
  })
})

describe('measurements CSV', () => {
  it('reads the long layout, fills gaps and computes the baseline', () => {
    const rows = ['date,indicator,value,unit,quality']
    for (let d = 1; d <= 9; d++) if (d !== 8) rows.push(`2026-10-${String(30 + d).padStart(2, '0')}`.replace('2026-10-32', '2026-11-01').replace('2026-10-33', '2026-11-02').replace('2026-10-34', '2026-11-03').replace('2026-10-35', '2026-11-04').replace('2026-10-36', '2026-11-05').replace('2026-10-37', '2026-11-06').replace('2026-10-38', '2026-11-07').replace('2026-10-39', '2026-11-08') + `,rhr,${58 + (d % 3)},bpm,good`)
    rows.push('2026-11-08,unknown_thing,3,,good')
    const r = parseMeasurementsCsv(rows.join('\n'), 'crew-a')
    expect(r.layout).toBe('long')
    const hr = r.series.find((s) => s.indicator === 'resting_hr')!
    expect(hr.days).toHaveLength(9)
    expect(hr.days[7]).toMatchObject({ missionDay: 8, value: null, quality: 'missing' })
    expect(hr.baseline).not.toBeNull()
    expect(hr.simulated).toBe(false)
    expect(r.issues[0].message).toMatch(/Unknown indicator/)
  })

  it('reads the wide layout with ";" and decimal commas (European spreadsheets)', () => {
    const csv = 'Date;Resting HR (bpm);Sleep hours;Weight\n31/10/2026;60;7,5;74,2\n01/11/2026;61;6,9;74,1\n02/11/2026;abc;7,0;74,0'
    const r = parseMeasurementsCsv(csv, 'crew-a')
    expect(r.layout).toBe('wide')
    expect(r.series.find((s) => s.indicator === 'sleep_duration')!.days[0].value).toBe(7.5)
    expect(r.series.find((s) => s.indicator === 'body_mass')!.days[1].value).toBe(74.1)
    expect(r.issues).toHaveLength(1)
    expect(r.firstDate).toBe('2026-10-31')
  })

  it('maps common names to indicators', () => {
    expect(indicatorOf('HRV')).toBe('hrv_rmssd')
    expect(indicatorOf('SpO2 (%)')).toBe('resting_spo2')
    expect(indicatorOf('nonsense')).toBeNull()
  })

  it('explains what is missing', () => {
    expect(() => parseMeasurementsCsv('value\n1', 'crew-a')).toThrow(/date/)
    expect(() => parseMeasurementsCsv('date,foo\n2026-11-01,1', 'crew-a')).toThrow(/No known indicator/)
  })
})
