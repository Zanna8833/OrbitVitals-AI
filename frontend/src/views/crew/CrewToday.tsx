import { useCallback, useState } from 'react'
import type { ReactNode } from 'react'
import type { DataSource } from '../../data'
import type { DailyIndicatorId, MissionStatus } from '../../domain/types'
import { DAILY_INDICATORS, PARAMETER_ORDER, formatDailyValue } from '../../domain/parameters'
import { checkedInOn, describeCheckIn, evaluateIndicator, summarizeHealth, type IndicatorEvaluation } from '../../domain/crewHealth'
import { describeCollection, describeSensors } from '../../domain/crewStatus'
import { describeActivityProgress, describeNextStep } from '../../domain/crewGuidance'
import { formatClock, formatDate, formatDuration, missionDayOf, toIso, toMs } from '../../domain/time'
import { useQuery } from '../../hooks/useQuery'
import { href, type CrewPage } from '../../hooks/useRoute'
import { useMutation } from '../../hooks/useMutation'
import { addDays, coverageOf, isPlanned, nightLabel, nightsFrom, wouldUncover } from '../../domain/sleepPlan'
import { Moon, SleepGrid } from '../../components/SleepGrid'
import { measurementsFor } from '../../state/crewLocal'
import type { DeviceMeasurement } from '../../domain/measurements'
import { Empty, ErrorState, FormError, LinkBanner, Loading, RefreshErrorNotice } from '../../components/Common'
import { MetricGlyph } from '../../components/MetricGlyph'
import { QualityGlyph } from '../../components/StatusGlyphs'
import { Sparkline } from '../../components/Sparkline'
import { toneOf } from '../../components/tone'
import { List, Row, Sheet, Symbol } from '../../components/ui'
import { DailyTrendChart } from '../../components/DailyTrendChart'
import { useBoxSize, useFitMode } from '../../hooks/useLayout'
import { CheckInSheet, IndicatorSheet, MeasureSheet, ShareSheet, statusText } from './Sheets'
import { useShare } from './shareSync'

/** Shown inside the single Health rectangle on the home screen. */
const DEFAULT_TILES: DailyIndicatorId[] = ['resting_hr', 'sleep_duration', 'resting_spo2', 'hrv_rmssd', 'bp_systolic', 'resting_resp_rate']
/** Every indicator, grouped by area, on the Health page. */
const ALL_TILES: DailyIndicatorId[] = [
  'resting_hr', 'hrv_rmssd', 'bp_systolic', 'resting_spo2', 'resting_resp_rate',
  'sleep_duration', 'sleep_efficiency', 'activity_minutes', 'body_temperature', 'body_mass',
]
/** Nights shown: a few past ones for context, then the next two weeks. */
const PLAN_PAST = 3
const PLAN_FUTURE = 11
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
    ds.listSleepAidPlan(addDays(night, -PLAN_PAST), addDays(night, PLAN_FUTURE - 1)),
  ])
  return { mission, crew, member, live: { snapshot, messages, series, activities, daily, checkIns, sleepPlan } }
}

type Sheet =
  | { type: 'indicator'; id: DailyIndicatorId }
  | { type: 'checkin' }
  | { type: 'measure'; id: DailyIndicatorId | null }
  | { type: 'share' }
  | { type: 'sleep-confirm'; night: string }
  | null

const setPlan = (ds: DataSource, crewId: string, night: string, planned: boolean) => ds.setSleepAidPlan(crewId, night, planned)

/**
 * The astronaut's area, three pages that each fit a laptop screen with no scroll:
 * - Today (home): what is happening now, what deserves attention, what I can do,
 *   one Health rectangle and the crew sleep plan;
 * - Health: every indicator and the trend of the one selected;
 * - Sleep plan: the crew calendar of planned sleep-aid nights.
 * Tasks (check-in, measurement, share, details) open as sheets.
 */
