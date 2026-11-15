import type { ReactNode } from 'react'
import type { MissionStatus } from '../domain/types'
import { formatAge, formatUtc } from '../domain/time'

/** Placeholder blocks in the shape of a page, instead of a bare "Loading…". */
export function Loading({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="skeleton" role="status" aria-label={label}>
      <span className="sk sk-title" />
      <div className="sk-grid">
        <span className="sk sk-card" />
        <span className="sk sk-card sk-wide" />
        <span className="sk sk-card" />
        <span className="sk sk-card sk-wide" />
      </div>
    </div>
  )
}

export function ErrorState({ error, title = 'Unable to load data' }: { error: Error; title?: string }) {
  return (
    <div className="notice notice-error" role="alert">
      <strong>{title}.</strong> {error.message}
    </div>
  )
}

/**
 * A refresh failed but earlier data is still on screen: say so explicitly,
 * so old data is never mistaken for current data.
 */
export function RefreshErrorNotice({ error }: { error: Error }) {
  return (
    <div className="notice notice-error" role="status">
      <strong>Could not refresh.</strong> {error.message} The data shown may be out of date.
    </div>
  )
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="state state-empty">{children}</p>
}

/** Shown only when the ground link is not connected. */
export function LinkBanner({ mission, audience }: { mission: MissionStatus; audience: 'surgeon' | 'crew' }) {
  if (mission.link.state === 'connected') return null
  const what = mission.link.state === 'offline' ? 'No ground link' : 'Limited ground link'
  return (
    <div className="notice notice-link" role="status">
      <strong>
        {what} since {formatUtc(mission.link.since, false)}
      </strong>{' '}
      <span className="muted">({formatAge(mission.link.since, mission.now)})</span>
      <span className="notice-text">
        {audience === 'surgeon'
          ? 'You are seeing the last data received, not the current state. Messages to the crew cannot be sent.'
          : 'Your readings stay on this device. Reports you share are queued and sent when the link returns.'}
      </span>
    </div>
  )
}

export function FormError({ message }: { message: string | null }) {
  if (!message) return null
  return (
    <p className="form-error" role="alert">
      {message}
    </p>
  )
}
