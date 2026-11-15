/**
 * Build-time configuration, read once from Vite env variables (see .env.example).
 */

export const DEFAULT_REFRESH_INTERVAL_S = 10

/** Parses VITE_REFRESH_INTERVAL_S: a whole number of seconds; 0 disables auto-refresh; anything invalid falls back to the default. */
export function parseRefreshIntervalS(raw: string | undefined): number {
  if (raw === undefined || raw.trim() === '') return DEFAULT_REFRESH_INTERVAL_S
  const n = Number(raw)
  return Number.isInteger(n) && n >= 0 ? n : DEFAULT_REFRESH_INTERVAL_S
}

export interface BackendCrew {
  /** Id used inside the interface (crew-a, crew-b, crew-c). */
  id: string
  /** crew_member_id on the backend. */
  backendId: string
  displayName: string
}

/** Default: the three crew members created by the backend seeder (python -m app.demo_seed seed). */
export const DEFAULT_BACKEND_CREW = 'crew-a=sim-mission-v1-01:Astronaut A,crew-b=sim-mission-v1-02:Astronaut B,crew-c=sim-mission-v1-03:Astronaut C'

/** "crew-a=backend-id:Name,…" → mapping. Invalid parts are ignored. */
export function parseBackendCrew(raw: string | undefined): BackendCrew[] {
  return (raw?.trim() ? raw : DEFAULT_BACKEND_CREW)
    .split(',')
    .map((part) => part.trim().match(/^([\w-]+)=([^:]+)(?::(.+))?$/))
    .filter((m): m is RegExpMatchArray => !!m)
    .map((m) => ({ id: m[1], backendId: m[2].trim(), displayName: (m[3] ?? m[2]).trim() }))
}

export const config = {
  /** mock (default): deterministic synthetic data · http: the team's FastAPI backend (backend/, /api/v1) */
  /** http (default): the OrbitVitals server. mock: generated sample data for offline development and tests only. */
  dataSource: import.meta.env.VITE_DATA_SOURCE === 'mock' ? ('mock' as const) : ('http' as const),
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL ?? '/api/v1',
  /** Seconds between automatic reloads of the data; 0 = off. */
  refreshIntervalS: parseRefreshIntervalS(import.meta.env.VITE_REFRESH_INTERVAL_S),
  /** Which backend crew members appear as crew-a/b/c (http mode). */
  backendCrew: parseBackendCrew(import.meta.env.VITE_BACKEND_CREW),
  /** The team's assistant service (ai_agent/, /agent/v1). */
  agentBaseUrl: (import.meta.env.VITE_AGENT_BASE_URL as string | undefined) ?? '/agent/v1',
  /** Optional "now" for http mode (ISO). Default: the day of the latest stored measurement. */
  asOf: import.meta.env.VITE_AS_OF as string | undefined,
  /** The team's cognition battery (cognition-frontend), built next to this app by `npm run cognition`. */
  cognitionUrl: (import.meta.env.VITE_COGNITION_URL as string | undefined) ?? './cognition/index.html',
  /** Optional mission day 1 (YYYY-MM-DD) for http mode. Default: the day of the earliest stored measurement. */
  missionStart: import.meta.env.VITE_MISSION_START as string | undefined,
}