export function CrewToday({ crewId, page = 'home' }: { crewId: string | null; page?: CrewPage }) {
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
  const sharing = useShare(memberId, mission)
  const offline = mission.link.state === 'offline'

  const today = missionDayOf(mission.now, mission.missionStartDate)
  const evaluations = live.daily.map((s) => evaluateIndicator(s, today))
  const byId = (id: DailyIndicatorId) => evaluations.find((e) => e.series.indicator === id)
  const summary = summarizeHealth(evaluations)
  const toRepeat = evaluations.filter((e) => e.repeatSuggested && e.series.indicator !== 'bp_diastolic')
  const checkIn = checkedInOn(live.checkIns, mission.now)
  const lastCapture = measurementsFor(memberId)[0]

  const flagged = [...toRepeat, ...summary.changed].map((e) => (e.series.indicator === 'bp_diastolic' ? 'bp_systolic' : e.series.indicator))
  const [selected, setSelected] = useState<DailyIndicatorId>(() => flagged[0] ?? 'resting_hr')

  // Sleep plan
  const tonight = mission.now.slice(0, 10)
  const crewIds = crew.map((c) => c.id)
  const plan = useMutation(setPlan)
  const [busyNight, setBusyNight] = useState<string | null>(null)
  const applyPlan = async (night: string, planned: boolean) => {
    setBusyNight(night)
    await plan.run(memberId, night, planned)
    setBusyNight(null)
  }
  const toggleNight = (night: string) => {
    const planned = isPlanned(live.sleepPlan, memberId, night)
    if (!planned && wouldUncover(live.sleepPlan, crewIds, memberId, night)) setSheet({ type: 'sleep-confirm', night })
    else void applyPlan(night, !planned)
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
    <div className="today">
      <header className="today-head">
        <div className="today-title">
          {page !== 'home' && (
            <a className="back-link-inline" href={href.crew(memberId)}>
              ‹ Today
            </a>
          )}
          <h1>{page === 'home' ? 'Today' : page === 'health' ? 'Health' : 'Sleep plan'}</h1>
          <p className="eyebrow">
            {page === 'health'
              ? `Mission day ${today} · compared with your own usual range`
              : page === 'sleep'
                ? 'Who plans a sleep aid, and when'
                : `${formatDate(mission.now)} · Mission day ${today}`}
          </p>
        </div>
        <label className="viewer">
          <span className="muted">Viewing as</span>
          <select value={memberId} onChange={(e) => (window.location.hash = href.crew(e.target.value, page))} aria-label="Crew member (demo)">
            {crew.map((c) => (
              <option key={c.id} value={c.id}>
                {c.displayName}
              </option>
            ))}
          </select>
        </label>
      </header>

      {page === 'home' && (
      <div className="today-grid">
        <div className="today-col">
          {/* During an activity the Now card already carries the link status. */}
          {!progress?.current && <LinkBanner mission={mission} audience="crew" />}

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
                  {offline && <span className="muted"> · shared reports wait on this device</span>}
                </li>
                {/* A sensor-level problem is only worth a line while data is otherwise flowing. */}
                {sensors
                  .filter((s) => s.level !== 'good' && collection.level === 'good')
                  .map((s) => (
                    <li key={s.deviceId}>
                      <QualityGlyph quality={s.level} /> {s.deviceLabel.replace(/\s*\(simulated\)$/, '')}: {s.text.toLowerCase()}
                    </li>
                  ))}
                {!asked && <li className="muted">Nothing to do — carry on with your activity.</li>}
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
              <span className="message-from">Medical team · {formatClock(message.createdAt, false)} UTC</span>
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
              subtitle={lastCapture ? `Last: ${describeCapture(memberId, lastCapture)}` : 'Guided, simulated reading'}
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
                      : 'Your trends and a note — only if you want'
              }
              trailing={sharing.queued ? <span className="badge">{sharing.queued}</span> : undefined}
              onClick={() => setSheet({ type: 'share' })}
            />
          </List>
          </div>
        </div>

        <div className="today-col today-col-wide">
          <HealthCard memberId={memberId} today={today} byId={byId} attention={flagged.length} />
          <SleepCard
            memberId={memberId}
            crew={crew}
            entries={live.sleepPlan}
            tonight={tonight}
            busyNight={busyNight}
            error={plan.error}
            onToggle={toggleNight}
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
          />
        </div>
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
        daily={live.daily}
        initial={sheet?.type === 'measure' ? sheet.id : null}
        onClose={() => setSheet(null)}
      />
      <ShareSheet open={sheet?.type === 'share'} onClose={() => setSheet(null)} sharing={sharing} summary={changedNames.length ? `the change in ${changedNames.join(' and ')}` : ''} />
      <Sheet open={sheet?.type === 'sleep-confirm'} title="Nobody would be without a sleep aid" onClose={() => setSheet(null)}>
        {sheet?.type === 'sleep-confirm' && (
          <div className="stack">
            <p className="body-text">
              {crew
                .filter((c) => c.id !== memberId && isPlanned(live.sleepPlan, c.id, sheet.night))
                .map((c) => c.displayName)
                .join(' and ')}{' '}
              already planned a sleep aid for the night of{' '}
              <strong>
                {nightLabel(sheet.night).weekday} {nightLabel(sheet.night).day} {nightLabel(sheet.night).month}
              </strong>
              . If you add yours, nobody on board would stay without one.
            </p>
            <p className="body-text muted">
              The crew agreed that at least one person stays without a sleep aid every night, ready for an emergency (demo rule — the real rule is set by
              the medical team). Talk with your crew first.
            </p>
            <div className="button-row">
              <button type="button" className="btn btn-primary" onClick={() => setSheet(null)}>
                Keep my night free
              </button>
              <button
                type="button"
                className="btn"
                onClick={() => {
                  const night = sheet.night
                  setSheet(null)
                  void applyPlan(night, true)
                }}
              >
                Plan anyway
              </button>
            </div>
          </div>
        )}
      </Sheet>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Home: the single Health rectangle                                   */
/* ------------------------------------------------------------------ */

function HealthCard({
  memberId,
  today,
  byId,
  attention,
}: {
  memberId: string
  today: number
  byId: (id: DailyIndicatorId) => IndicatorEvaluation | undefined
  attention: number
}) {
  return (
    <a className="card health-card" href={href.crew(memberId, 'health')} aria-label={`Health: ${attention ? `${attention} to look at` : 'all within your usual range'}. Open all indicators`}>
      <div className="card-head">
        <span className="card-head-title tone-heart">
          <MetricGlyph id="resting_hr" size={17} /> Health
        </span>
        <span className="card-head-link">
          {ALL_TILES.length} indicators <Chevron />
        </span>
      </div>
      <p className={`health-status${attention ? ' is-attention' : ''}`}>
        {attention ? `${attention} ${attention === 1 ? 'indicator' : 'indicators'} to look at` : 'All within your usual range'}
        <span className="muted"> · day {today}</span>
      </p>
      <div className="mini-grid">
        {DEFAULT_TILES.map((id) => {
          const e = byId(id)
          const d = id === 'bp_systolic' ? byId('bp_diastolic') : undefined
          const att = !!e && (e.repeatSuggested || (e.position !== null && e.position !== 'within' && e.streakDays >= 3))
          return (
            <div key={id} className={`mini tone-${toneOf(id)}${att ? ' is-attention' : ''}`}>
              <span className="mini-label">
                <MetricGlyph id={id} size={12} /> {id === 'bp_systolic' ? 'Blood pressure' : id === 'hrv_rmssd' ? 'HRV' : DAILY_INDICATORS[id].label}
              </span>
              <span className="mini-value">
                {e?.latest ? formatDailyValue(id, e.latest.value) : '—'}
                {d?.latest && `/${formatDailyValue('bp_diastolic', d.latest.value)}`}
                <span className="unit"> {DAILY_INDICATORS[id].unit === 'ms RMSSD' ? 'ms' : DAILY_INDICATORS[id].unit}</span>
                {att && e && !e.repeatSuggested && <span className="mini-arrow">{e.position === 'above' ? ' ↑' : ' ↓'}</span>}
                {att && e?.repeatSuggested && <span className="mini-arrow"> !</span>}
              </span>
            </div>
          )
        })}
      </div>
    </a>
  )
}

/* ------------------------------------------------------------------ */
/* Sleep plan                                                          */
/* ------------------------------------------------------------------ */

interface SleepProps {
  memberId: string
  crew: { id: string; displayName: string }[]
  entries: Live['sleepPlan']
  tonight: string
  busyNight: string | null
  error: string | null
  onToggle: (night: string) => void
}

function SleepCard({ memberId, crew, entries, tonight, busyNight, error, onToggle }: SleepProps) {
  const nights = nightsFrom(tonight, 7)
  const ids = crew.map((c) => c.id)
  const now = coverageOf(entries, ids, tonight)
  const mine = isPlanned(entries, memberId, tonight)
  const uncovered = nights.map((n) => coverageOf(entries, ids, n)).filter((c) => c.uncovered)
  return (
    <section className="card sleep-card" aria-labelledby="sleep-h">
      <div className="card-head">
        <h2 id="sleep-h" className="card-head-title tone-rest">
          <Moon size={16} /> Sleep plan
        </h2>
        <a className="card-head-link" href={href.crew(memberId, 'sleep')}>
          Two weeks <Chevron />
        </a>
      </div>
      <p className="sleep-summary">
        <strong>Tonight</strong> · {mine ? 'you planned a sleep aid' : 'no sleep aid planned for you'} · {now.available} of {now.total} crew without one
      </p>
      <SleepGrid nights={nights} today={tonight} crew={crew} entries={entries} me={memberId} busyNight={busyNight} onToggle={onToggle} />
      <SleepNotice uncovered={uncovered.map((c) => c.night)} />
      <FormError message={error} />
    </section>
  )
}

function SleepNotice({ uncovered }: { uncovered: string[] }) {
  if (!uncovered.length) {
    return <p className="sleep-note">Every night has at least one crew member without a sleep aid.</p>
  }
  const names = uncovered.map((n) => `${nightLabel(n).weekday} ${nightLabel(n).day}`).join(', ')
  return (
    <p className="sleep-note is-attention" role="status">
      <svg width="11" height="10" viewBox="0 0 11 10" aria-hidden="true">
        <path d="M5.5 0.8 10.4 9.2H0.6Z" fill="currentColor" />
      </svg>{' '}
      {names}: everyone has planned a sleep aid. Coordinate with the crew.
    </p>
  )
}

function SleepPage({ memberId, crew, entries, tonight, busyNight, error, onToggle }: SleepProps) {
  const nights = nightsFrom(addDays(tonight, -PLAN_PAST), PLAN_PAST + PLAN_FUTURE)
  const ids = crew.map((c) => c.id)
  const upcoming = nightsFrom(tonight, PLAN_FUTURE).map((n) => coverageOf(entries, ids, n))
  const mine = upcoming.filter((c) => c.planned.includes(memberId)).length
  return (
    <div className="sleep-page">
      <section className="card sleep-plan-card" aria-label="Sleep-aid calendar">
        <p className="body-text muted sleep-intro">
          Tap a night in your row to plan or remove a sleep aid. Everyone on board sees the plan, so at least one person stays rested and ready.
        </p>
        <SleepGrid nights={nights} today={tonight} crew={crew} entries={entries} me={memberId} busyNight={busyNight} onToggle={onToggle} />
        <ul className="legend">
          <li>
            <span className="sg-mark legend-moon">
              <Moon size={11} />
            </span>{' '}
            Sleep aid planned
          </li>
          <li>
            <span className="sg-warn">▲ 0/3</span> nobody left without one
          </li>
          <li className="muted">Past nights are shown for reference and cannot be changed</li>
        </ul>
        <FormError message={error} />
      </section>
      <aside className="sleep-side" aria-label="Summary">
        <section className="card">
          <p className="eyebrow">Next {PLAN_FUTURE} nights</p>
          <p className="sleep-big">
            {mine} <span className="unit">{mine === 1 ? 'night' : 'nights'} planned by you</span>
          </p>
          <SleepNotice uncovered={upcoming.filter((c) => c.uncovered).map((c) => c.night)} />
        </section>
        <section className="card">
          <p className="eyebrow">How it works</p>
          <ul className="plain-list">
            <li>Only the night is recorded: no medicine name and no dose. Those stay in your medical record.</li>
            <li>Demo rule: at least one crew member without a sleep aid every night. The real rule is set by the mission’s medical team.</li>
            <li>Your flight surgeon sees the same plan and any night without cover.</li>
          </ul>
        </section>
      </aside>
    </div>
  )
}

const Chevron = (): ReactNode => (
  <svg width="7" height="12" viewBox="0 0 8 13" aria-hidden="true">
    <path d="M1.5 1.5 6.5 6.5l-5 5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
)

/** The trend of the selected tile, sized to the space left on screen. */
function TrendCard({
  evaluation: e,
  paired,
  onDetails,
}: {
  evaluation: IndicatorEvaluation | undefined
  paired?: IndicatorEvaluation
  onDetails: () => void
}) {
  const fit = useFitMode()
  const [ref, size] = useBoxSize<HTMLDivElement>()
  if (!e) return null
  const id = e.series.indicator
  const def = DAILY_INDICATORS[id]
  const attention = e.repeatSuggested || (e.position !== null && e.position !== 'within' && e.streakDays >= 3)
  const chartH = fit ? Math.max(110, size.height - 30) : 170
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
          <p className={`trend-status${attention ? ' is-attention' : ''}`}>
            {statusText(e)} · mission days {e.series.days[0]?.missionDay}–{e.series.days[e.series.days.length - 1]?.missionDay}
          </p>
        </div>
        <div className="trend-actions">
          <button type="button" className="btn btn-small" onClick={onDetails}>
            Details
          </button>
        </div>
      </div>
      <div className="fill" ref={ref}>
        <div className="fill-inner">{(size.height > 0 || !fit) && <DailyTrendChart key={id} series={e.series} height={chartH} />}</div>
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
          <h2 id="hl-h">
            {DAILY_INDICATORS[id].label} has been {side} than usual for {main.streakDays} days
          </h2>
          <p>
            A change from your own pattern, not a diagnosis.
            {others.length ? ` Also changed: ${others.join(', ')}.` : ''}
            {repeat ? ` Today’s ${DAILY_INDICATORS[repeat.series.indicator].label.toLowerCase()} reading needs repeating.` : ''}
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
  if (c.indicator === 'bp_systolic' || c.indicator === 'bp_diastolic') {
    const all = measurementsFor(crewId)
    const sys = c.indicator === 'bp_systolic' ? c : all.find((m) => m.indicator === 'bp_systolic' && m.id === c.id.replace(/-DIA$/, ''))
    const dia = all.find((m) => m.indicator === 'bp_diastolic' && sys && m.id === `${sys.id}-DIA`)
    if (sys && dia) return `Blood pressure ${formatDailyValue('bp_systolic', sys.value)}/${formatDailyValue('bp_diastolic', dia.value)} mmHg`
  }
  return `${DAILY_INDICATORS[c.indicator].label} ${formatDailyValue(c.indicator, c.value)} ${DAILY_INDICATORS[c.indicator].unit}`
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
