import { useEffect, useRef } from 'react'
import { createRoot, type Root } from 'react-dom/client'
// The team's cognition battery (cognition-frontend/), used as it is: not copied, not modified.
import CognitionApp from '../../../../cognition-frontend/src/App'
import cognitionCss from '../../../../cognition-frontend/src/index.css?inline'
import { config } from '../../config'
import { href } from '../../hooks/useRoute'
import { useCognitionAvailable } from '../../hooks/useCognition'
import { BackLink } from '../../components/BackLink'

/**
 * The cognition battery inside OrbitVitals, full screen.
 *
 * When the battery's own build is installed next to the app (npm run cognition,
 * included in npm run build) it is shown as is, with the face photographs of the
 * emotion test. Otherwise the same code runs embedded in an isolated shadow
 * DOM, so its styles cannot touch OrbitVitals; the emotion test then uses the
 * drawn faces the battery provides for that case.
 */
export function CognitionPage() {
  const built = useCognitionAvailable()
  return (
    <div className="cognition-page">
      {built === null ? null : built ? <iframe className="cognition-frame" src={config.cognitionUrl} title="Cognition battery" /> : <EmbeddedBattery />}
      <BackLink fallback={href.crewHome()} label="Back to OrbitVitals" className="cognition-close" />
    </div>
  )
}

function EmbeddedBattery() {
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
    root.render(<CognitionApp />)
    return () => {
      const r = root
      root = null
      // Unmount after the current render, as React requires.
      setTimeout(() => r?.unmount(), 0)
    }
  }, [])
  return <div ref={host} className="cognition-host" />
}
