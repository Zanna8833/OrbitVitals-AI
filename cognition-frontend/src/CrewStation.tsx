import { useRef, useState } from 'react'
import type { JSX } from 'react'
import { seedFromText } from './random'
import { TEST_INSTRUCTIONS, TEST_NAMES, TEST_ORDER } from './types'
import type { Session, TestCode, TestProps, TestResult } from './types'
import MotorPraxis from './tests/MotorPraxis'
import VisualObjectLearning from './tests/VisualObjectLearning'
import FractalTwoBack from './tests/FractalTwoBack'
import AbstractMatching from './tests/AbstractMatching'
import LineOrientation from './tests/LineOrientation'
import EmotionRecognition from './tests/EmotionRecognition'
import MatrixReasoning from './tests/MatrixReasoning'
import DigitSymbol from './tests/DigitSymbol'
import BalloonRisk from './tests/BalloonRisk'
import Vigilance from './tests/Vigilance'

const TEST_COMPONENTS: Record<TestCode, (props: TestProps) => JSX.Element> = {
  MPT: MotorPraxis,
  VOLT: VisualObjectLearning,
  F2B: FractalTwoBack,
  AM: AbstractMatching,
  LOT: LineOrientation,
  ERT: EmotionRecognition,
  MRT: MatrixReasoning,
  DSST: DigitSymbol,
  BART: BalloonRisk,
  PVT: Vigilance,
}

// Short survey before the battery (the real one asks about sleep, stimulants and alertness on 11-point scales;
// the exact items were not in the sources read, these are examples)
const SURVEY_SCALES = [
  { key: 'sleep_quality', label: 'How well did you sleep last night?', low: 'Very poorly', high: 'Very well' },
  { key: 'tiredness', label: 'How tired are you right now?', low: 'Not at all', high: 'Extremely' },
  { key: 'mental_fatigue', label: 'How mentally fatigued are you?', low: 'Not at all', high: 'Extremely' },
  { key: 'stress', label: 'How stressed are you?', low: 'Not at all', high: 'Extremely' },
  { key: 'workload', label: 'How high was your workload today?', low: 'Very low', high: 'Very high' },
]

// The battery runs full screen, like on the station laptop (needs a click: browsers allow it only after one)
function enterFullScreen() {
  if (document.fullscreenElement === null && document.documentElement.requestFullscreen !== undefined) {
    document.documentElement.requestFullscreen().catch(function () {})
  }
}

function exitFullScreen() {
  if (document.fullscreenElement !== null) {
    document.exitFullscreen().catch(function () {})
  }
}

type Step = 'setup' | 'survey' | 'instructions' | 'running' | 'between' | 'done'

function downloadSession(session: Session) {
  const text = JSON.stringify(session, null, 2)
  const link = document.createElement('a')
  link.href = URL.createObjectURL(new Blob([text], { type: 'application/json' }))
  link.download = 'session_' + session.astronaut_id + '_day' + session.mission_day + '.json'
  link.click()
  URL.revokeObjectURL(link.href)
}

