import { useState, type FormEvent } from 'react'
import type { DataSource } from '../../data'
import type { CheckIn, CheckInInput, CheckInScore, DailyIndicatorId, MissionStatus } from '../../domain/types'
import { CHECK_IN_QUESTIONS, DAILY_INDICATORS, QUALITY_LABEL, formatDailyValue } from '../../domain/parameters'
import type { IndicatorEvaluation } from '../../domain/crewHealth'
import { MEASUREMENT_DEVICES, MEASUREMENT_GROUPS, NOT_TRACKED_EXAMS, type DeviceMeasurement } from '../../domain/measurements'
import { formatUtc } from '../../domain/time'
import { useMutation } from '../../hooks/useMutation'
import { useAppState } from '../../state/AppState'
import { DailyTrendChart } from '../../components/DailyTrendChart'
import { MetricGlyph } from '../../components/MetricGlyph'
import { toneOf } from '../../components/tone'
import { FormError } from '../../components/Common'
import { List, Row, Sheet, Symbol } from '../../components/ui'
import { INDICATOR_CONTEXT } from './indicatorText'
import { useToast } from '../../components/Toast'
import type { useShare } from './shareSync'

/* ------------------------------------------------------------------ */
/* Indicator detail                                                    */
/* ------------------------------------------------------------------ */

export function IndicatorSheet({
  evaluation,
  paired,
  today,
  onClose,
  onMeasure,
  onShare,
}: {
  evaluation: IndicatorEvaluation | null
  paired?: IndicatorEvaluation
  today: number
  onClose: () => void
  onMeasure: (id: DailyIndicatorId) => void
  onShare: () => void
}) {
  const e = evaluation
  const id = e?.series.indicator
  const def = id ? DAILY_INDICATORS[id] : null
  const changed = !!e && e.position !== null && e.position !== 'within' && e.streakDays >= 3
  const canMeasure = !!id && MEASUREMENT_DEVICES.some((d) => d.indicator === id)
  return (
    <Sheet open={!!e} title={def?.label ?? ''} onClose={onClose} wide>
      {e && id && def && (
        <>
          <div className="detail-hero">
            <span className={`detail-category tone-${toneOf(id)}`}>
              <MetricGlyph id={id} size={16} /> {def.when}
            </span>
            <p className="detail-value">
              {e.latest ? formatDailyValue(id, e.latest.value) : '—'}
              {paired?.latest && <>/{formatDailyValue(paired.series.indicator, paired.latest.value)}</>}
              <span className="unit"> {def.unit}</span>
            </p>
            <p className={`detail-status${changed || e.repeatSuggested ? ' is-attention' : ''}`}>{statusText(e)}</p>
            <p className="detail-meta">
              {e.latest ? `Day ${e.latest.missionDay}${e.latest.missionDay === today ? ' (today)' : ''} · quality ${QUALITY_LABEL[e.latest.quality].toLowerCase()}` : 'No reliable reading yet'}
            </p>
          </div>
          <DailyTrendChart series={e.series} height={Math.max(120, Math.min(190, Math.round(window.innerHeight * 0.86 - 460)))} />
          <p className="body-text">{INDICATOR_CONTEXT[id]}</p>
          <dl className="kv">
            <div>
              <dt>Usual range</dt>
              <dd>
                {e.series.baseline
                  ? `${formatDailyValue(id, e.series.baseline.low)}–${formatDailyValue(id, e.series.baseline.high)} ${def.unit} · days ${e.series.baseline.fromDay}–${e.series.baseline.toDay}`
                  : 'Not available yet'}
              </dd>
            </div>
            <div>
              <dt>Source</dt>
              <dd>{e.series.source}</dd>
            </div>
          </dl>
          <p className="fineprint">Compared with your own first mission days, not with medical thresholds.</p>
          {(canMeasure || changed) && (
            <div className="button-row">
              {canMeasure && (
                <button type="button" className={e.repeatSuggested ? 'btn btn-primary' : 'btn'} onClick={() => onMeasure(id)}>
                  Take a measurement
                </button>
              )}
              {changed && (
                <button type="button" className={e.repeatSuggested ? 'btn' : 'btn btn-primary'} onClick={onShare}>
                  Share with medical team
                </button>
              )}
            </div>
          )}
        </>
      )}
    </Sheet>
  )
}

