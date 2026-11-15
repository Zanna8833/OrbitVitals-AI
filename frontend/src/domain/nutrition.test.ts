import { describe, expect, it } from 'vitest'
import { ISS_FOODS, estimatedEnergyRequirement, requirementOf, summarize, totalsOf, type IntakeEntry, type NutritionProfile } from './nutrition'

const man: NutritionProfile = { sex: 'male', ageYears: 40, heightM: 1.8, bodyMassKg: 80, menstruating: false, source: 'test' }
const entry = (over: Partial<IntakeEntry>): IntakeEntry => ({ id: 'e', crewId: 'c', eatenAt: '2026-11-14T08:00:00Z', foodId: null, servings: 1, values: {}, label: 'x', ...over })

describe('nutrition requirements (same as backend nutrition.py)', () => {
  it('energy requirement uses the DRI equation with activity factor 1.25', () => {
    expect(estimatedEnergyRequirement(man)).toBeCloseTo(662 - 9.53 * 40 + 1.25 * (15.9 * 80 + 539.6 * 1.8), 6)
    expect(requirementOf('energy_intake', man, null).min).toBeCloseTo(estimatedEnergyRequirement(man) * 0.98, 6)
  })
  it('fluid: 32 mL/kg with a 2.5 L floor for men', () => {
    expect(requirementOf('fluid_intake', man, null).min).toBe(2560)
    expect(requirementOf('fluid_intake', { ...man, bodyMassKg: 60 }, null).min).toBe(2500)
  })
  it('iron is an upper limit unless menstruating under 50', () => {
    expect(requirementOf('iron_intake', man, null)).toMatchObject({ min: null, max: 8 })
    expect(requirementOf('iron_intake', { ...man, sex: 'female', menstruating: true, ageYears: 35 }, null)).toMatchObject({ min: 18, max: null })
  })
  it('phosphorus maximum follows calcium', () => {
    expect(requirementOf('phosphorus_intake', man, 1000).max).toBe(1500)
  })
})

describe('daily totals', () => {
  it('sums catalog foods by servings and direct values, and flags too much iron', () => {
    const eggs = ISS_FOODS.find((f) => f.id === 'scrambled_eggs')!
    const day = totalsOf([entry({ foodId: 'scrambled_eggs', servings: 2, label: 'Eggs' }), entry({ values: { fluid_intake: 500, iron_intake: 9 }, label: 'Water' })], ISS_FOODS)
    expect(day.totals.protein_intake).toBeCloseTo((eggs.values.protein_intake as number) * 2, 6)
    expect(day.totals.fluid_intake).toBeCloseTo((eggs.values.fluid_intake as number) * 2 + 500, 6)
    const s = summarize(day, man)
    expect(s.over.map((x) => x.def.id)).toContain('iron_intake')
    expect(s.water.state).toBe('below')
  })
  it('marks a total as uncertain when a food has no known value', () => {
    const day = totalsOf([entry({ foodId: 'x', label: 'x' })], [{ id: 'x', name: 'X', serving: '1', source: '', values: { vitamin_c_intake: null } }])
    expect(day.unknown.vitamin_c_intake).toEqual(['x'])
  })
})
