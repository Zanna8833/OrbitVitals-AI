import { useEffect, useRef, useState } from 'react'
import type { MissionStatus } from '../domain/types'
import { formatUtc } from '../domain/time'
import { config } from '../config'
import { SCENARIOS } from '../data'
import { href, type Route } from '../hooks/useRoute'
import { useAppState } from '../state/AppState'
import { resetCrewDemoData } from '../state/crewLocal'
import { BrandMark } from './Icons'
import { Segmented, Sheet, SimTag } from './ui'
import { BubbleIcon } from '../views/assistant/AssistantPage'
import { ImportSheet } from './ImportSheet'

/**
 * One slim bar: brand, the two areas, link status, and a single "Demo" menu
 * that holds everything that only exists for the demonstration (scenario,
 * replay, refresh, appearance). Nothing else competes for attention.
 */
export function NavBar({ route, mission, missionStale }: { route: Route; mission: MissionStatus | undefined; missionStale: boolean }) {
  const area = route.view === 'medical' ? 'medical' : route.view === 'crew' ? 'crew' : null
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
      <span className="met" title="Mission elapsed time (simulated mission)">
        T+{metOf(mission)}
      </span>
    </span>
  )
}

/** Mission elapsed time since the start of day 1 (UTC), as mission control writes it: 14d 10:40. */
function metOf(mission: MissionStatus): string {
  const ms = Date.parse(mission.now) - Date.parse(`${mission.missionStartDate}T00:00:00Z`)
  if (!(ms >= 0)) return '—'
  const d = Math.floor(ms / 86_400_000)
  const h = Math.floor((ms % 86_400_000) / 3_600_000)
  const m = Math.floor((ms % 3_600_000) / 60_000)
  return `${d}d ${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`
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
  const [importing, setImporting] = useState(false)
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
          {config.dataSource === 'mock' && (
            <>
              <hr />
              <button
                type="button"
                className="popover-option popover-import"
                onClick={() => {
                  setOpen(false)
                  setImporting(true)
                }}
              >
                <span className="check" aria-hidden="true" />
                Import crew data (JSON + CSV)…
              </button>
            </>
          )}
        </div>
      )}
      <ImportSheet open={importing} onClose={() => setImporting(false)} />
    </div>
  )
}

export function Footer({ showAssistant = true }: { showAssistant?: boolean }) {
  const [about, setAbout] = useState(false)
  return (
    <footer className="app-footer">
      <span>
        Prototype with simulated data · Not a medical device: no diagnosis or clinical advice · Not affiliated with or endorsed by NASA or ESA ·{' '}
        <button type="button" className="footer-link" onClick={() => setAbout(true)}>
          What is real, what is simulated?
        </button>
      </span>
      <AboutDemo open={about} onClose={() => setAbout(false)} />
      {/* The assistant is an add-on, kept to the side on purpose. */}
      {showAssistant && (
        <a className="assistant-bubble" href={href.assistant()} aria-label="Assistant (preview)">
          <BubbleIcon size={25} />
          <span className="assistant-tip">Assistant</span>
        </a>
      )}
    </footer>
  )
}

/** For judges and testers: what actually works in this prototype and what is simulated. */
function AboutDemo({ open, onClose }: { open: boolean; onClose: () => void }) {
  const rows: [string, 'works' | 'sim' | 'off', string][] = [
    ['Interface, navigation, accessibility', 'works', 'Fully working in the browser'],
    ['Data quality, personal baseline, trend', 'works', 'Really computed by the app from the data it receives'],
    ['Sleep-aid plan and coverage check', 'works', 'Really computed; saved only in this browser'],
    ['Offline queue for reports', 'works', 'Real logic: saved locally, sent when the (simulated) link returns'],
    ['Physiological readings and sensors', 'sim', 'Synthetic, deterministic data — no real person, no device'],
    ['Ground link and mission time', 'sim', 'Simulated scenarios chosen from the Demo menu'],
    ['Reports and messages with the medical team', 'sim', 'Delivered to the other side of this same demo, not over a network'],
    ['Measurements', 'sim', 'A guided, simulated acquisition: no instrument is connected'],
    ['Assistant', 'off', 'Placeholder page: no language model is connected'],
    ['Backend', 'off', 'HTTP adapter ready (docs/FRONTEND_DATA_CONTRACT.md), not yet connected'],
  ]
  const label = { works: 'Working', sim: 'Simulated', off: 'Not connected' }
  return (
    <Sheet open={open} title="What is real, what is simulated" onClose={onClose} wide>
      <table className="about-table">
        <tbody>
          {rows.map(([what, kind, how]) => (
            <tr key={what}>
              <th scope="row">{what}</th>
              <td>{kind === 'sim' ? <SimTag /> : <span className={`state-tag is-${kind}`}>{label[kind]}</span>}</td>
              <td className="muted">{how}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="fineprint">OrbitVitals is a prototype for the NASA Space Apps Challenge. It is not a medical device and gives no diagnosis or clinical advice.</p>
    </Sheet>
  )
}
