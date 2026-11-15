import { useEffect, useMemo, useRef, useState } from 'react'
import { Random } from '../random'
import { SYMBOL_PATHS, SymbolGlyph } from '../stimuli'
import type { CorrectTrial, TestProps } from '../types'

// One symbol at the top, legend of nine symbol-digit pairs at the bottom, answer with the number keys; about 90 s;
// legend re-assigned each session; the first three trials give feedback (NASA TM-2020-5008023; Basner et al. 2021)
const DURATION_MS = 90000
const FEEDBACK_TRIALS = 3
const FEEDBACK_MS = 600 // not given in the sources read, our choice

export default function DigitSymbol(props: TestProps) {
  const random = useMemo(function () {
    return new Random(props.seed)
  }, [props.seed])
  const legend = useMemo(function () {
    const indexes: number[] = []
    for (let i = 0; i < SYMBOL_PATHS.length; i++) {
      indexes.push(i)
    }
    // legend[digit - 1] = symbol index
    return random.shuffle(indexes).slice(0, 9)
  }, [random])
  const [targetDigit, setTargetDigit] = useState(function () {
    return random.int(1, 9)
  })
  const [feedback, setFeedback] = useState('')
  const [secondsLeft, setSecondsLeft] = useState(DURATION_MS / 1000)
  const trials = useRef<CorrectTrial[]>([])
  const startedAt = useRef(performance.now())
  const shownAt = useRef(performance.now())
  const finished = useRef(false)
  const waiting = useRef(false)

  useEffect(function () {
    const timer = window.setInterval(function () {
      const left = DURATION_MS - (performance.now() - startedAt.current)
      setSecondsLeft(Math.max(0, Math.ceil(left / 1000)))
      if (left <= 0 && !finished.current) {
        finished.current = true
        props.onFinish({ trials: trials.current })
      }
    }, 200)
    return function () {
      window.clearInterval(timer)
    }
  }, [])

  function nextSymbol() {
    let next = random.int(1, 9)
    while (next === targetDigit) {
      next = random.int(1, 9)
    }
    shownAt.current = performance.now()
    setTargetDigit(next)
  }

  function answer(digit: number) {
    if (finished.current || waiting.current) {
      return
    }
    const correct = digit === targetDigit
    trials.current.push({ rt_ms: Math.round(performance.now() - shownAt.current), correct: correct })
    if (trials.current.length <= FEEDBACK_TRIALS) {
      waiting.current = true
      setFeedback(correct ? 'Correct' : 'Incorrect')
      window.setTimeout(function () {
        waiting.current = false
        setFeedback('')
        nextSymbol()
      }, FEEDBACK_MS)
      return
    }
    nextSymbol()
  }

  useEffect(function () {
    function onKey(event: KeyboardEvent) {
      const digit = Number(event.key)
      if (digit >= 1 && digit <= 9) {
        answer(digit)
      }
    }
    window.addEventListener('keydown', onKey)
    return function () {
      window.removeEventListener('keydown', onKey)
    }
  })

  const key = []
  for (let digit = 1; digit <= 9; digit++) {
    // On touch screens the legend cells are the answer buttons
    key.push(
      <button key={digit} className="dsst-key-cell" onClick={function () { answer(digit) }}>
        <SymbolGlyph index={legend[digit - 1]} size={44} />
        <span>{digit}</span>
      </button>,
    )
  }
  let feedbackClass = 'dsst-feedback'
  if (feedback === 'Correct') feedbackClass = 'dsst-feedback correct'
  if (feedback === 'Incorrect') feedbackClass = 'dsst-feedback incorrect'
  return (
    <div className="stage">
      <div className="stimulus-box dsst-target"><SymbolGlyph index={legend[targetDigit - 1]} size={120} /></div>
      <div className={feedbackClass}>{feedback}</div>
      <div className="dsst-key">{key}</div>
      <div className="trial-counter">{secondsLeft} s</div>
    </div>
  )
}
