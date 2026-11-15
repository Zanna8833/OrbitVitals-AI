import { href, type CrewPage } from '../hooks/useRoute'
import { initialsOf } from '../domain/overview'

/**
 * Crew-level and per-astronaut views, side by side: "Crew" shows everyone,
 * each name opens that astronaut's own area (on the same page type).
 */
export function AstronautSwitch({ crew, current, page = 'home' }: { crew: { id: string; displayName: string }[]; current: string | null; page?: CrewPage }) {
  const target: CrewPage = page === 'crew' ? 'home' : page
  return (
    <nav className="astronaut-switch" aria-label="Crew and astronauts">
      <a href={href.crew()} className="astro-chip astro-crew" aria-current={current === null ? 'page' : undefined}>
        <svg width="15" height="15" viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="8" cy="9" r="3" fill="currentColor" />
          <circle cx="16" cy="9" r="3" fill="currentColor" opacity="0.6" />
          <path d="M2.5 19c.6-3.2 2.8-5 5.5-5s4.9 1.8 5.5 5M11 19c.5-2.6 2.4-4.4 5-4.4s4.5 1.8 5 4.4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
        </svg>
        Crew
      </a>
      {crew.map((c) => (
        <a key={c.id} href={href.crew(c.id, target)} className="astro-chip" aria-current={current === c.id ? 'page' : undefined}>
          <span className="avatar avatar-tiny" aria-hidden="true">
            {initialsOf(c.displayName)}
          </span>
          {c.displayName}
        </a>
      ))}
    </nav>
  )
}
