import { useCallback, useEffect, useRef, useState } from 'react'
import type { DataSource } from '../../data'
import type { DailyIndicatorId, MissionStatus } from '../../domain/types'
import { DAILY_INDICATORS, PARAMETER_ORDER, formatDailyValue } from '../../domain/parameters'
import { checkedInOn, describeCheckIn, evaluateIndicator, summarizeHealth, type IndicatorEvaluation } from '../../domain/crewHealth'
import { describeCollection, describeSensors } from '../../domain/crewStatus'
import { describeActivityProgress, describeNextStep } from '../../domain/crewGuidance'
import { formatAge, formatClock, formatDate, formatDuration, joinNames, missionDayOf, toIso, toMs } from '../../domain/time'
import { useQuery } from '../../hooks/useQuery'
import { href, type CrewPage } from '../../hooks/useRoute'
import { useMutation } from '../../hooks/useMutation'
import { addDays, coverageOf, isPlanned, nightLabel, nightsFrom, readyOn, suggestNight, wouldUncover } from '../../domain/sleepPlan'
import { MISSION_ACTIVITIES, activityAfterNight, involves } from '../../domain/missionPlan'
import { Moon, PillIcon, SleepGrid } from '../../components/SleepGrid'
import { AddPlanSheet, DaySheet, SleepMonth, monthOf, shiftMonth } from '../../components/SleepMonth'
import { useToast } from '../../components/Toast'
import { MissionTimeline } from '../../components/MissionTimeline'
import { PillarStrip, type MethodTopic } from '../../components/Pillars'
import { MethodSheet } from '../../components/MethodSheet'
import { pillarsOf } from '../../domain/pillars'
import { measurementsFor } from '../../state/crewLocal'
import type { DeviceMeasurement } from '../../domain/measurements'
import { Empty, ErrorState, FormError, LinkBanner, Loading, RefreshErrorNotice } from '../../components/Common'
import { MetricGlyph } from '../../components/MetricGlyph'
import { QualityGlyph } from '../../components/StatusGlyphs'
import { Sparkline } from '../../components/Sparkline'
import { toneOf } from '../../components/tone'
import { List, Row, SectionTitle, Segmented, Sheet, SimTag, Symbol } from '../../components/ui'
import { DailyTrendChart } from '../../components/DailyTrendChart'
import { useBoxSize, useFitMode } from '../../hooks/useLayout'
import { useTightness } from '../../hooks/useTightness'
import { CheckInSheet, IndicatorSheet, MeasureSheet, ShareSheet, statusText } from './Sheets'
import { useShare } from './shareSync'
import { config } from '../../config'
import { useCognitionAvailable } from '../../hooks/useCognition'
import { rememberAstronaut } from '../../state/lastAstronaut'
import { CrewOverview } from './CrewOverview'
import { AstronautSwitch } from '../../components/AstronautSwitch'
import { FoodSheet, NutritionCard, NutritionPage, loadNutrition } from './Nutrition'

/** Shown inside the single Health rectangle on the home screen. */
const DEFAULT_TILES: DailyIndicatorId[] = ['resting_hr', 'sleep_duration', 'resting_spo2', 'hrv_rmssd', 'bp_systolic', 'resting_resp_rate']
/** Every indicator, grouped by area, on the Health page. */
const ALL_TILES: DailyIndicatorId[] = [
  'resting_hr', 'hrv_rmssd', 'bp_systolic', 'resting_spo2', 'resting_resp_rate',
  'sleep_duration', 'sleep_efficiency', 'activity_minutes', 'active_energy', 'body_temperature', 'body_mass',
]
/** Where the day-to-day values come from: backend, imported file, or demo generator — and whether they are simulated. */
function DataOriginTag({ daily }: { daily: Live['daily'] }) {
  const origin = daily[0]?.origin ?? 'demo'
  const simulated = daily.some((d) => d.simulated && d.days.some((x) => x.value !== null))
  return (
    <span className="origin-tags">
      {origin === 'import' && (
        <span className="state-tag is-works" title={daily[0]?.source}>
          Imported data
        </span>
      )}
      {simulated && <SimTag>{origin === 'demo' ? 'Sample data' : 'Simulated records'}</SimTag>}
    </span>
  )
}

/** The team's cognition battery is a separate full-screen app: opened in its own tab, results go to the ground. */
function CognitionRow() {
  const available = useCognitionAvailable()
  const body = (
    <>
      <Symbol tone="rest">
        <BrainIcon />
      </Symbol>
      <span className="row-text">
        <span className="row-title">Cognition tests ↗</span>
        <span className="row-subtitle">{available === false ? 'Not installed: npm run cognition' : '10-test battery'}</span>
      </span>
    </>
  )
  return available === false ? (
    <div className="mini-row is-disabled" title="Build it with: npm run cognition">
      {body}
    </div>
  ) : (
    <a className="mini-row" href={config.cognitionUrl} target="_blank" rel="noopener" title="Opens the team's cognition battery in a new tab">
      {body}
    </a>
  )
}


const BrainIcon = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" aria-hidden="true">
    <path
      d="M9 4.5a3 3 0 0 0-3 3 3 3 0 0 0-2 5.2A3.2 3.2 0 0 0 7.5 18 2.5 2.5 0 0 0 12 19.2V6a2.5 2.5 0 0 0-3-1.5ZM15 4.5a3 3 0 0 1 3 3 3 3 0 0 1 2 5.2 3.2 3.2 0 0 1-3.5 5.3A2.5 2.5 0 0 1 12 19.2"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinejoin="round"
    />
  </svg>
)

const PAGE_TITLE: Record<CrewPage, string> = { home: 'Today', health: 'Health', sleep: 'Sleep plan', nutrition: 'Nutrition', crew: 'Crew' }

