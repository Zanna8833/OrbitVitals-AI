import { lastAstronaut } from '../state/lastAstronaut'
import { useEffect, useState } from 'react'

/**
 * Two places only:
 * - Crew → one "Today" screen for the astronaut (tasks open as sheets);
 * - Medical → one split view for the Flight Surgeon (list + detail).
 * Older links (#/surgeon, #/events/:id, #/crew/:id/health|now|measurements)
 * are still understood, so bookmarks and docs keep working.
 */
export type CrewPage = 'home' | 'health' | 'sleep' | 'nutrition' | 'crew'

export type Route =
  | { view: 'crew'; crewId: string | null; page: CrewPage }
  | { view: 'medical'; selection: MedicalSelection }
  | { view: 'assistant' }
  | { view: 'cognition' }
  | { view: 'not_found'; path: string }

export type MedicalSelection = { type: 'event'; id: string } | { type: 'crew'; id: string; metric?: string | null; tab?: string | null } | { type: 'sleep' } | null

export function parseRoute(hash: string): Route {
  const path = hash.replace(/^#/, '') || '/crew'
  // A query (?tab=…) belongs to the page, not to the route.
  const parts = path.split('?')[0].split('/').filter(Boolean).map(decodeURIComponent)
  const [area, a, b] = parts
  // 'health' was the former "My health" tab: it now means the Health page. Other old tabs open the home.
  if (area === 'crew') return { view: 'crew', crewId: a ?? null, page: !a ? 'crew' : b === 'health' || b === 'sleep' || b === 'nutrition' ? b : 'home' }
  if (area === 'medical') {
    if (a === 'event' && b) return { view: 'medical', selection: { type: 'event', id: b } }
    if (a === 'crew' && b) return { view: 'medical', selection: { type: 'crew', id: b, metric: parts[3] ?? null, tab: new URLSearchParams(path.split('?')[1] ?? '').get('tab') } }
    if (a === 'sleep') return { view: 'medical', selection: { type: 'sleep' } }
    return { view: 'medical', selection: null }
  }
  if (area === 'assistant') return { view: 'assistant' }
  if (area === 'cognition') return { view: 'cognition' }
  // Legacy routes.
  if (area === 'surgeon') return { view: 'medical', selection: a ? { type: 'crew', id: a } : null }
  if (area === 'events' && a) return { view: 'medical', selection: { type: 'event', id: a } }
  return { view: 'not_found', path }
}

export const href = {
  crew: (crewId?: string, page: CrewPage = 'home') =>
    `#/crew${crewId ? `/${encodeURIComponent(crewId)}${page === 'home' ? '' : `/${page}`}` : ''}`,
  /** The crew area as the user left it: the last astronaut and page, else the crew overview. */
  crewHome: () => {
    const last = lastAstronaut()
    return href.crew(last?.crewId ?? 'crew-a', last?.page ?? 'home')
  },
  medical: () => '#/medical',
  event: (eventId: string) => `#/medical/event/${encodeURIComponent(eventId)}`,
  medicalCrew: (crewId: string, metric?: string) => `#/medical/crew/${encodeURIComponent(crewId)}${metric ? `/${encodeURIComponent(metric)}` : ''}`,
  medicalSleep: () => '#/medical/sleep',
  assistant: () => '#/assistant',
  cognition: () => '#/cognition',
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
