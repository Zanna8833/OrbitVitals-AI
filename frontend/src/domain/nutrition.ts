/**
 * Daily nutrition against NASA's spaceflight requirements.
 *
 * Port of backend/app/domains/nutrition/nutrition.py (same constants, same
 * rules), so the crew sees the same targets the ground evaluation uses:
 * NASA JSC-67378 Rev 1 (2020), Nutritional Requirements for Exploration
 * Missions up to 365 days. A planning aid, not a diagnosis or a prescription.
 */
import foodCatalogJson from '../../../backend/app/domains/nutrition/iss_food_catalog.json'

export type NutrientId =
  | 'energy_intake' | 'protein_intake' | 'fluid_intake'
  | 'vitamin_a_intake' | 'vitamin_c_intake' | 'vitamin_d_intake' | 'vitamin_k_intake' | 'vitamin_b12_intake' | 'folate_intake'
  | 'calcium_intake' | 'phosphorus_intake' | 'sodium_intake' | 'potassium_intake' | 'iron_intake' | 'magnesium_intake' | 'zinc_intake'

export type NutrientGroup = 'essentials' | 'vitamins' | 'minerals'

export interface NutrientDef {
  id: NutrientId
  label: string
  short: string
  unit: string
  decimals: number
  group: NutrientGroup
}

const n = (id: NutrientId, label: string, short: string, unit: string, decimals: number, group: NutrientGroup): NutrientDef => ({ id, label, short, unit, decimals, group })

/** Same order as EVALUATED_METRICS in the backend; units from schemas/metric_catalog.json. */
export const NUTRIENTS: NutrientDef[] = [
  n('fluid_intake', 'Water', 'Water', 'mL', 0, 'essentials'),
  n('energy_intake', 'Energy', 'Energy', 'kcal', 0, 'essentials'),
  n('protein_intake', 'Protein', 'Protein', 'g', 0, 'essentials'),
  n('vitamin_a_intake', 'Vitamin A', 'A', 'µg', 0, 'vitamins'),
  n('vitamin_c_intake', 'Vitamin C', 'C', 'mg', 0, 'vitamins'),
  n('vitamin_d_intake', 'Vitamin D', 'D', 'µg', 1, 'vitamins'),
  n('vitamin_k_intake', 'Vitamin K', 'K', 'µg', 0, 'vitamins'),
  n('vitamin_b12_intake', 'Vitamin B12', 'B12', 'µg', 1, 'vitamins'),
  n('folate_intake', 'Folate', 'Folate', 'µg', 0, 'vitamins'),
  n('calcium_intake', 'Calcium', 'Ca', 'mg', 0, 'minerals'),
  n('phosphorus_intake', 'Phosphorus', 'P', 'mg', 0, 'minerals'),
  n('sodium_intake', 'Sodium', 'Na', 'mg', 0, 'minerals'),
  n('potassium_intake', 'Potassium', 'K', 'mg', 0, 'minerals'),
  n('iron_intake', 'Iron', 'Fe', 'mg', 1, 'minerals'),
  n('magnesium_intake', 'Magnesium', 'Mg', 'mg', 0, 'minerals'),
  n('zinc_intake', 'Zinc', 'Zn', 'mg', 1, 'minerals'),
]
export const NUTRIENT: Record<NutrientId, NutrientDef> = Object.fromEntries(NUTRIENTS.map((d) => [d.id, d])) as Record<NutrientId, NutrientDef>
/** Vitamins and minerals: the "micronutrients" ring. */
export const MICRONUTRIENTS = NUTRIENTS.filter((d) => d.group !== 'essentials').map((d) => d.id)

export type Sex = 'male' | 'female'
export interface NutritionProfile {
  sex: Sex
  ageYears: number
  heightM: number
  bodyMassKg: number
  menstruating: boolean
  /** Where the profile comes from (shown, never hidden). */
  source: string
}