/** Nights shown: a few past ones for context, then the next two weeks. */
const PLAN_PAST = 3
const PLAN_FUTURE = 11
/** The month view can plan this many nights ahead. */
const PLAN_HORIZON = 90
/** The five areas a crew member can glance at when nothing needs attention. */
const AREAS: { label: string; icon: DailyIndicatorId }[] = [
  { label: 'Heart', icon: 'resting_hr' },
  { label: 'Breathing', icon: 'resting_spo2' },
  { label: 'Sleep', icon: 'sleep_duration' },
  { label: 'Activity', icon: 'activity_minutes' },
  { label: 'Body', icon: 'body_mass' },
]

async function loadToday(ds: DataSource, crewIdParam: string | null) {
  const [mission, crew] = await Promise.all([ds.getMissionStatus(), ds.listCrew()])
  const member = crew.find((c) => c.id === crewIdParam) ?? crew[0]
  if (!member) return { mission, crew, member: null }
  const from = toIso(toMs(mission.now) - 60 * 60 * 1000)
  const night = mission.now.slice(0, 10)
  const [snapshot, messages, series, activities, daily, checkIns, sleepPlan] = await Promise.all([
    ds.getCrewSnapshot(member.id),
    ds.listCrewMessages(member.id),
    ds.getSeries(member.id, PARAMETER_ORDER, from, mission.now),
    ds.getActivities(member.id, from, mission.now),
    ds.getDailyIndicators(member.id),
    ds.listCheckIns(member.id),
    ds.listSleepAidPlan(`${addDays(night, -31).slice(0, 7)}-01`, addDays(night, PLAN_HORIZON)),
  ])
  const nutrition = await loadNutrition(ds, member.id, mission.now)
  return { mission, crew, member, live: { snapshot, messages, series, activities, daily, checkIns, sleepPlan, nutrition } }
}

type Sheet =
  | { type: 'indicator'; id: DailyIndicatorId }
  | { type: 'checkin' }
  | { type: 'measure'; id: DailyIndicatorId | null }
  | { type: 'share' }
  | { type: 'sleep-confirm'; night: string }
  | { type: 'method'; topic: MethodTopic }
  | { type: 'nutrition'; sheet: 'food' | 'values' | 'create' }
  | null

const setPlan = (ds: DataSource, crewId: string, night: string, planned: boolean) => ds.setSleepAidPlan(crewId, night, planned)

/**
 * The astronaut's area, three pages that each fit a laptop screen with no scroll:
 * - Today (home): what is happening now, what deserves attention, what I can do,
 *   one Health rectangle and the crew sleep plan;
 * - Health: every indicator and the trend of the one selected;
 * - Sleep plan: the crew calendar of planned sleeping-pill nights.
 * Tasks (check-in, measurement, share, details) open as sheets.
 */
export function CrewToday({ crewId, page = 'home' }: { crewId: string | null; page?: CrewPage }) {
  if (page === 'crew' || !crewId) return <CrewOverview />
  return <AstronautArea crewId={crewId} page={page} />
}

function AstronautArea({ crewId, page }: { crewId: string; page: CrewPage }) {
  useEffect(() => {
    rememberAstronaut(crewId, page)
  }, [crewId, page])
  const state = useQuery(useCallback((ds: DataSource) => loadToday(ds, crewId), [crewId]))
  if (state.status === 'loading') return <Loading />
  if (!state.data) return <ErrorState error={state.error!} />
  const { mission, crew, member, live } = state.data
  if (!member || !live) return <Empty>No crew member available.</Empty>
  return (
    <>
      {state.status === 'error' && <RefreshErrorNotice error={state.error} />}
      <TodayBody key={member.id} page={page} mission={mission} crew={crew} memberId={member.id} live={live} />
    </>
  )
}

type Live = NonNullable<Awaited<ReturnType<typeof loadToday>>['live']>