export function statusText(e: IndicatorEvaluation): string {
  if (e.repeatSuggested) return 'Today’s reading is missing or uncertain'
  if (!e.latest) return 'No readings yet'
  if (e.position === null) return 'Usual range not available yet'
  if (e.position === 'within') return 'Within your usual range'
  const side = e.position === 'above' ? 'Higher' : 'Lower'
  return e.streakDays > 1 ? `${side} than usual for ${e.streakDays} days` : `${side} than usual today`
}

/* ------------------------------------------------------------------ */
/* Daily check-in                                                      */
/* ------------------------------------------------------------------ */

const submitCheckIn = (ds: DataSource, crewId: string, input: CheckInInput) => ds.submitCheckIn(crewId, input)

export function CheckInSheet({ open, crewId, existing, onClose }: { open: boolean; crewId: string; existing: CheckIn | undefined; onClose: () => void }) {
  return (
    <Sheet open={open} title="Daily check-in" onClose={onClose}>
      {open && <CheckInForm crewId={crewId} existing={existing} onDone={onClose} />}
    </Sheet>
  )
}

function CheckInForm({ crewId, existing, onDone }: { crewId: string; existing: CheckIn | undefined; onDone: () => void }) {
  const [answers, setAnswers] = useState<Partial<Record<'sleepQuality' | 'energy' | 'mood', CheckInScore>>>(() =>
    existing ? { sleepQuality: existing.sleepQuality, energy: existing.energy, mood: existing.mood } : {},
  )
  const [note, setNote] = useState(existing?.note ?? '')
  const save = useMutation(submitCheckIn)
  const toast = useToast()
  const complete = CHECK_IN_QUESTIONS.every((q) => answers[q.id])

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (!complete) return
    const ok = await save.run(crewId, {
      sleepQuality: answers.sleepQuality!,
      energy: answers.energy!,
      mood: answers.mood!,
      note: note.trim().slice(0, 280),
    })
    if (ok) {
      toast(existing ? 'Check-in updated' : 'Check-in saved')
      onDone()
    }
  }

  return (
    <form onSubmit={submit} className="stack">
      <p className="body-text muted">Three quick questions. Your answers help you and the medical team notice changes over time.</p>
      {CHECK_IN_QUESTIONS.map((q) => (
        <fieldset key={q.id} className="scale">
          <legend>{q.label}</legend>
          <div className="scale-options">
            {q.scale.map((word, i) => {
              const score = (i + 1) as CheckInScore
              return (
                <label key={word} className={answers[q.id] === score ? 'is-selected' : undefined}>
                  <input type="radio" name={q.id} value={score} checked={answers[q.id] === score} onChange={() => setAnswers((a) => ({ ...a, [q.id]: score }))} />
                  <span>{word}</span>
                </label>
              )
            })}
          </div>
        </fieldset>
      ))}
      <label className="field">
        <span className="field-label">
          Note <span className="muted">(optional)</span>
        </span>
        <textarea rows={2} maxLength={280} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Anything you want to remember about today" />
      </label>
      <FormError message={save.error} />
      <button type="submit" className="btn btn-primary btn-block" disabled={!complete || save.busy}>
        {save.busy ? 'Saving…' : existing ? 'Update check-in' : 'Save check-in'}
      </button>
    </form>
  )
}

/* ------------------------------------------------------------------ */
/* Measurement (simulated acquisition)                                 */
/* ------------------------------------------------------------------ */

type Step = 'choose' | 'prepare' | 'result'

export function MeasureSheet({
  open,
  crewId,
  mission,
  initial,
  onClose,
}: {
  open: boolean
  crewId: string
  mission: MissionStatus
  initial: DailyIndicatorId | null
  onClose: () => void
}) {
  const startsWithDevice = !!initial && MEASUREMENT_DEVICES.some((d) => d.indicator === initial)
  return (
    <Sheet open={open} title="Take a measurement" onClose={onClose}>
      {open && <MeasureFlow key={initial ?? 'none'} crewId={crewId} mission={mission} initial={startsWithDevice ? initial : null} onDone={onClose} />}
    </Sheet>
  )
}