/* ---- constants: identical to nutrition.py ---- */
const ACTIVITY_FACTOR = 1.25
const ENERGY_MARGIN = 0.02
const PROTEIN_G_PER_KG: [number, number] = [1.2, 1.8]
const FLUID_ML_PER_KG = 32
const FLUID_MIN_ML: Record<Sex, number> = { male: 2500, female: 2100 }
const PHOSPHORUS_TO_CALCIUM_MAX = 1.5
const IRON_MENSTRUATION_MIN_MG = 18
const FIXED: Partial<Record<NutrientId, Record<Sex, [number | null, number | null]>>> = {
  vitamin_a_intake: { male: [900, null], female: [700, null] },
  vitamin_c_intake: { male: [125, null], female: [110, null] },
  vitamin_d_intake: { male: [25, null], female: [25, null] },
  vitamin_k_intake: { male: [120, null], female: [90, null] },
  vitamin_b12_intake: { male: [2.4, null], female: [2.4, null] },
  folate_intake: { male: [400, null], female: [400, null] },
  calcium_intake: { male: [1000, 2500], female: [1000, 2500] },
  phosphorus_intake: { male: [700, null], female: [700, null] },
  sodium_intake: { male: [1500, 2300], female: [1500, 2300] },
  potassium_intake: { male: [3400, null], female: [2600, null] },
  // Limited because spaceflight raises iron stores (JSC-67378)
  iron_intake: { male: [null, 8], female: [null, 8] },
  magnesium_intake: { male: [420, null], female: [320, null] },
  zinc_intake: { male: [11, null], female: [8, null] },
}

/** kcal/day, DRI equations for adults as in JSC-67378 / OCHMO-TB-013. */
export function estimatedEnergyRequirement(p: NutritionProfile): number {
  if (p.sex === 'male') return 662 - 9.53 * p.ageYears + ACTIVITY_FACTOR * (15.9 * p.bodyMassKg + 539.6 * p.heightM)
  return 354 - 6.91 * p.ageYears + ACTIVITY_FACTOR * (9.36 * p.bodyMassKg + 726 * p.heightM)
}

export interface Requirement {
  min: number | null
  max: number | null
  note: string
}

/** Daily (minimum, maximum) for this crew member; null = no limit. Same rules as requirement_range(). */
export function requirementOf(id: NutrientId, p: NutritionProfile, calciumIntake: number | null): Requirement {
  const m = p.bodyMassKg
  if (id === 'energy_intake') return { min: estimatedEnergyRequirement(p) * (1 - ENERGY_MARGIN), max: null, note: 'Estimated energy requirement for your age, height and mass (team margin 2%).' }
  if (id === 'protein_intake') return { min: PROTEIN_G_PER_KG[0] * m, max: PROTEIN_G_PER_KG[1] * m, note: '1.2–1.8 g per kg of body mass.' }
  if (id === 'fluid_intake') return { min: Math.max(FLUID_ML_PER_KG * m, FLUID_MIN_ML[p.sex]), max: null, note: '32 mL per kg, at least 2.5 L (men) or 2.1 L (women). Includes the water in food.' }
  if (id === 'iron_intake' && p.sex === 'female' && p.menstruating && p.ageYears < 50) return { min: IRON_MENSTRUATION_MIN_MG, max: null, note: 'At least 18 mg for women under 50 who menstruate.' }
  const [min, max] = FIXED[id]![p.sex]
  if (id === 'phosphorus_intake' && calciumIntake !== null) return { min, max: PHOSPHORUS_TO_CALCIUM_MAX * calciumIntake, note: 'At most 1.5 × your calcium intake.' }
  if (id === 'iron_intake') return { min, max, note: 'An upper limit: spaceflight raises iron stores, so too much is the risk.' }
  return { min, max, note: '' }
}

/* ---- foods ---- */
export interface Food {
  id: string
  name: string
  serving: string
  /** Per serving; null = value not known yet. */
  values: Partial<Record<NutrientId, number | null>>
  source: string
  custom?: boolean
}

interface CatalogFile {
  description: string
  foods: Record<string, { name: string; serving: string; source: string; values: Record<string, number | null> }>
}
const catalogFile = foodCatalogJson as unknown as CatalogFile
export const CATALOG_NOTE = catalogFile.description
/** The station foods shared with the backend (backend/app/domains/nutrition/iss_food_catalog.json). */
export const ISS_FOODS: Food[] = Object.entries(catalogFile.foods).map(([id, f]) => ({ id, name: f.name, serving: f.serving, source: f.source, values: f.values as Food['values'] }))

/* ---- intake log ---- */
export interface IntakeEntry {
  id: string
  crewId: string
  eatenAt: string
  /** A food (catalog or custom) and its servings, OR direct values. */
  foodId: string | null
  servings: number
  values: Partial<Record<NutrientId, number>>
  /** Shown in the log ("Water", "Lunch – typed values"…). */
  label: string
}

