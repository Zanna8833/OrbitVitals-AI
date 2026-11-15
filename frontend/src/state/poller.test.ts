import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { startPolling, type VisibilitySource } from './poller'
import { DEFAULT_REFRESH_INTERVAL_S, parseRefreshIntervalS } from '../config'

class FakeDocument implements VisibilitySource {
  hidden = false
  private listeners = new Set<() => void>()
  addEventListener(_: 'visibilitychange', l: () => void) {
    this.listeners.add(l)
  }
  removeEventListener(_: 'visibilitychange', l: () => void) {
    this.listeners.delete(l)
  }
  setHidden(hidden: boolean) {
    this.hidden = hidden
    this.listeners.forEach((l) => l())
  }
  get listenerCount() {
    return this.listeners.size
  }
}

describe('startPolling', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('ticks once per interval while visible', () => {
    const onTick = vi.fn()
    const stop = startPolling(10_000, onTick, new FakeDocument())
    vi.advanceTimersByTime(35_000)
    expect(onTick).toHaveBeenCalledTimes(3)
    stop()
  })

  it('does not tick while the page is hidden, and catches up once when it becomes visible', () => {
    const doc = new FakeDocument()
    const onTick = vi.fn()
    const stop = startPolling(10_000, onTick, doc)
    doc.setHidden(true)
    vi.advanceTimersByTime(60_000)
    expect(onTick).not.toHaveBeenCalled()
    doc.setHidden(false)
    expect(onTick).toHaveBeenCalledTimes(1)
    stop()
  })

  it('stops ticking and removes its listener when stopped', () => {
    const doc = new FakeDocument()
    const onTick = vi.fn()
    const stop = startPolling(10_000, onTick, doc)
    stop()
    vi.advanceTimersByTime(60_000)
    expect(onTick).not.toHaveBeenCalled()
    expect(doc.listenerCount).toBe(0)
  })
})

describe('parseRefreshIntervalS', () => {
  it('uses the default when unset or invalid', () => {
    expect(parseRefreshIntervalS(undefined)).toBe(DEFAULT_REFRESH_INTERVAL_S)
    expect(parseRefreshIntervalS('')).toBe(DEFAULT_REFRESH_INTERVAL_S)
    expect(parseRefreshIntervalS('abc')).toBe(DEFAULT_REFRESH_INTERVAL_S)
    expect(parseRefreshIntervalS('-5')).toBe(DEFAULT_REFRESH_INTERVAL_S)
    expect(parseRefreshIntervalS('2.5')).toBe(DEFAULT_REFRESH_INTERVAL_S)
  })
  it('accepts whole seconds, and 0 to disable', () => {
    expect(parseRefreshIntervalS('30')).toBe(30)
    expect(parseRefreshIntervalS('0')).toBe(0)
  })
})
