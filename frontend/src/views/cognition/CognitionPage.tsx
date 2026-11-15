import { useEffect, useRef } from 'react'
import { createRoot, type Root } from 'react-dom/client'
// The team's cognition battery (cognition-frontend/), used as it is: not copied, not modified.
import CrewStation from '../../../../cognition-frontend/src/CrewStation'
import cognitionCss from '../../../../cognition-frontend/src/index.css?inline'
import { href } from '../../hooks/useRoute'

/** Leaves the battery: out of full screen, back to the astronaut's home page. */
function goHome() {
  if (document.fullscreenElement) document.exitFullscreen().catch(() => undefined)
  window.location.hash = href.crewHome()
}

/**
 * The cognition battery, full screen: straight to the test (crew member,
 * mission day, tests to run, short survey, then the tests). The Home button
 * stays on top at every step, during the tests too. The battery runs in an
 * isolated shadow DOM, so its styles cannot touch OrbitVitals.
 */
export function CognitionPage() {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      // Esc leaves full screen (browser); a second Esc goes home.
      if (e.key === 'Escape' && !document.fullscreenElement) goHome()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])
  return (
    <div className="cognition-page">
      <Battery />
      <button type="button" className="cognition-home" onClick={goHome} aria-label="Back to the OrbitVitals home page">
        <svg width="14" height="14" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M3.5 11 12 4l8.5 7M6 9.5V20h4.5v-5.5h3V20H18V9.5" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        Home
      </button>
    </div>
  )
}

function Battery() {
  const host = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const el = host.current
    if (!el) return
    const shadow = el.shadowRoot ?? el.attachShadow({ mode: 'open' })
    const style = document.createElement('style')
    // The battery's global rules (:root, html, body) are scoped to this host.
    style.textContent = cognitionCss.replace(/:root\b/g, ':host').replace(/html,\s*body,\s*#root/g, ':host, .cog-root')
    const mount = document.createElement('div')
    mount.className = 'cog-root'
    shadow.replaceChildren(style, mount)
    let root: Root | null = createRoot(mount)
    // "Back" on the first screen and "Close" at the end return to OrbitVitals.
    root.render(<CrewStation onExit={goHome} />)
    return () => {
      const r = root
      root = null
      setTimeout(() => r?.unmount(), 0)
    }
  }, [])
  return <div ref={host} className="cognition-host" />
}
