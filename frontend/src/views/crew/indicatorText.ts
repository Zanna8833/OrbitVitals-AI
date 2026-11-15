import type { DailyIndicatorId } from '../../domain/types'

/** Plain-language context shown in the indicator sheet. Not medical advice. */
export const INDICATOR_CONTEXT: Record<DailyIndicatorId, string> = {
  resting_hr: 'A resting reading helps you compare cardiovascular patterns over time, considering sleep, activity and sensor quality.',
  hrv_rmssd: 'Heart-rate variability can fluctuate with recovery and activity. This trend is not a diagnosis or stress score.',
  bp_systolic: 'Review blood pressure as a paired systolic/diastolic reading and consider the measurement conditions.',
  bp_diastolic: 'Review both pressure readings together and verify the cuff and acquisition conditions.',
  resting_spo2: 'Oxygen saturation is one piece of the respiratory picture. Check the instrument and signal quality before interpretation.',
  resting_resp_rate: 'Respiratory measurements can be affected by movement and sensor contact. Compare similar resting contexts.',
  body_temperature: 'Temperature readings depend on the device and measurement method. Compare readings collected in similar conditions.',
  sleep_duration: 'Sleep duration is relevant to fatigue and performance, but does not describe sleep quality on its own.',
  sleep_efficiency: 'This is a device-derived estimate, not a clinical sleep assessment. Review with duration and self-reported sleep.',
  activity_minutes: 'Exercise is part of long-duration mission routines. The duration alone does not measure fitness or bone health.',
  active_energy: 'Energy spent in exercise sessions, as estimated by the device. Read it with exercise time and what you eat.',
  body_mass: 'Changes in body mass may be worth tracking alongside nutrition and activity. This is not a measure of bone density.',
}
