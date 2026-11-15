import { useMemo, useState, type FormEvent } from 'react'
import type { DataSource } from '../../data'
import type { MissionStatus } from '../../domain/types'
import {
  CATALOG_NOTE,
  NASA_SOURCE,
  NUTRIENT,
  NUTRIENTS,
  formatNutrient,
  progressOf,
  summarize,
  totalsOf,
  type Food,
  type IntakeEntry,
  type NutrientId,
  type NutrientProgress,
  type NutritionProfile,
} from '../../domain/nutrition'
import { formatClock } from '../../domain/time'
import { href } from '../../hooks/useRoute'
import { useMutation } from '../../hooks/useMutation'
import { useAppState } from '../../state/AppState'
import { Ring } from '../../components/Ring'
import { FormError } from '../../components/Common'
import { useToast } from '../../components/Toast'
import { Segmented, Sheet } from '../../components/ui'

export interface NutritionData {
  profile: NutritionProfile
  /** The last 8 UTC days, today included, oldest first. */
  intake: IntakeEntry[]
  foods: Food[]
}

export async function loadNutrition(ds: DataSource, crewId: string, nowIso: string): Promise<NutritionData> {
  const today = nowIso.slice(0, 10)
  const from = new Date(Date.parse(`${today}T00:00:00Z`) - 7 * 86_400_000).toISOString()
  const to = new Date(Date.parse(`${today}T00:00:00Z`) + 86_400_000).toISOString()
  const [profile, intake, foods] = await Promise.all([ds.getNutritionProfile(crewId), ds.listIntake(crewId, from, to), ds.listFoods()])
  return { profile, intake, foods }
}

const dayOf = (iso: string) => iso.slice(0, 10)
const todayEntries = (d: NutritionData, nowIso: string) => d.intake.filter((e) => dayOf(e.eatenAt) === dayOf(nowIso))

/** Percent label that never claims more precision than the data. */
const pct = (f: number) => `${Math.round(Math.min(f, 9.99) * 100)}%`

/* ------------------------------------------------------------------ */
/* Home slot                                                           */
/* ------------------------------------------------------------------ */

/**
 * The nutrition slot on Today. It stands out on purpose: NASA requires the
 * full daily requirement to be met, so the ring shows what is still missing.
 */
export function NutritionCard({ data, mission, crewId, onLogFood }: { data: NutritionData; mission: MissionStatus; crewId: string; onLogFood: () => void }) {
  const s = summarize(totalsOf(todayEntries(data, mission.now), data.foods), data.profile, true)
  const addWater = useAddWater(crewId, mission)
  const missing = s.micros.filter((m) => m.state === 'below' || m.state === 'unknown').map((m) => m.def.label)
  return (
    <section className="card nutrition-card" aria-labelledby="nutrition-h">
      <div className="nutrition-head">
        <a className="nutrition-title" href={href.crew(crewId, 'nutrition')}>
          <span className="nutrition-icon" aria-hidden="true">
            <svg width="16" height="16" viewBox="0 0 24 24">
              <path d="M12 2.5c3.6 4.3 6 7.7 6 11a6 6 0 0 1-12 0c0-3.3 2.4-6.7 6-11Z" fill="currentColor" />
            </svg>
          </span>
          <span>
            <span className="eyebrow">Nutrition · today</span>
            <h2 id="nutrition-h">Reach 100% of every daily need</h2>
          </span>
        </a>
        <div className="nutrition-actions">
          <button type="button" className="btn btn-small btn-water" disabled={addWater.busy} onClick={() => void addWater.add(250)} aria-label="Add 250 mL of water">
            + 250 mL
          </button>
          <button type="button" className="btn btn-small btn-water" disabled={addWater.busy} onClick={() => void addWater.add(500)} aria-label="Add 500 mL of water">
            + 500 mL
          </button>
          <button type="button" className="btn btn-primary btn-small" onClick={onLogFood}>
            Log food
          </button>
        </div>
      </div>
      <div className="nutrition-body">
        <a className="nutrition-rings" href={href.crew(crewId, 'nutrition')} aria-label="Open nutrition: vitamins, minerals and log">
          <RingStat p={s.water} tone="water" title="Water" />
          <RingStat p={s.energy} tone="energy" title="Energy" />
          <span className="ring-stat">
            <Ring size={56} fill={s.microsFill} tone="micro" label={`Micronutrients: ${s.microsOnTarget} of ${s.micros.length} on target`} over={s.over.some((o) => o.def.group !== 'essentials')}>
              <span className="ring-num">
                {s.microsOnTarget}
                <small>/{s.micros.length}</small>
              </span>
            </Ring>
            <span className="ring-caption">
              <strong>Vitamins & minerals</strong>
              <span>on target</span>
            </span>
          </span>
        </a>
        <p className={`nutrition-note${s.over.length ? ' is-attention' : ''}`}>
          {s.over.length ? (
            <>
              <strong>Above the limit:</strong> {s.over.map((o) => o.def.label).join(', ')}.{' '}
            </>
          ) : null}
          {missing.length ? (
            <>
              <span className="note-label">Still to reach</span> {missing.slice(0, 3).join(', ')}
              {missing.length > 3 ? ` and ${missing.length - 3} more` : ''}
            </>
          ) : (
            'Every vitamin and mineral is on target.'
          )}
          <a className="text-button note-link" href={href.crew(crewId, 'nutrition')}>
            See all
          </a>
        </p>
      </div>
    </section>
  )
}

