/**
 * Demo mode: the built-in scenarios (no ground link, data not updated,
 * uncertain quality, events to review) on generated sample data. It never
 * talks to the backend and keeps its own local store, so it cannot mix with
 * real records. The choice is remembered in this browser.
 */
const KEY = 'orbitvitals:demo-mode'

export function demoModeOn(): boolean {
  if (import.meta.env.VITE_DATA_SOURCE === 'mock') return true
  try {
    return window.localStorage.getItem(KEY) === '1'
  } catch {
    return false
  }
}

export function setDemoModeStored(on: boolean) {
  try {
    if (on) window.localStorage.setItem(KEY, '1')
    else window.localStorage.removeItem(KEY)
  } catch {
    /* private mode: applies to this page only */
  }
}
