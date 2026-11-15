import { MISSION_PLAN, phaseOf } from '../domain/missionPlan'
import { useAppState } from '../state/AppState'

/**
 * Where the crew is in the mission: day counter and, when mission control has
 * provided a plan (src/mission.config.ts), the current phase. With `today`,
 * the bar can be dragged back to any past day that has data (1…today) to see
 * the astronauts as they were; future days cannot be chosen.
 */
export function MissionTimeline({ day, today }: { day: number; today?: number }) {
  const { setViewDay } = useAppState()
  const { lengthDays, phases } = MISSION_PLAN
  const phase = phaseOf(day)
  const interactive = today !== undefined && today > 1
  const past = interactive && day < today
  const pct = lengthDays ? Math.min(100, Math.max(0, ((day - 0.5) / lengthDays) * 100)) : 0
  return (
    <div className={`mission${phase ? '' : ' is-compact'}${interactive ? ' is-interactive' : ''}${past ? ' is-past' : ''}`} role="group" aria-label={`Mission day ${day}${lengthDays ? ` of ${lengthDays}` : ''}${phase ? `, ${phase.label}` : ''}${past ? ', past day' : ''}.`}>
      <div className="mission-day">
        <span className="mission-day-label">{past ? 'Viewing day' : 'Mission day'}</span>
        <span className="mission-day-value">
          {day}
          {lengthDays && <span className="mission-day-total"> of {lengthDays}</span>}
        </span>
      </div>
      {phase && !interactive && (
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
              return <span key={p.id} className={`mission-phase is-${state}`} style={{ flexGrow: p.toDay - p.fromDay + 1 }} title={`${p.label} · days ${p.fromDay}–${p.toDay}`} />
            })}
            {lengthDays && <span className="mission-marker" style={{ left: `${pct}%` }} />}
          </div>
        </div>
      )}
      {interactive && (
        <div className="mission-scrub">
          <span className="mission-phase-label">
            <strong>{phase ? phase.label : past ? `${today - day} ${today - day === 1 ? 'day' : 'days'} ago` : 'Today'}</strong>
            {past ? (
              <button type="button" className="text-button mission-today" onClick={() => setViewDay(null)}>
                Back to today
              </button>
            ) : (
              <span className="mission-phase-day">drag to look back</span>
            )}
          </span>
          <input
            type="range"
            className="mission-range"
            min={1}
            max={today}
            value={day}
            aria-label="Mission day to view"
            aria-valuetext={`Mission day ${day}${past ? '' : ', today'}`}
            onChange={(e) => {
              const d = Number(e.target.value)
              setViewDay(d >= today ? null : d)
            }}
          />
        </div>
      )}
    </div>
  )
}