function RingStat({ p, tone, title }: { p: NutrientProgress; tone: 'water' | 'energy'; title: string }) {
  const target = p.req.min ?? 0
  return (
    <span className="ring-stat">
      <Ring size={56} fill={p.fill} tone={tone} label={`${title}: ${formatNutrient(p.def.id, p.value)} of ${formatNutrient(p.def.id, target)}`}>
        <span className="ring-num">{pct(target ? p.value / target : 0)}</span>
      </Ring>
      <span className="ring-caption">
        <strong>{title}</strong>
        <span>
          {formatNutrient(p.def.id, p.value)} / {formatNutrient(p.def.id, target)}
        </span>
      </span>
    </span>
  )
}

function useAddWater(crewId: string, mission: MissionStatus) {
  const { notifyChanged } = useAppState()
  const toast = useToast()
  const m = useMutation((ds: DataSource, entry: IntakeEntry) => ds.addIntake(entry))
  return {
    busy: m.busy,
    add: async (ml: number) => {
      const ok = await m.run(newEntry(crewId, mission, { values: { fluid_intake: ml }, label: 'Water' }))
      if (ok) {
        notifyChanged()
        toast(`${ml} mL of water logged`)
      } else toast(m.error ?? 'Not saved')
    },
  }
}

function newEntry(crewId: string, mission: MissionStatus, part: Partial<IntakeEntry>): IntakeEntry {
  return {
    id: `intake-${crewId}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`,
    crewId,
    eatenAt: mission.now,
    foodId: null,
    servings: 1,
    values: {},
    label: 'Entry',
    ...part,
  }
}

/* ------------------------------------------------------------------ */
/* Nutrition page                                                      */
/* ------------------------------------------------------------------ */

type View = 'today' | 'week'
type NutritionSheet = 'food' | 'values' | 'create' | null