function TodayBody({
  page,
  mission,
  crew,
  memberId,
  live,
}: {
  page: CrewPage
  mission: MissionStatus
  crew: { id: string; displayName: string }[]
  memberId: string
  live: Live
}) {
  const [sheet, setSheet] = useState<Sheet>(null)
  const rootRef = useRef<HTMLDivElement>(null)
  const tight = useTightness(rootRef)
  const sharing = useShare(memberId, mission)
  const offline = mission.link.state === 'offline'

  const today = missionDayOf(mission.now, mission.missionStartDate)
  const evaluations = live.daily.map((s) => evaluateIndicator(s, today))
  const byId = (id: DailyIndicatorId) => evaluations.find((e) => e.series.indicator === id)
  const summary = summarizeHealth(evaluations)
  // Only indicators actually measured before: a metric never recorded is not a reading to repeat.
  const toRepeat = evaluations.filter((e) => e.repeatSuggested && e.latest && e.series.indicator !== 'bp_diastolic')
  const checkIn = checkedInOn(live.checkIns, mission.now)
  const lastCapture = measurementsFor(memberId)[0]

  const flagged: DailyIndicatorId[] = [...toRepeat, ...summary.changed].map((e) => (e.series.indicator === 'bp_diastolic' ? 'bp_systolic' : e.series.indicator))
  const [selected, setSelected] = useState<DailyIndicatorId>(() => flagged[0] ?? 'resting_hr')

  // Sleep plan
  const tonight = mission.now.slice(0, 10)
  const crewIds = crew.map((c) => c.id)
  const plan = useMutation(setPlan)
  const [busyNight, setBusyNight] = useState<string | null>(null)
  const toast = useToast()
  const nameOf = (id: string) => crew.find((c) => c.id === id)?.displayName ?? id
  const applyPlan = async (night: string, planned: boolean, who: string = memberId) => {
    setBusyNight(night)
    const ok = await plan.run(who, night, planned)
    setBusyNight(null)
    const l = nightLabel(night)
    const forWhom = who === memberId ? '' : ` for ${nameOf(who)}`
    if (ok) toast(planned ? `Sleeping pill planned${forWhom} · ${l.weekday} ${l.day}` : `Removed${forWhom} · ${l.weekday} ${l.day}`)
  }
  const exerciseValue = (id: DailyIndicatorId) => live.daily.find((d) => d.indicator === id)?.days.find((d) => d.missionDay === today)?.value ?? null
  const exMin = exerciseValue('activity_minutes')
  const exKcal = exerciseValue('active_energy')
  const exerciseToday = exMin !== null ? `${Math.round(exMin)} min${exKcal !== null ? ` · ${Math.round(exKcal)} kcal` : ''}` : 'Log a session'
  const uncoveredWeek = nightsFrom(tonight, 7).filter((n) => coverageOf(live.sleepPlan, crewIds, n).uncovered)
  // Indicators that need attention always get a tile on Today; the rest fill up to six.
  const homeTiles = [...new Set<DailyIndicatorId>([...flagged, ...DEFAULT_TILES])].slice(0, 6)
  // Indicators needing attention first (only three tiles fit on short screens).
  homeTiles.sort((a, b) => Number(!flagged.includes(a)) - Number(!flagged.includes(b)) || ALL_TILES.indexOf(a) - ALL_TILES.indexOf(b))
  const lastNight = addDays(tonight, PLAN_FUTURE - 1)
  const myActivity = (night: string) => {
    const a = activityAfterNight(night, mission.missionStartDate)
    return a && involves(a, memberId) ? a : null
  }
  const alternativeTo = (night: string) => suggestNight(live.sleepPlan, crewIds, memberId, night, tonight, lastNight, (n) => !!myActivity(n))
  const toggleNight = (night: string, who: string = memberId) => {
    const planned = isPlanned(live.sleepPlan, who, night)
    if (who !== memberId) {
      // Editing someone else's night (crew-wide edit): ask only when it would leave nobody ready.
      if (!planned && wouldUncover(live.sleepPlan, crewIds, who, night)) {
        toast(`Not planned: ${nameOf(who)} would leave nobody ready that night`)
        return
      }
      void applyPlan(night, !planned, who)
      return
    }
    // Ask first when the night would leave nobody ready, or when the person has an activity next morning.
    if (!planned && (wouldUncover(live.sleepPlan, crewIds, memberId, night) || myActivity(night))) setSheet({ type: 'sleep-confirm', night })
    else void applyPlan(night, !planned)
  }
  const moveNight = async (from: string, to: string) => {
    setBusyNight(from)
    const ok = (await plan.run(memberId, from, false)) && (await plan.run(memberId, to, true))
    setBusyNight(null)
    if (ok) toast(`Moved to ${nightLabel(to).weekday} ${nightLabel(to).day}`)
  }

  const progress = describeActivityProgress(live.activities, mission.now)
  const collection = describeCollection(live.snapshot.device.lastReceivedAt, mission.now, live.snapshot.device.expectedIntervalS, offline)
  const sensors = describeSensors(live.series, mission.now)
  const nextStep = describeNextStep({ messages: live.messages, collection, sensors, linkOffline: offline })
  const asked = nextStep.kind === 'after_activity' || nextStep.kind === 'await_contact'
  const message = live.messages[0]

  const sheetEval = sheet?.type === 'indicator' ? byId(sheet.id) ?? null : null
  const changedNames = summary.changed.map((e) => DAILY_INDICATORS[e.series.indicator].label.toLowerCase())
  const selectedEval = byId(selected)

  return (
    <div className="today" ref={rootRef} data-tight={tight || undefined}>
      <header className="today-head">
        <div className="today-title">
          {page !== 'home' && (
            <a className="back-link-inline" href={href.crew(memberId)}>
              ‹ Today
            </a>
          )}
          <h1>{PAGE_TITLE[page]}</h1>
          <p className="eyebrow">
            {page === 'health'
              ? `Mission day ${today} · compared with your own usual range`
              : page === 'sleep'
                ? 'Sleeping pills: who takes one, and when'
                : page === 'nutrition'
                ? `Mission day ${today} · against NASA daily requirements`
                : formatDate(mission.now)}
          </p>
        </div>
        {page === 'home' && <MissionTimeline day={today} />}
        <AstronautSwitch crew={crew} current={memberId} page={page} />
      </header>

      {page === 'home' && (
      <div className="today-grid">
        <div className="today-col">
          {/* During an activity the Now card already carries the link status. */}
          {!progress?.current && <LinkBanner mission={mission} audience="crew" />}

          {/* Outside a live session: when the latest reading arrived, and a shortcut to add one. */}
          {!progress?.current && (
            <section className="card data-card" aria-labelledby="data-h">
              <div className="data-card-text">
                <p className="eyebrow">Your data</p>
                <h2 id="data-h">
                  {live.snapshot.device.lastReceivedAt
                    ? `Last reading ${formatDate(live.snapshot.device.lastReceivedAt)}, ${formatClock(live.snapshot.device.lastReceivedAt, false)} UTC`
                    : 'No reading received yet'}
                </h2>
                {live.snapshot.device.lastReceivedAt && <p className="data-card-sub">{formatAge(live.snapshot.device.lastReceivedAt, mission.now)}</p>}
              </div>
              <button type="button" className="btn btn-small" onClick={() => setSheet({ type: 'measure', id: null })}>
                Add a reading
              </button>
            </section>
          )}

          {/* Now: only while a scheduled activity is in progress */}
          {progress?.current && (
            <section className="card now-card" aria-labelledby="now-h">
              <div className="now-top">
                <div>
                  <p className="eyebrow">Now</p>
                  <h2 id="now-h">{progress.current.label}</h2>
                </div>
                {progress.remainingMs !== null && <span className="now-left">{formatDuration(progress.remainingMs)} left</span>}
              </div>
              <div className="phase-track" aria-hidden="true">
                {progress.phases.map((p) => (
                  <span key={p.segment.start} className={`phase phase-${p.state}`} style={{ flexGrow: p.share }} />
                ))}
              </div>
              <p className="phase-caption">
                {progress.next ? `Next: ${progress.next.label} at ${formatClock(progress.next.start, false)} UTC` : 'Last phase of the session'}
              </p>
              {/* Shown only on tall screens, where there is room for the full plan. */}
              <ol className="phase-list" aria-label="Session plan">
                {progress.phases.map((p) => (
                  <li key={p.segment.start} className={`phase-item is-${p.state}`}>
                    <span className="phase-dot" aria-hidden="true" />
                    <span className="phase-name">{p.segment.label}</span>
                    <span className="phase-time">
                      {formatClock(p.segment.start, false)}–{formatClock(p.segment.end, false)}
                    </span>
                    <span className="sr-only">{p.state === 'done' ? 'done' : p.state === 'current' ? 'in progress' : 'upcoming'}</span>
                  </li>
                ))}
              </ol>
              <ul className="now-status">
                <li>
                  <QualityGlyph quality={collection.level} /> {collection.headline}
                  {offline && <span className="muted now-extra"> · shared reports wait on this device</span>}
                </li>
                {/* A sensor-level problem is only worth a line while data is otherwise flowing. */}
                {sensors
                  .filter((s) => s.level !== 'good' && collection.level === 'good')
                  .map((s) => (
                    <li key={s.deviceId}>
                      <QualityGlyph quality={s.level} /> {s.deviceLabel.replace(/\s*\(simulated\)$/, '')}: {s.text.toLowerCase()}
                    </li>
                  ))}
                {!asked && <li className="muted now-nothing">Nothing to do — carry on with your activity.</li>}
              </ul>
              {asked && (
                <div className="callout">
                  <strong>{nextStep.title}</strong>
                  <span>{nextStep.detail}</span>
                </div>
              )}
            </section>
          )}

          <Summary
            compact={!!progress?.current && asked}
            repeat={toRepeat[0]}
            changed={summary.changed}
            onOpen={(id) => {
              setSelected(id)
              setSheet({ type: 'indicator', id })
            }}
            onMeasure={(id) => setSheet({ type: 'measure', id })}
            onShare={() => setSheet({ type: 'share' })}
          />

          {message && !(progress?.current && asked) && (
            <div className="message">
              <span className="message-from">
                Medical team · {formatClock(message.createdAt, false)} UTC
              </span>
              <p>{message.text}</p>
            </div>
          )}

          <div className="review-group">
          <p className="group-label">Daily review</p>
          <List label="Daily review">
            <Row
              leading={<Symbol tone={checkIn ? 'gray' : 'blue'}>{checkIn ? '✓' : <CheckInIcon />}</Symbol>}
              title="Daily check-in"
              subtitle={checkIn ? describeCheckIn(checkIn) : 'Sleep, energy and mood · 3 questions'}
              trailing={checkIn ? <span className="muted">Done</span> : <span className="badge">To do</span>}
              onClick={() => setSheet({ type: 'checkin' })}
            />
            <Row
              leading={
                <Symbol tone="blue">
                  <PlusIcon />
                </Symbol>
              }
              title="Take a measurement"
              subtitle={lastCapture ? `Last: ${describeCapture(memberId, lastCapture)}` : 'Vital signs, sleep, exercise, body mass'}
              onClick={() => setSheet({ type: 'measure', id: null })}
            />
            <Row
              leading={
                <Symbol tone="blue">
                  <ShareIcon />
                </Symbol>
              }
              title="Share with medical team"
              subtitle={
                sharing.queued
                  ? `${sharing.queued} report${sharing.queued === 1 ? '' : 's'} waiting for the ground link`
                  : sharing.notice && !sheet
                    ? sharing.notice
                    : offline
                      ? 'Saved and sent when the link returns'
                      : 'Trends and a note, only if you want'
              }
              trailing={sharing.queued ? <span className="badge">{sharing.queued}</span> : undefined}
              onClick={() => setSheet({ type: 'share' })}
            />
            <Row
              leading={
                <Symbol tone="rest">
                  <Moon size={14} />
                </Symbol>
              }
              title="Sleep plan"
              subtitle={
                uncoveredWeek.length ? (
                  <span className="text-attention">
                    {uncoveredWeek.map((n) => `${nightLabel(n).weekday} ${nightLabel(n).day}`).join(', ')}: nobody without a sleeping pill
                  </span>
                ) : (
                  `Tonight: ${isPlanned(live.sleepPlan, memberId, tonight) ? 'sleeping pill planned' : 'no sleeping pill planned'} · ${coverageOf(live.sleepPlan, crewIds, tonight).available} of ${crew.length} crew free`
                )
              }
              trailing={uncoveredWeek.length ? <span className="badge badge-attention">{uncoveredWeek.length}</span> : undefined}
              href={href.crew(memberId, 'sleep')}
            />
          </List>
          <div className="review-pair">
            <button type="button" className="mini-row" onClick={() => setSheet({ type: 'measure', id: 'activity_minutes' })}>
              <Symbol tone="activity">
                <MetricGlyph id="activity_minutes" size={15} />
              </Symbol>
              <span className="row-text">
                <span className="row-title">Exercise</span>
                <span className="row-subtitle">{exerciseToday}</span>
              </span>
            </button>
            <CognitionRow />
          </div>
          </div>
        </div>

        <div className="today-col today-col-wide">
          <NutritionCard data={live.nutrition} mission={mission} crewId={memberId} onLogFood={() => setSheet({ type: 'nutrition', sheet: 'food' })} />
          <section className="health" aria-labelledby="health-h">
            <SectionTitle
              id="health-h"
              action={
                <a className="text-button" href={href.crew(memberId, 'health')}>
                  All indicators ({ALL_TILES.length})
                </a>
              }
            >
              Your health{' '}
<DataOriginTag daily={live.daily} />
            </SectionTitle>
            <div className="tiles home-tiles">
              {homeTiles.map((id) => (
                <Tile
                  key={id}
                  e={byId(id)}
                  id={id}
                  today={today}
                  paired={id === 'bp_systolic' ? byId('bp_diastolic') : undefined}
                  selected={id === selected}
                  onOpen={() => setSelected(id)}
                />
              ))}
            </div>
          </section>
          <TrendCard
            evaluation={selectedEval}
            paired={selected === 'bp_systolic' ? byId('bp_diastolic') : undefined}
            onDetails={() => setSheet({ type: 'indicator', id: selected })}
            onExplain={(topic) => setSheet({ type: 'method', topic })}
          />
        </div>
      </div>
      )}

      {page === 'health' && (
        <div className="health-page">
          <section className="health" aria-label="All indicators">
            <div className="tiles tiles-all">
              {ALL_TILES.map((id) => (
                <Tile
                  key={id}
                  e={byId(id)}
                  id={id}
                  today={today}
                  paired={id === 'bp_systolic' ? byId('bp_diastolic') : undefined}
                  selected={id === selected}
                  onOpen={() => setSelected(id)}
                />
              ))}
            </div>
          </section>
          <TrendCard
            evaluation={selectedEval}
            paired={selected === 'bp_systolic' ? byId('bp_diastolic') : undefined}
            onDetails={() => setSheet({ type: 'indicator', id: selected })}
            onExplain={(topic) => setSheet({ type: 'method', topic })}
          />
        </div>
      )}

      {page === 'nutrition' && (
        <NutritionPage
          data={live.nutrition}
          mission={mission}
          crewId={memberId}
          sheet={sheet?.type === 'nutrition' ? sheet.sheet : null}
          setSheet={(x) => setSheet(x ? { type: 'nutrition', sheet: x } : null)}
        />
      )}

      {page !== 'nutrition' && (
        <FoodSheet
          open={sheet?.type === 'nutrition' && sheet.sheet === 'food'}
          foods={live.nutrition.foods}
          crewId={memberId}
          mission={mission}
          onClose={() => setSheet(null)}
          onCreate={() => (window.location.hash = href.crew(memberId, 'nutrition'))}
        />
      )}

      {page === 'sleep' && (
        <SleepPage
          memberId={memberId}
          crew={crew}
          entries={live.sleepPlan}
          tonight={tonight}
          busyNight={busyNight}
          error={plan.error}
          onToggle={toggleNight}
          missionStart={mission.missionStartDate}
          alternativeTo={alternativeTo}
          onMove={moveNight}
          onSet={(who, night, planned) => void applyPlan(night, planned, who)}
          onAddMany={async (who, nights) => {
            for (const n of nights) await plan.run(who, n, true)
            toast(`${nights.length === 1 ? '1 night' : `${nights.length} nights`} planned for ${nameOf(who)}`)
          }}
        />
      )}

      <IndicatorSheet
        evaluation={sheetEval}
        paired={sheet?.type === 'indicator' && sheet.id === 'bp_systolic' ? byId('bp_diastolic') : undefined}
        today={today}
        onClose={() => setSheet(null)}
        onMeasure={(id) => setSheet({ type: 'measure', id })}
        onShare={() => setSheet({ type: 'share' })}
      />
      <CheckInSheet open={sheet?.type === 'checkin'} crewId={memberId} existing={checkIn} onClose={() => setSheet(null)} />
      <MeasureSheet
        open={sheet?.type === 'measure'}
        crewId={memberId}
        mission={mission}
        initial={sheet?.type === 'measure' ? sheet.id : null}
        onClose={() => setSheet(null)}
      />
      <ShareSheet open={sheet?.type === 'share'} onClose={() => setSheet(null)} sharing={sharing} summary={changedNames.length ? `the change in ${joinNames(changedNames)}` : ''} />
      <MethodSheet topic={sheet?.type === 'method' ? sheet.topic : null} onClose={() => setSheet(null)} />
      <SleepConfirmSheet
        night={sheet?.type === 'sleep-confirm' ? sheet.night : null}
        others={sheet?.type === 'sleep-confirm' ? crew.filter((c) => c.id !== memberId && isPlanned(live.sleepPlan, c.id, sheet.night)).map((c) => c.displayName) : []}
        uncovers={sheet?.type === 'sleep-confirm' && wouldUncover(live.sleepPlan, crewIds, memberId, sheet.night)}
        activity={sheet?.type === 'sleep-confirm' ? myActivity(sheet.night) : null}
        alternative={sheet?.type === 'sleep-confirm' ? alternativeTo(sheet.night) : null}
        onClose={() => setSheet(null)}
        onPlan={(night) => {
          setSheet(null)
          void applyPlan(night, true)
        }}
      />
    </div>
  )
}

