import { useCallback, useState, type FormEvent } from 'react'
import { CREW_MESSAGE_TEMPLATES, DataSourceError, type DataSource } from '../../data'
import type { CheckIn, CrewMessage, DailyIndicatorSeries, EventStatus, MissionStatus, ParameterId, ReviewEvent } from '../../domain/types'
import { DAILY_INDICATORS, EVENT_KIND_LABEL, EVENT_STATUS_LABEL, EVENT_STATUSES, PARAMETERS, PARAMETER_ORDER, REASON_LABEL, formatDailyValue, formatValue } from '../../domain/parameters'
import { compareWithBand, countQuality, expectedSampleCount, findGaps, goodValues, samplesInWindow, statsOf } from '../../domain/observations'
import { describeCheckIn, evaluateIndicator } from '../../domain/crewHealth'
import { formatAge, formatClock, formatDuration, formatUtc, missionDayOf, toIso, toMs } from '../../domain/time'
import { useQuery } from '../../hooks/useQuery'
import { useMutation } from '../../hooks/useMutation'
import { ErrorState, FormError, Loading } from '../../components/Common'
import { TimeSeriesChart } from '../../components/TimeSeriesChart'
import { EventStatusChip } from '../../components/StatusGlyphs'
import { Sparkline } from '../../components/Sparkline'
import { toneOf } from '../../components/tone'
import { MetricGlyph } from '../../components/MetricGlyph'
import { Segmented, Sheet } from '../../components/ui'
import { loadSession, type SessionData } from '../sessionData'
import { useBoxSize, useFitMode } from '../../hooks/useLayout'

async function loadEvent(ds: DataSource, eventId: string) {
  const event = await ds.getEvent(eventId)
  const [crew, messages, mission] = await Promise.all([ds.listCrew(), ds.listCrewMessages(event.crewId), ds.getMissionStatus()])
  const common = {
    event,
    mission,
    crewName: crew.find((c) => c.id === event.crewId)?.displayName ?? event.crewId,
    messages: messages.filter((m) => m.relatedEventId === event.id),
  }
  if (event.kind === 'crew_report') {
    const [daily, checkIns] = await Promise.all([ds.getDailyIndicators(event.crewId), ds.listCheckIns(event.crewId)])
    return { ...common, report: { daily, checkIns }, session: null }
  }
  return { ...common, report: null, session: await loadSession(ds, event.crewId, PARAMETER_ORDER) }
}

export function EventPane({ eventId }: { eventId: string }) {
  const state = useQuery(useCallback((ds: DataSource) => loadEvent(ds, eventId), [eventId]))
  if (state.status === 'loading') return <Loading />
  if (!state.data) {
    const notFound = state.error instanceof DataSourceError && state.error.code === 'not_found'
    return <ErrorState error={state.error!} title={notFound ? 'This item is not available in the current scenario' : 'Unable to load the item'} />
  }
  const { event, mission, crewName, messages, report, session } = state.data
  const what = event.parameter ? PARAMETERS[event.parameter].label : event.kind === 'crew_report' ? 'Shared daily trends' : 'All signals'

  return (
    <article className="pane pane-fit">
      <header className="pane-header">
        <p className="eyebrow">
          {crewName} · {what}
        </p>
        <h1>{EVENT_KIND_LABEL[event.kind]}</h1>
        <p className="pane-meta">
          <EventStatusChip status={event.status} />
          <span>
            {event.kind === 'crew_report' ? 'Shared' : 'Detected'} {formatUtc(event.detectedAt, false)} · {formatAge(event.detectedAt, mission.now)}
          </span>
        </p>
        <p className="why">
          <strong>{event.kind === 'crew_report' ? 'From the crew member. ' : 'Why it is here. '}</strong>
          {event.trigger.description}
        </p>
      </header>

      <div className="pane-grid">
        <div className="pane-main">
          {session && <SessionEvidence event={event} session={session} />}
          {report && <ReportTrends crewName={crewName} mission={mission} daily={report.daily} />}
        </div>
        <aside className="pane-side" aria-label="Review and context">
          <ReviewCard event={event} crewName={crewName} offline={mission.link.state === 'offline'} sent={messages} />
          {session && event.parameter && <Provenance event={event} parameter={event.parameter} session={session} />}
          {report && <ReportCheckIns checkIns={report.checkIns} />}
          {session && !event.parameter && (
            <p className="fineprint side-note">The data alone cannot tell whether the device, the transmission or something else is the cause.</p>
          )}
        </aside>
      </div>
    </article>
  )
}

