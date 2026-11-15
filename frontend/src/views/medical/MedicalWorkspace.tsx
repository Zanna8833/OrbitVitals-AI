import { useCallback, useRef, useState, type ReactNode } from 'react'
import { CREW_MESSAGE_TEMPLATES, type DataSource } from '../../data'
import type { CrewMember, DailyIndicatorId, MissionStatus, ReviewEvent } from '../../domain/types'
import { DAILY_INDICATORS, EVENT_KIND_LABEL } from '../../domain/parameters'
import { completeness, latestCell } from '../../domain/deviation'
import type { BackendEvaluation } from '../../domain/metricCatalog'
import { NUTRIENTS, progressOf, totalsOf } from '../../domain/nutrition'
import { addDays, coverageOf, nightLabel, nightsFrom, readyOn } from '../../domain/sleepPlan'
import { formatAge, formatClock, formatDate, joinNames, missionDayOf } from '../../domain/time'
import { useQuery } from '../../hooks/useQuery'
import { useMutation } from '../../hooks/useMutation'
import { useTightness } from '../../hooks/useTightness'
import { useBoxSize } from '../../hooks/useLayout'
import { href } from '../../hooks/useRoute'
import { useAppState } from '../../state/AppState'
import { sliceToDay, viewMission } from '../../domain/viewDay'
import { AstronautSwitch } from '../../components/AstronautSwitch'
import { BackLink } from '../../components/BackLink'
import { MissionTimeline } from '../../components/MissionTimeline'
import { DailyTrendChart } from '../../components/DailyTrendChart'
import { CheckInChart, CompletenessMap, DeviationChart, EvaluationTimeline, IndicatorChip, MATRIX_INDICATORS, NutritionBullets, StatusMatrix } from '../../components/MedicalCharts'
import { SleepGrid } from '../../components/SleepGrid'
import { ErrorState, FormError, Loading } from '../../components/Common'
import { EventKindBadge } from '../../components/EventKindBadge'
import { useToast } from '../../components/Toast'
import { List, Row, Segmented, SimTag } from '../../components/ui'
import { EvaluationsList } from './Evaluations'
import { loadNutrition } from '../crew/Nutrition'

const DOMAIN_LABEL: Record<string, string> = { vital_signs: 'Vital signs', sleep: 'Sleep', physical_activity: 'Activity', nutrition: 'Nutrition', cognition: 'Cognition' }
const STATUS_LABEL: Record<string, string> = { nominal: 'Nominal', attention: 'Attention', alert: 'Alert', insufficient_data: 'Insufficient data' }

/** Latest evaluation of each domain. */
function latestByDomain(items: BackendEvaluation[]): BackendEvaluation[] {
  const m = new Map<string, BackendEvaluation>()
  for (const e of items) if (!m.has(e.domain) || m.get(e.domain)!.window_end < e.window_end) m.set(e.domain, e)
  return [...m.values()]
}
const needsReview = (e: BackendEvaluation) => e.status === 'attention' || e.status === 'alert'

/** Same header as the crew side: title, mission day, and the Crew / Astronaut switch. */
export function MedicalHeader({ title, eyebrow, mission, crew, current, back, actualDay }: { title: string; eyebrow: ReactNode; mission: MissionStatus; crew: CrewMember[]; current: string | null; back?: { href: string; label?: string }; actualDay?: number }) {
  return (
    <header className="today-head">
      <div className="today-title">
        {back && <BackLink fallback={back.href} label={back.label} />}
        <h1>{title}</h1>
        <p className="eyebrow">{eyebrow}</p>
      </div>
      <MissionTimeline day={missionDayOf(mission.now, mission.missionStartDate)} today={actualDay} />
      <AstronautSwitch crew={crew} current={current} area="medical" />
    </header>
  )
}

/* ================================================================== */
/* Medical · Crew                                                       */
/* ================================================================== */

/** Evaluations whose window ended by the viewed day. */
const byDay = (items: BackendEvaluation[], nowIso: string) => items.filter((e) => e.window_end <= nowIso)

async function loadCrewView(ds: DataSource, viewDay: number | null) {
  const [real, crew, events] = await Promise.all([ds.getMissionStatus(), ds.listCrew(), ds.listEvents()])
  const view = viewMission(real, viewDay)
  const mission = view.mission
  const tonight = mission.now.slice(0, 10)
  const [members, plan] = await Promise.all([
    Promise.all(
      crew.map(async (c) => ({
        crew: c,
        daily: sliceToDay(await ds.getDailyIndicators(c.id), view.day),
        evaluations: byDay(await ds.listEvaluations(c.id).catch(() => []), mission.now),
      })),
    ),
    ds.listSleepAidPlan(tonight, addDays(tonight, 6)),
  ])
  return { mission, crew, events: view.past ? [] : events, members, plan, actualDay: view.actualDay }
}

