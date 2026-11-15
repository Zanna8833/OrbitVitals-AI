import type { DailyIndicatorId, DailyIndicatorSeries, DailyValue, QualityFlag } from '../../domain/types'
import { DAILY_INDICATORS, DAILY_INDICATOR_ORDER } from '../../domain/parameters'
import { BASELINE_DAYS, MISSION_START_DATE, baselineOf } from '../mock/daily'

/**
 * Import of the team's data files:
 * - crew profile: JSON;
 * - measurements: CSV, "long" (date,indicator,value[,unit][,quality]) or
 *   "wide" (date,resting_hr,sleep_duration,…) layout.
 * Tolerant on purpose (aliases, ";" separators, decimal commas) and explicit
 * about every row it cannot use. The format is a PROPOSAL until the team's
 * real files are available (docs/FRONTEND_DATA_CONTRACT.md, docs/samples/).
 */

export interface CrewProfileInput {
  crewId: string | null
  displayName: string | null
  role: string | null
  missionStartDate: string
  /** For the nutrition requirements (NASA JSC-67378), when present. */
  sex: 'male' | 'female' | null
  ageYears: number | null
  heightM: number | null
}

export interface ImportIssue {
  line: number
  message: string
}

export interface MeasurementsImport {
  series: DailyIndicatorSeries[]
  rowsRead: number
  rowsUsed: number
  issues: ImportIssue[]
  layout: 'long' | 'wide'
  firstDate: string | null
  lastDate: string | null
}

/* ---------------- profile (JSON) ---------------- */

const str = (v: unknown): string | null => (typeof v === 'string' && v.trim() ? v.trim() : typeof v === 'number' ? String(v) : null)

export function parseProfileJson(text: string): CrewProfileInput {
  let raw: unknown
  try {
    raw = JSON.parse(text)
  } catch (e) {
    throw new Error(`The profile is not valid JSON (${e instanceof Error ? e.message : 'parse error'}).`)
  }
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) throw new Error('The profile must be a JSON object, e.g. { "crewId": "crew-a", "displayName": "Crew A" }.')
  const o = raw as Record<string, unknown>
  const pick = (...keys: string[]) => {
    for (const k of keys) if (str(o[k])) return str(o[k])
    return null
  }
  const start = pick('missionStartDate', 'mission_start_date', 'missionStart', 'launchDate', 'launch_date')
  if (start && !/^\d{4}-\d{2}-\d{2}/.test(start)) throw new Error(`missionStartDate must be a date like 2026-10-31 (found "${start}").`)
  const sexRaw = pick('sex', 'gender')?.toLowerCase() ?? null
  const sex = sexRaw === null ? null : ['m', 'male', 'man', 'maschio', 'uomo'].includes(sexRaw) ? 'male' : ['f', 'female', 'woman', 'femmina', 'donna'].includes(sexRaw) ? 'female' : null
  const num = (...keys: string[]) => {
    const v = Number(pick(...keys)?.replace(',', '.'))
    return Number.isFinite(v) && v > 0 ? v : null
  }
  const h = num('heightM', 'height_m', 'height', 'heightCm', 'height_cm')
  return {
    sex,
    ageYears: num('ageYears', 'age_years', 'age'),
    // Heights above 3 are read as centimetres.
    heightM: h === null ? null : h > 3 ? h / 100 : h,
    crewId: pick('crewId', 'crew_id', 'id', 'astronautId', 'astronaut_id'),
    displayName: pick('displayName', 'display_name', 'name', 'callsign', 'callSign'),
    role: pick('role', 'position'),
    missionStartDate: start ? start.slice(0, 10) : MISSION_START_DATE,
  }
}

/* ---------------- measurements (CSV) ---------------- */

const ALIASES: Record<string, DailyIndicatorId> = {
  resting_hr: 'resting_hr', rhr: 'resting_hr', hr_rest: 'resting_hr', resting_heart_rate: 'resting_hr', heart_rate_resting: 'resting_hr', heart_rate: 'resting_hr', hr: 'resting_hr',
  sleep_duration: 'sleep_duration', sleep: 'sleep_duration', sleep_hours: 'sleep_duration', sleep_h: 'sleep_duration',
  resting_spo2: 'resting_spo2', spo2: 'resting_spo2', o2_saturation: 'resting_spo2', oxygen_saturation: 'resting_spo2',
  resting_resp_rate: 'resting_resp_rate', resp_rate: 'resting_resp_rate', respiratory_rate: 'resting_resp_rate', rr: 'resting_resp_rate',
  hrv_rmssd: 'hrv_rmssd', hrv: 'hrv_rmssd', rmssd: 'hrv_rmssd',
  bp_systolic: 'bp_systolic', systolic: 'bp_systolic', sbp: 'bp_systolic',
  bp_diastolic: 'bp_diastolic', diastolic: 'bp_diastolic', dbp: 'bp_diastolic',
  body_temperature: 'body_temperature', temperature: 'body_temperature', temp: 'body_temperature', body_temp: 'body_temperature',
  activity_minutes: 'activity_minutes', activity: 'activity_minutes', exercise_minutes: 'activity_minutes', exercise_min: 'activity_minutes',
  body_mass: 'body_mass', mass: 'body_mass', weight: 'body_mass', body_weight: 'body_mass',
  sleep_efficiency: 'sleep_efficiency', sleep_eff: 'sleep_efficiency',
}