export function NutritionPage({ data, mission, crewId, sheet, setSheet }: { data: NutritionData; mission: MissionStatus; crewId: string; sheet: NutritionSheet; setSheet: (s: NutritionSheet) => void }) {
  const [view, setView] = useState<View>('today')
  const [editing, setEditing] = useState(false)
  const addWater = useAddWater(crewId, mission)
  const today = todayEntries(data, mission.now)
  const totals = useMemo(() => {
    if (view === 'today') return totalsOf(today, data.foods)
    // 7-day mean of the complete days before today, as the backend evaluation does.
    const days = [...new Set(data.intake.map((e) => dayOf(e.eatenAt)))].filter((d) => d < dayOf(mission.now))
    const sum = totalsOf(data.intake.filter((e) => days.includes(dayOf(e.eatenAt))), data.foods)
    const n = Math.max(1, days.length)
    for (const k of Object.keys(sum.totals) as NutrientId[]) sum.totals[k] /= n
    return sum
  }, [view, today, data, mission.now])
  const progress = NUTRIENTS.map((d) => progressOf(d.id, totals, data.profile, view === 'today'))
  const group = (g: string) => progress.filter((p) => p.def.group === g)

  return (
    <div className="nutrition-page">
      <section className="card nutrition-main" aria-label="Daily requirements">
        <div className="nutrition-main-head">
          <Segmented
            label="Period"
            value={view}
            onChange={setView}
            options={[
              { value: 'today', label: 'Today so far' },
              { value: 'week', label: 'Average, last 7 days' },
            ]}
          />
          <p className={`fineprint profile-line${data.profile.source.startsWith('Profile not set') ? ' is-unset' : ''}`}>
            Targets for {data.profile.sex === 'male' ? 'a man' : 'a woman'}, {data.profile.ageYears} y, {data.profile.heightM.toFixed(2)} m, {data.profile.bodyMassKg.toFixed(1)} kg · {data.profile.source}{' '}
            <button type="button" className="text-button" onClick={() => setEditing(true)}>
              {data.profile.source.startsWith('Profile not set') ? 'Set your profile' : 'Edit'}
            </button>
          </p>
        </div>
        <div className="essentials">
          {group('essentials').map((p) => (
            <NutrientBar key={p.def.id} p={p} big />
          ))}
        </div>
        <div className="micro-columns">
          <div>
            <p className="list-label">Vitamins</p>
            {group('vitamins').map((p) => (
              <NutrientBar key={p.def.id} p={p} />
            ))}
          </div>
          <div>
            <p className="list-label">Minerals</p>
            {group('minerals').map((p) => (
              <NutrientBar key={p.def.id} p={p} />
            ))}
          </div>
        </div>
        <p className="fineprint nutrition-source">
          Requirements: {NASA_SOURCE} — the same rules as the backend nutrition module. A planning aid, not medical advice.
        </p>
      </section>

      <aside className="nutrition-side" aria-label="Log">
        <section className="card">
          <p className="eyebrow">Log</p>
          <div className="log-actions">
            <button type="button" className="btn btn-primary" onClick={() => setSheet('food')}>
              Log food
            </button>
            <button type="button" className="btn" onClick={() => setSheet('values')}>
              Enter values
            </button>
            <button type="button" className="btn btn-water" disabled={addWater.busy} onClick={() => void addWater.add(250)}>
              + 250 mL water
            </button>
            <button type="button" className="btn" onClick={() => setSheet('create')}>
              Create a food
            </button>
          </div>
        </section>
        <IntakeLog entries={today} foods={data.foods} crewId={crewId} />
      </aside>

      <FoodSheet open={sheet === 'food'} foods={data.foods} crewId={crewId} mission={mission} onClose={() => setSheet(null)} onCreate={() => setSheet('create')} />
      <ValuesSheet open={sheet === 'values'} crewId={crewId} mission={mission} onClose={() => setSheet(null)} />
      <CreateFoodSheet open={sheet === 'create'} onClose={() => setSheet('food')} />
      <ProfileSheet open={editing} profile={data.profile} crewId={crewId} onClose={() => setEditing(false)} />
    </div>
  )
}

function stateText(p: NutrientProgress): string {
  const unit = (v: number) => formatNutrient(p.def.id, v)
  switch (p.state) {
    case 'reached':
      return p.req.max !== null ? `In range (max ${unit(p.req.max)})` : 'Target reached'
    case 'below':
      return `${unit(p.remaining)} to go`
    case 'over':
      return `Above the limit of ${unit(p.req.max ?? 0)}`
    case 'within_limit':
      return `Under the limit of ${unit(p.req.max ?? 0)}`
    case 'unknown':
      return 'Some foods have no value: total not known'
  }
}

function NutrientBar({ p, big = false }: { p: NutrientProgress; big?: boolean }) {
  const target = p.req.min ?? p.req.max ?? 0
  const limitOnly = p.req.min === null
  return (
    <div className={`nutrient${big ? ' nutrient-big' : ''} is-${p.state}`} title={p.req.note || undefined}>
      <div className="nutrient-top">
        <span className="nutrient-name">{p.def.label}</span>
        <span className="nutrient-value">
          {formatNutrient(p.def.id, p.value)}
          <span className="muted">
            {' '}
            / {limitOnly ? 'max ' : ''}
            {formatNutrient(p.def.id, target)}
          </span>
        </span>
      </div>
      <div className={`bar${limitOnly ? ' bar-limit' : ''}`} aria-hidden="true">
        <span style={{ width: `${Math.min(100, p.fill * 100)}%` }} />
      </div>
      <span className="nutrient-state">{stateText(p)}</span>
    </div>
  )
}

