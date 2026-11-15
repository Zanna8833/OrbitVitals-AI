import { useMemo, useRef, useState } from 'react'
import { Random } from '../random'
import type { Balloon, TestProps } from '../types'

// 30 balloons; 'inflate' adds $1 to the balloon or pops it, 'collect' moves it to the total winnings; the pop point
// follows a distribution the participant is not told, and its average changes between sessions
// (NASA TM-2020-5008023; Basner et al. 2021). The ranges below are our choice: the sources read do not give them.
const BALLOON_COUNT = 30
const MAX_POP_POINTS = [16, 24, 32]
const POINTS_PER_PUMP = 1
const POP_SHOW_MS = 900

export default function BalloonRisk(props: TestProps) {
  const popPoints = useMemo(function () {
    const random = new Random(props.seed)
    const maximum = random.pick(MAX_POP_POINTS)
    const list: number[] = []
    for (let i = 0; i < BALLOON_COUNT; i++) {
      list.push(random.int(1, maximum))
    }
    return list
  }, [props.seed])
  const [index, setIndex] = useState(0)
  const [pumps, setPumps] = useState(0)
  const [total, setTotal] = useState(0)
  const [popped, setPopped] = useState(false)
  const balloons = useRef<Balloon[]>([])
  const pumpTimes = useRef<number[]>([])
  const lastAction = useRef(performance.now())

  function nextBalloon(wasPopped: boolean, pumpCount: number) {
    balloons.current.push({ pumps: pumpCount, pop_point: popPoints[index], popped: wasPopped, pump_rts_ms: pumpTimes.current })
    pumpTimes.current = []
    if (index + 1 === BALLOON_COUNT) {
      props.onFinish({ balloons: balloons.current })
      return
    }
    setPumps(0)
    setPopped(false)
    setIndex(index + 1)
    lastAction.current = performance.now()
  }

  function pump() {
    if (popped) {
      return
    }
    pumpTimes.current.push(Math.round(performance.now() - lastAction.current))
    lastAction.current = performance.now()
    const count = pumps + 1
    setPumps(count)
    if (count >= popPoints[index]) {
      setPopped(true)
      window.setTimeout(function () {
        nextBalloon(true, count)
      }, POP_SHOW_MS)
    }
  }

  function collect() {
    if (popped) {
      return
    }
    setTotal(total + pumps * POINTS_PER_PUMP)
    nextBalloon(false, pumps)
  }

  const radius = 30 + pumps * 4
  return (
    <div className="stage">
      <svg className="bart-board" viewBox="0 0 400 340">
        {popped ? (
          <text x={200} y={180} textAnchor="middle" className="bart-pop">POP!</text>
        ) : (
          <g>
            <line x1={200} y1={300 - radius * 0.2} x2={200} y2={330} stroke="#8a8a8a" strokeWidth={2} />
            <ellipse cx={200} cy={300 - radius * 1.1} rx={radius} ry={radius * 1.1} fill="#2f6fe0" stroke="#8fb8f5" strokeWidth={2} />
                      </g>
        )}
      </svg>
      <div className="bart-info">
        <span>Balloon {index + 1} / {BALLOON_COUNT}</span>
        <span>Reward: ${pumps * POINTS_PER_PUMP}</span>
        <span>Total winnings: ${total}</span>
      </div>
      <div className="answer-row">
        <button className="answer primary" onClick={pump} disabled={popped}>Inflate</button>
        <button className="answer" onClick={collect} disabled={popped}>Collect</button>
      </div>
    </div>
  )
}