const norm = (h: string) =>
  h
    .trim()
    .toLowerCase()
    .replace(/\(.*?\)/g, '')
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_|_$/g, '')

export function indicatorOf(name: string): DailyIndicatorId | null {
  return ALIASES[norm(name)] ?? null
}

/** Splits one CSV line, honouring double quotes. */
function splitLine(line: string, sep: string): string[] {
  const out: string[] = []
  let cur = ''
  let quoted = false
  for (let i = 0; i < line.length; i++) {
    const c = line[i]
    if (c === '"') {
      if (quoted && line[i + 1] === '"') {
        cur += '"'
        i++
      } else quoted = !quoted
    } else if (c === sep && !quoted) {
      out.push(cur)
      cur = ''
    } else cur += c
  }
  out.push(cur)
  return out.map((s) => s.trim())
}

function toNumber(s: string, sep: string): number | null {
  if (!s) return null
  // With ";" as separator, a comma is a decimal comma (Italian / European spreadsheets).
  const t = sep === ';' ? s.replace(/\./g, '').replace(',', '.') : s
  const n = Number(t)
  return Number.isFinite(n) ? n : null
}

function toDate(s: string): string | null {
  const iso = s.match(/^(\d{4})-(\d{2})-(\d{2})/)
  if (iso) return `${iso[1]}-${iso[2]}-${iso[3]}`
  const eu = s.match(/^(\d{1,2})[/.](\d{1,2})[/.](\d{4})/)
  if (eu) return `${eu[3]}-${eu[2].padStart(2, '0')}-${eu[1].padStart(2, '0')}`
  return null
}

function toQuality(s: string | undefined): QualityFlag | null {
  if (!s) return 'good'
  const q = s.trim().toLowerCase()
  if (['good', 'ok', 'reliable', '1', 'true', ''].includes(q)) return 'good'
  if (['uncertain', 'questionable', 'motion', 'artifact', 'artefact'].includes(q)) return 'uncertain'
  if (['poor', 'bad', '0', 'false'].includes(q)) return 'poor'
  if (['missing', 'na', 'n/a', 'null', 'none'].includes(q)) return 'missing'
  return null
}

const DAY_MS = 86_400_000
const dayOf = (date: string, start: string) => Math.floor((Date.parse(`${date}T00:00:00Z`) - Date.parse(`${start}T00:00:00Z`)) / DAY_MS) + 1

