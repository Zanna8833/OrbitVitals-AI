/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_DATA_SOURCE?: 'mock' | 'http'
  readonly VITE_API_BASE_URL?: string
  /** Seconds between automatic data reloads; "0" disables auto-refresh. Default 10. */
  readonly VITE_REFRESH_INTERVAL_S?: string
}
