import type { DailyIndicatorId, ParameterId } from '../domain/types'
import type { Tone } from './ui'

/** Category colour of a metric, as in a health app: heart, respiration, rest, activity, body. */
export function toneOf(id: DailyIndicatorId | ParameterId): Tone {
  switch (id) {
    case 'resting_hr':
    case 'heart_rate':
    case 'hrv_rmssd':
    case 'bp_systolic':
    case 'bp_diastolic':
      return 'heart'
    case 'resting_spo2':
    case 'spo2':
    case 'resting_resp_rate':
    case 'resp_rate':
      return 'respiration'
    case 'sleep_duration':
    case 'sleep_efficiency':
      return 'rest'
    case 'activity_minutes':
    case 'motion':
      return 'activity'
    default:
      return 'body'
  }
}