/* ------------------------------------------------------------------ */
/* Evidence from the session data                                      */
/* ------------------------------------------------------------------ */

const PAD_MS = 5 * 60 * 1000
/** Vertical space a chart needs besides its plot (title row, activity strip, quality strip, time axis). */
const CHART_EXTRA = { strip: 92, plain: 74 }

function SessionEvidence({ event, session }: { event: ReviewEvent; session: SessionData }) {
  const feedLevel = !event.parameter
  const [range, setRange] = useState<'window' | 'session'>(feedLevel ? 'session' : 'window')
  const [compare, setCompare] = useState(false)
  const [cursor, setCursor] = useState<number | null>(null)
  const fit = useFitMode()
  const [ref, size] = useBoxSize<HTMLDivElement>()
  const nowMs = toMs(session.mission.now)
  const a = toMs(event.window.start)
  const b = toMs(event.window.end)
  const domain: [number, number] =
    range === 'session' ? session.domain : [Math.max(session.domain[0], a - PAD_MS), Math.min(nowMs, Math.max(b + PAD_MS, a + 2 * PAD_MS))]
  // A feed-level event (device not reporting) starts from heart rate; the rest is one switch away.
  const main: ParameterId[] = [event.parameter ?? 'heart_rate']
  const others = PARAMETER_ORDER.filter((p) => !main.includes(p))

  // Plot heights: in fit mode they share the measured space; otherwise fixed.
  const avail = size.height
  let mainPlot = 190
  if (fit && avail > 0) mainPlot = Math.max(60, avail - CHART_EXTRA.strip - 4)
  const chart = (p: ParameterId, plot: number, strip: boolean) => (
    <TimeSeriesChart
      key={p}
      title={PARAMETERS[p].label}
      series={session.series[p]}
      domain={domain}
      nowMs={nowMs}
      sessionStart={session.sessionStart}
      activities={session.activities}
      showActivityStrip={strip}
      band={session.bands[p]}
      highlight={feedLevel ? null : event.window}
      cursor={cursor}
      onCursor={setCursor}
      plotHeight={plot}
    />
  )
  const charts = <>{main.map((p) => chart(p, mainPlot, true))}</>
  // Comparison sheet: four charts sized to the window, so the sheet does not scroll either.
  const sheetSpace = Math.min(window.innerHeight * 0.86, 860) - 150 - CHART_EXTRA.strip - others.length * CHART_EXTRA.plain
  const sheetPlots = { main: Math.max(60, Math.floor(sheetSpace * 0.4)), other: Math.max(36, Math.floor((sheetSpace * 0.6) / others.length)) }

  return (
    <>
      <section className="card chart-card" aria-label="Trend">
        <div className="card-toolbar">
          <Segmented
            size="small"
            label="Time range"
            value={range}
            onChange={setRange}
            options={[
              { value: 'window', label: 'Event ±5 min' },
              { value: 'session', label: 'Whole session' },
            ]}
          />
          <button type="button" className="btn btn-small" onClick={() => setCompare(true)}>
            Compare signals
          </button>
        </div>
        {fit ? (
          <div className="fill" ref={ref}>
            <div className="fill-inner">{avail > 0 && charts}</div>
          </div>
        ) : (
          charts
        )}
        <ul className="legend" aria-label="Legend">
          <li>
            <i className="lg-line" /> Measured
          </li>
          <li>
            <i className="lg-ring" /> Uncertain
          </li>
          <li>
            <i className="lg-band" /> Usual range
          </li>
          {!feedLevel && (
            <li>
              <i className="lg-window" /> Event window
            </li>
          )}
          <li>
            <i className="lg-hatch" /> No data
          </li>
          <li className="muted">Bottom strip: quality of each sample</li>
        </ul>
      </section>
      {feedLevel ? <LastData session={session} /> : <Figures event={event} parameter={event.parameter!} session={session} />}
      <Sheet open={compare} title="Compare signals" onClose={() => setCompare(false)} wide>
        <p className="fineprint">Same time range, shared cursor: move over a chart (or use the arrow keys) to read every signal at the same instant.</p>
        <div className="compare">
          {[...main, ...others].map((p, i) => chart(p, i === 0 ? sheetPlots.main : sheetPlots.other, i === 0))}
        </div>
      </Sheet>
    </>
  )
}