function IntakeLog({ entries, foods, crewId }: { entries: IntakeEntry[]; foods: Food[]; crewId: string }) {
  const { notifyChanged } = useAppState()
  const toast = useToast()
  const remove = useMutation((ds: DataSource, id: string) => ds.removeIntake(crewId, id))
  const sorted = [...entries].reverse()
  return (
    <section className="card intake-log" aria-labelledby="log-h">
      <h2 id="log-h" className="side-title">
        Today’s log <span className="muted">· {entries.length}</span>
      </h2>
      {sorted.length ? (
        <ul className="intake-list">
          {sorted.map((e) => {
            const t = totalsOf([e], foods).totals
            const food = e.foodId ? foods.find((f) => f.id === e.foodId) : null
            return (
              <li key={e.id}>
                <span className="intake-time">{formatClock(e.eatenAt, false)}</span>
                <span className="intake-label">
                  {food ? food.name : e.label}
                  {e.servings !== 1 ? ` × ${e.servings}` : ''}
                  <small>{t.energy_intake > 0 ? `${Math.round(t.energy_intake)} kcal` : ''}{t.fluid_intake > 0 ? `${t.energy_intake > 0 ? ' · ' : ''}${Math.round(t.fluid_intake)} mL` : ''}</small>
                </span>
                <button
                  type="button"
                  className="icon-button"
                  aria-label={`Remove ${food ? food.name : e.label}`}
                  disabled={remove.busy}
                  onClick={async () => {
                    if (await remove.run(e.id)) {
                      notifyChanged()
                      toast('Entry removed')
                    }
                  }}
                >
                  <svg width="10" height="10" viewBox="0 0 12 12" aria-hidden="true">
                    <path d="M2 2l8 8M10 2l-8 8" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
                  </svg>
                </button>
              </li>
            )
          })}
        </ul>
      ) : (
        <p className="list-empty">Nothing logged yet today.</p>
      )}
      <FormError message={remove.error} />
    </section>
  )
}

/* ------------------------------------------------------------------ */
/* Sheets: log a food, enter values, create a food                     */
/* ------------------------------------------------------------------ */

export function FoodSheet({ open, foods, crewId, mission, onClose, onCreate }: { open: boolean; foods: Food[]; crewId: string; mission: MissionStatus; onClose: () => void; onCreate: () => void }) {
  const { notifyChanged } = useAppState()
  const toast = useToast()
  const [query, setQuery] = useState('')
  const [picked, setPicked] = useState<Food | null>(null)
  const [servings, setServings] = useState(1)
  const add = useMutation((ds: DataSource, entry: IntakeEntry) => ds.addIntake(entry))
  const q = query.trim().toLowerCase()
  const list = foods.filter((f) => !q || f.name.toLowerCase().includes(q)).sort((a, b) => Number(!!b.custom) - Number(!!a.custom) || a.name.localeCompare(b.name))
  const close = () => {
    setPicked(null)
    setQuery('')
    setServings(1)
    onClose()
  }
  const submit = async () => {
    if (!picked) return
    if (await add.run(newEntry(crewId, mission, { foodId: picked.id, servings, label: picked.name }))) {
      notifyChanged()
      toast(`${picked.name} logged`)
      close()
    }
  }
  const unknown = picked ? NUTRIENTS.filter((d) => picked.values[d.id] === null).length : 0
  return (
    <Sheet open={open} title="Log food" onClose={close}>
      {picked ? (
        <div className="stack">
          <button type="button" className="text-button back" onClick={() => setPicked(null)}>
            ‹ All foods
          </button>
          <div>
            <p className="detail-title">{picked.name}</p>
            <p className="body-text muted">
              1 serving = {picked.serving}
              {picked.custom ? ' · created by the crew' : ''}
            </p>
          </div>
          <div className="servings">
            <span className="field-label">Servings</span>
            <div className="stepper">
              <button type="button" className="btn btn-small" aria-label="Fewer servings" disabled={servings <= 0.5} onClick={() => setServings((s) => Math.max(0.5, s - 0.5))}>
                −
              </button>
              <span className="stepper-value" aria-live="polite">
                {servings}
              </span>
              <button type="button" className="btn btn-small" aria-label="More servings" onClick={() => setServings((s) => s + 0.5)}>
                +
              </button>
            </div>
          </div>
          <dl className="food-facts">
            {(['energy_intake', 'protein_intake', 'fluid_intake', 'vitamin_d_intake', 'calcium_intake', 'iron_intake'] as NutrientId[]).map((id) => {
              const v = picked.values[id]
              return (
                <div key={id}>
                  <dt>{NUTRIENT[id].label}</dt>
                  <dd>{v === null || v === undefined ? 'not known' : formatNutrient(id, v * servings)}</dd>
                </div>
              )
            })}
          </dl>
          {unknown > 0 && <p className="fineprint">{unknown} nutrient values of this food are not known yet: those totals will be marked as incomplete.</p>}
          <FormError message={add.error} />
          <button type="button" className="btn btn-primary btn-block" disabled={add.busy} onClick={() => void submit()}>
            Add to today
          </button>
        </div>
      ) : (
        <div className="stack">
          <input type="search" placeholder="Search foods" value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Search foods" />
          <ul className="food-list">
            {list.map((f) => (
              <li key={f.id}>
                <button type="button" className="food-row" onClick={() => setPicked(f)}>
                  <span>
                    {f.name}
                    <small>{f.serving}</small>
                  </span>
                  {f.custom ? <span className="pill tone-blue">Yours</span> : <span className="pill">Station</span>}
                </button>
              </li>
            ))}
            {!list.length && <li className="list-empty">No food matches “{query}”.</li>}
          </ul>
          <button type="button" className="text-button" onClick={onCreate}>
            + Create a food that is not in the list
          </button>
          <p className="fineprint">{CATALOG_NOTE}</p>
        </div>
      )}
    </Sheet>
  )
}