interface SleepProps {
  memberId: string
  crew: { id: string; displayName: string }[]
  entries: Live['sleepPlan']
  tonight: string
  busyNight: string | null
  error: string | null
  onToggle: (night: string, crewId: string) => void
  missionStart: string
  alternativeTo: (night: string) => string | null
  onMove: (from: string, to: string) => void
  onSet: (crewId: string, night: string, planned: boolean) => void
  onAddMany: (crewId: string, nights: string[]) => Promise<void>
}

const fullNight = (n: string) => `${nightLabel(n).weekday} ${nightLabel(n).day} ${nightLabel(n).month}`
const shortNight = (n: string) => `${nightLabel(n).weekday} ${nightLabel(n).day}`

/** Asked before a plan that leaves nobody ready, or before a morning activity the person takes part in. */
function SleepConfirmSheet({
  night,
  others,
  uncovers,
  activity,
  alternative,
  onClose,
  onPlan,
}: {
  night: string | null
  others: string[]
  uncovers: boolean
  activity: ReturnType<typeof activityAfterNight>
  alternative: string | null
  onClose: () => void
  onPlan: (night: string) => void
}) {
  const title = uncovers ? 'Nobody would be without a sleeping pill' : `${activity?.label ?? 'Activity'} the next morning`
  return (
    <Sheet open={!!night} title={title} onClose={onClose}>
      {night && (
        <div className="stack">
          {uncovers && (
            <p className="body-text">
              {joinNames(others)} already planned a sleeping pill for the night of <strong>{fullNight(night)}</strong>. If you add yours, nobody on board
              would stay without one.
            </p>
          )}
          {activity && (
            <p className="sleep-activity-note">
              <span className="sg-activity is-mine">{activity.short}</span>
              <span>
                Next morning: <strong>{activity.label}</strong> at {activity.startUtc} UTC, and you take part. Check the timing with your flight surgeon.
              </span>
            </p>
          )}
          <p className="body-text muted">
            {uncovers
              ? 'The crew agreed that at least one person stays without a sleeping pill every night, ready for an emergency (crew rule, set with the medical team).'
              : 'OrbitVitals only coordinates the plan: whether and what to take stays with you and the medical team.'}
          </p>
          {alternative && (
            <p className="body-text">
              <strong>{fullNight(alternative)}</strong> keeps someone ready{activity ? ' and has no activity of yours the next morning' : ''}.
            </p>
          )}
          <div className="button-row">
            {alternative ? (
              <button type="button" className="btn btn-primary" onClick={() => onPlan(alternative)}>
                Plan {shortNight(alternative)} instead
              </button>
            ) : null}
            <button type="button" className={alternative ? 'btn' : 'btn btn-primary'} onClick={onClose}>
              Keep my night free
            </button>
            <button type="button" className="btn btn-plain" onClick={() => onPlan(night)}>
              Plan anyway
            </button>
          </div>
        </div>
      )}
    </Sheet>
  )
}

