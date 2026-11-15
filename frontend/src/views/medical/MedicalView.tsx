import { useState } from 'react'
import type { DataSource } from '../../data'
import type { CrewSnapshot, ReviewEvent } from '../../domain/types'
import { PARAMETERS } from '../../domain/parameters'
import { computeFreshness, FRESHNESS_GLYPH } from '../../domain/freshness'
import { initialsOf } from '../../domain/overview'
import { formatAge, formatClock, formatDate } from '../../domain/time'
import { useQuery } from '../../hooks/useQuery'
import { href, type MedicalSelection } from '../../hooks/useRoute'
import { ErrorState, LinkBanner, Loading, RefreshErrorNotice } from '../../components/Common'
import { EventKindBadge } from '../../components/EventKindBadge'
import { QualityGlyph } from '../../components/StatusGlyphs'
import { List, Row, Segmented } from '../../components/ui'
import { EventPane } from './EventPane'
import { SleepPane, SLEEP_FUTURE, SLEEP_PAST } from './SleepPane'
import { Moon } from '../../components/SleepGrid'
import { addDays, coverageOf, nightsFrom } from '../../domain/sleepPlan'
import { CrewPane } from './CrewPane'
import { config } from '../../config'
import type { BackendEvaluation } from '../../domain/metricCatalog'

const DOMAIN_LABEL: Record<string, string> = { vital_signs: 'Vital signs', sleep: 'Sleep', physical_activity: 'Physical activity', nutrition: 'Nutrition', cognition: 'Cognition' }

async function loadOverview(ds: DataSource) {
  const [mission, crew, events] = await Promise.all([ds.getMissionStatus(), ds.listCrew(), ds.listEvents()])
  const tonight = mission.now.slice(0, 10)
  const [snapshots, sleepPlan, evaluations] = await Promise.all([
    Promise.all(crew.map((c) => ds.getCrewSnapshot(c.id))),
    ds.listSleepAidPlan(addDays(tonight, -SLEEP_PAST), addDays(tonight, SLEEP_FUTURE - 1)),
    Promise.all(crew.map((c) => ds.listEvaluations(c.id).catch(() => []))),
  ])
  // The latest evaluation of each astronaut and domain that asks for a review.
  const flagged = crew.flatMap((c, i) => {
    const latest = new Map<string, BackendEvaluation>()
    for (const e of evaluations[i]) if (!latest.has(e.domain) || latest.get(e.domain)!.window_end < e.window_end) latest.set(e.domain, e)
    return [...latest.values()].filter((e) => e.status === 'attention' || e.status === 'alert').map((e) => ({ crewId: c.id, evaluation: e }))
  })
  return { mission, events, snapshots, sleepPlan, flagged }
}

/**
 * The Flight Surgeon's single workspace, like a mail app:
 * left, what needs review and who is on board; right, the selected item.
 * Replaces the former dashboard, event page and crew sections.
 */
