import type { ReactNode } from 'react'
import type { DailyIndicatorId, ParameterId } from '../domain/types'

type MetricId = DailyIndicatorId | ParameterId

type GlyphTheme = 'heart' | 'respiration' | 'rest' | 'activity' | 'body'

const themes: Record<MetricId, GlyphTheme> = {
  heart_rate: 'heart', resting_hr: 'heart', hrv_rmssd: 'heart',
  bp_systolic: 'heart', bp_diastolic: 'heart',
  spo2: 'respiration', resting_spo2: 'respiration',
  resp_rate: 'respiration', resting_resp_rate: 'respiration',
  sleep_duration: 'rest', sleep_efficiency: 'rest',
  activity_minutes: 'activity', motion: 'activity', active_energy: 'activity',
  body_temperature: 'body', body_mass: 'body',
}

/** Meaningful, single-weight line icons. Color is supplementary to the visible label. */
export function MetricGlyph({ id, size = 20 }: { id: MetricId; size?: number }) {
  const type = themes[id]
  const common = { fill: 'none', stroke: 'currentColor', strokeWidth: 1.8, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const }
  let content: ReactNode
  if (id === 'bp_systolic' || id === 'bp_diastolic') {
    content = <><rect x="3" y="7" width="12" height="9" rx="2.5"/><path d="M15 11.5h3a3 3 0 0 1 3 3v2"/><circle cx="18" cy="19" r="2"/><path d="M7 11h4"/></>
  } else if (id === 'resting_hr' || id === 'heart_rate' || id === 'hrv_rmssd') {
    content = <><path d="M20.4 5.8a5 5 0 0 0-7.1 0L12 7.1l-1.3-1.3a5 5 0 0 0-7.1 7.1L12 21l8.4-8.1a5 5 0 0 0 0-7.1Z"/><path d="M5.5 12h3l1.5-2.5 2.2 5 1.6-2.5h4.7"/></>
  } else if (id === 'resting_spo2' || id === 'spo2') {
    content = <><path d="M12 2C9 6 5 10 5 14a7 7 0 0 0 14 0c0-4-4-8-7-12Z"/><path d="M9 15.5a3 3 0 0 0 3 2.5"/></>
  } else if (id === 'resting_resp_rate' || id === 'resp_rate') {
    content = <><path d="M12 5v15M12 9c-2.5-3.2-5.2-2-6.8 1.2C3.8 13.4 3 17.8 4.4 19.2c1.5 1.3 5.2-.1 7.6-3.3M12 9c2.5-3.2 5.2-2 6.8 1.2 1.4 3.2 2.2 7.6.8 9-1.5 1.3-5.2-.1-7.6-3.3"/></>
  } else if (id === 'sleep_duration' || id === 'sleep_efficiency') {
    content = <><path d="M20.2 15.8A8.5 8.5 0 0 1 8.2 3.8 8.7 8.7 0 1 0 20.2 15.8Z"/><path d="M17 4v4M15 6h4"/></>
  } else if (id === 'body_temperature') {
    content = <><path d="M14 13.6V5a3 3 0 0 0-6 0v8.6a5 5 0 1 0 6 0Z"/><path d="M11 9v8"/><circle cx="11" cy="18" r="1.5"/></>
  } else if (id === 'body_mass') {
    content = <><rect x="3" y="5" width="18" height="15" rx="3"/><path d="M9 9a4.5 4.5 0 0 1 6 0l-3 4-3-4Z"/></>
  } else {
    content = <><circle cx="14" cy="4" r="2"/><path d="m10 9 4 2 2 4m-2-4-4 4-2 6M10 9l-3 4H3m13 2 5 5"/></>
  }
  return <span className={`metric-glyph metric-glyph-${type}`} aria-hidden="true"><svg width={size} height={size} viewBox="0 0 24 24" {...common}>{content}</svg></span>
}
