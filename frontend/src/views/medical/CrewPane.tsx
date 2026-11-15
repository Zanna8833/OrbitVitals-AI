import { useCallback, useState } from 'react'
import type { DataSource } from '../../data'
import type { ParameterId, ReviewEvent } from '../../domain/types'
import { DAILY_INDICATORS, EVENT_KIND_LABEL, PARAMETERS, PARAMETER_ORDER, QUALITY_LABEL, VITAL_PARAMETERS, formatDailyValue, formatValue } from '../../domain/parameters'
import { computeFreshness, FRESHNESS_LABEL } from '../../domain/freshness'
import { evaluateIndicator } from '../../domain/crewHealth'
import { formatAge, formatClock, missionDayOf, toMs } from '../../domain/time'
import { useQuery } from '../../hooks/useQuery'
import { href } from '../../hooks/useRoute'
import { ErrorState, Loading } from '../../components/Common'
import { EventKindBadge } from '../../components/EventKindBadge'
import { MetricGlyph } from '../../components/MetricGlyph'
import { QualityGlyph } from '../../components/StatusGlyphs'
import { Sparkline } from '../../components/Sparkline'
import { toneOf } from '../../components/tone'
import { TimeSeriesChart } from '../../components/TimeSeriesChart'
import { List, Row } from '../../components/ui'
import { loadSession } from '../sessionData'
import { useBoxSize, useFitMode } from '../../hooks/useLayout'
import { EvaluationsList } from './Evaluations'
import { loadNutrition, type NutritionData } from '../crew/Nutrition'
import { NUTRIENTS, progressOf, totalsOf } from '../../domain/nutrition'

/** Mean daily intake over the complete logged days of the last week, against NASA requirements. */
function weekNutrition(data: NutritionData, nowIso: string) {
  const days = [...new Set(data.intake.map((e) => e.eatenAt.slice(0, 10)))].filter((d) => d < nowIso.slice(0, 10))
  const sum = totalsOf(data.intake.filter((e) => days.includes(e.eatenAt.slice(0, 10))), data.foods)
  for (const k of Object.keys(sum.totals) as (keyof typeof sum.totals)[]) sum.totals[k] /= Math.max(1, days.length)
  const all = NUTRIENTS.map((d) => progressOf(d.id, sum, data.profile))
  return { days: days.length, off: all.filter((p) => p.state === 'over' || p.state === 'below').sort((a, b) => Number(b.state === 'over') - Number(a.state === 'over')) }
}

async function loadCrew(ds: DataSource, crewId: string) {
  const [snapshot, session, daily, evaluations] = await Promise.all([
    ds.getCrewSnapshot(crewId),
    loadSession(ds, crewId, PARAMETER_ORDER),
    ds.getDailyIndicators(crewId),
    ds.listEvaluations(crewId),
  ])
  const nutrition = await loadNutrition(ds, crewId, session.mission.now)
  return { snapshot, session, daily, evaluations, nutrition }
}

