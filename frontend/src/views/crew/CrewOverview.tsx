import { useCallback } from 'react'
import type { DataSource } from '../../data'
import { DAILY_INDICATORS } from '../../domain/parameters'
import { checkedInOn, evaluateIndicator, summarizeHealth } from '../../domain/crewHealth'
import { formatDate, missionDayOf } from '../../domain/time'
import { addDays, coverageOf, isPlanned, nightLabel, nightsFrom, readyOn } from '../../domain/sleepPlan'
import { activityAfterNight, involves } from '../../domain/missionPlan'
import { summarize, totalsOf } from '../../domain/nutrition'
import { initialsOf } from '../../domain/overview'
import { useQuery } from '../../hooks/useQuery'
import { href } from '../../hooks/useRoute'
import { ErrorState, Loading } from '../../components/Common'
import { MissionTimeline } from '../../components/MissionTimeline'
import { AstronautSwitch } from '../../components/AstronautSwitch'
import { Ring } from '../../components/Ring'
import { PillIcon } from '../../components/SleepGrid'
import { loadNutrition } from './Nutrition'

async function loadCrew(ds: DataSource) {
  const [mission, crew] = await Promise.all([ds.getMissionStatus(), ds.listCrew()])
  const tonight = mission.now.slice(0, 10)
  const [plan, members] = await Promise.all([
    ds.listSleepAidPlan(tonight, addDays(tonight, 6)),
    Promise.all(
      crew.map(async (c) => {
        const [daily, checkIns, nutrition] = await Promise.all([ds.getDailyIndicators(c.id), ds.listCheckIns(c.id), loadNutrition(ds, c.id, mission.now)])
        return { crew: c, daily, checkIns, nutrition }
      }),
    ),
  ])
  return { mission, crew, plan, members }
}

/** Everyone at a glance: one card per astronaut, then what the crew shares (tonight's readiness). */
export function CrewOverview() {
  const state = useQuery(useCallback((ds: DataSource) => loadCrew(ds), []))
  if (state.status === 'loading') return <Loading />
  if (!state.data) return <ErrorState error={state.error!} />
  const { mission, crew, plan, members } = state.data
  const day = missionDayOf(mission.now, mission.missionStartDate)
  const tonight = mission.now.slice(0, 10)
  const ids = crew.map((c) => c.id)
  const ready = readyOn(plan, ids, tonight)
  const uncovered = nightsFrom(tonight, 7).filter((n) => coverageOf(plan, ids, n).uncovered)
  const nextActivity = nightsFrom(tonight, 7)
    .map((n) => ({ n, a: activityAfterNight(n, mission.missionStartDate) }))
    .find((x) => x.a)

  return (
    <div className="today crew-overview">
      <header className="today-head">
        <div className="today-title">
          <h1>Crew</h1>
          <p className="eyebrow">{formatDate(mission.now)}</p>
        </div>
        <MissionTimeline day={day} />
        <AstronautSwitch crew={crew} current={null} />
      </header>

      <div className="astro-grid">
        {members.map((m) => {
          const evals = m.daily.map((s) => evaluateIndicator(s, day))
          const health = summarizeHealth(evals)
          const changed = health.changed.map((e) => DAILY_INDICATORS[e.series.indicator].label)
          const n = summarize(totalsOf(m.nutrition.intake.filter((e) => e.eatenAt.slice(0, 10) === tonight), m.nutrition.foods), m.nutrition.profile, true)
          const pill = isPlanned(plan, m.crew.id, tonight)
          const checkIn = checkedInOn(m.checkIns, mission.now)
          const act = nextActivity?.a && involves(nextActivity.a, m.crew.id) ? nextActivity : null
          return (
            <a key={m.crew.id} className="card astro-card" href={href.crew(m.crew.id)}>
              <div className="astro-head">
                <span className="avatar">{initialsOf(m.crew.displayName)}</span>
                <span className="astro-name">
                  <strong>{m.crew.displayName}</strong>
                  <small>{m.crew.note}</small>
                </span>
                <span className="astro-open">Open ›</span>
              </div>

              <div className={`astro-health${changed.length ? ' is-attention' : ''}`}>
                <span className="astro-label">Health</span>
                <span>{changed.length ? `Changed from usual: ${changed.join(', ').toLowerCase()}` : 'Nothing needs attention'}</span>
              </div>

              <div className="astro-nutrition">
                <span className="astro-label">Nutrition today</span>
                <div className="mini-rings">
                  <span className="mini-ring">
                    <Ring size={40} stroke={5} fill={n.water.fill} tone="water" label={`Water ${Math.round(n.water.fill * 100)}%`}>
                      <span className="ring-num">{Math.round(n.water.fill * 100)}</span>
                    </Ring>
                    Water
                  </span>
                  <span className="mini-ring">
                    <Ring size={40} stroke={5} fill={n.energy.fill} tone="energy" label={`Energy ${Math.round(n.energy.fill * 100)}%`}>
                      <span className="ring-num">{Math.round(n.energy.fill * 100)}</span>
                    </Ring>
                    Energy
                  </span>
                  <span className="mini-ring">
                    <Ring size={40} stroke={5} fill={n.microsFill} tone="micro" over={n.over.length > 0} label={`${n.microsOnTarget} of ${n.micros.length} micronutrients on target`}>
                      <span className="ring-num">{n.microsOnTarget}</span>
                    </Ring>
                    Vit. & min.
                  </span>
                </div>
              </div>

              <ul className="astro-facts">
                <li>
                  <span className="astro-label">Tonight</span>
                  {pill ? (
                    <span className="pill-planned">
                      <PillIcon size={12} /> Sleeping pill planned
                    </span>
                  ) : (
                    <span>No sleeping pill · ready to respond</span>
                  )}
                </li>
                <li>
                  <span className="astro-label">Check-in</span>
                  <span>{checkIn ? 'Done today' : 'Not yet today'}</span>
                </li>
                {act?.a && (
                  <li>
                    <span className="astro-label">Next</span>
                    <span>
                      {act.a.label}, {nightLabel(addDays(act.n, 1)).weekday} {act.a.startUtc}
                    </span>
                  </li>
                )}
              </ul>
            </a>
          )
        })}
      </div>

      <section className={`card crew-strip${uncovered.length ? ' is-attention' : ''}`} aria-label="Shared by the crew">
        <div>
          <span className="astro-label">Ready tonight</span>
          <strong>{ready.length ? ready.map((id) => crew.find((c) => c.id === id)?.displayName ?? id).join(' and ') : 'Nobody without a sleeping pill'}</strong>
        </div>
        <div>
          <span className="astro-label">Next 7 nights</span>
          <strong>{uncovered.length ? `${uncovered.map((u) => `${nightLabel(u).weekday} ${nightLabel(u).day}`).join(', ')}: everyone planned a pill` : 'Someone ready every night'}</strong>
        </div>
        {nextActivity?.a && (
          <div>
            <span className="astro-label">Next activity</span>
            <strong>
              {nextActivity.a.label} · {nightLabel(addDays(nextActivity.n, 1)).weekday} {nextActivity.a.startUtc} UTC
            </strong>
          </div>
        )}
        <a className="btn btn-small" href={href.crew(crew[0]?.id, 'sleep')}>
          Sleep plan
        </a>
      </section>
    </div>
  )
}
