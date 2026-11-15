import { MISSION_PLAN, phaseOf } from '../domain/missionPlan'

/**
 * Where the crew is in the mission: day counter and, when mission control has
 * provided a plan (src/mission.config.ts), the current phase on a quiet bar.
 */
export function MissionTimeline({ day }: { day: number }) {
  const { lengthDays, phases } = MISSION_PLAN
  const phase = phaseOf(day)
  const pct = lengthDays ? Math.min(100, Math.max(0, ((day - 0.5) / lengthDays) * 100)) : 0
  return (
    <div className={`mission${phase ? '' : ' is-compact'}`} aria-label={`Mission day ${day}${lengthDays ? ` of ${lengthDays}` : ''}${phase ? `, ${phase.label}` : ''}.`} role="group">
      <div className="mission-day">
        <span className="mission-day-label">Mission day</span>
        <span className="mission-day-value">
          {day}
          {lengthDays && <span className="mission-day-total"> of {lengthDays}</span>}
        </span>
      </div>
      {phase && (
        <div className="mission-track-wrap">
          <span className="mission-phase-label">
            <strong>{phase.label}</strong>
            <span className="mission-phase-day">
              day {day - phase.fromDay + 1} of {phase.toDay - phase.fromDay + 1}
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
            {lengthDays && <span className="mission-marker" style={{ left: `${pct}%` }} />}
          </div>
        </div>
      )}
    </div>
  )
}