export interface DayTotals {
  totals: Record<NutrientId, number>
  /** Nutrients for which a logged food has no known value: the total is a lower bound. */
  unknown: Partial<Record<NutrientId, string[]>>
  entries: number
}

export function entryValues(e: IntakeEntry, foods: Food[]): Partial<Record<NutrientId, number | null>> {
  if (!e.foodId) return e.values
  const f = foods.find((x) => x.id === e.foodId)
  if (!f) return {}
  const out: Partial<Record<NutrientId, number | null>> = {}
  for (const d of NUTRIENTS) {
    const v = f.values[d.id]
    out[d.id] = v === null || v === undefined ? (v === null ? null : 0) : v * e.servings
  }
  return out
}

export function totalsOf(entries: IntakeEntry[], foods: Food[]): DayTotals {
  const totals = Object.fromEntries(NUTRIENTS.map((d) => [d.id, 0])) as Record<NutrientId, number>
  const unknown: DayTotals['unknown'] = {}
  for (const e of entries) {
    const v = entryValues(e, foods)
    for (const d of NUTRIENTS) {
      const x = v[d.id]
      if (x === null) (unknown[d.id] ??= []).push(e.label)
      else totals[d.id] += x ?? 0
    }
  }
  return { totals, unknown, entries: entries.length }
}

export type NutrientState = 'reached' | 'below' | 'over' | 'within_limit' | 'unknown'

export interface NutrientProgress {
  def: NutrientDef
  value: number
  req: Requirement
  /** 0–1 towards the minimum (or of the limit, for limit-only nutrients). */
  fill: number
  state: NutrientState
  /** Amount still needed to reach the minimum (0 when reached). */
  remaining: number
}

/**
 * `partial`: a day still in progress. The phosphorus limit (1.5 × calcium) is
 * only applied to complete days, as the backend does with daily means.
 */
export function progressOf(id: NutrientId, day: DayTotals, p: NutritionProfile, partial = false): NutrientProgress {
  const def = NUTRIENT[id]
  const req = requirementOf(id, p, day.entries && !partial ? day.totals.calcium_intake : null)
  const value = day.totals[id]
  let state: NutrientState
  let fill: number
  if (req.max !== null && value > req.max) state = 'over'
  else if (req.min !== null) state = value >= req.min ? 'reached' : 'below'
  else state = 'within_limit'
  if (req.min !== null) fill = Math.min(1, value / req.min)
  else fill = req.max ? Math.min(1, value / req.max) : 0
  if (day.unknown[id]?.length && state === 'below') state = 'unknown'
  return { def, value, req, fill, state, remaining: req.min !== null ? Math.max(0, req.min - value) : 0 }
}

export interface NutritionSummary {
  water: NutrientProgress
  energy: NutrientProgress
  protein: NutrientProgress
  micros: NutrientProgress[]
  /** Micronutrients at their target (minimum reached, no limit exceeded). */
  microsOnTarget: number
  /** Mean fill of the micronutrients (0–1): the ring. */
  microsFill: number
  /** Nutrients above an upper limit (e.g. iron, sodium). */
  over: NutrientProgress[]
}

export function summarize(day: DayTotals, p: NutritionProfile, partial = false): NutritionSummary {
  const micros = MICRONUTRIENTS.map((id) => progressOf(id, day, p, partial))
  const ok = (x: NutrientProgress) => x.state === 'reached' || x.state === 'within_limit'
  const all = [...NUTRIENTS.map((d) => progressOf(d.id, day, p, partial))]
  return {
    water: progressOf('fluid_intake', day, p, partial),
    energy: progressOf('energy_intake', day, p, partial),
    protein: progressOf('protein_intake', day, p, partial),
    micros,
    microsOnTarget: micros.filter(ok).length,
    microsFill: micros.reduce((a, x) => a + (x.state === 'over' ? 1 : x.fill), 0) / micros.length,
    over: all.filter((x) => x.state === 'over'),
  }
}

export function formatNutrient(id: NutrientId, v: number): string {
  if (id === 'fluid_intake' && v >= 1000) return `${(v / 1000).toFixed(v >= 10000 ? 0 : 1)} L`
  const d = NUTRIENT[id]
  return `${v.toFixed(d.decimals)} ${d.unit}`
}

export const NASA_SOURCE = 'NASA JSC-67378 Rev 1 (2020), Nutritional Requirements for Exploration Missions up to 365 days'
