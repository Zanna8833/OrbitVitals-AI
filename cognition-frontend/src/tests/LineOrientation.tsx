import { useEffect, useMemo, useRef, useState } from 'react'
import { Random } from '../random'
import type { LineTrial, TestProps } from '../types'

// 12 self-paced trials: rotate the blue line in 2-degree steps with the arrows until it is parallel to the black
// reference line. Reference 6.06 cm long; test line 1.73, 3.46, 5.19 or 6.06 cm, centre 6.93 cm from the
// reference (NASA TM-2020-5008023). Lengths below are in units of 24 per cm.
const PAIR_COUNT = 12
const DEGREES_PER_CLICK = 2
const UNIT = 24
const REFERENCE_LENGTH = 6.06 * UNIT
const TEST_LENGTHS = [1.73 * UNIT, 3.46 * UNIT, 5.19 * UNIT, 6.06 * UNIT]
const CENTRE_DISTANCE = 6.93 * UNIT
const MAX_START_CLICKS = 40 // the starting angle of the test line is our choice

type Pair = { referenceAngle: number; startOffset: number; testLength: number; cx: number; cy: number; direction: number }

function clicksOff(offset: number): number {
  // Lines are parallel every 180 degrees
  let rest = ((offset % 180) + 180) % 180
  if (180 - rest < rest) {
    rest = 180 - rest
  }
  return Math.round(rest / DEGREES_PER_CLICK)
}

function lineEnds(cx: number, cy: number, angle: number, length: number) {
  const radians = (angle * Math.PI) / 180
  const dx = (Math.cos(radians) * length) / 2
  const dy = (Math.sin(radians) * length) / 2
  return { x1: cx - dx, y1: cy - dy, x2: cx + dx, y2: cy + dy }
}

export default function LineOrientation(props: TestProps) {
  const pairs = useMemo(function () {
    const random = new Random(props.seed)
    const list: Pair[] = []
    for (let i = 0; i < PAIR_COUNT; i++) {
      let clicks = random.int(5, MAX_START_CLICKS)
      if (random.next() < 0.5) {
        clicks = -clicks
      }
      list.push({
        referenceAngle: random.int(0, 179),
        startOffset: clicks * DEGREES_PER_CLICK,
        testLength: random.pick(TEST_LENGTHS),
        cx: random.int(-60, 60),
        cy: random.int(-30, 30),
        direction: random.int(0, 359),
      })
    }
    return list
  }, [props.seed])
  const [index, setIndex] = useState(0)
  const [offset, setOffset] = useState(pairs[0].startOffset)
  const trials = useRef<LineTrial[]>([])
  const shownAt = useRef(performance.now())

  function done() {
    trials.current.push({ rt_ms: Math.round(performance.now() - shownAt.current), clicks_off: clicksOff(offset) })
    if (index + 1 === PAIR_COUNT) {
      props.onFinish({ trials: trials.current })
      return
    }
    shownAt.current = performance.now()
    setOffset(pairs[index + 1].startOffset)
    setIndex(index + 1)
  }

  // Arrow keys also rotate the line
  useEffect(function () {
    function onKey(event: KeyboardEvent) {
      if (event.key === 'ArrowLeft') setOffset(offset - DEGREES_PER_CLICK)
      if (event.key === 'ArrowRight') setOffset(offset + DEGREES_PER_CLICK)
      if (event.key === 'Enter') done()
    }
    window.addEventListener('keydown', onKey)
    return function () {
      window.removeEventListener('keydown', onKey)
    }
  })

  const pair = pairs[index]
  // Reference and test line centres are a constant distance apart, in a random direction
  const radians = (pair.direction * Math.PI) / 180
  const referenceX = pair.cx - (Math.cos(radians) * CENTRE_DISTANCE) / 2
  const referenceY = pair.cy - (Math.sin(radians) * CENTRE_DISTANCE) / 2
  const testX = pair.cx + (Math.cos(radians) * CENTRE_DISTANCE) / 2
  const testY = pair.cy + (Math.sin(radians) * CENTRE_DISTANCE) / 2
  const reference = lineEnds(referenceX, referenceY, pair.referenceAngle, REFERENCE_LENGTH)
  const test = lineEnds(testX, testY, pair.referenceAngle + offset, pair.testLength)
  return (
    <div className="stage">
      <svg className="lot-board" viewBox="-320 -200 640 400">
        <rect x={-320} y={-200} width={640} height={400} fill="#d6d6d6" />
        <line {...reference} stroke="#111" strokeWidth={4} strokeLinecap="round" />
        <line {...test} stroke="#2f6fe0" strokeWidth={4} strokeLinecap="round" />
      </svg>
      <div className="answer-row">
        <button className="answer" onClick={function () { setOffset(offset - DEGREES_PER_CLICK) }}>↺</button>
        <button className="answer primary" onClick={done}>Done</button>
        <button className="answer" onClick={function () { setOffset(offset + DEGREES_PER_CLICK) }}>↻</button>
      </div>
      <div className="trial-counter">{index + 1} / {PAIR_COUNT}</div>
    </div>
  )
}
