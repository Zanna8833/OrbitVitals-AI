import { useCallback, useEffect, useState } from 'react'

/**
 * "Fit" mode: on a desktop/laptop screen every view fits the viewport with no
 * page scroll. Below this size (phones, small windows) the page scrolls
 * normally — keep in sync with the media query in index.css.
 */
export const FIT_QUERY = '(min-width: 1024px) and (min-height: 620px)'

export function useFitMode(): boolean {
  const [fit, setFit] = useState(() => typeof window !== 'undefined' && window.matchMedia(FIT_QUERY).matches)
  useEffect(() => {
    const mq = window.matchMedia(FIT_QUERY)
    const on = () => setFit(mq.matches)
    on()
    mq.addEventListener('change', on)
    return () => mq.removeEventListener('change', on)
  }, [])
  return fit
}

/**
 * Size of an element whose size is set by the layout (not by its content).
 * Returns a callback ref, so it also works for elements that appear later.
 */
export function useBoxSize<T extends HTMLElement>() {
  const [el, setEl] = useState<T | null>(null)
  const [size, setSize] = useState({ width: 0, height: 0 })
  useEffect(() => {
    if (!el) return
    const measure = () => setSize({ width: el.clientWidth, height: el.clientHeight })
    measure()
    const ro = new ResizeObserver(measure)
    ro.observe(el)
    return () => ro.disconnect()
  }, [el])
  const ref = useCallback((node: T | null) => setEl(node), [])
  return [ref, size] as const
}