function SleepPage({ memberId, crew, entries, tonight, busyNight, error, onToggle, missionStart, alternativeTo, onMove, onSet, onAddMany }: SleepProps) {
  const [editAll, setEditAll] = useState(false)
  const [view, setView] = useState<'month' | 'weeks'>('month')
  const [month, setMonth] = useState(monthOf(tonight))
  const [day, setDay] = useState<string | null>(null)
  const [adding, setAdding] = useState(false)
  const lastPlannable = addDays(tonight, PLAN_HORIZON - 1)
  const nights = nightsFrom(addDays(tonight, -PLAN_PAST), PLAN_PAST + PLAN_FUTURE)
  const ids = crew.map((c) => c.id)
  const upcoming = nightsFrom(tonight, PLAN_FUTURE).map((n) => coverageOf(entries, ids, n))
  const mine = upcoming.filter((c) => c.planned.includes(memberId))
  const uncovered = upcoming.filter((c) => c.uncovered)
  const ready = readyOn(entries, ids, tonight).map((id) => crew.find((c) => c.id === id)?.displayName ?? id)
  const nameOf = (id: string) => crew.find((c) => c.id === id)?.displayName ?? id
  const nextActivity = upcoming.map((c) => ({ night: c.night, a: activityAfterNight(c.night, missionStart) })).find((x) => x.a && involves(x.a, memberId))
  return (
    <div className="sleep-page">
      <section className="card sleep-plan-card" aria-label="Sleeping-pill calendar">
        <div className="sleep-intro-row">
          <p className="body-text muted sleep-intro">
            Plan the nights you take a <strong>sleeping pill</strong>. Tap a day to change it, or <strong>+ Add</strong> to plan one or a series. At least one person stays without a pill every night, ready for an emergency.
          </p>
          <Segmented
            size="small"
            label="Calendar view"
            value={view}
            onChange={setView}
            options={[
              { value: 'month', label: 'Month' },
              { value: 'weeks', label: 'Two weeks' },
            ]}
          />
        </div>
        {view === 'month' ? (
          <SleepMonth
            month={month}
            onMonth={setMonth}
            today={tonight}
            crew={crew}
            entries={entries}
            me={memberId}
            missionStart={missionStart}
            onPick={setDay}
            onAdd={() => setAdding(true)}
            minMonth={shiftMonth(monthOf(tonight), -1)}
            maxMonth={monthOf(lastPlannable)}
          />
        ) : (
          <>
            <div className="weeks-tools">
              <Segmented
                size="small"
                label="Who can be edited"
                value={editAll ? 'all' : 'mine'}
                onChange={(v) => setEditAll(v === 'all')}
                options={[
                  { value: 'mine', label: 'My nights' },
                  { value: 'all', label: 'Edit whole crew' },
                ]}
              />
              <button type="button" className="btn btn-primary btn-small" onClick={() => setAdding(true)}>
                + Add
              </button>
            </div>
            <SleepGrid nights={nights} today={tonight} crew={crew} entries={entries} me={memberId} busyNight={busyNight} onToggle={onToggle} missionStart={missionStart} editAll={editAll} />
          </>
        )}
        <ul className="legend">
          {view === 'month' ? (
            <>
              <li>
                <span className="day-pill">B</span> sleeping pill planned · <span className="day-pill is-me">A</span> you
              </li>
              <li>
                <span className="sg-warn">▲</span> nobody left ready
              </li>
            </>
          ) : (
            <>
              <li>
                <span className="sg-mark legend-moon">
                  <PillIcon size={12} />
                </span>{' '}
                Sleeping pill planned
              </li>
              <li>
                <span className="sg-warn">▲ 0/3</span> nobody left ready
              </li>
            </>
          )}
          {MISSION_ACTIVITIES.length > 0 && (
            <li>
              <span className="sg-activity is-mine">EVA</span> activity next morning (yours in blue)
            </li>
          )}
        </ul>
        <FormError message={error} />
        <DaySheet night={day} today={tonight} crew={crew} entries={entries} me={memberId} missionStart={missionStart} busy={!!busyNight} onSet={onSet} onClose={() => setDay(null)} />
        <AddPlanSheet open={adding} today={tonight} lastNight={lastPlannable} crew={crew} entries={entries} me={memberId} onAdd={onAddMany} onClose={() => setAdding(false)} />
      </section>
      <aside className="sleep-side" aria-label="Summary">
        <section className="card">
          <p className="eyebrow">Tonight · {shortNight(tonight)}</p>
          <p className="sleep-ready">
            {ready.length ? (
              <>
                <strong>{joinNames(ready)}</strong> {ready.length === 1 ? 'stays' : 'stay'} ready to respond.
              </>
            ) : (
              <strong className="attention-text">Nobody stays without a sleeping pill.</strong>
            )}
          </p>
          <dl className="sleep-facts">
            <div>
              <dt>Your nights</dt>
              <dd>
                {mine.length
                  ? mine
                      .map((c) => {
                        const a = activityAfterNight(c.night, missionStart)
                        return a && involves(a, memberId) ? `${shortNight(c.night)} (${a.short} next morning)` : shortNight(c.night)
                      })
                      .join(', ')
                  : 'None planned'}
              </dd>
            </div>
            {nextActivity?.a && (
              <div>
                <dt>Next activity</dt>
                <dd>
                  {nextActivity.a.label}, {shortNight(addDays(nextActivity.night, 1))} {nextActivity.a.startUtc}
                </dd>
              </div>
            )}
          </dl>
        </section>
        <section className={`card${uncovered.length ? ' sleep-conflicts' : ''}`} aria-live="polite">
          <p className="eyebrow">Next {PLAN_FUTURE} nights</p>
          {uncovered.length ? (
            <ul className="conflict-list">
              {uncovered.map((c) => {
                const alt = c.planned.includes(memberId) ? alternativeTo(c.night) : null
                return (
                  <li key={c.night}>
                    <p className="sleep-note is-attention">
                      <svg width="11" height="10" viewBox="0 0 11 10" aria-hidden="true">
                        <path d="M5.5 0.8 10.4 9.2H0.6Z" fill="currentColor" />
                      </svg>{' '}
                      <span>
                        <strong>{shortNight(c.night)}</strong>: everyone planned a sleeping pill ({c.planned.map(nameOf).join(', ')}).
                      </span>
                    </p>
                    {alt ? (
                      <button type="button" className="btn btn-small" disabled={busyNight === c.night} onClick={() => onMove(c.night, alt)}>
                        Move mine to {shortNight(alt)}
                      </button>
                    ) : (
                      <p className="fineprint">Coordinate with the crew.</p>
                    )}
                  </li>
                )
              })}
            </ul>
          ) : (
            <p className="sleep-note">Every night has at least one crew member ready to respond.</p>
          )}
        </section>
        <section className="card how-card">
          <p className="eyebrow">How it works</p>
          <ul className="plain-list">
            <li>Only the night is recorded: no medicine name and no dose.</li>
            <li>Crew rule: at least one crew member without a sleeping pill every night, as agreed with the medical team.</li>
            <li>Your flight surgeon sees the same plan.</li>
          </ul>
        </section>
      </aside>
    </div>
  )
}


