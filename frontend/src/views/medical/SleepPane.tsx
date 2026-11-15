import type { CrewMember, SleepAidPlanEntry } from '../../domain/types'
import { addDays, coverageOf, nightLabel, nightsFrom, SLEEP_COVER_RULE } from '../../domain/sleepPlan'
import { PillIcon, SleepGrid } from '../../components/SleepGrid'
import { List, Row } from '../../components/ui'
import { activityAfterNight } from '../../domain/missionPlan'

export const SLEEP_PAST = 3
export const SLEEP_FUTURE = 11

/**
 * The crew's sleep-aid plan as the Flight Surgeon sees it: read-only, every
 * crew member, and the nights where nobody would stay without a sleeping pill.
 */
export function SleepPane({ crew, entries, tonight, missionStart }: { crew: CrewMember[]; entries: SleepAidPlanEntry[]; tonight: string; missionStart: string }) {
  const ids = crew.map((c) => c.id)
  const nights = nightsFrom(addDays(tonight, -SLEEP_PAST), SLEEP_PAST + SLEEP_FUTURE)
  const upcoming = nightsFrom(tonight, SLEEP_FUTURE).map((n) => coverageOf(entries, ids, n))
  const uncovered = upcoming.filter((c) => c.uncovered)
  return (
    <article className="pane pane-fit">
      <header className="pane-header">
        <p className="eyebrow">Crew schedule</p>
        <h1>Sleeping-pill plan</h1>
        <p className="why explain">
          <strong>Why it is here · </strong>
          Each crew member plans the nights they intend to use a sleeping pill. Demo rule: at least {SLEEP_COVER_RULE.minWithoutSleepAid} crew member stays
          without one every night, ready for an emergency.
        </p>
      </header>
      <div className="pane-grid">
        <div className="pane-main">
          <section className="card sleep-plan-card" aria-label="Sleeping-pill calendar">
            <SleepGrid nights={nights} today={tonight} crew={crew} entries={entries} me={null} missionStart={missionStart} />
            <ul className="legend">
              <li>
                <span className="sg-mark legend-moon">
                  <PillIcon size={12} />
                </span>{' '}
                Sleeping pill planned
              </li>
              <li>
                <span className="sg-warn">▲ 0/3</span> nobody left without one
              </li>
              <li className="muted">Only the plan is recorded: no medicine and no dose</li>
            </ul>
          </section>
        </div>
        <aside className="pane-side" aria-label="Nights without cover">
          <section>
            <h2 className="side-title">Nights without cover</h2>
            {uncovered.length ? (
              <List label="Nights without cover">
                {uncovered.map((c) => (
                  <Row
                    key={c.night}
                    leading={<span className="symbol tone-orange">▲</span>}
                    title={`${nightLabel(c.night).weekday} ${nightLabel(c.night).day} ${nightLabel(c.night).month}`}
                    subtitle={(() => {
                      const a = activityAfterNight(c.night, missionStart)
                      return a ? `Everyone planned a sleeping pill · ${a.label} at ${a.startUtc} next morning` : 'Every crew member planned a sleeping pill'
                    })()}
                  />
                ))}
              </List>
            ) : (
              <p className="list-empty">Every night in the next {SLEEP_FUTURE} has at least one crew member without a sleeping pill.</p>
            )}
          </section>
          <p className="fineprint side-note">
            Planning data only. Medication decisions stay with the medical team and the approved procedures; this view gives no advice.
          </p>
        </aside>
      </div>
    </article>
  )
}
