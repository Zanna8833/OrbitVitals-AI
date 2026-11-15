import type { IntakeEntry, NutrientId, NutritionProfile } from '../../domain/nutrition'

/** SIMULATED crew profiles for the nutrition requirements (no real person). */
export const NUTRITION_PROFILES: Record<string, Omit<NutritionProfile, 'bodyMassKg' | 'source'>> = {
  'crew-a': { sex: 'male', ageYears: 42, heightM: 1.8, menstruating: false },
  'crew-b': { sex: 'female', ageYears: 37, heightM: 1.66, menstruating: false },
  'crew-c': { sex: 'male', ageYears: 45, heightM: 1.84, menstruating: false },
}

type Item = [time: string, foodId: string | null, servings: number, label?: string, values?: Partial<Record<NutrientId, number>>]

/** A typical day with station foods, typed fresh-food values and water. */
const DAY: Item[] = [
  ['07:20', 'scrambled_eggs', 1],
  ['07:20', 'flour_tortilla', 2],
  ['07:25', 'coffee', 1],
  ['09:30', null, 1, 'Water', { fluid_intake: 500 }],
  ['12:40', 'tuna', 1],
  ['12:40', 'flour_tortilla', 2],
  ['12:45', 'cream_of_mushroom_soup', 2],
  ['12:50', 'lemonade', 1],
  ['14:30', null, 1, 'Water', { fluid_intake: 500 }],
  ['16:00', 'almonds', 1],
  ['16:00', 'dried_apricots', 1],
  ['16:05', 'granola_bar', 1],
  ['18:30', null, 1, 'Water', { fluid_intake: 500 }],
  ['19:30', 'salmon', 2],
  [
    '19:30', null, 1, 'Fresh food (typed values)',
    { energy_intake: 980, protein_intake: 34, fluid_intake: 260, vitamin_a_intake: 420, vitamin_c_intake: 95, vitamin_k_intake: 80, folate_intake: 210, calcium_intake: 540, phosphorus_intake: 420, sodium_intake: 690, potassium_intake: 1700, iron_intake: 2.1, magnesium_intake: 210, zinc_intake: 4.5, vitamin_b12_intake: 1.1, vitamin_d_intake: 2 },
  ],
  ['19:40', 'shortbread_cookies', 1],
  ['20:00', 'tea', 1],
  ['21:00', null, 1, 'Water', { fluid_intake: 400 }],
]

/** Seven previous days in full and today until `now` (UTC). Deterministic. */
export function seedIntake(crewId: string, nowIso: string, missionDay = 8): IntakeEntry[] {
  const today = nowIso.slice(0, 10)
  const out: IntakeEntry[] = []
  const skip = crewId === 'crew-b' ? new Set(['16:00', '21:00']) : new Set<string>()
  for (let back = Math.max(7, missionDay - 1); back >= 0; back--) {
    // Days before the last week: the same menu with a little day-to-day variety (one snack or drink less some days).
    const lighter = back > 7 ? DAY.length - 1 - ((back * 3 + crewId.length) % 4) : -1
    const date = new Date(Date.parse(`${today}T00:00:00Z`) - back * 86_400_000).toISOString().slice(0, 10)
    DAY.forEach(([time, foodId, servings, label, values], i) => {
      if (back === 0 && `${date}T${time}:00Z` > nowIso) return
      if (back % 3 === 1 && skip.has(time)) return
      if (i === lighter) return
      out.push({
        id: `seed-${crewId}-${date}-${i}`,
        crewId,
        eatenAt: `${date}T${time}:00Z`,
        foodId,
        servings,
        values: values ?? {},
        label: label ?? foodId ?? 'Entry',
      })
    })
  }
  return out
}