/** The trend of the selected tile, sized to the space left on screen. */
function TrendCard({
  evaluation: e,
  paired,
  onDetails,
  onExplain,
}: {
  evaluation: IndicatorEvaluation | undefined
  paired?: IndicatorEvaluation
  onDetails: () => void
  onExplain: (topic: MethodTopic) => void
}) {
  const fit = useFitMode()
  const [ref, size] = useBoxSize<HTMLDivElement>()
  if (!e) return null
  const id = e.series.indicator
  const def = DAILY_INDICATORS[id]
  // The plot takes the whole card; the legend and the data table are in Details.
  const chartH = fit ? Math.max(54, size.height - 6) : 170
  return (
    <section className={`card trend-card tone-${toneOf(id)}`} aria-labelledby="trend-h">
      <div className="trend-head">
        <div>
          <h2 id="trend-h" className="trend-title">
            <MetricGlyph id={id} size={16} /> {id === 'bp_systolic' ? 'Blood pressure' : def.label}
            <span className="trend-value">
              {e.latest ? formatDailyValue(id, e.latest.value) : '—'}
              {paired?.latest && `/${formatDailyValue('bp_diastolic', paired.latest.value)}`} <span className="unit">{def.unit}</span>
            </span>
          </h2>
        </div>
        <div className="trend-actions">
          <button type="button" className="btn btn-small" onClick={onDetails}>
            Details
          </button>
        </div>
      </div>
      <PillarStrip p={pillarsOf(e.series, e)} indicator={id} onExplain={onExplain} />
      <div className="fill" ref={ref}>
        <div className="fill-inner">{(size.height > 0 || !fit) && <DailyTrendChart key={id} series={e.series} height={chartH} legend={!fit} />}</div>
      </div>
    </section>
  )
}