export function MedicalView({ selection }: { selection: MedicalSelection }) {
  const state = useQuery(loadOverview)
  const [filter, setFilter] = useState<'open' | 'all'>('open')

  if (state.status === 'loading') return <Loading />
  if (!state.data) return <ErrorState error={state.error!} />
  const { mission, events, snapshots, sleepPlan, flagged } = state.data
  const tonight = mission.now.slice(0, 10)
  const crewIds = snapshots.map((x) => x.crew.id)
  const uncovered = nightsFrom(tonight, SLEEP_FUTURE).filter((n) => coverageOf(sleepPlan, crewIds, n).uncovered)
  const pending = events.filter((e) => e.status !== 'reviewed')
  const toReview = pending.length + flagged.length
  const listed = filter === 'open' ? pending : events
  const name = (id: string) => snapshots.find((s) => s.crew.id === id)?.crew.displayName ?? id

  // With nothing selected, desktop shows the first item to review (or the first crew member).
  const effective: MedicalSelection =
    selection ??
    (pending[0]
      ? { type: 'event', id: pending[0].id }
      : flagged[0]
        ? { type: 'crew', id: flagged[0].crewId }
        : snapshots[0]
          ? { type: 'crew', id: snapshots[0].crew.id }
          : null)

  return (
    <div className={`split${selection ? ' has-selection' : ''}`}>
      <aside className="sidebar" aria-label="Review list">
        <div className="sidebar-head">
          <p className="eyebrow">
            {formatDate(mission.now)} · {formatClock(mission.now, false)} UTC
          </p>
          <h1>Review</h1>
          <p className="muted">{toReview ? `${toReview} item${toReview === 1 ? '' : 's'} to review` : 'Nothing to review'}</p>
        </div>
        {state.status === 'error' && <RefreshErrorNotice error={state.error} />}
        <LinkBanner mission={mission} audience="surgeon" />

        <div className="sidebar-section">
          <Segmented
            size="small"
            label="Show"
            value={filter}
            onChange={setFilter}
            options={[
              { value: 'open', label: `To review (${toReview})` },
              { value: 'all', label: `All (${events.length + flagged.length})` },
            ]}
          />
          {listed.length || flagged.length ? (
            <List label="Items to review">
              {flagged.map(({ crewId, evaluation: ev }) => (
                <Row
                  key={ev.evaluation_id}
                  href={href.medicalCrew(crewId)}
                  selected={effective?.type === 'crew' && effective.id === crewId && !selection?.type}
                  leading={<span className="symbol tone-orange">▲</span>}
                  title={`${DOMAIN_LABEL[ev.domain] ?? ev.domain} · ${ev.status === 'alert' ? 'alert' : 'attention'}`}
                  subtitle={`${name(crewId)} · to ${formatDate(ev.window_end)}`}
                  chevron={false}
                />
              ))}
              {listed.map((e) => (
                <EventRow key={e.id} event={e} crewName={name(e.crewId)} now={mission.now} selected={effective?.type === 'event' && effective.id === e.id} />
              ))}
            </List>
          ) : (
            <p className="list-empty">{events.length ? 'All items have been reviewed.' : 'Nothing to review.'}</p>
          )}
        </div>

        <div className="sidebar-section">
          <h2 className="list-title">Crew</h2>
          <List label="Crew">
            {snapshots.map((s) => (
              <CrewRow key={s.crew.id} snapshot={s} now={mission.now} selected={effective?.type === 'crew' && effective.id === s.crew.id} />
            ))}
          </List>
        </div>
        <div className="sidebar-section">
          <h2 className="list-title">Crew schedule</h2>
          <List label="Crew schedule">
            <Row
              href={href.medicalSleep()}
              selected={effective?.type === 'sleep'}
              leading={
                <span className="symbol tone-rest">
                  <Moon size={14} />
                </span>
              }
              title="Sleeping-pill plan"
              subtitle={
                uncovered.length ? (
                  <span className="text-attention">
                    {uncovered.length === 1 ? '1 night' : `${uncovered.length} nights`} without cover
                  </span>
                ) : (
                  `Every night covered · next ${SLEEP_FUTURE}`
                )
              }
              trailing={uncovered.length ? <span className="badge badge-attention">{uncovered.length}</span> : undefined}
              chevron={false}
            />
            <Row
              href={config.cognitionUrl}
              newTab
              leading={<span className="symbol tone-rest">◎</span>}
              title="Cognition results ↗"
              subtitle="Opens the ground research view"

              chevron={false}
            />
          </List>
        </div>
        <p className="fineprint sidebar-note">Items are review signals from OrbitVitals rules and the backend engines, not clinical alarms.</p>
      </aside>

      <section className="detail" aria-label="Selected item">
        <a className="back-link" href={href.medical()}>
          ‹ Review
        </a>
        {effective?.type === 'event' && <EventPane key={effective.id} eventId={effective.id} />}
        {effective?.type === 'crew' && <CrewPane key={effective.id} crewId={effective.id} events={events.filter((e) => e.crewId === effective.id)} />}
        {effective?.type === 'sleep' && (
          <SleepPane crew={snapshots.map((x) => x.crew)} entries={sleepPlan} tonight={tonight} missionStart={mission.missionStartDate} />
        )}
        {!effective && <p className="list-empty">Select an item.</p>}
      </section>
    </div>
  )
}

/** Short titles for the list; the full title is in the detail. */
const SHORT_KIND: Record<ReviewEvent['kind'], string> = {
  outside_personal_range: 'Above usual range',
  signal_quality: 'Signal quality',
  data_stale: 'Data not updated',
  crew_report: 'Shared by crew',
}

function EventRow({ event, crewName, now, selected }: { event: ReviewEvent; crewName: string; now: string; selected: boolean }) {
  const what = event.parameter ? PARAMETERS[event.parameter].shortLabel : event.kind === 'crew_report' ? 'Daily trends' : 'All signals'
  return (
    <Row
      href={href.event(event.id)}
      selected={selected}
      leading={<EventKindBadge kind={event.kind} size={16} />}
      title={SHORT_KIND[event.kind]}
      subtitle={
        <>
          {crewName} · {what}
          {event.status === 'in_review' ? ' · in review' : event.status === 'reviewed' ? ' · reviewed' : ''}
        </>
      }
      trailing={
        <span className="row-time" title={formatAge(event.detectedAt, now)}>
          {formatClock(event.detectedAt, false)}
        </span>
      }
      chevron={false}
    />
  )
}

function CrewRow({ snapshot: s, now, selected }: { snapshot: CrewSnapshot; now: string; selected: boolean }) {
  const fresh = computeFreshness(s.device.lastReceivedAt, now, s.device.expectedIntervalS)
  const status =
    fresh === 'current'
      ? 'Data up to date'
      : s.device.lastReceivedAt
        ? `No data since ${formatClock(s.device.lastReceivedAt, false)}`
        : 'No data received'
  return (
    <Row
      href={href.medicalCrew(s.crew.id)}
      selected={selected}
      leading={<span className="avatar">{initialsOf(s.crew.displayName)}</span>}
      title={s.crew.displayName}
      subtitle={
        <>
          <QualityGlyph quality={FRESHNESS_GLYPH[fresh]} size={10} /> {status}
        </>
      }
      trailing={s.openEvents ? <span className="badge">{s.openEvents}</span> : undefined}
      chevron={false}
    />
  )
}
