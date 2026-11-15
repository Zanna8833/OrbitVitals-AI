import { useCallback } from 'react'
import type { DataSource } from '../../data'
import type { MedicalSelection } from '../../hooks/useRoute'
import { href } from '../../hooks/useRoute'
import { useQuery } from '../../hooks/useQuery'
import { addDays } from '../../domain/sleepPlan'
import { formatClock, formatDate } from '../../domain/time'
import { ErrorState, Loading } from '../../components/Common'
import { EventPane } from './EventPane'
import { SleepPane, SLEEP_FUTURE, SLEEP_PAST } from './SleepPane'
import { MedicalAstronaut, MedicalCrew, MedicalHeader } from './MedicalWorkspace'

/**
 * The medical area mirrors the crew area: a crew view (everyone) and one view
 * per astronaut, switched from the header. Review items and the crew sleep
 * plan open in the same frame.
 */
export function MedicalView({ selection }: { selection: MedicalSelection }) {
  if (!selection) return <MedicalCrew />
  if (selection.type === 'crew') return <MedicalAstronaut key={`${selection.id}-${selection.metric ?? ''}-${selection.tab ?? ''}`} crewId={selection.id} metric={selection.metric ?? null} tab={selection.tab ?? null} />
  return <MedicalFrame selection={selection} />
}

async function loadFrame(ds: DataSource) {
  const [mission, crew] = await Promise.all([ds.getMissionStatus(), ds.listCrew()])
  const tonight = mission.now.slice(0, 10)
  const sleepPlan = await ds.listSleepAidPlan(addDays(tonight, -SLEEP_PAST), addDays(tonight, SLEEP_FUTURE - 1))
  return { mission, crew, sleepPlan }
}

function MedicalFrame({ selection }: { selection: Exclude<MedicalSelection, null | { type: 'crew' }> }) {
  const state = useQuery(useCallback((ds: DataSource) => loadFrame(ds), []))
  if (state.status === 'loading') return <Loading />
  if (!state.data) return <ErrorState error={state.error!} />
  const { mission, crew, sleepPlan } = state.data
  return (
    <div className="today medical-ws medical-frame">
      <MedicalHeader
        title={selection.type === 'sleep' ? 'Sleeping-pill plan' : 'Review'}
        eyebrow={`${formatDate(mission.now)} · ${formatClock(mission.now, false)} UTC`}
        mission={mission}
        crew={crew}
        current={null}
        back={{ href: href.medical(), label: 'Back' }}
      />
      <div className="ws-pane">
        {selection.type === 'event' && <EventPane key={selection.id} eventId={selection.id} />}
        {selection.type === 'sleep' && <SleepPane crew={crew} entries={sleepPlan} tonight={mission.now.slice(0, 10)} missionStart={mission.missionStartDate} />}
      </div>
    </div>
  )
}