export function MedicalCrew() {
  const { viewDay } = useAppState()
  const state = useQuery(useCallback((ds: DataSource) => loadCrewView(ds, viewDay), [viewDay]))
  const rootRef = useRef<HTMLDivElement>(null)
  const tight = useTightness(rootRef)
  if (state.status === 'loading') return <Loading />
  if (!state.data) return <ErrorState error={state.error!} />
  const { mission, crew, events, members, plan, actualDay } = state.data
  const day = missionDayOf(mission.now, mission.missionStartDate)
  const simulated = members.some((m) => m.daily.some((s) => s.simulated && s.days.some((d) => d.value !== null)))
  const name = (id: string) => crew.find((c) => c.id === id)?.displayName ?? id
  const flagged = members.flatMap((m) => latestByDomain(m.evaluations).filter(needsReview).map((e) => ({ crewId: m.crew.id, e })))
  const pending = events.filter((e) => e.status !== 'reviewed')
  const tonight = mission.now.slice(0, 10)
  const ids = crew.map((c) => c.id)
  const ready = readyOn(plan, ids, tonight)
  const uncovered = nightsFrom(tonight, 7).filter((n) => coverageOf(plan, ids, n).uncovered)
  const rows = members.map((m) => ({ id: m.crew.id, name: m.crew.displayName, cells: MATRIX_INDICATORS.map((x) => latestCell(m.daily.find((s) => s.indicator === x.id)!)) }))
  const cmap = members.map((m) => ({ id: m.crew.id, name: m.crew.displayName, days: completeness(m.daily, day, 21) }))

  return (
    <div className="today medical-ws" ref={rootRef} data-tight={tight || undefined}>
      <MedicalHeader title="Medical" eyebrow={<>{formatDate(mission.now)} · {formatClock(mission.now, false)} UTC {simulated && <SimTag>Simulated records</SimTag>}</>} mission={mission} crew={crew} current={null} actualDay={actualDay} />
      <div className="today-grid">
        <div className="today-col">
          <section className="card ws-card" aria-labelledby="rev-h">
            <div className="ws-card-head">
              <h2 id="rev-h">To review</h2>
              <span className={`count${flagged.length + pending.length ? ' is-attention' : ''}`}>{flagged.length + pending.length}</span>
            </div>
            {flagged.length + pending.length ? (
              <List label="To review">
                {flagged.map(({ crewId, e }) => (
                  <Row
                    key={e.evaluation_id}
                    href={`${href.medicalCrew(crewId)}?tab=evaluations`}
                    leading={<span className="symbol tone-orange">▲</span>}
                    title={`${DOMAIN_LABEL[e.domain] ?? e.domain} · ${STATUS_LABEL[e.status]?.toLowerCase() ?? e.status}`}
                    subtitle={`${name(crewId)} · window to ${formatDate(e.window_end)}`}
                  />
                ))}
                {pending.map((e) => (
                  <Row
                    key={e.id}
                    href={href.event(e.id)}
                    leading={<EventKindBadge kind={e.kind} size={16} />}
                    title={e.kind === 'crew_report' ? 'Shared by the astronaut' : EVENT_KIND_LABEL[e.kind]}
                    subtitle={`${name(e.crewId)} · ${formatClock(e.detectedAt, false)} UTC${e.status === 'in_review' ? ' · in review' : ''}`}
                  />
                ))}
              </List>
            ) : (
              <p className="list-empty">Nothing to review.</p>
            )}
          </section>

          <section className={`card ws-card${uncovered.length ? ' sleep-conflicts' : ''}`} aria-labelledby="night-h">
            <div className="ws-card-head">
              <h2 id="night-h">Tonight and the next 7 nights</h2>
            </div>
            <p className="ws-line">
              <span className="muted">Ready to respond tonight</span>
              <strong>{ready.length ? joinNames(ready.map(name)) : 'Nobody'}</strong>
            </p>
            <p className="ws-line">
              <span className="muted">Nights without cover</span>
              <strong className={uncovered.length ? 'text-attention' : undefined}>{uncovered.length ? uncovered.map((n) => `${nightLabel(n).weekday} ${nightLabel(n).day}`).join(', ') : 'None'}</strong>
            </p>
            <div className="ws-links">
              <a className="btn btn-small" href={href.medicalSleep()}>
                Sleeping-pill plan
              </a>
            </div>
          </section>
        </div>

        <div className="today-col today-col-wide">
          <section className="card ws-card" aria-labelledby="mx-h">
            <div className="ws-card-head">
              <h2 id="mx-h">Crew status</h2>
              <span className="muted">Latest reliable value · against each astronaut’s own usual range</span>
            </div>
            <StatusMatrix rows={rows} onOpen={(id, m) => (window.location.hash = href.medicalCrew(id, m))} />
          </section>
          <section className="card ws-card" aria-labelledby="cm-h">
            <div className="ws-card-head">
              <h2 id="cm-h">Data completeness</h2>
              <span className="muted">Last 21 mission days</span>
            </div>
            <CompletenessMap rows={cmap} />
          </section>
        </div>
      </div>
    </div>
  )
}