export function parseMeasurementsCsv(text: string, crewId: string, missionStartDate: string = MISSION_START_DATE, fileName = 'measurements.csv'): MeasurementsImport {
  const lines = text.replace(/^﻿/, '').split(/\r?\n/)
  const headerIdx = lines.findIndex((l) => l.trim() && !l.trim().startsWith('#'))
  if (headerIdx < 0) throw new Error('The CSV file is empty.')
  const sep = (lines[headerIdx].match(/;/g)?.length ?? 0) > (lines[headerIdx].match(/,/g)?.length ?? 0) ? ';' : ','
  const header = splitLine(lines[headerIdx], sep).map(norm)
  const col = (...names: string[]) => header.findIndex((h) => names.includes(h))
  const dateCol = col('date', 'day', 'timestamp', 'time', 'datetime', 'measured_at', 'acquired_at')
  const missionDayCol = col('mission_day', 'missionday')
  if (dateCol < 0 && missionDayCol < 0) throw new Error('The CSV needs a "date" (or "mission_day") column.')
  const indCol = col('indicator', 'parameter', 'metric', 'measure', 'type')
  const valCol = col('value', 'reading', 'result')
  const layout: 'long' | 'wide' = indCol >= 0 && valCol >= 0 ? 'long' : 'wide'
  const qualCol = col('quality', 'quality_flag', 'flag')
  const wideCols = header.map((h, i) => ({ i, id: ALIASES[h] ?? null, q: header.indexOf(`${h}_quality`) })).filter((c) => c.id)
  if (layout === 'wide' && !wideCols.length) {
    throw new Error('No known indicator columns found. Use a long layout (date,indicator,value) or columns such as resting_hr, sleep_duration, spo2.')
  }

  const values = new Map<DailyIndicatorId, Map<number, DailyValue>>()
  const issues: ImportIssue[] = []
  let rowsRead = 0
  let rowsUsed = 0
  let first = null as string | null
  let last = null as string | null
  const put = (id: DailyIndicatorId, day: number, date: string, v: number | null, q: QualityFlag) => {
    if (!values.has(id)) values.set(id, new Map())
    values.get(id)!.set(day, { date, missionDay: day, value: v, quality: v === null ? 'missing' : q })
    rowsUsed++
  }

  for (let li = headerIdx + 1; li < lines.length; li++) {
    const raw = lines[li]
    if (!raw.trim() || raw.trim().startsWith('#')) continue
    rowsRead++
    const cells = splitLine(raw, sep)
    const lineNo = li + 1
    let date: string | null = null
    let day: number | null = null
    if (dateCol >= 0) date = toDate(cells[dateCol] ?? '')
    if (missionDayCol >= 0 && cells[missionDayCol]) day = Number(cells[missionDayCol]) || null
    if (!date && day) date = new Date(Date.parse(`${missionStartDate}T00:00:00Z`) + (day - 1) * DAY_MS).toISOString().slice(0, 10)
    if (!date) {
      issues.push({ line: lineNo, message: `Unreadable date "${cells[dateCol] ?? ''}"` })
      continue
    }
    day ??= dayOf(date, missionStartDate)
    if (day < 1) {
      issues.push({ line: lineNo, message: `Date ${date} is before the mission start (${missionStartDate})` })
      continue
    }
    first = !first || date < first ? date : first
    last = !last || date > last ? date : last

    if (layout === 'long') {
      const id = indicatorOf(cells[indCol] ?? '')
      if (!id) {
        issues.push({ line: lineNo, message: `Unknown indicator "${cells[indCol] ?? ''}"` })
        continue
      }
      const q = toQuality(qualCol >= 0 ? cells[qualCol] : undefined)
      if (!q) {
        issues.push({ line: lineNo, message: `Unknown quality "${cells[qualCol]}" (use good, uncertain, poor or missing)` })
        continue
      }
      const v = toNumber(cells[valCol] ?? '', sep)
      if (v === null && q !== 'missing') {
        issues.push({ line: lineNo, message: `Value "${cells[valCol] ?? ''}" is not a number` })
        continue
      }
      put(id, day, date, v, q)
    } else {
      for (const c of wideCols) {
        const cell = cells[c.i] ?? ''
        const q = toQuality(c.q >= 0 ? cells[c.q] : undefined) ?? 'good'
        const v = toNumber(cell, sep)
        if (!cell) continue
        if (v === null) {
          issues.push({ line: lineNo, message: `${header[c.i]}: "${cell}" is not a number` })
          continue
        }
        put(c.id!, day, date, v, q)
      }
    }
  }

  const series: DailyIndicatorSeries[] = DAILY_INDICATOR_ORDER.filter((id) => values.has(id)).map((id) => {
    const byDay = values.get(id)!
    const maxDay = Math.max(...byDay.keys())
    // Days without a row are explicit gaps, never interpolated.
    const days: DailyValue[] = []
    for (let d = 1; d <= maxDay; d++) {
      days.push(byDay.get(d) ?? { date: new Date(Date.parse(`${missionStartDate}T00:00:00Z`) + (d - 1) * DAY_MS).toISOString().slice(0, 10), missionDay: d, value: null, quality: 'missing' })
    }
    const baseline = baselineOf(id, days)
    return {
      crewId,
      indicator: id,
      unit: DAILY_INDICATORS[id].unit,
      days,
      baseline: baseline ? { ...baseline, basis: baseline.basis.replace('Reference data set.', `Imported from ${fileName}.`) } : null,
      source: `Imported from ${fileName}`,
      simulated: false,
      origin: 'import' as const,
    }
  })
  if (!series.length) throw new Error('No usable measurement found in the CSV.')
  return { series, rowsRead, rowsUsed, issues, layout, firstDate: first, lastDate: last }
}

export const BASELINE_NOTE = `The personal baseline uses mission days ${BASELINE_DAYS.from}–${BASELINE_DAYS.to}: import at least 5 good readings in those days for each indicator.`