function NutrientFields({ values, onChange }: { values: Record<string, string>; onChange: (v: Record<string, string>) => void }) {
  return (
    <div className="nutrient-fields">
      {NUTRIENTS.map((d) => (
        <label key={d.id} className="field">
          <span className="field-label">
            {d.label} <span className="muted">({d.unit})</span>
          </span>
          <input inputMode="decimal" value={values[d.id] ?? ''} onChange={(e) => onChange({ ...values, [d.id]: e.target.value })} />
        </label>
      ))}
    </div>
  )
}

function parseValues(raw: Record<string, string>): { values: Partial<Record<NutrientId, number>>; bad: string | null } {
  const values: Partial<Record<NutrientId, number>> = {}
  for (const d of NUTRIENTS) {
    const t = (raw[d.id] ?? '').replace(',', '.').trim()
    if (!t) continue
    const v = Number(t)
    if (!Number.isFinite(v) || v < 0) return { values, bad: d.label }
    values[d.id] = v
  }
  return { values, bad: null }
}

function ValuesSheet({ open, crewId, mission, onClose }: { open: boolean; crewId: string; mission: MissionStatus; onClose: () => void }) {
  const { notifyChanged } = useAppState()
  const toast = useToast()
  const [label, setLabel] = useState('')
  const [raw, setRaw] = useState<Record<string, string>>({})
  const add = useMutation((ds: DataSource, entry: IntakeEntry) => ds.addIntake(entry))
  const { values, bad } = parseValues(raw)
  const close = () => {
    setRaw({})
    setLabel('')
    onClose()
  }
  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (bad || !Object.keys(values).length) return
    if (await add.run(newEntry(crewId, mission, { values, label: label.trim() || 'Typed values' }))) {
      notifyChanged()
      toast('Values logged')
      close()
    }
  }
  return (
    <Sheet open={open} title="Enter values" onClose={close} wide>
      <form className="stack" onSubmit={submit}>
        <p className="body-text muted">For fresh food or anything not in the list. Fill in only what you know; empty fields count as nothing.</p>
        <label className="field">
          <span className="field-label">What was it?</span>
          <input value={label} placeholder="e.g. Fresh apple" onChange={(e) => setLabel(e.target.value)} />
        </label>
        <NutrientFields values={raw} onChange={setRaw} />
        {bad && <p className="form-error">{bad}: enter a number of zero or more.</p>}
        <FormError message={add.error} />
        <button type="submit" className="btn btn-primary btn-block" disabled={!!bad || !Object.keys(values).length || add.busy}>
          Add to today
        </button>
      </form>
    </Sheet>
  )
}

function CreateFoodSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { notifyChanged } = useAppState()
  const toast = useToast()
  const [name, setName] = useState('')
  const [serving, setServing] = useState('')
  const [raw, setRaw] = useState<Record<string, string>>({})
  const save = useMutation((ds: DataSource, food: Food) => ds.saveCustomFood(food))
  const { values, bad } = parseValues(raw)
  const close = () => {
    setName('')
    setServing('')
    setRaw({})
    onClose()
  }
  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (!name.trim() || bad) return
    const food: Food = { id: `custom-${Date.now().toString(36)}`, name: name.trim(), serving: serving.trim() || '1 serving', values, source: 'Created by the crew', custom: true }
    if (await save.run(food)) {
      notifyChanged()
      toast(`${food.name} saved: you can now log it`)
      close()
    }
  }
  return (
    <Sheet open={open} title="Create a food" onClose={close} wide>
      <form className="stack" onSubmit={submit}>
        <p className="body-text muted">Save a food you eat often with its values per serving, then log it in one tap.</p>
        <div className="manual-grid">
          <label className="field">
            <span className="field-label">Name</span>
            <input value={name} required placeholder="e.g. Pizza from the cargo" onChange={(e) => setName(e.target.value)} />
          </label>
          <label className="field">
            <span className="field-label">One serving is</span>
            <input value={serving} placeholder="e.g. 1 slice (120 g)" onChange={(e) => setServing(e.target.value)} />
          </label>
        </div>
        <NutrientFields values={raw} onChange={setRaw} />
        {bad && <p className="form-error">{bad}: enter a number of zero or more.</p>}
        <FormError message={save.error} />
        <button type="submit" className="btn btn-primary btn-block" disabled={!name.trim() || !!bad || save.busy}>
          Save food
        </button>
      </form>
    </Sheet>
  )
}

/** Sex, age and height: what the NASA requirements depend on, besides body mass (read from the latest measurement). */
function ProfileSheet({ open, profile, crewId, onClose }: { open: boolean; profile: NutritionProfile; crewId: string; onClose: () => void }) {
  const { notifyChanged } = useAppState()
  const toast = useToast()
  const [sex, setSex] = useState(profile.sex)
  const [age, setAge] = useState(String(profile.ageYears))
  const [height, setHeight] = useState(String(Math.round(profile.heightM * 100)))
  const [menstruating, setMenstruating] = useState(profile.menstruating)
  const save = useMutation((ds: DataSource, p: Omit<NutritionProfile, 'bodyMassKg' | 'source'>) => ds.saveNutritionProfile(crewId, p))
  const ageN = Number(age)
  const heightN = Number(height.replace(',', '.'))
  const valid = Number.isInteger(ageN) && ageN >= 19 && ageN <= 90 && heightN >= 120 && heightN <= 230
  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (!valid) return
    if (await save.run({ sex, ageYears: ageN, heightM: heightN / 100, menstruating: sex === 'female' && menstruating })) {
      notifyChanged()
      toast('Profile saved: targets updated')
      onClose()
    }
  }
  return (
    <Sheet open={open} title="Your profile" onClose={onClose}>
      {open && (
        <form className="stack" onSubmit={submit}>
          <p className="body-text muted">The daily requirements depend on these values and on your latest body mass ({profile.bodyMassKg.toFixed(1)} kg).</p>
          <div className="field">
            <span className="field-label">Sex</span>
            <Segmented label="Sex" value={sex} onChange={setSex} options={[{ value: 'male', label: 'Male' }, { value: 'female', label: 'Female' }]} />
          </div>
          <div className="manual-grid">
            <label className="field">
              <span className="field-label">Age (years)</span>
              <input inputMode="numeric" value={age} onChange={(e) => setAge(e.target.value)} />
            </label>
            <label className="field">
              <span className="field-label">Height (cm)</span>
              <input inputMode="decimal" value={height} onChange={(e) => setHeight(e.target.value)} />
            </label>
          </div>
          {sex === 'female' && (
            <label className="popover-toggle">
              <span>
                Menstruating
                <small>Raises the iron requirement to at least 18 mg (under 50 years)</small>
              </span>
              <input type="checkbox" role="switch" checked={menstruating} onChange={(e) => setMenstruating(e.target.checked)} />
            </label>
          )}
          {!valid && <p className="form-error">Age 19–90 and height 120–230 cm (the NASA equations are for adults).</p>}
          <FormError message={save.error} />
          <button type="submit" className="btn btn-primary btn-block" disabled={!valid || save.busy}>
            Save
          </button>
        </form>
      )}
    </Sheet>
  )
}
