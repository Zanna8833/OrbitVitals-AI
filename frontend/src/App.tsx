import { useEffect } from 'react'
import { lastAstronaut } from './state/lastAstronaut'
import { Empty } from './components/Common'
import { Footer, NavBar } from './components/NavBar'
import type { DataSource } from './data'
import { useQuery } from './hooks/useQuery'
import { href, useRoute } from './hooks/useRoute'
import { AppStateProvider } from './state/AppState'
import { CrewToday } from './views/crew/CrewToday'
import { MedicalView } from './views/medical/MedicalView'
import { AssistantPage } from './views/assistant/AssistantPage'
import { CognitionPage } from './views/cognition/CognitionPage'
import { ToastProvider } from './components/Toast'

const loadMissionStatus = (ds: DataSource) => ds.getMissionStatus()

function Shell() {
  // Opening the app without a link resumes the astronaut used last in this session.
  useEffect(() => {
    if (!window.location.hash && lastAstronaut()) window.location.replace(href.crewHome())
  }, [])
  const route = useRoute()
  const mission = useQuery(loadMissionStatus)
  // The cognition battery runs full screen, like on the station laptop.
  if (route.view === 'cognition') return <CognitionPage />

  return (
    <div className={`app app-${route.view}`}>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <NavBar route={route} mission={mission.data} missionStale={mission.status === 'error'} />
      {/* key: each place fades in when you arrive, without moving the layout */}
      <main id="main" tabIndex={-1} key={route.view === 'crew' ? `crew-${route.page}` : route.view} className="route-enter">
        {route.view === 'crew' && <CrewToday crewId={route.crewId} page={route.page} />}
        {route.view === 'medical' && <MedicalView selection={route.selection} />}
        {route.view === 'assistant' && <AssistantPage />}
        {route.view === 'not_found' && (
          <div className="page page-narrow">
            <Empty>
              Page not found. <a href={href.crewHome()}>Go to the crew</a>
            </Empty>
          </div>
        )}
      </main>
      <Footer showAssistant={route.view !== 'assistant'} />
    </div>
  )
}

export default function App() {
  return (
    <AppStateProvider>
      <ToastProvider>
        <Shell />
      </ToastProvider>
    </AppStateProvider>
  )
}
