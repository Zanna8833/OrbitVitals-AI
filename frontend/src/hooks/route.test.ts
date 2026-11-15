import { describe, expect, it } from 'vitest'
import { href, parseRoute } from './useRoute'

describe('parseRoute', () => {
  it('parses the two areas', () => {
    expect(parseRoute('')).toEqual({ view: 'crew', crewId: 'crew-a', page: 'home' })
    expect(parseRoute('#/crew')).toEqual({ view: 'crew', crewId: null, page: 'home' })
    expect(parseRoute(href.crew('crew-b'))).toEqual({ view: 'crew', crewId: 'crew-b', page: 'home' })
    expect(parseRoute(href.crew('crew-b', 'health'))).toEqual({ view: 'crew', crewId: 'crew-b', page: 'health' })
    expect(parseRoute(href.crew('crew-b', 'sleep'))).toEqual({ view: 'crew', crewId: 'crew-b', page: 'sleep' })
    expect(parseRoute(href.medicalSleep())).toEqual({ view: 'medical', selection: { type: 'sleep' } })
    expect(parseRoute(href.medical())).toEqual({ view: 'medical', selection: null })
    expect(parseRoute(href.event('EV-0142'))).toEqual({ view: 'medical', selection: { type: 'event', id: 'EV-0142' } })
    expect(parseRoute(href.medicalCrew('crew-c'))).toEqual({ view: 'medical', selection: { type: 'crew', id: 'crew-c' } })
    expect(parseRoute(href.assistant())).toEqual({ view: 'assistant' })
    expect(parseRoute('#/xyz').view).toBe('not_found')
  })

  it('keeps older links working', () => {
    expect(parseRoute('#/crew/crew-a/health')).toEqual({ view: 'crew', crewId: 'crew-a', page: 'health' })
    expect(parseRoute('#/crew/crew-a/measurements')).toEqual({ view: 'crew', crewId: 'crew-a', page: 'home' })
    expect(parseRoute('#/surgeon')).toEqual({ view: 'medical', selection: null })
    expect(parseRoute('#/surgeon/crew-b')).toEqual({ view: 'medical', selection: { type: 'crew', id: 'crew-b' } })
    expect(parseRoute('#/events/EV-0142')).toEqual({ view: 'medical', selection: { type: 'event', id: 'EV-0142' } })
  })
})
