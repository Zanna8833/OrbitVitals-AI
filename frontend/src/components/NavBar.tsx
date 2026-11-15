import { useEffect, useRef, useState } from 'react'
import type { MissionStatus } from '../domain/types'
import { formatUtc } from '../domain/time'
import { config } from '../config'
import { SCENARIOS } from '../data'
import { href, type Route } from '../hooks/useRoute'
import { useAppState } from '../state/AppState'
import { BrandMark } from './Icons'
import { Segmented } from './ui'
import { BubbleIcon } from '../views/assistant/AssistantPage'
import { ImportSheet } from './ImportSheet'

/** One slim bar: brand, the two areas, link status and the settings menu. */
export function NavBar({ route, mission, missionStale }: { route: Route; mission: MissionStatus | undefined; missionStale: boolean }) {
  const area = route.view === 'medical' ? 'medical' : route.view === 'crew' ? 'crew' : null
  return (
    <header className="navbar">
      <div className="navbar-inner">
        <a className="brand" href={href.crewHome()} aria-label="OrbitVitals, home">
          <BrandMark size={24} />
          <span className="brand-name">OrbitVitals</span>
        </a>
        <nav className="area-switch" aria-label="Area">
          <a href={href.crewHome()} aria-current={area === 'crew' ? 'page' : undefined}>
            Crew
          </a>
          <a href={href.medical()} aria-current={area === 'medical' ? 'page' : undefined}>
            Medical
          </a>
        </nav>
        <div className="navbar-trailing">
          <DemoBadge />
          {mission && <LinkStatus mission={mission} stale={missionStale} />}
          <SettingsMenu />
        </div>
      </div>
    </header>
  )
}

function LinkStatus({ mission, stale }: { mission: MissionStatus; stale: boolean }) {
  const state = mission.link.state
  const label = state === 'connected' ? 'Ground link' : state === 'offline' ? 'No ground link' : 'Limited link'
  return (
    <span className={`link-status link-${state}`} title={stale ? 'Last known time: the latest refresh failed' : 'Mission time (UTC)'}>
      <span className="link-dot" aria-hidden="true" />
      <span className="link-label">{label}</span>
      <span className="link-time">
        {formatUtc(mission.now, false)}
        {stale ? ' · not refreshed' : ''}
      </span>
      <span className="met" title="Mission elapsed time">
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

function SettingsMenu() {
  const { dataSource, notifyChanged, demo, setDemo, scenarioId, setScenarioId } = useAppState()
  const [open, setOpen] = useState(false)
  const [importing, setImporting] = useState(false)
  const [theme, setTheme] = useState<Theme>(readTheme)
  const [server, setServer] = useState<'checking' | 'ok' | 'down'>('checking')
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
    let alive = true
    dataSource
      .getMissionStatus()
      .then(() => alive && setServer('ok'))
      .catch(() => alive && setServer('down'))
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
      alive = false
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open, dataSource])

  return (
    <div className="demo-menu" ref={wrap}>
      <button ref={button} type="button" className="demo-button settings-button" aria-expanded={open} aria-controls="settings-panel" aria-label="Settings" onClick={() => setOpen((v) => !v)}>
        <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
          <path
            d="M12 15.2a3.2 3.2 0 1 0 0-6.4 3.2 3.2 0 0 0 0 6.4Zm7.4-2.2.1-1-.1-1 2-1.6-2-3.4-2.4 1a7.6 7.6 0 0 0-1.7-1L14.9 3h-3.8l-.4 2.6a7.6 7.6 0 0 0-1.7 1l-2.4-1-2 3.4 2 1.6-.1 1 .1 1-2 1.6 2 3.4 2.4-1a7.6 7.6 0 0 0 1.7 1l.4 2.6h3.8l.4-2.6a7.6 7.6 0 0 0 1.7-1l2.4 1 2-3.4Z"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinejoin="round"
          />
        </svg>
      </button>
      {open && (
        <div className="popover" id="settings-panel" role="region" aria-label="Settings">
          <p className="popover-label">Server</p>
          <p className="popover-note popover-source">
            <span className={`server-dot is-${server}`} aria-hidden="true" />
            {demo ? 'Demo mode: sample data, the server is not used' : server === 'checking' ? 'Checking the connection…' : server === 'ok' ? 'Connected to the OrbitVitals server' : 'The OrbitVitals server is not reachable'}
          </p>
          <hr />
          <label className="popover-toggle">
            <span>
              Demo mode
              <small>Scenarios on sample data, separate from the server</small>
            </span>
            <input type="checkbox" role="switch" checked={demo} disabled={config.dataSource === 'mock'} onChange={(e) => setDemo(e.target.checked)} />
          </label>
          {demo && (
            <>
              <p className="popover-label" id="scenario-label">
                Scenario
              </p>
              <div className="popover-list" role="radiogroup" aria-labelledby="scenario-label">
                {SCENARIOS.map((s) => (
                  <button key={s.id} type="button" role="radio" aria-checked={s.id === scenarioId} className="popover-option" onClick={() => setScenarioId(s.id)}>
                    <span className="check" aria-hidden="true">
                      {s.id === scenarioId ? '✓' : ''}
                    </span>
                    {s.label.replace(/^\d · /, '')}
                  </button>
                ))}
              </div>
              <p className="popover-note">{SCENARIOS.find((s) => s.id === scenarioId)?.description}</p>
            </>
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
          <button
            type="button"
            className="popover-option"
            onClick={() => {
              setOpen(false)
              notifyChanged()
            }}
          >
            <span className="check" aria-hidden="true" />
            Refresh data
          </button>
        </div>
      )}
      <ImportSheet open={importing} onClose={() => setImporting(false)} />
    </div>
  )
}

export function Footer({ showAssistant = true }: { showAssistant?: boolean }) {
  return (
    <footer className="app-footer">
      <span>OrbitVitals supports the crew and the medical team · Not a medical device: no diagnosis or clinical advice</span>
      {/* The assistant is an add-on, kept to the side on purpose. */}
      {showAssistant && (
        <a className="assistant-bubble" href={href.assistant()} aria-label="Assistant">
          <BubbleIcon size={28} />
          <span className="assistant-tip">Assistant</span>
        </a>
      )}
    </footer>
  )
}

/** Always visible while demo mode is on, so sample scenarios are never mistaken for real data. */
function DemoBadge() {
  const { demo } = useAppState()
  return demo ? (
    <span className="demo-badge" title="Demo mode: built-in scenarios on sample data, the server is not used">
      Demo
    </span>
  ) : null
}
