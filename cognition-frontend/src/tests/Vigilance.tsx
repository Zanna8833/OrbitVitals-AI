import { useEffect, useMemo, useRef, useState } from 'react'
import { Random } from '../random'
import type { TestProps } from '../types'

// 3-minute PVT-B: millisecond counter at random 2-5 s intervals, reaction time shown for 1 s (Basner et al. 2021)
const DURATION_MS = 180000
const MIN_INTERVAL_MS = 2000
const MAX_INTERVAL_MS = 5000
const FEEDBACK_MS = 1000
// No response after this time: recorded as a missed stimulus (our choice)
const NO_RESPONSE_MS = 30000

type Phase = 'waiting' | 'counting' | 'feedback' | 'false-start'

export default function Vigilance(props: TestProps) {
  const random = useMemo(function () {
    return new Random(props.seed)
  }, [props.seed])
  const [phase, setPhase] = useState<Phase>('waiting')
  const [counter, setCounter] = useState(0)
  const stimuli = useRef<{ rt_ms: number | null }[]>([])
  const falseStarts = useRef(0)
  const startedAt = useRef(performance.now())
  const stimulusAt = useRef(0)
  const finished = useRef(false)

  function finishOrWait() {
    if (performance.now() - startedAt.current >= DURATION_MS) {
      if (!finished.current) {
        finished.current = true
        props.onFinish({ stimuli: stimuli.current, false_starts: falseStarts.current })
      }
      return
    }
    setPhase('waiting')
  }

  useEffect(function () {
    let timer = 0
    let frame = 0
    if (phase === 'waiting') {
      timer = window.setTimeout(function () {
        stimulusAt.current = performance.now()
        setCounter(0)
        setPhase('counting')
      }, random.int(MIN_INTERVAL_MS, MAX_INTERVAL_MS))
    } else if (phase === 'counting') {
      const tick = function () {
        const elapsed = performance.now() - stimulusAt.current
        setCounter(Math.round(elapsed))
        if (elapsed >= NO_RESPONSE_MS) {
          stimuli.current.push({ rt_ms: null })
          finishOrWait()
          return
        }
        frame = window.requestAnimationFrame(tick)
      }
      frame = window.requestAnimationFrame(tick)
    } else {
      timer = window.setTimeout(finishOrWait, FEEDBACK_MS)
    }
    return function () {
      window.clearTimeout(timer)
      window.cancelAnimationFrame(frame)
    }
  }, [phase])

  function press() {
    if (phase === 'counting') {
      const reactionTime = Math.round(performance.now() - stimulusAt.current)
      stimuli.current.push({ rt_ms: reactionTime })
      setCounter(reactionTime)
      setPhase('feedback')
    } else if (phase === 'waiting') {
      falseStarts.current = falseStarts.current + 1
      setPhase('false-start')
    }
  }

  useEffect(function () {
    function onKey(event: KeyboardEvent) {
      if (event.code === 'Space') {
        event.preventDefault()
        if (!event.repeat) {
          press()
        }
      }
    }
    window.addEventListener('keydown', onKey)
    return function () {
      window.removeEventListener('keydown', onKey)
    }
  })

  let content = ''
  if (phase === 'counting' || phase === 'feedback') {
    content = String(counter)
  } else if (phase === 'false-start') {
    content = 'FALSE START'
  }
  return (
    <div className="stage">
      <div className={'pvt-box ' + phase} onMouseDown={press}>{content}</div>
    </div>
  )
}