function windowFacts(event: ReviewEvent, p: ParameterId, session: SessionData) {
  const series = session.series[p]
  if (!series) return null
  const { start, end } = event.window
  const inWindow = samplesInWindow(series.samples, start, end)
  const band = session.bands[p]
  return {
    series,
    inWindow,
    expected: expectedSampleCount(start, end, series.source.samplingIntervalS),
    q: countQuality(inWindow),
    stats: statsOf(goodValues(inWindow)),
    band,
    cmp: band ? compareWithBand(inWindow, band, session.sessionStart) : null,
  }
}

/** Four facts computed from the samples in the event window. No interpretation. */
function Figures({ event, parameter: p, session }: { event: ReviewEvent; parameter: ParameterId; session: SessionData }) {
  const f = windowFacts(event, p, session)
  if (!f) return null
  const { series, inWindow, expected, q, stats, cmp } = f
  const unit = PARAMETERS[p].unit
  return (
    <section className="figures" aria-label={`Observed ${formatClock(event.window.start, false)}–${formatClock(event.window.end, false)} UTC, computed from samples`}>
      <Figure label="Samples received" value={`${inWindow.length} of ${expected}`} note={`one every ${series.source.samplingIntervalS} s`} />
      <Figure
        label="Reliable samples"
        value={`${q.counts.good}`}
        note={`${q.counts.uncertain} uncertain · ${q.counts.poor} poor · ${q.counts.missing} missing`}
        attention={q.counts.good < inWindow.length / 2}
      />
      <Figure label="Median (reliable)" value={stats ? `${formatValue(p, stats.median)} ${unit}` : '—'} note={stats ? `range ${formatValue(p, stats.min)}–${formatValue(p, stats.max)}` : 'no reliable samples'} />
      <Figure
        label="Above usual range"
        value={cmp && cmp.compared ? `${cmp.above} of ${cmp.compared}` : '—'}
        note={cmp && cmp.compared ? `${cmp.below} below · personal history` : 'nothing comparable'}
        attention={!!cmp && cmp.compared > 0 && cmp.above > cmp.compared / 2}
      />
    </section>
  )
}

/** Context and provenance, behind a disclosure: available, never in the way. */
function Provenance({ event, parameter: p, session }: { event: ReviewEvent; parameter: ParameterId; session: SessionData }) {
  const f = windowFacts(event, p, session)
  if (!f) return null
  const { series, inWindow, band } = f
  const { start, end } = event.window
  const motion = session.series.motion
  const mWin = motion ? statsOf(goodValues(samplesInWindow(motion.samples, start, end))) : null
  const mBefore = motion ? statsOf(goodValues(samplesInWindow(motion.samples, toIso(toMs(start) - PAD_MS), toIso(toMs(start) - 1000)))) : null
  const gaps = PARAMETER_ORDER.flatMap((pp) => {
    const s = session.series[pp]
    return s ? findGaps(samplesInWindow(s.samples, start, end), s.source.samplingIntervalS).map((g) => ({ p: pp, g })) : []
  })
  const reasons = [...new Set(inWindow.flatMap((s) => s.reasons ?? []))]
  const activity = session.activities.filter((s) => toMs(s.end) > toMs(start) && toMs(s.start) < toMs(end))
  return (
    <details className="disclosure">
      <summary>Context and data provenance</summary>
      <dl className="kv">
        <div>
          <dt>Window</dt>
          <dd>
            {formatClock(start)}–{formatClock(end)} UTC
          </dd>
        </div>
        <div>
          <dt>Activity</dt>
          <dd>{activity.length ? activity.map((s) => `${s.label} (${s.scheduled ? 'planned' : 'inferred'})`).join('; ') : 'No scheduled activity'}</dd>
        </div>
        <div>
          <dt>Motion</dt>
          <dd>
            {mWin ? `median ${formatValue('motion', mWin.median)} g` : 'not available'}
            {mBefore ? `; ${formatValue('motion', mBefore.median)} g in the 5 min before` : ''}
          </dd>
        </div>
        {reasons.length > 0 && (
          <div>
            <dt>Quality flags</dt>
            <dd>{reasons.map((r) => REASON_LABEL[r]).join('; ')}</dd>
          </div>
        )}
        <div>
          <dt>Missing data</dt>
          <dd>
            {gaps.length
              ? gaps.map(({ p: pp, g }) => `${PARAMETERS[pp].shortLabel} ${formatClock(g.start)}${g.end !== g.start ? `–${formatClock(g.end)}` : ''} (${g.missingSamples})`).join('; ')
              : 'No gaps'}
          </dd>
        </div>
        <div>
          <dt>Device</dt>
          <dd>
            {series.source.deviceLabel} · {series.source.sensorType} · {series.source.placement}
          </dd>
        </div>
        <div>
          <dt>Processing</dt>
          <dd>{series.source.processing}</dd>
        </div>
        <div>
          <dt>Quality method</dt>
          <dd>{series.source.qualityMethod}</dd>
        </div>
        {band && (
          <div>
            <dt>Usual range</dt>
            <dd>{band.basis}</dd>
          </div>
        )}
      </dl>
    </details>
  )
}