/* ================================================================== */
/* Medical · Astronaut                                                  */
/* ================================================================== */

type Tab = 'trends' | 'evaluations' | 'nutrition' | 'sleep'

async function loadAstronaut(ds: DataSource, crewId: string, viewDay: number | null) {
  const [real, crew] = await Promise.all([ds.getMissionStatus(), ds.listCrew()])
  const view = viewMission(real, viewDay)
  const mission = view.mission
  const tonight = mission.now.slice(0, 10)
  const [daily, evaluations, checkIns, events, messages, plan, snapshot, nutrition] = await Promise.all([
    ds.getDailyIndicators(crewId).then((d) => sliceToDay(d, view.day)),
    ds.listEvaluations(crewId).then((e) => byDay(e, mission.now)).catch(() => [] as BackendEvaluation[]),
    ds.listCheckIns(crewId).then((c) => c.filter((x) => x.missionDay <= view.day)),
    ds.listEvents({ crewId }).then((e) => (view.past ? [] : e)),
    ds.listCrewMessages(crewId),
    ds.listSleepAidPlan(addDays(tonight, -3), addDays(tonight, 10)),
    ds.getCrewSnapshot(crewId),
    loadNutrition(ds, crewId, mission.now),
  ])
  return { mission, crew, daily, evaluations, checkIns, events, messages, plan, snapshot, nutrition, actualDay: view.actualDay }
}

