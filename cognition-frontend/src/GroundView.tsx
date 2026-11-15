import { useState } from 'react'
import type { ChangeEvent } from 'react'
import { TEST_NAMES, TEST_ORDER } from './types'
import type { TestCode } from './types'

// Reads the registry written by cognition.py: registry[astronaut_id][mission_day] = session report.
// Only the ground team sees these numbers.

type Summary = { speed: number | null; accuracy: number | null; efficiency: number | null }
type Report = {
  astronaut_id: string
  mission_day: number
  survey: Record<string, number>
  tests: Partial<Record<TestCode, { name: string; metrics: Record<string, number | null>; z: Record<string, number> }>>
  summary: Summary
  change_from_preflight: Summary | null
  low_scores: string[]
}
type Registry = Record<string, Record<string, Report>>

// Dev et al. 2024: z <= -1.5 counts as a low score
const LOW_Z = -1.5

function zClass(z: number | undefined | null): string {
  if (z === undefined || z === null) return 'z-empty'
  if (z <= LOW_Z) return 'z-low'
  if (z <= -0.5) return 'z-watch'
  if (z >= 0.5) return 'z-good'
  return 'z-normal'
}

function formatZ(z: number | undefined | null): string {
  if (z === undefined || z === null) return '–'
  let text = z.toFixed(2)
  if (z > 0) text = '+' + text
  return text
}

function phaseName(day: number): string {
  if (day < 0) return 'Pre-flight L' + day
  return 'Mission day ' + day
}

function sortedDays(reports: Record<string, Report>): number[] {
  const days: number[] = []
  for (const day in reports) {
    days.push(Number(day))
  }
  days.sort(function (a, b) { return a - b })
  return days
}

function SummaryChart(props: { reports: Record<string, Report>; days: number[] }) {
  const width = 760
  const height = 260
  const left = 48
  const right = 16
  const top = 16
  const bottom = 36
  const minZ = -3
  const maxZ = 2
  function x(i: number): number {
    if (props.days.length === 1) return (left + width - right) / 2
    return left + (i * (width - left - right)) / (props.days.length - 1)
  }
  function y(z: number): number {
    const clipped = Math.max(minZ, Math.min(maxZ, z))
    return top + ((maxZ - clipped) * (height - top - bottom)) / (maxZ - minZ)
  }
  const series: { key: keyof Summary; colour: string; label: string }[] = [
    { key: 'speed', colour: '#f2f2f2', label: 'Speed' },
    { key: 'accuracy', colour: '#8a8a8a', label: 'Accuracy' },
    { key: 'efficiency', colour: '#c9a227', label: 'Efficiency' },
  ]
  const elements = []
  for (let z = minZ; z <= maxZ; z++) {
    elements.push(<line key={'g' + z} x1={left} x2={width - right} y1={y(z)} y2={y(z)} stroke="#2a2a2a" />)
    elements.push(<text key={'gt' + z} x={left - 8} y={y(z) + 4} textAnchor="end" className="chart-axis">{z}</text>)
  }
  elements.push(<line key="low" x1={left} x2={width - right} y1={y(LOW_Z)} y2={y(LOW_Z)} stroke="#e5484d" strokeDasharray="6 4" />)
  elements.push(<text key="lowt" x={width - right} y={y(LOW_Z) - 6} textAnchor="end" className="chart-low">low score z ≤ −1.5</text>)
  for (let i = 0; i < props.days.length; i++) {
    elements.push(<text key={'d' + i} x={x(i)} y={height - 12} textAnchor="middle" className="chart-axis">{props.days[i]}</text>)
  }
  for (const line of series) {
    const points: string[] = []
    for (let i = 0; i < props.days.length; i++) {
      const value = props.reports[props.days[i]].summary[line.key]
      if (value !== null) {
        points.push(x(i) + ',' + y(value))
        elements.push(<circle key={line.key + i} cx={x(i)} cy={y(value)} r={4} fill={line.colour} />)
      }
    }
    elements.push(<polyline key={line.key} points={points.join(' ')} fill="none" stroke={line.colour} strokeWidth={2.5} />)
  }
  const legend = []
  for (const line of series) {
    legend.push(<span key={line.key}><i style={{ background: line.colour }} />{line.label}</span>)
  }
  return (
    <div className="card">
      <h3>Summary scores (z vs astronaut pre-flight norms) by mission day</h3>
      <svg viewBox={'0 0 ' + width + ' ' + height} className="chart">{elements}</svg>
      <div className="legend">{legend}</div>
    </div>
  )
}