/** Feed-level event: when each signal was last received. */
function LastData({ session }: { session: SessionData }) {
  return (
    <section className="figures" aria-label="Last data received per signal">
      {PARAMETER_ORDER.map((p) => {
        const s = session.series[p]?.samples ?? []
        const last = s[s.length - 1]
        return (
          <Figure
            key={p}
            label={`${PARAMETERS[p].shortLabel} last received`}
            value={last ? formatClock(last.t) : '—'}
            note={last ? `${formatDuration(toMs(session.mission.now) - toMs(last.t))} ago · UTC` : 'no sample'}
            attention={!!last}
          />
        )
      })}
    </section>
  )
}

function Figure({ label, value, note, attention }: { label: string; value: string; note: string; attention?: boolean }) {
  return (
    <div className={`figure${attention ? ' is-attention' : ''}`}>
      <span className="figure-label">{label}</span>
      <span className="figure-value">{value}</span>
      <span className="figure-note">{note}</span>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Evidence from a report shared by the crew member                    */
/* ------------------------------------------------------------------ */

function ReportTrends({ crewName, mission, daily }: { crewName: string; mission: MissionStatus; daily: DailyIndicatorSeries[] }) {
  const today = missionDayOf(mission.now, mission.missionStartDate)
  const evals = daily.filter((s) => s.indicator !== 'bp_diastolic').map((s) => evaluateIndicator(s, today, 'their'))
  const isChanged = (e: (typeof evals)[number]) => e.position !== null && e.position !== 'within' && e.streakDays >= 3
  const sorted = [...evals].sort((x, y) => Number(isChanged(y)) - Number(isChanged(x)))
  return (
    <section className="card list-card" aria-labelledby="trends-h">
      <h2 className="card-title" id="trends-h">
        Shared daily trends <span className="muted">· against {crewName}’s own usual range</span>
      </h2>
      <ul className="trend-grid">
        {sorted.map((e) => {
          const id = e.series.indicator
          const attention = isChanged(e) || e.repeatSuggested
          return (
            <li key={id} className={`trend-cell tone-${toneOf(id)}`}>
              <span className="trend-cell-label" title={DAILY_INDICATORS[id].label}>
                <MetricGlyph id={id} size={13} /> {DAILY_INDICATORS[id].label}
              </span>
              <span className="trend-cell-value">
                {e.latest ? formatDailyValue(id, e.latest.value) : '—'} <span className="unit">{DAILY_INDICATORS[id].unit}</span>
              </span>
              <Sparkline series={e.series} width={56} height={22} />
              <span className={`trend-cell-status${attention ? ' text-attention' : ''}`}>{e.headline}</span>
            </li>
          )
        })}
      </ul>
    </section>
  )
}

function ReportCheckIns({ checkIns }: { checkIns: CheckIn[] }) {
  return (
    <section aria-labelledby="checkins-h">
      <h2 className="side-title" id="checkins-h">
        Latest check-in
      </h2>
      {checkIns.length ? (
        <dl className="kv kv-compact kv-checkins">
          {checkIns.slice(0, 1).map((c) => (
            <div key={c.id}>
              <dt>Day {c.missionDay}</dt>
              <dd>{describeCheckIn(c)}</dd>
            </div>
          ))}
        </dl>
      ) : (
        <p className="list-empty">No check-ins shared.</p>
      )}
    </section>
  )
}

/* ------------------------------------------------------------------ */
/* Review: status, interpretation notes, message to the crew           */
/* ------------------------------------------------------------------ */

const updateStatus = (ds: DataSource, id: string, status: EventStatus) => ds.updateEventStatus(id, status)
const addNote = (ds: DataSource, id: string, text: string) => ds.addAnnotation(id, text)
const sendMessage = (ds: DataSource, crewId: string, templateId: string, eventId: string) => ds.sendCrewMessage(crewId, templateId, eventId)

/** Short menu labels; the full, predefined text is what the crew receives. */
const TEMPLATE_SHORT: Record<string, string> = {
  ack_no_action: 'Received — no action needed',
  review_after: 'Will review after the session',
  check_sensor_after: 'Check sensor after the activity',
  contact_planned: 'Will contact at next window',
}

function ReviewCard({ event, crewName, offline, sent }: { event: ReviewEvent; crewName: string; offline: boolean; sent: CrewMessage[] }) {
  const [pending, setPending] = useState<{ status: EventStatus; basedOn: EventStatus } | null>(null)
  const status = useMutation(updateStatus)
  const note = useMutation(addNote)
  const message = useMutation(sendMessage)
  const [text, setText] = useState('')
  const [templateId, setTemplateId] = useState(CREW_MESSAGE_TEMPLATES[0].id)
  const current = pending && pending.basedOn === event.status ? pending.status : event.status

  const choose = async (s: EventStatus) => {
    setPending({ status: s, basedOn: event.status })
    if (!(await status.run(event.id, s))) setPending(null)
  }
  const saveNote = async (e: FormEvent) => {
    e.preventDefault()
    if (await note.run(event.id, text)) setText('')
  }
  const send = (e: FormEvent) => {
    e.preventDefault()
    void message.run(event.crewId, templateId, event.id)
  }

  return (
    <section className="card review" aria-labelledby="review-h">
      <div className="review-head">
        <h2 id="review-h">Your review</h2>
        <Segmented size="small" label="Review status" value={current} onChange={choose} options={EVENT_STATUSES.map((s) => ({ value: s, label: EVENT_STATUS_LABEL[s] }))} />
      </div>
      <FormError message={status.error} />

      {event.annotations.length > 0 && (
        <ol className="notes">
          {event.annotations.map((a) => (
            <li key={a.id}>
              <span className="note-meta">
                {a.authorLabel} · {formatUtc(a.createdAt, false)}
              </span>
              <p>{a.text}</p>
            </li>
          ))}
        </ol>
      )}
      <form onSubmit={saveNote} className="inline-form note-form">
        <label className="sr-only" htmlFor={`note-${event.id}`}>
          Interpretation note
        </label>
        <textarea
          id={`note-${event.id}`}
          className="note-input"
          rows={2}
          maxLength={2000}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Your interpretation: checks done, procedures consulted…"
        />
        <button type="submit" className="btn" disabled={note.busy || !text.trim()}>
          {note.busy ? 'Saving…' : 'Add note'}
        </button>
      </form>
      <FormError message={note.error} />

      <form onSubmit={send} className="message-form">
        <label htmlFor={`tpl-${event.id}`} className="field-label">
          Message to {crewName} <span className="muted">· predefined, never urgent</span>
        </label>
        <div className="inline-form">
          <select id={`tpl-${event.id}`} value={templateId} onChange={(e) => setTemplateId(e.target.value)} disabled={offline}>
            {CREW_MESSAGE_TEMPLATES.map((t) => (
              <option key={t.id} value={t.id} title={t.text}>
                {TEMPLATE_SHORT[t.id] ?? t.text}
              </option>
            ))}
          </select>
          <button type="submit" className="btn" disabled={offline || message.busy}>
            {message.busy ? 'Sending…' : 'Send'}
          </button>
        </div>
        <p className="fineprint template-preview">“{CREW_MESSAGE_TEMPLATES.find((t) => t.id === templateId)?.text}”</p>
        {offline && <p className="fineprint">No ground link: messages cannot be sent right now.</p>}
        <FormError message={message.error} />
        {sent.length > 0 && (
          <ul className="sent">
            {sent.map((m) => (
              <li key={m.id}>
                <span className="muted">Sent {formatClock(m.createdAt, false)} UTC</span> — {m.text}
              </li>
            ))}
          </ul>
        )}
      </form>
      <p className="fineprint review-note">Notes are written by people, separate from the observed data. No automatic diagnosis.</p>
    </section>
  )
}
