import { config } from '../config'
import type { DataSource } from './DataSource'
import { BackendDataSource } from './backend/BackendDataSource'
import { fixedClock, replayClock } from './mock/clock'
import { MockDataSource } from './mock/MockDataSource'

export interface MockOptions {
  /** Live replay: the simulated clock advances in real time from 10:30 UTC (mock only). */
  replay: boolean
}

/** Chooses the data adapter from the build configuration (see src/config.ts). */
export function createDataSource(scenarioId: string, mock: MockOptions = { replay: false }): DataSource {
  if (config.dataSource === 'http') return new BackendDataSource(config.apiBaseUrl, config.backendCrew, { asOf: config.asOf, missionStart: config.missionStart })
  return new MockDataSource(scenarioId, undefined, mock.replay ? replayClock(Date.now()) : fixedClock)
}

export type { DataSource } from './DataSource'
export { CREW_MESSAGE_TEMPLATES, DataSourceError } from './DataSource'
export { SCENARIOS, DEFAULT_SCENARIO_ID } from './mock/scenarios'
