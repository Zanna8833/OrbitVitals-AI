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

export const config = {
  /** mock (default): deterministic synthetic data · http: backend described in docs/API_CONTRACT.md */
  dataSource: import.meta.env.VITE_DATA_SOURCE === 'http' ? ('http' as const) : ('mock' as const),
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL ?? '/api/v1',
  /** Seconds between automatic reloads of the data; 0 = off. */
  refreshIntervalS: parseRefreshIntervalS(import.meta.env.VITE_REFRESH_INTERVAL_S),
}
