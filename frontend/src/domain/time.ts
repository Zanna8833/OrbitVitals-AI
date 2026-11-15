/** Time helpers. All display is in UTC and always labelled as such. */

export const toMs = (iso: string): number => Date.parse(iso)
export const toIso = (ms: number): string => new Date(ms).toISOString().replace('.000Z', 'Z')

const pad = (n: number) => String(n).padStart(2, '0')

export function formatClock(iso: string | number, withSeconds = true): string {
  const d = new Date(typeof iso === 'number' ? iso : toMs(iso))
  const hm = `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`
  return withSeconds ? `${hm}:${pad(d.getUTCSeconds())}` : hm
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

export function formatDate(iso: string | number): string {
  const d = new Date(typeof iso === 'number' ? iso : toMs(iso))
  return `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}`
}

/** "10:15:20 UTC" */
export function formatUtc(iso: string | number, withSeconds = true): string {
  return `${formatClock(iso, withSeconds)} UTC`
}

/** Relative age with respect to the simulated "now": "40 s ago", "18 min ago". */
export function formatAge(iso: string, nowIso: string): string {
  const s = Math.max(0, Math.round((toMs(nowIso) - toMs(iso)) / 1000))
  if (s < 60) return `${s} s ago`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m} min ago`
  const h = Math.floor(m / 60)
  return `${h} h ${m % 60} min ago`
}

const DAY_MS = 24 * 60 * 60 * 1000

/** Mission day of a UTC instant: the start date is day 1. */
export function missionDayOf(nowIso: string, missionStartDate: string): number {
  return Math.floor((toMs(nowIso.slice(0, 10)) - toMs(missionStartDate)) / DAY_MS) + 1
}

export function formatDuration(ms: number): string {
  const s = Math.round(ms / 1000)
  if (s < 60) return `${s} s`
  const m = Math.floor(s / 60)
  const r = s % 60
  return r ? `${m} min ${r} s` : `${m} min`
}

/** "A", "A and B", "A, B and C". */
export function joinNames(names: string[]): string {
  if (names.length <= 2) return names.join(' and ')
  return `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`
}