function MeasureFlow({ crewId, mission, initial, onDone }: { crewId: string; mission: MissionStatus; initial: DailyIndicatorId | null; onDone: () => void }) {
  const { notifyChanged } = useAppState()
  const toast = useToast()
  const [step, setStep] = useState<Step>(initial ? 'prepare' : 'choose')
  const [selected, setSelected] = useState<DailyIndicatorId>(initial ?? 'resting_spo2')
  const [context, setContext] = useState('Routine morning check')
  const [typed, setTyped] = useState<Record<string, string>>({})
  const [results, setResults] = useState<DeviceMeasurement[]>([])
  const save = useMutation((ds: DataSource, items: DeviceMeasurement[]) => ds.recordMeasurements(crewId, items))
  const device = MEASUREMENT_DEVICES.find((d) => d.indicator === selected)!
  const ids = [device.indicator, ...(device.also ?? [])]
  // No instrument is connected to the browser: readings are typed from the instrument's display.

  const reading = (indicator: DailyIndicatorId, value: number, manual: boolean, n: number, at: number): DeviceMeasurement => ({
    id: `MEAS-${crewId}-${at}-${n}-${Math.random().toString(36).slice(2, 6)}`,
    crewId,
    indicator,
    value,
    quality: 'good',
    simulated: true,
    deviceLabel: device.kind,
    acquiredAt: mission.now,
    savedAtMs: at,
    signal: 'clear',
    context,
    manual,
  })
  const parsed = ids.map((id) => {
    const raw = (typed[id] ?? '').replace(',', '.').trim()
    const v = raw === '' ? null : Number(raw)
    return { id, v: v !== null && Number.isFinite(v) && v >= 0 ? v : null, raw }
  })
  const manualError = parsed.find((p) => p.raw !== '' && p.v === null)
  const manualReady = parsed[0].v !== null && !manualError
  const useTyped = () => {
    const at = Date.now()
    setResults(parsed.filter((p) => p.v !== null).map((p, n) => reading(p.id, p.v as number, true, n, at)))
    setStep('result')
  }

  const confirm = async () => {
    if (!results.length) return
    const ok = await save.run(results)
    if (!ok) return
    notifyChanged()
    toast(`${device.name} saved`)
    onDone()
  }

  if (step === 'choose') {
    return (
      <div className="stack">
        <p className="body-text muted">
          Every measurement taken on board. Choose the instrument, follow its steps and type the value it shows.
        </p>
        {MEASUREMENT_GROUPS.map((g) => (
          <section key={g} className="measure-group" aria-label={g}>
            <p className="list-label">{g}</p>
            <List label={g}>
              {MEASUREMENT_DEVICES.filter((d) => d.group === g).map((d) => (
                <Row
                  key={d.indicator}
                  leading={
                    <Symbol tone={toneOf(d.indicator)}>
                      <MetricGlyph id={d.indicator} size={16} />
                    </Symbol>
                  }
                  title={d.name}
                  subtitle={`${d.kind} · ${d.expected}`}
                  onClick={() => {
                    setSelected(d.indicator)
                    setTyped({})
                    setStep('prepare')
                  }}
                />
              ))}
            </List>
          </section>
        ))}
        <p className="fineprint">Periodic examinations with the medical team ({NOT_TRACKED_EXAMS.join(', ')}) are not tracked in OrbitVitals yet.</p>
      </div>
    )
  }

  if (step === 'prepare') {
    return (
      <div className="stack">
        <button type="button" className="text-button back" onClick={() => setStep('choose')}>
          ‹ All measurements
        </button>
        <div className="detail-hero compact">
          <span className={`detail-category tone-${toneOf(selected)}`}>
            <MetricGlyph id={selected} size={16} /> {device.kind}
          </span>
          <p className="detail-title">{device.name}</p>
        </div>
        <ol className="steps">
          {device.preparation.map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
        <div className="manual-grid">
          {ids.map((id) => (
            <label key={id} className="field">
              <span className="field-label">
                {DAILY_INDICATORS[id].label} ({DAILY_INDICATORS[id].unit})
              </span>
              <input
                inputMode="decimal"
                value={typed[id] ?? ''}
                placeholder={id === device.indicator ? 'Required' : 'Optional'}
                onChange={(e) => setTyped((t) => ({ ...t, [id]: e.target.value }))}
              />
            </label>
          ))}
          {manualError && <p className="form-error">“{manualError.raw}” is not a number.</p>}
        </div>
        <label className="field">
          <span className="field-label">Context</span>
          <select value={context} onChange={(e) => setContext(e.target.value)}>
            <option>Routine morning check</option>
            <option>Before scheduled exercise</option>
            <option>After scheduled exercise</option>
            <option>Additional measurement requested</option>
          </select>
        </label>
        <button type="button" className="btn btn-primary btn-block" disabled={!manualReady} onClick={useTyped}>
          Review
        </button>
        <p className="fineprint">Nothing is saved until you confirm.</p>
      </div>
    )
  }

  const main = results[0]
  return (
    main && (
      <div className="stack">
        <div className="detail-hero">
          <span className={`detail-category tone-${toneOf(selected)}`}>
            <MetricGlyph id={selected} size={16} /> {device.name}
          </span>
          <div className="result-values">
            {selected === 'bp_systolic' && results.length === 2 ? (
              <p className="detail-value">
                {formatDailyValue('bp_systolic', results[0].value)}/{formatDailyValue('bp_diastolic', results[1].value)}
                <span className="unit"> mmHg</span>
              </p>
            ) : results.map((r) => (
              <p key={r.indicator} className="detail-value">
                {formatDailyValue(r.indicator, r.value)}
                <span className="unit"> {DAILY_INDICATORS[r.indicator].unit}</span>
                {results.length > 1 && <span className="result-label">{DAILY_INDICATORS[r.indicator].label}</span>}
              </p>
            ))}
          </div>
          <p className={`detail-status${main.quality === 'good' ? '' : ' is-attention'}`}>
            {main.manual ? 'Entered from the instrument' : main.quality === 'good' ? 'Signal not flagged' : 'Signal uncertain — consider repeating'}
          </p>
          <p className="detail-meta">
            {formatUtc(main.acquiredAt, false)} · {main.context}

          </p>
        </div>
        <FormError message={save.error} />
        <div className="button-row">
          <button type="button" className="btn" onClick={() => setStep('prepare')}>
            {main.manual ? 'Edit' : 'Repeat'}
          </button>
          <button type="button" className="btn btn-primary" disabled={save.busy} onClick={() => void confirm()}>
            Save
          </button>
        </div>
      </div>
    )
  )
}

/* ------------------------------------------------------------------ */
/* Share with the medical team                                         */
/* ------------------------------------------------------------------ */

export function ShareSheet({ open, onClose, sharing, summary }: { open: boolean; onClose: () => void; sharing: ReturnType<typeof useShare>; summary: string }) {
  const [note, setNote] = useState('')
  const [done, setDone] = useState<'sent' | 'queued' | null>(null)
  const close = () => {
    setDone(null)
    onClose()
  }
  const submit = async (e: FormEvent) => {
    e.preventDefault()
    const r = await sharing.share(note.trim().slice(0, 500))
    if (r !== 'failed') {
      setNote('')
      setDone(r)
    }
  }
  return (
    <Sheet open={open} title="Share with medical team" onClose={close}>
      {done ? (
        <div className="stack center">
          <span className="done-mark" aria-hidden="true">
            ✓
          </span>
          <p className="detail-title">{done === 'sent' ? 'Shared' : 'Saved for later'}</p>
          <p className="body-text muted">{sharing.notice}</p>
          <button type="button" className="btn btn-primary btn-block" onClick={close}>
            Done
          </button>
        </div>
      ) : (
        <form className="stack" onSubmit={submit}>
          <p className="body-text">
            The team will see your daily trends and check-ins{summary ? ` — including ${summary}` : ''}. Sharing is your choice.
          </p>
          {sharing.offline && (
            <p className="notice notice-link">
              {sharing.canQueue ? 'No ground link right now. Your report will be saved on this device and sent when the link returns.' : 'No ground link: offline queuing is not available with this backend.'}
            </p>
          )}
          <label className="field">
            <span className="field-label">
              Note for the team <span className="muted">(optional)</span>
            </span>
            <textarea rows={3} maxLength={500} value={note} onChange={(e) => setNote(e.target.value)} placeholder="e.g. I woke up several times during the night" />
          </label>
          <FormError message={sharing.error} />
          <button type="submit" className="btn btn-primary btn-block" disabled={sharing.busy || (sharing.offline && !sharing.canQueue)}>
            {sharing.busy ? 'Sharing…' : sharing.offline ? 'Save and send later' : 'Share'}
          </button>
        </form>
      )}
    </Sheet>
  )
}
