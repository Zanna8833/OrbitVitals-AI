import { useEffect, useRef, useState } from 'react'
import type { MissionStatus } from '../domain/types'
import { formatUtc } from '../domain/time'
import { config } from '../config'
import { SCENARIOS } from '../data'
import { href, type Route } from '../hooks/useRoute'
import { useAppState } from '../state/AppState'
import { resetCrewDemoData } from '../state/crewLocal'
import { BrandMark } from './Icons'
import { Segmented } from './ui'

/**
 * One slim bar: brand, the two areas, link status, and a single "Demo" menu
 * that holds everything that only exists for the demonstration (scenario,
 * replay, refresh, appearance). Nothing else competes for attention.
 */
export function NavBar({ route, mission, missionStale }: { route: Route; mission: MissionStatus | undefined; missionStale: boolean }) {
  const area = route.view === 'medical' ? 'medical' : 'crew'
  return (
    <header className="navbar">
      <div className="navbar-inner">
        <a className="brand" href={href.crew()} aria-label="OrbitVitals, home">
          <BrandMark size={24} />
          <span className="brand-name">OrbitVitals</span>
        </a>
        <nav className="area-switch" aria-label="Area">
          <a href={href.crew()} aria-current={area === 'crew' ? 'page' : undefined}>
            Crew
          </a>
          <a href={href.medical()} aria-current={area === 'medical' ? 'page' : undefined}>
            Medical
          </a>
        </nav>
        <div className="navbar-trailing">
          {mission && <LinkStatus mission={mission} stale={missionStale} />}
          <DemoMenu />
        </div>
      </div>
    </header>
  )
}

function LinkStatus({ mission, stale }: { mission: MissionStatus; stale: boolean }) {
  const state = mission.link.state
  const label = state === 'connected' ? 'Ground link' : state === 'offline' ? 'No ground link' : 'Limited link'
  return (
    <span className={`link-status link-${state}`} title={stale ? 'Last known simulated time: the latest refresh failed' : 'Simulated mission time'}>
      <span className="link-dot" aria-hidden="true" />
      <span className="link-label">{label}</span>
      <span className="link-time">
        {formatUtc(mission.now, false)}
        {stale ? ' · not refreshed' : ''}
      </span>
    </span>
  )
}

type Theme = 'system' | 'light' | 'dark'
const THEME_KEY = 'orbitvitals-theme'

function readTheme(): Theme {
  try {
    const v = window.localStorage.getItem(THEME_KEY)
    return v === 'light' || v === 'dark' ? v : 'system'
  } catch {
    return 'system'
  }
}

/** Applies the stored appearance as early as possible (also called before first render). */
export function applyStoredTheme() {
  const t = readTheme()
  if (t === 'system') document.documentElement.removeAttribute('data-theme')
  else document.documentElement.setAttribute('data-theme', t)
}

function DemoMenu() {
  const { scenarioId, setScenarioId, replay, setReplay, autoRefresh, notifyChanged } = useAppState()
  const [open, setOpen] = useState(false)
  const [theme, setTheme] = useState<Theme>(readTheme)
  const wrap = useRef<HTMLDivElement>(null)
  const button = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    try {
      if (theme === 'system') window.localStorage.removeItem(THEME_KEY)
      else window.localStorage.setItem(THEME_KEY, theme)
    } catch {
      /* private mode: the choice still applies to this page */
    }
    applyStoredTheme()
    if (theme !== 'system') document.documentElement.setAttribute('data-theme', theme)
  }, [theme])

  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => {
      if (wrap.current && !wrap.current.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setOpen(false)
        button.current?.focus()
      }
    }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  const scenario = SCENARIOS.find((s) => s.id === scenarioId)
  const refreshOn = autoRefresh.intervalS > 0

  return (
    <div className="demo-menu" ref={wrap}>
      <button ref={button} type="button" className="demo-button" aria-expanded={open} aria-controls="demo-panel" onClick={() => setOpen((v) => !v)}>
        Demo
        <svg width="10" height="6" viewBox="0 0 10 6" aria-hidden="true">
          <path d="M1 1l4 4 4-4" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>
      {open && (
        <div className="popover" id="demo-panel" role="region" aria-label="Demo controls">
          {config.dataSource === 'mock' && (
            <>
              <p className="popover-label" id="scenario-label">
                Scenario
              </p>
              <div className="popover-list" role="radiogroup" aria-labelledby="scenario-label">
                {SCENARIOS.map((s) => (
                  <button
                    key={s.id}
                    type="button"
                    role="radio"
                    aria-checked={s.id === scenarioId}
                    className="popover-option"
                    onClick={() => setScenarioId(s.id)}
                  >
                    <span className="check" aria-hidden="true">
                      {s.id === scenarioId ? '✓' : ''}
                    </span>
                    {s.label.replace(/^\d · /, '')}
                  </button>
                ))}
              </div>
              {scenario && <p className="popover-note">{scenario.description}</p>}
              <hr />
              <label className="popover-toggle">
                <span>
                  Live replay
                  <small>Clock runs from 10:30 UTC</small>
                </span>
                <input type="checkbox" role="switch" checked={replay} onChange={(e) => setReplay(e.target.checked)} />
              </label>
            </>
          )}
          {refreshOn && (
            <label className="popover-toggle">
              <span>
                Auto-refresh
                <small>Every {autoRefresh.intervalS} s</small>
              </span>
              <input type="checkbox" role="switch" checked={!autoRefresh.paused} onChange={(e) => autoRefresh.setPaused(!e.target.checked)} />
            </label>
          )}
          <hr />
          <p className="popover-label">Appearance</p>
          <Segmented
            size="small"
            label="Appearance"
            value={theme}
            onChange={setTheme}
            options={[
              { value: 'system', label: 'Auto' },
              { value: 'light', label: 'Light' },
              { value: 'dark', label: 'Dark' },
            ]}
          />
          <hr />
          <div className="popover-actions">
            <button type="button" className="text-button" onClick={notifyChanged}>
              Refresh now
            </button>
            {config.dataSource === 'mock' && (
              <button
                type="button"
                className="text-button"
                onClick={() => {
                  resetCrewDemoData()
                  setScenarioId(scenarioId)
                }}
              >
                Reset demo data
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export function Footer() {
  return (
    <footer className="app-footer">
      Prototype with simulated data · Not a medical device: no diagnosis or clinical advice · Not affiliated with or endorsed by NASA or ESA
    </footer>
  )
}
