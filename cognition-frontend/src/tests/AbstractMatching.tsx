import { useMemo, useRef, useState } from 'react'
import { Random } from '../random'
import { FIGURE_SHAPES, FigurePicture, SHADES } from '../stimuli'
import type { Figure, FigureShape } from '../stimuli'
import type { CorrectTrial, TestProps } from '../types'

// NASA TM-2020-5008023: pairs of figures (circles, triangles, hexagons, crosses, stars; light blue, dark blue or
// unfilled) at the bottom, one figure at the top centre; choose the pair that fits; feedback (green/red, always over
// the left-hand set) teaches a fixed set of five undisclosed rules over 30 trials.
// The five real rules are not published: these five, one per target shape, are our own.
const TRIAL_COUNT = 30
const FEEDBACK_MS = 800 // not given in the sources read, our choice

type Relation = 'shape' | 'shade' | 'neither'
const RULES: Record<FigureShape, Relation> = {
  circle: 'shape', // the right pair has the target's shape
  triangle: 'shade', // the right pair has the target's shade
  hexagon: 'shade',
  cross: 'neither', // the right pair shares neither shape nor shade with the target
  star: 'shape',
}

type Trial = { target: Figure; left: Figure[]; right: Figure[]; answerLeft: boolean }

function otherShape(random: Random, avoid: FigureShape): FigureShape {
  let shape = random.pick(FIGURE_SHAPES)
  while (shape === avoid) shape = random.pick(FIGURE_SHAPES)
  return shape
}

function otherShade(random: Random, avoid: string) {
  let shade = random.pick(SHADES)
  while (shade === avoid) shade = random.pick(SHADES)
  return shade
}

// Two figures related to the target in one way only
function makePair(random: Random, target: Figure, relation: Relation): Figure[] {
  const pair: Figure[] = []
  for (let i = 0; i < 2; i++) {
    if (relation === 'shape') {
      pair.push({ shape: target.shape, shade: otherShade(random, target.shade) })
    } else if (relation === 'shade') {
      pair.push({ shape: otherShape(random, target.shape), shade: target.shade })
    } else {
      pair.push({ shape: otherShape(random, target.shape), shade: otherShade(random, target.shade) })
    }
  }
  return pair
}

function makeTrials(random: Random): Trial[] {
  // 6 targets of each shape, in random order
  const targets: Figure[] = []
  for (const shape of FIGURE_SHAPES) {
    for (let i = 0; i < TRIAL_COUNT / FIGURE_SHAPES.length; i++) {
      targets.push({ shape: shape, shade: random.pick(SHADES) })
    }
  }
  const trials: Trial[] = []
  for (const target of random.shuffle(targets)) {
    const rule = RULES[target.shape]
    // The wrong pair follows one of the other relations, so both pairs always look plausible
    const others: Relation[] = []
    for (const relation of ['shape', 'shade', 'neither'] as Relation[]) {
      if (relation !== rule) others.push(relation)
    }
    const right = makePair(random, target, rule)
    const wrong = makePair(random, target, random.pick(others))
    if (random.next() < 0.5) {
      trials.push({ target: target, left: right, right: wrong, answerLeft: true })
    } else {
      trials.push({ target: target, left: wrong, right: right, answerLeft: false })
    }
  }
  return trials
}

export default function AbstractMatching(props: TestProps) {
  const trials = useMemo(function () {
    return makeTrials(new Random(props.seed))
  }, [props.seed])
  const [index, setIndex] = useState(0)
  const [feedback, setFeedback] = useState<'correct' | 'incorrect' | null>(null)
  const results = useRef<CorrectTrial[]>([])
  const shownAt = useRef(performance.now())

  function answer(left: boolean) {
    if (feedback !== null) return
    const correct = left === trials[index].answerLeft
    results.current.push({ rt_ms: Math.round(performance.now() - shownAt.current), correct: correct })
    setFeedback(correct ? 'correct' : 'incorrect')
    window.setTimeout(function () {
      if (index + 1 === TRIAL_COUNT) {
        props.onFinish({ trials: results.current })
        return
      }
      setFeedback(null)
      shownAt.current = performance.now()
      setIndex(index + 1)
    }, FEEDBACK_MS)
  }

  const trial = trials[index]
  let feedbackText = ''
  if (feedback === 'correct') feedbackText = 'Correct'
  if (feedback === 'incorrect') feedbackText = 'Incorrect'
  return (
    <div className="stage">
      <div className="am-target"><FigurePicture figure={trial.target} /></div>
      <div className="am-pairs">
        <div className="am-side">
          <div className={'am-feedback ' + (feedback === null ? '' : feedback)}>{feedbackText}</div>
          <button className="am-pair" onClick={function () { answer(true) }}>
            <FigurePicture figure={trial.left[0]} /><FigurePicture figure={trial.left[1]} />
          </button>
        </div>
        <div className="am-side">
          <div className="am-feedback" />
          <button className="am-pair" onClick={function () { answer(false) }}>
            <FigurePicture figure={trial.right[0]} /><FigurePicture figure={trial.right[1]} />
          </button>
        </div>
      </div>
      <div className="trial-counter">{index + 1} / {TRIAL_COUNT}</div>
    </div>
  )
}
