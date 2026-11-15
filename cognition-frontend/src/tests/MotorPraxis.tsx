import { useMemo, useRef, useState } from 'react'
import type { MouseEvent } from 'react'
import { Random } from '../random'
import type { MotorTrial, TestProps } from '../types'

// 20 squares, each smaller than the one before (Basner et al. 2015)
const SQUARE_COUNT = 20
const FIRST_SIZE = 90
const LAST_SIZE = 16
const ARENA_WIDTH = 720
const ARENA_HEIGHT = 440

type Square = { x: number; y: number; size: number }

export default function MotorPraxis(props: TestProps) {
  const squares = useMemo(function () {
    const random = new Random(props.seed)
    const list: Square[] = []
    for (let i = 0; i < SQUARE_COUNT; i++) {
      const size = FIRST_SIZE - ((FIRST_SIZE - LAST_SIZE) * i) / (SQUARE_COUNT - 1)
      const x = random.int(Math.ceil(size / 2) + 10, Math.floor(ARENA_WIDTH - size / 2 - 10))
      const y = random.int(Math.ceil(size / 2) + 10, Math.floor(ARENA_HEIGHT - size / 2 - 10))
      list.push({ x: x, y: y, size: size })
    }
    return list
  }, [props.seed])
  const [index, setIndex] = useState(0)
  const trials = useRef<MotorTrial[]>([])
  const shownAt = useRef(performance.now())

  function handleClick(event: MouseEvent<HTMLDivElement>) {
    const box = event.currentTarget.getBoundingClientRect()
    // The arena can be scaled on small screens: convert to arena pixels
    const x = ((event.clientX - box.left) * ARENA_WIDTH) / box.width
    const y = ((event.clientY - box.top) * ARENA_HEIGHT) / box.height
    const square = squares[index]
    const distance = Math.hypot(x - square.x, y - square.y)
    trials.current.push({ rt_ms: Math.round(performance.now() - shownAt.current), distance_px: Math.round(distance * 10) / 10 })
    if (index + 1 === SQUARE_COUNT) {
      props.onFinish({ trials: trials.current })
      return
    }
    shownAt.current = performance.now()
    setIndex(index + 1)
  }

  const square = squares[index]
  return (
    <div className="arena" style={{ aspectRatio: ARENA_WIDTH + ' / ' + ARENA_HEIGHT }} onMouseDown={handleClick}>
      <div className="mpt-square" style={{
        left: ((square.x - square.size / 2) / ARENA_WIDTH) * 100 + '%',
        top: ((square.y - square.size / 2) / ARENA_HEIGHT) * 100 + '%',
        width: (square.size / ARENA_WIDTH) * 100 + '%',
        height: (square.size / ARENA_HEIGHT) * 100 + '%',
      }} />
      <div className="trial-counter">{index + 1} / {SQUARE_COUNT}</div>
    </div>
  )
}