/** One crew member: latest values, the current session, and long-term changes. */
export function CrewPane({ crewId, events }: { crewId: string; events: ReviewEvent[] }) {
  const state = useQuery(useCallback((ds: DataSource) => loadCrew(ds, crewId), [crewId]))
  const [cursor, setCursor] = useState<number | null>(null)
  const [all, setAll] = useState(false)
  const fit = useFitMode()
  const [ref, size] = useBoxSize<HTMLDivElement>()
  if (state.status === 'loading') return <Loading />
  if (!state.data) return <ErrorState error={state.error!} />
  const { snapshot: s, session, daily, evaluations, nutrition } = state.data
  // The backend has no live sessions yet: then the main area shows its evaluations.
  const hasSession = PARAMETER_ORDER.some((p) => (session.series[p]?.samples.length ?? 0) > 0)
  const week = weekNutrition(nutrition, session.mission.now)
  const now = session.mission.now
  const fresh = computeFreshness(s.device.lastReceivedAt, now, s.device.expectedIntervalS)
  const today = missionDayOf(now, session.mission.missionStartDate)
  const changes = daily
    .map((d) => evaluateIndicator(d, today, 'their'))
    .filter((e) => e.series.indicator !== 'bp_diastolic' && ((e.position !== null && e.position !== 'within' && e.streakDays >= 3) || e.repeatSuggested))
  const pendingEvents = events.filter((e) => e.status !== 'reviewed')
  const shown: ParameterId[] = all ? PARAMETER_ORDER : ['heart_rate']
  const avail = size.height
  const firstPlot = fit && avail > 0 ? Math.max(70, all ? Math.floor((avail - 92 - 3 * 74) * 0.4) : avail - 96) : 150
  const restPlot = fit && avail > 0 && all ? Math.max(30, Math.floor((avail - 92 - firstPlot - 3 * 74 - 4) / 3)) : 70
  const charts = shown.map((p, i) => (
    <TimeSeriesChart
      key={p}
      title={PARAMETERS[p].label}
      series={session.series[p]}
      domain={session.domain}
      nowMs={toMs(now)}
      sessionStart={session.sessionStart}
      activities={session.activities}
      showActivityStrip={i === 0}
      band={session.bands[p]}
      highlight={null}
      cursor={cursor}
      onCursor={setCursor}
      plotHeight={i === 0 ? firstPlot : restPlot}
    />
  ))

  return (
    <article className="pane pane-fit">
      <header className="pane-header">
        <p className="eyebrow">{s.activity ? s.activity.label : 'No scheduled activity'}</p>
        <h1>{s.crew.displayName}</h1>
        <p className="pane-meta">
          <span className="freshness">
            <QualityGlyph quality={fresh === 'current' ? 'good' : fresh === 'delayed' ? 'uncertain' : fresh === 'stale' ? 'poor' : 'missing'} /> {FRESHNESS_LABEL[fresh]}
          </span>
          <span>{s.device.lastReceivedAt ? `Last data ${formatClock(s.device.lastReceivedAt)} UTC · ${formatAge(s.device.lastReceivedAt, now)}` : 'No data received'}</span>
        </p>
      </header>

      <div className="pane-grid">
        <div className="pane-main">
          {!hasSession && (
            <section className="card eval-card" aria-labelledby="eval-h">
              <div className="card-toolbar">
                <h2 className="card-title" id="eval-h">
                  Backend evaluations
                </h2>
                <span className="muted">{evaluations.length} stored</span>
              </div>
              <div className="eval-scroll">
                <EvaluationsList items={evaluations} />
              </div>
            </section>
          )}
          {hasSession && (
          <section className="card chart-card" aria-label="Current session">
            <div className="card-toolbar">
              <h2 className="card-title">Current session</h2>
              <label className="switch-label">
                <input type="checkbox" role="switch" checked={all} onChange={(e) => setAll(e.target.checked)} />
                All signals
              </label>
            </div>
            {fit ? (
              <div className="fill" ref={ref}>
                <div className="fill-inner">{size.height > 0 && charts}</div>
              </div>
            ) : (
              charts
            )}
          </section>
          )}
          {hasSession && (
          <div className="figures">
            {VITAL_PARAMETERS.map((p) => {
              const snap = s.parameters.find((x) => x.parameter === p)
              const shownSample = snap?.latest?.value != null ? snap.latest : snap?.lastValidSample
              return (
                <div key={p} className={`figure tone-${toneOf(p)}${fresh === 'stale' ? ' is-stale' : ''}`}>
                  <span className="figure-label">
                    <MetricGlyph id={p} size={13} /> {PARAMETERS[p].label}
                  </span>
                  <span className="figure-value">
                    {shownSample ? formatValue(p, shownSample.value) : '—'} <span className="unit">{PARAMETERS[p].unit}</span>
                  </span>
                  <span className="figure-note">
                    {shownSample ? (
                      <>
                        <QualityGlyph quality={shownSample.quality} size={10} /> {QUALITY_LABEL[shownSample.quality]} · {formatClock(shownSample.t, false)} UTC
                      </>
                    ) : (
                      'No sample'
                    )}
                  </span>
                </div>
              )
            })}
          </div>
          )}
        </div>

        <aside className="pane-side" aria-label="To review and day-to-day changes">
          <section aria-labelledby="crew-ev-h">
            <h2 className="side-title" id="crew-ev-h">
              To review
            </h2>
            {pendingEvents.length ? (
              <List label="Events for this crew member">
                {pendingEvents.map((e) => (
                  <Row
                    key={e.id}
                    href={href.event(e.id)}
                    leading={<EventKindBadge kind={e.kind} size={16} />}
                    title={EVENT_KIND_LABEL[e.kind]}
                    subtitle={`${e.parameter ? PARAMETERS[e.parameter].label : e.kind === 'crew_report' ? 'Shared trends' : 'All signals'} · ${formatClock(e.detectedAt, false)} UTC`}
                  />
                ))}
              </List>
            ) : (
              <p className="list-empty">Nothing to review.</p>
            )}
          </section>
          {hasSession && evaluations.length > 0 && (
            <section aria-labelledby="crew-eval-h">
              <h2 className="side-title" id="crew-eval-h">
                Backend evaluations
              </h2>
              <EvaluationsList items={evaluations} compact />
            </section>
          )}
          <section aria-labelledby="crew-nutrition-h">
            <h2 className="side-title" id="crew-nutrition-h">
              Nutrition <span className="muted">· mean of {week.days} {week.days === 1 ? 'day' : 'days'}</span>
            </h2>
            {week.days === 0 ? (
              <p className="list-empty">No intake logged in the last 7 days.</p>
            ) : week.off.length ? (
              <div className="nutri-off">
                {week.off.some((p) => p.state === 'over') && (
                  <p>
                    <span className="nutri-tag is-over">▲ Above limit</span> {week.off.filter((p) => p.state === 'over').map((p) => p.def.label).join(', ')}
                  </p>
                )}
                {week.off.some((p) => p.state === 'below') && (
                  <p>
                    <span className="nutri-tag">▼ Below minimum</span> {week.off.filter((p) => p.state === 'below').map((p) => p.def.label).join(', ')}
                  </p>
                )}
              </div>
            ) : (
              <p className="list-empty">Every nutrient within the NASA requirements.</p>
            )}
          </section>
          <section aria-labelledby="crew-daily-h">
            <h2 className="side-title" id="crew-daily-h">
              Day-to-day changes <span className="muted">· day {today}</span>
            </h2>
            {changes.length ? (
              <List label="Day-to-day changes">
                {changes.map((e) => (
                  <Row
                    key={e.series.indicator}
                    leading={
                      <span className={`symbol tone-${toneOf(e.series.indicator)}`}>
                        <MetricGlyph id={e.series.indicator} size={14} />
                      </span>
                    }
                    title={
                      <>
                        {DAILY_INDICATORS[e.series.indicator].label}{' '}
                        <span className="row-value">
                          {e.latest ? formatDailyValue(e.series.indicator, e.latest.value) : '—'} {DAILY_INDICATORS[e.series.indicator].unit}
                        </span>
                      </>
                    }
                    subtitle={<span className="text-attention">{e.headline}</span>}
                    trailing={<Sparkline series={e.series} width={72} height={24} />}
                  />
                ))}
              </List>
            ) : (
              <p className="list-empty">No sustained changes against their own usual range.</p>
            )}
          </section>
        </aside>
      </div>
    </article>
  )
}
