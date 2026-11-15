import type { SleepAidPlanEntry } from '../domain/types'
import { coverageOf, isPlanned, nightLabel } from '../domain/sleepPlan'
import { initialsOf } from '../domain/overview'
import { activityAfterNight, involves } from '../domain/missionPlan'

export interface SleepGridCrew {
  id: string
  displayName: string
}

/**
 * Nights as columns, crew members as rows, coverage at the bottom.
 * The viewer's own future nights are toggles; everything else is read-only.
 * A night where nobody would stay without a sleep aid is marked with a shape,
 * a word and a tint — never colour alone.
 */
export function SleepGrid({
  nights,
  today,
  crew,
  entries,
  me,
  busyNight,
  onToggle,
  missionStart,
}: {
  nights: string[]
  today: string
  crew: SleepGridCrew[]
  entries: SleepAidPlanEntry[]
  me: string | null
  busyNight?: string | null
  onToggle?: (night: string) => void
  /** Shows the (simulated) activity of the following morning above each night. */
  missionStart?: string
}) {
  const ids = crew.map((c) => c.id)
  const ordered = me ? [...crew.filter((c) => c.id === me), ...crew.filter((c) => c.id !== me)] : crew
  const cover = nights.map((n) => coverageOf(entries, ids, n))
  return (
    <div className="sleep-grid-wrap">
      <table className="sleep-grid">
        <caption className="sr-only">Planned sleep-aid nights per crew member, and how many stay without one</caption>
        <thead>
          <tr>
            <th scope="col" className="sg-corner">
              <span className="sr-only">Crew member</span>
            </th>
            {nights.map((n, i) => {
              const l = nightLabel(n)
              return (
                <th key={n} scope="col" className={`sg-day${n === today ? ' is-today' : ''}${n < today ? ' is-past' : ''}${cover[i].uncovered ? ' is-uncovered' : ''}`}>
                  <span className="sg-weekday">{l.weekday}</span>
                  <span className="sg-date">{l.day}</span>
                  {n === today && <span className="sr-only">(tonight)</span>}
                </th>
              )
            })}
          </tr>
          {missionStart && (
            <tr className="sg-activity-row">
              <th scope="row" className="sg-person sg-foot-label">
                Next morning
              </th>
              {nights.map((n) => {
                const a = activityAfterNight(n, missionStart)
                if (!a) return <td key={n} className={n < today ? 'is-past' : undefined} />
                const who = a.crew.length ? a.crew.map((id) => crew.find((c) => c.id === id)?.displayName ?? id).join(', ') : 'Whole crew'
                const mine = !!me && involves(a, me)
                const text = `Morning after: ${a.label}, ${a.startUtc} UTC · ${who} (simulated timeline)`
                return (
                  <td key={n} className={n < today ? 'is-past' : undefined}>
                    <span className={`sg-activity${mine ? ' is-mine' : ''}`} title={text}>
                      {a.short}
                      <span className="sr-only">: {text}</span>
                    </span>
                  </td>
                )
              })}
            </tr>
          )}
        </thead>
        <tbody>
          {ordered.map((c) => (
            <tr key={c.id}>
              <th scope="row" className="sg-person">
                <span className="avatar avatar-small">{initialsOf(c.displayName)}</span>
                <span className="sg-name">{c.displayName}</span>
                {c.id === me && <span className="pill tone-blue">You</span>}
              </th>
              {nights.map((n, i) => {
                const planned = isPlanned(entries, c.id, n)
                const editable = c.id === me && n >= today && !!onToggle
                const label = `${planned ? 'Remove' : 'Plan'} a sleep aid for the night of ${nightLabel(n).weekday} ${nightLabel(n).day} ${nightLabel(n).month}`
                const cls = `sg-cell${n < today ? ' is-past' : ''}${cover[i].uncovered ? ' is-uncovered' : ''}`
                return (
                  <td key={n} className={cls}>
                    {editable ? (
                      <button
                        type="button"
                        className={`sg-toggle${planned ? ' is-planned' : ''}`}
                        aria-pressed={planned}
                        aria-label={label}
                        title={label}
                        disabled={busyNight === n}
                        onClick={() => onToggle!(n)}
                      >
                        {planned ? <Moon /> : <span className="sg-plus" aria-hidden="true">+</span>}
                      </button>
                    ) : planned ? (
                      <span className="sg-mark" title="Sleep aid planned">
                        <Moon />
                        <span className="sr-only">Sleep aid planned</span>
                      </span>
                    ) : (
                      <span className="sg-empty" aria-hidden="true" />
                    )}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <th scope="row" className="sg-person sg-foot-label">
              Without a sleep aid
            </th>
            {cover.map((c) => (
              <td
                key={c.night}
                title={
                  c.available
                    ? `Ready to respond: ${crew.filter((m) => !c.planned.includes(m.id)).map((m) => m.displayName).join(', ')}`
                    : 'Nobody without a sleep aid'
                } className={`sg-cover${c.uncovered ? ' is-uncovered' : ''}${c.night < today ? ' is-past' : ''}`}>
                {c.uncovered ? (
                  <span className="sg-warn" title="Nobody without a sleep aid">
                    <svg width="9" height="8" viewBox="0 0 11 10" aria-hidden="true">
                      <path d="M5.5 0.8 10.4 9.2H0.6Z" fill="currentColor" />
                    </svg>
                    {c.available}/{c.total}
                    <span className="sr-only">: nobody without a sleep aid</span>
                  </span>
                ) : (
                  <span className="sg-ok">
                    {c.available}/{c.total}
                  </span>
                )}
              </td>
            ))}
          </tr>
        </tfoot>
      </table>
    </div>
  )
}

export const Moon = ({ size = 13 }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
    <path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5Z" fill="currentColor" />
  </svg>
)
