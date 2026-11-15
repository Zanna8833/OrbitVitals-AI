import { useState } from 'react'
import type { SleepAidPlanEntry } from '../domain/types'
import { addDays, coverageOf, isPlanned, nightLabel, wouldUncover } from '../domain/sleepPlan'
import { activityAfterNight, involves } from '../domain/missionPlan'
import { initialsOf } from '../domain/overview'
import { PillIcon } from './SleepGrid'
import { Segmented, Sheet } from './ui'

/**
 * Month view of the sleeping-pill plan, like a phone calendar: each day shows
 * who planned a pill (initials), the activity of the next morning and a
 * warning when nobody would stay ready. Tap a day to edit it.
 */

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
const WEEK = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

export function monthOf(date: string): string {
  return date.slice(0, 7)
}
export function shiftMonth(month: string, by: number): string {
  const [y, m] = month.split('-').map(Number)
  const d = new Date(Date.UTC(y, m - 1 + by, 1))
  return d.toISOString().slice(0, 7)
}

/** Monday-first weeks covering the month. */
function weeksOf(month: string): string[][] {
  const first = `${month}-01`
  const dow = (new Date(`${first}T00:00:00Z`).getUTCDay() + 6) % 7
  const start = addDays(first, -dow)
  const weeks: string[][] = []
  let d = start
  do {
    weeks.push(Array.from({ length: 7 }, (_, i) => addDays(d, i)))
    d = addDays(d, 7)
  } while (d.slice(0, 7) === month)
  return weeks
}

