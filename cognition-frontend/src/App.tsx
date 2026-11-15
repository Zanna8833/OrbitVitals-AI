import { useState } from 'react'
import CrewStation from './CrewStation'
import GroundView from './GroundView'

type View = 'home' | 'crew' | 'ground'

export default function App() {
  const [view, setView] = useState<View>('home')

  function goHome() {
    setView('home')
  }

  if (view === 'crew') {
    return <CrewStation onExit={goHome} />
  }
  if (view === 'ground') {
    return <GroundView onExit={goHome} />
  }
  return (
    <div className="screen center">
      <h1 className="home-title">Cognition</h1>
      <div className="home-choices">
        <button className="button primary" onClick={function () { setView('crew') }}>Crew station</button>
        <button className="button" onClick={function () { setView('ground') }}>Ground research</button>
      </div>
    </div>
  )
}
