import { useEffect, useState } from 'react'

/**
 * Two places only:
 * - Crew → one "Today" screen for the astronaut (tasks open as sheets);
 * - Medical → one split view for the Flight Surgeon (list + detail).
 * Older links (#/surgeon, #/events/:id, #/crew/:id/health|now|measurements)
 * are still understood, so bookmarks and docs keep working.
 */
export type CrewPage = 'home' | 'health' | 'sleep'

export type Route =
  | { view: 'crew'; crewId: string | null; page: CrewPage }
  | { view: 'medical'; selection: MedicalSelection }
  | { view: 'assistant' }
  | { view: 'not_found'; path: string }

export type MedicalSelection = { type: 'event'; id: string } | { type: 'crew'; id: string } | { type: 'sleep' } | null

export function parseRoute(hash: string): Route {
  const path = hash.replace(/^#/, '') || '/crew/crew-a'
  const parts = path.split('/').filter(Boolean).map(decodeURIComponent)
  const [area, a, b] = parts
  // 'health' was the former "My health" tab: it now means the Health page. Other old tabs open the home.
  if (area === 'crew') return { view: 'crew', crewId: a ?? null, page: b === 'health' || b === 'sleep' ? b : 'home' }
  if (area === 'medical') {
    if (a === 'event' && b) return { view: 'medical', selection: { type: 'event', id: b } }
    if (a === 'crew' && b) return { view: 'medical', selection: { type: 'crew', id: b } }
    if (a === 'sleep') return { view: 'medical', selection: { type: 'sleep' } }
    return { view: 'medical', selection: null }
  }
  if (area === 'assistant') return { view: 'assistant' }
  // Legacy routes.
  if (area === 'surgeon') return { view: 'medical', selection: a ? { type: 'crew', id: a } : null }
  if (area === 'events' && a) return { view: 'medical', selection: { type: 'event', id: a } }
  return { view: 'not_found', path }
}

export const href = {
  crew: (crewId?: string, page: CrewPage = 'home') =>
    `#/crew${crewId ? `/${encodeURIComponent(crewId)}${page === 'home' ? '' : `/${page}`}` : ''}`,
  medical: () => '#/medical',
  event: (eventId: string) => `#/medical/event/${encodeURIComponent(eventId)}`,
  medicalCrew: (crewId: string) => `#/medical/crew/${encodeURIComponent(crewId)}`,
  medicalSleep: () => '#/medical/sleep',
  assistant: () => '#/assistant',
  /** Kept for older call sites. */
  surgeon: (crewId?: string) => (crewId ? `#/medical/crew/${encodeURIComponent(crewId)}` : '#/medical'),
}

export function useRoute(): Route {
  const [route, setRoute] = useState(() => parseRoute(window.location.hash))
  useEffect(() => {
    const onChange = () => setRoute(parseRoute(window.location.hash))
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])
  return route
}
