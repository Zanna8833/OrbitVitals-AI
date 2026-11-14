import { Empty } from './components/Common'
import { Footer, NavBar } from './components/NavBar'
import type { DataSource } from './data'
import { useQuery } from './hooks/useQuery'
import { href, useRoute } from './hooks/useRoute'
import { AppStateProvider } from './state/AppState'
import { CrewToday } from './views/crew/CrewToday'
import { MedicalView } from './views/medical/MedicalView'

const loadMissionStatus = (ds: DataSource) => ds.getMissionStatus()

function Shell() {
  const route = useRoute()
  const mission = useQuery(loadMissionStatus)

  return (
    <div className={`app app-${route.view}`}>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <NavBar route={route} mission={mission.data} missionStale={mission.status === 'error'} />
      <main id="main" tabIndex={-1}>
        {route.view === 'crew' && <CrewToday crewId={route.crewId} page={route.page} />}
        {route.view === 'medical' && <MedicalView selection={route.selection} />}
        {route.view === 'not_found' && (
          <div className="page page-narrow">
            <Empty>
              Page not found. <a href={href.crew()}>Go to Today</a>
            </Empty>
          </div>
        )}
      </main>
      <Footer />
    </div>
  )
}

export default function App() {
  return (
    <AppStateProvider>
      <Shell />
    </AppStateProvider>
  )
}