export function MedicalAstronaut({ crewId, metric, tab: tabParam }: { crewId: string; metric: string | null; tab: string | null }) {
  const { viewDay } = useAppState()
  const state = useQuery(useCallback((ds: DataSource) => loadAstronaut(ds, crewId, viewDay), [crewId, viewDay]))
  const rootRef = useRef<HTMLDivElement>(null)
  const tight = useTightness(rootRef)
  const [tab, setTab] = useState<Tab>(tabParam === 'evaluations' || tabParam === 'nutrition' || tabParam === 'sleep' ? tabParam : 'trends')
  const [selected, setSelected] = useState<DailyIndicatorId | null>((metric as DailyIndicatorId | null) ?? null)
  const [evalSel, setEvalSel] = useState<string | null>(null)
  const [chartsRef, chartsBox] = useBoxSize<HTMLDivElement>()
  if (state.status === 'loading') return <Loading />
  if (!state.data) return <ErrorState error={state.error!} />
  const { mission, crew, daily, evaluations, checkIns, events, messages, plan, snapshot, nutrition, actualDay } = state.data
  const me = crew.find((c) => c.id === crewId)
  const day = missionDayOf(mission.now, mission.missionStartDate)
  const cells = MATRIX_INDICATORS.map((m) => latestCell(daily.find((s) => s.indicator === m.id)!))
  // Default: the indicator furthest from its usual range.
  const auto = [...cells].filter((c) => c.units !== null).sort((a, b) => Math.abs(b.units!) - Math.abs(a.units!))[0]?.indicator ?? 'resting_hr'
  const current = selected ?? auto
  const series = daily.find((s) => s.indicator === current)!
  const latest = latestByDomain(evaluations)
  const flagged = latest.filter(needsReview)
  const pending = events.filter((e) => e.status !== 'reviewed')
  const last14 = completeness(daily, day, 14)
  const reliable = last14.reduce((a, d) => a + d.reliable, 0)
  const possible = last14.reduce((a, d) => a + d.total, 0)

  // Nutrition: mean of the complete days logged in the last week.
  const days = [...new Set(nutrition.intake.map((e) => e.eatenAt.slice(0, 10)))].filter((d) => d < mission.now.slice(0, 10))
  const sum = totalsOf(nutrition.intake.filter((e) => days.includes(e.eatenAt.slice(0, 10))), nutrition.foods)
  for (const k of Object.keys(sum.totals) as (keyof typeof sum.totals)[]) sum.totals[k] /= Math.max(1, days.length)
  const nutri = NUTRIENTS.map((d) => progressOf(d.id, sum, nutrition.profile))

  return (
    <div className="today medical-ws" ref={rootRef} data-tight={tight || undefined}>
      <MedicalHeader
        title={me?.displayName ?? 'Astronaut'}
        eyebrow={snapshot.device.lastReceivedAt ? `Last reading ${formatDate(snapshot.device.lastReceivedAt)}, ${formatClock(snapshot.device.lastReceivedAt, false)} UTC · ${formatAge(snapshot.device.lastReceivedAt, mission.now)}` : 'No reading received yet'}
        mission={mission}
        crew={crew}
        current={crewId}
        back={{ href: href.medical(), label: 'Back' }}
        actualDay={actualDay}
      />
      <div className="today-grid">
        <div className="today-col">
          <section className="card ws-card" aria-labelledby="st-h">
            <div className="ws-card-head">
              <h2 id="st-h">Status by area</h2>
              <span className="muted">Server evaluations</span>
            </div>
            {latest.length ? (
              <ul className="domain-status">
                {['vital_signs', 'sleep', 'physical_activity', 'nutrition'].map((d) => {
                  const e = latest.find((x) => x.domain === d)
                  return (
                    <li key={d}>
                      <button type="button" className={`domain-chip is-${e?.status ?? 'none'}`} disabled={!e} onClick={() => e && (setTab('evaluations'), setEvalSel(e.evaluation_id))}>
                        <span>{DOMAIN_LABEL[d]}</span>
                        <strong>{e ? STATUS_LABEL[e.status] ?? e.status : 'Not evaluated'}</strong>
                        {e && <small>to {formatDate(e.window_end)}</small>}
                      </button>
                    </li>
                  )
                })}
              </ul>
            ) : (
              <p className="list-empty">No evaluation stored yet.</p>
            )}
            <p className="ws-line">
              <span className="muted">Reliable readings, last 14 days</span>
              <strong>{possible ? `${Math.round((reliable / possible) * 100)}% (${reliable}/${possible})` : '—'}</strong>
            </p>
          </section>

          {pending.length > 0 && (
            <section className="card ws-card" aria-labelledby="arev-h">
              <div className="ws-card-head">
                <h2 id="arev-h">Shared and flagged items</h2>
              </div>
              <List label="Items">
                {pending.map((e) => (
                  <Row
                    key={e.id}
                    href={href.event(e.id)}
                    leading={<EventKindBadge kind={e.kind} size={16} />}
                    title={e.kind === 'crew_report' ? 'Shared by the astronaut' : EVENT_KIND_LABEL[e.kind]}
                    subtitle={`${formatClock(e.detectedAt, false)} UTC${e.status === 'in_review' ? ' · in review' : ''}`}
                  />
                ))}
              </List>
            </section>
          )}

          <MessageCard crewId={crewId} name={me?.displayName ?? ''} messages={messages} events={events} />

          <section className="card ws-card" aria-labelledby="ci-h">
            <div className="ws-card-head">
              <h2 id="ci-h">Check-ins</h2>
              <span className="muted">Last 14 days</span>
            </div>
            <CheckInChart items={checkIns} lastDay={day} />
          </section>
        </div>

        <div className="today-col today-col-wide">
          <section className="card ws-card ws-main" aria-label="Details">
            <div className="ws-card-head">
              <Segmented
                label="View"
                value={tab}
                onChange={setTab}
                options={[
                  { value: 'trends', label: 'Trends' },
                  { value: 'evaluations', label: `Evaluations${flagged.length ? ` · ${flagged.length}` : ''}` },
                  { value: 'nutrition', label: 'Nutrition' },
                  { value: 'sleep', label: 'Sleep' },
                ]}
              />
            </div>

            {tab === 'trends' && (
              <div className="ws-trends">
                <p className="ws-hint">Latest reliable value · distance from the astronaut’s usual median in range units (±1 = edge of the usual range). Select one for its days.</p>
                <div className="ichips">
                  {cells.map((c) => (
                    <IndicatorChip key={c.indicator} cell={c} selected={c.indicator === current} onSelect={() => setSelected(c.indicator)} />
                  ))}
                </div>
                <div className="ws-detail">
                  <div className="ws-detail-head">
                    <strong>{DAILY_INDICATORS[current].label}</strong>
                    <span className="muted">
                      {series.baseline ? `Usual range ${series.baseline.low}–${series.baseline.high} ${DAILY_INDICATORS[current].unit} (grey band, days ${series.baseline.fromDay}–${series.baseline.toDay})` : 'No usual range yet'} · hatched: no reading · {series.source}
                    </span>
                  </div>
                  {/* The two charts share the height left in the card. */}
                  <div className="ws-charts" ref={chartsRef}>
                    {chartsBox.height > 0 && (
                      <>
                        <DailyTrendChart key={current} series={series} height={Math.max(96, Math.round((chartsBox.height - 24) * 0.55))} legend={false} />
                        <DeviationChart key={`d-${current}`} series={series} height={Math.max(92, Math.round((chartsBox.height - 24) * 0.45))} />
                      </>
                    )}
                  </div>
                </div>
              </div>
            )}

            {tab === 'evaluations' && (
              <div className="ws-evals">
                <EvaluationTimeline items={evaluations} nowIso={mission.now} selected={evalSel} onSelect={(id) => setEvalSel((cur) => (cur === id ? null : id))} />
                {evalSel && (
                  <p className="filter-bar">
                    <span>Showing 1 of {evaluations.length} evaluations</span>
                    <button type="button" className="btn btn-small" onClick={() => setEvalSel(null)}>
                      Show all
                    </button>
                  </p>
                )}
                <div className="ws-scroll">
                  <EvaluationsList items={evalSel ? evaluations.filter((e) => e.evaluation_id === evalSel) : evaluations} openFirst={!!evalSel} />
                </div>
              </div>
            )}

            {tab === 'nutrition' && (
              <div className="ws-nutrition">
                <p className="ws-line">
                  <span className="muted">Mean of the complete days logged in the last week</span>
                  <strong>{days.length ? `${days.length} ${days.length === 1 ? 'day' : 'days'}` : 'No day logged'}</strong>
                </p>
                {days.length ? (
                  <div className="bullet-cols">
                    <NutritionBullets items={nutri.filter((p) => p.def.group !== 'minerals')} />
                    <NutritionBullets items={nutri.filter((p) => p.def.group === 'minerals')} />
                  </div>
                ) : (
                  <p className="list-empty">The astronaut has not logged a complete day of food in the last week.</p>
                )}
                <p className="fineprint">
                  Bar: mean intake as a share of the NASA minimum (line at 100%); for iron, of the upper limit. Orange: above a limit. Targets for {nutrition.profile.sex}, {nutrition.profile.ageYears} y, {nutrition.profile.bodyMassKg.toFixed(1)} kg ({nutrition.profile.source}). NASA JSC-67378.
                </p>
              </div>
            )}

            {tab === 'sleep' && (
              <div className="ws-sleep">
                <SleepGrid nights={nightsFrom(addDays(mission.now.slice(0, 10), -3), 14)} today={mission.now.slice(0, 10)} crew={crew} entries={plan} me={crewId} missionStart={mission.missionStartDate} />
                <p className="fineprint">Sleeping-pill nights planned by the crew. Only the night is recorded: no medicine and no dose.</p>
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  )
}

function MessageCard({ crewId, name, messages, events }: { crewId: string; name: string; messages: { id: string; createdAt: string; text: string }[]; events: ReviewEvent[] }) {
  const { notifyChanged } = useAppState()
  const toast = useToast()
  const [template, setTemplate] = useState(CREW_MESSAGE_TEMPLATES[0].id)
  const send = useMutation((ds: DataSource, t: string) => ds.sendCrewMessage(crewId, t, events.find((e) => e.status !== 'reviewed')?.id ?? null))
  const last = messages[0]
  return (
    <section className="card ws-card" aria-labelledby="msg-h">
      <div className="ws-card-head">
        <h2 id="msg-h">Message to {name}</h2>
      </div>
      <div className="msg-row">
        <select value={template} onChange={(e) => setTemplate(e.target.value)} aria-label="Predefined message">
          {CREW_MESSAGE_TEMPLATES.map((t) => (
            <option key={t.id} value={t.id}>
              {t.text}
            </option>
          ))}
        </select>
        <button
          type="button"
          className="btn btn-primary btn-small"
          disabled={send.busy}
          onClick={async () => {
            if (await send.run(template)) {
              notifyChanged()
              toast(`Message sent to ${name}`)
            }
          }}
        >
          Send
        </button>
      </div>
      <FormError message={send.error} />
      {last && (
        <p className="fineprint">
          Last sent {formatClock(last.createdAt, false)} UTC: “{last.text}”
        </p>
      )}
    </section>
  )
}