/* ------------------------------------------------------------------ */

function Summary({
  compact,
  repeat,
  changed,
  onOpen,
  onMeasure,
  onShare,
}: {
  compact: boolean
  repeat: IndicatorEvaluation | undefined
  changed: IndicatorEvaluation[]
  onOpen: (id: DailyIndicatorId) => void
  onMeasure: (id: DailyIndicatorId) => void
  onShare: () => void
}) {
  const main = changed[0]
  if (!main && !repeat) {
    return (
      <section className="card summary-card is-calm" aria-labelledby="hl-h">
        <span className="summary-mark" aria-hidden="true">
          ✓
        </span>
        <div className="summary-body">
          <h2 id="hl-h">Everything is within your usual range</h2>
          <p>Compared with your own first mission days.</p>
          {!compact && (
          <ul className="areas" aria-label="Areas checked">
            {AREAS.map((a) => (
              <li key={a.label} className={`tone-${toneOf(a.icon)}`}>
                <MetricGlyph id={a.icon} size={14} />
                <span>{a.label}</span>
                <span className="areas-ok">Usual</span>
              </li>
            ))}
          </ul>
          )}
        </div>
      </section>
    )
  }
  if (main) {
    const id = main.series.indicator
    const side = main.position === 'above' ? 'higher' : 'lower'
    const others = changed.slice(1).map((e) => DAILY_INDICATORS[e.series.indicator].label.toLowerCase())
    return (
      <section className="card summary-card" aria-labelledby="hl-h">
        <span className={`summary-icon tone-${toneOf(id)}`} aria-hidden="true">
          <MetricGlyph id={id} size={20} />
        </span>
        <div className="summary-body">
          <p className="attention-label">Worth a look</p>
          <h2 id="hl-h">
            {DAILY_INDICATORS[id].label} has been {side} than usual for {main.streakDays} days
          </h2>
          <p>
            A change from your own pattern, not a diagnosis.
            <span className="summary-more">
              {others.length ? ` Also changed: ${others.join(', ')}.` : ''}
              {repeat ? ` Today’s ${DAILY_INDICATORS[repeat.series.indicator].label.toLowerCase()} reading needs repeating.` : ''}
            </span>
          </p>
          <div className="button-row">
            <button type="button" className="btn btn-primary" onClick={onShare}>
              Share with medical team
            </button>
            <button type="button" className="btn" onClick={() => onOpen(id)}>
              Details
            </button>
          </div>
        </div>
      </section>
    )
  }
  const id = repeat!.series.indicator
  return (
    <section className="card summary-card" aria-labelledby="hl-h">
      <span className={`summary-icon tone-${toneOf(id)}`} aria-hidden="true">
        <MetricGlyph id={id} size={20} />
      </span>
      <div className="summary-body">
        <p className="attention-label">To check</p>
        <h2 id="hl-h">Today’s {DAILY_INDICATORS[id].label.toLowerCase()} reading needs repeating</h2>
        <p>It is missing or its signal was uncertain. Your last reliable value is still shown.</p>
        <div className="button-row">
          <button type="button" className="btn btn-primary" onClick={() => onMeasure(id)}>
            Take measurement
          </button>
          <button type="button" className="btn" onClick={() => onOpen(id)}>
            Details
          </button>
        </div>
      </div>
    </section>
  )
}

