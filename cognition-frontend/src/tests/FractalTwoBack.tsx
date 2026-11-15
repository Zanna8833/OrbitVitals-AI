import { useEffect, useMemo, useRef, useState } from 'react'
import { Random } from '../random'
import { Fractal, makeFractal } from '../stimuli'
import type { FractalSpec } from '../stimuli'
import type { FractalTrial, TestProps } from '../types'

// 62 fractals shown for 1.75 s each, 15 of them match the one two before; the picture is switched off when the
// participant responds (NASA TM-2020-5008023; Basner et al. 2021)
const STIMULUS_COUNT = 62
const MATCH_COUNT = 15
const SHOW_MS = 1750
const FRACTAL_POOL = 8 // number of different pictures: not given in the sources read, our choice

export default function FractalTwoBack(props: TestProps) {
  const sequence = useMemo(function () {
    const random = new Random(props.seed)
    const pool: FractalSpec[] = []
    for (let i = 0; i < FRACTAL_POOL; i++) {
      pool.push(makeFractal(random))
    }
    const positions: number[] = []
    for (let i = 2; i < STIMULUS_COUNT; i++) {
      positions.push(i)
    }
    const matchPositions = random.shuffle(positions).slice(0, MATCH_COUNT)
    const order: number[] = []
    const matches: boolean[] = []
    for (let i = 0; i < STIMULUS_COUNT; i++) {
      if (matchPositions.indexOf(i) !== -1) {
        order.push(order[i - 2])
        matches.push(true)
      } else {
        let choice = random.int(0, FRACTAL_POOL - 1)
        while (i >= 2 && choice === order[i - 2]) {
          choice = random.int(0, FRACTAL_POOL - 1)
        }
        order.push(choice)
        matches.push(false)
      }
    }
    return { pool: pool, order: order, matches: matches }
  }, [props.seed])

  const [index, setIndex] = useState(0)
  const [hidden, setHidden] = useState(false)
  const trials = useRef<FractalTrial[]>([])
  const shownAt = useRef(performance.now())
  const response = useRef<number | null>(null)

  useEffect(function () {
    shownAt.current = performance.now()
    response.current = null
    const timer = window.setTimeout(function () {
      trials.current.push({ is_match: sequence.matches[index], responded: response.current !== null, rt_ms: response.current })
      if (index + 1 === STIMULUS_COUNT) {
        props.onFinish({ trials: trials.current })
        return
      }
      setHidden(false)
      setIndex(index + 1)
    }, SHOW_MS)
    return function () {
      window.clearTimeout(timer)
    }
  }, [index])

  function respond() {
    if (response.current !== null) {
      return
    }
    response.current = Math.round(performance.now() - shownAt.current)
    setHidden(true)
  }

  useEffect(function () {
    function onKey(event: KeyboardEvent) {
      if (event.code === 'Space') {
        event.preventDefault()
        respond()
      }
    }
    window.addEventListener('keydown', onKey)
    return function () {
      window.removeEventListener('keydown', onKey)
    }
  })

  return (
    <div className="stage">
      <div className="stimulus-box dark">
        {hidden ? <svg /> : <Fractal spec={sequence.pool[sequence.order[index]]} size={260} />}
      </div>
      <div className="answer-row">
        <button className="answer" onMouseDown={respond}>Same as 2 back</button>
      </div>
      <div className="trial-counter">{index + 1} / {STIMULUS_COUNT}</div>
    </div>
  )
}