export default function GroundView(props: { onExit: () => void }) {
  const [registry, setRegistry] = useState<Registry | null>(null)
  const [astronaut, setAstronaut] = useState('')
  const [error, setError] = useState('')

  function loadFile(event: ChangeEvent<HTMLInputElement>) {
    const files = event.target.files
    if (files === null || files.length === 0) return
    files[0].text().then(function (text) {
      try {
        const loaded = JSON.parse(text) as Registry
        setRegistry(loaded)
        setAstronaut(Object.keys(loaded)[0])
        setError('')
      } catch {
        setError('This file is not a cognition registry (JSON).')
      }
    })
  }

  const loader = (
    <div className="card">
      <h3>Load results</h3>
      <p className="muted">
        Score the crew session files with <code>python -m app.domains.cognition.cognition session_*.json --registry cognition_registry.json</code> (from <code>backend/</code>),
        then open <code>cognition_registry.json</code> here.
      </p>
      <input type="file" accept=".json,application/json" onChange={loadFile} />
      {error !== '' ? <p className="error">{error}</p> : null}
    </div>
  )

  if (registry === null || registry[astronaut] === undefined) {
    return (
      <div className="ground-page">
        <div className="ground">
          <div className="ground-head"><button className="button" onClick={props.onExit}>Back</button></div>
          {loader}
        </div>
      </div>
    )
  }

  const reports = registry[astronaut]
  const days = sortedDays(reports)

  const astronautTabs = []
  for (const id in registry) {
    astronautTabs.push(
      <button key={id} className={id === astronaut ? 'tab active' : 'tab'} onClick={function () { setAstronaut(id) }}>{id}</button>,
    )
  }

  // Heat map: one row per test metric, one column per session
  const headerCells = [<th key="h">Test · metric</th>]
  for (const day of days) {
    headerCells.push(<th key={day}>{day}</th>)
  }
  const rows = []
  for (const code of TEST_ORDER) {
    for (const metric of ['speed', 'accuracy', 'risk']) {
      let present = false
      for (const day of days) {
        const test = reports[day].tests[code]
        if (test !== undefined && test.z[metric] !== undefined) present = true
      }
      if (!present) continue
      const cells = [<td key="n" className="metric-name">{TEST_NAMES[code]} · {metric}</td>]
      for (const day of days) {
        const test = reports[day].tests[code]
        let z: number | undefined = undefined
        if (test !== undefined) z = test.z[metric]
        cells.push(<td key={day} className={'z-cell ' + zClass(z)}>{formatZ(z)}</td>)
      }
      rows.push(<tr key={code + metric}>{cells}</tr>)
    }
  }

  const sessions = []
  for (const day of days) {
    const report = reports[day]
    let change = '–'
    if (report.change_from_preflight !== null) {
      change = 'speed ' + formatZ(report.change_from_preflight.speed) + ', accuracy ' + formatZ(report.change_from_preflight.accuracy)
    }
    let low = 'none'
    if (report.low_scores.length > 0) low = report.low_scores.join(', ')
    let sleep = '–'
    if (report.survey.hours_slept !== undefined) sleep = report.survey.hours_slept + ' h'
    sessions.push(
      <tr key={day}>
        <td>{phaseName(day)}</td>
        <td>{sleep}</td>
        <td className={zClass(report.summary.speed)}>{formatZ(report.summary.speed)}</td>
        <td className={zClass(report.summary.accuracy)}>{formatZ(report.summary.accuracy)}</td>
        <td className={zClass(report.summary.efficiency)}>{formatZ(report.summary.efficiency)}</td>
        <td>{change}</td>
        <td className={report.low_scores.length > 0 ? 'low-text' : ''}>{low}</td>
      </tr>,
    )
  }

  return (
    <div className="ground-page">
    <div className="ground">
      <div className="ground-head">
        <button className="button" onClick={props.onExit}>Back</button>
        <div className="tabs">{astronautTabs}</div>
        <span className="muted">Ground team only: crew members do not see these scores.</span>
      </div>
      <SummaryChart reports={reports} days={days} />
      <div className="card">
        <h3>Sessions</h3>
        <div className="table-scroll">
        <table className="table">
          <thead>
            <tr><th>Session</th><th>Sleep</th><th>Speed</th><th>Accuracy</th><th>Efficiency</th><th>Change from own pre-flight</th><th>Low scores (z ≤ −1.5)</th></tr>
          </thead>
          <tbody>{sessions}</tbody>
        </table>
        </div>
      </div>
      <div className="card">
        <h3>Test z-scores by mission day</h3>
        <div className="table-scroll">
          <table className="table heat">
            <thead><tr>{headerCells}</tr></thead>
            <tbody>{rows}</tbody>
          </table>
        </div>
        <p className="muted">
          z against 25 NASA astronauts before 6-month ISS missions (Dev et al. 2024). Speed is flipped: higher z = faster.
          BART risk is risk taking, not accuracy. No correction for practice effects is applied.
        </p>
      </div>
      {loader}
    </div>
    </div>
  )
}
