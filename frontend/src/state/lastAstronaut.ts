import type { CrewPage } from '../hooks/useRoute'

/**
 * The astronaut (and page) last opened, so "Crew" in the bar, the logo and
 * "back" from the assistant return there instead of the crew overview.
 */
const KEY = 'orbitvitals:last-astronaut'

export interface LastPlace {
  crewId: string
  page: CrewPage
}

let memory: LastPlace | null = null

export function rememberAstronaut(crewId: string, page: CrewPage) {
  memory = { crewId, page: page === 'crew' ? 'home' : page }
  try {
    window.sessionStorage.setItem(KEY, JSON.stringify(memory))
  } catch {
    /* session storage unavailable: memory only */
  }
}

export function lastAstronaut(): LastPlace | null {
  if (memory) return memory
  try {
    const raw = window.sessionStorage.getItem(KEY)
    memory = raw ? (JSON.parse(raw) as LastPlace) : null
  } catch {
    memory = null
  }
  return memory
}
