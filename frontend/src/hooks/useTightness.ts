import { useEffect, useLayoutEffect, useState, type RefObject } from 'react'
import { useFitMode } from './useLayout'

/** Containers that must never cut their content in the one-screen layout. */
const WATCHED = '.today-col, .nutrition-main, .nutrition-side, .sleep-plan-card, .sleep-side, .health-page'

/**
 * Fonts, zoom and system scaling differ between computers, so the one-screen
 * layout cannot rely on exact pixels. After each render this checks whether a
 * column overflows and, if so, raises a "tightness" level (1–3) that hides
 * secondary lines step by step in CSS; level 4 lets the column scroll rather
 * than cut anything. A window resize starts again from 0.
 */
export function useTightness(ref: RefObject<HTMLElement | null>): number {
  const fit = useFitMode()
  const [level, setLevel] = useState(0)

  // Measured once the layout has settled (charts size themselves a moment after the first paint).
  useLayoutEffect(() => {
    const el = ref.current
    if (!fit || !el || level >= 4) return
    const t = window.setTimeout(() => {
      const over = [...el.querySelectorAll<HTMLElement>(WATCHED)].some((c) => c.scrollHeight > c.clientHeight + 1)
      if (over) setLevel((l) => Math.min(4, l + 1))
    }, 250)
    return () => window.clearTimeout(t)
  })

  useEffect(() => {
    let t: number | undefined
    const reset = () => {
      window.clearTimeout(t)
      t = window.setTimeout(() => setLevel(0), 120)
    }
    window.addEventListener('resize', reset)
    return () => {
      window.removeEventListener('resize', reset)
      window.clearTimeout(t)
    }
  }, [])

  return fit ? level : 0
}
