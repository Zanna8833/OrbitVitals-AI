import { useRef, useState, type KeyboardEvent, type PointerEvent } from 'react'
import { MISSION_PLAN, phaseOf } from '../domain/missionPlan'
import { useAppState } from '../state/AppState'

/**
 * Where the crew is in the mission: day counter and, when mission control has
 * provided a plan (src/mission.config.ts), the current phase. With `today`,
 * a slim day track lets the viewer slide back to any past day (1…today) to
 * see the astronauts as they were; future days cannot be chosen.
 */
export function MissionTimeline({ day, today }: { day: number; today?: number }) {
  const { setViewDay } = useAppState()
  const { lengthDays, phases } = MISSION_PLAN
  const phase = phaseOf(day)
  const interactive = today !== undefined && today > 1
  const past = interactive && day < today
  const [preview, setPreview] = useState<number | null>(null)
  const go = (d: number) => setViewDay(today === undefined || d >= today ? null : Math.max(1, d))
  const shown = preview ?? day
  const pct = lengthDays ? Math.min(100, Math.max(0, ((day - 0.5) / lengthDays) * 100)) : 0
  return (
    <div className={`mission${phase ? '' : ' is-compact'}${interactive ? ' is-interactive' : ''}${past ? ' is-past' : ''}`} role="group" aria-label={`Mission day ${day}${lengthDays ? ` of ${lengthDays}` : ''}${phase ? `, ${phase.label}` : ''}${past ? ', past day' : ''}.`}>
      <div className="mission-day">
        <span className="mission-day-label">{shown < (today ?? shown) ? 'Viewing day' : 'Mission day'}</span>
        <span className="mission-day-value">
          {shown}
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
      {interactive && <DayScrubber day={day} today={today} onPreview={setPreview} onCommit={go} />}
    </div>
  )
}

/**
 * Slim track from day 1 to today. The thumb follows the pointer smoothly and
 * snaps to whole days; data are loaded only when it is released, so dragging
 * never stutters. Click anywhere on the track, use the arrow keys, or Home/End.
 */
function DayScrubber({ day, today, onPreview, onCommit }: { day: number; today: number; onPreview: (d: number | null) => void; onCommit: (d: number) => void }) {
  const trackRef = useRef<HTMLDivElement>(null)
  const [drag, setDrag] = useState<{ x: number; d: number } | null>(null)
  const span = Math.max(1, today - 1)
  const pctOf = (d: number) => ((d - 1) / span) * 100
  const read = (clientX: number) => {
    const r = trackRef.current!.getBoundingClientRect()
    const f = Math.min(1, Math.max(0, (clientX - r.left) / r.width))
    return { x: f * 100, d: Math.round(1 + f * span) }
  }
  const move = (e: PointerEvent<HTMLDivElement>) => {
    if (!drag) return
    const next = read(e.clientX)
    setDrag(next)
    onPreview(next.d)
  }
  const end = (e: PointerEvent<HTMLDivElement>) => {
    if (!drag) return
    const { d } = read(e.clientX)
    setDrag(null)
    onPreview(null)
    if (d !== day) onCommit(d)
  }
  const key = (e: KeyboardEvent<HTMLDivElement>) => {
    const to = e.key === 'ArrowLeft' || e.key === 'ArrowDown' ? day - 1 : e.key === 'ArrowRight' || e.key === 'ArrowUp' ? day + 1 : e.key === 'Home' ? 1 : e.key === 'End' ? today : null
    if (to === null) return
    e.preventDefault()
    const d = Math.min(today, Math.max(1, to))
    if (d !== day) onCommit(d)
  }
  const shown = drag?.d ?? day
  const thumb = drag ? drag.x : pctOf(day)
  const labels = [...new Set([1, ...Array.from({ length: Math.floor(today / 7) }, (_, i) => (i + 1) * 7).filter((d) => pctOf(d) <= 90)])]
  return (
    <div className="scrub">
      <div className="scrub-main">
      <div
        ref={trackRef}
        className={`scrub-track${drag ? ' is-dragging' : ''}`}
        role="slider"
        tabIndex={0}
        aria-label="Mission day to view"
        aria-valuemin={1}
        aria-valuemax={today}
        aria-valuenow={shown}
        aria-valuetext={shown === today ? `Mission day ${shown}, today` : `Mission day ${shown}`}
        onPointerDown={(e) => {
          e.currentTarget.setPointerCapture(e.pointerId)
          const next = read(e.clientX)
          setDrag(next)
          onPreview(next.d)
        }}
        onPointerMove={move}
        onPointerUp={end}
        onPointerCancel={() => {
          setDrag(null)
          onPreview(null)
        }}
        onKeyDown={key}
      >
        <span className="scrub-rail" aria-hidden="true">
          <span className="scrub-fill" style={{ width: `${thumb}%` }} />
          {today <= 60 &&
            Array.from({ length: today }, (_, i) => i + 1).map((d) => (
              <span key={d} className={`scrub-tick${d <= shown ? ' is-in' : ''}`} style={{ left: `${pctOf(d)}%` }} />
            ))}
        </span>
        <span className="scrub-thumb" style={{ left: `${thumb}%` }} aria-hidden="true">
          {drag && <span className="scrub-bubble">{shown === today ? 'Today' : `Day ${shown}`}</span>}
        </span>
      </div>
      <div className="scrub-labels">
        {labels.map((d) => (
          <span key={d} style={{ left: `${pctOf(d)}%` }} aria-hidden="true">
            {d}
          </span>
        ))}
      </div>
      </div>
      <button type="button" className="scrub-today" disabled={day === today} title="Back to today" onClick={() => onCommit(today)}>
        Today
      </button>
    </div>
  )
}