export function SleepMonth({
  month,
  onMonth,
  today,
  crew,
  entries,
  me,
  missionStart,
  onPick,
  onAdd,
  minMonth,
  maxMonth,
}: {
  month: string
  onMonth: (m: string) => void
  today: string
  crew: { id: string; displayName: string }[]
  entries: SleepAidPlanEntry[]
  me: string
  missionStart: string
  onPick: (night: string) => void
  onAdd: () => void
  minMonth: string
  maxMonth: string
}) {
  const ids = crew.map((c) => c.id)
  const [y, m] = month.split('-').map(Number)
  return (
    <div className="month">
      <div className="month-head">
        <h2 className="month-title">
          {MONTHS[m - 1]} <span className="muted">{y}</span>
        </h2>
        <div className="month-nav">
          <button type="button" className="icon-button" aria-label="Previous month" disabled={month <= minMonth} onClick={() => onMonth(shiftMonth(month, -1))}>
            ‹
          </button>
          <button type="button" className="btn btn-small" disabled={month === monthOf(today)} onClick={() => onMonth(monthOf(today))}>
            Today
          </button>
          <button type="button" className="icon-button" aria-label="Next month" disabled={month >= maxMonth} onClick={() => onMonth(shiftMonth(month, 1))}>
            ›
          </button>
          <button type="button" className="btn btn-primary btn-small month-add" onClick={onAdd} aria-label="Plan a sleeping pill">
            + Add
          </button>
        </div>
      </div>
      <div className="month-grid" role="grid" aria-label={`Sleeping-pill plan, ${MONTHS[m - 1]} ${y}`}>
        <div className="month-row month-weekdays" role="row">
          {WEEK.map((w) => (
            <span key={w} role="columnheader">
              {w}
            </span>
          ))}
        </div>
        {weeksOf(month).map((week) => (
          <div key={week[0]} className="month-row" role="row">
            {week.map((d) => {
              const inMonth = monthOf(d) === month
              const cov = coverageOf(entries, ids, d)
              const act = activityAfterNight(d, missionStart)
              const planned = crew.filter((c) => isPlanned(entries, c.id, d))
              const l = nightLabel(d)
              const label = `${l.weekday} ${l.day} ${l.month}: ${planned.length ? `sleeping pill planned by ${planned.map((c) => c.displayName).join(', ')}` : 'no sleeping pill planned'}${cov.uncovered ? ', nobody ready' : ''}${act ? `, ${act.label} next morning` : ''}`
              return (
                <button
                  key={d}
                  type="button"
                  role="gridcell"
                  className={`day${inMonth ? '' : ' is-outside'}${d < today ? ' is-past' : ''}${d === today ? ' is-today' : ''}${cov.uncovered ? ' is-uncovered' : ''}`}
                  aria-label={label}
                  onClick={() => onPick(d)}
                >
                  <span className="day-num">{Number(d.slice(8))}</span>
                  {act && <span className={`day-act${involves(act, me) ? ' is-mine' : ''}`}>{act.short}</span>}
                  <span className="day-pills" aria-hidden="true">
                    {planned.map((c) => (
                      <span key={c.id} className={`day-pill${c.id === me ? ' is-me' : ''}`}>
                        {initialsOf(c.displayName)}
                      </span>
                    ))}
                  </span>
                  {cov.uncovered && (
                    <span className="day-warn" aria-hidden="true">
                      ▲
                    </span>
                  )}
                </button>
              )
            })}
          </div>
        ))}
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Edit one night, like opening a day in a phone calendar              */
/* ------------------------------------------------------------------ */

export function DaySheet({
  night,
  today,
  crew,
  entries,
  me,
  missionStart,
  busy,
  onSet,
  onClose,
}: {
  night: string | null
  today: string
  crew: { id: string; displayName: string }[]
  entries: SleepAidPlanEntry[]
  me: string
  missionStart: string
  busy: boolean
  onSet: (crewId: string, night: string, planned: boolean) => void
  onClose: () => void
}) {
  const [warn, setWarn] = useState<string | null>(null)
  const ids = crew.map((c) => c.id)
  const l = night ? nightLabel(night) : null
  const past = !!night && night < today
  const cov = night ? coverageOf(entries, ids, night) : null
  const act = night ? activityAfterNight(night, missionStart) : null
  const close = () => {
    setWarn(null)
    onClose()
  }
  return (
    <Sheet open={!!night} title={l ? `Night of ${l.weekday} ${l.day} ${l.month}` : ''} onClose={close}>
      {night && cov && (
        <div className="stack">
          <p className={`day-status${cov.uncovered ? ' is-attention' : ''}`}>
            {cov.uncovered ? '▲ Nobody stays without a sleeping pill.' : `${cov.available} of ${cov.total} stay without a sleeping pill, ready to respond.`}
          </p>
          {act && (
            <p className="sleep-activity-note">
              <span className={`sg-activity${involves(act, me) ? ' is-mine' : ''}`}>{act.short}</span>
              <span>
                Next morning: <strong>{act.label}</strong> at {act.startUtc} UTC ({act.crew.length ? act.crew.map((id) => crew.find((c) => c.id === id)?.displayName ?? id).join(', ') : 'whole crew'}).
              </span>
            </p>
          )}
          <ul className="day-people">
            {crew.map((c) => {
              const on = isPlanned(entries, c.id, night)
              return (
                <li key={c.id}>
                  <span className="avatar avatar-small">{initialsOf(c.displayName)}</span>
                  <span className="day-person">
                    {c.displayName}
                    {c.id === me && <span className="pill tone-blue">You</span>}
                  </span>
                  <label className="day-switch">
                    <span className={on ? 'pill-planned' : 'muted'}>
                      {on ? (
                        <>
                          <PillIcon size={13} /> Sleeping pill
                        </>
                      ) : (
                        'No pill'
                      )}
                    </span>
                    <input
                      type="checkbox"
                      role="switch"
                      checked={on}
                      disabled={past || busy}
                      aria-label={`Sleeping pill for ${c.displayName}`}
                      onChange={(e) => {
                        const planned = e.target.checked
                        if (planned && wouldUncover(entries, ids, c.id, night)) {
                          setWarn(c.id)
                          return
                        }
                        setWarn(null)
                        onSet(c.id, night, planned)
                      }}
                    />
                  </label>
                  {warn === c.id && (
                    <div className="day-warn-box">
                      <span>Nobody would stay ready that night.</span>
                      <button
                        type="button"
                        className="text-button"
                        onClick={() => {
                          setWarn(null)
                          onSet(c.id, night, true)
                        }}
                      >
                        Plan anyway
                      </button>
                    </div>
                  )}
                </li>
              )
            })}
          </ul>
          {past && <p className="fineprint">Past nights are kept as a record and cannot be changed.</p>}
          <p className="fineprint">Only the night is recorded: no medicine and no dose.</p>
          <button type="button" className="btn btn-primary btn-block" onClick={close}>
            Done
          </button>
        </div>
      )}
    </Sheet>
  )
}

/* ------------------------------------------------------------------ */
/* Add: a night or a repeating series, like a new calendar event        */
/* ------------------------------------------------------------------ */

type Repeat = 'none' | '2' | '3' | '7'

export function AddPlanSheet({
  open,
  today,
  lastNight,
  crew,
  entries,
  me,
  onAdd,
  onClose,
}: {
  open: boolean
  today: string
  lastNight: string
  crew: { id: string; displayName: string }[]
  entries: SleepAidPlanEntry[]
  me: string
  onAdd: (crewId: string, nights: string[]) => Promise<void>
  onClose: () => void
}) {
  const [who, setWho] = useState(me)
  const [date, setDate] = useState(today)
  const [repeat, setRepeat] = useState<Repeat>('none')
  const [until, setUntil] = useState(addDays(today, 13))
  const ids = crew.map((c) => c.id)
  const step = repeat === 'none' ? 0 : Number(repeat)
  const nights: string[] = []
  if (date >= today && date <= lastNight) {
    if (!step) nights.push(date)
    else for (let d = date; d <= until && d <= lastNight && nights.length < 60; d = addDays(d, step)) nights.push(d)
  }
  // Nights that would leave nobody ready are skipped and listed.
  const plan: SleepAidPlanEntry[] = [...entries]
  const ok: string[] = []
  const skipped: string[] = []
  for (const n of nights) {
    if (isPlanned(plan, who, n)) continue
    if (wouldUncover(plan, ids, who, n)) skipped.push(n)
    else {
      ok.push(n)
      plan.push({ crewId: who, night: n, updatedAt: '', simulated: true })
    }
  }
  const fmt = (n: string) => `${nightLabel(n).weekday} ${nightLabel(n).day} ${nightLabel(n).month}`
  return (
    <Sheet open={open} title="Plan a sleeping pill" onClose={onClose}>
      {open && (
        <form
          className="stack"
          onSubmit={async (e) => {
            e.preventDefault()
            if (!ok.length) return
            await onAdd(who, ok)
            onClose()
          }}
        >
          <label className="field">
            <span className="field-label">Who</span>
            <select value={who} onChange={(e) => setWho(e.target.value)}>
              {crew.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.displayName}
                  {c.id === me ? ' (you)' : ''}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span className="field-label">Night of</span>
            <input type="date" value={date} min={today} max={lastNight} onChange={(e) => setDate(e.target.value)} />
          </label>
          <div className="field">
            <span className="field-label">Repeat</span>
            <Segmented
              size="small"
              label="Repeat"
              value={repeat}
              onChange={setRepeat}
              options={[
                { value: 'none', label: 'Never' },
                { value: '2', label: 'Every 2 nights' },
                { value: '3', label: 'Every 3 nights' },
                { value: '7', label: 'Weekly' },
              ]}
            />
          </div>
          {repeat !== 'none' && (
            <label className="field">
              <span className="field-label">Until</span>
              <input type="date" value={until} min={date} max={lastNight} onChange={(e) => setUntil(e.target.value)} />
            </label>
          )}
          <div className="add-summary">
            {ok.length ? (
              <p>
                <strong>{ok.length === 1 ? '1 night' : `${ok.length} nights`}</strong>: {ok.slice(0, 6).map(fmt).join(', ')}
                {ok.length > 6 ? ` and ${ok.length - 6} more` : ''}.
              </p>
            ) : (
              <p className="muted">Nothing new to plan with these settings.</p>
            )}
            {skipped.length > 0 && (
              <p className="text-attention">
                Skipped, nobody else would stay ready: {skipped.map(fmt).join(', ')}.
              </p>
            )}
          </div>
          <button type="submit" className="btn btn-primary btn-block" disabled={!ok.length}>
            Add to the plan
          </button>
          <p className="fineprint">Nights can be planned up to {fmt(lastNight)}. Only the night is recorded: no medicine and no dose.</p>
        </form>
      )}
    </Sheet>
  )
}