function Tile({ e, id, today, paired, selected, onOpen }: { e: IndicatorEvaluation | undefined; id: DailyIndicatorId; today: number; paired?: IndicatorEvaluation; selected: boolean; onOpen: () => void }) {
  const def = DAILY_INDICATORS[id]
  const label = id === 'bp_systolic' ? 'Blood pressure' : def.label
  if (!e) {
    return (
      <div className={`tile is-empty tone-${toneOf(id)}`}>
        <span className={`tile-label tone-${toneOf(id)}`}>
          <MetricGlyph id={id} size={14} /> {label}
        </span>
        <span className="tile-value muted">—</span>
        <span className="tile-status">Not supplied by this data source</span>
      </div>
    )
  }
  const attention = e.repeatSuggested || (e.position !== null && e.position !== 'within' && e.streakDays >= 3)
  const arrow = e.position === 'above' ? '↑ ' : e.position === 'below' ? '↓ ' : ''
  return (
    <button type="button" className={`tile tone-${toneOf(id)}${attention ? ' is-attention' : ''}${selected ? ' is-selected' : ''}`} aria-pressed={selected} onClick={onOpen}>
      <span className="tile-top">
        <span className={`tile-label tone-${toneOf(id)}`}>
          <MetricGlyph id={id} size={14} /> {label}
        </span>
        {e.latest && e.latest.missionDay !== today && <span className="tile-day">Day {e.latest.missionDay}</span>}
      </span>
      <span className="tile-main">
        <span className="tile-value">
          {e.latest ? formatDailyValue(id, e.latest.value) : '—'}
          {paired?.latest && `/${formatDailyValue('bp_diastolic', paired.latest.value)}`}
          <span className="unit"> {def.unit}</span>
        </span>
        <Sparkline series={e.series} />
      </span>
      <span className={`tile-status${attention ? ' is-attention' : ''}`}>
        {attention && !e.repeatSuggested ? arrow : ''}
        {statusText(e)}
      </span>
    </button>
  )
}

/** "Blood pressure 115/75 mmHg" rather than the systolic half alone. */
function describeCapture(crewId: string, c: DeviceMeasurement): string {
  // Values saved together (blood pressure, sleep, exercise) share the same save time.
  const together = measurementsFor(crewId).filter((m) => m.savedAtMs === c.savedAtMs)
  const sys = together.find((m) => m.indicator === 'bp_systolic')
  const dia = together.find((m) => m.indicator === 'bp_diastolic')
  if (sys && dia) return `Blood pressure ${formatDailyValue('bp_systolic', sys.value)}/${formatDailyValue('bp_diastolic', dia.value)} mmHg`
  return together
    .map((m) => `${DAILY_INDICATORS[m.indicator].label} ${formatDailyValue(m.indicator, m.value)} ${DAILY_INDICATORS[m.indicator].unit}`)
    .join(' · ')
}

const CheckInIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden="true">
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7v5l3 2" />
  </svg>
)
const PlusIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" aria-hidden="true">
    <path d="M12 5v14M5 12h14" />
  </svg>
)
const ShareIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M12 15V3M7 8l5-5 5 5M5 13v6a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-6" />
  </svg>
)
