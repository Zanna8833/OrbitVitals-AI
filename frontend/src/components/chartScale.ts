/** Small, dependency-free helpers for the SVG charts. */

export function linear(d0: number, d1: number, r0: number, r1: number) {
  const k = d1 === d0 ? 0 : (r1 - r0) / (d1 - d0)
  return (v: number) => r0 + (v - d0) * k
}

/** "Nice" ticks (1, 2, 2.5, 5 × 10^n). */
export function niceTicks(min: number, max: number, count = 4): number[] {
  if (!(max > min)) return [min]
  const raw = (max - min) / count
  const mag = Math.pow(10, Math.floor(Math.log10(raw)))
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? 10 * mag
  const ticks: number[] = []
  for (let v = Math.ceil(min / step) * step; v <= max + step * 1e-9; v += step) ticks.push(Math.round(v / step) * step)
  return ticks
}

export function niceDomain(min: number, max: number, count = 4): [number, number] {
  if (!(max > min)) return [min - 1, max + 1]
  const ticks = niceTicks(min, max, count)
  const step = ticks.length > 1 ? ticks[1] - ticks[0] : 1
  return [Math.floor(min / step) * step, Math.ceil(max / step) * step]
}

/** Time ticks aligned to round minutes. */
export function timeTicks(fromMs: number, toMs: number, maxTicks = 8): number[] {
  const spanMin = (toMs - fromMs) / 60000
  const step = [1, 2, 5, 10, 15, 30, 60].find((s) => spanMin / s <= maxTicks) ?? 60
  const stepMs = step * 60000
  const out: number[] = []
  for (let t = Math.ceil(fromMs / stepMs) * stepMs; t <= toMs; t += stepMs) out.push(t)
  return out
}
