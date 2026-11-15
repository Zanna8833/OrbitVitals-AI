import { MISSION_PLAN, phaseOf } from '../domain/missionPlan'

/**
 * Where the crew is in the mission: day counter, phase, and a quiet
 * phase bar with a marker for today. Simulated plan (labelled as such).
 */
export function MissionTimeline({ day }: { day: number }) {
  const { lengthDays, phases } = MISSION_PLAN
  const phase = phaseOf(day)
  const pct = Math.min(100, Math.max(0, ((day - 0.5) / lengthDays) * 100))
  return (
    <div className="mission" aria-label={`Mission day ${day} of ${lengthDays}, ${phase.label}. Simulated mission plan.`} role="group">
      <div className="mission-day">
        <span className="mission-day-label">Mission day</span>
        <span className="mission-day-value">
          {day}
          <span className="mission-day-total"> of {lengthDays}</span>
        </span>
      </div>
      <div className="mission-track-wrap">
        <span className="mission-phase-label">
          <strong>{phase.label}</strong>
          <span className="mission-phase-day">
            day {day - phase.fromDay + 1} of {phase.toDay - phase.fromDay + 1}
          </span>
          <span className="mission-sim" title="The mission plan is simulated in this demo">
            Simulated
          </span>
        </span>
        <div className="mission-track" aria-hidden="true">
          {phases.map((p) => {
            const state = day > p.toDay ? 'done' : day >= p.fromDay ? 'current' : 'next'
            return (
              <span
                key={p.id}
                className={`mission-phase is-${state}`}
                style={{ flexGrow: p.toDay - p.fromDay + 1 }}
                title={`${p.label} · days ${p.fromDay}–${p.toDay}`}
              />
            )
          })}
          <span className="mission-marker" style={{ left: `${pct}%` }} />
        </div>
      </div>
    </div>
  )
}
