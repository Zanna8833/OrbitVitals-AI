import { useEffect, useMemo, useRef, useState } from 'react'
import { Random } from '../random'
import { WireObjectPicture, makeWireObject, wireObjectKey } from '../stimuli'
import type { WireObject } from '../stimuli'
import type { CorrectTrial, TestProps } from '../types'

// Learn 10 wireframe objects with one blue facet, 5 s each; then 20 objects (10 seen, 10 new): seen before?
// definitely / probably (NASA TM-2020-5008023; Basner et al. 2021)
const LEARN_COUNT = 10
const LEARN_MS = 5000

type Item = { object: WireObject; seen: boolean }

export default function VisualObjectLearning(props: TestProps) {
  const stimuli = useMemo(function () {
    const random = new Random(props.seed)
    const objects: WireObject[] = []
    const keys: string[] = []
    while (objects.length < 2 * LEARN_COUNT) {
      const object = makeWireObject(random)
      const key = wireObjectKey(object)
      if (keys.indexOf(key) === -1) {
        keys.push(key)
        objects.push(object)
      }
    }
    const learn = objects.slice(0, LEARN_COUNT)
    const test: Item[] = []
    for (let i = 0; i < objects.length; i++) {
      test.push({ object: objects[i], seen: i < LEARN_COUNT })
    }
    return { learn: learn, test: random.shuffle(test) }
  }, [props.seed])

  const [phase, setPhase] = useState<'learn' | 'test'>('learn')
  const [index, setIndex] = useState(0)
  const trials = useRef<CorrectTrial[]>([])
  const shownAt = useRef(performance.now())

  useEffect(function () {
    if (phase !== 'learn') {
      return
    }
    const timer = window.setTimeout(function () {
      if (index + 1 < LEARN_COUNT) {
        setIndex(index + 1)
      } else {
        setPhase('test')
        setIndex(0)
        shownAt.current = performance.now()
      }
    }, LEARN_MS)
    return function () {
      window.clearTimeout(timer)
    }
  }, [phase, index])

  function answer(saysSeen: boolean) {
    const item = stimuli.test[index]
    trials.current.push({ rt_ms: Math.round(performance.now() - shownAt.current), correct: saysSeen === item.seen })
    if (index + 1 === stimuli.test.length) {
      props.onFinish({ trials: trials.current })
      return
    }
    shownAt.current = performance.now()
    setIndex(index + 1)
  }

  if (phase === 'learn') {
    return (
      <div className="stage">
                <div className="stimulus-box"><WireObjectPicture object={stimuli.learn[index]} size={260} /></div>
        <div className="trial-counter">{index + 1} / {LEARN_COUNT}</div>
      </div>
    )
  }
  return (
    <div className="stage">
            <div className="stimulus-box"><WireObjectPicture object={stimuli.test[index].object} size={260} /></div>
      <div className="answer-row">
        <button className="answer" onClick={function () { answer(true) }}>Definitely yes</button>
        <button className="answer" onClick={function () { answer(true) }}>Probably yes</button>
        <button className="answer" onClick={function () { answer(false) }}>Probably no</button>
        <button className="answer" onClick={function () { answer(false) }}>Definitely no</button>
      </div>
      <div className="trial-counter">{index + 1} / {stimuli.test.length}</div>
    </div>
  )
}
