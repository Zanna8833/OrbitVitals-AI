import { useEffect, useRef } from 'react'
import { MISSION_PLAN, phaseOf } from '../domain/missionPlan'
import { useAppState } from '../state/AppState'

/**
 * Where the crew is in the mission: day counter and, when mission control has
 * provided a plan (src/mission.config.ts), the current phase. With `today`,
 * a row of days (1…today) and two arrows let the viewer open any past day to
 * see the astronauts as they were; future days cannot be chosen.
 */
export function MissionTimeline({ day, today }: { day: number; today?: number }) {
  const { setViewDay } = useAppState()
  const { lengthDays, phases } = MISSION_PLAN
  const phase = phaseOf(day)
  const interactive = today !== undefined && today > 1
  const past = interactive && day < today
  const stripRef = useRef<HTMLDivElement>(null)
  const go = (d: number) => setViewDay(today === undefined || d >= today ? null : Math.max(1, d))
  // Keep the chosen day in sight inside the strip.
  useEffect(() => {
    stripRef.current?.querySelector<HTMLElement>('.day-pill.is-on')?.scrollIntoView({ block: 'nearest', inline: 'center' })
  }, [day])
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
        <div className="day-picker" role="group" aria-label="Choose a mission day to view">
          <button type="button" className="day-step" aria-label="Previous day" disabled={day <= 1} onClick={() => go(day - 1)}>
            ‹
          </button>
          <div className="day-strip" ref={stripRef}>
            {Array.from({ length: today }, (_, i) => i + 1).map((d) => (
              <button
                key={d}
                type="button"
                className={`day-pill${d === day ? ' is-on' : ''}${d === today ? ' is-today' : ''}`}
                aria-pressed={d === day}
                aria-label={d === today ? `Mission day ${d}, today` : `Mission day ${d}`}
                onClick={() => go(d)}
              >
                {d === today ? 'Today' : d}
              </button>
            ))}
          </div>
          <button type="button" className="day-step" aria-label="Next day" disabled={day >= today} onClick={() => go(day + 1)}>
            ›
          </button>
        </div>
      )}
    </div>
  )
}
