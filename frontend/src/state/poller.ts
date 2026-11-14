/** The part of `document` the poller needs; injectable so it can be tested without a browser. */
export interface VisibilitySource {
  readonly hidden: boolean
  addEventListener(type: 'visibilitychange', listener: () => void): void
  removeEventListener(type: 'visibilitychange', listener: () => void): void
}

/**
 * Calls `onTick` every `intervalMs` while the page is visible. When the page
 * becomes visible again it ticks immediately, so returning to a background tab
 * never shows data older than one interval. Returns a function that stops it.
 */
export function startPolling(intervalMs: number, onTick: () => void, visibility?: VisibilitySource): () => void {
  const isVisible = () => !visibility?.hidden
  const timer = setInterval(() => {
    if (isVisible()) onTick()
  }, intervalMs)
  const onVisibilityChange = () => {
    if (isVisible()) onTick()
  }
  visibility?.addEventListener('visibilitychange', onVisibilityChange)
  return () => {
    clearInterval(timer)
    visibility?.removeEventListener('visibilitychange', onVisibilityChange)
  }
}