export default function CrewStation(props: { onExit: () => void }) {
  const [step, setStep] = useState<Step>('setup')
  const [astronautId, setAstronautId] = useState('A1')
  const [missionDay, setMissionDay] = useState(30)
  const [selected, setSelected] = useState<TestCode[]>(TEST_ORDER)
  const [hoursSlept, setHoursSlept] = useState(7)
  const [scales, setScales] = useState<Record<string, number>>({})
  const [position, setPosition] = useState(0)
  const session = useRef<Session | null>(null)

  function toggleTest(code: TestCode) {
    const next: TestCode[] = []
    for (const test of TEST_ORDER) {
      const isSelected = selected.indexOf(test) !== -1
      if (test === code) {
        if (!isSelected) next.push(test)
      } else if (isSelected) {
        next.push(test)
      }
    }
    setSelected(next)
  }

  function startSurvey() {
    session.current = {
      astronaut_id: astronautId.trim(),
      mission_day: missionDay,
      started_at: new Date().toISOString(),
      survey: {},
      tests: {},
    }
    setStep('survey')
  }

  function startBattery() {
    if (session.current === null) return
    const survey: Record<string, number> = { hours_slept: hoursSlept }
    for (const scale of SURVEY_SCALES) {
      let value = 5
      if (scales[scale.key] !== undefined) value = scales[scale.key]
      survey[scale.key] = value
    }
    session.current.survey = survey
    enterFullScreen()
    setPosition(0)
    setStep('instructions')
  }

  function testFinished(result: TestResult) {
    if (session.current === null) return
    session.current.tests[selected[position]] = result
    if (position + 1 === selected.length) {
      exitFullScreen()
      setStep('done')
    } else {
      setStep('between')
    }
  }

  if (step === 'setup') {
    const checkboxes = []
    for (const code of TEST_ORDER) {
      checkboxes.push(
        <label key={code} className="test-check">
          <input type="checkbox" checked={selected.indexOf(code) !== -1} onChange={function () { toggleTest(code) }} />
          <span>{TEST_NAMES[code]}</span>
        </label>,
      )
    }
    return (
      <div className="screen center">
        <div className="panel">
          <div className="form-row">
            <label>Crew member<input value={astronautId} onChange={function (e) { setAstronautId(e.target.value) }} /></label>
            <label>Mission day (before launch: negative)
              <input type="number" value={missionDay} onChange={function (e) { setMissionDay(Number(e.target.value)) }} />
            </label>
          </div>
          <div className="test-list">{checkboxes}</div>
          <div className="actions">
            <button className="button" onClick={props.onExit}>Back</button>
            <button className="button primary" disabled={selected.length === 0 || astronautId.trim() === ''} onClick={startSurvey}>Continue</button>
          </div>
        </div>
      </div>
    )
  }

  if (step === 'survey') {
    const rows = []
    for (const scale of SURVEY_SCALES) {
      let value = 5
      if (scales[scale.key] !== undefined) value = scales[scale.key]
      rows.push(
        <div key={scale.key} className="survey-row">
          <div className="survey-label">{scale.label}</div>
          <div className="survey-scale">
            <span>{scale.low}</span>
            <input type="range" min={0} max={10} value={value}
              onChange={function (e) { setScales({ ...scales, [scale.key]: Number(e.target.value) }) }} />
            <span>{scale.high}</span>
            <b>{value}</b>
          </div>
        </div>,
      )
    }
    return (
      <div className="screen center">
        <div className="panel">
          <div className="survey-row">
            <div className="survey-label">Hours slept last night</div>
            <input type="number" min={0} max={16} step={0.5} value={hoursSlept}
              onChange={function (e) { setHoursSlept(Number(e.target.value)) }} />
          </div>
          {rows}
          <div className="actions">
            <button className="button primary" onClick={startBattery}>Start</button>
          </div>
        </div>
      </div>
    )
  }

  const code = selected[position]

  if (step === 'instructions') {
    const lines = []
    for (const line of TEST_INSTRUCTIONS[code]) {
      lines.push(<p key={line}>{line}</p>)
    }
    return (
      <div className="screen center">
        <div className="instructions">
          <div className="muted">{position + 1} / {selected.length}</div>
          <h2>{TEST_NAMES[code]}</h2>
          {lines}
          <button className="button primary" onClick={function () { setStep('running') }}>Begin</button>
        </div>
      </div>
    )
  }

  if (step === 'running') {
    const Test = TEST_COMPONENTS[code]
    // A new seed for each crew member, mission day and test: a new stimulus set each session
    const seed = seedFromText(astronautId + '|' + missionDay + '|' + code)
    return (
      <div className="screen test-screen">
        <Test key={code} seed={seed} onFinish={testFinished} />
      </div>
    )
  }

  if (step === 'between') {
    return (
      <div className="screen center">
        <div className="instructions">
          <h2>Test complete</h2>
          <button className="button primary" onClick={function () { setPosition(position + 1); setStep('instructions') }}>Continue</button>
        </div>
      </div>
    )
  }

  return (
    <div className="screen center">
      <div className="instructions">
        <h2>Session complete</h2>
        <p className="muted">Results go to the ground research team.</p>
        <button className="button primary" onClick={function () { if (session.current !== null) downloadSession(session.current) }}>
          Send to ground
        </button>
        <button className="button" onClick={props.onExit}>Close</button>
      </div>
    </div>
  )
}
